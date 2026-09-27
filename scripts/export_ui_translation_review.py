"""Explicit offline export of display-only translation drafts and remaining work."""

import argparse
import hashlib
import socket
from pathlib import Path
from typing import Any

import orjson

from latros.common import LatrosError
from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2


def review_rows(presentation: ObservationPresentationRepository) -> list[dict[str, Any]]:
    presentation._prepare()
    entries = {entry["code"]: entry for entry in presentation.lexicon["entries"]}
    rows = presentation.connection.execute(
        "SELECT o.concept_id,o.system,o.code,o.label,min(a.code) "
        "FROM ui_observations o LEFT JOIN ui_aliases a USING(concept_id) "
        "GROUP BY o.concept_id,o.system,o.code,o.label ORDER BY o.concept_id"
    ).fetchall()
    return [
        {
            "role": "translation_review_only_not_clinical_knowledge",
            "concept_id": row[0],
            "system": row[1],
            "canonical_code": row[2],
            "source_label": row[3],
            "draft": entries[row[4]] if row[4] in entries else None,
            "language_reviewer": None,
            "decision_fr": None,
            "decision_de": None,
            "comment": None,
        }
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("External network forbidden")

    socket.socket.connect = blocked
    socket.getaddrinfo = blocked
    root = Path(__file__).resolve().parents[1]
    with CanonicalKnowledgeRepositoryV2(root, "v0.7.0-general-dev-unreviewed") as repository:
        rows = review_rows(ObservationPresentationRepository(repository))
    payload = b"".join(orjson.dumps(row, option=orjson.OPT_SORT_KEYS) + b"\n" for row in rows)
    destination = args.output_dir / "translation-review.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != payload:
        raise LatrosError("Refusing to overwrite an existing translation review export")
    if not destination.exists():
        with destination.open("xb") as handle:
            handle.write(payload)
    print(
        orjson.dumps({"items": len(rows), "sha256": hashlib.sha256(payload).hexdigest()}).decode()
    )


if __name__ == "__main__":
    main()
