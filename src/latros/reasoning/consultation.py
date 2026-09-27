"""Explicit experimental General/Rare policies, without replacing general_v1."""

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, encoded, stable_id
from latros.knowledge.consultation_repository import ConsultationRepository, Phase
from latros.knowledge.repository_v2 import CandidateRows, ScoringAssertion
from latros.reasoning.general_v1 import GENERAL_V1_DESCRIPTOR, ResolvedObservation
from latros.reasoning.general_v1_lazy import LazyGeneralV1Strategy
from latros.reasoning.interfaces import CandidateSet
from latros.reasoning.profiles import ReasoningProfile, load_reasoning_profile
from latros.reasoning.results_v2 import (
    AdaptiveQuestionV2,
    ContributionV2,
    CoverageAssessment,
    QuestionConcept,
    QuestionResultV2,
    RunReceipt,
)

CONSULTATION_IDS = ("general_question_v2", "rare_question_v1")
DESCRIPTORS = {
    name: GENERAL_V1_DESCRIPTOR.model_copy(
        update={
            "strategy_id": name,
            "strategy_version": "2" if name == "general_question_v2" else "1",
            "score_scale_id": f"{name}.compatibility",
            "candidate_generation": "Source-scoped candidates; not prevalence classification",
            "question_strategy": (
                "Case-conditioned G4-retained documentation variation; unknown is not negative"
                if name == "general_question_v2"
                else "Explicit opposing polarity in rare-oriented source scope"
            ),
        }
    )
    for name in CONSULTATION_IDS
}


