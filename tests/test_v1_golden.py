"""Freeze the complete public v1 payloads before introducing v2 adapters."""

import hashlib

from latros.clinical import ClinicalCase
from latros.common import encoded
from latros.reasoning.engine import Engine
from latros.reasoning.questions import next_question


def _case() -> ClinicalCase:
    return ClinicalCase.model_validate(
        {
            "case_id": "invented",
            "observations": [{"concept_id": "HP:9000001", "status": "present"}],
            "question_history": [],
        }
    )


def _digest(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def test_semantic_v1_complete_output_is_frozen(built):
    engine = Engine(built[0], "test")
    assert _digest(engine.diagnose(_case())) == (
        "31845c3a42cd9474010c8c2d30d25a73e98a525ea4398b1042be56e181c514fc"
    )


def test_question_v1_complete_output_is_frozen(built):
    engine = Engine(built[0], "test")
    assert _digest(next_question(engine, _case())) == (
        "2456ada9d9547b71aa2ecde5b646b86f009bf9e640405d3c92dbc8177e2dbb73"
    )
