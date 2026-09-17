"""Import restricted RF2 subsets and reviewed assertion packages into canonical v2."""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self

import orjson
from pydantic import Field, model_validator

from latros.common import LatrosError, stable_id
from latros.knowledge.models_v2 import (
    AssertionDerivation,
    AssertionQualifiers,
    CanonicalAssertion,
    CanonicalKnowledgeV2,
    ConceptObject,
    ConceptV2,
    DesignationV2,
    EvidenceFamily,
    ExternalIdentifierV2,
    HierarchyEdgeV2,
    RelationType,
    SourceArtifactV2,
    SourceAssertion,
    SourceDependency,
    SourceRecordV2,
    SourceReleaseV2,
    make_canonical_assertion_id,
    make_source_assertion_id,
)
from latros.sources.registry import Contract
from latros.sources.registry_v2 import (
    RegistryArtifactV2,
    RegistryDependencyV2,
    RegistryV2,
    SourcePackageV2,
)

RF2_FSN = {"900000000000003001", "TEST-FSN"}
RF2_IS_A = {"116680003", "TEST-IS-A"}


class CuratedCode(Contract):
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)


class CurationReviewer(Contract):
    reviewer_id: str = Field(min_length=1)
    role: Literal["clinical", "mapping"]


class CuratedEvidenceFamily(Contract):
    family_id: str = Field(min_length=1)
    dependency_type: Literal[
        "primary", "derived_from", "republication", "shared_upstream", "unknown"
    ]
    primary_reference: str = Field(min_length=1)


class CuratedAssertionRecord(Contract):
    assertion_id: str | None = Field(default=None, min_length=1)
    record_id: str = Field(min_length=1)
    record_locator: str = Field(min_length=1)
    source_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: str | None = Field(default=None, min_length=1)
    source_url: str | None = Field(default=None, pattern=r"^https://")
    source_release: str | None = Field(default=None, min_length=1)
    access_date: date | None = None
    segment_id: str | None = Field(default=None, min_length=1)
    subject: CuratedCode
    relation: RelationType
    object: CuratedCode
    polarity: Literal["present", "excluded", "unknown"] = "present"
    population: list[str] = Field(default_factory=list)
    clinical_context: str | None = Field(default=None, min_length=1)
    temporal_context: str | None = Field(default=None, min_length=1)
    severity: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    laterality: Literal["left", "right", "bilateral", "midline", "unspecified"] | None = None
    evidence_type: str | None = Field(default=None, min_length=1)
    evidence_level: str | None = Field(default=None, min_length=1)
    curator_id: str = Field(min_length=1)
    reviewers: list[CurationReviewer] = Field(min_length=2)
    status: Literal["approved"]
    evidence_family: CuratedEvidenceFamily
    mapping_notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def independent_review_roles(self) -> Self:
        roles = {reviewer.role for reviewer in self.reviewers}
        identities = {reviewer.reviewer_id for reviewer in self.reviewers}
        if roles != {"clinical", "mapping"}:
            raise ValueError("Curation requires clinical and mapping reviewers")
        if len(identities) != len(self.reviewers) or self.curator_id in identities:
            raise ValueError("Curator and reviewers must be distinct")
        return self


