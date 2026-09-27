"""Versioned, source-scoped projections; the frozen database is never rewritten."""

from pathlib import Path
from typing import Any, Literal

from latros.common import LatrosError, sha256
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2

Phase = Literal["general", "rare"]
SNAPSHOT = "v0.7.0-general-dev-unreviewed"
CONTENT = "bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0"
G4_HASH = "78cdfd2d47f3b1fd7aa87f7f564442d7d5b606ed655fb593b8bc366e007cf9a7"
GENERAL_RELEASE = "medlineplus:2026-09-19"


class ConsultationRepository(CanonicalKnowledgeRepositoryV2):
    def __init__(self, root: Path, snapshot: str, phase: Phase) -> None:
        super().__init__(root, snapshot)
        self.phase = phase
        self.g4_path: Path | None = None
        self.g4_sha256 = G4_HASH if phase == "general" else None
        try:
            if snapshot != SNAPSHOT or self.manifest.content_sha256 != CONTENT:
                raise LatrosError("Consultation policies require the explicitly pinned v0.7 corpus")
            connection = self.connection
            catalog = connection.execute("SELECT current_database()").fetchone()
            assert catalog is not None
            self._base_catalog = '"' + catalog[0].replace('"', '""') + '"'
            if phase == "general":
                self.g4_path = (
                    root / "data/staging/v0.7-g4/quality-v2-release/candidate_assertions_v2.jsonl"
                )
                if not self.g4_path.is_file() or sha256(self.g4_path) != G4_HASH:
                    raise LatrosError(
                        "Pinned G4 retained candidates missing/corrupt; replay G4 offline"
                    )
                connection.execute(
                    "CREATE TEMP TABLE retained_candidate AS SELECT candidate_assertion_id "
                    "FROM read_json_auto(?,format='newline_delimited') "
                    "WHERE review_status='unreviewed' AND len(reviewer_ids)=0 "
                    "AND subject_mapping.status='resolved' "
                    "AND subject_mapping.relation IN ('exact','equivalent') "
                    "AND object_mapping.status='resolved' "
                    "AND object_mapping.relation IN ('exact','equivalent')",
                    [str(self.g4_path)],
                )
                # Structural rare/genetic markers, NOT an invented prevalence classification.
                connection.execute(
                    "CREATE TEMP TABLE rare_marker AS WITH RECURSIVE genetic(id) AS ("
                    "SELECT id FROM main.concept WHERE json_extract_string(payload_json, "
                    "'$.primary_code') IN ('MONDO:0003847','DOID:630') UNION "
                    "SELECT json_extract_string(e.payload_json,'$.child_concept_id') "
                    "FROM genetic g JOIN main.hierarchy_edge e ON "
                    "json_extract_string(e.payload_json,'$.parent_concept_id')=g.id) "
                    "SELECT id FROM genetic UNION SELECT id FROM main.concept WHERE "
                    "json_extract_string(payload_json,'$.primary_code') LIKE 'ORPHA:%' "
                    "UNION SELECT json_extract_string(payload_json,'$.source_concept_id') "
                    "FROM main.concept_mapping WHERE "
                    "json_extract_string(payload_json,'$.target_system')='https://www.orpha.net' "
                    "AND json_extract_string(payload_json,'$.relation') IN ('exact','equivalent') "
                    "AND json_extract_string(payload_json,'$.resolution_status')='resolved' "
                    "AND json_extract_string(payload_json,'$.target_concept_id') IS NOT NULL"
                )
                connection.execute(
                    "CREATE TEMP TABLE scoped_source AS SELECT s.id FROM main.source_assertion s "
                    "JOIN retained_candidate r ON r.candidate_assertion_id="
                    "json_extract_string(s.payload_json,"
                    "'$.raw_value.candidate.candidate_assertion_id') "
                    "WHERE json_extract_string(s.payload_json,'$.source_release_id')="
                    "? AND "
                    "json_extract_string(s.payload_json,'$.subject_concept_id') "
                    "NOT IN (SELECT id FROM rare_marker)",
                    [GENERAL_RELEASE],
                )
            else:
                connection.execute(
                    "CREATE TEMP TABLE scoped_source AS SELECT id FROM main.source_assertion "
                    "WHERE json_extract_string(payload_json,'$.source_release_id') "
                    "LIKE 'orphadata:%' "
                    "OR (json_extract_string(payload_json,'$.source_release_id') LIKE 'monarch:%' "
                    "AND json_extract_string(payload_json,'$.raw_value.primary_knowledge_source') "
                    "IN ('infores:omim','infores:orphanet'))"
                )
            # TEMP shadows only this connection; base tables and the build hash stay intact.
            connection.execute(
                "CREATE TEMP TABLE source_assertion AS SELECT s.* FROM main.source_assertion s "
                "JOIN scoped_source k USING(id)"
            )
            connection.execute(
                "CREATE TEMP TABLE assertion_derivation AS SELECT d.* "
                "FROM main.assertion_derivation d JOIN scoped_source s ON "
                "json_extract_string(d.payload_json,'$.source_assertion_id')=s.id"
            )
            connection.execute(
                "CREATE TEMP TABLE canonical_assertion AS SELECT a.* "
                "FROM main.canonical_assertion a WHERE a.id IN (SELECT "
                "json_extract_string(payload_json,'$.canonical_assertion_id') "
                "FROM assertion_derivation)"
            )
        except Exception:
            self.close()
            raise

    def assert_unchanged(self) -> None:
        super().assert_unchanged()
        if self.g4_path is not None and (
            not self.g4_path.is_file() or sha256(self.g4_path) != G4_HASH
        ):
            raise LatrosError("Pinned G4 candidate artifact changed")

    def resolve_observation(
        self, concept_id: str, system: str, code: str
    ) -> tuple[str | None, str | None]:
        direct = self.connection.execute(
            "SELECT id FROM concept WHERE id=? AND "
            "json_extract_string(payload_json,'$.status')='active'",
            [concept_id],
        ).fetchone()
        if direct:
            return direct[0], None
        identifiers = self.connection.execute(
            "SELECT DISTINCT c.id FROM external_identifier i JOIN concept c ON "
            "c.id=json_extract_string(i.payload_json,'$.concept_id') WHERE "
            "json_extract_string(i.payload_json,'$.system')=? AND "
            "json_extract_string(i.payload_json,'$.code')=? AND "
            "json_extract_string(c.payload_json,'$.status')='active' ORDER BY c.id LIMIT 2",
            [system, code],
        ).fetchall()
        if identifiers:
            return (identifiers[0][0], None) if len(identifiers) == 1 else (None, None)
        mappings = self.connection.execute(
            "SELECT m.id,c.id FROM concept_mapping m JOIN concept c ON "
            "c.id=json_extract_string(m.payload_json,'$.target_concept_id') WHERE "
            "json_extract_string(m.payload_json,'$.target_system')=? AND "
            "json_extract_string(m.payload_json,'$.target_code')=? AND "
            "json_extract_string(m.payload_json,'$.relation') IN ('exact','equivalent') AND "
            "json_extract_string(m.payload_json,'$.resolution_status')='resolved' AND "
            "json_extract_string(c.payload_json,'$.status')='active' ORDER BY m.id LIMIT 2",
            [system, code],
        ).fetchall()
        return (mappings[0][1], mappings[0][0]) if len(mappings) == 1 else (None, None)

    def supported_findings(self, ids: list[str]) -> set[str]:
        return {
            row[0]
            for row in self.connection.execute(
                "SELECT DISTINCT json_extract_string(payload_json,'$.object.concept_id') "
                "AS finding "
                "FROM canonical_assertion WHERE finding IN (SELECT unnest(?::VARCHAR[]))",
                [ids],
            ).fetchall()
        }

    def single_source_family_ids(self) -> set[str]:
        self._family_members()
        rows = self.connection.execute(
            "SELECT DISTINCT family_id FROM family_member f "
            "JOIN scoped_source s ON s.id=f.source_id"
        ).fetchall()
        if len(rows) != 1:
            raise LatrosError(
                "Experimental MedlinePlus policy requires exactly one editorial family"
            )
        return {rows[0][0]}

    def case_candidate_ids(
        self, observations: list[tuple[str, str]], families: set[str]
    ) -> list[str]:
        return self.matching_candidate_ids(observations, families)

    def general_question(self, ids: list[str], excluded: set[str]) -> tuple[str, int, int] | None:
        # Missing annotations are NOT negative evidence. This ranks documentation variation,
        # not a calibrated gain or an opposing-polarity discriminant.
        row = self.connection.execute(
            "WITH items AS (SELECT "
            "json_extract_string(payload_json,'$.object.concept_id') AS finding_id, "
            "json_extract_string(payload_json,'$.subject_concept_id') AS disease_id "
            "FROM canonical_assertion WHERE "
            "json_extract_string(payload_json,'$.qualifiers.polarity')='present' "
            "AND disease_id IN (SELECT unnest(?::VARCHAR[]))), counts AS ("
            "SELECT finding_id,count(DISTINCT disease_id) AS documented FROM items "
            "WHERE finding_id NOT IN (SELECT unnest(?::VARCHAR[])) GROUP BY finding_id) "
            "SELECT finding_id,least(documented,?-documented),documented FROM counts "
            "WHERE documented>0 AND documented<? "
            "ORDER BY least(documented,?-documented) DESC,documented DESC,finding_id LIMIT 1",
            [ids, sorted(excluded), len(ids), len(ids), len(ids)],
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None

    def scope_metrics(self) -> dict[str, Any]:
        assertions = self.connection.execute("SELECT count(*) FROM canonical_assertion").fetchone()
        sources = self.connection.execute("SELECT count(*) FROM source_assertion").fetchone()
        findings = self.connection.execute(
            "SELECT count(DISTINCT json_extract_string(payload_json,'$.object.concept_id')) "
            "FROM canonical_assertion"
        ).fetchone()
        only = (
            self.connection.execute(
                "SELECT count(DISTINCT json_extract_string(a.payload_json,'$.subject_concept_id')) "
                "FROM canonical_assertion a WHERE NOT EXISTS (SELECT 1 FROM "
                f"{self._base_catalog}.main.source_assertion s "
                "WHERE json_extract_string(s.payload_json,'$.subject_concept_id')="
                "json_extract_string(a.payload_json,'$.subject_concept_id') AND "
                "json_extract_string(s.payload_json,'$.source_release_id')<>?)",
                [GENERAL_RELEASE],
            ).fetchone()
            if self.phase == "general"
            else None
        )
        assert assertions is not None and sources is not None and findings is not None
        return {
            "phase": self.phase,
            "diseases": len(self.all_candidate_ids()),
            "assertions": assertions[0],
            "sources": sources[0],
            "findings": findings[0],
            "medlineplus_only_diseases": only[0] if only else None,
            "g4_sha256": G4_HASH if self.phase == "general" else None,
        }

    def rare_question(self, ids: list[str], excluded: set[str]) -> tuple[str, int, int] | None:
        if not ids:
            return None
        row = self.connection.execute(
            "WITH items AS (SELECT "
            "json_extract_string(payload_json,'$.object.concept_id') AS finding_id, "
            "json_extract_string(payload_json,'$.subject_concept_id') AS candidate_id, "
            "json_extract_string(payload_json,'$.qualifiers.polarity') AS polarity "
            "FROM canonical_assertion WHERE candidate_id IN "
            "(SELECT candidate_id FROM selected_matching_candidate_id)), "
            "counts AS (SELECT finding_id, "
            "count(DISTINCT CASE WHEN polarity='present' THEN candidate_id END) AS positive, "
            "count(DISTINCT CASE WHEN polarity='excluded' THEN candidate_id END) AS negative, "
            "count(DISTINCT candidate_id) AS documented FROM items "
            "WHERE finding_id NOT IN (SELECT unnest(?::VARCHAR[])) GROUP BY finding_id) "
            "SELECT finding_id,least(positive,negative),documented FROM counts "
            "WHERE positive>0 AND negative>0 "
            "ORDER BY least(positive,negative) DESC,documented DESC,finding_id LIMIT 1",
            [sorted(excluded)],
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None
