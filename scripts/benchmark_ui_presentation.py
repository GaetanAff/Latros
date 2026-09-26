"""Reproducible offline search timings on the immutable local v0.7 runtime."""

import argparse
import json
import socket
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from latros.application.service import ResearchApplicationService
from latros.knowledge.presentation_repository import Language

QUERIES: list[tuple[Language, str, str]] = [
    ("fr", "nez qui coule", "HP:0031417"),
    ("de", "Schnupfen", "HP:0031417"),
    ("en", "runny nose", "HP:0031417"),
    ("fr", "mal à la gorge", "HP:0033050"),
    ("de", "Halsschmerzen", "HP:0033050"),
    ("en", "sore throat", "HP:0033050"),
    ("fr", "mal au ventre", "HP:0002027"),
    ("de", "Bauchschmerzen", "HP:0002027"),
    ("en", "stomach pain", "HP:0002027"),
    ("fr", "tête qui tourne", "HP:0002321"),
    ("de", "mir ist schwindelig", "HP:0002321"),
    ("en", "dizzy", "HP:0002321"),
    ("fr", "mal de tête", "HP:0002315"),
    ("de", "Kopfschmerzen", "HP:0002315"),
    ("en", "headache", "HP:0002315"),
    ("fr", "nez bouché", "HP:0001742"),
    ("de", "verstopfte Nase", "HP:0001742"),
    ("en", "blocked nose", "HP:0001742"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--phase-breakdown", action="store_true")
    args = parser.parse_args()

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("External network forbidden")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.getaddrinfo = blocked
    service = ResearchApplicationService(args.root)
    report: dict[str, Any] = {"snapshot": "v0.7.0-general-dev-unreviewed", "warm": []}
    try:
        start = perf_counter()
        if args.phase_breakdown:
            presentation = service._presentation_repository(report["snapshot"], "general_v1")
            opened = perf_counter()
            presentation._prepare()
            prepared = perf_counter()
        first = service.search_display_concepts(
            report["snapshot"], "general_v1", "nez qui coule", "fr"
        )
        report["cold_seconds"] = round(perf_counter() - start, 3)
        if args.phase_breakdown:
            report["cold_phases"] = {
                "compatible_open_integrity": round(opened - start, 3),
                "sql_presentation_prepare": round(prepared - opened, 3),
                "first_query_and_labels": round(perf_counter() - prepared, 3),
            }
        assert first[0]["code"] == "HP:0031417"
        # Historical catalog primary codes may differ from the navigation/source code.
        # Check canonical identity, never rewrite its coding for a benchmark.
        presentation = service._presentation_repository(report["snapshot"], "general_v1")
        expected_ids = presentation.resolve_supported_codes(
            presentation.lexicon["system"], sorted({code for _, _, code in QUERIES})
        )
        for language, query, expected in QUERIES:
            timings = []
            for _ in range(3):
                start = perf_counter()
                rows = service.search_display_concepts(
                    report["snapshot"], "general_v1", query, language
                )
                timings.append(perf_counter() - start)
                assert rows[0]["concept_id"] == expected_ids[expected]["concept_id"], (
                    language,
                    query,
                )
            report["warm"].append(
                {
                    "language": language,
                    "query": query,
                    "navigation_code": expected,
                    "catalog_code": rows[0]["code"],
                    "median_seconds": round(median(timings), 3),
                }
            )
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    finally:
        service.close()


if __name__ == "__main__":
    main()
