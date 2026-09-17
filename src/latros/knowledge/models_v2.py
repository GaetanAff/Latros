"""Canonical knowledge contracts independent from source-specific import formats."""

from typing import Annotated, Any, Literal, Self, TypeAlias

import orjson
from pydantic import Field, model_validator

from latros.common import stable_id
from latros.knowledge.frequency import Frequency
from latros.sources.registry import Contract

RelationType = Literal[
    "has_symptom",
    "has_sign",
    "has_risk_factor",
    "has_lab_finding",
    "has_exam_finding",
    "has_imaging_finding",
    "typical_age",
    "typical_sex",
    "has_complication",
]
MappingRelation = Literal["exact", "equivalent", "broader", "narrower", "related", "unresolved"]
DependencyType = Literal["primary", "derived_from", "republication", "shared_upstream", "unknown"]


class SourceReleaseV2(Contract):
    source_release_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    release: str = Field(min_length=1)
    release_date: str | None = None
    license_name: str = Field(min_length=1)
    license_url: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    redistribution: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=list)


class SourceArtifactV2(Contract):
    artifact_id: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: str = Field(min_length=1)
    language: str | None = None
    source_url: str = Field(min_length=1)


class SourceRecordV2(Contract):
    source_record_id: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    artifact_ids: list[str] = Field(min_length=1)
    record_locator: str = Field(min_length=1)
    raw_value: dict[str, Any]


class ConceptV2(Contract):
    concept_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    status: Literal["active", "obsolete"] = "active"
    primary_code: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)


class DesignationV2(Contract):
    designation_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    text: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)


class ExternalIdentifierV2(Contract):
    external_identifier_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)


class HierarchyEdgeV2(Contract):
    hierarchy_edge_id: str = Field(min_length=1)
    child_concept_id: str = Field(min_length=1)
    parent_concept_id: str = Field(min_length=1)
    relation: Literal["is_a"] = "is_a"
    source_release_id: str = Field(min_length=1)


class ConceptMappingV2(Contract):
    mapping_id: str = Field(min_length=1)
    source_concept_id: str = Field(min_length=1)
    target_concept_id: str | None = Field(default=None, min_length=1)
    target_system: str = Field(min_length=1)
    target_code: str = Field(min_length=1)
    direction: Literal["source_to_target", "bidirectional"]
    relation: MappingRelation
    original_relation: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    evidence: dict[str, Any]
    resolution_status: Literal["resolved", "ambiguous", "unresolved"]

    @model_validator(mode="after")
    def resolution_matches_target(self) -> Self:
        if (self.resolution_status == "resolved") != (self.target_concept_id is not None):
            raise ValueError("Only resolved mappings may reference a target concept")
        return self


class ConceptObject(Contract):
    kind: Literal["concept"] = "concept"
    concept_id: str = Field(min_length=1)


class CodedObject(Contract):
    kind: Literal["coded"] = "coded"
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)


class QuantityObject(Contract):
    kind: Literal["quantity"] = "quantity"
    value: float
    unit_system: str = Field(min_length=1)
    unit_code: str = Field(min_length=1)


class IntervalObject(Contract):
    kind: Literal["interval"] = "interval"
    low: float
    high: float
    unit_system: str = Field(min_length=1)
    unit_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.low > self.high:
            raise ValueError("Assertion interval low must not exceed high")
        return self


AssertionObject: TypeAlias = Annotated[
    ConceptObject | CodedObject | QuantityObject | IntervalObject,
    Field(discriminator="kind"),
]


class AssertionQualifiers(Contract):
    polarity: Literal["present", "excluded", "unknown"] = "present"
    frequency: Frequency | None = None
    population: list[str] = Field(default_factory=list)
    age: IntervalObject | None = None
    sex: Literal["male", "female", "intersex", "any", "unknown"] | None = None
    temporal_context: str | None = Field(default=None, min_length=1)
    clinical_context: str | None = Field(default=None, min_length=1)
    evidence_type: str | None = Field(default=None, min_length=1)
    evidence_level: str | None = Field(default=None, min_length=1)