def import_registry_v2(root: Path, registry: RegistryV2) -> CanonicalKnowledgeV2:
    source_releases: list[SourceReleaseV2] = []
    source_artifacts: list[SourceArtifactV2] = []
    artifact_lookup: dict[tuple[str, str], SourceArtifactV2] = {}
    for source in registry.sources:
        release_id = _release_id(source)
        source_releases.append(_source_release(source))
        for artifact in source.artifacts:
            canonical = _source_artifact(release_id, artifact)
            source_artifacts.append(canonical)
            artifact_lookup[(release_id, artifact.filename)] = canonical

    concepts: dict[str, ConceptV2] = {}
    designations: list[DesignationV2] = []
    identifiers: list[ExternalIdentifierV2] = []
    edges: list[HierarchyEdgeV2] = []
    code_index: dict[tuple[str, str], str] = {}
    for source in registry.sources:
        formats = {artifact.format for artifact in source.artifacts}
        if "rf2-concepts-tsv" not in formats:
            continue
        imported = _import_rf2(root, source, artifact_lookup)
        for concept in imported[0]:
            if concept.concept_id in concepts:
                raise LatrosError(f"Duplicate canonical concept: {concept.concept_id}")
            concepts[concept.concept_id] = concept
        designations.extend(imported[1])
        identifiers.extend(imported[2])
        edges.extend(imported[3])
        for code, concept_id in imported[4].items():
            key = (source.code_system, code)
            if key in code_index:
                raise LatrosError(f"Duplicate code in v2 terminology: {key}")
            code_index[key] = concept_id

    records: list[SourceRecordV2] = []
    source_assertions: list[SourceAssertion] = []
    canonical_assertions: dict[str, CanonicalAssertion] = {}
    derivations: list[AssertionDerivation] = []
    families: dict[str, dict[str, Any]] = {}
    seen_records: set[tuple[str, str]] = set()
    for source in registry.sources:
        release_id = _release_id(source)
        for artifact in source.artifacts:
            if artifact.format != "curated-assertions-jsonl":
                continue
            canonical_artifact = artifact_lookup[(release_id, artifact.filename)]
            path = _raw_path(root, source, artifact)
            for ordinal, payload in _jsonl(path):
                curated = CuratedAssertionRecord.model_validate(payload)
                record_key = (release_id, curated.record_id)
                if record_key in seen_records:
                    raise LatrosError(f"Duplicate curated record: {curated.record_id}")
                seen_records.add(record_key)
                subject_id = _resolve_code(code_index, curated.subject)
                object_id = _resolve_code(code_index, curated.object)
                source_record_id = stable_id("source_record", release_id, curated.record_id)
                records.append(
                    SourceRecordV2(
                        source_record_id=source_record_id,
                        source_release_id=release_id,
                        artifact_ids=[canonical_artifact.artifact_id],
                        record_locator=curated.record_locator,
                        raw_value=payload,
                    )
                )
                qualifiers = AssertionQualifiers(
                    polarity=curated.polarity,
                    population=curated.population,
                    temporal_context=curated.temporal_context,
                    clinical_context=curated.clinical_context,
                    severity=curated.severity,
                    location=curated.location,
                    laterality=curated.laterality,
                    evidence_type=curated.evidence_type,
                    evidence_level=curated.evidence_level,
                )
                object_value = ConceptObject(concept_id=object_id)
                source_assertion_id = make_source_assertion_id(
                    source.source_id,
                    source.release,
                    [canonical_artifact.sha256],
                    curated.record_locator,
                    ordinal,
                )
                source_assertions.append(
                    SourceAssertion(
                        source_assertion_id=source_assertion_id,
                        subject_concept_id=subject_id,
                        relation=curated.relation,
                        object=object_value,
                        qualifiers=qualifiers,
                        source_release_id=release_id,
                        source_record_id=source_record_id,
                        artifact_ids=[canonical_artifact.artifact_id],
                        record_ordinal=ordinal,
                        raw_value=payload,
                    )
                )
                canonical_id = make_canonical_assertion_id(
                    subject_id, curated.relation, object_value, qualifiers
                )
                canonical_assertions.setdefault(
                    canonical_id,
                    CanonicalAssertion(
                        canonical_assertion_id=canonical_id,
                        subject_concept_id=subject_id,
                        relation=curated.relation,
                        object=object_value,
                        qualifiers=qualifiers,
                    ),
                )
                derivations.append(
                    AssertionDerivation(
                        derivation_id=stable_id(
                            "assertion_derivation", source_assertion_id, canonical_id
                        ),
                        source_assertion_id=source_assertion_id,
                        canonical_assertion_id=canonical_id,
                        rule_id="curated_assertion_jsonl",
                        rule_version="1",
                        transformations=["code_resolution", "qualifier_normalization"],
                    )
                )
                _add_family(families, curated, release_id, source_assertion_id)

    dependencies = _dependencies(registry)
    evidence_families = [
        EvidenceFamily(
            evidence_family_id=family_id,
            source_release_ids=sorted(data["source_release_ids"]),
            source_assertion_ids=sorted(data["source_assertion_ids"]),
            dependency_type=data["dependency_type"],
            primary_reference=data["primary_reference"],
        )
        for family_id, data in sorted(families.items())
    ]
    return CanonicalKnowledgeV2(
        source_releases=source_releases,
        source_artifacts=source_artifacts,
        source_records=records,
        concepts=list(concepts.values()),
        designations=designations,
        external_identifiers=identifiers,
        hierarchy_edges=edges,
        concept_mappings=[],
        source_assertions=source_assertions,
        canonical_assertions=list(canonical_assertions.values()),
        assertion_derivations=derivations,
        evidence_families=evidence_families,
        source_dependencies=dependencies,
    )


