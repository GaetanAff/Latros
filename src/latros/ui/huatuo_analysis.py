"""Independent, opt-in local hypothesis generation from patient-supplied case data."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Literal

import orjson
from pydantic import Field

from latros.common import LatrosError
from latros.sources.registry import Contract
from latros.ui.models import ResearchSession

PROMPT_VERSION = "huatuo_independent_v1"
MODEL_ID = "HuatuoGPT-3-27B-local"
SYSTEM_PROMPT = """You are an EXPERIMENTAL local model, not a clinician.
The following JSON is only patient-reported information and structured observations.
It contains no Latros differential. Work independently from that input.
Return one valid JSON object ONLY with keys:
  hypotheses: array of 1 to 5 objects {name, reason, uncertainty};
  uncertainties: array of short strings; limitations: short string.
Use tentative language. Separate observations from inference. Do not invent patient findings.
Do not give probabilities, percentages, urgency/triage, treatment or reassurance.
If information is sparse, explicitly say so in uncertainties and limitations.
Do not treat an unknown or skipped answer as absent.
This is not a diagnosis or clinical validation. No markdown, no text outside JSON."""


class LocalHypothesis(Contract):
    name: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=1000)
    uncertainty: str = Field(min_length=1, max_length=1000)


class HuatuoOutput(Contract):
    hypotheses: list[LocalHypothesis] = Field(min_length=1, max_length=5)
    uncertainties: list[str] = Field(default_factory=list, max_length=10)
    limitations: str = Field(min_length=1, max_length=1000)


class HuatuoAnalysisV1(Contract):
    schema_version: Literal[1] = 1
    analysis_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime
    prompt_version: Literal["huatuo_independent_v1"] = "huatuo_independent_v1"
    model_id: Literal["HuatuoGPT-3-27B-local"] = "HuatuoGPT-3-27B-local"
    output_language: Literal["fr", "de", "en"]
    case_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_case: dict[str, Any]
    output: HuatuoOutput
    raw_model_response: str = Field(max_length=20000)
    research_unreviewed: Literal[True] = True
    clinical_validation: Literal[False] = False
    publishable: Literal[False] = False
    safety_status: Literal["not_evaluated"] = "not_evaluated"


def independent_case_payload(session: ResearchSession) -> dict[str, Any]:
    """Allowlist only: never serialize ResearchSession or a stored Latros run."""
    if session.patient_context is None:
        raise LatrosError("Save patient information before requesting local AI analysis")
    return {
        "patient_context": session.patient_context.model_dump(mode="json"),
        "clinical_case": session.clinical_case.model_dump(mode="json"),
        "refinement_answers": [item.model_dump(mode="json") for item in session.refinement_answers],
    }


def case_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()


class HuatuoRequest(Contract):
    revision: int = Field(ge=0)
    language: Literal["fr", "de", "en"] = "fr"


def huatuo_messages(
    payload: dict[str, Any], language: Literal["fr", "de", "en"]
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": orjson.dumps(
                {"patient_case": payload, "output_language": language},
                option=orjson.OPT_SORT_KEYS,
            ).decode(),
        },
    ]


def parse_huatuo_output(raw: str) -> HuatuoOutput:
    """Reject malformed or visibly probabilistic output; no model claim is trusted."""
    if len(raw) > 20000 or re.search(r"\b\d{1,3}\s*%", raw):
        raise LatrosError("Local AI output is oversized or contains an unsupported percentage")
    try:
        document = orjson.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("JSON object required")
        return HuatuoOutput.model_validate(document)
    except (orjson.JSONDecodeError, ValueError) as exc:
        raise LatrosError("Local AI did not return the required structured hypotheses") from exc