class SourceAssertion(Contract):
    source_assertion_id: str = Field(min_length=1)
    subject_concept_id: str = Field(min_length=1)
    relation: RelationType
    object: AssertionObject
    qualifiers: AssertionQualifiers = Field(default_factory=AssertionQualifiers)
    source_release_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    artifact_ids: list[str] = Field(min_length=1)
    record_ordinal: int = Field(ge=0)
    raw_value: dict[str, Any]


class CanonicalAssertion(Contract):
    canonical_assertion_id: str = Field(min_length=1)
    schema_version: Literal[2] = 2
    subject_concept_id: str = Field(min_length=1)
    relation: RelationType
    object: AssertionObject
    qualifiers: AssertionQualifiers = Field(default_factory=AssertionQualifiers)


class AssertionDerivation(Contract):
    derivation_id: str = Field(min_length=1)
    source_assertion_id: str = Field(min_length=1)
    canonical_assertion_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    transformations: list[str] = Field(default_factory=list)


class EvidenceFamily(Contract):
    evidence_family_id: str = Field(min_length=1)
    source_release_ids: list[str] = Field(min_length=1)
    source_assertion_ids: list[str] = Field(min_length=1)
    dependency_type: DependencyType
    primary_reference: str = Field(min_length=1)


class SourceDependency(Contract):
    source_dependency_id: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    upstream_reference: str = Field(min_length=1)
    dependency_type: DependencyType
    evidence: str = Field(min_length=1)


class CanonicalKnowledgeV2(Contract):
    schema_version: Literal[2] = 2
    source_releases: list[SourceReleaseV2] = Field(default_factory=list)
    source_artifacts: list[SourceArtifactV2] = Field(default_factory=list)
    source_records: list[SourceRecordV2] = Field(default_factory=list)
    concepts: list[ConceptV2] = Field(default_factory=list)
    designations: list[DesignationV2] = Field(default_factory=list)
    external_identifiers: list[ExternalIdentifierV2] = Field(default_factory=list)
    hierarchy_edges: list[HierarchyEdgeV2] = Field(default_factory=list)
    concept_mappings: list[ConceptMappingV2] = Field(default_factory=list)
    source_assertions: list[SourceAssertion] = Field(default_factory=list)
    canonical_assertions: list[CanonicalAssertion] = Field(default_factory=list)
    assertion_derivations: list[AssertionDerivation] = Field(default_factory=list)
    evidence_families: list[EvidenceFamily] = Field(default_factory=list)
    source_dependencies: list[SourceDependency] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_exist(self) -> Self:
        releases = _ids(self.source_releases, "source_release_id", "source release")
        artifacts = _ids(self.source_artifacts, "artifact_id", "source artifact")
        records = _ids(self.source_records, "source_record_id", "source record")
        concepts = _ids(self.concepts, "concept_id", "concept")
        _ids(self.designations, "designation_id", "designation")
        _ids(self.external_identifiers, "external_identifier_id", "external identifier")
        _ids(self.hierarchy_edges, "hierarchy_edge_id", "hierarchy edge")
        _ids(self.concept_mappings, "mapping_id", "concept mapping")
        source_assertions = _ids(self.source_assertions, "source_assertion_id", "source assertion")
        canonical_assertions = _ids(
            self.canonical_assertions, "canonical_assertion_id", "canonical assertion"
        )
        _ids(self.assertion_derivations, "derivation_id", "assertion derivation")
        _ids(self.evidence_families, "evidence_family_id", "evidence family")
        _ids(self.source_dependencies, "source_dependency_id", "source dependency")
        for artifact in self.source_artifacts:
            _require(artifact.source_release_id, releases, "artifact source release")
        for record in self.source_records:
            _require(record.source_release_id, releases, "record source release")
            for artifact_id in record.artifact_ids:
                _require(artifact_id, artifacts, "record artifact")
        for concept in self.concepts:
            _require(concept.source_release_id, releases, "concept source release")
        for designation in self.designations:
            _require(designation.concept_id, concepts, "designation concept")
            _require(designation.source_release_id, releases, "designation source release")
        for identifier in self.external_identifiers:
            _require(identifier.concept_id, concepts, "external identifier concept")
            _require(identifier.source_release_id, releases, "identifier source release")
        for edge in self.hierarchy_edges:
            _require(edge.child_concept_id, concepts, "hierarchy child")
            _require(edge.parent_concept_id, concepts, "hierarchy parent")
            _require(edge.source_release_id, releases, "hierarchy source release")
        for mapping in self.concept_mappings:
            _require(mapping.source_concept_id, concepts, "mapping source concept")
            if mapping.target_concept_id is not None:
                _require(mapping.target_concept_id, concepts, "mapping target concept")
            _require(mapping.source_release_id, releases, "mapping source release")
        for source_assertion in self.source_assertions:
            _require(source_assertion.subject_concept_id, concepts, "assertion subject")
            _require(source_assertion.source_release_id, releases, "assertion source release")
            _require(source_assertion.source_record_id, records, "assertion source record")
            for artifact_id in source_assertion.artifact_ids:
                _require(artifact_id, artifacts, "assertion artifact")
            _require_object(source_assertion.object, concepts)
        for canonical_assertion in self.canonical_assertions:
            _require(
                canonical_assertion.subject_concept_id,
                concepts,
                "canonical assertion subject",
            )
            _require_object(canonical_assertion.object, concepts)
        for derivation in self.assertion_derivations:
            _require(derivation.source_assertion_id, source_assertions, "derivation source")
            _require(derivation.canonical_assertion_id, canonical_assertions, "derivation target")
        for family in self.evidence_families:
            for release_id in family.source_release_ids:
                _require(release_id, releases, "evidence family source release")
            for assertion_id in family.source_assertion_ids:
                _require(assertion_id, source_assertions, "evidence family assertion")
        for dependency in self.source_dependencies:
            _require(dependency.source_release_id, releases, "dependency source release")
        return self