def _import_rf2(
    root: Path,
    source: SourcePackageV2,
    artifacts: dict[tuple[str, str], SourceArtifactV2],
) -> tuple[
    list[ConceptV2],
    list[DesignationV2],
    list[ExternalIdentifierV2],
    list[HierarchyEdgeV2],
    dict[str, str],
]:
    del artifacts
    release_id = _release_id(source)
    concept_artifact = _one_artifact(source, "rf2-concepts-tsv")
    description_artifact = _one_artifact(source, "rf2-descriptions-tsv")
    relationship_artifact = _one_artifact(source, "rf2-relationships-tsv")
    concept_rows = _tsv(
        _raw_path(root, source, concept_artifact),
        {"id", "active"},
    )
    description_rows = _tsv(
        _raw_path(root, source, description_artifact),
        {"id", "active", "conceptId", "languageCode", "typeId", "term"},
    )
    relationship_rows = _tsv(
        _raw_path(root, source, relationship_artifact),
        {"id", "active", "sourceId", "destinationId", "typeId"},
    )
    active_codes = {row["id"] for row in concept_rows if _active(row)}
    descriptions_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in description_rows:
        if _active(row) and row["conceptId"] in active_codes:
            descriptions_by_code[row["conceptId"]].append(row)
    concepts: list[ConceptV2] = []
    designations: list[DesignationV2] = []
    identifiers: list[ExternalIdentifierV2] = []
    code_index: dict[str, str] = {}
    for code in sorted(active_codes):
        descriptions = descriptions_by_code.get(code, [])
        fsn = next((row for row in descriptions if row["typeId"] in RF2_FSN), None)
        if fsn is None:
            raise LatrosError(f"Active RF2 concept lacks an active FSN: {code}")
        kind = _semantic_kind(fsn["term"])
        concept_id = stable_id("concept", source.code_system, code)
        code_index[code] = concept_id
        concepts.append(
            ConceptV2(
                concept_id=concept_id,
                kind=kind,
                primary_code=code,
                source_release_id=release_id,
            )
        )
        identifiers.append(
            ExternalIdentifierV2(
                external_identifier_id=stable_id(
                    "external_identifier", concept_id, source.code_system, code
                ),
                concept_id=concept_id,
                system=source.code_system,
                code=code,
                relation="identity",
                source_release_id=release_id,
            )
        )
        for row in sorted(descriptions, key=lambda item: item["id"]):
            designations.append(
                DesignationV2(
                    designation_id=stable_id("designation", release_id, row["id"]),
                    concept_id=concept_id,
                    language=row["languageCode"],
                    text=row["term"],
                    scope="fully_specified_name" if row["typeId"] in RF2_FSN else "synonym",
                    source_release_id=release_id,
                )
            )
    edges: list[HierarchyEdgeV2] = []
    for row in relationship_rows:
        if not _active(row) or row["typeId"] not in RF2_IS_A:
            continue
        if row["sourceId"] not in code_index or row["destinationId"] not in code_index:
            raise LatrosError("RF2 is-a relationship references a concept outside the subset")
        edges.append(
            HierarchyEdgeV2(
                hierarchy_edge_id=stable_id("hierarchy_edge", release_id, row["id"]),
                child_concept_id=code_index[row["sourceId"]],
                parent_concept_id=code_index[row["destinationId"]],
                source_release_id=release_id,
            )
        )
    return concepts, designations, identifiers, edges, code_index


