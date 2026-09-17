"""Regenerate reviewable contract schemas, or fail if tracked schemas are stale."""

import argparse
from pathlib import Path

from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import encoded
from latros.knowledge.frequency import Frequency
from latros.knowledge.importers import TABLES
from latros.sources.registry import Registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "schemas"
    documents = {
        "clinical-case.schema.json": ClinicalCase.model_json_schema(),
        "clinical-case-v2.schema.json": ClinicalCaseV2.model_json_schema(),
        "frequency.schema.json": Frequency.model_json_schema(),
        "source-registry.schema.json": Registry.model_json_schema(),
        "canonical-tables.json": {"schema": "canonical_v1", "tables": TABLES},
    }
    for name, document in documents.items():
        path = root / name
        content = encoded(document)
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                raise SystemExit(f"Outdated schema: {path}; run scripts/export_schemas.py")
        else:
            root.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


if __name__ == "__main__":
    main()