CANONICAL_TABLES_V2: dict[str, str] = {
    "source_release": "SourceReleaseV2",
    "source_artifact": "SourceArtifactV2",
    "source_record": "SourceRecordV2",
    "concept": "ConceptV2",
    "designation": "DesignationV2",
    "external_identifier": "ExternalIdentifierV2",
    "hierarchy_edge": "HierarchyEdgeV2",
    "concept_mapping": "ConceptMappingV2",
    "source_assertion": "SourceAssertion",
    "canonical_assertion": "CanonicalAssertion",
    "assertion_derivation": "AssertionDerivation",
    "evidence_family": "EvidenceFamily",
    "source_dependency": "SourceDependency",
}


def make_source_assertion_id(
    source_id: str,
    release: str,
    artifact_hashes: list[str],
    record_locator: str,
    ordinal: int,
) -> str:
    return stable_id(
        "source_assertion",
        source_id,
        release,
        _canonical_text(sorted(artifact_hashes)),
        record_locator,
        str(ordinal),
    )


def make_canonical_assertion_id(
    subject_concept_id: str,
    relation: RelationType,
    object_value: AssertionObject,
    qualifiers: AssertionQualifiers,
) -> str:
    signature = {
        "schema_version": 2,
        "subject_concept_id": subject_concept_id,
        "relation": relation,
        "object": object_value.model_dump(mode="json"),
        "qualifiers": qualifiers.model_dump(mode="json"),
    }
    return stable_id("canonical_assertion", _canonical_text(signature))


def aggregatable_evidence_family_ids(
    knowledge: CanonicalKnowledgeV2,
    *,
    allow_unknown_sources: set[str] | None = None,
) -> set[str]:
    allowed = allow_unknown_sources or set()
    unknown = {
        dependency.source_release_id
        for dependency in knowledge.source_dependencies
        if dependency.dependency_type == "unknown" and dependency.source_release_id not in allowed
    }
    return {
        family.evidence_family_id
        for family in knowledge.evidence_families
        if family.dependency_type != "unknown"
        and not unknown.intersection(family.source_release_ids)
    }


def _canonical_text(value: Any) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode()


def _ids(items: list[Any], field: str, label: str) -> set[str]:
    result: set[str] = set()
    for item in items:
        identifier = str(getattr(item, field))
        if identifier in result:
            raise ValueError(f"Duplicate {label}: {identifier}")
        result.add(identifier)
    return result


def _require(identifier: str, values: set[str], label: str) -> None:
    if identifier not in values:
        raise ValueError(f"Unknown {label}: {identifier}")


def _require_object(value: AssertionObject, concepts: set[str]) -> None:
    if isinstance(value, ConceptObject):
        _require(value.concept_id, concepts, "assertion object concept")
