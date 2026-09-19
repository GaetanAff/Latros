"""Inspectable v2 results and deterministic run receipts."""

import hashlib
from pathlib import Path
from typing import Any, Literal, Self

import orjson
from pydantic import Field, model_validator

from latros import __version__
from latros.clinical.loading import ClinicalCaseDocument
from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, encoded, sha256, stable_id
from latros.reasoning.profiles import ReasoningProfile
from latros.reasoning.semantic_v1_adapter import IgnoredClinicalInput, SemanticV1Adapter
from latros.sources.registry import Contract


class SafetyAssessment(Contract):
    status: Literal["not_evaluated"] = "not_evaluated"
    component: Literal["separate"] = "separate"


class InputDisposition(Contract):
    input_id: str = Field(min_length=1)
    input_kind: str = Field(min_length=1)
    disposition: Literal["used", "ignored", "refused"]
    reason: str = Field(min_length=1)


class CoverageAssessment(Contract):
    confirmed_observation_count: int = Field(ge=0)
    supported_observation_count: int = Field(ge=0)
    supported_present_count: int = Field(ge=0)
    proposal_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    inputs: list[InputDisposition]


class ContributionV2(Contract):
    contribution_id: str = Field(min_length=1)
    direction: Literal["favorable", "unfavorable", "unknown"]
    observation: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    value: float | None = None
    scale_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    assertion_ids: list[str] = Field(min_length=1)
    evidence_family_id: str = Field(min_length=1)
    provenance: list[dict[str, Any]]
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unknown_has_no_numeric_value(self) -> Self:
        if (self.direction == "unknown") != (self.value is None):
            raise ValueError("Only unknown contributions omit a numeric value")
        return self


class SourceContributionView(Contract):
    source_release_id: str = Field(min_length=1)
    evidence_family_ids: list[str]
    contribution_ids: list[str]
    subtotal: float
    scale_id: str = Field(min_length=1)


class ScoreAggregate(Contract):
    value: float
    scale_id: str = Field(min_length=1)
    kind: Literal["compatibility", "probability", "ordinal"]
    calibrated: bool

    @model_validator(mode="after")
    def no_uncalibrated_probability(self) -> Self:
        if self.kind == "probability" and not self.calibrated:
            raise ValueError("An uncalibrated score cannot be labelled as probability")
        return self


class DiagnosticCandidateV2(Contract):
    candidate_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    rank: int = Field(ge=1)
    aggregate: ScoreAggregate
    favorable: list[ContributionV2]
    unfavorable: list[ContributionV2]
    unknown: list[ContributionV2]
    source_views: list[SourceContributionView]
    terminology_mappings: list[str]
    frequency_conflicts: list[str]


class Abstention(Contract):
    reason: Literal[
        "no_supported_present_observation",
        "insufficient_snapshot_coverage",
        "insufficient_supported_findings",
        "insufficient_case_coverage",
        "outside_snapshot_population",
        "missing_required_context",
    ]
    explanation: str = Field(min_length=1)


class RunReceipt(Contract):
    receipt_id: str = Field(min_length=1)
    operation: Literal["diagnose", "question"]
    clinical_contract: Literal["clinical_case_v1", "clinical_case_v2"]
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1)
    snapshot_schema_version: int = Field(ge=1)
    snapshot_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_parameters: dict[str, Any]
    source_releases_used: list[str]
    evidence_family_ids_used: list[str]
    mappings_applied: list[str]
    transformations_applied: list[str]
    software_version: str = Field(min_length=1)
    warnings: list[str]
    ignored_inputs: list[InputDisposition]
    research_unreviewed: bool = False
    knowledge_validation_status: Literal["unreviewed"] | None = None
    intended_use: Literal["local_research_only"] | None = None
    unreviewed_assertion_count: int = Field(default=0, ge=0)
    unreviewed_mapping_count: int = Field(default=0, ge=0)
    research_override_used: bool = False

    @model_validator(mode="after")
    def unreviewed_receipt_is_explicit(self) -> Self:
        if self.research_unreviewed:
            if (
                self.knowledge_validation_status != "unreviewed"
                or self.intended_use != "local_research_only"
                or not self.research_override_used
                or self.unreviewed_assertion_count < 1
            ):
                raise ValueError("Unreviewed run receipt safeguards are incomplete")
        elif any(
            (
                self.knowledge_validation_status is not None,
                self.intended_use is not None,
                self.unreviewed_assertion_count,
                self.unreviewed_mapping_count,
                self.research_override_used,
            )
        ):
            raise ValueError("Reviewed receipt cannot contain unreviewed research markers")
        return self


