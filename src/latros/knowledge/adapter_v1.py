"""Read-only projection of a canonical_v1 snapshot into the v2 contracts."""

from typing import Any

import orjson

from latros.common import stable_id
from latros.knowledge.frequency import Frequency
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
    HierarchyEdgeV2,
    MappingRelation,
    SourceArtifactV2,
    SourceAssertion,
    SourceDependency,
    SourceRecordV2,
    SourceReleaseV2,
    make_canonical_assertion_id,
    make_source_assertion_id,
)


def adapt_v1_tables(
    manifest: dict[str, Any], tables: dict[str, list[dict[str, Any]]]
) -> CanonicalKnowledgeV2:
    """Project v1 data without modifying or republishing its immutable snapshot."""
    if manifest.get("schema_version") != 1:
        raise ValueError("The legacy adapter requires a schema_version 1 manifest")
    releases, artifacts, artifact_lookup = _sources(manifest)
    concepts = [
        ConceptV2(
            concept_id=row["id"],
            kind=row["kind"],
            status="obsolete" if row["obsolete"] else "active",
            primary_code=row["external_id"],
            source_release_id=row["source_release_id"],
        )
        for row in tables["concept"]
    ]
    concept_by_code = {item.primary_code: item.concept_id for item in concepts}
    designations = [
        DesignationV2(
            designation_id=row["id"],
            concept_id=row["concept_id"],
            language=row["language"],
            text=row["text"],
            scope=row["scope"],
            source_release_id=row["source_release_id"],
        )
        for row in tables["term"]
    ]
    identifiers = [
        ExternalIdentifierV2(
            external_identifier_id=row["id"],
            concept_id=row["concept_id"],
            system=_system(row["identifier"]),
            code=row["identifier"],
            relation=row["relation"],
            source_release_id=row["source_release_id"],
        )
        for row in tables["external_identifier"]
    ]
    hierarchy = [
        HierarchyEdgeV2(
            hierarchy_edge_id=row["id"],
            child_concept_id=row["child_id"],
            parent_concept_id=row["parent_id"],
            source_release_id=row["source_release_id"],
        )
        for row in tables["hierarchy_edge"]
    ]
    mappings = [_mapping(row, concept_by_code) for row in tables["mapping"]]
    records: list[SourceRecordV2] = []
    source_assertions: list[SourceAssertion] = []
    canonical_by_id: dict[str, CanonicalAssertion] = {}
    derivations: list[AssertionDerivation] = []
    family_members: dict[str, list[str]] = {}
    assertion_releases: dict[str, str] = {}
    release_metadata = {release.source_release_id: release for release in releases}
    for row in tables["disease_phenotype_assertion"]:
        provenance: list[dict[str, Any]] = orjson.loads(row["provenance_json"])
        artifact_ids = sorted(
            {artifact_lookup[(row["source_release_id"], item["artifact"])] for item in provenance}
        )
        record_id = stable_id("source_record", row["source_release_id"], row["source_record_id"])
        records.append(
            SourceRecordV2(
                source_record_id=record_id,
                source_release_id=row["source_release_id"],
                artifact_ids=artifact_ids,
                record_locator=row["source_record_id"],
                raw_value={
                    "legacy_assertion_id": row["id"],
                    "source_phenotype_id": row["source_phenotype_id"],
                    "languages": orjson.loads(row["languages_json"]),
                    "provenance": provenance,
                },
            )
        )
        release = release_metadata[row["source_release_id"]]
        artifact_hashes = sorted(item["sha256"] for item in provenance)
        source_assertion_id = make_source_assertion_id(
            release.source_id,
            release.release,
            artifact_hashes,
            row["source_record_id"],
            0,
        )
        object_value = ConceptObject(concept_id=row["phenotype_id"])
        qualifiers = AssertionQualifiers(
            polarity=row["polarity"],
            frequency=Frequency.model_validate_json(row["frequency_json"]),
        )
        source_assertion = SourceAssertion(
            source_assertion_id=source_assertion_id,
            subject_concept_id=row["disease_id"],
            relation="has_sign",
            object=object_value,
            qualifiers=qualifiers,
            source_release_id=row["source_release_id"],
            source_record_id=record_id,
            artifact_ids=artifact_ids,
            record_ordinal=0,
            raw_value={
                "legacy_assertion_id": row["id"],
                "source_phenotype_id": row["source_phenotype_id"],
                "languages": orjson.loads(row["languages_json"]),
                "provenance": provenance,
            },
        )
        source_assertions.append(source_assertion)
        assertion_releases[source_assertion_id] = source_assertion.source_release_id
        canonical_id = make_canonical_assertion_id(
            source_assertion.subject_concept_id,
            source_assertion.relation,
            source_assertion.object,
            source_assertion.qualifiers,
        )
        canonical_by_id.setdefault(
            canonical_id,
            CanonicalAssertion(
                canonical_assertion_id=canonical_id,
                subject_concept_id=source_assertion.subject_concept_id,
                relation=source_assertion.relation,
                object=source_assertion.object,
                qualifiers=source_assertion.qualifiers,
            ),
        )
        derivations.append(
            AssertionDerivation(
                derivation_id=stable_id("derivation", source_assertion_id, canonical_id),
                source_assertion_id=source_assertion_id,
                canonical_assertion_id=canonical_id,
                rule_id="canonical_v1_orphadata_projection",
                rule_version="1",
                transformations=["preserve_frequency", "coalesced_bilingual_artifacts"],
            )
        )
        family_id = stable_id("evidence_family", row["source_release_id"], canonical_id)
        family_members.setdefault(family_id, []).append(source_assertion_id)
    dependencies = _dependencies(manifest)
    families = [
        EvidenceFamily(
            evidence_family_id=family_id,
            source_release_ids=[assertion_releases[members[0]]],
            source_assertion_ids=sorted(members),
            dependency_type="primary",
            primary_reference=family_id,
        )
        for family_id, members in sorted(family_members.items())
    ]
    return CanonicalKnowledgeV2(
        source_releases=releases,
        source_artifacts=artifacts,
        source_records=records,
        concepts=concepts,
        designations=designations,
        external_identifiers=identifiers,
        hierarchy_edges=hierarchy,
        concept_mappings=mappings,
        source_assertions=source_assertions,
        canonical_assertions=sorted(
            canonical_by_id.values(), key=lambda assertion: assertion.canonical_assertion_id
        ),
        assertion_derivations=derivations,
        evidence_families=families,
        source_dependencies=dependencies,
    )


