"""Offline synthetic scenario comparison; never a clinical evaluation."""

import hashlib
import json
import socket
import time
from pathlib import Path

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import encoded, stable_id
from latros.knowledge.consultation_repository import SNAPSHOT
from latros.ui.server import _case_with_question_answer


def main() -> None:
    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline benchmark attempted a network connection")

    socket.socket.connect = deny  # type: ignore[method-assign, assignment]
    socket.socket.connect_ex = deny  # type: ignore[method-assign, assignment]
    socket.create_connection = deny  # type: ignore[assignment]
    socket.getaddrinfo = deny  # type: ignore[assignment]
    root = Path(__file__).resolve().parents[1]
    service = ResearchApplicationService(root)
    scenarios = {
        "rhinitis": ["HP:0031417"],
        "sinus": ["HP:0031417", "HP:0002315", "HP:0001742"],
        "pharyngeal": ["HP:0001945", "HP:0033050"],
        "respiratory": ["HP:0001945", "HP:0012735"],
        "urinary": ["HP:0100639", "HP:0001945"],
        "digestive": ["HP:0002027", "HP:0002013"],
        "ambiguous": ["HP:0001945", "HP:0002315"],
        "rare_multisystem": ["HP:0000268", "HP:0000490", "HP:0003758"],
    }
    report = {"synthetic_not_clinical_validation": True, "scenarios": {}}
    try:
        general = service._general_strategy(SNAPSHOT, "general_question_v2")
        report["general_scope"] = general.repository.scope_metrics()
        for name, codes in scenarios.items():
            print("scenario", name, flush=True)
            options = service.navigation_concepts(
                SNAPSHOT, "general_v1", "http://purl.obolibrary.org/obo/hp.owl", codes, "en"
            )
            case = ClinicalCaseV2.model_validate(
                {
                    "schema_version": 2,
                    "case_id": "synthetic-policy-" + name,
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
                            "kind": o["observation_kind"],
                            "observation_id": f"obs-{i}",
                            "concept": {
                                "concept_id": o["concept_id"],
                                "coding": {
                                    "system": o["system"],
                                    "code": o["code"],
                                    "display": o["label"],
                                },
                            },
                            "clinical_status": "present",
                            "evaluation_status": "assessed",
                            "acquisition_method": "reported",
                            "provenance": {
                                "provenance_id": f"prov-{i}",
                                "origin_type": "patient_report",
                            },
                        }
                        for i, o in enumerate(options)
                    ],
                }
            )
            results = {}
            for strategy in ("general_v1", "general_question_v2", "rare_question_v1"):
                print("diagnose", name, strategy, flush=True)
                start = time.perf_counter()
                result = service.diagnose(SNAPSHOT, case, strategy, "v2")
                question = service.next_question(SNAPSHOT, case, strategy, "v2")
                results[strategy] = {
                    "seconds": round(time.perf_counter() - start, 3),
                    "status": result.status,
                    "coverage": result.coverage.coverage_ratio,
                    "abstention": result.abstention.reason if result.abstention else None,
                    "top": [
                        {"id": c.candidate_id, "label": c.label, "score": c.aggregate.value}
                        for c in result.candidates[:5]
                    ],
                    "candidates": len(result.candidates),
                    "first_question": question.question.concept.model_dump()
                    if question.question
                    else None,
                    "result_sha256": hashlib.sha256(
                        encoded(result.model_dump(mode="json"))
                    ).hexdigest(),
                }
            sequence = []
            for _ in range(7):
                q = service.next_question(SNAPSHOT, case, "general_question_v2", "v2")
                if q.question is None:
                    stop = q.stop_reason
                    break
                sequence.append(q.question.concept.code)
                option = service.resolve_question_concept(
                    SNAPSHOT,
                    "general_question_v2",
                    q.question.concept.system,
                    q.question.concept.code,
                )
                case = _case_with_question_answer(
                    case, q.question.question_id, option.model_dump(mode="json"), "unknown"
                )
                # Stabilize generated synthetic IDs, not patient observations.
                payload = case.model_dump(mode="json")
                new = stable_id("synthetic_answer", name, q.question.concept.code)
                payload["observations"][-1]["observation_id"] = new
                payload["question_history"][-1]["resulting_observation_id"] = new
                case = ClinicalCaseV2.model_validate(payload)
            report["scenarios"][name] = {
                "resolved_codes": [o["code"] for o in options],
                "requested_codes": codes,
                "comparison": results,
                "general_sequence_unknown_answers": sequence,
                "stop_reason": stop,
                "repetitions": len(sequence) - len(set(sequence)),
            }
            assert len(sequence) == len(set(sequence)), "Repeated general finding"
            if name == "rhinitis":
                first = results["general_question_v2"]["first_question"]
                assert first is None or first["code"] not in {"HP:0000730", "HP:0001249"}
            print(name, sequence, stop)
    finally:
        service.close()
    destination = root / "data/staging/consultation-policies/benchmark.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