class DifferentialResultV2(Contract):
    schema_version: Literal[2] = 2
    case_id: str = Field(min_length=1)
    status: Literal["ranked", "abstained"]
    scope_status: Literal["in_scope", "partial", "out_of_scope"]
    coverage: CoverageAssessment
    candidates: list[DiagnosticCandidateV2]
    abstention: Abstention | None = None
    safety: SafetyAssessment = Field(default_factory=SafetyAssessment)
    research_unreviewed: bool = False
    run_receipt: RunReceipt

    @model_validator(mode="after")
    def status_matches_result(self) -> Self:
        if self.status == "ranked" and (not self.candidates or self.abstention is not None):
            raise ValueError("A ranked result requires candidates and no abstention")
        if self.status == "abstained" and self.abstention is None:
            raise ValueError("An abstained result requires a reason")
        if self.research_unreviewed != self.run_receipt.research_unreviewed:
            raise ValueError("Result and run receipt research markers disagree")
        return self


class QuestionConcept(Contract):
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    label_language: str = Field(min_length=1)


class AdaptiveQuestionV2(Contract):
    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    concept: QuestionConcept
    allowed_answers: list[Literal["present", "absent", "unknown", "unable_to_assess"]] = Field(
        min_length=1
    )
    justification: str = Field(min_length=1)
    expected_contribution: dict[str, Any]
    coverage: float = Field(ge=0, le=1)
    assertion_ids: list[str]
    source_release_ids: list[str]
    evidence_family_ids: list[str]
    evaluation_difficulty: Literal["not_assessed"] = "not_assessed"


class QuestionResultV2(Contract):
    schema_version: Literal[2] = 2
    case_id: str = Field(min_length=1)
    status: Literal["question", "stopped"]
    scope_status: Literal["in_scope", "partial", "out_of_scope"]
    question: AdaptiveQuestionV2 | None
    stop_reason: str | None = None
    safety: SafetyAssessment = Field(default_factory=SafetyAssessment)
    research_unreviewed: bool = False
    run_receipt: RunReceipt

    @model_validator(mode="after")
    def question_matches_status(self) -> Self:
        if (self.status == "question") != (self.question is not None):
            raise ValueError("Question status and payload disagree")
        if self.status == "stopped" and self.stop_reason is None:
            raise ValueError("Stopped question selection requires a reason")
        if self.research_unreviewed != self.run_receipt.research_unreviewed:
            raise ValueError("Result and run receipt research markers disagree")
        return self


