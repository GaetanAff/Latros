"""Deterministic general reasoning over canonical-v2 assertion families."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from latros import __version__
from latros.clinical.v2 import ClinicalCaseV2, QuantityValue, RangeValue
from latros.common import LatrosError, encoded, sha256, stable_id
from latros.knowledge.models_v2 import (
    CanonicalAssertion,
    CanonicalKnowledgeV2,
    ConceptObject,
    EvidenceFamily,
    SourceAssertion,
    aggregatable_evidence_family_ids,
)
from latros.knowledge.store_v2 import read_knowledge_v2
from latros.reasoning.interfaces import (
    CandidateAssessment,
    CandidateSet,
    ExplanationDocument,
    QuestionSelection,
    ReasoningStrategyDescriptor,
)
from latros.reasoning.profiles import ReasoningProfile
from latros.reasoning.results_v2 import (
    Abstention,
    AdaptiveQuestionV2,
    ContributionV2,
    CoverageAssessment,
    DiagnosticCandidateV2,
    DifferentialResultV2,
    InputDisposition,
    QuestionConcept,
    QuestionResultV2,
    RunReceipt,
    ScoreAggregate,
    SourceContributionView,
)

GENERAL_V1_DESCRIPTOR = ReasoningStrategyDescriptor(
    strategy_id="general_v1",
    strategy_version="1",
    accepted_case_versions=[2],
    accepted_observation_types=["symptom", "sign", "exam", "vital"],
    accepted_relations=["has_symptom", "has_sign", "has_exam_finding"],
    score_scale_id="general_v1.compatibility",
    score_kind="compatibility",
    candidate_generation="Active condition subjects with canonical assertions in snapshot scope",
    question_strategy="Explicit opposing assertion polarity only",
    explanation_strategy="Canonical assertions grouped by independent evidence family",
)

OBSERVATION_RELATIONS = {
    "symptom": "has_symptom",
    "sign": "has_sign",
    "exam": "has_exam_finding",
    "vital": "has_sign",
}


@dataclass(frozen=True)
class ResolvedObservation:
    observation_id: str
    concept_id: str
    clinical_status: Literal["present", "absent", "unknown"]
    evaluation_status: Literal["assessed", "not_assessed", "unable_to_assess"]
    kind: str
    relation: str
    mapping_id: str | None


@dataclass
class ComputedCandidate:
    candidate_id: str
    label: str
    score: float
    evaluated_count: int
    favorable: list[ContributionV2]
    unfavorable: list[ContributionV2]
    unknown: list[ContributionV2]
    source_views: list[SourceContributionView]
    mappings: list[str]


class GeneralV1Strategy:
    descriptor = GENERAL_V1_DESCRIPTOR

    def __init__(self, root: Path, snapshot: str, profile: ReasoningProfile) -> None:
        self.root = root
        self.snapshot = snapshot
        self.profile = profile
        self.manifest, self.knowledge = read_knowledge_v2(root, snapshot)
        self._check_profile()
        self._concepts = {item.concept_id: item for item in self.knowledge.concepts}
        self._labels = _labels(self.knowledge)
        self._assertions_by_candidate: dict[str, list[CanonicalAssertion]] = {}
        for assertion in self.knowledge.canonical_assertions:
            self._assertions_by_candidate.setdefault(assertion.subject_concept_id, []).append(
                assertion
            )
        self._source_assertions = {
            item.source_assertion_id: item for item in self.knowledge.source_assertions
        }
        self._records = {item.source_record_id: item for item in self.knowledge.source_records}
        self._derivations: dict[str, list[str]] = {}
        for item in self.knowledge.assertion_derivations:
            self._derivations.setdefault(item.canonical_assertion_id, []).append(
                item.source_assertion_id
            )
        self._families = {
            item.evidence_family_id: item for item in self.knowledge.evidence_families
        }
        self._families_by_source_assertion: dict[str, list[str]] = {}
        for family in self.knowledge.evidence_families:
            for assertion_id in family.source_assertion_ids:
                self._families_by_source_assertion.setdefault(assertion_id, []).append(
                    family.evidence_family_id
                )
        self._aggregatable = aggregatable_evidence_family_ids(self.knowledge)

    def generate(self, case: ClinicalCaseV2) -> CandidateSet:
        del case
        candidate_ids = sorted(
            candidate_id
            for candidate_id in self._assertions_by_candidate
            if self._concepts[candidate_id].kind == "condition"
            and self._concepts[candidate_id].status == "active"
        )
        return CandidateSet(
            strategy_id=self.descriptor.strategy_id,
            candidate_ids=candidate_ids,
            generation_details={
                "rule": "active_condition_subjects_with_assertions",
                "candidate_count": len(candidate_ids),
            },
        )

    def score(self, case: ClinicalCaseV2, candidates: CandidateSet) -> list[CandidateAssessment]:
        if candidates.strategy_id != self.descriptor.strategy_id:
            raise LatrosError("Candidate set belongs to another strategy")
        observations, _, _ = self._project(case)
        computed = self._compute(candidates.candidate_ids, observations)
        return [
            CandidateAssessment(
                candidate_id=item.candidate_id,
                rank=rank,
                score=item.score,
                scale_id=self.descriptor.score_scale_id,
                details={"evaluated_count": item.evaluated_count},
            )
            for rank, item in enumerate(computed, 1)
        ]

    def next(self, case: ClinicalCaseV2) -> QuestionSelection:
        result = self.question(case)
        return QuestionSelection(
            strategy_id=self.descriptor.strategy_id,
            payload=result.model_dump(mode="json"),
        )

    def build(
        self, case: ClinicalCaseV2, assessments: list[CandidateAssessment]
    ) -> ExplanationDocument:
        del assessments
        return ExplanationDocument(
            strategy_id=self.descriptor.strategy_id,
            payload=self.diagnose(case).model_dump(mode="json"),
        )

    def diagnose(self, case: ClinicalCaseV2) -> DifferentialResultV2:
        observations, coverage, mappings = self._project(case)
        population_reason = self._population_reason(case)
        minimum_findings = int(self.profile.parameters["minimum_assessed_findings"])
        minimum_coverage = float(self.profile.parameters["minimum_coverage_ratio"])
        assessed = sum(
            item.evaluation_status == "assessed" and item.clinical_status in {"present", "absent"}
            for item in observations.values()
        )
        reason: (
            Literal[
                "no_supported_present_observation",
                "insufficient_snapshot_coverage",
                "insufficient_supported_findings",
                "insufficient_case_coverage",
                "outside_snapshot_population",
                "missing_required_context",
            ]
            | None
        ) = population_reason
        explanation = ""
        if reason == "outside_snapshot_population":
            explanation = "The case is outside the adult population declared by this snapshot"
        elif reason == "missing_required_context":
            explanation = "An unambiguous age in UCUM years is required for this adult snapshot"
        elif not observations:
            reason = "no_supported_present_observation"
            explanation = "No confirmed observation is supported and resolved by general_v1"
        elif coverage.coverage_ratio < minimum_coverage:
            reason = "insufficient_case_coverage"
            explanation = "Supported observations are below the versioned case coverage threshold"
        elif assessed < minimum_findings:
            reason = "insufficient_supported_findings"
            explanation = "Too few supported observations are assessed for deterministic ranking"
        candidate_set = self.generate(case)
        computed = (
            [] if reason is not None else self._compute(candidate_set.candidate_ids, observations)
        )
        if reason is None and not computed:
            reason = "insufficient_snapshot_coverage"
            explanation = "No candidate has aggregatable assessed evidence in this snapshot"
        candidates = [self._result_candidate(item, rank) for rank, item in enumerate(computed, 1)]
        used_sources = {
            view.source_release_id for candidate in candidates for view in candidate.source_views
        }
        used_families = {
            family_id
            for candidate in candidates
            for view in candidate.source_views
            for family_id in view.evidence_family_ids
        }
        receipt = self._receipt(
            case,
            "diagnose",
            used_sources,
            used_families,
            mappings,
            [item for item in coverage.inputs if item.disposition != "used"],
        )
        if reason is not None:
            return DifferentialResultV2(
                case_id=case.case_id,
                status="abstained",
                scope_status=(
                    "out_of_scope"
                    if reason in {"outside_snapshot_population", "missing_required_context"}
                    else "partial"
                ),
                coverage=coverage,
                candidates=[],
                abstention=Abstention(reason=reason, explanation=explanation),
                research_unreviewed=self._research_unreviewed,
                run_receipt=receipt,
            )
        return DifferentialResultV2(
            case_id=case.case_id,
            status="ranked",
            scope_status="in_scope" if coverage.coverage_ratio == 1 else "partial",
            coverage=coverage,
            candidates=candidates,
            research_unreviewed=self._research_unreviewed,
            run_receipt=receipt,
        )

    def question(self, case: ClinicalCaseV2) -> QuestionResultV2:
        observations, coverage, mappings = self._project(case)
        population_reason = self._population_reason(case)
        if population_reason is not None:
            receipt = self._receipt(
                case,
                "question",
                set(),
                set(),
                mappings,
                [item for item in coverage.inputs if item.disposition != "used"],
            )
            return QuestionResultV2(
                case_id=case.case_id,
                status="stopped",
                scope_status="out_of_scope",
                question=None,
                stop_reason=population_reason,
                research_unreviewed=self._research_unreviewed,
                run_receipt=receipt,
            )
        selected = self._select_question(set(observations))
        if selected is None:
            receipt = self._receipt(
                case,
                "question",
                set(),
                set(),
                mappings,
                [item for item in coverage.inputs if item.disposition != "used"],
            )
            return QuestionResultV2(
                case_id=case.case_id,
                status="stopped",
                scope_status="partial" if coverage.coverage_ratio < 1 else "in_scope",
                question=None,
                stop_reason="insufficient_question_evidence",
                research_unreviewed=self._research_unreviewed,
                run_receipt=receipt,
            )
        concept_id, assertion_ids, family_ids, source_ids, separation, candidate_coverage = selected
        label = self._labels.get(concept_id, concept_id)
        question = AdaptiveQuestionV2(
            question_id=stable_id("question", case.case_id, concept_id, "general_v1"),
            text=f"Is {label} present?",
            concept=QuestionConcept(
                system=_concept_system(self.knowledge, concept_id),
                code=_concept_code(self.knowledge, concept_id),
                label=label,
                label_language="en",
            ),
            allowed_answers=["present", "absent", "unknown", "unable_to_assess"],
            justification="Explicit opposing assertion polarities separate snapshot candidates",
            expected_contribution={
                "measure": "explicit_polarity_separation",
                "value": separation,
                "not_a_clinical_probability": True,
            },
            coverage=candidate_coverage,
            assertion_ids=assertion_ids,
            source_release_ids=source_ids,
            evidence_family_ids=family_ids,
        )
        receipt = self._receipt(
            case,
            "question",
            set(source_ids),
            set(family_ids),
            mappings,
            [item for item in coverage.inputs if item.disposition != "used"],
        )
        return QuestionResultV2(
            case_id=case.case_id,
            status="question",
            scope_status="partial" if coverage.coverage_ratio < 1 else "in_scope",
            question=question,
            research_unreviewed=self._research_unreviewed,
            run_receipt=receipt,
        )

    def _project(
        self, case: ClinicalCaseV2
    ) -> tuple[dict[str, ResolvedObservation], CoverageAssessment, set[str]]:
        superseded = {item.supersedes for item in case.observations if item.supersedes is not None}
        active = [item for item in case.observations if item.observation_id not in superseded]
        resolved: dict[str, ResolvedObservation] = {}
        inputs: list[InputDisposition] = []
        mappings: set[str] = set()
        supported_present = 0
        for observation in active:
            relation = OBSERVATION_RELATIONS.get(observation.kind)
            concept_id, mapping_id = self._resolve_observation(
                observation.concept.concept_id,
                observation.concept.coding.system,
                observation.concept.coding.code,
            )
            if relation is None:
                inputs.append(
                    InputDisposition(
                        input_id=observation.observation_id,
                        input_kind=observation.kind,
                        disposition="ignored",
                        reason="unsupported_observation_type",
                    )
                )
                continue
            if concept_id is None:
                inputs.append(
                    InputDisposition(
                        input_id=observation.observation_id,
                        input_kind=observation.kind,
                        disposition="ignored",
                        reason="unsupported_or_unresolved_terminology",
                    )
                )
                continue
            if concept_id in resolved:
                raise LatrosError("general_v1 refuses multiple active observations for one concept")
            resolved[concept_id] = ResolvedObservation(
                observation_id=observation.observation_id,
                concept_id=concept_id,
                clinical_status=observation.clinical_status,
                evaluation_status=observation.evaluation_status,
                kind=observation.kind,
                relation=relation,
                mapping_id=mapping_id,
            )
            if mapping_id is not None:
                mappings.add(mapping_id)
            if (
                observation.clinical_status == "present"
                and observation.evaluation_status == "assessed"
            ):
                supported_present += 1
            inputs.append(
                InputDisposition(
                    input_id=observation.observation_id,
                    input_kind=observation.kind,
                    disposition="used",
                    reason=(
                        "supported_concept; quantitative_value_not_used"
                        if observation.kind == "vital" and observation.value is not None
                        else "supported_by_general_v1"
                    ),
                )
            )
        inputs.extend(
            InputDisposition(
                input_id=proposal.proposal_id,
                input_kind="observation_proposal",
                disposition="ignored",
                reason="not_confirmed_not_used_for_reasoning",
            )
            for proposal in case.observation_proposals
        )
        ratio = len(resolved) / len(active) if active else 0.0
        coverage = CoverageAssessment(
            confirmed_observation_count=len(active),
            supported_observation_count=len(resolved),
            supported_present_count=supported_present,
            proposal_count=len(case.observation_proposals),
            coverage_ratio=ratio,
            inputs=sorted(inputs, key=lambda item: item.input_id),
        )
        return resolved, coverage, mappings

    def _resolve_observation(
        self, concept_id: str, system: str, code: str
    ) -> tuple[str | None, str | None]:
        if concept_id in self._concepts and self._concepts[concept_id].status == "active":
            return concept_id, None
        for identifier in self.knowledge.external_identifiers:
            if (
                identifier.system == system
                and identifier.code == code
                and self._concepts[identifier.concept_id].status == "active"
            ):
                return identifier.concept_id, None
        allowed = [
            mapping
            for mapping in self.knowledge.concept_mappings
            if mapping.target_system == system
            and mapping.target_code == code
            and mapping.relation in {"exact", "equivalent"}
            and mapping.resolution_status == "resolved"
            and mapping.target_concept_id is not None
        ]
        if len(allowed) == 1:
            return allowed[0].target_concept_id, allowed[0].mapping_id
        return None, None

    def _compute(
        self, candidate_ids: list[str], observations: dict[str, ResolvedObservation]
    ) -> list[ComputedCandidate]:
        result: list[ComputedCandidate] = []
        for candidate_id in candidate_ids:
            contributions: list[ContributionV2] = []
            family_values: dict[str, list[float]] = {}
            mappings = sorted(
                {
                    observation.mapping_id
                    for observation in observations.values()
                    if observation.mapping_id is not None
                }
            )
            for assertion in self._assertions_by_candidate[candidate_id]:
                if not isinstance(assertion.object, ConceptObject):
                    continue
                source_ids = sorted(self._derivations.get(assertion.canonical_assertion_id, []))
                family_ids = sorted(
                    {
                        family_id
                        for source_id in source_ids
                        for family_id in self._families_by_source_assertion.get(source_id, [])
                    }
                )
                for family_id in family_ids:
                    family = self._families[family_id]
                    family_source_ids = [
                        source_id
                        for source_id in source_ids
                        if source_id in family.source_assertion_ids
                    ]
                    contribution = self._contribution(
                        candidate_id,
                        assertion,
                        family,
                        family_source_ids,
                        observations.get(assertion.object.concept_id),
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
                    label=self._labels.get(candidate_id, candidate_id),
                    score=weighted,
                    evaluated_count=sum(
                        contribution.value is not None
                        and contribution.evidence_family_id in self._aggregatable
                        for contribution in contributions
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

    def _contribution(
        self,
        candidate_id: str,
        assertion: CanonicalAssertion,
        family: EvidenceFamily,
        source_ids: list[str],
        observation: ResolvedObservation | None,
    ) -> ContributionV2:
        if not isinstance(assertion.object, ConceptObject):
            raise LatrosError("general_v1 contributions require a concept assertion object")
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
        provenance = [self._provenance(source_id) for source_id in source_ids]
        source_releases = sorted(
            {self._source_assertions[source_id].source_release_id for source_id in source_ids}
        )
        return ContributionV2(
            contribution_id=stable_id(
                "reasoning_contribution",
                candidate_id,
                assertion.canonical_assertion_id,
                family.evidence_family_id,
            ),
            direction=direction,
            observation=observation.observation_id if observation else "not_observed",
            finding=finding_concept_id,
            value=value,
            scale_id=self.descriptor.score_scale_id,
            reason=reason,
            source_release_id=source_releases[0],
            assertion_ids=source_ids,
            evidence_family_id=family.evidence_family_id,
            provenance=provenance,
            details={
                "canonical_assertion_id": assertion.canonical_assertion_id,
                "relation": assertion.relation,
                "assertion_polarity": assertion.qualifiers.polarity,
                "aggregatable": family.evidence_family_id in self._aggregatable,
                "all_source_release_ids": source_releases,
            },
        )

    def _provenance(self, source_assertion_id: str) -> dict[str, Any]:
        assertion: SourceAssertion = self._source_assertions[source_assertion_id]
        record = self._records[assertion.source_record_id]
        return {
            "source_assertion_id": source_assertion_id,
            "source_release_id": assertion.source_release_id,
            "source_record_id": assertion.source_record_id,
            "record_locator": record.record_locator,
            "artifact_ids": assertion.artifact_ids,
        }

    def _aggregate_families(self, family_scores: dict[str, float]) -> float | None:
        configured = self.profile.parameters.get("family_weights", {})
        if not isinstance(configured, dict):
            raise LatrosError("general_v1 family_weights must be an object")
        allow_unlisted = bool(
            self.profile.parameters.get("allow_unlisted_evidence_families", False)
        )
        weighted: list[tuple[float, float]] = []
        for family_id, score in family_scores.items():
            if family_id not in configured and not allow_unlisted:
                continue
            weight = float(configured.get(family_id, 1.0))
            if weight <= 0:
                raise LatrosError("general_v1 evidence family weights must be positive")
            weighted.append((score, weight))
        if not weighted:
            return None
        return sum(score * weight for score, weight in weighted) / sum(
            weight for _, weight in weighted
        )

    def _result_candidate(self, item: ComputedCandidate, rank: int) -> DiagnosticCandidateV2:
        return DiagnosticCandidateV2(
            candidate_id=item.candidate_id,
            label=item.label,
            rank=rank,
            aggregate=ScoreAggregate(
                value=item.score,
                scale_id=self.descriptor.score_scale_id,
                kind="compatibility",
                calibrated=False,
            ),
            favorable=item.favorable,
            unfavorable=item.unfavorable,
            unknown=item.unknown,
            source_views=item.source_views,
            terminology_mappings=item.mappings,
            frequency_conflicts=[],
        )

    def _select_question(
        self, observed_concepts: set[str]
    ) -> tuple[str, list[str], list[str], list[str], int, float] | None:
        candidates = self.generate(ClinicalCaseV2(case_id="question-selection")).candidate_ids
        by_concept: dict[str, dict[str, list[CanonicalAssertion]]] = {}
        for candidate_id in candidates:
            for assertion in self._assertions_by_candidate[candidate_id]:
                if isinstance(assertion.object, ConceptObject):
                    by_concept.setdefault(assertion.object.concept_id, {}).setdefault(
                        candidate_id, []
                    ).append(assertion)
        options = []
        for concept_id, assertions_by_candidate in by_concept.items():
            if concept_id in observed_concepts:
                continue
            positive = {
                candidate_id
                for candidate_id, assertions in assertions_by_candidate.items()
                if any(item.qualifiers.polarity == "present" for item in assertions)
            }
            excluded = {
                candidate_id
                for candidate_id, assertions in assertions_by_candidate.items()
                if any(item.qualifiers.polarity == "excluded" for item in assertions)
            }
            if not positive or not excluded:
                continue
            separation = min(len(positive), len(excluded))
            canonical_ids = {
                item.canonical_assertion_id
                for assertions in assertions_by_candidate.values()
                for item in assertions
            }
            source_assertion_ids = sorted(
                {
                    source_id
                    for canonical_id in canonical_ids
                    for source_id in self._derivations.get(canonical_id, [])
                }
            )
            family_ids = sorted(
                {
                    family_id
                    for source_id in source_assertion_ids
                    for family_id in self._families_by_source_assertion.get(source_id, [])
                }
            )
            source_ids = sorted(
                {self._source_assertions[item].source_release_id for item in source_assertion_ids}
            )
            options.append(
                (
                    -separation,
                    -len(assertions_by_candidate),
                    concept_id,
                    source_assertion_ids,
                    family_ids,
                    source_ids,
                    separation,
                    len(assertions_by_candidate) / len(candidates),
                )
            )
        if not options:
            return None
        selected = sorted(options)[0]
        return selected[2], selected[3], selected[4], selected[5], selected[6], selected[7]

    def _population_reason(
        self, case: ClinicalCaseV2
    ) -> Literal["outside_snapshot_population", "missing_required_context"] | None:
        age = case.subject_context.age
        minimum = float(self.profile.parameters["minimum_age_years"])
        if isinstance(age, QuantityValue):
            if age.system != "http://unitsofmeasure.org" or age.code != "a":
                return "missing_required_context"
            if age.comparator == "eq":
                return "outside_snapshot_population" if age.value < minimum else None
            if age.comparator in {"ge", "gt"} and age.value >= minimum:
                return None
            if age.comparator in {"lt", "le"} and age.value <= minimum:
                return "outside_snapshot_population"
            return "missing_required_context"
        if isinstance(age, RangeValue):
            if (
                age.low.system != "http://unitsofmeasure.org"
                or age.low.code != "a"
                or age.high.system != "http://unitsofmeasure.org"
                or age.high.code != "a"
            ):
                return "missing_required_context"
            if age.high.value < minimum:
                return "outside_snapshot_population"
            if age.low.value >= minimum:
                return None
        return "missing_required_context"

    def _receipt(
        self,
        case: ClinicalCaseV2,
        operation: Literal["diagnose", "question"],
        sources: set[str],
        families: set[str],
        mappings: set[str],
        ignored: list[InputDisposition],
    ) -> RunReceipt:
        manifest_path = self.root / "manifests" / f"{self.snapshot}.json"
        input_sha256 = hashlib.sha256(encoded(case.model_dump(mode="json"))).hexdigest()
        source_releases = sorted(sources)
        evidence_families = sorted(families)
        applied_mappings = sorted(mappings)
        transformations = [
            "clinical_case_v2_concept_resolution",
            "canonical_assertion_polarity_comparison",
            "independent_evidence_family_aggregation",
        ]
        warnings = ["Some inputs were not used by general_v1"] if ignored else []
        if self._research_unreviewed:
            warnings.append(
                "UNREVIEWED LOCAL RESEARCH DATA: not clinically validated, not publishable, "
                "and not suitable for clinical use"
            )
        receipt_payload = {
            "operation": operation,
            "clinical_contract": "clinical_case_v2",
            "input_sha256": input_sha256,
            "snapshot_id": self.snapshot,
            "snapshot_schema_version": self.manifest.schema_version,
            "snapshot_manifest_sha256": sha256(manifest_path),
            "snapshot_content_sha256": self.manifest.content_sha256,
            "strategy_id": self.descriptor.strategy_id,
            "strategy_version": self.descriptor.strategy_version,
            "profile_id": self.profile.profile_id,
            "profile_sha256": self.profile.profile_sha256,
            "effective_parameters": self.profile.parameters,
            "source_releases_used": source_releases,
            "evidence_family_ids_used": evidence_families,
            "mappings_applied": applied_mappings,
            "transformations_applied": transformations,
            "software_version": __version__,
            "warnings": warnings,
            "ignored_inputs": [item.model_dump(mode="json") for item in ignored],
            "research_unreviewed": self._research_unreviewed,
            "knowledge_validation_status": self.manifest.validation_status,
            "intended_use": self.manifest.intended_use,
            "unreviewed_assertion_count": len(self.manifest.unreviewed_assertion_ids),
            "unreviewed_mapping_count": len(self.manifest.unreviewed_mapping_ids),
            "research_override_used": self.manifest.research_override_used,
        }
        return RunReceipt(
            receipt_id=stable_id(
                "run_receipt", hashlib.sha256(encoded(receipt_payload)).hexdigest()
            ),
            operation=operation,
            clinical_contract="clinical_case_v2",
            input_sha256=input_sha256,
            snapshot_id=self.snapshot,
            snapshot_schema_version=self.manifest.schema_version,
            snapshot_manifest_sha256=sha256(manifest_path),
            snapshot_content_sha256=self.manifest.content_sha256,
            strategy_id=self.descriptor.strategy_id,
            strategy_version=self.descriptor.strategy_version,
            profile_id=self.profile.profile_id,
            profile_sha256=self.profile.profile_sha256,
            effective_parameters=self.profile.parameters,
            source_releases_used=source_releases,
            evidence_family_ids_used=evidence_families,
            mappings_applied=applied_mappings,
            transformations_applied=transformations,
            software_version=__version__,
            warnings=warnings,
            ignored_inputs=ignored,
            research_unreviewed=self._research_unreviewed,
            knowledge_validation_status=self.manifest.validation_status,
            intended_use=self.manifest.intended_use,
            unreviewed_assertion_count=len(self.manifest.unreviewed_assertion_ids),
            unreviewed_mapping_count=len(self.manifest.unreviewed_mapping_ids),
            research_override_used=self.manifest.research_override_used,
        )

    @property
    def _research_unreviewed(self) -> bool:
        return (
            self.manifest.validation_status == "unreviewed"
            and self.manifest.intended_use == "local_research_only"
            and self.manifest.clinical_validation is False
            and self.manifest.human_review_complete is False
            and self.manifest.publishable is False
            and self.manifest.research_override_used
        )

    def _check_profile(self) -> None:
        if self.profile.strategy_id != self.descriptor.strategy_id:
            raise LatrosError("Reasoning profile strategy mismatch")
        if self.profile.strategy_version != self.descriptor.strategy_version:
            raise LatrosError("Reasoning profile strategy version mismatch")
        if self.profile.score_scale.scale_id != self.descriptor.score_scale_id:
            raise LatrosError("Reasoning profile score scale mismatch")
        if self.profile.score_scale.kind != self.descriptor.score_kind:
            raise LatrosError("Reasoning profile score kind mismatch")
        if self.profile.score_scale.calibrated:
            raise LatrosError("general_v1 does not accept a calibrated score profile")
        if not self.profile.accepts_snapshot(self.snapshot, self.manifest.schema_version):
            raise LatrosError("Reasoning profile is incompatible with the knowledge snapshot")
        if self.profile.profile_id not in self.manifest.compatible_profiles:
            raise LatrosError("Snapshot does not declare this reasoning profile as compatible")


def _labels(knowledge: CanonicalKnowledgeV2) -> dict[str, str]:
    preferred = [
        item
        for item in knowledge.designations
        if item.scope in {"preferred", "fully_specified_name"}
    ]
    return {
        item.concept_id: item.text
        for item in sorted(preferred, key=lambda item: (item.concept_id, item.scope, item.language))
    }


def _source_views(contributions: list[ContributionV2]) -> list[SourceContributionView]:
    result = []
    sources = {
        source_id
        for item in contributions
        for source_id in item.details.get("all_source_release_ids", [item.source_release_id])
        if isinstance(source_id, str)
    }
    for source_id in sorted(sources):
        selected = [
            item
            for item in contributions
            if source_id in item.details.get("all_source_release_ids", [item.source_release_id])
        ]
        numeric = [item.value for item in selected if item.value is not None]
        result.append(
            SourceContributionView(
                source_release_id=source_id,
                evidence_family_ids=sorted({item.evidence_family_id for item in selected}),
                contribution_ids=[item.contribution_id for item in selected],
                subtotal=sum(numeric) / len(numeric) if numeric else 0.0,
                scale_id="general_v1.compatibility",
            )
        )
    return result


def _concept_system(knowledge: CanonicalKnowledgeV2, concept_id: str) -> str:
    identifiers = [item for item in knowledge.external_identifiers if item.concept_id == concept_id]
    if not identifiers:
        raise LatrosError(f"Concept {concept_id!r} has no external identifier")
    return sorted(identifiers, key=lambda item: (item.system, item.code))[0].system


def _concept_code(knowledge: CanonicalKnowledgeV2, concept_id: str) -> str:
    identifiers = [item for item in knowledge.external_identifiers if item.concept_id == concept_id]
    if not identifiers:
        raise LatrosError(f"Concept {concept_id!r} has no external identifier")
    return sorted(identifiers, key=lambda item: (item.system, item.code))[0].code
