"""Hash a complete synthetic general_v1 result without saving its payload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2
from latros.reasoning.results_v2 import DifferentialResultV2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.case.read_text(encoding="utf-8"))
    case = ClinicalCaseV2.model_validate(value.get("clinical_case", value))
    service = ResearchApplicationService(args.root)
    try:
        result = service.diagnose("v0.7.0-general-dev-unreviewed", case, "general_v1")
        assert isinstance(result, DifferentialResultV2)
        encoded = result.model_dump_json().encode()
        print(
            json.dumps(
                {
                    "candidate_count": len(result.candidates),
                    "result_bytes": len(encoded),
                    "result_sha256": hashlib.sha256(encoded).hexdigest(),
                },
                sort_keys=True,
            )
        )
    finally:
        service.close()


if __name__ == "__main__":
    main()
