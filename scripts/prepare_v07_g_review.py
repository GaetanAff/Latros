"""Prepare local, unreviewed v0.7-G mapping and assertion review sets.

All output is generated under ignored data/staging. No mapping or clinical status is changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb
import orjson
from audit_v07_general_quality import CONTENT_SHA256, SNAPSHOT, _prepare, _sample

from latros.common import LatrosError
from latros.knowledge.store_v2 import load_manifest_v2, snapshot_path_v2

CANDIDATE_SHA256 = "5eea9600f726e5306a07afb9405cce3f5795bd620c0efb9c53ae06d55b6ca704"
MEDLINE_RELEASE = "medlineplus:2026-09-19"
GENERIC_TERMS = {"pain", "severe", "mild", "healthy", "right", "left"}
SAMPLE_QUOTAS = (
    ("orl", 12),
    ("respiratoire", 12),
    ("urinaire", 12),
    ("rhumatologique", 12),
    ("medline_only_source", 16),
    ("generic_hpo_lexeme", 16),
    ("multiple_sources", 12),
    ("rare_or_genetic_linked", 12),
    ("other_medline", 16),
)


def _read_topics(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "WITH grouped AS (SELECT source_record_id, min(subject_text) AS subject_text, "
        "min(subject_mapping.status) AS mapping_status, "
        "min(subject_mapping.relation) AS mapping_relation, "
        "min(subject_mapping.code) AS mapping_code, count(*) AS candidate_count "
        "FROM candidate GROUP BY source_record_id) "
        "SELECT g.*, json_extract_string(r.payload_json,'$.raw_value.topic_id'), "
        "json_extract_string(r.payload_json,'$.raw_value.title'), "
        "json_extract(r.payload_json,'$.raw_value.synonyms')::VARCHAR, "
        "json_extract(r.payload_json,'$.raw_value.mesh_headings')::VARCHAR, "
        "json_extract_string(r.payload_json,'$.raw_value.url'), "
        "json_extract_string(r.payload_json,'$.record_locator'), "
        "json_extract(r.payload_json,'$.artifact_ids')::VARCHAR "
        "FROM grouped g JOIN source_record r ON r.id=g.source_record_id "
        "ORDER BY g.source_record_id"
    ).fetchall()
    topics = []
    for row in rows:
        synonyms = orjson.loads(row[8]) if row[8] else []
        mesh = orjson.loads(row[9]) if row[9] else []
        topics.append(
            {
                "source_record_id": row[0],
                "source_label": row[1],
                "mapping_status": row[2],
                "mapping_relation": row[3],
                "mapping_code": row[4],
                "candidate_count": row[5],
                "topic_id": row[6],
                "title": row[7],
                "synonyms": synonyms,
                "mesh_headings": mesh,
                "url": row[10],
                "locator": row[11],
                "artifact_ids": orjson.loads(row[12]) if row[12] else [],
            }
        )
    return topics


def _normalize_label(value: str) -> str:
    import re
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value))


def _suggestions(
    connection: duckdb.DuckDBPyConnection, topics: list[dict[str, Any]]
) -> dict[str, list[dict[str, str]]]:
    blocked = [topic for topic in topics if topic["mapping_status"] != "resolved"]
    connection.execute(
        "CREATE TEMP TABLE review_terms(topic_id VARCHAR, norm VARCHAR, origin VARCHAR)"
    )
    terms = []
    for topic in blocked:
        for origin, label in [
            ("title", topic["title"]),
            *[("synonym", s) for s in topic["synonyms"]],
        ]:
            normalized = _normalize_label(label)
            if normalized:
                terms.append((topic["topic_id"], normalized, origin))
    connection.executemany("INSERT INTO review_terms VALUES (?,?,?)", terms)
    connection.execute("CREATE TEMP TABLE review_mesh(topic_id VARCHAR, mesh_code VARCHAR)")
    mesh_rows = [
        (topic["topic_id"], "MESH:" + heading["descriptor_id"].removeprefix("MESH:"))
        for topic in blocked
        for heading in topic["mesh_headings"]
    ]
    if mesh_rows:
        connection.executemany("INSERT INTO review_mesh VALUES (?,?)", mesh_rows)
    lexical = connection.execute(
        "WITH disease_labels AS (SELECT c.code, c.id, "
        "json_extract_string(d.payload_json,'$.text') AS label, "
        "trim(regexp_replace(lower(strip_accents(json_extract_string(d.payload_json,'$.text'))),"
        "'[^a-z0-9]+',' ','g')) AS norm "
        "FROM designation d JOIN concepts c ON c.id="
        "json_extract_string(d.payload_json,'$.concept_id') "
        "WHERE c.kind='condition' AND c.status='active' "
        "AND (c.code LIKE 'MONDO:%' OR c.code LIKE 'DOID:%')) "
        "SELECT DISTINCT t.topic_id,l.code,l.label,t.origin FROM review_terms t "
        "JOIN disease_labels l ON l.norm=t.norm ORDER BY t.topic_id,l.code,t.origin,l.label"
    ).fetchall()
    mesh = connection.execute(
        "SELECT DISTINCT t.topic_id,c.code,coalesce(l.label_text,c.code), "
        "json_extract_string(m.payload_json,'$.target_code') AS mesh_code, "
        "json_extract_string(m.payload_json,'$.relation') AS relation, "
        "json_extract_string(m.payload_json,'$.resolution_status') AS status "
        "FROM review_mesh t JOIN concept_mapping m ON "
        "json_extract_string(m.payload_json,'$.target_code')=t.mesh_code "
        "JOIN concepts c ON c.id=json_extract_string(m.payload_json,'$.source_concept_id') "
        "LEFT JOIN labels l ON l.concept_id=c.id "
        "WHERE c.kind='condition' AND c.status='active' "
        "AND (c.code LIKE 'MONDO:%' OR c.code LIKE 'DOID:%') "
        "ORDER BY t.topic_id,c.code,mesh_code"
    ).fetchall()
    suggestions: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for topic_id, code, label, origin in lexical:
        item = suggestions[topic_id].setdefault(
            code, {"code": code, "label": label, "lexical_basis": "", "mesh_basis": ""}
        )
        item["lexical_basis"] = ", ".join(
            sorted(set(filter(None, [item["lexical_basis"], origin])))
        )
    for topic_id, code, label, mesh_code, relation, status in mesh:
        item = suggestions[topic_id].setdefault(
            code, {"code": code, "label": label, "lexical_basis": "", "mesh_basis": ""}
        )
        basis = f"{mesh_code} ({relation}/{status})"
        item["mesh_basis"] = ", ".join(sorted(set(filter(None, [item["mesh_basis"], basis]))))
    return {key: [values[code] for code in sorted(values)] for key, values in suggestions.items()}


def _g1_rows(
    topics: list[dict[str, Any]], suggestions: dict[str, list[dict[str, str]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for topic in topics:
        if topic["mapping_status"] == "resolved":
            continue
        options = suggestions.get(topic["topic_id"], []) or [
            {"code": "", "label": "", "lexical_basis": "", "mesh_basis": ""}
        ]
        for option in options:
            basis = []
            if option["lexical_basis"]:
                basis.append("désignation identique : " + option["lexical_basis"])
            if option["mesh_basis"]:
                basis.append("xref MeSH non résolu : " + option["mesh_basis"])
            rows.append(
                {
                    "topic_id": topic["topic_id"],
                    "topic_title": topic["title"],
                    "disease_source_label": topic["source_label"],
                    "synonyms": "; ".join(topic["synonyms"]),
                    "mesh_ids": "; ".join(
                        heading["descriptor_id"] for heading in topic["mesh_headings"]
                    ),
                    "candidate_assertions_blocked": topic["candidate_count"],
                    "current_mapping_status": topic["mapping_status"],
                    "current_mapping_relation": topic["mapping_relation"],
                    "candidate_disease_code": option["code"],
                    "candidate_disease_label": option["label"],
                    "hypothesis_type": (
                        "lexical_plus_mesh_review"
                        if option["lexical_basis"] and option["mesh_basis"]
                        else "lexical_review"
                        if option["lexical_basis"]
                        else "mesh_xref_unresolved"
                        if option["mesh_basis"]
                        else "no_candidate_identified"
                    ),
                    "technical_justification": "; ".join(basis),
                    "source_release": MEDLINE_RELEASE,
                    "source_record_id": topic["source_record_id"],
                    "source_locator": topic["locator"],
                    "source_url": topic["url"],
                    "artifact_ids": "; ".join(topic["artifact_ids"]),
                    "review_status": "pending_human_mapping_review",
                    "human_mapping_decision": "",
                    "human_reviewer_id": "",
                    "human_review_note": "",
                }
            )
    return rows


def _eligible_candidates(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    query = (
        "SELECT candidate_assertion_id,source_record_id,source_locator,artifact_sha256,"
        "subject_text,object_text,predicate,polarity,subject_mapping,object_mapping,"
        "extraction,evidence_family,dependency_group,review_status "
        "FROM candidate WHERE subject_mapping.status='resolved' "
        "AND object_mapping.status='resolved' "
        "AND subject_mapping.relation IN ('exact','equivalent') "
        "AND object_mapping.relation IN ('exact','equivalent') "
        "ORDER BY candidate_assertion_id"
    )
    keys = (
        "candidate_id",
        "source_record_id",
        "locator",
        "artifact_sha256",
        "disease_label",
        "finding_label",
        "relation",
        "polarity",
        "subject_mapping",
        "object_mapping",
        "extraction",
        "evidence_family",
        "dependency_group",
        "review_status",
    )
    return [dict(zip(keys, row, strict=True)) for row in connection.execute(query).fetchall()]


def _g2_rows(
    connection: duckdb.DuckDBPyConnection, topics: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    by_record = {item["source_record_id"]: item for item in topics}
    domains: dict[str, set[str]] = defaultdict(set)
    for concept_id, domain in connection.execute(
        "SELECT disease_id,domain FROM domain_assignment"
    ).fetchall():
        domains[concept_id].add(domain)
    audit_classes = dict(
        connection.execute("SELECT disease_id,audit_class FROM disease_class").fetchall()
    )
    medline_only = {
        row[0]
        for row in connection.execute(
            "SELECT disease_id FROM sa GROUP BY disease_id "
            "HAVING count(DISTINCT source_release)=1 AND min(source_release)=?",
            [MEDLINE_RELEASE],
        ).fetchall()
    }
    multi_source = {
        row[0]
        for row in connection.execute(
            "SELECT disease_id FROM sa GROUP BY disease_id HAVING count(DISTINCT source_release)>1"
        ).fetchall()
    }
    eligible = _eligible_candidates(connection)
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in eligible:
        concept_id = item["subject_mapping"]["concept_id"]
        for domain in ("ORL", "respiratoire", "urinaire", "rhumatologique"):
            if domain in domains.get(concept_id, set()):
                pools[domain.casefold()].append(item)
        if concept_id in medline_only:
            pools["medline_only_source"].append(item)
        if _normalize_label(item["finding_label"]) in GENERIC_TERMS:
            pools["generic_hpo_lexeme"].append(item)
        if concept_id in multi_source:
            pools["multiple_sources"].append(item)
        if audit_classes.get(concept_id) == "rare_or_genetic_linked":
            pools["rare_or_genetic_linked"].append(item)
        pools["other_medline"].append(item)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    coverage: dict[str, int] = {}
    for stratum, quota in SAMPLE_QUOTAS:
        pool = sorted(
            pools[stratum],
            key=lambda item: (
                hashlib.sha256(item["candidate_id"].encode()).hexdigest(),
                item["candidate_id"],
            ),
        )
        chosen = [item for item in pool if item["candidate_id"] not in seen][:quota]
        coverage[stratum] = len(chosen)
        for item in chosen:
            seen.add(item["candidate_id"])
            disease_id = item["subject_mapping"]["concept_id"]
            topic = by_record[item["source_record_id"]]
            selected.append(
                {
                    "review_stratum": stratum,
                    "candidate_assertion_id": item["candidate_id"],
                    "topic_id": topic["topic_id"],
                    "topic_title": topic["title"],
                    "disease_label": item["disease_label"],
                    "disease_code": item["subject_mapping"]["code"],
                    "finding_label": item["finding_label"],
                    "finding_code": item["object_mapping"]["code"],
                    "relation": item["relation"],
                    "polarity": item["polarity"],
                    "audit_class": audit_classes.get(disease_id, "unclassified"),
                    "domains": "; ".join(sorted(domains.get(disease_id, set()))),
                    "subject_mapping_provenance": item["subject_mapping"]["provenance"],
                    "object_mapping_provenance": item["object_mapping"]["provenance"],
                    "extractor": item["extraction"]["extractor_id"],
                    "source_release": MEDLINE_RELEASE,
                    "source_record_id": item["source_record_id"],
                    "source_locator": item["locator"],
                    "source_url": topic["url"],
                    "artifact_sha256": "; ".join(item["artifact_sha256"]),
                    "evidence_family": item["evidence_family"],
                    "dependency_group": item["dependency_group"],
                    "review_status": item["review_status"],
                    "human_assertion_decision": "",
                    "human_reviewer_id": "",
                    "human_review_note": "",
                }
            )
    return selected, coverage, len(eligible)


def _dependency_rows(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    picked = [
        item
        for item in _sample(connection)
        if item.get("source_release") in {"monarch:2026-09-02", "orphadata:2026-07"}
    ]
    rows: list[dict[str, Any]] = []
    for item in picked:
        source = connection.execute(
            "SELECT payload_json FROM source_assertion WHERE id=?",
            [item["source_assertion_id"]],
        ).fetchone()
        if source is None:
            raise LatrosError("Selected source assertion is absent")
        raw = orjson.loads(source[0])["raw_value"]
        rows.append(
            {
                "review_stratum": item["sample_stratum"],
                "source_assertion_id": item["source_assertion_id"],
                "disease_code": item["disease"],
                "disease_label": item["disease_label"],
                "finding_code": item["finding"],
                "finding_label": item["finding_label"],
                "relation": item["relation"],
                "polarity": item["polarity"],
                "source_release": item["source_release"],
                "source_record_id": item["source_record_id"],
                "source_locator": item["locator"],
                "primary_knowledge_source": raw.get("primary_knowledge_source", ""),
                "aggregator_knowledge_source": raw.get("aggregator_knowledge_source", ""),
                "evidence_family": item["evidence_family"],
                "dependency_type": item["dependency"]["type"],
                "dependency_primary_reference": item["dependency"]["primary_reference"],
                "artifact_ids": "; ".join(item["artifact_ids"]),
                "audit_class": item["audit_class"],
                "review_status": item["review_status"],
                "human_provenance_decision": "",
                "human_reviewer_id": "",
                "human_review_note": "",
            }
        )
    return rows


def _csv_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip()[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def _write_without_overwriting_review(path: Path, content: bytes) -> str:
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise LatrosError(f"Existing review output differs; refusing to overwrite: {path}")
    else:
        with path.open("xb") as stream:
            stream.write(content)
    return hashlib.sha256(content).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise LatrosError(f"Review set is empty: {path.name}")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: _csv_value(value) for key, value in row.items()} for row in rows)
    return _write_without_overwriting_review(path, stream.getvalue().encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output_dir or root / "data/staging/v0.7-g").resolve()
    staging = (root / "data/staging").resolve()
    if output != staging and staging not in output.parents:
        raise LatrosError("Review outputs must stay under data/staging")
    manifest = load_manifest_v2(root, SNAPSHOT)
    if (
        manifest.content_sha256 != CONTENT_SHA256
        or manifest.clinical_validation
        or manifest.publishable
        or manifest.validation_status != "unreviewed"
    ):
        raise LatrosError("The immutable unreviewed snapshot contract has changed")
    candidates = root / "data/staging/general" / SNAPSHOT / "candidate_assertions.jsonl"
    if not candidates.is_file():
        raise LatrosError("Pinned MedlinePlus candidate staging file is absent")
    with candidates.open("rb") as stream:
        actual_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_sha256 != CANDIDATE_SHA256:
        raise LatrosError("MedlinePlus candidates differ from the G0-audited file")
    with duckdb.connect(str(snapshot_path_v2(root, SNAPSHOT)), read_only=True) as connection:
        _prepare(connection, candidates)
        topics = _read_topics(connection)
        suggestions = _suggestions(connection, topics)
        g1 = _g1_rows(topics, suggestions)
        g2, quotas, eligible_count = _g2_rows(connection, topics)
        dependencies = _dependency_rows(connection)
    blocked_topics = [item for item in topics if item["mapping_status"] != "resolved"]
    if (
        len(topics) != 946
        or len(blocked_topics) != 689
        or sum(item["candidate_count"] for item in topics) != 7736
        or sum(item["candidate_count"] for item in blocked_topics) != 5106
        or eligible_count != 2630
        or len(g2) != 120
        or len(dependencies) != 40
    ):
        raise LatrosError("The MedlinePlus review population differs from G0")
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "g1-mapping-review.csv": g1,
        "g2-medline-assertion-review.csv": g2,
        "g2-upstream-dependency-review.csv": dependencies,
    }
    hashes = {name: _write_csv(output / name, rows) for name, rows in files.items()}
    summary = {
        "snapshot": SNAPSHOT,
        "snapshot_sha256": CONTENT_SHA256,
        "candidate_file_sha256": actual_sha256,
        "topics_with_candidates": len(topics),
        "blocked_topics": len(blocked_topics),
        "blocked_candidate_assertions": 5106,
        "technically_eligible_candidates": eligible_count,
        "mapping_review_rows": len(g1),
        "topics_with_hypothesis": len(
            {row["topic_id"] for row in g1 if row["hypothesis_type"] != "no_candidate_identified"}
        ),
        "mapping_hypotheses": dict(Counter(row["hypothesis_type"] for row in g1)),
        "medline_assertion_review_rows": len(g2),
        "medline_sample_by_stratum": quotas,
        "upstream_dependency_review_rows": len(dependencies),
        "medline_negative_assertions": 0,
        "human_decisions_recorded": 0,
        "files_sha256": hashes,
    }
    _write_without_overwriting_review(
        output / "summary.json",
        orjson.dumps(summary, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2) + b"\n",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
