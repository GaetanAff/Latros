"""Reviewable clinical curation packages and their publication gate.

Draft assertions are intentionally separate from canonical snapshots.  A package
may be versioned while pending review, but it cannot be exported to the approved
JSONL importer until every legal, provenance, mapping and human-review gate is
satisfied.
"""

import hashlib
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self

import orjson
from pydantic import Field, field_validator, model_validator

from latros.common import LatrosError, encoded, sha256
from latros.knowledge.importers_v2 import (
    CuratedAssertionRecord,
    CuratedCode,
    CuratedEvidenceFamily,
    CurationReviewer,
)
from latros.knowledge.models_v2 import DependencyType, MappingRelation, RelationType
from latros.sources.registry import Contract

ReviewState = Literal["pending_review", "approved", "approved_with_change", "rejected"]
ReviewDecisionValue = Literal["approved", "approved_with_change", "rejected"]
ReviewItemType = Literal["assertion", "mapping"]


class CurationPackageManifest(Contract):
    schema_version: Literal[1] = 1
    package_id: str = Field(min_length=1)
    status: Literal["pending_clinical_review", "approved_for_snapshot"]
    domain: str = Field(min_length=1)
    population: str = Field(min_length=1)
    candidate_codes: list[CuratedCode] = Field(min_length=1)
    minimum_assertions_per_candidate: int = Field(default=2, ge=1)
    minimum_discriminating_per_candidate: int = Field(default=1, ge=1)
    source_artifacts_file: str = "sources.json"
    concepts_file: str = "concepts.jsonl"
    mappings_file: str = "mappings.jsonl"
    assertions_file: str = "assertions.jsonl"
    reviewers_file: str = "reviewers.jsonl"
    reviews_file: str = "reviews.jsonl"
    segment_representation_path: str
    segment_representation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exclusions: list[str] = Field(default_factory=list)

    @field_validator(
        "source_artifacts_file",
        "concepts_file",
        "mappings_file",
        "assertions_file",
        "reviewers_file",
        "reviews_file",
    )
    @classmethod
    def package_filename(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or len(path.parts) != 1 or value in {".", ".."}:
            raise ValueError("Curation package files must be direct relative filenames")
        return value

    @field_validator("segment_representation_path")
    @classmethod
    def local_segment_path(cls, value: str) -> str:
        _safe_local_path(value)
        return value


class SourceArtifactReceipt(Contract):
    artifact_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    role: Literal["terminology", "clinical_assertions", "license_evidence"]
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    release: str = Field(min_length=1)
    publication_date: date | None = None
    access_date: date
    local_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capture_kind: Literal["full_capture", "verified_segment_representation"]
    license_name: str = Field(min_length=1)
    license_url: str = Field(pattern=r"^https://")
    attribution: str = Field(min_length=1)
    redistribution: Literal["allowed_with_attribution", "local_only", "prohibited", "unknown"]
    legal_status: Literal["approved_for_structured_reuse", "requires_review", "prohibited"]
    evidence_family_id: str | None = Field(default=None, min_length=1)
    dependency_type: DependencyType | None = None
    upstream_reference: str | None = Field(default=None, min_length=1)
    aggregatable: bool = False
    notes: str = ""

    @field_validator("local_path")
    @classmethod
    def safe_local_path(cls, value: str) -> str:
        _safe_local_path(value)
        return value

    @model_validator(mode="after")
    def evidence_metadata_matches_role(self) -> Self:
        if self.role == "clinical_assertions":
            if (
                self.evidence_family_id is None
                or self.dependency_type is None
                or self.upstream_reference is None
            ):
                raise ValueError("Clinical artifacts require evidence dependency metadata")
            if self.dependency_type == "unknown" and self.aggregatable:
                raise ValueError("Unknown dependencies cannot be aggregatable")
        elif any(
            value is not None
            for value in (
                self.evidence_family_id,
                self.dependency_type,
                self.upstream_reference,
            )
        ):
            raise ValueError("Terminology and license artifacts are not evidence families")
        return self


class CurationConcept(Contract):
    concept: CuratedCode
    kind: Literal["condition", "symptom", "sign", "exam", "vital"]
    label: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2)
    definition_scope: str = Field(min_length=1)
    status: Literal["active"] = "active"