def _source_release(source: SourcePackageV2) -> SourceReleaseV2:
    return SourceReleaseV2(
        source_release_id=_release_id(source),
        source_id=source.source_id,
        release=source.release,
        release_date=source.release_date.isoformat() if source.release_date else None,
        license_name=source.license.name,
        license_url=source.license.url,
        attribution=source.license.attribution,
        redistribution=source.license.redistribution,
        roles=source.roles,
    )


def _source_artifact(release_id: str, artifact: RegistryArtifactV2) -> SourceArtifactV2:
    return SourceArtifactV2(
        artifact_id=stable_id("artifact", release_id, artifact.filename),
        source_release_id=release_id,
        filename=artifact.filename,
        sha256=artifact.sha256,
        format=artifact.format,
        language=artifact.language,
        source_url=artifact.source_url,
    )


def _dependencies(registry: RegistryV2) -> list[SourceDependency]:
    result: list[SourceDependency] = []
    for source in registry.sources:
        release_id = _release_id(source)
        dependencies = source.dependencies or [
            RegistryDependencyV2(
                upstream_reference=release_id,
                dependency_type="primary",
                evidence="Source declares itself primary",
            )
        ]
        for dependency in dependencies:
            result.append(
                SourceDependency(
                    source_dependency_id=stable_id(
                        "source_dependency", release_id, dependency.upstream_reference
                    ),
                    source_release_id=release_id,
                    upstream_reference=dependency.upstream_reference,
                    dependency_type=dependency.dependency_type,
                    evidence=dependency.evidence,
                )
            )
    return result


def _add_family(
    families: dict[str, dict[str, Any]],
    curated: CuratedAssertionRecord,
    release_id: str,
    assertion_id: str,
) -> None:
    definition = {
        "dependency_type": curated.evidence_family.dependency_type,
        "primary_reference": curated.evidence_family.primary_reference,
    }
    existing = families.setdefault(
        curated.evidence_family.family_id,
        {**definition, "source_release_ids": set(), "source_assertion_ids": set()},
    )
    if any(existing[key] != value for key, value in definition.items()):
        raise LatrosError("Conflicting definitions for an evidence family")
    existing["source_release_ids"].add(release_id)
    existing["source_assertion_ids"].add(assertion_id)


def _release_id(source: SourcePackageV2) -> str:
    return f"{source.source_id}:{source.release}"


def _raw_path(root: Path, source: SourcePackageV2, artifact: RegistryArtifactV2) -> Path:
    return root / "data/raw" / source.source_id / source.release / artifact.filename


def _one_artifact(source: SourcePackageV2, format_name: str) -> RegistryArtifactV2:
    matches = [artifact for artifact in source.artifacts if artifact.format == format_name]
    if len(matches) != 1:
        raise LatrosError(f"RF2 source requires exactly one {format_name} artifact")
    return matches[0]


def _tsv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise LatrosError(f"RF2 fixture is missing columns {sorted(missing)}: {path}")
        rows = [dict(row) for row in reader]
    identifiers = [row["id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise LatrosError(f"Duplicate RF2 row identifier: {path}")
    return rows


def _jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    result: list[tuple[int, dict[str, Any]]] = []
    for ordinal, line in enumerate(path.read_bytes().splitlines()):
        if not line.strip():
            continue
        payload = orjson.loads(line)
        if not isinstance(payload, dict):
            raise LatrosError(f"Curated assertion line {ordinal + 1} must be an object")
        result.append((ordinal, payload))
    return result


def _active(row: dict[str, str]) -> bool:
    if row["active"] not in {"0", "1"}:
        raise LatrosError(f"Invalid RF2 active flag: {row['active']!r}")
    return row["active"] == "1"


def _semantic_kind(term: str) -> str:
    lowered = term.lower()
    mapping = {
        "(disorder)": "condition",
        "(finding)": "finding",
        "(observable entity)": "finding",
    }
    matches = [kind for suffix, kind in mapping.items() if lowered.endswith(suffix)]
    if len(matches) != 1:
        raise LatrosError(f"Unsupported or ambiguous RF2 semantic tag: {term}")
    return matches[0]


def _resolve_code(index: dict[tuple[str, str], str], code: CuratedCode) -> str:
    try:
        return index[(code.system, code.code)]
    except KeyError as exc:
        raise LatrosError(f"Curated assertion references an unknown code: {code}") from exc
