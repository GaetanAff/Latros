"""Profile a real offline general_v1 question/diagnosis without storing case data.

The optional session input must be a locally generated synthetic UI session.
Only timings, counts, memory and output digests are written to the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import orjson
from profile_general_v1_runtime import SNAPSHOT, memory_mb

from latros.application.service import ResearchApplicationService
from latros.clinical.loading import load_clinical_case
from latros.clinical.v2 import ClinicalCaseV2
from latros.reasoning.results_v2 import DifferentialResultV2, QuestionResultV2


def _block_network(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("F3 profile attempted a network connection")


def _load_case(case_path: Path) -> ClinicalCaseV2:
    data = json.loads(case_path.read_text(encoding="utf-8"))
    if "clinical_case" in data:
        return ClinicalCaseV2.model_validate(data["clinical_case"])
    case = load_clinical_case(case_path.read_bytes())
    if not isinstance(case, ClinicalCaseV2):
        raise ValueError("F3 requires a v2 case")
    return case


def _instrument(
    target: Any, names: tuple[str, ...], phases: dict[str, dict[str, float | int]]
) -> None:
    for name in names:
        original: Callable[..., Any] = getattr(target, name)

        def measured(
            *args: Any, _name: str = name, _original: Callable[..., Any] = original, **kwargs: Any
        ) -> Any:
            started = time.perf_counter()
            try:
                return _original(*args, **kwargs)
            finally:
                item = phases[_name]
                item["calls"] += 1
                item["seconds"] += time.perf_counter() - started

        setattr(target, name, measured)


def _timed(label: str, action: Callable[[], Any], report: dict[str, Any]) -> Any:
    started = time.perf_counter()
    result = action()
    report[label] = {"seconds": round(time.perf_counter() - started, 3), "memory": memory_mb()}
    print(label, report[label], flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    socket.create_connection = _block_network
    socket.socket.connect = _block_network
    socket.socket.connect_ex = _block_network
    socket.getaddrinfo = _block_network
    case = _load_case(args.case)
    report: dict[str, Any] = {
        "snapshot": SNAPSHOT,
        "observation_count": len(case.observations),
        "question_history_count": len(case.question_history),
        "initial_memory": memory_mb(),
        "steps": {},
    }
    steps: dict[str, Any] = report["steps"]
    service = _timed("service_startup", lambda: ResearchApplicationService(args.root), steps)
    strategy = _timed(
        "repository_open_and_integrity", lambda: service._general_strategy(SNAPSHOT), steps
    )
    measurements: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"calls": 0, "seconds": 0.0}
    )
    _instrument(
        strategy.repository,
        (
            "all_candidate_ids",
            "resolve_observation",
            "matching_candidate_ids",
            "candidate_rows",
            "best_question_concept",
            "question_provenance",
            "labels",
            "first_external_identifier",
        ),
        measurements,
    )
    _instrument(
        strategy,
        ("_project", "generate", "_compute", "_select_question", "_result_candidate", "_receipt"),
        measurements,
    )
    question = _timed(
        "question_after_answer", lambda: service.next_question(SNAPSHOT, case, "general_v1"), steps
    )
    assert isinstance(question, QuestionResultV2)
    report["question_digest"] = hashlib.sha256(question.model_dump_json().encode()).hexdigest()
    diagnosis = _timed(
        "diagnosis_after_answer", lambda: service.diagnose(SNAPSHOT, case, "general_v1"), steps
    )
    assert isinstance(diagnosis, DifferentialResultV2)
    report["candidate_count"] = len(diagnosis.candidates)
    report["diagnosis_digest"] = hashlib.sha256(diagnosis.model_dump_json().encode()).hexdigest()
    _timed("pydantic_to_json_document", lambda: diagnosis.model_dump(mode="json"), steps)
    document = diagnosis.model_dump(mode="json")
    encoded = _timed("json_encoding", lambda: orjson.dumps(document), steps)
    report["encoded_bytes"] = len(encoded)
    report["method_totals"] = {
        name: {"calls": item["calls"], "seconds": round(item["seconds"], 3)}
        for name, item in sorted(measurements.items())
    }
    service.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
