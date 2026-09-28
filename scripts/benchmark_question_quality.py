"""Reproducible, offline UX diagnostics for general questions; not clinical validation."""

import argparse
import hashlib
import json
import socket
from pathlib import Path
from typing import Any

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import stable_id
from latros.knowledge.consultation_repository import SNAPSHOT
from latros.knowledge.presentation_repository import Language
from latros.reasoning.results_v2 import QuestionResultV2
from latros.ui.server import _case_with_question_answer

HPO_SYSTEM = "http://purl.obolibrary.org/obo/hp.owl"
STRATEGY = "general_question_v2"

# These are synthetic UX probes, not diagnoses or clinical review cases.
SCENARIOS: dict[str, tuple[str, ...]] = {
    "headache": ("HP:0002315",),
    "sore_throat": ("HP:0033050",),
    "cold_like": ("HP:0031417", "HP:0012735"),
    "sinus_like": ("HP:0031417", "HP:0002315", "HP:0001742"),
    "cough": ("HP:0012735",),
    "fever": ("HP:0001945",),
    "abdominal_pain": ("HP:0002027",),
    "diarrhea": ("HP:0002014",),
    "urinary_symptom": ("HP:0100639",),
    "chest_pain": ("HP:0100749",),
    "low_back_pain": ("HP:0003419",),
    "joint_pain": ("HP:0002829",),
    "fatigue": ("HP:0012378",),
    "vertigo": ("HP:0002321",),
}


def _deny_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("Question benchmark attempted a network connection")


def _case(name: str, options: list[dict[str, Any]]) -> ClinicalCaseV2:
    return ClinicalCaseV2.model_validate(
        {
            "schema_version": 2,
            "case_id": "synthetic-question-quality-" + name,
            "subject_context": {
                "age": {
                    "kind": "quantity",
                    "value": 30,
                    "unit": "year",
                    "system": "http://unitsofmeasure.org",
                    "code": "a",
                }
            },
            "observations": [
                {
                    "kind": option["observation_kind"],
                    "observation_id": f"observation-initial-{index}",
                    "concept": {
                        "concept_id": option["concept_id"],
                        "coding": {
                            "system": option["system"],
                            "code": option["code"],
                            "display": option["label"],
                        },
                    },
                    "clinical_status": "present",
                    "evaluation_status": "assessed",
                    "acquisition_method": "reported",
                    "provenance": {
                        "provenance_id": f"provenance-initial-{index}",
                        "origin_type": "patient_report",
                    },
                }
                for index, option in enumerate(options)
            ],
        }
    )


def _stabilize_answer(case: ClinicalCaseV2, name: str, code: str) -> ClinicalCaseV2:
    payload = case.model_dump(mode="json")
    observation_id = stable_id("question_quality_answer", name, code)
    payload["observations"][-1]["observation_id"] = observation_id
    payload["question_history"][-1]["resulting_observation_id"] = observation_id
    return ClinicalCaseV2.model_validate(payload)


def _scenario(
    service: ResearchApplicationService, name: str, codes: tuple[str, ...], max_questions: int
) -> dict[str, Any]:
    options = service.navigation_concepts(SNAPSHOT, "general_v1", HPO_SYSTEM, list(codes), "en")
    resolved_codes = [str(option["code"]) for option in options]
    resolution = {
        requested: {"concept_id": option["concept_id"], "canonical_code": option["code"]}
        for requested, option in zip(dict.fromkeys(codes), options, strict=False)
    }
    if len(options) != len(set(codes)):
        return {
            "requested_codes": list(codes),
            "resolved_codes": resolved_codes,
            "requested_to_canonical": resolution,
            "status": "input_not_fully_resolved",
        }
    case = _case(name, options)
    sequence: list[dict[str, Any]] = []
    stop_reason: str | None = None
    for _ in range(max_questions + 1):
        result = service.next_question(SNAPSHOT, case, STRATEGY, "v2")
        assert isinstance(result, QuestionResultV2)
        if result.question is None:
            stop_reason = result.stop_reason
            break
        if len(sequence) == max_questions:
            stop_reason = "benchmark_cap_reached"
            break
        question = result.question
        languages: tuple[Language, ...] = ("fr", "de", "en")
        displays = {
            language: service.display_question(
                SNAPSHOT, STRATEGY, question.concept.system, question.concept.code, language
            )
            for language in languages
        }
        sequence.append(
            {
                "question_id": question.question_id,
                "concept_code": question.concept.code,
                "source_label": question.concept.label,
                "text_by_language": {
                    language: {
                        "question_text": display.get("question_text"),
                        "display_label": display.get("display_label"),
                        "fallback_english": display.get("fallback_english"),
                    }
                    for language, display in displays.items()
                },
            }
        )
        option = service.resolve_question_concept(
            SNAPSHOT, STRATEGY, question.concept.system, question.concept.code
        )
        case = _stabilize_answer(
            _case_with_question_answer(
                case, question.question_id, option.model_dump(mode="json"), "unknown"
            ),
            name,
            question.concept.code,
        )
    sequence_codes = [item["concept_code"] for item in sequence]
    return {
        "requested_codes": list(codes),
        "resolved_codes": resolved_codes,
        "requested_to_canonical": resolution,
        "status": "measured",
        "unknown_answer_sequence": sequence,
        "question_count": len(sequence),
        "stop_reason": stop_reason,
        "repeated_question_concepts": len(sequence_codes) - len(set(sequence_codes)),
        "asked_initial_observation": sorted(set(sequence_codes) & set(resolved_codes)),
        "english_fallback_questions": {
            language: sum(
                bool(item["text_by_language"][language]["fallback_english"]) for item in sequence
            )
            for language in ("fr", "de")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-questions", type=int, default=6)
    parser.add_argument(
        "--output", type=Path, default=Path("data/staging/question-quality/benchmark.json")
    )
    args = parser.parse_args()
    if not 1 <= args.max_questions <= 6:
        parser.error("--max-questions must be between 1 and 6")
    socket.socket.connect = _deny_network  # type: ignore[method-assign, assignment]
    socket.socket.connect_ex = _deny_network  # type: ignore[method-assign]
    socket.create_connection = _deny_network  # type: ignore[assignment]
    socket.getaddrinfo = _deny_network  # type: ignore[assignment]
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    report: dict[str, Any] = {
        "snapshot": SNAPSHOT,
        "strategy": STRATEGY,
        "synthetic_not_clinical_validation": True,
        "answer_policy": "unknown_for_each_question",
        "max_questions": args.max_questions,
        "scenario_definition_sha256": hashlib.sha256(
            json.dumps(SCENARIOS, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "scenarios": {},
    }
    service = ResearchApplicationService(root)
    try:
        for name, codes in SCENARIOS.items():
            print(name, flush=True)
            report["scenarios"][name] = _scenario(service, name, codes, args.max_questions)
    finally:
        service.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
