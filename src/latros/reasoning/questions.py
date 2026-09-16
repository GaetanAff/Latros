"""Question utility uses explicitly synthetic weights, never patient probabilities."""

import math
from typing import Any

from latros.clinical.models import ClinicalCase
from latros.reasoning.engine import Engine


def entropy(weights: list[float]) -> float:
    return -sum(p * math.log2(p) for p in weights if p > 0)


def next_question(engine: Engine, case: ClinicalCase) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        case_id=case.case_id,
        snapshot=engine.snapshot,
        safety_status="not_evaluated",
        method="question_v1",
        weight_type="softmax_of_compatibility_not_diagnostic_probabilities",
    )
    observations = engine.observations(case)
    if len(case.question_history) >= 12:
        return base | dict(status="stopped", reason="question_limit", question=None)
    ranked = engine.rank(case)[:10]
    if len(ranked) < 2:
        return base | dict(status="stopped", reason="insufficient_candidates", question=None)
    raw_weights = [math.exp(row["score"] - ranked[0]["score"]) for row in ranked]
    total = sum(raw_weights)
    weights = [value / total for value in raw_weights]
    features = sorted({a["phenotype_id"] for d in ranked for a in engine.assertions[d["_key"]]})
    candidates: list[dict[str, Any]] = []
    for feature in features:
        if feature in observations:
            continue
        external = engine.concepts[feature]["external_id"]
        # Do not ask something already entailed by a present child or absent parent.
        if any(
            (status == "present" and feature in engine.ancestors(key))
            or (status == "absent" and key in engine.ancestors(feature))
            for key, status in observations.items()
        ):
            continue
        root = engine.external.get("HP:0000118")
        if root not in engine.ancestors(feature) or feature == root:
            continue
        estimates: list[float | None] = []
        evidence = []
        for candidate in ranked:
            disease = candidate["_key"]
            annotations = [a for a in engine.assertions[disease] if a["phenotype_id"] == feature]
            value = None
            if annotations and (disease, feature) not in engine.conflicts:
                value = annotations[0]["frequency"].estimate()
                if value is not None:
                    evidence.append(
                        dict(
                            disease=candidate["disease"],
                            estimate=value,
                            frequency=annotations[0]["frequency"].model_dump(),
                            assertion_ids=[a["id"] for a in annotations],
                            provenance=engine.evidence(
                                annotations[0], feature, 0.0, feature, "question_frequency"
                            )["provenance"],
                        )
                    )
            estimates.append(value)
        coverage = sum(w for w, value in zip(weights, estimates, strict=True) if value is not None)
        if coverage < 0.6:
            continue
        yes = (
            sum(w * value for w, value in zip(weights, estimates, strict=True) if value is not None)
            / coverage
        )
        if not 0 < yes < 1:
            continue
        # Missing frequency uses the known-candidate mixture: no assertion of absence,
        # and no evidence for or against that unmeasured candidate for either answer.
        likelihoods = [yes if value is None else value for value in estimates]
        post_yes = [w * p / yes for w, p in zip(weights, likelihoods, strict=True)]
        post_no = [w * (1 - p) / (1 - yes) for w, p in zip(weights, likelihoods, strict=True)]
        gain = entropy(weights) - yes * entropy(post_yes) - (1 - yes) * entropy(post_no)
        if gain <= 1e-12:
            continue
        fr_label = engine.labels.get((feature, "fr"))
        label = fr_label or engine.concepts[feature]["label"]
        candidates.append(
            dict(
                concept_id=external,
                question_type="presence",
                label=label,
                label_language="fr" if fr_label else "en",
                text=f"Le signe « {label} » est-il présent ?",
                allowed_answers=["present", "absent", "unknown"],
                information_gain_bits=gain,
                coverage=coverage,
                information_content=engine.ic.get(feature, 0.0),
                frequency_policy="Beta(1,1) for counts; midpoint for intervals/categories",
                unknown_frequency_policy="known_candidate_mixture; no medical absence inferred",
                evidence=evidence,
            )
        )
    if not candidates:
        return base | dict(
            status="stopped", reason="no_admissible_informative_question", question=None
        )
    candidates.sort(
        key=lambda q: (
            -q["information_gain_bits"],
            -q["coverage"],
            -q["information_content"],
            q["concept_id"],
        )
    )
    return base | dict(
        status="question", question_number=len(case.question_history) + 1, question=candidates[0]
    )