class CurationMapping(Contract):
    mapping_id: str = Field(min_length=1)
    source: CuratedCode
    target: CuratedCode
    direction: Literal["source_to_target", "bidirectional"]
    relation: MappingRelation
    resolution_status: Literal["resolved", "ambiguous", "unresolved"]
    source_artifact_id: str = Field(min_length=1)
    record_locator: str = Field(min_length=1)
    provenance_note: str = Field(min_length=1)
    confidence: Literal["high", "medium", "low", "not_assessed"]
    review_status: ReviewState = "pending_review"

    @model_validator(mode="after")
    def resolution_is_coherent(self) -> Self:
        if self.resolution_status == "resolved" and self.relation == "unresolved":
            raise ValueError("A resolved mapping needs a qualified relation")
        if self.resolution_status != "resolved" and self.relation in {"exact", "equivalent"}:
            raise ValueError("Unresolved mappings cannot be exact or equivalent")
        return self


class DraftCurator(Contract):
    curator_id: str = Field(min_length=1)
    kind: Literal["human", "automated_assistance"]
    method: str = Field(min_length=1)


class CurationAssertionDraft(Contract):
    assertion_id: str = Field(min_length=1)
    condition_source: str = Field(min_length=1)
    subject: CuratedCode
    observation_source: str = Field(min_length=1)
    object: CuratedCode
    relation: RelationType
    polarity: Literal["present", "excluded", "unknown"] = "present"
    population: list[str] = Field(min_length=1)
    clinical_context: str = Field(min_length=1)
    temporal_context: str | None = Field(default=None, min_length=1)
    severity: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    laterality: Literal["left", "right", "bilateral", "midline", "unspecified"] | None = None
    source_artifact_id: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    record_locator: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    source_segment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_date: date
    source_release: str = Field(min_length=1)
    evidence_family_id: str = Field(min_length=1)
    dependency_type: DependencyType
    upstream_reference: str = Field(min_length=1)
    curator: DraftCurator
    review_status: ReviewState = "pending_review"
    mapping_notes: str = Field(min_length=1)
    is_discriminating: bool = False
    discriminating_against: list[str] = Field(default_factory=list)
    therapeutic_content: bool = False

    @model_validator(mode="after")
    def discriminant_has_comparators(self) -> Self:
        if self.is_discriminating != bool(self.discriminating_against):
            raise ValueError("Discriminating assertions must list compared candidates")
        if self.therapeutic_content:
            raise ValueError("Therapeutic content is outside the v0.5 corpus")
        return self


class ReviewerAttestation(Contract):
    reviewer_id: str = Field(min_length=1)
    roles: list[Literal["clinical", "mapping"]] = Field(min_length=1)
    qualified_clinician: bool = False
    attestation_path: str
    attestation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_by: str = Field(min_length=1)
    verification_date: date

    @field_validator("attestation_path")
    @classmethod
    def safe_attestation_path(cls, value: str) -> str:
        _safe_local_path(value)
        return value


class ReviewDecision(Contract):
    item_type: ReviewItemType
    item_id: str = Field(min_length=1)
    item_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_id: str = Field(min_length=1)
    decision: ReviewDecisionValue
    reviewed_at: datetime
    comment: str = ""


class PublicationBlocker(Contract):
    code: str = Field(min_length=1)
    item_id: str | None = None
    message: str = Field(min_length=1)


class CandidateCoverage(Contract):
    candidate: CuratedCode
    assertions_total: int = Field(ge=0)
    assertions_discriminating: int = Field(ge=0)
    assertions_pending_review: int = Field(ge=0)
    assertions_approved: int = Field(ge=0)
    evidence_families: list[str]
    content_threshold_met: bool
    publication_threshold_met: bool


class CurationPublicationReport(Contract):
    schema_version: Literal[1] = 1
    package_id: str
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["ready_for_publication", "blocked"]
    technical_status: Literal[
        "ready_for_human_review", "not_ready_for_human_review", "publication_ready"
    ]
    artifacts_verified: bool
    totals: dict[str, int]
    assertions_by_status: dict[str, int]
    assertions_by_family: dict[str, int]
    candidates: list[CandidateCoverage]
    blockers: list[PublicationBlocker]