def _sources(
    manifest: dict[str, Any],
) -> tuple[list[SourceReleaseV2], list[SourceArtifactV2], dict[tuple[str, str], str]]:
    releases: list[SourceReleaseV2] = []
    artifacts: list[SourceArtifactV2] = []
    lookup: dict[tuple[str, str], str] = {}
    for source in manifest["sources"]:
        source_release_id = f"{source['id']}:{source['release']}"
        license_value = source["license"]
        releases.append(
            SourceReleaseV2(
                source_release_id=source_release_id,
                source_id=source["id"],
                release=source["release"],
                release_date=source.get("release_date"),
                license_name=license_value["name"],
                license_url=license_value["url"],
                attribution=license_value["attribution"],
                redistribution=license_value["redistribution"],
                roles=source["role"],
            )
        )
        for artifact in source["artifacts"]:
            artifact_id = stable_id(
                "source_artifact", source_release_id, artifact["filename"], artifact["sha256"]
            )
            lookup[source_release_id, artifact["filename"]] = artifact_id
            artifacts.append(
                SourceArtifactV2(
                    artifact_id=artifact_id,
                    source_release_id=source_release_id,
                    filename=artifact["filename"],
                    sha256=artifact["sha256"],
                    format=artifact["format"],
                    language=artifact.get("language"),
                    source_url=artifact["url"],
                )
            )
    return releases, artifacts, lookup


def _mapping(row: dict[str, Any], concepts: dict[str, str]) -> ConceptMappingV2:
    target = row["target_external_id"]
    target_id = concepts.get(target)
    original = row["relation"]
    relation: MappingRelation = "exact" if original == "exactMatch" else "related"
    if target_id is None:
        relation = "unresolved"
    return ConceptMappingV2(
        mapping_id=row["id"],
        source_concept_id=row["subject_id"],
        target_concept_id=target_id,
        target_system=_system(target),
        target_code=target,
        direction="bidirectional" if relation == "exact" else "source_to_target",
        relation=relation,
        original_relation=original,
        source_release_id=row["source_release_id"],
        evidence=orjson.loads(row["evidence_json"]),
        resolution_status="resolved" if target_id is not None else "unresolved",
    )


def _dependencies(manifest: dict[str, Any]) -> list[SourceDependency]:
    result: list[SourceDependency] = []
    for source in manifest["sources"]:
        source_release_id = f"{source['id']}:{source['release']}"
        upstream = source.get("upstream_dependencies", [])
        if not upstream:
            result.append(
                SourceDependency(
                    source_dependency_id=stable_id("source_dependency", source_release_id, "self"),
                    source_release_id=source_release_id,
                    upstream_reference=source_release_id,
                    dependency_type="primary",
                    evidence="canonical_v1 source manifest",
                )
            )
        for reference in upstream:
            result.append(
                SourceDependency(
                    source_dependency_id=stable_id(
                        "source_dependency", source_release_id, reference
                    ),
                    source_release_id=source_release_id,
                    upstream_reference=reference,
                    dependency_type="derived_from",
                    evidence="canonical_v1 upstream_dependencies",
                )
            )
    return result


def _system(code: str) -> str:
    prefix = code.split(":", 1)[0]
    return {
        "HP": "http://purl.obolibrary.org/obo/hp.owl",
        "MONDO": "http://purl.obolibrary.org/obo/mondo.owl",
        "ORPHA": "https://www.orpha.net",
    }.get(prefix, f"urn:latros:legacy-code-system:{prefix}")
