import math

import pytest
from pydantic import ValidationError

from latros.clinical import ClinicalCase
from latros.knowledge.frequency import Frequency, parse_frequency
from latros.sources.registry import Registry


@pytest.mark.parametrize(
    "raw,kind,estimate",
    [
        (None, "missing", None),
        ("", "missing", None),
        ("7/13", "count", 8 / 15),
        ("0/200", "count", 1 / 202),
        ("22%", "percentage", 0.22),
        ("30–79%", "interval", 0.545),
        ("HP:0040282", "category", 0.545),
        ("HP:0040285", "excluded", 0),
        ("HP:0040280", "category", 1),
    ],
)
def test_frequency_lossless(raw, kind, estimate):
    value = parse_frequency(raw)
    assert value.raw == raw
    assert value.kind == kind
    assert (
        value.estimate() == pytest.approx(estimate)
        if estimate is not None
        else value.estimate() is None
    )
    assert Frequency.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize("raw", ["5/2", "1/0", "101%", "80-20%", "-1%", "frequently"])
def test_invalid_frequency(raw):
    with pytest.raises(ValueError):
        parse_frequency(raw)


def test_invalid_bounds_and_nan():
    with pytest.raises(ValidationError):
        Frequency(kind="percentage", lower=math.nan, upper=math.nan)
    with pytest.raises(ValidationError):
        Frequency(kind="missing", lower=0.2)
    with pytest.raises(ValidationError):
        Frequency(kind="category", category="HP:0040282", lower=0.1, upper=0.9)


def test_observation_states_and_history():
    case = ClinicalCase.model_validate(
        dict(
            case_id="synthetic",
            observations=[
                dict(concept_id="HP:9000001", status="present"),
                dict(concept_id="HP:9000002", status="absent"),
            ],
            question_history=[dict(concept_id="HP:9000003", answer="unknown")],
        )
    )
    assert case.effective_observations() == {
        "HP:9000001": "present",
        "HP:9000002": "absent",
        "HP:9000003": "unknown",
    }


@pytest.mark.parametrize(
    "changes",
    [
        dict(
            observations=[
                dict(concept_id="HP:9000001", status="present"),
                dict(concept_id="HP:9000001", status="absent"),
            ]
        ),
        dict(observations=[dict(concept_id="HP:9000001", status="yes")]),
        dict(observations=[dict(concept_id="MONDO:9000001", status="present")]),
        dict(age=-1),
        dict(age=math.nan),
        dict(secret="not-in-schema"),
        dict(
            observations=[dict(concept_id="HP:9000001", status="present")],
            question_history=[dict(concept_id="HP:9000001", answer="unknown")],
        ),
    ],
)
def test_invalid_cases(changes):
    with pytest.raises(ValidationError):
        ClinicalCase.model_validate(dict(case_id="test", **changes))


@pytest.mark.parametrize("change", ["license", "release", "latest", "hash", "traversal"])
def test_registry_refuses_unpinned_sources(registry, change):
    payload = registry.model_dump()
    source = payload["sources"][0]
    if change == "license":
        del source["license"]
    elif change == "release":
        source["release"] = ""
    elif change == "latest":
        source["artifacts"][0]["url"] = "https://example.test/latest/hp.json"
    elif change == "hash":
        source["artifacts"][0]["sha256"] = "1234"
    else:
        source["artifacts"][0]["filename"] = "../hp.json"
    with pytest.raises(ValidationError):
        Registry.model_validate(payload)