class LoadedCurationPackage:
    def __init__(
        self,
        *,
        path: Path,
        manifest: CurationPackageManifest,
        sources: list[SourceArtifactReceipt],
        concepts: list[CurationConcept],
        mappings: list[CurationMapping],
        assertions: list[CurationAssertionDraft],
        reviewers: list[ReviewerAttestation],
        reviews: list[ReviewDecision],
    ) -> None:
        self.path = path
        self.manifest = manifest
        self.sources = sources
        self.concepts = concepts
        self.mappings = mappings
        self.assertions = assertions
        self.reviewers = reviewers
        self.reviews = reviews


def load_curation_package(path: Path) -> LoadedCurationPackage:
    path = path.resolve()
    manifest = CurationPackageManifest.model_validate_json((path / "manifest.json").read_bytes())
    sources_payload = orjson.loads((path / manifest.source_artifacts_file).read_bytes())
    if not isinstance(sources_payload, list):
        raise LatrosError("Curation source artifact catalog must be a JSON array")
    return LoadedCurationPackage(
        path=path,
        manifest=manifest,
        sources=[SourceArtifactReceipt.model_validate(item) for item in sources_payload],
        concepts=_load_jsonl(path / manifest.concepts_file, CurationConcept),
        mappings=_load_jsonl(path / manifest.mappings_file, CurationMapping),
        assertions=_load_jsonl(path / manifest.assertions_file, CurationAssertionDraft),
        reviewers=_load_jsonl(path / manifest.reviewers_file, ReviewerAttestation),
        reviews=_load_jsonl(path / manifest.reviews_file, ReviewDecision),
    )


