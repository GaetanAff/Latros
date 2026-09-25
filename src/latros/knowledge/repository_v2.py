"""Read-only, query-driven access to an existing canonical-v2 DuckDB runtime.

This module is deliberately outside ``pipeline_hash_v2``: it never changes the
published snapshot or the deterministic build implementation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import orjson

from latros.common import LatrosError
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.models_v2 import CanonicalAssertion
from latros.knowledge.store_v2 import load_manifest_v2, snapshot_path_v2


@dataclass(frozen=True)
class SourceProvenance:
    source_release_id: str
    source_record_id: str
    artifact_ids: list[str]
    record_locator: str


@dataclass
class CandidateRows:
    assertions: dict[str, list[CanonicalAssertion]]
    derivations: dict[str, list[str]]
    families_by_source: dict[str, list[str]]
    provenance: dict[str, SourceProvenance]
    labels: dict[str, str]


class CanonicalKnowledgeRepositoryV2:
    """Targeted queries; no full ``CanonicalKnowledgeV2`` materialization."""

    def __init__(self, root: Path, snapshot: str) -> None:
        self.root = root
        self.snapshot = snapshot
        self.manifest: KnowledgeSnapshotManifestV2 = load_manifest_v2(root, snapshot)
        self.connection = duckdb.connect(str(snapshot_path_v2(root, snapshot)), read_only=True)
        self.connection.execute("SET threads=1")
        self._members_ready = False
        self._derivations_ready = False
        self._verified_file_attributes = self._file_attributes()

    def _file_attributes(self) -> tuple[tuple[str, int, int, int], ...]:
        database = snapshot_path_v2(self.root, self.snapshot)
        files = [
            self.root / "manifests" / f"{self.snapshot}.json",
            database,
            database.parent / "integrity.json",
            *(
                self.root / "data/canonical" / self.snapshot / f"{name}.parquet"
                for name in self.manifest.tables
            ),
        ]
        return tuple(
            (str(path), path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ctime_ns)
            for path in files
        )

    def assert_unchanged(self) -> None:
        """Fail closed if a previously verified snapshot changed in this process."""
        try:
            current = self._file_attributes()
        except OSError as exc:
            raise LatrosError("Verified snapshot files are no longer available") from exc
        if current != self._verified_file_attributes:
            raise LatrosError("Verified snapshot files changed during this process")

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> CanonicalKnowledgeRepositoryV2:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def _family_members(self) -> None:
        if self._members_ready:
            return
        self.connection.execute(
            "CREATE TEMP TABLE family_member AS "
            "SELECT id AS family_id, "
            "unnest(json_extract(payload_json, '$.source_assertion_ids')::VARCHAR[]) "
            "AS source_id FROM evidence_family"
        )
        self._members_ready = True

    def _derivation_refs(self) -> None:
        if self._derivations_ready:
            return
        self.connection.execute(
            "CREATE TEMP TABLE derivation_ref AS SELECT id, "
            "json_extract_string(payload_json, '$.canonical_assertion_id') AS canonical_id, "
            "json_extract_string(payload_json, '$.source_assertion_id') AS source_id "
            "FROM assertion_derivation"
        )
        self._derivations_ready = True

    def aggregatable_family_ids(self) -> set[str]:
        unknown = {
            row[0]
            for row in self.connection.execute(
                "SELECT json_extract_string(payload_json, '$.source_release_id') "
                "FROM source_dependency WHERE "
                "json_extract_string(payload_json, '$.dependency_type') = 'unknown'"
            ).fetchall()
        }
        result: set[str] = set()
        for family_id, dependency_type, releases_json in self.connection.execute(
            "SELECT id, json_extract_string(payload_json, '$.dependency_type'), "
            "json_extract(payload_json, '$.source_release_ids') "
            "FROM evidence_family ORDER BY id"
        ).fetchall():
            releases = orjson.loads(releases_json)
            if dependency_type != "unknown" and not unknown.intersection(releases):
                result.add(family_id)
        return result

    def all_candidate_ids(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT DISTINCT a.subject_id FROM "
            "(SELECT json_extract_string(payload_json, '$.subject_concept_id') AS subject_id "
            "FROM canonical_assertion) AS a "
            "JOIN concept AS c ON c.id = a.subject_id "
            "WHERE json_extract_string(c.payload_json, '$.kind') = 'condition' "
            "AND json_extract_string(c.payload_json, '$.status') = 'active' "
            "ORDER BY a.subject_id"
        ).fetchall()
        return [row[0] for row in rows]

    def resolve_observation(
        self, concept_id: str, system: str, code: str
    ) -> tuple[str | None, str | None]:
        direct = self.connection.execute(
            "SELECT id FROM concept WHERE id = ? AND "
            "json_extract_string(payload_json, '$.status') = 'active'",
            [concept_id],
        ).fetchone()
        if direct:
            return direct[0], None
        identifiers = self.connection.execute(
            "SELECT json_extract_string(i.payload_json, '$.concept_id') "
            "FROM external_identifier AS i JOIN concept AS c "
            "ON c.id = json_extract_string(i.payload_json, '$.concept_id') "
            "WHERE json_extract_string(i.payload_json, '$.system') = ? "
            "AND json_extract_string(i.payload_json, '$.code') = ? "
            "AND json_extract_string(c.payload_json, '$.status') = 'active' "
            "ORDER BY i.id LIMIT 1",
            [system, code],
        ).fetchone()
        if identifiers:
            return identifiers[0], None
        mappings = self.connection.execute(
            "SELECT id, json_extract_string(payload_json, '$.target_concept_id') "
            "FROM concept_mapping WHERE "
            "json_extract_string(payload_json, '$.target_system') = ? "
            "AND json_extract_string(payload_json, '$.target_code') = ? "
            "AND json_extract_string(payload_json, '$.relation') IN ('exact', 'equivalent') "
            "AND json_extract_string(payload_json, '$.resolution_status') = 'resolved' "
            "AND json_extract_string(payload_json, '$.target_concept_id') IS NOT NULL "
            "ORDER BY id LIMIT 2",
            [system, code],
        ).fetchall()
        return (mappings[0][1], mappings[0][0]) if len(mappings) == 1 else (None, None)

    def matching_candidate_ids(
        self,
        observations: Iterable[tuple[str, str]],
        allowed_family_ids: set[str],
    ) -> list[str]:
        pairs = sorted(set(observations))
        if not pairs or not allowed_family_ids:
            return []
        self._family_members()
        self._derivation_refs()
        values = ", ".join("(?, ?)" for _ in pairs)
        parameters: list[Any] = [part for pair in pairs for part in pair]
        parameters.append(sorted(allowed_family_ids))
        rows = self.connection.execute(
            f"WITH observed(concept_id, relation) AS (VALUES {values}), "
            "matched AS (SELECT a.id, "
            "json_extract_string(a.payload_json, '$.subject_concept_id') AS candidate_id "
            "FROM canonical_assertion AS a JOIN observed AS o "
            "ON json_extract_string(a.payload_json, '$.object.concept_id') = o.concept_id "
            "AND json_extract_string(a.payload_json, '$.relation') = o.relation "
            "AND json_extract_string(a.payload_json, '$.object.kind') = 'concept') "
            "SELECT DISTINCT m.candidate_id FROM matched AS m "
            "JOIN concept AS c ON c.id = m.candidate_id "
            "JOIN derivation_ref AS d ON d.canonical_id = m.id "
            "JOIN family_member AS fm ON fm.source_id = d.source_id "
            "WHERE json_extract_string(c.payload_json, '$.kind') = 'condition' "
            "AND json_extract_string(c.payload_json, '$.status') = 'active' "
            "AND fm.family_id IN (SELECT unnest(?::VARCHAR[])) "
            "ORDER BY m.candidate_id",
            parameters,
        ).fetchall()
        return [row[0] for row in rows]

    def labels(self, concept_ids: list[str]) -> dict[str, str]:
        if not concept_ids:
            return {}
        rows = self.connection.execute(
            "SELECT json_extract_string(payload_json, '$.concept_id'), "
            "json_extract_string(payload_json, '$.text') FROM designation "
            "WHERE json_extract_string(payload_json, '$.concept_id') "
            "IN (SELECT unnest(?::VARCHAR[])) "
            "AND json_extract_string(payload_json, '$.scope') "
            "IN ('preferred', 'fully_specified_name') "
            "ORDER BY json_extract_string(payload_json, '$.concept_id'), "
            "json_extract_string(payload_json, '$.scope'), "
            "json_extract_string(payload_json, '$.language'), id",
            [concept_ids],
        ).fetchall()
        return {concept_id: label for concept_id, label in rows}

    def first_external_identifier(self, concept_id: str) -> tuple[str, str]:
        row = self.connection.execute(
            "SELECT json_extract_string(payload_json, '$.system'), "
            "json_extract_string(payload_json, '$.code') FROM external_identifier "
            "WHERE json_extract_string(payload_json, '$.concept_id') = ? "
            "ORDER BY 1, 2 LIMIT 1",
            [concept_id],
        ).fetchone()
        if row is None:
            raise LatrosError(f"Concept {concept_id!r} has no external identifier")
        return row[0], row[1]

    def candidate_rows(self, candidate_ids: list[str]) -> CandidateRows:
        """Materialize only assertions/provenance of candidates that can score."""
        if not candidate_ids:
            return CandidateRows({}, {}, {}, {}, {})
        self._family_members()
        self._derivation_refs()
        assertions: dict[str, list[CanonicalAssertion]] = defaultdict(list)
        rows = self.connection.execute(
            "SELECT payload_json FROM canonical_assertion WHERE "
            "json_extract_string(payload_json, '$.subject_concept_id') "
            "IN (SELECT unnest(?::VARCHAR[])) ORDER BY id",
            [candidate_ids],
        ).fetchall()
        for (payload,) in rows:
            assertion = CanonicalAssertion.model_validate_json(payload)
            assertions[assertion.subject_concept_id].append(assertion)
        del rows
        # Passing tens of thousands of IDs as a VARCHAR[] parameter is very slow
        # in DuckDB's Python binding. Derive the selected IDs inside DuckDB instead.
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE selected_canonical_id AS "
            "SELECT id FROM canonical_assertion WHERE "
            "json_extract_string(payload_json, '$.subject_concept_id') "
            "IN (SELECT unnest(?::VARCHAR[]))",
            [candidate_ids],
        )
        derivations: dict[str, list[str]] = defaultdict(list)
        family_by_source: dict[str, list[str]] = defaultdict(list)
        rows = self.connection.execute(
            "SELECT d.canonical_id, d.source_id, fm.family_id "
            "FROM derivation_ref AS d LEFT JOIN family_member AS fm "
            "ON fm.source_id = d.source_id "
            "JOIN selected_canonical_id AS picked ON picked.id = d.canonical_id "
            "ORDER BY d.id, fm.family_id",
        ).fetchall()
        for canonical_id, source_id, family_id in rows:
            if source_id not in derivations[canonical_id]:
                derivations[canonical_id].append(source_id)
            if family_id is not None:
                family_by_source[source_id].append(family_id)
        provenance: dict[str, SourceProvenance] = {}
        if family_by_source:
            self.connection.execute(
                "CREATE OR REPLACE TEMP TABLE selected_source_id AS "
                "SELECT DISTINCT fm.source_id AS id FROM derivation_ref AS d "
                "JOIN selected_canonical_id AS c ON c.id = d.canonical_id "
                "JOIN family_member AS fm ON fm.source_id = d.source_id",
            )
            source_rows = self.connection.execute(
                "SELECT id, json_extract_string(payload_json, '$.source_release_id'), "
                "json_extract_string(payload_json, '$.source_record_id'), "
                "json_extract(payload_json, '$.artifact_ids') "
                "FROM source_assertion JOIN selected_source_id USING (id)",
            ).fetchall()
            self.connection.execute(
                "CREATE OR REPLACE TEMP TABLE selected_record_id AS "
                "SELECT DISTINCT json_extract_string(a.payload_json, '$.source_record_id') "
                "AS id FROM source_assertion AS a JOIN selected_source_id AS s USING (id)",
            )
            locators = dict(
                self.connection.execute(
                    "SELECT id, json_extract_string(payload_json, '$.record_locator') "
                    "FROM source_record JOIN selected_record_id USING (id)",
                ).fetchall()
            )
            for source_id, release_id, record_id, artifact_json in source_rows:
                provenance[source_id] = SourceProvenance(
                    release_id, record_id, orjson.loads(artifact_json), locators[record_id]
                )
        return CandidateRows(
            dict(assertions),
            dict(derivations),
            dict(family_by_source),
            provenance,
            self.labels(candidate_ids),
        )

    def best_question_concept(self, observed_concepts: set[str]) -> tuple[str, int, int] | None:
        row = self.connection.execute(
            "WITH items AS (SELECT "
            "json_extract_string(a.payload_json, '$.object.concept_id') AS finding_id, "
            "json_extract_string(a.payload_json, '$.subject_concept_id') AS candidate_id, "
            "json_extract_string(a.payload_json, '$.qualifiers.polarity') AS polarity "
            "FROM canonical_assertion AS a JOIN concept AS c ON "
            "c.id = json_extract_string(a.payload_json, '$.subject_concept_id') "
            "WHERE json_extract_string(a.payload_json, '$.object.kind') = 'concept' "
            "AND json_extract_string(c.payload_json, '$.kind') = 'condition' "
            "AND json_extract_string(c.payload_json, '$.status') = 'active'), "
            "counts AS (SELECT finding_id, "
            "count(DISTINCT CASE WHEN polarity = 'present' THEN candidate_id END) AS positive, "
            "count(DISTINCT CASE WHEN polarity = 'excluded' THEN candidate_id END) AS excluded, "
            "count(DISTINCT candidate_id) AS coverage_count FROM items "
            "WHERE finding_id NOT IN (SELECT unnest(?::VARCHAR[])) GROUP BY finding_id) "
            "SELECT finding_id, least(positive, excluded) AS separation, coverage_count "
            "FROM counts WHERE positive > 0 AND excluded > 0 "
            "ORDER BY separation DESC, coverage_count DESC, finding_id LIMIT 1",
            [sorted(observed_concepts)],
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None

    def question_provenance(self, concept_id: str) -> tuple[list[str], list[str], list[str]]:
        self._family_members()
        self._derivation_refs()
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE question_canonical AS "
            "SELECT a.id FROM canonical_assertion AS a JOIN concept AS c ON "
            "c.id = json_extract_string(a.payload_json, '$.subject_concept_id') "
            "WHERE json_extract_string(a.payload_json, '$.object.kind') = 'concept' "
            "AND json_extract_string(a.payload_json, '$.object.concept_id') = ? "
            "AND json_extract_string(c.payload_json, '$.kind') = 'condition' "
            "AND json_extract_string(c.payload_json, '$.status') = 'active'",
            [concept_id],
        )
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE question_source AS "
            "SELECT DISTINCT d.source_id FROM derivation_ref AS d "
            "JOIN question_canonical AS a ON d.canonical_id = a.id"
        )
        source_assertion_ids = [
            row[0]
            for row in self.connection.execute(
                "SELECT source_id FROM question_source ORDER BY source_id"
            ).fetchall()
        ]
        if not source_assertion_ids:
            return [], [], []
        family_ids = [
            row[0]
            for row in self.connection.execute(
                "SELECT DISTINCT f.family_id FROM family_member AS f "
                "JOIN question_source AS s ON f.source_id = s.source_id "
                "ORDER BY f.family_id"
            ).fetchall()
        ]
        source_releases = [
            row[0]
            for row in self.connection.execute(
                "SELECT DISTINCT json_extract_string(a.payload_json, '$.source_release_id') "
                "FROM source_assertion AS a JOIN question_source AS s ON a.id = s.source_id "
                "ORDER BY 1"
            ).fetchall()
        ]
        return source_assertion_ids, family_ids, source_releases

    def observation_options(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
        system: str | None = None,
        code: str | None = None,
    ) -> list[tuple[str, str, str, str, str, str]]:
        """Return supported observation concepts, never a global Python catalog."""
        if (system is None) != (code is None):
            raise ValueError("system and code must be specified together")
        # The choice of designation/identifier exactly follows the v0.6 catalog
        # ordering, including its stable ID tie-break inherited from table order.
        sql = (
            "WITH kinds AS (SELECT "
            "json_extract_string(payload_json, '$.object.concept_id') AS concept_id, "
            "max(CASE WHEN json_extract_string(payload_json, '$.relation') = 'has_sign' "
            "THEN 1 ELSE 0 END) AS has_sign, "
            "max(CASE WHEN json_extract_string(payload_json, '$.relation') = 'has_exam_finding' "
            "THEN 1 ELSE 0 END) AS has_exam, "
            "max(CASE WHEN json_extract_string(payload_json, '$.relation') = 'has_symptom' "
            "THEN 1 ELSE 0 END) AS has_symptom FROM canonical_assertion "
            "WHERE json_extract_string(payload_json, '$.object.kind') = 'concept' "
            "AND json_extract_string(payload_json, '$.relation') "
            "IN ('has_sign', 'has_exam_finding', 'has_symptom') GROUP BY concept_id), "
            "labels AS (SELECT json_extract_string(payload_json, '$.concept_id') AS concept_id, "
            "json_extract_string(payload_json, '$.text') AS label, "
            "json_extract_string(payload_json, '$.language') AS language, "
            "row_number() OVER (PARTITION BY concept_id ORDER BY "
            "json_extract_string(payload_json, '$.scope') != 'preferred', "
            "json_extract_string(payload_json, '$.language') != 'en', "
            "json_extract_string(payload_json, '$.text'), id) AS ordinal "
            "FROM designation), "
            "identifiers AS (SELECT "
            "json_extract_string(payload_json, '$.concept_id') AS concept_id, "
            "json_extract_string(payload_json, '$.system') AS system, "
            "json_extract_string(payload_json, '$.code') AS code, "
            "row_number() OVER (PARTITION BY concept_id ORDER BY "
            "json_extract_string(payload_json, '$.relation') "
            "NOT IN ('identity', 'source_code'), "
            "json_extract_string(payload_json, '$.code'), id) AS ordinal "
            "FROM external_identifier), "
            "options AS (SELECT c.id AS concept_id, i.system, i.code, "
            "coalesce(l.label, json_extract_string(c.payload_json, '$.primary_code')) AS label, "
            "coalesce(l.language, 'und') AS language, "
            "CASE WHEN k.has_sign = 1 THEN 'sign' "
            "WHEN k.has_exam = 1 THEN 'exam' ELSE 'symptom' END AS kind "
            "FROM kinds AS k JOIN concept AS c ON c.id = k.concept_id "
            "JOIN identifiers AS i ON i.concept_id = c.id AND i.ordinal = 1 "
            "LEFT JOIN labels AS l ON l.concept_id = c.id AND l.ordinal = 1 "
            "WHERE json_extract_string(c.payload_json, '$.status') = 'active') "
            "SELECT concept_id, system, code, label, language, kind FROM options WHERE "
        )
        if system is not None:
            sql += "system = ? AND code = ? ORDER BY lower(label), code"
            parameters: list[Any] = [system, code]
        else:
            sql += "(lower(label) LIKE ? OR lower(code) LIKE ?) ORDER BY lower(label), code"
            normalized = (query or "").strip().casefold()
            pattern = (
                "%" + normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            )
            parameters = [pattern, pattern]
            sql = sql.replace("LIKE ?", "LIKE ? ESCAPE '\\'")
        if limit > 0:
            sql += " LIMIT ?"
            parameters.append(limit)
        return [tuple(row) for row in self.connection.execute(sql, parameters).fetchall()]
