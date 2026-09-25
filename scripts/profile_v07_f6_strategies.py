"""Compare read-only F6 materialization probes on one synthetic case.

Each invocation uses one case and an immutable snapshot. Results are timings and
row counts only; neither assertions nor patient data are written to the report.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path
from typing import Any

import orjson
from profile_general_v1_runtime import memory_mb

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2
from latros.knowledge.models_v2 import CanonicalAssertion

SNAPSHOT = "v0.7.0-general-dev-unreviewed"


def measure(action: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    value = action()
    return value, round(time.perf_counter() - started, 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case_data = json.loads(args.case.read_text(encoding="utf-8"))
    case = ClinicalCaseV2.model_validate(case_data.get("clinical_case", case_data))
    service = ResearchApplicationService(args.root)
    try:
        strategy = service._general_strategy(SNAPSHOT)
        repository = strategy.repository
        observations, _, _ = strategy._project(case)
        allowed = strategy._aggregatable.copy()
        if not bool(strategy.profile.parameters.get("allow_unlisted_evidence_families", False)):
            weights = strategy.profile.parameters.get("family_weights", {})
            if isinstance(weights, dict):
                allowed.intersection_update(weights)
        assessed = [
            (item.concept_id, item.relation)
            for item in observations.values()
            if item.evaluation_status == "assessed"
            and item.clinical_status in {"present", "absent"}
        ]
        selected, match_s = measure(lambda: repository.matching_candidate_ids(assessed, allowed))
        if not selected:
            raise ValueError("Case has no matched candidates; choose another benchmark case")
        report: dict[str, Any] = {
            "case": args.case.name,
            "candidate_count": len(selected),
            "matching_s": match_s,
            "rss_start_mb": memory_mb(),
        }
        baseline, baseline_s = measure(
            lambda: repository.candidate_rows(selected, reuse_last_match=True)
        )
        report["baseline"] = {
            "seconds": baseline_s,
            "assertion_rows": sum(len(items) for items in baseline.assertions.values()),
            "source_rows": len(baseline.provenance),
            "rss_after_mb": memory_mb(),
        }
        del baseline
        gc.collect()
        connection = repository.connection
        # A: a single joined query with provenance projected in SQL. The query
        # excludes no final fields but does not build a DifferentialResultV2.
        joined_sql = (
            "SELECT a.id, a.candidate_id, "
            "json_extract_string(a.payload_json, '$.relation'), "
            "json_extract_string(a.payload_json, '$.object.concept_id'), "
            "json_extract_string(a.payload_json, '$.qualifiers.polarity'), "
            "d.source_id, fm.family_id, "
            "json_extract_string(sa.payload_json, '$.source_release_id'), "
            "json_extract_string(sa.payload_json, '$.source_record_id'), "
            "json_extract(sa.payload_json, '$.artifact_ids'), "
            "json_extract_string(sr.payload_json, '$.record_locator') "
            "FROM selected_canonical_id AS a "
            "JOIN derivation_ref AS d ON d.canonical_id = a.id "
            "LEFT JOIN family_member AS fm ON fm.source_id = d.source_id "
            "LEFT JOIN source_assertion AS sa ON sa.id = d.source_id "
            "LEFT JOIN source_record AS sr ON sr.id = "
            "json_extract_string(sa.payload_json, '$.source_record_id') "
            "ORDER BY a.id, d.id, fm.family_id"
        )
        joined, a_s = measure(lambda: connection.execute(joined_sql).fetchall())
        report["A_sql_join"] = {
            "seconds": a_s,
            "rows_returned": len(joined),
            "rss_after_mb": memory_mb(),
        }
        del joined
        gc.collect()
        # B: an ephemeral, full-snapshot index. This is an optimistic lower
        # bound for a persistent derivative because it excludes disk/hash I/O.
        index_sql = joined_sql.replace(
            "FROM selected_canonical_id AS a",
            "FROM (SELECT id, payload_json, "
            "json_extract_string(payload_json, '$.subject_concept_id') AS candidate_id "
            "FROM canonical_assertion) AS a",
        ).replace("ORDER BY a.id, d.id, fm.family_id", "")
        _, cold_s = measure(
            lambda: connection.execute("CREATE TEMP TABLE f6_evidence_index AS " + index_sql)
        )
        warm, warm_s = measure(
            lambda: connection.execute(
                "SELECT i.* FROM f6_evidence_index AS i "
                "JOIN selected_matching_candidate_id AS m ON i.candidate_id = m.candidate_id "
                "ORDER BY i.id, i.source_id, i.family_id"
            ).fetchall()
        )
        report["B_derived_index"] = {
            "cold_build_s": cold_s,
            "warm_fetch_s": warm_s,
            "cold_plus_warm_s": round(cold_s + warm_s, 3),
            "rows_returned": len(warm),
            "rss_after_mb": memory_mb(),
        }
        del warm
        gc.collect()
        # C: identical canonical payload fetch, but only fields used by
        # general_v1 are represented as Python tuples before final expansion.
        payloads, fetch_s = measure(
            lambda: connection.execute(
                "SELECT payload_json FROM selected_canonical_id ORDER BY id"
            ).fetchall()
        )
        models, pydantic_s = measure(
            lambda: [CanonicalAssertion.model_validate_json(row[0]) for row in payloads]
        )
        del models
        gc.collect()

        def compact() -> list[tuple[str, str, str, str | None, str]]:
            result: list[tuple[str, str, str, str | None, str]] = []
            for (payload,) in payloads:
                item = orjson.loads(payload)
                result.append(
                    (
                        item["canonical_assertion_id"],
                        item["subject_concept_id"],
                        item["relation"],
                        item["object"].get("concept_id"),
                        item["qualifiers"]["polarity"],
                    )
                )
            return result

        tuples, compact_s = measure(compact)
        report["C_compact_python"] = {
            "payload_fetch_s": fetch_s,
            "pydantic_build_s": pydantic_s,
            "compact_build_s": compact_s,
            "rows_returned": len(tuples),
            "rss_after_mb": memory_mb(),
        }
        del tuples
        gc.collect()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
    finally:
        service.close()


if __name__ == "__main__":
    main()
