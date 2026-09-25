"""Query-driven general_v1 runtime over immutable canonical-v2 snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import stable_id
from latros.knowledge.models_v2 import CanonicalAssertion, ConceptObject
from latros.knowledge.repository_v2 import CandidateRows, CanonicalKnowledgeRepositoryV2
from latros.reasoning.general_v1 import (
    ComputedCandidate,
    GeneralV1Strategy,
    ResolvedObservation,
    _source_views,
)
from latros.reasoning.interfaces import CandidateSet
from latros.reasoning.profiles import ReasoningProfile
from latros.reasoning.results_v2 import ContributionV2


class LazyGeneralV1Strategy(GeneralV1Strategy):
    """Preserve general_v1 semantics without constructing the full knowledge graph."""

    def __init__(self, root: Path, snapshot: str, profile: ReasoningProfile) -> None:
        self.root = root
        self.snapshot = snapshot
        self.profile = profile
        self.repository = CanonicalKnowledgeRepositoryV2(root, snapshot)
        self.manifest = self.repository.manifest
        try:
            self._check_profile()
            self._aggregatable = self.repository.aggregatable_family_ids()
        except Exception:
            self.repository.close()
            raise

    def close(self) -> None:
        self.repository.close()

    def generate(self, case: ClinicalCaseV2) -> CandidateSet:
        del case
        ids = self.repository.all_candidate_ids()
        return CandidateSet(
            strategy_id=self.descriptor.strategy_id,
            candidate_ids=ids,
            generation_details={
                "rule": "active_condition_subjects_with_assertions",
                "candidate_count": len(ids),
            },
        )

    def _resolve_observation(
        self, concept_id: str, system: str, code: str
    ) -> tuple[str | None, str | None]:
        return self.repository.resolve_observation(concept_id, system, code)

    def _compute(
        self, candidate_ids: list[str], observations: dict[str, ResolvedObservation]
    ) -> list[ComputedCandidate]:
        allowed = self._aggregatable.copy()
        if not bool(self.profile.parameters.get("allow_unlisted_evidence_families", False)):
            configured = self.profile.parameters.get("family_weights", {})
            if isinstance(configured, dict):
                allowed.intersection_update(configured)
        assessed = [
            (item.concept_id, item.relation)
            for item in observations.values()
            if item.evaluation_status == "assessed"
            and item.clinical_status in {"present", "absent"}
        ]
        matched = set(self.repository.matching_candidate_ids(assessed, allowed))
        selected = [candidate_id for candidate_id in candidate_ids if candidate_id in matched]
        rows = self.repository.candidate_rows(selected, reuse_last_match=True)
        mappings = sorted(
            {item.mapping_id for item in observations.values() if item.mapping_id is not None}
        )
        result: list[ComputedCandidate] = []
        for candidate_id in selected:
            contributions: list[ContributionV2] = []
            family_values: dict[str, list[float]] = {}
            for assertion in rows.assertions.get(candidate_id, []):
                if not isinstance(assertion.object, ConceptObject):
                    continue
                source_ids = sorted(rows.derivations.get(assertion.canonical_assertion_id, []))
                family_ids = sorted(
                    {
                        family_id
                        for source_id in source_ids
                        for family_id in rows.families_by_source.get(source_id, [])
                    }
                )
                for family_id in family_ids:
                    family_source_ids = [
                        source_id
                        for source_id in source_ids
                        if family_id in rows.families_by_source.get(source_id, [])
                    ]
                    contribution = self._contribution_lazy(
                        candidate_id,
                        assertion,
                        family_id,
                        family_source_ids,
                        observations.get(assertion.object.concept_id),
                        rows,
                    )
                    contributions.append(contribution)
                    if contribution.value is not None and family_id in self._aggregatable:
                        family_values.setdefault(family_id, []).append(contribution.value)
            family_scores = {
                family_id: sum(values) / len(values) for family_id, values in family_values.items()
            }
            weighted = self._aggregate_families(family_scores)
            if weighted is None:
                continue
            result.append(
                ComputedCandidate(
                    candidate_id=candidate_id,
                    label=rows.labels.get(candidate_id, candidate_id),
                    score=weighted,
                    evaluated_count=sum(
                        item.value is not None and item.evidence_family_id in self._aggregatable
                        for item in contributions
                    ),
                    favorable=[item for item in contributions if item.direction == "favorable"],
                    unfavorable=[item for item in contributions if item.direction == "unfavorable"],
                    unknown=[item for item in contributions if item.direction == "unknown"],
                    source_views=_source_views(contributions),
                    mappings=mappings,
                )
            )
        return sorted(
            result, key=lambda item: (-item.score, -item.evaluated_count, item.candidate_id)
        )

    def _contribution_lazy(
        self,
        candidate_id: str,
        assertion: CanonicalAssertion,
        family_id: str,
        source_ids: list[str],
        observation: ResolvedObservation | None,
        rows: CandidateRows,
    ) -> ContributionV2:
        assert isinstance(assertion.object, ConceptObject)
        finding_concept_id = assertion.object.concept_id
        value: float | None = None
        direction: Literal["favorable", "unfavorable", "unknown"] = "unknown"
        reason = "finding_not_observed"
        if observation is not None and observation.relation != assertion.relation:
            reason = "observation_relation_mismatch"
        elif observation is not None and (
            observation.evaluation_status != "assessed" or observation.clinical_status == "unknown"
        ):
            reason = "finding_unknown_or_not_assessable"
        elif observation is not None:
            expected_present = assertion.qualifiers.polarity == "present"
            observed_present = observation.clinical_status == "present"
            value = 1.0 if expected_present == observed_present else -1.0
            direction = "favorable" if value > 0 else "unfavorable"
            reason = "explicit_polarity_match" if value > 0 else "explicit_polarity_conflict"
        provenance: list[dict[str, Any]] = []
        for source_id in source_ids:
            source = rows.provenance[source_id]
            provenance.append(
                {
                    "source_assertion_id": source_id,
                    "source_release_id": source.source_release_id,
                    "source_record_id": source.source_record_id,
                    "record_locator": source.record_locator,
                    "artifact_ids": source.artifact_ids,
                }
            )
        source_releases = sorted(
            {rows.provenance[source_id].source_release_id for source_id in source_ids}
        )
        return ContributionV2(
            contribution_id=stable_id(
                "reasoning_contribution",
                candidate_id,
                assertion.canonical_assertion_id,
                family_id,
            ),
            direction=direction,
            observation=observation.observation_id if observation else "not_observed",
            finding=finding_concept_id,
            value=value,
            scale_id=self.descriptor.score_scale_id,
            reason=reason,
            source_release_id=source_releases[0],
            assertion_ids=source_ids,
            evidence_family_id=family_id,
            provenance=provenance,
            details={
                "canonical_assertion_id": assertion.canonical_assertion_id,
                "relation": assertion.relation,
                "assertion_polarity": assertion.qualifiers.polarity,
                "aggregatable": family_id in self._aggregatable,
                "all_source_release_ids": source_releases,
            },
        )

    def _select_question(
        self, observed_concepts: set[str]
    ) -> tuple[str, list[str], list[str], list[str], int, float] | None:
        best = self.repository.best_question_concept(observed_concepts)
        if best is None:
            return None
        concept_id, separation, coverage_count = best
        assertion_ids, family_ids, source_ids = self.repository.question_provenance(concept_id)
        candidate_count = len(self.repository.all_candidate_ids())
        return (
            concept_id,
            assertion_ids,
            family_ids,
            source_ids,
            separation,
            coverage_count / candidate_count,
        )

    def _question_label(self, concept_id: str) -> str:
        return self.repository.labels([concept_id]).get(concept_id, concept_id)

    def _question_coding(self, concept_id: str) -> tuple[str, str]:
        return self.repository.first_external_identifier(concept_id)
