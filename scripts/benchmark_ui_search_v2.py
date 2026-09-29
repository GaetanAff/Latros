"""Offline discoverability benchmark; curated targets are not clinical ground truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import statistics
import time
from pathlib import Path
from typing import Any

from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2

# Explicit source concept selection tasks, including unsupported concepts. None is a diagnosis.
QUERY_GROUPS = (
    ("HP:0002027", ("mal au bide", "Bauchweh", "stomach ache")),
    ("HP:0002027", ("mal au ventre", "Bauchschmerzen", "abdominal pain")),
    ("HP:0002321", ("tête qui tourne", "mir ist schwindelig", "dizzy")),
    ("HP:0001742", ("nez bouché", "Nase zu", "blocked nose")),
    ("HP:0031417", ("nez qui coule", "laufende Nase", "runny nose")),
    (None, ("oreilles bouchées", "Ohrendruck", "ear pressure")),
    (
        "HP:0100518",
        ("brûlure quand je fais pipi", "Brennen beim Wasserlassen", "burning when urinating"),
    ),
    ("HP:0001962", ("coeur qui bat vite", "Herzrasen", "racing heart")),
    ("HP:0002094", ("souffle court", "Atemnot", "shortness of breath")),
    (None, ("mal derrière les yeux", "Schmerzen hinter den Augen", "pain behind eyes")),
    ("HP:0033050", ("mal à la gorge", "Halsschmerzen", "sore throat")),
    ("HP:0002315", ("mal de tête", "Kopfschmerzen", "headache")),
    ("HP:0002018", ("envie de vomir", "mir ist übel", "nausea")),
    ("HP:0012735", ("je tousse", "ich huste", "coughing")),
    ("HP:0002014", ("selles liquides", "Durchfall", "loose stools")),
    ("HP:0003419", ("douleur au bas du dos", "Kreuzschmerzen", "lower back pain")),
    ("HP:0000989", ("ça me gratte", "es juckt", "itching")),
    ("HP:0001945", ("FIÈVRES", "Fieber", "fever")),
    ("HP:0031417", ("rhinorrhée", "Schnupfen", "nasal discharge")),
    ("HP:0031417", ("nez-qui-coule", "laufende nase", "runnny nose")),
    ("HP:0002094", ("essoufflé", "schlecht Luft bekommen", "breathless")),
    ("HP:0002027", ("ventre mal", "Schmerzen Bauch", "pain abdomen")),
    ("HP:0001742", ("nez bouhé", "verstopfte Nas", "blockd nose")),
    (None, ("absence de fièvre", "kein Fieber", "no fever")),
    (None, ("pas de douleur", "keine Schmerzen", "without pain")),
    (None, ("aucun symptôme", "keine Symptome", "no symptoms")),
)


def benchmark(presentation: ObservationPresentationRepository, modes: list[str]) -> dict[str, Any]:
    presentation._prepare()
    source_codes = [code for code, _ in QUERY_GROUPS if code]
    resolved = presentation.resolve_supported_codes(presentation.lexicon["system"], source_codes)
    outcomes: dict[str, Any] = {}
    for mode in modes:
        rows = []
        for code, queries in QUERY_GROUPS:
            expected = resolved.get(code or "", {}).get("concept_id")
            if code and not expected:
                raise ValueError(f"Unsupported benchmark reference: {code}")
            for language, query in zip(("fr", "de", "en"), queries, strict=True):
                started = time.perf_counter()
                options = presentation.search(query, language, 5, search_mode=mode)
                seconds = time.perf_counter() - started
                ids = [row["concept_id"] for row in options]
                rows.append(
                    {
                        "query": query,
                        "language": language,
                        "expected_source_code": code,
                        "expected_concept_id": expected,
                        "returned_codes": [row["code"] for row in options],
                        "returned_concept_ids": ids,
                        "seconds": seconds,
                        "top1": bool(expected and ids[:1] == [expected]),
                        "top3": bool(expected and expected in ids[:3]),
                        "top5": bool(expected and expected in ids[:5]),
                        "unexpected_suggestion": expected is None and bool(ids),
                    }
                )
        supported = [row for row in rows if row["expected_concept_id"]]
        negatives = [row for row in rows if not row["expected_concept_id"]]
        outcomes[mode] = {
            "supported_queries": len(supported),
            "unsupported_or_negated_queries": len(negatives),
            "top1_count": sum(row["top1"] for row in supported),
            "top3_count": sum(row["top3"] for row in supported),
            "top5_count": sum(row["top5"] for row in supported),
            "no_result_supported": sum(not row["returned_codes"] for row in supported),
            "unexpected_suggestion_count": sum(row["unexpected_suggestion"] for row in negatives),
            "median_seconds": statistics.median(row["seconds"] for row in rows),
            "queries": rows,
        }
    return {
        "benchmark_version": "ui-search-discoverability-1",
        "scope": (
            "software retrieval/explicit selection; not clinical validation or synonym approval"
        ),
        "snapshot": presentation.repository.snapshot,
        "lexicon_version": presentation.lexicon["version"],
        "lexicon_sha256": hashlib.sha256(
            json.dumps(presentation.lexicon, sort_keys=True).encode()
        ).hexdigest(),
        "modes": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("data/staging/ui-search-v2/benchmark.json")
    )
    parser.add_argument("--modes", nargs="+", default=["existing"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "data/staging"):
        raise ValueError("Benchmark outputs belong in ignored data/staging")

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Search benchmark is offline")

    socket.socket.connect = blocked
    socket.getaddrinfo = blocked
    with CanonicalKnowledgeRepositoryV2(root, "v0.7.0-general-dev-unreviewed") as repository:
        report = benchmark(ObservationPresentationRepository(repository), args.modes)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                mode: {key: value for key, value in row.items() if key != "queries"}
                for mode, row in report["modes"].items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