def build_differential_v2(
    root: Path,
    case: ClinicalCaseDocument,
    adapter: SemanticV1Adapter,
    profile: ReasoningProfile,
) -> DifferentialResultV2:
    _check_profile(adapter, profile)
    projection = adapter.project(case)
    legacy = adapter.engine.diagnose(projection.case)
    coverage, scope = _coverage(case, projection.ignored_inputs, projection.used_observation_ids)
    candidates = [_candidate(adapter, item) for item in legacy["differential"]]
    if candidates:
        status: Literal["ranked", "abstained"] = "ranked"
        abstention = None
    else:
        status = "abstained"
        abstention_reason: Literal[
            "no_supported_present_observation", "insufficient_snapshot_coverage"
        ]
        if coverage.supported_present_count == 0:
            abstention_reason = "no_supported_present_observation"
            explanation = "semantic_v1 requires at least one confirmed present HPO phenotype"
            scope = "out_of_scope"
        else:
            abstention_reason = "insufficient_snapshot_coverage"
            explanation = "No candidate in this snapshot covers the supported present findings"
            scope = "partial"
        abstention = Abstention(reason=abstention_reason, explanation=explanation)
    sources, families, mappings = _used_references(candidates)
    receipt = _receipt(
        root,
        case,
        adapter,
        profile,
        operation="diagnose",
        sources=sources,
        families=families,
        mappings=mappings,
        ignored=[item for item in coverage.inputs if item.disposition != "used"],
    )
    return DifferentialResultV2(
        case_id=case.case_id,
        status=status,
        scope_status=scope,
        coverage=coverage,
        candidates=candidates,
        abstention=abstention,
        run_receipt=receipt,
    )


def build_question_v2(
    root: Path,
    case: ClinicalCaseDocument,
    adapter: SemanticV1Adapter,
    profile: ReasoningProfile,
) -> QuestionResultV2:
    _check_profile(adapter, profile)
    projection = adapter.project(case)
    legacy = adapter.next(case).payload
    coverage, scope = _coverage(case, projection.ignored_inputs, projection.used_observation_ids)
    question_data = legacy.get("question")
    sources: set[str] = set()
    families: set[str] = set()
    question = None
    if isinstance(question_data, dict):
        assertion_ids = sorted(
            {
                assertion_id
                for evidence in question_data["evidence"]
                for assertion_id in evidence["assertion_ids"]
            }
        )
        for evidence in question_data["evidence"]:
            for provenance in evidence["provenance"]:
                sources.add(provenance["source_release"])
        families = {_legacy_family(source, assertion_ids) for source in sources}
        question = AdaptiveQuestionV2(
            question_id=stable_id(
                "question",
                case.case_id,
                question_data["concept_id"],
                str(legacy.get("question_number", 0)),
            ),
            text=question_data["text"],
            concept=QuestionConcept(
                system="http://purl.obolibrary.org/obo/hp.owl",
                code=question_data["concept_id"],
                label=question_data["label"],
                label_language=question_data["label_language"],
            ),
            allowed_answers=["present", "absent", "unknown", "unable_to_assess"],
            justification="Maximum deterministic information gain under question_v1",
            expected_contribution={
                "measure": "information_gain_bits",
                "value": question_data["information_gain_bits"],
                "weight_type": legacy["weight_type"],
                "not_a_clinical_probability": True,
            },
            coverage=question_data["coverage"],
            assertion_ids=assertion_ids,
            source_release_ids=sorted(sources),
            evidence_family_ids=sorted(families),
        )
    receipt = _receipt(
        root,
        case,
        adapter,
        profile,
        operation="question",
        sources=sources,
        families=families,
        mappings=set(),
        ignored=[item for item in coverage.inputs if item.disposition != "used"],
    )
    return QuestionResultV2(
        case_id=case.case_id,
        status="question" if question is not None else "stopped",
        scope_status=scope,
        question=question,
        stop_reason=None if question is not None else str(legacy.get("reason", "no_question")),
        run_receipt=receipt,
    )


