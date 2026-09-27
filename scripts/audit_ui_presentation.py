"""Offline, SQL-based coverage audit of display-only translations and navigation."""

import json
import socket
from pathlib import Path
from typing import Any

from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2


def main() -> None:
    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Network forbidden")

    socket.socket.connect = blocked
    socket.getaddrinfo = blocked
    root = Path(__file__).resolve().parents[1]
    with CanonicalKnowledgeRepositoryV2(root, "v0.7.0-general-dev-unreviewed") as repository:
        presentation = ObservationPresentationRepository(repository)
        presentation._prepare()
        connection = repository.connection
        total = connection.execute("SELECT count(*) FROM ui_observations").fetchone()[0]
        report: dict[str, Any] = {"searchable_concepts": total, "languages": {}}
        codes = [entry["code"] for entry in presentation.lexicon["entries"]]
        resolved = {}
        for start in range(0, len(codes), 100):
            resolved.update(
                presentation.resolve_supported_codes(
                    presentation.lexicon["system"], codes[start : start + 100]
                )
            )
        report["disabled_lexicon_codes"] = [
            entry["code"]
            for entry in presentation.lexicon["entries"]
            if entry["code"] not in resolved
        ]
        report["historical_primary_code_differences"] = [
            {"navigation_code": code, "catalog_code": option["code"], "label": option["label"]}
            for code, option in sorted(resolved.items())
            if code != option["code"]
        ]
        for language in ("en", "fr", "de"):
            native = connection.execute(
                "SELECT count(DISTINCT o.concept_id) FROM ui_observations o JOIN designation d "
                "ON o.concept_id=json_extract_string(d.payload_json,'$.concept_id') "
                "WHERE json_extract_string(d.payload_json,'$.language')=?",
                [language],
            ).fetchone()[0]
            covered = connection.execute(
                "SELECT count(DISTINCT concept_id) FROM ui_search_terms WHERE language=?",
                [language],
            ).fetchone()[0]
            aliases = connection.execute(
                "SELECT count(*) FROM ui_aliases a JOIN ui_observations o USING(concept_id) "
                "WHERE a.language=? AND a.scope='ui_alias'",
                [language],
            ).fetchone()[0]
            question_count = connection.execute(
                "SELECT count(DISTINCT concept_id) FROM ui_aliases WHERE language=? "
                "AND scope='ui_preferred' AND question!=''",
                [language],
            ).fetchone()[0]
            report["languages"][language] = {
                "native_designations": native,
                "display_covered": covered,
                "public_aliases": aliases,
                "without_translation": total - covered,
                "natural_questions": question_count,
                "potential_english_question_fallback": total - covered,
            }
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