class ConsultationStrategy(LazyGeneralV1Strategy):
    repository: ConsultationRepository

    def __init__(self, root: Path, snapshot: str, profile: ReasoningProfile) -> None:
        self.root, self.snapshot, self.profile = root, snapshot, profile
        self.phase: Phase = "general" if profile.strategy_id == "general_question_v2" else "rare"
        self.descriptor = DESCRIPTORS[profile.strategy_id]
        self.repository = ConsultationRepository(root, snapshot, self.phase)
        self.manifest = self.repository.manifest
        try:
            self._check_profile()
            self._aggregatable = (
                self.repository.single_source_family_ids()
                if self.phase == "general"
                else self.repository.aggregatable_family_ids()
            )
        except Exception:
            self.close()
            raise

    def _check_profile(self) -> None:
        # New policy declares a pinned extension, NOT compatibility silently added to a manifest.
        parent = self.profile.parameters["parent_profile_id"]
        parent_path = (
            Path(__file__).resolve().parents[3] / "profiles/general_v1-general-unreviewed.json"
        )
        if not parent_path.is_file():
            parent_path = (
                Path(__file__).resolve().parents[1] / "profiles/general_v1-general-unreviewed.json"
            )
        parent_profile = load_reasoning_profile(parent_path)
        if (
            parent not in self.manifest.compatible_profiles
            or parent_profile.profile_id != parent
            or parent_profile.profile_sha256 != self.profile.parameters["parent_profile_sha256"]
            or self.profile.strategy_id != self.descriptor.strategy_id
            or self.profile.strategy_version != self.descriptor.strategy_version
            or self.profile.score_scale.scale_id != self.descriptor.score_scale_id
            or not self.profile.accepts_snapshot(self.snapshot, self.manifest.schema_version)
            or self.profile.parameters["snapshot_content_sha256"] != self.manifest.content_sha256
            or self.profile.score_scale.calibrated
            or (
                self.phase == "general"
                and self.profile.parameters["g4_retained_sha256"] != self.repository.g4_sha256
            )
        ):
            raise LatrosError("Invalid explicit consultation profile binding")
        budget = self.profile.parameters["maximum_questions"]
        if not isinstance(budget, int) or not 1 <= budget <= 20:
            raise LatrosError("Question budget must be an engineering bound of 1–20")

    def generate(self, case: ClinicalCaseV2) -> CandidateSet:
        observations, _, _ = self._project(case)
        pairs = [
            (item.concept_id, item.relation)
            for item in observations.values()
            if item.evaluation_status == "assessed"
            and item.clinical_status in {"present", "absent"}
        ]
        ids = self.repository.case_candidate_ids(pairs, self._aggregatable)
        return CandidateSet(
            strategy_id=self.descriptor.strategy_id,
            candidate_ids=ids,
            generation_details={"rule": "source_scoped_assessed_case_match", "phase": self.phase},
        )

    def _project(
        self, case: ClinicalCaseV2
    ) -> tuple[dict[str, ResolvedObservation], CoverageAssessment, set[str]]:
        observations, coverage, mappings = super()._project(case)
        supported = self.repository.supported_findings(list(observations))
        unsupported_inputs = {
            item.observation_id for key, item in observations.items() if key not in supported
        }
        observations = {key: item for key, item in observations.items() if key in supported}
        coverage = coverage.model_copy(
            update={
                "supported_observation_count": len(observations),
                "supported_present_count": sum(
                    item.clinical_status == "present" and item.evaluation_status == "assessed"
                    for item in observations.values()
                ),
                "coverage_ratio": len(observations) / coverage.confirmed_observation_count
                if coverage.confirmed_observation_count
                else 0.0,
                "inputs": [
                    item.model_copy(
                        update={"disposition": "ignored", "reason": "outside_explicit_source_scope"}
                    )
                    if item.input_id in unsupported_inputs
                    else item
                    for item in coverage.inputs
                ],
            }
        )
        if self.phase == "general":
            # The source models manifestations as has_symptom. Patient coding/kind is unchanged.
            observations = {
                key: replace(item, relation="has_symptom") for key, item in observations.items()
            }
        return observations, coverage, mappings

    def _contribution_lazy(
        self,
        candidate_id: str,
        assertion: ScoringAssertion,
        family_id: str,
        source_ids: list[str],
        observation: ResolvedObservation | None,
        rows: CandidateRows,
    ) -> ContributionV2:
        contribution = super()._contribution_lazy(
            candidate_id, assertion, family_id, source_ids, observation, rows
        )
        if self.phase == "general":
            # Numeric eligibility in this NEW profile is not dependency independence.
            contribution.details.update(
                {
                    "aggregatable": False,
                    "single_source_numeric_eligible": family_id in self._aggregatable,
                    "dependency_type": "unknown",
                    "clinical_source_count": 1,
                    "g4_status": "retained_not_clinically_approved",
                }
            )
        return contribution

    def _receipt(
        self,
        case: ClinicalCaseV2,
        operation: Literal["diagnose", "question"],
        sources: set[str],
        families: set[str],
        mappings: set[str],
        ignored: list[Any],
    ) -> RunReceipt:
        receipt = super()._receipt(case, operation, sources, families, mappings, ignored)
        payload = receipt.model_dump(mode="json", exclude={"receipt_id"})
        payload["transformations_applied"] = [
            "clinical_case_v2_concept_resolution",
            "explicit_versioned_source_scope",
            "canonical_assertion_polarity_comparison",
            "manifestation_role_projection_has_symptom"
            if self.phase == "general"
            else "original_observation_relation",
            "single_editorial_source_not_independent_proofs"
            if self.phase == "general"
            else "independent_evidence_family_aggregation",
        ]
        payload["warnings"].append(
            "EXPERIMENTAL SINGLE SOURCE: unknown editorial dependency remains unknown; "
            "G4 retained is not approved; no prevalence or clinical validation"
            if self.phase == "general"
            else "OPTIONAL RARE-ORIENTED SOURCE EXPLORATION"
        )
        payload["receipt_id"] = stable_id(
            "run_receipt", hashlib.sha256(encoded(payload)).hexdigest()
        )
        return RunReceipt.model_validate(payload)

    def question(self, case: ClinicalCaseV2) -> QuestionResultV2:
        observations, coverage, mappings = self._project(case)
        excluded = set(observations)
        for answer in case.question_history:
            resolved, _ = self._resolve_observation(
                answer.concept.concept_id, answer.concept.coding.system, answer.concept.coding.code
            )
            if resolved:
                excluded.add(resolved)
        prefix = f"{self.descriptor.strategy_id}:"
        answered = sum(item.question_id.startswith(prefix) for item in case.question_history)
        budget = int(self.profile.parameters["maximum_questions"])
        reason: str | None = self._population_reason(case)
        if reason is None and answered >= budget:
            reason = "question_budget_reached"
        candidates = self.generate(case).candidate_ids
        best = None
        if reason is None:
            if self.phase == "general":
                best = self.repository.general_question(candidates, excluded)
            else:
                best = self.repository.rare_question(candidates, excluded)
            if best is None:
                reason = "insufficient_question_evidence"
        receipt = self._receipt(case, "question", set(), set(), mappings, [])
        if reason is not None:
            return QuestionResultV2(
                case_id=case.case_id,
                status="stopped",
                question=None,
                scope_status="partial",
                stop_reason=reason,
                research_unreviewed=self._research_unreviewed,
                run_receipt=receipt,
            )
        assert best is not None
        concept_id, variation, documented = best
        system, code = self._question_coding(concept_id)
        label = self._question_label(concept_id)
        assertions, families, releases = self.repository.question_provenance(concept_id)
        receipt = self._receipt(case, "question", set(releases), set(families), mappings, [])
        question = AdaptiveQuestionV2(
            question_id=prefix + stable_id("question", case.case_id, concept_id).split(":")[-1],
            text=f"Is {label} present?",
            concept=QuestionConcept(system=system, code=code, label=label, label_language="en"),
            allowed_answers=["present", "absent", "unknown", "unable_to_assess"],
            justification=(
                "Variation in G4-retained MedlinePlus documentation among case-matched topics; "
                "undocumented does not mean absent; not a validated clinical discriminant"
                if self.phase == "general"
                else "Opposing explicit polarities in rare-oriented sources"
            ),
            expected_contribution={
                "measure": "documentation_variation"
                if self.phase == "general"
                else "polarity_separation",
                "value": variation,
                "not_a_clinical_probability": True,
                "phase": self.phase,
                "answered_in_phase": answered,
                "maximum_questions": budget,
                "remaining_budget": budget - answered - 1,
            },
            coverage=min(1.0, documented / max(1, len(candidates)))
            if self.phase == "general"
            else documented / max(1, len(self.repository.all_candidate_ids())),
            assertion_ids=assertions,
            source_release_ids=releases,
            evidence_family_ids=families,
        )
        return QuestionResultV2(
            case_id=case.case_id,
            status="question",
            scope_status="partial",
            question=question,
            research_unreviewed=self._research_unreviewed,
            run_receipt=receipt,
        )
