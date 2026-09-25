"""Build an experimental, unreviewed MedlinePlus candidate set entirely offline.

The historical v0.7 snapshot and G2 exports are read-only. All new artifacts
remain ignored under data/staging and cannot overwrite annotated review files.
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
from audit_v07_general_quality import _prepare
from replay_v07_medlineplus_candidates import (
    BASELINE_SHA256,
    CONTENT_SHA256,
    SNAPSHOT,
    replay,
)

from latros.common import LatrosError, sha256
from latros.knowledge.candidates import CandidateAssertion, ExtractionProvenance
from latros.knowledge.general_factory import _candidate_rejection, _normalize
from latros.knowledge.medlineplus import parse_medlineplus_topics
from latros.knowledge.medlineplus_quality import (
    classify_candidate,
    load_condition_terms,
    locator_parts,
)
from latros.knowledge.store_v2 import snapshot_path_v2

EXTRACTOR_ID = "latros.medlineplus.exact-term-context"
EXTRACTOR_VERSION = "2"
G2_FIELDS = (
    "candidate_assertion_id",
    "topic_id",
    "topic_title",
    "disease_label",
    "finding_label",
    "relation",
    "polarity",
    "source_locator",
    "source_url",
    "source_release_id",
    "source_record_id",
    "artifact_sha256",
    "subject_mapping_status",
    "subject_mapping_relation",
    "subject_mapping_code",
    "subject_concept_id",
    "object_mapping_status",
    "object_mapping_relation",
    "object_mapping_code",
    "object_concept_id",
    "evidence_family",
    "dependency_group",
    "auto_filter_decision",
    "auto_filter_rule",
    "source_section",
    "source_context",
    "resulting_candidate_id",
    "review_status",
    "human_assertion_decision",
    "human_reviewer_id",
    "human_review_note",
)


def _write_once(path: Path, value: bytes) -> str:
    if path.exists():
        if path.read_bytes() != value:
            raise LatrosError(f"Refusing to overwrite modified G4 output: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    return hashlib.sha256(value).hexdigest()


def _jsonl(items: list[dict[str, Any]]) -> bytes:
    return b"".join(orjson.dumps(item, option=orjson.OPT_SORT_KEYS) + b"\n" for item in items)


def _csv(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode("utf-8")


def _mapping_counts(candidates: list[CandidateAssertion]) -> dict[str, int]:
    counts = Counter(
        _candidate_rejection(item) for item in candidates if not item.technically_eligible
    )
    return dict(sorted(counts.items()))


def _coverage(candidates: list[CandidateAssertion], medline_only: set[str]) -> dict[str, Any]:
    eligible = [item for item in candidates if item.technically_eligible]
    diseases = {
        item.subject_mapping.concept_id
        for item in eligible
        if item.subject_mapping is not None and item.subject_mapping.concept_id is not None
    }
    return {
        "total": len(candidates),
        "technically_eligible": len(eligible),
        "mapping_rejected": len(candidates) - len(eligible),
        "mapping_rejection_reasons": _mapping_counts(candidates),
        "positive": sum(item.polarity == "present" for item in candidates),
        "negative": sum(item.polarity == "excluded" for item in candidates),
        "unique_finding_codes": len(
            {
                item.object_mapping.code
                for item in candidates
                if item.object_mapping is not None and item.object_mapping.status == "resolved"
            }
        ),
        "eligible_diseases": len(diseases),
        "eligible_medline_only_diseases": len(diseases & medline_only),
        "top_eligible_hpo": Counter(
            item.object_mapping.code for item in eligible if item.object_mapping is not None
        ).most_common(20),
    }


def _domains(
    candidates: list[CandidateAssertion], assignments: dict[str, set[str]]
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in candidates:
        if not item.technically_eligible or item.subject_mapping is None:
            continue
        for domain in assignments.get(item.subject_mapping.concept_id or "", {"unclassified"}):
            counts[domain] += 1
    return dict(sorted(counts.items()))


def _sample(
    candidates: list[CandidateAssertion], assignments: dict[str, set[str]]
) -> list[CandidateAssertion]:
    eligible = [item for item in candidates if item.technically_eligible]
    eligible.sort(key=lambda item: hashlib.sha256(item.candidate_assertion_id.encode()).hexdigest())
    selected: list[CandidateAssertion] = []
    used: set[str] = set()
    per_topic: Counter[str] = Counter()
    for domain in ("ORL", "respiratoire", "urinaire", "rhumatologique"):
        count = 0
        for item in eligible:
            topic_id, _ = locator_parts(item)
            concept_id = item.subject_mapping.concept_id if item.subject_mapping else ""
            if (
                item.candidate_assertion_id not in used
                and domain in assignments.get(concept_id or "", set())
                and per_topic[topic_id] < 3
            ):
                selected.append(item)
                used.add(item.candidate_assertion_id)
                per_topic[topic_id] += 1
                count += 1
                if count == 12:
                    break
    for item in eligible:
        if len(selected) == 120:
            break
        topic_id, _ = locator_parts(item)
        if item.candidate_assertion_id not in used and per_topic[topic_id] < 3:
            selected.append(item)
            used.add(item.candidate_assertion_id)
            per_topic[topic_id] += 1
    return selected


def build(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    staging = (root / "data/staging").resolve()
    destination = (root / output_dir).resolve()
    if not destination.is_relative_to(staging):
        raise ValueError("G4 output must stay under data/staging")
    candidates = replay(root)
    condition_terms = load_condition_terms(snapshot_path_v2(root, SNAPSHOT))
    topics = {
        item.topic_id: item
        for item in parse_medlineplus_topics(
            root / "data/raw/medlineplus/2026-09-19/mplus_topics_compressed_2026-09-19.zip"
        )
    }
    phrases: dict[tuple[str, int], set[str]] = defaultdict(set)
    for item in candidates:
        topic_id, summary_index = locator_parts(item)
        phrases[(topic_id, summary_index)].add(_normalize(item.object_text))
    original_g2 = root / "data/staging/v0.7-g/g2-medline-assertion-review.csv"
    with original_g2.open(encoding="utf-8", newline="") as handle:
        g2_rows = list(csv.DictReader(handle))
    if len(g2_rows) != 120 or len({row["candidate_assertion_id"] for row in g2_rows}) != 120:
        raise LatrosError("G4 requires the pinned 120-row original G2 sample")
    old_by_id = {item.candidate_assertion_id: item for item in candidates}
    if any(row["candidate_assertion_id"] not in old_by_id for row in g2_rows):
        raise LatrosError("Original G2 sample is not aligned with the pinned candidates")

    with duckdb.connect(str(snapshot_path_v2(root, SNAPSHOT)), read_only=True) as connection:
        _prepare(
            connection,
            root / "data/staging/general" / SNAPSHOT / "candidate_assertions.jsonl",
        )
        assignments: dict[str, set[str]] = defaultdict(set)
        for concept_id, domain in connection.execute(
            "SELECT disease_id,domain FROM domain_assignment"
        ).fetchall():
            assignments[concept_id].add(domain)
        medline_only = {
            row[0]
            for row in connection.execute(
                "SELECT disease_id FROM sa GROUP BY disease_id "
                "HAVING count(DISTINCT source_release)=1 "
                "AND min(source_release)='medlineplus:2026-09-19'"
            ).fetchall()
        }

    after: list[CandidateAssertion] = []
    decisions: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    for item in sorted(candidates, key=lambda value: value.candidate_assertion_id):
        topic_id, summary_index = locator_parts(item)
        decision = classify_candidate(
            item,
            topics[topic_id],
            other_phrases=phrases[(topic_id, summary_index)],
            condition_terms=condition_terms,
        )
        status_counts[decision.status] += 1
        rule_counts[decision.rule_id] += 1
        signal_counts.update(decision.signals)
        if decision.status == "auto_keep":
            updated = CandidateAssertion.model_validate(
                item.model_copy(
                    update={
                        "extraction": ExtractionProvenance(
                            extractor_id=EXTRACTOR_ID,
                            extractor_version=EXTRACTOR_VERSION,
                            method="rule_based",
                        ),
                        "transformation_chain": [
                            *item.transformation_chain,
                            f"visible-context quality filter {EXTRACTOR_VERSION}",
                        ],
                    }
                ).model_dump(mode="json")
            )
            after.append(updated)
        row = {
            "candidate_assertion_id": item.candidate_assertion_id,
            "topic_id": topic_id,
            "topic_title": topics[topic_id].title,
            "disease_label": item.subject_text,
            "finding_label": item.object_text,
            "relation": item.predicate,
            "polarity": item.polarity,
            "source_locator": item.source_locator,
            "source_url": topics[topic_id].url,
            "source_release_id": item.source_release_id,
            "source_record_id": item.source_record_id,
            "artifact_sha256": "|".join(item.artifact_sha256),
            "subject_mapping_status": item.subject_mapping.status if item.subject_mapping else "",
            "subject_mapping_relation": item.subject_mapping.relation
            if item.subject_mapping
            else "",
            "object_mapping_status": item.object_mapping.status if item.object_mapping else "",
            "object_mapping_relation": item.object_mapping.relation if item.object_mapping else "",
            "subject_mapping_code": item.subject_mapping.code if item.subject_mapping else "",
            "subject_concept_id": (item.subject_mapping.concept_id if item.subject_mapping else ""),
            "object_mapping_code": item.object_mapping.code if item.object_mapping else "",
            "object_concept_id": item.object_mapping.concept_id if item.object_mapping else "",
            "evidence_family": item.evidence_family,
            "dependency_group": item.dependency_group,
            "auto_filter_decision": decision.status,
            "auto_filter_rule": decision.rule_id,
            "source_section": decision.section,
            "source_context": decision.context[:400],
            "resulting_candidate_id": item.candidate_assertion_id
            if decision.status == "auto_keep"
            else "",
            "review_status": item.review_status,
            "human_assertion_decision": "",
            "human_reviewer_id": "",
            "human_review_note": "",
            "signals": list(decision.signals),
        }
        decisions.append(row)
        by_id[item.candidate_assertion_id] = row

    before_after = [
        {
            **row,
            "auto_filter_decision": by_id[row["candidate_assertion_id"]]["auto_filter_decision"],
            "auto_filter_rule": by_id[row["candidate_assertion_id"]]["auto_filter_rule"],
            "source_section": by_id[row["candidate_assertion_id"]]["source_section"],
            "source_context": by_id[row["candidate_assertion_id"]]["source_context"],
            "resulting_candidate_id": by_id[row["candidate_assertion_id"]][
                "resulting_candidate_id"
            ],
        }
        for row in g2_rows
    ]
    sample_rows = [by_id[item.candidate_assertion_id] for item in _sample(after, assignments)]
    if len(sample_rows) != 120:
        raise LatrosError("G4 could not construct a 120-row deterministic after sample")
    controls = {
        ("Tonsillitis", "right"): "reject_from_auto_extraction",
        ("Common Cold", "chronic"): "reject_from_auto_extraction",
        ("Sinusitis", "acute"): "reject_from_auto_extraction",
        ("Sinusitis", "recurrent"): "reject_from_auto_extraction",
        ("Nasal Cancer", "cancer"): "reject_from_auto_extraction",
        ("Tonsillitis", "fever"): "auto_keep",
        ("Common Cold", "runny nose"): "auto_keep",
        ("Motion Sickness", "nausea and vomiting"): "auto_keep",
        ("Motion Sickness", "dizziness"): "auto_keep",
        ("Ankylosing Spondylitis", "crohn s disease"): "needs_human_review",
        ("Ankylosing Spondylitis", "psoriasis"): "needs_human_review",
    }
    verified_controls: dict[str, str] = {}
    for (topic, finding), expected in controls.items():
        matches = [
            row
            for row in decisions
            if row["topic_title"] == topic and row["finding_label"] == finding
        ]
        if len(matches) != 1 or matches[0]["auto_filter_decision"] != expected:
            raise LatrosError(f"G4 verified source control changed: {topic} / {finding}")
        verified_controls[f"{topic} -> {finding}"] = expected

    after.sort(key=lambda item: item.candidate_assertion_id)
    files = {
        "candidate_assertions_v2.jsonl": _jsonl([item.model_dump(mode="json") for item in after]),
        "candidate_decisions.jsonl": _jsonl(decisions),
        "g2-before-after.csv": _csv(
            before_after,
            (
                *tuple(g2_rows[0]),
                "auto_filter_decision",
                "auto_filter_rule",
                "source_section",
                "source_context",
                "resulting_candidate_id",
            ),
        ),
        "g2-after-review.csv": _csv(sample_rows, G2_FIELDS),
    }
    hashes = {name: _write_once(destination / name, value) for name, value in files.items()}
    metrics = {
        "snapshot": SNAPSHOT,
        "snapshot_sha256": CONTENT_SHA256,
        "medlineplus_raw_sha256": sha256(
            root / "data/raw/medlineplus/2026-09-19/mplus_topics_compressed_2026-09-19.zip"
        ),
        "historical_candidate_sha256": BASELINE_SHA256,
        "extractor_id": EXTRACTOR_ID,
        "extractor_version": EXTRACTOR_VERSION,
        "before": _coverage(candidates, medline_only),
        "after_auto_keep": _coverage(after, medline_only),
        "before_domains_eligible": _domains(candidates, assignments),
        "after_domains_eligible": _domains(after, assignments),
        "auto_filter_statuses": dict(sorted(status_counts.items())),
        "auto_filter_primary_rules": dict(sorted(rule_counts.items())),
        "audit_signals_overlapping": dict(sorted(signal_counts.items())),
        "g2_original_sample_impact": dict(
            sorted(Counter(row["auto_filter_decision"] for row in before_after).items())
        ),
        "g2_after_sample_size": len(sample_rows),
        "source_verified_controls": verified_controls,
        "new_negative_assertions": 0,
        "clinically_approved_assertions": 0,
        "outputs_sha256": hashes,
        "limitations": [
            "Technical context filtering is not clinical validation.",
            "Quarantined candidates require qualified human review before any use.",
            "No candidate is automatically approved or promoted into the immutable snapshot.",
        ],
    }
    _write_once(
        destination / "metrics.json",
        (json.dumps(metrics, indent=2, sort_keys=True) + "\n").encode(),
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/staging/v0.7-g4/quality-v2-experimental")
    )
    args = parser.parse_args()
    metrics = build(args.root, args.output_dir)
    print(
        json.dumps(
            {
                key: metrics[key]
                for key in (
                    "before",
                    "after_auto_keep",
                    "auto_filter_statuses",
                    "g2_original_sample_impact",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
