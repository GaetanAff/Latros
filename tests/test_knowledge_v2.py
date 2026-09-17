from copy import deepcopy

from latros.common import stable_id
from latros.knowledge.adapter_v1 import adapt_v1_tables
from latros.knowledge.models_v2 import (
    AssertionQualifiers,
    CanonicalKnowledgeV2,
    ConceptObject,
    SourceDependency,
    aggregatable_evidence_family_ids,
    make_canonical_assertion_id,
    make_source_assertion_id,
)
from latros.knowledge.store import read_tables


def test_v1_adapter_preserves_sources_and_keeps_mappings_separate(built) -> None:
    root, _ = built
    manifest, tables = read_tables(root, "test")

    projected = adapt_v1_tables(manifest, tables)

    assert projected.schema_version == 2
    assert len(projected.source_assertions) == len(tables["disease_phenotype_assertion"])
    assert len(projected.concept_mappings) == len(tables["mapping"])
    assert {item.relation for item in projected.source_assertions} == {"has_sign"}
    assert any(item.relation == "exact" for item in projected.concept_mappings)
    assert any(item.relation == "related" for item in projected.concept_mappings)


def test_bilingual_artifacts_are_one_assertion_and_one_evidence_family(built) -> None:
    root, _ = built
    manifest, tables = read_tables(root, "test")

    projected = adapt_v1_tables(manifest, tables)

    assert all(len(item.artifact_ids) == 2 for item in projected.source_assertions)
    assert len(projected.evidence_families) == len(projected.source_assertions)
    assert all(len(item.source_assertion_ids) == 1 for item in projected.evidence_families)


def test_duplicate_source_records_remain_but_share_a_canonical_assertion(built) -> None:
    root, _ = built
    manifest, tables = read_tables(root, "test")
    duplicated = deepcopy(tables)
    copy = deepcopy(duplicated["disease_phenotype_assertion"][0])
    copy["id"] = "invented-duplicate-row"
    copy["source_record_id"] = "invented-duplicate-record"
    duplicated["disease_phenotype_assertion"].append(copy)

    projected = adapt_v1_tables(manifest, duplicated)
    derivation_targets = [item.canonical_assertion_id for item in projected.assertion_derivations]

    assert len(projected.source_assertions) == len(tables["disease_phenotype_assertion"]) + 1
    assert len(set(derivation_targets)) < len(derivation_targets)
    assert len(projected.evidence_families) < len(projected.source_assertions)
    assert any(len(item.source_assertion_ids) == 2 for item in projected.evidence_families)


def test_assertion_identity_has_distinct_source_and_semantic_scopes() -> None:
    object_value = ConceptObject(concept_id="concept:sign")
    qualifiers = AssertionQualifiers(polarity="present")

    canonical = make_canonical_assertion_id("concept:disease", "has_sign", object_value, qualifiers)
    same_canonical = make_canonical_assertion_id(
        "concept:disease", "has_sign", object_value, qualifiers
    )
    first_source = make_source_assertion_id("source", "1", ["a" * 64, "b" * 64], "record-1", 0)
    reordered_artifacts = make_source_assertion_id(
        "source", "1", ["b" * 64, "a" * 64], "record-1", 0
    )
    other_record = make_source_assertion_id("source", "1", ["a" * 64, "b" * 64], "record-2", 0)

    assert canonical == same_canonical
    assert first_source == reordered_artifacts
    assert first_source != other_record


def test_unknown_source_dependency_is_visible_but_not_aggregatable(built) -> None:
    root, _ = built
    manifest, tables = read_tables(root, "test")
    projected = adapt_v1_tables(manifest, tables)
    unknown = SourceDependency(
        source_dependency_id=stable_id("source_dependency", "orphadata:test-v1", "unknown"),
        source_release_id="orphadata:test-v1",
        upstream_reference="unresolved-upstream",
        dependency_type="unknown",
        evidence="synthetic unresolved dependency",
    )
    payload = projected.model_dump(mode="json")
    payload["source_dependencies"].append(unknown.model_dump(mode="json"))
    with_unknown = CanonicalKnowledgeV2.model_validate(payload)

    assert aggregatable_evidence_family_ids(with_unknown) == set()
    assert aggregatable_evidence_family_ids(
        with_unknown, allow_unknown_sources={"orphadata:test-v1"}
    ) == {item.evidence_family_id for item in with_unknown.evidence_families}


def test_canonical_assertion_ids_do_not_depend_on_designations_or_provenance() -> None:
    object_value = ConceptObject(concept_id="concept:sign")
    qualifiers = AssertionQualifiers(polarity="present", clinical_context="ambulatory")

    identifier = make_canonical_assertion_id(
        "concept:disease", "has_sign", object_value, qualifiers
    )

    assert identifier.startswith("canonical_assertion:")
