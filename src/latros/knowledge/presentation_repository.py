"""Local display/search projections only, never clinical mappings or assertions."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import orjson

from latros.common import LatrosError
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2

Language = Literal["fr", "de", "en"]
LEXICON_PATH = Path(__file__).resolve().parents[1] / "ui/assets/display-lexicon.json"


def normalize_search(value: str) -> str:
    value = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\b([a-z]{3,}[^s])s\b", r"\1", value)


def load_display_lexicon() -> dict[str, Any]:
    lexicon: dict[str, Any] = orjson.loads(LEXICON_PATH.read_bytes())
    if len(lexicon["entries"]) > 2048:
        raise LatrosError("Oversized display lexicon")
    seen: dict[tuple[str, str], str] = {}
    codes = set()
    for entry in lexicon["entries"]:
        if entry["code"] in codes:
            raise LatrosError("Duplicate display identifier")
        codes.add(entry["code"])
        for language in ("fr", "de", "en"):
            for text in [entry["labels"][language], *entry["aliases"][language]]:
                key = language, normalize_search(text)
                if key in seen and seen[key] != entry["code"]:
                    raise LatrosError("Ambiguous public alias in display lexicon")
                seen[key] = entry["code"]
    return lexicon


class ObservationPresentationRepository:
    """Bounded query results; shared temporary SQL tables live with the read-only runtime."""

    def __init__(self, repository: CanonicalKnowledgeRepositoryV2) -> None:
        self.repository = repository
        self.connection = repository.connection
        self.lexicon = load_display_lexicon()

    def _prepare(self) -> None:
        self.repository.assert_unchanged()
        if self.repository._presentation_ready:
            return
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE ui_observations AS "
            + self.repository.observation_options_sql()
            + "SELECT * FROM options"
        )
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE ui_aliases "
            "(concept_id VARCHAR, code VARCHAR, language VARCHAR, text VARCHAR, "
            "scope VARCHAR, question VARCHAR)"
        )
        codes = [entry["code"] for entry in self.lexicon["entries"]]
        identities = self._resolve_supported_codes(self.lexicon["system"], codes)
        rows = []
        for entry in self.lexicon["entries"]:
            option = identities.get(entry["code"])
            if not option or option["label"] != entry["source_label"]:
                continue  # Fail closed, without rescanning identifiers/designations per alias.
            concept_id = option["concept_id"]
            for language in ("fr", "de", "en"):
                rows.append(
                    (
                        concept_id,
                        entry["code"],
                        language,
                        entry["labels"][language],
                        "ui_preferred",
                        entry["questions"][language],
                    )
                )
                rows.extend(
                    (concept_id, entry["code"], language, text, "ui_alias", "")
                    for text in entry["aliases"][language]
                )
        if rows:
            # One bounded insert instead of hundreds of Python/SQL round trips.
            self.connection.execute(
                "INSERT INTO ui_aliases SELECT "
                + ",".join("unnest(?::VARCHAR[])" for _ in range(6)),
                [list(column) for column in zip(*rows, strict=True)],
            )
        # Normalization matches normalize_search; no source payload is rewritten.
        self.connection.execute(
            "CREATE OR REPLACE TEMP TABLE ui_search_terms AS WITH terms AS ("
            "SELECT o.concept_id, json_extract_string(d.payload_json,'$.language') AS language, "
            "json_extract_string(d.payload_json,'$.text') AS text, "
            "json_extract_string(d.payload_json,'$.scope') AS scope FROM designation d "
            "JOIN ui_observations o ON "
            "o.concept_id=json_extract_string(d.payload_json,'$.concept_id') "
            "UNION ALL SELECT a.concept_id,a.language,a.text,a.scope FROM ui_aliases a "
            "JOIN ui_observations o ON o.concept_id=a.concept_id "
            "UNION ALL SELECT concept_id,'en',code,'identifier' FROM ui_observations) "
            "SELECT *, regexp_replace(trim(regexp_replace("
            "strip_accents(lower(replace(text,'ß','ss'))), "
            "'[^a-z0-9]+',' ','g')), '\\b([a-z]{3,}[^s])s\\b','\\1','g') AS normalized FROM terms"
        )
        self.repository._presentation_ready = True

    def resolve_supported_codes(self, system: str, codes: list[str]) -> dict[str, dict[str, Any]]:
        """Resolve navigation references, never create or broaden a clinical mapping."""
        if len(codes) > 100:
            raise LatrosError("At most 100 navigation identifiers per request")
        return self._resolve_supported_codes(system, codes)

    def _resolve_supported_codes(self, system: str, codes: list[str]) -> dict[str, dict[str, Any]]:
        # Internal lexicon is bounded separately; public navigation remains limited to 100.
        if not codes:
            return {}
        rows = self.connection.execute(
            "WITH identifiers AS (SELECT "
            "json_extract_string(payload_json,'$.concept_id') AS concept_id, "
            "json_extract_string(payload_json,'$.code') AS code FROM external_identifier "
            "WHERE json_extract_string(payload_json,'$.system')=? "
            "AND json_extract_string(payload_json,'$.code') IN (SELECT unnest(?::VARCHAR[])) "
            "AND json_extract_string(payload_json,'$.relation') "
            "IN ('primary','identity','source_code')), "
            "unique_ids AS (SELECT code,min(concept_id) AS concept_id FROM identifiers "
            "GROUP BY code HAVING count(DISTINCT concept_id)=1) "
            "SELECT u.code,o.concept_id,o.system,o.code,o.label,o.language,o.kind "
            "FROM unique_ids u JOIN ui_observations o USING(concept_id) ORDER BY u.code",
            [system, codes],
        ).fetchall()
        return {
            row[0]: dict(
                zip(
                    ("concept_id", "system", "code", "label", "language", "observation_kind"),
                    row[1:],
                    strict=True,
                )
            )
            for row in rows
        }

    def navigation_options(
        self, system: str, codes: list[str], language: Language
    ) -> list[dict[str, Any]]:
        self._prepare()
        resolved = self.resolve_supported_codes(system, codes)
        displays = self.display_labels([row["concept_id"] for row in resolved.values()], language)
        return [
            {**resolved[code], **displays.get(resolved[code]["concept_id"], {})}
            for code in dict.fromkeys(codes)
            if code in resolved
        ]

    def search(self, query: str, language: Language, limit: int) -> list[dict[str, Any]]:
        if not 1 <= limit <= 50:
            raise LatrosError("Concept result limit must be between 1 and 50")
        normalized = normalize_search(query[:120])
        if len(normalized) < 2:
            return []
        self._prepare()
        tokens = normalized.split()[:10]
        token_sql = " AND ".join("contains(normalized, ?)" for _ in tokens)
        # Fuzzy is restricted to explicit public aliases, edit distance one, unique target.
        sql = (
            "WITH matched AS (SELECT concept_id, CASE "
            "WHEN language=? AND normalized=? AND scope IN ('preferred','ui_preferred') THEN 0 "
            "WHEN language=? AND normalized=? THEN 1 "
            "WHEN language=? AND starts_with(normalized,?) THEN 2 "
            f"WHEN language=? AND ({token_sql}) THEN 3 "
            "WHEN language=? AND scope IN ('ui_alias','ui_preferred') AND length(?)>=5 "
            "AND levenshtein(normalized,?)=1 THEN 4 "
            "WHEN language='en' AND (normalized=? OR starts_with(normalized,?) "
            f"OR ({token_sql})) THEN 5 ELSE 99 END AS rank FROM ui_search_terms), "
            "best AS (SELECT concept_id,min(rank) AS rank FROM matched GROUP BY concept_id), "
            "safe AS (SELECT * FROM best WHERE rank<99 AND (rank!=4 OR "
            "(SELECT count(*) FROM best WHERE rank=4)=1)) "
            "SELECT o.concept_id,o.system,o.code,o.label,o.language,o.kind,s.rank "
            "FROM safe s JOIN ui_observations o USING(concept_id) "
            "ORDER BY s.rank,lower(o.label),o.code,o.concept_id LIMIT ?"
        )
        parameters: list[Any] = [
            language,
            normalized,
            language,
            normalized,
            language,
            normalized,
            language,
            *tokens,
            language,
            normalized,
            normalized,
            normalized,
            normalized,
            *tokens,
            limit,
        ]
        rows = self.connection.execute(sql, parameters).fetchall()
        displays = self.display_labels([row[0] for row in rows], language)
        return [
            {
                "concept_id": row[0],
                "system": row[1],
                "code": row[2],
                "label": row[3],
                "language": row[4],
                "observation_kind": row[5],
                "match_rank": row[6],
                **displays.get(
                    row[0],
                    {
                        "display_label": row[3],
                        "display_language": row[4],
                        "fallback_english": row[4] != language,
                    },
                ),
            }
            for row in rows
        ]

    def display_labels(self, ids: list[str], language: Language) -> dict[str, dict[str, Any]]:
        if len(ids) > 100:
            raise LatrosError("At most 100 display labels per request")
        if not ids:
            return {}
        self._prepare()
        rows = self.connection.execute(
            "WITH labels AS (SELECT "
            "json_extract_string(d.payload_json,'$.concept_id') AS concept_id, "
            "json_extract_string(d.payload_json,'$.language') AS language, "
            "json_extract_string(d.payload_json,'$.text') AS text, "
            "json_extract_string(d.payload_json,'$.scope') AS scope, '' AS question, "
            "'source_designation' AS origin FROM designation d "
            "WHERE json_extract_string(d.payload_json,'$.concept_id') "
            "IN (SELECT unnest(?::VARCHAR[])) "
            "UNION ALL SELECT concept_id,language,text,scope,question,'ui_display_lexicon' "
            "FROM ui_aliases WHERE scope='ui_preferred' "
            "AND concept_id IN (SELECT unnest(?::VARCHAR[]))), "
            "ordered AS (SELECT *, row_number() OVER(PARTITION BY concept_id ORDER BY language!=?, "
            "CASE WHEN language='en' AND scope='ui_preferred' THEN 0 "
            "WHEN scope='preferred' THEN 1 WHEN scope='ui_preferred' THEN 2 ELSE 3 END, "
            "language!='en',text) AS ordinal FROM labels WHERE language IN (?,'en')), "
            "active AS (SELECT id FROM concept "
            "WHERE json_extract_string(payload_json,'$.status')='active') "
            "SELECT o.concept_id,o.text,o.language,o.origin,o.question FROM ordered o "
            "JOIN active c ON c.id=o.concept_id WHERE ordinal=1 ORDER BY o.concept_id",
            [ids, ids, language, language],
        ).fetchall()
        return {
            row[0]: {
                "display_label": row[1],
                "display_language": row[2],
                "display_origin": row[3],
                "display_lexicon_version": self.lexicon["version"],
                "fallback_english": row[2] != language,
                "question_text": row[4]
                or {
                    "fr": f"Avez-vous ce symptôme : {row[1]} ?",
                    "de": f"Haben Sie dieses Symptom: {row[1]}?",
                    "en": f"Do you have this symptom: {row[1]}?",
                }[row[2]],
            }
            for row in rows
        }

    def question_display(self, system: str, code: str, language: Language) -> dict[str, Any]:
        self._prepare()
        rows = self.connection.execute(
            "SELECT concept_id,system,code,label,language,kind FROM ui_observations "
            "WHERE system=? AND code=? ORDER BY concept_id",
            [system, code],
        ).fetchall()
        if len(rows) != 1:
            raise LatrosError("Question concept has no unambiguous supported observation type")
        row = rows[0]
        return {
            "source_concept": {
                "concept_id": row[0],
                "system": row[1],
                "code": row[2],
                "label": row[3],
                "language": row[4],
                "observation_kind": row[5],
            },
            **self.display_labels([row[0]], language).get(row[0], {}),
        }