def _candidate(adapter: SemanticV1Adapter, legacy: dict[str, Any]) -> DiagnosticCandidateV2:
    favorable = [
        _evidence_contribution(item, "favorable") for item in legacy["supporting_evidence"]
    ]
    unfavorable = [
        _evidence_contribution(item, "unfavorable") for item in legacy["contradicting_evidence"]
    ]
    assertion_lookup = {
        row["id"]: row for rows in adapter.engine.assertions.values() for row in rows
    }
    unknown = []
    for item in legacy["important_unknowns"]:
        assertion = assertion_lookup[item["assertion_id"]]
        provenance = orjson.loads(assertion["provenance_json"])
        source = assertion["source_release_id"]
        unknown.append(
            ContributionV2(
                contribution_id=stable_id(
                    "reasoning_contribution", legacy["disease"], item["assertion_id"], "unknown"
                ),
                direction="unknown",
                observation=item["concept_id"],
                finding=item["concept_id"],
                value=None,
                scale_id="semantic_v1.compatibility",
                reason="important_unknown",
                source_release_id=source,
                assertion_ids=[item["assertion_id"]],
                evidence_family_id=_legacy_family(source, [item["assertion_id"]]),
                provenance=provenance,
                details={"information_content": item["information_content"]},
            )
        )
    contributions = [*favorable, *unfavorable, *unknown]
    source_views = []
    for source in sorted({item.source_release_id for item in contributions}):
        selected = [item for item in contributions if item.source_release_id == source]
        source_views.append(
            SourceContributionView(
                source_release_id=source,
                evidence_family_ids=sorted({item.evidence_family_id for item in selected}),
                contribution_ids=[item.contribution_id for item in selected],
                subtotal=sum(item.value or 0.0 for item in selected),
                scale_id="semantic_v1.compatibility",
            )
        )
    return DiagnosticCandidateV2(
        candidate_id=legacy["disease"],
        label=legacy["label"],
        rank=legacy["rank"],
        aggregate=ScoreAggregate(
            value=legacy["score"],
            scale_id="semantic_v1.compatibility",
            kind="compatibility",
            calibrated=False,
        ),
        favorable=favorable,
        unfavorable=unfavorable,
        unknown=unknown,
        source_views=source_views,
        terminology_mappings=legacy["exact_mondo_mappings"],
        frequency_conflicts=legacy["frequency_conflicts"],
    )


def _evidence_contribution(
    evidence: dict[str, Any], direction: Literal["favorable", "unfavorable"]
) -> ContributionV2:
    source = evidence["source_release"]
    family = _legacy_family(source, evidence["assertion_ids"])
    return ContributionV2(
        contribution_id=stable_id(
            "reasoning_contribution",
            evidence["observation"],
            evidence["phenotype"],
            direction,
            *evidence["assertion_ids"],
        ),
        direction=direction,
        observation=evidence["observation"],
        finding=evidence["phenotype"],
        value=evidence["contribution"],
        scale_id="semantic_v1.compatibility",
        reason=evidence["reason"],
        source_release_id=source,
        assertion_ids=evidence["assertion_ids"],
        evidence_family_id=family,
        provenance=evidence["provenance"],
        details={
            "matched_ancestor": evidence["matched_ancestor"],
            "source_phenotype": evidence["source_phenotype"],
            "frequency": evidence["frequency"],
            "frequency_estimate": evidence["frequency_estimate"],
        },
    )


