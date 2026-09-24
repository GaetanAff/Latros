"""Record byte-for-byte general_v1 outputs on local, untracked snapshot data.

Run before and after runtime changes; the JSON report contains only digests, not
medical source distributions or patient data. Inputs are synthetic examples.
"""

import argparse
import hashlib
import json
import socket
import time
from pathlib import Path
from typing import Any

from latros.application.service import ResearchApplicationService
from latros.clinical.loading import load_clinical_case
from latros.clinical.v2 import ClinicalCaseV2
from latros.reasoning.results_v2 import DifferentialResultV2, QuestionResultV2

EXAMPLES = (
    "respiratory-common",
    "ambiguous-febrile",
    "contradictory",
    "insufficient",
    "empty",
    "outside-corpus",
    "rare-multisystem",
)
SNAPSHOT = "v0.7.0-general-dev-unreviewed"


def digest(value: DifferentialResultV2 | QuestionResultV2) -> str:
    return hashlib.sha256(value.model_dump_json().encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected", type=Path)
    arguments = parser.parse_args()

    def reject_network(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("The golden comparison attempted a network connection")

    socket.create_connection = reject_network
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    socket.getaddrinfo = reject_network
    expected = (
        json.loads(arguments.expected.read_text(encoding="utf-8")) if arguments.expected else None
    )
    service = ResearchApplicationService(arguments.root)
    output: dict[str, object] = {"snapshot": SNAPSHOT, "cases": {}}
    cases = output["cases"]
    assert isinstance(cases, dict)
    for name in EXAMPLES:
        case = load_clinical_case(
            (arguments.root / "examples/general" / f"{name}.json").read_bytes()
        )
        assert isinstance(case, ClinicalCaseV2)
        start = time.perf_counter()
        diagnosis = service.diagnose(SNAPSHOT, case, "general_v1")
        assert isinstance(diagnosis, DifferentialResultV2)
        diagnosis_seconds = round(time.perf_counter() - start, 3)
        start = time.perf_counter()
        question = service.next_question(SNAPSHOT, case, "general_v1")
        assert isinstance(question, QuestionResultV2)
        cases[name] = {
            "diagnosis_sha256": digest(diagnosis),
            "question_sha256": digest(question),
            "candidate_count": len(diagnosis.candidates),
            "diagnosis_seconds": diagnosis_seconds,
            "question_seconds": round(time.perf_counter() - start, 3),
        }
        if expected is not None:
            for key in ("diagnosis_sha256", "question_sha256", "candidate_count"):
                if cases[name][key] != expected["cases"][name][key]:
                    raise SystemExit(f"Golden mismatch: {name} {key}")
        print(
            f"{name}: {diagnosis_seconds:.3f}s, {len(diagnosis.candidates)} candidates", flush=True
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    service.close()


if __name__ == "__main__":
    main()