def audit_curation_package(
    root: Path, package_path: Path, *, verify_artifacts: bool = True
) -> CurationPublicationReport:
    root = root.resolve()
    package = load_curation_package(package_path)
    blockers: list[PublicationBlocker] = []
    sources = _unique(package.sources, "artifact_id", "source artifact")
    concepts = _unique_code(package.concepts)
    _unique(package.mappings, "mapping_id", "mapping")
    _unique(package.assertions, "assertion_id", "assertion")
    reviewers = _unique(package.reviewers, "reviewer_id", "reviewer")
    segments = _load_segments(root, package.manifest, blockers, verify_artifacts)

    if package.manifest.status != "approved_for_snapshot":
        _block(
            blockers,
            "package_status_pending",
            package.manifest.package_id,
            "Package manifest is not approved for snapshot publication",
        )

    if not verify_artifacts:
        _block(
            blockers,
            "artifact_verification_skipped",
            None,
            "Local artifacts were not verified; publication is forbidden",
        )
    for artifact in package.sources:
        if verify_artifacts:
            _verify_file(
                root,
                artifact.local_path,
                artifact.sha256,
                blockers,
                "source_artifact_invalid",
                artifact.artifact_id,
            )
        if artifact.legal_status != "approved_for_structured_reuse":
            _block(
                blockers,
                "source_legal_status",
                artifact.artifact_id,
                f"Source legal status is {artifact.legal_status}",
            )
        if artifact.redistribution in {"prohibited", "unknown"}:
            _block(
                blockers,
                "source_redistribution",
                artifact.artifact_id,
                f"Source redistribution is {artifact.redistribution}",
            )

    candidate_keys = {_code_key(item) for item in package.manifest.candidate_codes}
    for candidate in package.manifest.candidate_codes:
        concept = concepts.get(_code_key(candidate))
        if concept is None or concept.kind != "condition":
            _block(
                blockers,
                "candidate_concept_missing",
                _display_code(candidate),
                "Candidate must resolve to an internal condition concept",
            )

    mapping_reviews = _decisions_by_item(package.reviews, "mapping")
    for mapping in package.mappings:
        if _code_key(mapping.source) not in concepts:
            _block(
                blockers,
                "mapping_source_missing",
                mapping.mapping_id,
                "Mapping source does not resolve to a package concept",
            )
        mapping_artifact = sources.get(mapping.source_artifact_id)
        if mapping_artifact is None or mapping_artifact.role != "terminology":
            _block(
                blockers,
                "mapping_provenance_invalid",
                mapping.mapping_id,
                "Mapping must cite a terminology artifact",
            )
        if mapping.resolution_status != "resolved":
            _block(
                blockers,
                "mapping_unresolved",
                mapping.mapping_id,
                f"Mapping resolution is {mapping.resolution_status}",
            )
        if mapping.review_status != "approved" or not _mapping_is_approved(
            mapping, mapping_reviews.get(mapping.mapping_id, []), reviewers, root, blockers
        ):
            _block(
                blockers,
                "mapping_review_incomplete",
                mapping.mapping_id,
                "Mapping lacks an approved decision from an attested mapping reviewer",
            )

    assertion_reviews = _decisions_by_item(package.reviews, "assertion")
    signatures: set[tuple[str, str, str, str, str]] = set()
    approved_assertions: set[str] = set()
    counts_by_candidate: Counter[tuple[str, str]] = Counter()
    eligible_by_candidate: Counter[tuple[str, str]] = Counter()
    discriminants_by_candidate: Counter[tuple[str, str]] = Counter()
    pending_by_candidate: Counter[tuple[str, str]] = Counter()
    approved_by_candidate: Counter[tuple[str, str]] = Counter()
    families_by_candidate: dict[tuple[str, str], set[str]] = defaultdict(set)
    assertions_by_family: Counter[str] = Counter()
    assertions_by_status: Counter[str] = Counter()
    for assertion in package.assertions:
        subject_key = _code_key(assertion.subject)
        counts_by_candidate[subject_key] += 1
        eligible = assertion.review_status in {"pending_review", "approved"}
        if eligible:
            eligible_by_candidate[subject_key] += 1
        assertions_by_status[assertion.review_status] += 1
        assertions_by_family[assertion.evidence_family_id] += 1
        families_by_candidate[subject_key].add(assertion.evidence_family_id)
        if assertion.is_discriminating and eligible:
            discriminants_by_candidate[subject_key] += 1
        if assertion.review_status == "pending_review":
            pending_by_candidate[subject_key] += 1
        signature = (
            *subject_key,
            assertion.relation,
            _display_code(assertion.object),
            assertion.polarity,
        )
        if signature in signatures:
            _block(
                blockers,
                "duplicate_assertion",
                assertion.assertion_id,
                "Duplicate semantic assertion in pending package",
            )
        signatures.add(signature)
        if subject_key not in candidate_keys:
            _block(
                blockers,
                "assertion_candidate_out_of_scope",
                assertion.assertion_id,
                "Assertion subject is outside the four declared candidates",
            )
        if _code_key(assertion.object) not in concepts:
            _block(
                blockers,
                "assertion_object_missing",
                assertion.assertion_id,
                "Assertion observation does not resolve to a package concept",
            )
        assertion_artifact = sources.get(assertion.source_artifact_id)
        if assertion_artifact is None or assertion_artifact.role != "clinical_assertions":
            _block(
                blockers,
                "assertion_source_invalid",
                assertion.assertion_id,
                "Assertion must cite a clinical source artifact",
            )
        else:
            if assertion.source_url != assertion_artifact.source_url:
                _block(
                    blockers,
                    "assertion_source_url_mismatch",
                    assertion.assertion_id,
                    "Assertion URL differs from its artifact receipt",
                )
            if (
                assertion.source_release != assertion_artifact.release
                or assertion.access_date != assertion_artifact.access_date
            ):
                _block(
                    blockers,
                    "assertion_source_version_mismatch",
                    assertion.assertion_id,
                    "Assertion release or access date differs from its artifact receipt",
                )
            if (
                assertion.evidence_family_id != assertion_artifact.evidence_family_id
                or assertion.dependency_type != assertion_artifact.dependency_type
                or assertion.upstream_reference != assertion_artifact.upstream_reference
            ):
                _block(
                    blockers,
                    "assertion_dependency_mismatch",
                    assertion.assertion_id,
                    "Assertion family/dependency differs from its artifact receipt",
                )
        segment = segments.get(assertion.segment_id)
        if segment is None or segment.get("artifact_id") != assertion.source_artifact_id:
            _block(
                blockers,
                "assertion_segment_missing",
                assertion.assertion_id,
                "Source segment is absent or belongs to another artifact",
            )
        else:
            if segment.get("locator") != assertion.record_locator:
                _block(
                    blockers,
                    "assertion_segment_locator",
                    assertion.assertion_id,
                    "Assertion locator differs from the local source segment",
                )
            if _text_hash(str(segment.get("text", ""))) != assertion.source_segment_sha256:
                _block(
                    blockers,
                    "assertion_segment_hash",
                    assertion.assertion_id,
                    "Source segment hash does not match the local representation",
                )
        if _assertion_is_approved(
            assertion,
            assertion_reviews.get(assertion.assertion_id, []),
            reviewers,
            root,
            blockers,
        ):
            approved_assertions.add(assertion.assertion_id)
            approved_by_candidate[subject_key] += 1
        else:
            _block(
                blockers,
                "assertion_review_incomplete",
                assertion.assertion_id,
                "Assertion requires two attested approvals, including a qualified clinician",
            )

    candidate_reports: list[CandidateCoverage] = []
    for candidate in package.manifest.candidate_codes:
        key = _code_key(candidate)
        total = counts_by_candidate[key]
        eligible_total = eligible_by_candidate[key]
        discriminating = discriminants_by_candidate[key]
        content_met = (
            eligible_total >= package.manifest.minimum_assertions_per_candidate
            and discriminating >= package.manifest.minimum_discriminating_per_candidate
        )
        publication_met = (
            content_met
            and approved_by_candidate[key] >= package.manifest.minimum_assertions_per_candidate
            and sum(
                item.is_discriminating and item.assertion_id in approved_assertions
                for item in package.assertions
                if _code_key(item.subject) == key
            )
            >= package.manifest.minimum_discriminating_per_candidate
        )
        if not content_met:
            _block(
                blockers,
                "candidate_content_threshold",
                _display_code(candidate),
                "Candidate lacks the required assertions or discriminant",
            )
        if not publication_met:
            _block(
                blockers,
                "candidate_publication_threshold",
                _display_code(candidate),
                "Candidate lacks enough fully approved assertions",
            )
        candidate_reports.append(
            CandidateCoverage(
                candidate=candidate,
                assertions_total=total,
                assertions_discriminating=discriminating,
                assertions_pending_review=pending_by_candidate[key],
                assertions_approved=approved_by_candidate[key],
                evidence_families=sorted(families_by_candidate[key]),
                content_threshold_met=content_met,
                publication_threshold_met=publication_met,
            )
        )

    blockers = _deduplicate_blockers(blockers)
    status: Literal["ready_for_publication", "blocked"] = (
        "ready_for_publication" if not blockers else "blocked"
    )
    non_review_blockers = [
        item
        for item in blockers
        if item.code
        not in {
            "assertion_review_incomplete",
            "candidate_publication_threshold",
            "mapping_review_incomplete",
            "package_status_pending",
        }
    ]
    technical_status: Literal[
        "ready_for_human_review", "not_ready_for_human_review", "publication_ready"
    ]
    if status == "ready_for_publication":
        technical_status = "publication_ready"
    elif not non_review_blockers and all(item.content_threshold_met for item in candidate_reports):
        technical_status = "ready_for_human_review"
    else:
        technical_status = "not_ready_for_human_review"
    return CurationPublicationReport(
        package_id=package.manifest.package_id,
        package_sha256=_package_hash(package),
        status=status,
        technical_status=technical_status,
        artifacts_verified=verify_artifacts,
        totals={
            "source_artifacts": len(package.sources),
            "concepts": len(package.concepts),
            "mappings": len(package.mappings),
            "assertions": len(package.assertions),
            "reviewers": len(package.reviewers),
            "reviews": len(package.reviews),
        },
        assertions_by_status=dict(sorted(assertions_by_status.items())),
        assertions_by_family=dict(sorted(assertions_by_family.items())),
        candidates=candidate_reports,
        blockers=blockers,
    )


