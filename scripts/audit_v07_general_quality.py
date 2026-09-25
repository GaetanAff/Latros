"""Audit the immutable v0.7 general snapshot with bounded DuckDB queries.

The report data and review sample are local generated files under data/staging.
No clinical decision or source artifact is written to the repository.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
import orjson

from latros.common import LatrosError
from latros.knowledge.store_v2 import load_manifest_v2, snapshot_path_v2

SNAPSHOT = "v0.7.0-general-dev-unreviewed"
CONTENT_SHA256 = "bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0"
DOMAINS = (
    ("respiratoire", "MONDO:0005087"),
    ("ORL", "MONDO:0024623"),
    ("digestif", "MONDO:0004335"),
    ("cardiovasculaire", "MONDO:0004995"),
    ("neurologique", "MONDO:0005071"),
    ("dermatologique", "MONDO:0005093"),
    ("endocrinien", "MONDO:0005151"),
    ("urinaire", "MONDO:0002118"),
    ("rhumatologique", "MONDO:0005554"),
    ("musculosquelettique", "MONDO:0002081"),
)


def _rows(
    connection: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> list[tuple[Any, ...]]:
    return connection.execute(sql, params or []).fetchall()


def _counts(connection: duckdb.DuckDBPyConnection, sql: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in _rows(connection, sql)}


def _prepare(connection: duckdb.DuckDBPyConnection, candidates: Path) -> None:
    connection.execute("SET threads=2")
    connection.execute(
        "CREATE TEMP TABLE concepts AS SELECT id, "
        "json_extract_string(payload_json, '$.primary_code') AS code, "
        "json_extract_string(payload_json, '$.kind') AS kind, "
        "json_extract_string(payload_json, '$.status') AS status FROM concept"
    )
    connection.execute(
        "CREATE TEMP TABLE labels AS SELECT "
        "json_extract_string(payload_json, '$.concept_id') AS concept_id, "
        "json_extract_string(payload_json, '$.text') AS label_text FROM designation "
        "QUALIFY row_number() OVER (PARTITION BY concept_id ORDER BY "
        "json_extract_string(payload_json, '$.scope')!='preferred', "
        "json_extract_string(payload_json, '$.language')!='en', "
        "json_extract_string(payload_json, '$.text'),id)=1"
    )
    connection.execute(
        "CREATE TEMP TABLE ca AS SELECT id, "
        "json_extract_string(payload_json, '$.subject_concept_id') AS disease_id, "
        "json_extract_string(payload_json, '$.object.concept_id') AS finding_id, "
        "json_extract_string(payload_json, '$.relation') AS relation, "
        "json_extract_string(payload_json, '$.qualifiers.polarity') AS polarity, "
        "json_extract_string(payload_json, '$.qualifiers.temporal_context') AS temporal, "
        "json_extract_string(payload_json, '$.qualifiers.frequency.kind') AS frequency_kind "
        "FROM canonical_assertion"
    )
    connection.execute(
        "CREATE TEMP TABLE sa AS SELECT id, "
        "json_extract_string(payload_json, '$.source_release_id') AS source_release, "
        "json_extract_string(payload_json, '$.source_record_id') AS record_id, "
        "json_extract_string(payload_json, '$.subject_concept_id') AS disease_id, "
        "json_extract_string(payload_json, '$.object.concept_id') AS finding_id, "
        "json_extract_string(payload_json, '$.relation') AS relation, "
        "json_extract_string(payload_json, '$.qualifiers.polarity') AS polarity, "
        "json_extract_string(payload_json, "
        "'$.raw_value.primary_knowledge_source') AS primary_source "
        "FROM source_assertion"
    )
    connection.execute(
        "CREATE TEMP TABLE deriv AS SELECT "
        "json_extract_string(payload_json, '$.canonical_assertion_id') AS canonical_id, "
        "json_extract_string(payload_json, '$.source_assertion_id') AS source_id "
        "FROM assertion_derivation"
    )
    connection.execute(
        "CREATE TEMP TABLE families AS SELECT id, "
        "json_extract_string(payload_json, '$.dependency_type') AS dependency_type, "
        "json_extract_string(payload_json, '$.primary_reference') AS primary_reference, "
        "json_extract(payload_json, '$.source_release_ids')::VARCHAR[] AS releases, "
        "json_extract(payload_json, '$.source_assertion_ids')::VARCHAR[] AS members "
        "FROM evidence_family"
    )
    connection.execute(
        "CREATE TEMP TABLE family_members AS SELECT id AS family_id, "
        "unnest(members) AS source_id FROM families"
    )
    connection.execute(
        "CREATE TEMP TABLE mappings AS SELECT id, "
        "json_extract_string(payload_json, '$.source_concept_id') AS source_id, "
        "json_extract_string(payload_json, '$.target_concept_id') AS target_id, "
        "json_extract_string(payload_json, '$.target_system') AS target_system, "
        "json_extract_string(payload_json, '$.relation') AS relation, "
        "json_extract_string(payload_json, '$.resolution_status') AS status "
        "FROM concept_mapping"
    )
    connection.execute(
        "CREATE TEMP TABLE edges AS SELECT "
        "json_extract_string(payload_json, '$.child_concept_id') AS child_id, "
        "json_extract_string(payload_json, '$.parent_concept_id') AS parent_id "
        "FROM hierarchy_edge"
    )
    connection.execute(
        "CREATE TEMP TABLE diseases AS SELECT disease_id, count(*) AS assertion_count "
        "FROM ca GROUP BY disease_id"
    )
    connection.execute(
        "CREATE TEMP TABLE candidate AS SELECT * FROM read_json_auto(?, "
        "format='newline_delimited')",
        [str(candidates)],
    )
    connection.execute(
        "CREATE TEMP TABLE rare_exact AS SELECT DISTINCT source_id AS disease_id "
        "FROM mappings WHERE target_system='https://www.orpha.net' "
        "AND relation='exact' AND status='resolved' AND target_id IS NOT NULL"
    )
    connection.execute(
        "CREATE TEMP TABLE genetic_descendant AS "
        "WITH RECURSIVE walk(id) AS ("
        "SELECT id FROM concepts WHERE code IN ('MONDO:0003847', 'DOID:630') "
        "UNION SELECT e.child_id FROM walk w JOIN edges e ON e.parent_id=w.id) "
        "SELECT DISTINCT id FROM walk"
    )
    connection.execute(
        "CREATE TEMP TABLE disease_class AS SELECT d.disease_id, "
        "CASE WHEN c.code LIKE 'ORPHA:%' OR r.disease_id IS NOT NULL THEN 1 ELSE 0 END "
        "AS orphanet_linked, "
        "CASE WHEN g.id IS NOT NULL THEN 1 ELSE 0 END AS genetic_hierarchy, "
        "CASE WHEN med.disease_id IS NOT NULL THEN 1 ELSE 0 END AS medline_linked, "
        "CASE WHEN c.code LIKE 'ORPHA:%' OR r.disease_id IS NOT NULL "
        "OR g.id IS NOT NULL THEN 'rare_or_genetic_linked' "
        "WHEN med.disease_id IS NOT NULL THEN 'medline_only_unclassified_prevalence' "
        "ELSE 'unclassified' END AS audit_class "
        "FROM diseases d JOIN concepts c ON c.id=d.disease_id "
        "LEFT JOIN rare_exact r ON r.disease_id=d.disease_id "
        "LEFT JOIN genetic_descendant g ON g.id=d.disease_id "
        "LEFT JOIN (SELECT DISTINCT disease_id FROM sa "
        "WHERE source_release='medlineplus:2026-09-19') med "
        "ON med.disease_id=d.disease_id"
    )
    roots = ",".join(f"('{name}','{code}')" for name, code in DOMAINS)
    connection.execute(
        "CREATE TEMP TABLE domain_assignment AS "
        "WITH RECURSIVE roots(domain, code) AS (VALUES " + roots + "), "
        "walk(domain, id) AS ("
        "SELECT r.domain,c.id FROM roots r JOIN concepts c ON c.code=r.code "
        "UNION SELECT w.domain,e.child_id FROM walk w JOIN edges e ON e.parent_id=w.id), "
        "linked(disease_id, ontology_id) AS ("
        "SELECT d.disease_id,d.disease_id FROM diseases d "
        "UNION SELECT d.disease_id,m.source_id FROM diseases d "
        "JOIN mappings m ON m.target_id=d.disease_id "
        "WHERE m.target_system='https://www.orpha.net' AND m.relation='exact' "
        "AND m.status='resolved') "
        "SELECT DISTINCT l.disease_id,w.domain FROM linked l "
        "JOIN walk w ON w.id=l.ontology_id"
    )
    connection.execute(
        "CREATE TEMP TABLE opposing AS SELECT finding_id,relation FROM ca "
        "GROUP BY finding_id,relation HAVING count(DISTINCT polarity)>1"
    )


def _metrics(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    result: dict[str, Any] = {}
    result["row_counts"] = _counts(
        connection,
        "SELECT name,n FROM (VALUES "
        "('canonical_assertion',(SELECT count(*) FROM ca)),"
        "('source_assertion',(SELECT count(*) FROM sa)),"
        "('candidate_assertion',(SELECT count(*) FROM candidate)),"
        "('diseases_with_assertions',(SELECT count(*) FROM diseases))) t(name,n)",
    )
    result["source_assertions"] = _counts(
        connection, "SELECT source_release,count(*) FROM sa GROUP BY source_release ORDER BY 1"
    )
    result["source_diseases"] = _counts(
        connection,
        "SELECT source_release,count(DISTINCT disease_id) FROM sa "
        "GROUP BY source_release ORDER BY 1",
    )
    result["relations"] = _counts(
        connection, "SELECT relation,count(*) FROM ca GROUP BY relation ORDER BY 1"
    )
    result["polarities"] = _counts(
        connection, "SELECT polarity,count(*) FROM ca GROUP BY polarity ORDER BY 1"
    )
    result["temporal"] = _counts(
        connection,
        "SELECT coalesce(temporal,'missing'),count(*) FROM ca GROUP BY 1 ORDER BY 1",
    )
    result["frequency"] = _counts(
        connection,
        "SELECT coalesce(frequency_kind,'missing'),count(*) FROM ca GROUP BY 1 ORDER BY 1",
    )
    result["mapping_status"] = _counts(
        connection,
        "SELECT relation||'/'||status,count(*) FROM mappings GROUP BY 1 ORDER BY 1",
    )
    result["unresolved_mapping_targets"] = _counts(
        connection,
        "SELECT target_system,count(*) FROM mappings WHERE status='unresolved' "
        "GROUP BY target_system ORDER BY 1",
    )
    result["family_memberships"] = _counts(
        connection,
        "SELECT f.primary_reference||'/'||f.dependency_type,count(*) "
        "FROM family_members m JOIN families f ON f.id=m.family_id GROUP BY 1 ORDER BY 1",
    )
    result["families"] = [
        dict(zip(("id", "dependency_type", "primary_reference", "members"), row, strict=True))
        for row in _rows(
            connection,
            "SELECT id,dependency_type,primary_reference,array_length(members) "
            "FROM families ORDER BY id",
        )
    ]
    result["dependency_groups"] = _counts(
        connection,
        "SELECT dependency_type,count(*) FROM families GROUP BY 1 ORDER BY 1",
    )
    result["source_dependency_types"] = _counts(
        connection,
        "SELECT json_extract_string(payload_json,'$.dependency_type'),count(*) "
        "FROM source_dependency GROUP BY 1 ORDER BY 1",
    )
    result["disease_assertion_buckets"] = _counts(
        connection,
        "SELECT CASE WHEN assertion_count=1 THEN '1' "
        "WHEN assertion_count BETWEEN 2 AND 4 THEN '2-4' "
        "WHEN assertion_count BETWEEN 5 AND 9 THEN '5-9' "
        "WHEN assertion_count BETWEEN 10 AND 19 THEN '10-19' ELSE '20+' END,count(*) "
        "FROM diseases GROUP BY 1 ORDER BY 1",
    )
    result["disease_thresholds"] = dict(
        zip(
            ("at_least_5", "at_least_10", "at_least_20"),
            _rows(
                connection,
                "SELECT sum(assertion_count>=5),sum(assertion_count>=10),"
                "sum(assertion_count>=20) FROM diseases",
            )[0],
            strict=True,
        )
    )
    result["audit_classes"] = _counts(
        connection,
        "SELECT audit_class,count(*) FROM disease_class GROUP BY 1 ORDER BY 1",
    )
    result["classification_markers"] = dict(
        zip(
            ("orphanet_linked", "genetic_hierarchy", "both_markers", "medline_linked"),
            _rows(
                connection,
                "SELECT sum(orphanet_linked),sum(genetic_hierarchy),"
                "sum(orphanet_linked*genetic_hierarchy),sum(medline_linked) "
                "FROM disease_class",
            )[0],
            strict=True,
        )
    )
    result["domain_diseases"] = _counts(
        connection,
        "SELECT domain,count(DISTINCT disease_id) FROM domain_assignment GROUP BY 1 ORDER BY 1",
    )
    result["domain_by_source"] = [
        dict(zip(("domain", "source", "diseases"), row, strict=True))
        for row in _rows(
            connection,
            "SELECT a.domain,s.source_release,count(DISTINCT a.disease_id) "
            "FROM domain_assignment a JOIN sa s ON s.disease_id=a.disease_id "
            "GROUP BY 1,2 ORDER BY 1,2",
        )
    ]
    result["domain_unclassified_count"] = _rows(
        connection,
        "SELECT count(*) FROM diseases d WHERE NOT EXISTS "
        "(SELECT 1 FROM domain_assignment a WHERE a.disease_id=d.disease_id)",
    )[0][0]
    result["negative_and_discriminants"] = dict(
        zip(
            ("diseases_with_negative", "opposing_findings", "diseases_with_discriminant"),
            (
                _rows(
                    connection,
                    "SELECT count(DISTINCT disease_id) FROM ca WHERE polarity='excluded'",
                )[0][0],
                _rows(connection, "SELECT count(*) FROM opposing")[0][0],
                _rows(
                    connection,
                    "SELECT count(DISTINCT ca.disease_id) FROM ca JOIN opposing o "
                    "ON o.finding_id=ca.finding_id AND o.relation=ca.relation",
                )[0][0],
            ),
            strict=True,
        )
    )
    result["opposing_strength"] = [
        dict(
            zip(
                (
                    "finding_code",
                    "relation",
                    "positive_diseases",
                    "negative_diseases",
                    "separation",
                ),
                row,
                strict=True,
            )
        )
        for row in _rows(
            connection,
            "SELECT c.code,q.relation,q.positive,q.negative,least(q.positive,q.negative) "
            "FROM (SELECT finding_id,relation, "
            "count(DISTINCT CASE WHEN polarity='present' THEN disease_id END) AS positive, "
            "count(DISTINCT CASE WHEN polarity='excluded' THEN disease_id END) AS negative "
            "FROM ca GROUP BY finding_id,relation) q JOIN concepts c ON c.id=q.finding_id "
            "WHERE q.positive>0 AND q.negative>0 "
            "ORDER BY least(q.positive,q.negative) DESC, "
            "q.positive+q.negative DESC,c.code LIMIT 12",
        )
    ]
    result["opposing_separation_buckets"] = _counts(
        connection,
        "SELECT CASE WHEN separation=1 THEN '1' WHEN separation BETWEEN 2 AND 4 THEN '2-4' "
        "WHEN separation BETWEEN 5 AND 9 THEN '5-9' ELSE '10+' END,count(*) "
        "FROM (SELECT least("
        "count(DISTINCT CASE WHEN polarity='present' THEN disease_id END), "
        "count(DISTINCT CASE WHEN polarity='excluded' THEN disease_id END)) AS separation "
        "FROM ca GROUP BY finding_id,relation HAVING count(DISTINCT polarity)>1) "
        "GROUP BY 1 ORDER BY 1",
    )
    result["canonical_deduplication"] = dict(
        zip(
            ("source_minus_canonical", "multi_source_canonical", "scorable_canonical"),
            (
                _rows(connection, "SELECT (SELECT count(*) FROM sa)-(SELECT count(*) FROM ca)")[0][
                    0
                ],
                _rows(
                    connection,
                    "SELECT count(*) FROM (SELECT d.canonical_id FROM deriv d JOIN sa s "
                    "ON s.id=d.source_id GROUP BY d.canonical_id "
                    "HAVING count(DISTINCT s.source_release)>1)",
                )[0][0],
                _rows(
                    connection,
                    "SELECT count(DISTINCT d.canonical_id) FROM deriv d "
                    "JOIN family_members m ON m.source_id=d.source_id "
                    "JOIN families f ON f.id=m.family_id "
                    "WHERE f.dependency_type!='unknown'",
                )[0][0],
            ),
            strict=True,
        )
    )
    result["monarch_primary"] = _counts(
        connection,
        "SELECT primary_source,count(*) FROM sa "
        "WHERE source_release='monarch:2026-09-02' GROUP BY 1 ORDER BY 1",
    )
    result["monarch_overlap"] = dict(
        zip(
            (
                "orphanet_republications",
                "canonical_shared_with_orphadata",
                "mapped_pair_shared_with_orphadata",
                "other_primary_rows",
            ),
            (
                _rows(
                    connection, "SELECT count(*) FROM sa WHERE primary_source='infores:orphanet'"
                )[0][0],
                _rows(
                    connection,
                    "SELECT count(DISTINCT d1.canonical_id) FROM deriv d1 JOIN sa m "
                    "ON m.id=d1.source_id AND m.source_release='monarch:2026-09-02' "
                    "JOIN deriv d2 ON d2.canonical_id=d1.canonical_id "
                    "JOIN sa o ON o.id=d2.source_id "
                    "AND o.source_release='orphadata:2026-07'",
                )[0][0],
                _rows(
                    connection,
                    "SELECT count(DISTINCT m.id) FROM sa m JOIN mappings x "
                    "ON x.source_id=m.disease_id AND x.target_system='https://www.orpha.net' "
                    "AND x.relation='exact' AND x.status='resolved' "
                    "JOIN sa o ON o.disease_id=x.target_id AND o.finding_id=m.finding_id "
                    "AND o.relation=m.relation AND o.polarity=m.polarity "
                    "WHERE m.primary_source='infores:orphanet' "
                    "AND o.source_release='orphadata:2026-07'",
                )[0][0],
                _rows(
                    connection,
                    "SELECT count(*) FROM sa WHERE source_release='monarch:2026-09-02' "
                    "AND primary_source!='infores:orphanet'",
                )[0][0],
            ),
            strict=True,
        )
    )
    result["monarch_disease_classes"] = _counts(
        connection,
        "SELECT c.audit_class,count(DISTINCT s.disease_id) FROM sa s "
        "JOIN disease_class c ON c.disease_id=s.disease_id "
        "WHERE s.source_release='monarch:2026-09-02' GROUP BY 1 ORDER BY 1",
    )
    result["medline_candidates"] = _counts(
        connection,
        "SELECT CASE WHEN subject_mapping.status='unresolved' THEN 'subject_unresolved' "
        "WHEN subject_mapping.status='ambiguous' THEN 'subject_ambiguous' "
        "WHEN object_mapping.status='unresolved' THEN 'object_unresolved' "
        "WHEN object_mapping.status='ambiguous' THEN 'object_ambiguous' "
        "WHEN subject_mapping.relation NOT IN ('exact','equivalent') "
        "OR object_mapping.relation NOT IN ('exact','equivalent') THEN 'non_exact' "
        "ELSE 'technically_eligible' END,count(*) FROM candidate GROUP BY 1 ORDER BY 1",
    )
    result["medline_topic_counts"] = dict(
        zip(
            (
                "english_with_candidates",
                "english_with_eligible",
                "topics_with_unresolved",
                "topics_with_ambiguous",
            ),
            _rows(
                connection,
                "SELECT count(DISTINCT source_record_id), "
                "count(DISTINCT CASE WHEN subject_mapping.status='resolved' "
                "THEN source_record_id END), "
                "count(DISTINCT CASE WHEN subject_mapping.status='unresolved' "
                "THEN source_record_id END), "
                "count(DISTINCT CASE WHEN subject_mapping.status='ambiguous' "
                "THEN source_record_id END) "
                "FROM candidate",
            )[0],
            strict=True,
        )
    )
    result["medline_eligible"] = dict(
        zip(
            ("rows", "diseases", "distinct_signatures", "duplicate_rows", "negative_rows"),
            _rows(
                connection,
                "SELECT count(*),count(DISTINCT subject_mapping.concept_id), "
                "count(DISTINCT (subject_mapping.concept_id,object_mapping.concept_id, "
                "predicate,polarity)), "
                "count(*)-count(DISTINCT (subject_mapping.concept_id, "
                "object_mapping.concept_id,predicate,polarity)), "
                "sum(CASE WHEN polarity='excluded' THEN 1 ELSE 0 END) FROM candidate "
                "WHERE subject_mapping.status='resolved' AND object_mapping.status='resolved' "
                "AND subject_mapping.relation IN ('exact','equivalent') "
                "AND object_mapping.relation IN ('exact','equivalent')",
            )[0],
            strict=True,
        )
    )
    result["medline_disease_buckets"] = _counts(
        connection,
        "SELECT CASE WHEN n=1 THEN '1' WHEN n BETWEEN 2 AND 4 THEN '2-4' "
        "WHEN n BETWEEN 5 AND 9 THEN '5-9' WHEN n BETWEEN 10 AND 19 THEN '10-19' "
        "ELSE '20+' END,count(*) FROM (SELECT disease_id,count(*) n FROM sa "
        "WHERE source_release='medlineplus:2026-09-19' GROUP BY disease_id) GROUP BY 1 ORDER BY 1",
    )
    result["medline_relations"] = _counts(
        connection,
        "SELECT relation||'/'||polarity,count(*) FROM sa "
        "WHERE source_release='medlineplus:2026-09-19' GROUP BY 1",
    )
    result["medline_classes"] = _counts(
        connection,
        "SELECT c.audit_class,count(DISTINCT s.disease_id) FROM sa s "
        "JOIN disease_class c ON c.disease_id=s.disease_id "
        "WHERE s.source_release='medlineplus:2026-09-19' GROUP BY 1 ORDER BY 1",
    )
    result["medline_only_source_diseases"] = _rows(
        connection,
        "SELECT count(*) FROM (SELECT disease_id FROM sa GROUP BY disease_id "
        "HAVING count(DISTINCT source_release)=1 "
        "AND min(source_release)='medlineplus:2026-09-19')",
    )[0][0]
    result["scorable_diseases"] = _rows(
        connection,
        "SELECT count(DISTINCT c.disease_id) FROM ca c JOIN deriv d ON d.canonical_id=c.id "
        "JOIN family_members fm ON fm.source_id=d.source_id "
        "JOIN families f ON f.id=fm.family_id WHERE f.dependency_type!='unknown'",
    )[0][0]
    result["medline_frequent_findings"] = [
        dict(zip(("code", "candidate_rows"), row, strict=True))
        for row in _rows(
            connection,
            "SELECT object_mapping.code,count(*) FROM candidate "
            "WHERE subject_mapping.status='resolved' AND object_mapping.status='resolved' "
            "GROUP BY 1 ORDER BY 2 DESC,1 LIMIT 20",
        )
    ]
    result["generic_findings"] = [
        dict(zip(("code", "diseases"), row, strict=True))
        for row in _rows(
            connection,
            "SELECT c.code,count(DISTINCT a.disease_id) FROM ca a "
            "JOIN concepts c ON c.id=a.finding_id GROUP BY c.code "
            "ORDER BY 2 DESC,c.code LIMIT 15",
        )
    ]
    result["medline_topic_examples"] = [
        dict(
            zip(
                (
                    "disease_code",
                    "label",
                    "medline_source_assertions",
                    "canonical_assertions",
                    "symptom_assertions",
                    "sign_assertions",
                    "other_sources",
                    "negatives",
                    "opposing_finding_assertions",
                    "audit_class",
                ),
                row,
                strict=True,
            )
        )
        for row in _rows(
            connection,
            "WITH med AS (SELECT disease_id,count(*) n FROM sa "
            "WHERE source_release='medlineplus:2026-09-19' GROUP BY 1), "
            "others AS (SELECT disease_id,string_agg(DISTINCT source_release,', ' "
            "ORDER BY source_release) AS source_names "
            "FROM sa WHERE source_release!='medlineplus:2026-09-19' GROUP BY 1), "
            "stats AS (SELECT a.disease_id,count(*) total, "
            "sum(CASE WHEN a.relation='has_symptom' THEN 1 ELSE 0 END) symptoms, "
            "sum(CASE WHEN a.relation='has_sign' THEN 1 ELSE 0 END) signs, "
            "sum(CASE WHEN a.polarity='excluded' THEN 1 ELSE 0 END) negatives, "
            "sum(CASE WHEN p.finding_id IS NOT NULL THEN 1 ELSE 0 END) opposing "
            "FROM ca a LEFT JOIN opposing p ON p.finding_id=a.finding_id "
            "AND p.relation=a.relation GROUP BY a.disease_id) "
            "SELECT c.code,coalesce(l.label_text,c.code),med.n,stats.total, "
            "stats.symptoms,stats.signs,coalesce(o.source_names,''), "
            "stats.negatives,stats.opposing,cl.audit_class "
            "FROM med JOIN concepts c ON c.id=med.disease_id "
            "JOIN disease_class cl ON cl.disease_id=med.disease_id "
            "JOIN stats ON stats.disease_id=med.disease_id "
            "LEFT JOIN labels l ON l.concept_id=med.disease_id "
            "LEFT JOIN others o ON o.disease_id=med.disease_id "
            "WHERE cl.audit_class='medline_only_unclassified_prevalence' "
            "ORDER BY med.n DESC,c.code LIMIT 12",
        )
    ]
    return result


def _sample(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    wanted = {
        "medline_eligible": 8,
        "monarch_omim": 8,
        "monarch_orphanet": 8,
        "monarch_mondo": 4,
        "monarch_negative": 6,
        "orphadata_positive": 8,
        "orphadata_negative": 6,
    }
    picks = _rows(
        connection,
        "WITH tagged AS (SELECT s.id, CASE "
        "WHEN s.source_release='medlineplus:2026-09-19' THEN 'medline_eligible' "
        "WHEN s.source_release='monarch:2026-09-02' AND s.polarity='excluded' "
        "THEN 'monarch_negative' "
        "WHEN s.source_release='monarch:2026-09-02' AND s.primary_source='infores:orphanet' "
        "THEN 'monarch_orphanet' "
        "WHEN s.source_release='monarch:2026-09-02' AND s.primary_source='infores:omim' "
        "THEN 'monarch_omim' "
        "WHEN s.source_release='monarch:2026-09-02' AND s.primary_source='infores:mondo' "
        "THEN 'monarch_mondo' "
        "WHEN s.source_release='orphadata:2026-07' AND s.polarity='excluded' "
        "THEN 'orphadata_negative' ELSE 'orphadata_positive' END AS stratum "
        "FROM sa s), ranked AS (SELECT id,stratum, "
        "row_number() OVER (PARTITION BY stratum ORDER BY md5(id),id) AS rank FROM tagged) "
        "SELECT id,stratum FROM ranked WHERE "
        + " OR ".join(f"(stratum='{key}' AND rank<={value})" for key, value in wanted.items())
        + " ORDER BY stratum,rank",
    )
    selected: list[dict[str, Any]] = []
    for source_id, stratum in picks:
        row = _rows(
            connection,
            "SELECT s.payload_json,r.payload_json,f.id,f.dependency_type,f.primary_reference, "
            "dc.audit_class,d.code,h.code,dl.label_text,hl.label_text "
            "FROM source_assertion s "
            "JOIN source_record r ON r.id=json_extract_string(s.payload_json,'$.source_record_id') "
            "JOIN family_members fm ON fm.source_id=s.id "
            "JOIN families f ON f.id=fm.family_id "
            "JOIN sa x ON x.id=s.id JOIN disease_class dc ON dc.disease_id=x.disease_id "
            "JOIN concepts d ON d.id=x.disease_id JOIN concepts h ON h.id=x.finding_id "
            "LEFT JOIN labels dl ON dl.concept_id=d.id "
            "LEFT JOIN labels hl ON hl.concept_id=h.id "
            "WHERE s.id=?",
            [source_id],
        )[0]
        assertion = orjson.loads(row[0])
        record = orjson.loads(row[1])
        candidate = assertion["raw_value"].get("candidate")
        crosswalk = _rows(
            connection,
            "SELECT id,source_id,target_id FROM mappings WHERE source_id=? "
            "AND target_system='https://www.orpha.net' "
            "AND relation='exact' AND status='resolved' ORDER BY id",
            [assertion["subject_concept_id"]],
        )
        selected.append(
            {
                "sample_stratum": stratum,
                "disease": row[6],
                "disease_label": row[8] or row[6],
                "finding": row[7],
                "finding_label": row[9] or row[7],
                "relation": assertion["relation"],
                "polarity": assertion["qualifiers"]["polarity"],
                "source_release": assertion["source_release_id"],
                "source_assertion_id": source_id,
                "source_record_id": assertion["source_record_id"],
                "locator": (
                    candidate["source_locator"]
                    if candidate
                    else assertion["raw_value"].get("source_locator", record["record_locator"])
                ),
                "source_record_locator": record["record_locator"],
                "artifact_ids": assertion["artifact_ids"],
                "mapping": {
                    "subject": candidate["subject_mapping"]
                    if candidate
                    else "direct_local_identifier",
                    "object": candidate["object_mapping"]
                    if candidate
                    else "direct_local_identifier",
                    "exact_orphanet_crosswalk_ids": [item[0] for item in crosswalk],
                },
                "evidence_family": row[2],
                "dependency": {"type": row[3], "primary_reference": row[4]},
                "audit_class": row[5],
                "review_status": candidate["review_status"] if candidate else "unreviewed_snapshot",
            }
        )
    candidate_picks = _rows(
        connection,
        "WITH tagged AS (SELECT *, CASE "
        "WHEN subject_mapping.status='ambiguous' THEN 'medline_subject_ambiguous' "
        "ELSE 'medline_subject_unresolved' END AS stratum "
        "FROM candidate WHERE subject_mapping.status IN ('ambiguous','unresolved')), "
        "ranked AS (SELECT *,row_number() OVER (PARTITION BY stratum "
        "ORDER BY md5(candidate_assertion_id),candidate_assertion_id) AS rank FROM tagged) "
        "SELECT stratum,candidate_assertion_id,subject_text,object_text,predicate,polarity, "
        "source_release_id,source_record_id,source_locator,subject_mapping,object_mapping, "
        "evidence_family,dependency_group,review_status FROM ranked WHERE rank<=6 "
        "ORDER BY stratum,rank",
    )
    for row in candidate_picks:
        selected.append(
            {
                "sample_stratum": row[0],
                "candidate_assertion_id": row[1],
                "disease": row[2],
                "finding": row[3],
                "relation": row[4],
                "polarity": row[5],
                "source_release": row[6],
                "source_record_id": row[7],
                "locator": row[8],
                "mapping": {"subject": row[9], "object": row[10]},
                "evidence_family": row[11],
                "dependency": {"group": row[12], "type": "unknown"},
                "audit_class": "unresolved_mapping_not_canonical",
                "review_status": row[13],
            }
        )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--with-diagnostic-ties",
        action="store_true",
        help="Also run one real synthetic diagnostic to quantify equal scores",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir or root / "data/staging/v0.7-g0"
    output = output.resolve()
    if root not in output.parents:
        raise LatrosError("Audit output must remain inside the local repository")
    manifest = load_manifest_v2(root, SNAPSHOT)
    if manifest.content_sha256 != CONTENT_SHA256:
        raise LatrosError("The v0.7 snapshot hash differs from the immutable audit target")
    if (
        manifest.clinical_validation
        or manifest.publishable
        or manifest.validation_status != "unreviewed"
        or not manifest.research_override_used
    ):
        raise LatrosError("The target snapshot no longer has its unreviewed research status")
    candidates = root / "data/staging/general" / SNAPSHOT / "candidate_assertions.jsonl"
    if not candidates.is_file():
        raise LatrosError(f"Local candidate staging file is missing: {candidates}")
    with candidates.open("rb") as candidate_stream:
        candidate_sha256 = hashlib.file_digest(candidate_stream, "sha256").hexdigest()
    with duckdb.connect(str(snapshot_path_v2(root, SNAPSHOT)), read_only=True) as connection:
        _prepare(connection, candidates)
        metrics = _metrics(connection)
        sample = _sample(connection)
    if args.with_diagnostic_ties:
        from latros.application.service import ResearchApplicationService
        from latros.clinical.loading import load_clinical_case

        case = load_clinical_case((root / "examples/general/respiratory-common.json").read_bytes())
        service = ResearchApplicationService(root)
        try:
            result = service.diagnose(SNAPSHOT, case, "general_v1")
        finally:
            service.close()
        scores = Counter(item.aggregate.value for item in result.candidates)
        metrics["respiratory_case_score_ties"] = {
            "case": "examples/general/respiratory-common.json",
            "candidate_count": len(result.candidates),
            "distinct_scores": len(scores),
            "candidates_in_tied_groups": sum(n for n in scores.values() if n > 1),
            "largest_tied_group": max(scores.values(), default=0),
            "score_groups": [
                {"score": score, "candidates": count}
                for score, count in sorted(scores.items(), key=lambda pair: (-pair[1], -pair[0]))[
                    :12
                ]
            ],
        }
    if metrics["row_counts"]["candidate_assertion"] != 7736 or len(sample) != 60:
        raise LatrosError("Audit counts or stratified sample size differ from the pinned release")
    output.mkdir(parents=True, exist_ok=True)
    sample_bytes = b"".join(
        orjson.dumps(item, option=orjson.OPT_SORT_KEYS) + b"\n" for item in sample
    )
    (output / "stratified-review-sample.jsonl").write_bytes(sample_bytes)
    metrics["audit"] = {
        "snapshot": SNAPSHOT,
        "content_sha256": CONTENT_SHA256,
        "candidate_file_sha256": candidate_sha256,
        "review_sample_rows": len(sample),
        "review_sample_sha256": hashlib.sha256(sample_bytes).hexdigest(),
        "clinical_review_performed": False,
    }
    (output / "metrics.json").write_bytes(
        orjson.dumps(metrics, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2) + b"\n"
    )
    print(orjson.dumps(metrics["audit"], option=orjson.OPT_INDENT_2).decode())


if __name__ == "__main__":
    main()
