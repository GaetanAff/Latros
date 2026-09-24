"""Explicitly non-clinical construction from a pending curation package.

This module is deliberately separate from the approved curation exporter.  It
does not alter review files or relax the official publication gate.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Literal

from latros.common import LatrosError, sha256, stable_id
from latros.knowledge.curation import (
    LoadedCurationPackage,
    SourceArtifactReceipt,
    audit_curation_package,
    load_curation_package,
)
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.models_v2 import (
    AssertionDerivation,
    AssertionQualifiers,
    CanonicalAssertion,
    CanonicalKnowledgeV2,
    ConceptMappingV2,
    ConceptObject,
    ConceptV2,
    DesignationV2,
    EvidenceFamily,
    ExternalIdentifierV2,
    SourceArtifactV2,
    SourceAssertion,
    SourceDependency,
    SourceRecordV2,
    SourceReleaseV2,
    make_canonical_assertion_id,
    make_source_assertion_id,
)
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.sources.registry_v2 import (
    ArtifactFormatV2,
    LicenseV2,
    Redistribution,
    RegistryArtifactV2,
    RegistryDependencyV2,
    RegistryV2,
    SnapshotScopeV2,
    SourcePackageV2,
)

UNREVIEWED_SNAPSHOT_SUFFIX = "-dev-unreviewed"
UNREVIEWED_PROFILE_ID = "general_v1-orl-unreviewed"
UNREVIEWED_WARNING = (
    "UNREVIEWED LOCAL RESEARCH DATA: assertions and terminology mappings have not completed "
    "human clinical review; this snapshot is not clinically validated or publishable"
)
_REVIEW_ONLY_BLOCKERS = {
    "assertion_review_incomplete",
    "candidate_publication_threshold",
    "mapping_review_incomplete",
    "package_status_pending",
}


def build_unreviewed_research_snapshot(
    root: Path,
    package_path: Path,
    snapshot: str,
    *,
    allow_unreviewed_research_data: bool,
) -> KnowledgeSnapshotManifestV2:
    """Build the local-only snapshot after a deliberate, recorded override."""
    if not allow_unreviewed_research_data:
        raise LatrosError(
            "Unreviewed research data is disabled; pass --allow-unreviewed-research-data "
            "deliberately"
        )
    if not snapshot.endswith(UNREVIEWED_SNAPSHOT_SUFFIX):
        raise LatrosError(
            "The unreviewed override may only build a snapshot ending in -dev-unreviewed"
        )
    package = _validated_pending_package(root, package_path)
    registry, knowledge = canonicalize_pending_package(root, package)
    metadata = {
        "validation_status": "unreviewed",
        "intended_use": "local_research_only",
        "clinical_validation": False,
        "human_review_complete": False,
        "publishable": False,
        "research_override_used": True,
        "unreviewed_assertion_ids": sorted(item.assertion_id for item in package.assertions),
        "unreviewed_mapping_ids": sorted(item.mapping_id for item in package.mappings),
        "reviewer_count": len(package.reviewers),
        "limitations": [
            UNREVIEWED_WARNING,
            "All clinical assertions retain their actual pending_review status.",
            "All terminology mappings retain their actual pending_review status.",
            "Exact/equivalent mappings may resolve codes technically but are not human-validated.",
            "Broader, narrower, related, ambiguous and unresolved mappings never score.",
            "general_v1.compatibility is not a diagnostic probability.",
            "Safety and triage are not evaluated.",
        ],
    }
    return build_snapshot_v2(
        root,
        registry,
        snapshot,
        knowledge,
        research_metadata=metadata,
    )


def require_official_gate(root: Path, package_path: Path) -> None:
    """Keep the official v0.5.0 path tied to the unchanged human-review gate."""
    report = audit_curation_package(root, package_path)
    if report.status != "ready_for_publication":
        codes = ", ".join(sorted({item.code for item in report.blockers}))
        raise LatrosError(f"Official v0.5.0 publication gate is blocked: {codes}")


def canonicalize_pending_package(
    root: Path, package: LoadedCurationPackage
) -> tuple[RegistryV2, CanonicalKnowledgeV2]:
    """Translate pending records without changing their contents or statuses."""
    registry = _registry(root, package)
    release_by_artifact: dict[str, str] = {}
    curation_artifact_ids: dict[str, str] = {}
    source_releases: list[SourceReleaseV2] = []
    source_artifacts: list[SourceArtifactV2] = []
    for source in registry.sources:
        release_id = f"{source.source_id}:{source.release}"
        source_releases.append(
            SourceReleaseV2(
                source_release_id=release_id,
                source_id=source.source_id,
                release=source.release,
                release_date=source.release_date.isoformat() if source.release_date else None,
                license_name=source.license.name,
                license_url=source.license.url,
                attribution=source.license.attribution,
                redistribution=source.license.redistribution,
                roles=source.roles,
            )
        )
        for artifact in source.artifacts:
            artifact_id = _artifact_id(source, artifact)
            source_artifacts.append(
                SourceArtifactV2(
                    artifact_id=artifact_id,
                    source_release_id=release_id,
                    filename=artifact.filename,
                    sha256=artifact.sha256,
                    format=artifact.format,
                    language=artifact.language,
                    source_url=artifact.source_url,
                )
            )
            receipt_id = artifact.product.removeprefix("curation-source:")
            release_by_artifact[receipt_id] = release_id
            if artifact.product.startswith("curation-package:"):
                curation_artifact_ids[artifact.product] = artifact_id

    curation_release_id = f"latros-curation:{package.manifest.package_id}"
    concepts: list[ConceptV2] = []
    designations: list[DesignationV2] = []
    identifiers: list[ExternalIdentifierV2] = []
    concept_ids: dict[tuple[str, str], str] = {}
    for concept_item in package.concepts:
        key = (concept_item.concept.system, concept_item.concept.code)
        concept_id = f"orl:{concept_item.concept.code}"
        concept_ids[key] = concept_id
        concepts.append(
            ConceptV2(
                concept_id=concept_id,
                kind=concept_item.kind,
                status=concept_item.status,
                primary_code=concept_item.concept.code,
                source_release_id=curation_release_id,
            )
        )
        designations.append(
            DesignationV2(
                designation_id=stable_id(
                    "designation", concept_id, concept_item.language, concept_item.label
                ),
                concept_id=concept_id,
                language=concept_item.language,
                text=concept_item.label,
                scope="preferred",
                source_release_id=curation_release_id,
            )
        )
        identifiers.append(
            ExternalIdentifierV2(
                external_identifier_id=stable_id(
                    "external_identifier",
                    concept_id,
                    concept_item.concept.system,
                    concept_item.concept.code,
                ),
                concept_id=concept_id,
                system=concept_item.concept.system,
                code=concept_item.concept.code,
                relation="source_code",
                source_release_id=curation_release_id,
            )
        )

    mappings = [
        ConceptMappingV2(
            mapping_id=item.mapping_id,
            source_concept_id=concept_ids[(item.source.system, item.source.code)],
            target_concept_id=(
                concept_ids[(item.source.system, item.source.code)]
                if item.resolution_status == "resolved"
                else None
            ),
            target_system=item.target.system,
            target_code=item.target.code,
            direction=item.direction,
            relation=item.relation,
            original_relation=item.relation,
            source_release_id=release_by_artifact[item.source_artifact_id],
            evidence={
                "source_artifact_id": item.source_artifact_id,
                "curation_mapping_artifact_id": curation_artifact_ids[
                    f"curation-package:{package.manifest.mappings_file}"
                ],
                "record_locator": item.record_locator,
                "provenance_note": item.provenance_note,
                "confidence": item.confidence,
                "review_status": item.review_status,
                "human_review_complete": False,
                "research_unreviewed": True,
            },
            resolution_status=item.resolution_status,
        )
        for item in package.mappings
    ]

    source_lookup = {item.artifact_id: item for item in package.sources}
    canonical_artifact_lookup = {
        item.product.removeprefix("curation-source:"): _artifact_id(source, item)
        for source in registry.sources
        for item in source.artifacts
        if item.product.startswith("curation-source:")
    }
    source_records: list[SourceRecordV2] = []
    source_assertions: list[SourceAssertion] = []
    canonical_assertions: dict[str, CanonicalAssertion] = {}
    derivations: list[AssertionDerivation] = []
    family_assertions: dict[str, list[str]] = defaultdict(list)
    family_releases: dict[str, set[str]] = defaultdict(set)
    family_dependencies: dict[str, list[str]] = defaultdict(list)
    family_references: dict[str, set[str]] = defaultdict(set)
    for ordinal, assertion in enumerate(package.assertions):
        receipt = source_lookup[assertion.source_artifact_id]
        release_id = release_by_artifact[assertion.source_artifact_id]
        artifact_id = canonical_artifact_lookup[assertion.source_artifact_id]
        curation_assertions_artifact_id = curation_artifact_ids[
            f"curation-package:{package.manifest.assertions_file}"
        ]
        provenance_artifact_ids = [artifact_id, curation_assertions_artifact_id]
        subject_id = concept_ids[(assertion.subject.system, assertion.subject.code)]
        object_id = concept_ids[(assertion.object.system, assertion.object.code)]
        record_id = stable_id("source_record", release_id, assertion.assertion_id)
        raw_value = assertion.model_dump(mode="json")
        source_records.append(
            SourceRecordV2(
                source_record_id=record_id,
                source_release_id=release_id,
                artifact_ids=provenance_artifact_ids,
                record_locator=assertion.record_locator,
                raw_value=raw_value,
            )
        )
        qualifiers = AssertionQualifiers(
            polarity=assertion.polarity,
            population=assertion.population,
            temporal_context=assertion.temporal_context,
            clinical_context=assertion.clinical_context,
            severity=assertion.severity,
            location=assertion.location,
            laterality=assertion.laterality,
            evidence_type="unreviewed_structured_curation",
            evidence_level="pending_review",
        )
        object_value = ConceptObject(concept_id=object_id)
        source_assertion_id = make_source_assertion_id(
            receipt.source_id,
            receipt.release,
            [receipt.sha256, sha256(package.path / package.manifest.assertions_file)],
            assertion.record_locator,
            ordinal,
        )
        source_assertions.append(
            SourceAssertion(
                source_assertion_id=source_assertion_id,
                subject_concept_id=subject_id,
                relation=assertion.relation,
                object=object_value,
                qualifiers=qualifiers,
                source_release_id=release_id,
                source_record_id=record_id,
                artifact_ids=provenance_artifact_ids,
                record_ordinal=ordinal,
                raw_value=raw_value,
            )
        )
        canonical_id = make_canonical_assertion_id(
            subject_id, assertion.relation, object_value, qualifiers
        )
        canonical_assertions.setdefault(
            canonical_id,
            CanonicalAssertion(
                canonical_assertion_id=canonical_id,
                subject_concept_id=subject_id,
                relation=assertion.relation,
                object=object_value,
                qualifiers=qualifiers,
            ),
        )
        derivations.append(
            AssertionDerivation(
                derivation_id=stable_id("assertion_derivation", source_assertion_id, canonical_id),
                source_assertion_id=source_assertion_id,
                canonical_assertion_id=canonical_id,
                rule_id="pending_curation_research_override",
                rule_version="1",
                transformations=[
                    "internal_code_resolution",
                    "qualifier_normalization",
                    "review_status_preserved_pending_review",
                ],
            )
        )
        family_assertions[assertion.evidence_family_id].append(source_assertion_id)
        family_releases[assertion.evidence_family_id].add(release_id)
        family_dependencies[assertion.evidence_family_id].append(assertion.dependency_type)
        family_references[assertion.evidence_family_id].add(assertion.upstream_reference)

    families = []
    for family_id in sorted(family_assertions):
        family_dependency_values = set(family_dependencies[family_id])
        dependency: Literal[
            "primary", "derived_from", "republication", "shared_upstream", "unknown"
        ]
        if "unknown" in family_dependency_values:
            dependency = "unknown"
        elif "primary" in family_dependency_values:
            dependency = "primary"
        else:
            dependency = sorted(family_dependency_values)[0]  # type: ignore[assignment]
        families.append(
            EvidenceFamily(
                evidence_family_id=family_id,
                source_release_ids=sorted(family_releases[family_id]),
                source_assertion_ids=sorted(family_assertions[family_id]),
                dependency_type=dependency,
                primary_reference=";".join(sorted(family_references[family_id])),
            )
        )

    source_dependencies: list[SourceDependency] = []
    for receipt in package.sources:
        release_id = release_by_artifact[receipt.artifact_id]
        dependency_type = receipt.dependency_type or "primary"
        upstream = receipt.upstream_reference or release_id
        source_dependencies.append(
            SourceDependency(
                source_dependency_id=stable_id(
                    "source_dependency", release_id, upstream, receipt.artifact_id
                ),
                source_release_id=release_id,
                upstream_reference=upstream,
                dependency_type=dependency_type,
                evidence=(
                    f"Curation receipt {receipt.artifact_id}; actual dependency metadata "
                    "preserved without human approval"
                ),
            )
        )
    source_dependencies.append(
        SourceDependency(
            source_dependency_id=stable_id(
                "source_dependency", curation_release_id, package.manifest.package_id
            ),
            source_release_id=curation_release_id,
            upstream_reference=package.manifest.package_id,
            dependency_type="derived_from",
            evidence="Latros structured curation package; review status preserved",
        )
    )
    return registry, CanonicalKnowledgeV2(
        source_releases=source_releases,
        source_artifacts=source_artifacts,
        source_records=source_records,
        concepts=concepts,
        designations=designations,
        external_identifiers=identifiers,
        hierarchy_edges=[],
        concept_mappings=mappings,
        source_assertions=source_assertions,
        canonical_assertions=list(canonical_assertions.values()),
        assertion_derivations=derivations,
        evidence_families=families,
        source_dependencies=source_dependencies,
    )


def _validated_pending_package(root: Path, package_path: Path) -> LoadedCurationPackage:
    report = audit_curation_package(root, package_path)
    unexpected = [item for item in report.blockers if item.code not in _REVIEW_ONLY_BLOCKERS]
    if report.technical_status != "ready_for_human_review" or unexpected:
        codes = ", ".join(sorted({item.code for item in unexpected})) or report.technical_status
        raise LatrosError(f"Pending curation package has non-review blockers: {codes}")
    package = load_curation_package(package_path)
    if package.manifest.status != "pending_clinical_review":
        raise LatrosError("Research override requires a pending_clinical_review package")
    if any(item.review_status != "pending_review" for item in package.assertions):
        raise LatrosError("Research snapshot requires assertions to retain pending_review status")
    if any(item.review_status != "pending_review" for item in package.mappings):
        raise LatrosError("Research snapshot requires mappings to retain pending_review status")
    if package.reviews:
        raise LatrosError("Research snapshot refuses partially recorded review decisions")
    return package


def _registry(root: Path, package: LoadedCurationPackage) -> RegistryV2:
    grouped_receipts: dict[tuple[str, str], list[SourceArtifactReceipt]] = defaultdict(list)
    for receipt in package.sources:
        grouped_receipts[(receipt.source_id, receipt.release)].append(receipt)
    sources = [
        _source_package(items)
        for _, items in sorted(grouped_receipts.items(), key=lambda pair: pair[0])
    ]
    concepts_path = package.path / package.manifest.concepts_file
    segment_path = (root / package.manifest.segment_representation_path).resolve()
    curation_artifact_paths = [
        package.path / "manifest.json",
        package.path / package.manifest.source_artifacts_file,
        concepts_path,
        package.path / package.manifest.mappings_file,
        package.path / package.manifest.assertions_file,
        package.path / package.manifest.reviewers_file,
        package.path / package.manifest.reviews_file,
        root / package.manifest.segment_representation_path,
    ]
    sources.append(
        SourcePackageV2(
            source_id="latros-curation",
            producer="Latros project",
            roles=["curation_metadata"],
            code_system="urn:latros:orl",
            homepage="https://github.com/GaetanAff/Latros",
            release=package.manifest.package_id,
            access_date=max(item.access_date for item in package.sources),
            importer="latros.knowledge.research_unreviewed:canonicalize_pending_package",
            license=LicenseV2(
                name="Project-internal research curation metadata",
                url="https://github.com/GaetanAff/Latros",
                attribution=(
                    "Latros local research curation; upstream provenance retained per assertion"
                ),
                redistribution="restricted",
                implementation_rights_confirmed=True,
                transformation_rights="restricted",
                restrictions=["Local research use only; not clinically validated."],
                notes="Not clinically reviewed; not a redistributable clinical reference snapshot.",
            ),
            dependencies=[
                RegistryDependencyV2(
                    upstream_reference=package.manifest.package_id,
                    dependency_type="derived_from",
                    evidence="Pinned package hash and source-level provenance",
                )
            ],
            artifacts=[
                RegistryArtifactV2(
                    filename=(
                        f"package-{path.name}"
                        if path.parent.resolve() == package.path.resolve()
                        else "source-segments.json"
                    ),
                    product=f"curation-package:{path.name}",
                    format=(
                        "curation-jsonl"
                        if path.suffix == ".jsonl"
                        else (
                            "source-segments-json"
                            if path.resolve() == segment_path
                            else "curation-package-json"
                        )
                    ),
                    language="en",
                    source_url="https://github.com/GaetanAff/Latros",
                    sha256=sha256(path),
                    access_mode="manual_local",
                    local_path=path.resolve().relative_to(root.resolve()).as_posix(),
                )
                for path in curation_artifact_paths
            ],
        )
    )
    return RegistryV2(
        scope=SnapshotScopeV2(
            scope_id="adult-ambulatory-orl-unreviewed",
            domain=package.manifest.domain,
            population=package.manifest.population,
            observation_types=["symptom", "sign", "exam", "vital"],
            relations=sorted({item.relation for item in package.assertions}),
            exclusions=package.manifest.exclusions,
        ),
        compatible_profiles=[UNREVIEWED_PROFILE_ID],
        sources=sources,
    )


def _source_package(receipts: list[SourceArtifactReceipt]) -> SourcePackageV2:
    receipt = receipts[0]
    redistribution_values: dict[str, Redistribution] = {
        "allowed_with_attribution": "allowed_with_attribution",
        "local_only": "restricted",
        "prohibited": "prohibited",
        "unknown": "restricted",
    }
    redistribution = redistribution_values[receipt.redistribution]
    dependencies = [
        RegistryDependencyV2(
            upstream_reference=item.upstream_reference,
            dependency_type=item.dependency_type,
            evidence=f"Pinned curation receipt {item.artifact_id}",
        )
        for item in receipts
        if item.dependency_type is not None and item.upstream_reference is not None
    ]
    license_signature = {
        (item.license_name, item.license_url, item.redistribution) for item in receipts
    }
    if len(license_signature) != 1:
        raise LatrosError("One source release cannot mix incompatible curation licenses")
    if any(item.legal_status != "approved_for_structured_reuse" for item in receipts):
        raise LatrosError("Unreviewed research mode does not bypass legal source review")
    return SourcePackageV2(
        source_id=receipt.source_id,
        producer=receipt.source_id,
        roles=sorted({_sovereign_role(item.role) for item in receipts}),
        code_system=f"urn:latros:source:{receipt.source_id}",
        homepage=receipt.source_url,
        release=receipt.release,
        release_date=max(
            (item.publication_date for item in receipts if item.publication_date is not None),
            default=None,
        ),
        access_date=max(item.access_date for item in receipts),
        importer="latros.knowledge.research_unreviewed:canonicalize_pending_package",
        license=LicenseV2(
            name=receipt.license_name,
            url=receipt.license_url,
            attribution="; ".join(sorted({item.attribution for item in receipts})),
            redistribution=redistribution,
            implementation_rights_confirmed=True,
            transformation_rights="allowed",
            restrictions=["Pinned local research capture; upstream terms remain controlling."],
            notes=" ".join(item.notes for item in receipts if item.notes),
        ),
        dependencies=dependencies,
        artifacts=[
            RegistryArtifactV2(
                filename=Path(item.local_path).name,
                product=f"curation-source:{item.artifact_id}",
                format=_artifact_format(item),
                language="en",
                source_url=item.source_url,
                sha256=item.sha256,
                access_mode="manual_local",
                local_path=Path(item.local_path).as_posix(),
            )
            for item in receipts
        ],
    )


def _artifact_format(receipt: SourceArtifactReceipt) -> ArtifactFormatV2:
    if receipt.capture_kind == "verified_segment_representation":
        return "source-segments-json"
    if receipt.local_path.endswith(".json"):
        return "obographs-json"
    return "html-capture"


def _sovereign_role(role: str) -> str:
    return {
        "terminology": "terminology",
        "clinical_assertions": "clinical_assertion_source",
    }.get(role, role)


def _artifact_id(source: SourcePackageV2, artifact: RegistryArtifactV2) -> str:
    receipt_id = artifact.product.removeprefix("curation-source:")
    if receipt_id != artifact.product:
        return receipt_id
    return stable_id("artifact", source.source_id, source.release, artifact.filename)
