import math

import pytest

from latros.clinical import ClinicalCase
from latros.common import LatrosError
from latros.reasoning.engine import Engine
from latros.reasoning.questions import next_question


def case(*observations, history=None):
    return ClinicalCase.model_validate(
        dict(
            case_id="invented",
            observations=[dict(concept_id=key, status=status) for key, status in observations],
            question_history=history or [],
        )
    )


def test_numeric_resnik_and_negative_evidence(built):
    root, _ = built
    engine = Engine(root, "test")
    initial = engine.diagnose(case(("HP:9000001", "present")))
    assert initial["safety_status"] == "not_evaluated"
    assert initial["candidate_count"] == 2
    a, b = initial["differential"]
    assert a["score"] == pytest.approx(math.log(3 / 2))
    assert a["exact_mondo_mappings"] == ["MONDO:9000001"]
    assert a["score"] == b["score"]
    negative = engine.diagnose(case(("HP:9000001", "present"), ("HP:9000002", "absent")))
    assert negative["differential"][0]["disease"] == "ORPHA:900002"
    by_id = {d["disease"]: d for d in negative["differential"]}
    assert by_id["ORPHA:900001"]["score"] == pytest.approx(math.log(1.5) * (1 - 0.895))
    for candidate in negative["differential"]:
        evidence = candidate["supporting_evidence"] + candidate["contradicting_evidence"]
        assert sum(x["contribution"] for x in evidence) == candidate["score"]
        assert all(x["assertion_ids"] and x["provenance"] for x in evidence)


def test_unknown_does_not_change_scores_and_missing_frequency_not_penalized(built):
    engine = Engine(built[0], "test")
    base = case(("HP:9000001", "present"))
    original = [(x["disease"], x["score"]) for x in engine.diagnose(base)["differential"]]
    for status in ("unknown", "absent"):
        result = engine.diagnose(case(("HP:9000001", "present"), ("HP:9000003", status)))
        assert [(x["disease"], x["score"]) for x in result["differential"]] == original
        assert not result["differential"][0]["contradicting_evidence"]
    absent = case(("HP:9000001", "present"), ("HP:9000002", "absent"))
    extra = case(("HP:9000001", "present"), ("HP:9000002", "absent"), ("HP:9000003", "absent"))
    assert [r["score"] for r in engine.rank(extra)] == [r["score"] for r in engine.rank(absent)]


def test_question_information_gain_and_no_repetition(built):
    engine = Engine(built[0], "test")
    base = case(("HP:9000001", "present"))
    output = next_question(engine, base)
    question = output["question"]
    assert question["concept_id"] == "HP:9000002"
    assert question["coverage"] == 1
    assert question["information_gain_bits"] > 0.5
    assert question["label_language"] == "fr"
    assert output == next_question(engine, base)
    answered = case(
        ("HP:9000001", "present"), history=[dict(concept_id="HP:9000002", answer="unknown")]
    )
    assert next_question(engine, answered)["question"] is None
    assert [r["score"] for r in engine.rank(answered)] == [r["score"] for r in engine.rank(base)]


def test_question_limit_and_empty_case(built):
    engine = Engine(built[0], "test")
    history = [dict(concept_id=f"HP:90000{i:02}", answer="unknown") for i in range(1, 13)]
    assert next_question(engine, case(history=history))["reason"] == "question_limit"
    assert engine.diagnose(case())["differential"] == []


def test_hierarchy_conflicts_unknown_and_obsolete_inputs(built):
    engine = Engine(built[0], "test")
    assert engine.resolve("HP:9999901") == engine.resolve("HP:9000001")
    assert engine.resolve("HP:9999998") == engine.resolve("HP:9000001")
    assert engine.diagnose(case(("HP:9000004", "present")))["candidate_count"] == 2
    with pytest.raises(LatrosError, match="contradicts"):
        engine.diagnose(case(("HP:9000004", "present"), ("HP:9000001", "absent")))
    for identifier in ("HP:9999999", "HP:8888888", "HP:0000118"):
        with pytest.raises(LatrosError):
            engine.diagnose(case((identifier, "present")))


def test_question_coverage_threshold_and_conflicts(built):
    engine = Engine(built[0], "test")
    base = case(("HP:9000001", "present"))
    a = engine.external["ORPHA:900001"]
    feature = engine.external["HP:9000002"]
    # One of two equal-weight candidates becomes unusable: 50% < 60%.
    engine.conflicts.add((a, feature))
    assert next_question(engine, base)["question"] is None
    with_absence = case(("HP:9000001", "present"), ("HP:9000002", "absent"))
    disease = next(r for r in engine.rank(with_absence) if r["disease"] == "ORPHA:900001")
    assert disease["contradicting_evidence"] == []
    assert disease["frequency_conflicts"] == ["HP:9000002"]


def test_age_sex_ignored_and_unknown_remains_visible(built):
    engine = Engine(built[0], "test")
    base = case(("HP:9000001", "present"), ("HP:9000002", "unknown"))
    result = engine.diagnose(base)
    changed = base.model_copy(update={"age": 88, "sex": "female"})
    assert result == engine.diagnose(changed)
    assert any(
        x["concept_id"] == "HP:9000002" for x in result["differential"][0]["important_unknowns"]
    )


def test_question_tie_breaks_by_external_id(built):
    from copy import deepcopy

    engine = Engine(built[0], "test")
    original = engine.external["HP:9000002"]
    other = engine.external["HP:9000006"]
    engine.ic[other] = engine.ic[original]
    for rows in engine.assertions.values():
        for row in list(rows):
            if row["phenotype_id"] == original:
                clone = deepcopy(row)
                clone["phenotype_id"] = other
                rows.append(clone)
    assert (
        next_question(engine, case(("HP:9000001", "present")))["question"]["concept_id"]
        == "HP:9000002"
    )