def _coverage(
    case: ClinicalCaseDocument,
    ignored: list[IgnoredClinicalInput],
    used_ids: list[str],
) -> tuple[CoverageAssessment, Literal["in_scope", "partial", "out_of_scope"]]:
    if isinstance(case, ClinicalCase):
        effective = case.effective_observations()
        used = [f"v1:{code}" for code in sorted(effective)]
        inputs = [
            InputDisposition(
                input_id=identifier,
                input_kind="phenotype",
                disposition="used",
                reason="supported_by_semantic_v1",
            )
            for identifier in used
        ]
        total = len(effective)
        present = sum(status == "present" for status in effective.values())
        proposals = 0
    else:
        superseded = {item.supersedes for item in case.observations if item.supersedes is not None}
        active = [item for item in case.observations if item.observation_id not in superseded]
        ignored_ids = {item.input_id for item in ignored}
        inputs = [
            InputDisposition(
                input_id=identifier,
                input_kind="phenotype",
                disposition="used",
                reason="supported_by_semantic_v1",
            )
            for identifier in used_ids
        ]
        inputs.extend(
            InputDisposition(
                input_id=item.input_id,
                input_kind=item.input_kind,
                disposition="ignored",
                reason=item.reason,
            )
            for item in ignored
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
        total = len(active)
        present = sum(
            item.clinical_status == "present" and item.observation_id not in ignored_ids
            for item in active
        )
        proposals = len(case.observation_proposals)
    supported = len(used_ids) if not isinstance(case, ClinicalCase) else total
    ratio = supported / total if total else 0.0
    if present == 0:
        scope: Literal["in_scope", "partial", "out_of_scope"] = "out_of_scope"
    elif ignored or supported < total:
        scope = "partial"
    else:
        scope = "in_scope"
    return (
        CoverageAssessment(
            confirmed_observation_count=total,
            supported_observation_count=supported,
            supported_present_count=present,
            proposal_count=proposals,
            coverage_ratio=ratio,
            inputs=sorted(inputs, key=lambda item: (item.input_id, item.disposition)),
        ),
        scope,
    )


def _receipt(
    root: Path,
    case: ClinicalCaseDocument,
    adapter: SemanticV1Adapter,
    profile: ReasoningProfile,
    *,
    operation: Literal["diagnose", "question"],
    sources: set[str],
    families: set[str],
    mappings: set[str],
    ignored: list[InputDisposition],
) -> RunReceipt:
    manifest_path = root / "manifests" / f"{adapter.engine.snapshot}.json"
    manifest = adapter.engine.manifest
    payload = {
        "operation": operation,
        "clinical_contract": (
            "clinical_case_v1" if isinstance(case, ClinicalCase) else "clinical_case_v2"
        ),
        "input_sha256": hashlib.sha256(
            encoded(case.model_dump(mode="json", exclude_none=False))
        ).hexdigest(),
        "snapshot_id": adapter.engine.snapshot,
        "snapshot_schema_version": manifest["schema_version"],
        "snapshot_manifest_sha256": sha256(manifest_path),
        "snapshot_content_sha256": manifest["content_sha256"],
        "strategy_id": adapter.descriptor.strategy_id,
        "strategy_version": adapter.descriptor.strategy_version,
        "profile_id": profile.profile_id,
        "profile_sha256": profile.profile_sha256,
        "effective_parameters": profile.parameters,
        "source_releases_used": sorted(sources),
        "evidence_family_ids_used": sorted(families),
        "mappings_applied": sorted(mappings),
        "transformations_applied": [
            "semantic_v1_hpo_resolution",
            *(["clinical_case_v2_to_semantic_v1"] if isinstance(case, ClinicalCaseV2) else []),
        ],
        "software_version": __version__,
        "warnings": (["Some inputs were not used by semantic_v1"] if ignored else []),
        "ignored_inputs": [item.model_dump(mode="json") for item in ignored],
    }
    receipt_id = stable_id("run_receipt", hashlib.sha256(encoded(payload)).hexdigest())
    return RunReceipt(receipt_id=receipt_id, **payload)


def _check_profile(adapter: SemanticV1Adapter, profile: ReasoningProfile) -> None:
    manifest = adapter.engine.manifest
    if profile.strategy_id != adapter.descriptor.strategy_id:
        raise LatrosError("Reasoning profile strategy mismatch")
    if not profile.accepts_snapshot(adapter.engine.snapshot, manifest["schema_version"]):
        raise LatrosError("Reasoning profile is incompatible with the knowledge snapshot")


def _used_references(
    candidates: list[DiagnosticCandidateV2],
) -> tuple[set[str], set[str], set[str]]:
    contributions = [
        contribution
        for candidate in candidates
        for contribution in [*candidate.favorable, *candidate.unfavorable, *candidate.unknown]
    ]
    return (
        {item.source_release_id for item in contributions},
        {item.evidence_family_id for item in contributions},
        {mapping for candidate in candidates for mapping in candidate.terminology_mappings},
    )


def _legacy_family(source_release: str, assertion_ids: list[str]) -> str:
    return stable_id("legacy_evidence_family", source_release, *sorted(assertion_ids))