def export_approved_assertions(
    root: Path, package_path: Path, output_path: Path
) -> list[CuratedAssertionRecord]:
    report = audit_curation_package(root, package_path)
    if report.status != "ready_for_publication":
        codes = ", ".join(sorted({item.code for item in report.blockers}))
        raise LatrosError(f"Curation package is not publishable: {codes}")
    package = load_curation_package(package_path)
    reviewers = {item.reviewer_id: item for item in package.reviewers}
    decisions = _decisions_by_item(package.reviews, "assertion")
    exported: list[CuratedAssertionRecord] = []
    for assertion in sorted(package.assertions, key=lambda item: item.assertion_id):
        review_pair = _approved_assertion_review_pair(
            assertion,
            decisions[assertion.assertion_id],
            reviewers,
            root,
            [],
        )
        if review_pair is None:
            raise LatrosError(f"Approved curation lost its reviewer pair: {assertion.assertion_id}")
        clinical_reviewer, mapping_reviewer = review_pair
        review_models = [
            CurationReviewer(reviewer_id=clinical_reviewer.reviewer_id, role="clinical"),
            CurationReviewer(reviewer_id=mapping_reviewer.reviewer_id, role="mapping"),
        ]
        exported.append(
            CuratedAssertionRecord(
                assertion_id=assertion.assertion_id,
                record_id=assertion.assertion_id,
                record_locator=assertion.record_locator,
                source_text_sha256=assertion.source_segment_sha256,
                source_id=assertion.source_artifact_id,
                source_url=assertion.source_url,
                source_release=assertion.source_release,
                access_date=assertion.access_date,
                segment_id=assertion.segment_id,
                subject=assertion.subject,
                relation=assertion.relation,
                object=assertion.object,
                polarity=assertion.polarity,
                population=assertion.population,
                clinical_context=assertion.clinical_context,
                temporal_context=assertion.temporal_context,
                severity=assertion.severity,
                location=assertion.location,
                laterality=assertion.laterality,
                curator_id=assertion.curator.curator_id,
                reviewers=review_models,
                status="approved",
                evidence_family=CuratedEvidenceFamily(
                    family_id=assertion.evidence_family_id,
                    dependency_type=assertion.dependency_type,
                    primary_reference=assertion.upstream_reference,
                ),
                mapping_notes=assertion.mapping_notes,
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        for item in exported:
            handle.write(orjson.dumps(item.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS))
            handle.write(b"\n")
    temporary.replace(output_path)
    return exported


def write_review_workbook(package_path: Path, output_path: Path) -> None:
    """Render a deterministic review aid without creating review decisions."""
    package = load_curation_package(package_path)
    reviews = _decisions_by_item(package.reviews, "assertion")
    lines = [
        f"# Review workbook — {package.manifest.package_id}",
        "",
        "> Generated review aid. Blank reviewer columns are intentional and are not approvals.",
        "",
        f"- Package hash: `{_package_hash(package)}`",
        f"- Status: `{package.manifest.status}`",
        f"- Population: {package.manifest.population}",
        "",
        "## Assertions",
        "",
        "| ID | Record hash | Condition | Observation | Polarity and qualifiers | Source locator | "
        "Structured interpretation | Mapping note | Evidence | Reviewer decisions | "
        "Final state |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for assertion in sorted(package.assertions, key=lambda item: item.assertion_id):
        qualifiers = ", ".join(
            value
            for value in (
                assertion.polarity,
                assertion.temporal_context,
                assertion.severity,
                assertion.location,
                assertion.laterality,
            )
            if value
        )
        decisions = reviews.get(assertion.assertion_id, [])
        decision_text = "; ".join(f"{item.reviewer_id}: {item.decision}" for item in decisions)
        source = (
            f"[{assertion.source_artifact_id}]({assertion.source_url}) — {assertion.record_locator}"
        )
        interpretation = (
            f"{_display_code(assertion.subject)} "
            f"{assertion.relation} {_display_code(assertion.object)}"
        )
        evidence = f"{assertion.evidence_family_id} / {assertion.dependency_type}"
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    assertion.assertion_id,
                    record_hash(assertion),
                    assertion.condition_source,
                    assertion.observation_source,
                    qualifiers,
                    source,
                    interpretation,
                    assertion.mapping_notes,
                    evidence,
                    decision_text,
                    assertion.review_status,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Terminology mappings",
            "",
            "| ID | Record hash | Source | Target | Relation | Resolution | Provenance | "
            "Confidence | Review state |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for mapping in sorted(package.mappings, key=lambda item: item.mapping_id):
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    mapping.mapping_id,
                    record_hash(mapping),
                    _display_code(mapping.source),
                    _display_code(mapping.target),
                    f"{mapping.direction} / {mapping.relation}",
                    mapping.resolution_status,
                    f"{mapping.source_artifact_id} — {mapping.record_locator}",
                    mapping.confidence,
                    mapping.review_status,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Required evidence of review",
            "",
            "A decision is effective only when its JSONL record contains the hash of the "
            "exact assertion or mapping and its reviewer has a matching local attestation "
            "file. Publication requires two distinct assertion approvals, including one "
            "attested qualified clinician, plus an attested mapping reviewer.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(output_path)


def record_hash(value: Contract) -> str:
    return hashlib.sha256(encoded(value.model_dump(mode="json"))).hexdigest()


def _assertion_is_approved(
    assertion: CurationAssertionDraft,
    decisions: list[ReviewDecision],
    reviewers: dict[str, ReviewerAttestation],
    root: Path,
    blockers: list[PublicationBlocker],
) -> bool:
    return (
        _approved_assertion_review_pair(assertion, decisions, reviewers, root, blockers) is not None
    )


def _approved_assertion_review_pair(
    assertion: CurationAssertionDraft,
    decisions: list[ReviewDecision],
    reviewers: dict[str, ReviewerAttestation],
    root: Path,
    blockers: list[PublicationBlocker],
) -> tuple[ReviewerAttestation, ReviewerAttestation] | None:
    if assertion.review_status != "approved":
        return None
    expected = record_hash(assertion)
    accepted = [
        item for item in decisions if item.item_sha256 == expected and item.decision == "approved"
    ]
    identities = {item.reviewer_id for item in accepted}
    if len(identities) < 2 or assertion.curator.curator_id in identities:
        return None
    attestations = [
        reviewers[reviewer_id] for reviewer_id in identities if reviewer_id in reviewers
    ]
    if len(attestations) != len(identities):
        return None
    if not all(_attestation_valid(root, item, blockers) for item in attestations):
        return None
    clinicians = sorted(
        (item for item in attestations if item.qualified_clinician and "clinical" in item.roles),
        key=lambda item: item.reviewer_id,
    )
    for clinician in clinicians:
        mapping_reviewers = sorted(
            (
                item
                for item in attestations
                if item.reviewer_id != clinician.reviewer_id and "mapping" in item.roles
            ),
            key=lambda item: item.reviewer_id,
        )
        if mapping_reviewers:
            return clinician, mapping_reviewers[0]
    return None


def _mapping_is_approved(
    mapping: CurationMapping,
    decisions: list[ReviewDecision],
    reviewers: dict[str, ReviewerAttestation],
    root: Path,
    blockers: list[PublicationBlocker],
) -> bool:
    expected = record_hash(mapping)
    for decision in decisions:
        attestation = reviewers.get(decision.reviewer_id)
        if (
            decision.item_sha256 == expected
            and decision.decision == "approved"
            and attestation is not None
            and "mapping" in attestation.roles
            and _attestation_valid(root, attestation, blockers)
        ):
            return True
    return False


def _attestation_valid(
    root: Path,
    attestation: ReviewerAttestation,
    blockers: list[PublicationBlocker],
) -> bool:
    path = root / PurePosixPath(attestation.attestation_path)
    valid = path.is_file() and sha256(path) == attestation.attestation_sha256
    if not valid:
        _block(
            blockers,
            "reviewer_attestation_invalid",
            attestation.reviewer_id,
            "Reviewer attestation is missing or has the wrong hash",
        )
    return valid


def _load_segments(
    root: Path,
    manifest: CurationPackageManifest,
    blockers: list[PublicationBlocker],
    verify: bool,
) -> dict[str, dict[str, Any]]:
    path = root / PurePosixPath(manifest.segment_representation_path)
    if verify and (not path.is_file() or sha256(path) != manifest.segment_representation_sha256):
        _block(
            blockers,
            "segment_representation_invalid",
            None,
            "Local source-segment representation is missing or corrupt",
        )
        return {}
    if not path.is_file():
        return {}
    payload = orjson.loads(path.read_bytes())
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        raise LatrosError("Segment representation must contain a segments array")
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("segment_id"), str):
            raise LatrosError("Invalid source segment representation")
        segment_id = segment["segment_id"]
        if segment_id in result:
            raise LatrosError(f"Duplicate source segment: {segment_id}")
        result[segment_id] = segment
    return result


def _verify_file(
    root: Path,
    relative: str,
    expected: str,
    blockers: list[PublicationBlocker],
    code: str,
    item_id: str,
) -> None:
    path = root / PurePosixPath(relative)
    if not path.is_file() or sha256(path) != expected:
        _block(blockers, code, item_id, "Local artifact is missing or has the wrong hash")


def _decisions_by_item(
    decisions: list[ReviewDecision], item_type: ReviewItemType
) -> dict[str, list[ReviewDecision]]:
    result: dict[str, list[ReviewDecision]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for decision in decisions:
        if decision.item_type != item_type:
            continue
        key = (decision.item_id, decision.reviewer_id)
        if key in seen:
            raise LatrosError(
                f"Duplicate review decision for {decision.item_id}/{decision.reviewer_id}"
            )
        seen.add(key)
        result[decision.item_id].append(decision)
    return result


def _load_jsonl(path: Path, model: type[Contract]) -> list[Any]:
    result: list[Any] = []
    if not path.is_file():
        raise LatrosError(f"Curation package file is missing: {path}")
    for ordinal, line in enumerate(path.read_bytes().splitlines(), 1):
        if not line.strip():
            continue
        payload = orjson.loads(line)
        if not isinstance(payload, dict):
            raise LatrosError(f"Curation JSONL line {ordinal} must be an object: {path}")
        result.append(model.model_validate(payload))
    return result


def _unique(items: list[Any], field: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        identifier = str(getattr(item, field))
        if identifier in result:
            raise LatrosError(f"Duplicate {label}: {identifier}")
        result[identifier] = item
    return result


def _unique_code(items: list[CurationConcept]) -> dict[tuple[str, str], CurationConcept]:
    result: dict[tuple[str, str], CurationConcept] = {}
    for item in items:
        key = _code_key(item.concept)
        if key in result:
            raise LatrosError(f"Duplicate curation concept: {_display_code(item.concept)}")
        result[key] = item
    return result


def _package_hash(package: LoadedCurationPackage) -> str:
    payload = {
        "manifest": package.manifest.model_dump(mode="json"),
        "sources": [item.model_dump(mode="json") for item in package.sources],
        "concepts": [item.model_dump(mode="json") for item in package.concepts],
        "mappings": [item.model_dump(mode="json") for item in package.mappings],
        "assertions": [item.model_dump(mode="json") for item in package.assertions],
        "reviewers": [item.model_dump(mode="json") for item in package.reviewers],
        "reviews": [item.model_dump(mode="json") for item in package.reviews],
    }
    return hashlib.sha256(encoded(payload)).hexdigest()


def _code_key(value: CuratedCode) -> tuple[str, str]:
    return (value.system, value.code)


def _display_code(value: CuratedCode) -> str:
    return f"{value.system}|{value.code}"


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _safe_local_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("A safe root-relative local path is required")


def _block(
    blockers: list[PublicationBlocker], code: str, item_id: str | None, message: str
) -> None:
    blockers.append(PublicationBlocker(code=code, item_id=item_id, message=message))


def _deduplicate_blockers(blockers: list[PublicationBlocker]) -> list[PublicationBlocker]:
    unique = {(item.code, item.item_id, item.message): item for item in blockers}
    return [
        unique[key]
        for key in sorted(
            unique,
            key=lambda item: (item[0], item[1] or "", item[2]),
        )
    ]
