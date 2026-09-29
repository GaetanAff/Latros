"""Untrusted local NLP suggestions, confirmed explicitly before clinical use."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal
from uuid import uuid4

import orjson
from pydantic import Field

from latros.application.models import ConceptOption
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError
from latros.sources.registry import Contract

Language = Literal["fr", "de", "en"]
Status = Literal["present", "absent", "unknown"]

SYSTEM_PROMPT = (
    "You only transcribe explicit current symptoms reported by the patient. "
    "Do not diagnose, infer symptoms, ask questions, or use medical knowledge to add facts. "
    "Ignore family history, risk, prevention, treatments and other people's symptoms. "
    'Return ONLY JSON: {"mentions":[{"text":"exact substring",'
    '"status":"present|absent|unknown"}]}. '
    "A negated symptom is absent, uncertainty is unknown. "
    "The text field must occur verbatim in the input. At most 20 mentions."
)


class SymptomInterpretationRequest(Contract):
    revision: int = Field(ge=0)
    language: Language = "fr"


class Mention(Contract):
    text: str = Field(min_length=2, max_length=160)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    status: Status
    options: list[ConceptOption] = Field(default_factory=list, max_length=3)
    suggested_concept_id: str | None = None


class ConfirmedMention(Contract):
    text: str = Field(min_length=2, max_length=160)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    status: Status
    concept_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)


class ConfirmInterpretationRequest(Contract):
    revision: int = Field(ge=0)
    narrative: str = Field(min_length=1, max_length=4000)
    language: Language = "fr"
    confirmed: list[ConfirmedMention] = Field(default_factory=list, max_length=20)


def parse_mentions(raw: str, narrative: str) -> list[tuple[str, int, int, Status]]:
    """Reject fabricated spans; repeated matches are assigned in source order."""
    value = raw.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = orjson.loads(value)
    except orjson.JSONDecodeError as exc:
        raise LatrosError("Local symptom extraction did not return valid JSON") from exc
    items = payload.get("mentions") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) > 20:
        raise LatrosError("Local symptom extraction returned invalid mentions")
    found: list[tuple[str, int, int, Status]] = []
    occupied: set[tuple[int, int]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        phrase, status = item.get("text"), item.get("status")
        if not isinstance(phrase, str) or not 2 <= len(phrase) <= 160:
            continue
        if status not in {"present", "absent", "unknown"}:
            continue
        start = narrative.find(phrase)
        while start >= 0 and (start, start + len(phrase)) in occupied:
            start = narrative.find(phrase, start + 1)
        if start < 0:
            continue
        end = start + len(phrase)
        occupied.add((start, end))
        found.append((phrase, start, end, status))
    return found


def map_mentions(
    extracted: list[tuple[str, int, int, Status]],
    search: Callable[[str], list[dict[str, Any]]],
    snapshot: str,
    strategy: str,
) -> list[Mention]:
    result: list[Mention] = []
    for phrase, start, end, status in extracted:
        raw_options = [
            item
            for item in search(phrase)
            if item.get("observation_kind") in {"symptom", "sign", "exam"}
        ][:3]
        options = [
            ConceptOption(
                snapshot_id=snapshot,
                strategy_id=strategy,
                concept_id=item["concept_id"],
                system=item["system"],
                code=item["code"],
                label=item["label"],
                language=item["language"],
                observation_kind=item["observation_kind"],
            )
            for item in raw_options
        ]
        # Exact/alias match only, with no equally ranked competitor.
        suggested = None
        if options and int(raw_options[0].get("match_rank", 99)) <= 1:
            best_rank = raw_options[0].get("match_rank")
            if len(raw_options) == 1 or raw_options[1].get("match_rank") != best_rank:
                suggested = options[0].concept_id
        result.append(
            Mention(
                text=phrase,
                start=start,
                end=end,
                status=status,
                options=options,
                suggested_concept_id=suggested,
            )
        )
    return result


def confirm_mentions(
    case: ClinicalCaseV2,
    request: ConfirmInterpretationRequest,
    resolve: Callable[[str, str], ConceptOption],
) -> ClinicalCaseV2:
    if not request.confirmed:
        return case
    payload = case.model_dump(mode="json")
    statement_id = f"statement-{uuid4()}"
    payload["source_statements"].append(
        {
            "statement_id": statement_id,
            "text": request.narrative,
            "author_type": "patient",
            "language": request.language,
        }
    )
    existing = {item.concept.concept_id for item in case.observations}
    for item in request.confirmed:
        if request.narrative[item.start : item.end] != item.text:
            raise LatrosError("Confirmed symptom span differs from the patient's text")
        option = resolve(item.system, item.code)
        if option.concept_id != item.concept_id:
            raise LatrosError("Confirmed symptom is not a supported canonical concept")
        if item.concept_id in existing:
            continue
        existing.add(item.concept_id)
        observation_id = f"observation-{uuid4()}"
        concept = {
            "concept_id": option.concept_id,
            "coding": {"system": option.system, "code": option.code, "display": option.label},
        }
        payload["observations"].append(
            {
                "kind": option.observation_kind,
                "observation_id": observation_id,
                "concept": concept,
                "clinical_status": item.status,
                "evaluation_status": "assessed",
                "uncertainty_reason": "unknown_to_subject" if item.status == "unknown" else None,
                "acquisition_method": "reported",
                "provenance": {
                    "provenance_id": f"provenance-{uuid4()}",
                    "origin_type": "patient_report",
                    "source_statement_id": statement_id,
                },
            }
        )
        payload["observation_proposals"].append(
            {
                "proposal_id": f"proposal-{uuid4()}",
                "source_statement_id": statement_id,
                "span": {"start": item.start, "end": item.end, "text": item.text},
                "candidates": [{"concept": concept, "extraction_confidence": 0.0}],
                "method": {
                    "kind": "llm",
                    "tool": "Qwen3.5-9B-local",
                    "version": "symptom-extraction-v1",
                    "parameters": {
                        "review": "patient_confirmed",
                        "mapping": "local_search_patient_choice",
                        "not_clinical_confidence": "true",
                    },
                },
                "state": "accepted",
                "confirmed_observation_id": observation_id,
            }
        )
    return ClinicalCaseV2.model_validate(payload)
