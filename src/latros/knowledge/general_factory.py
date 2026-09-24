"""Deterministic, fully local factory for the first sovereign general snapshot."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

import orjson

from latros.common import LatrosError, stable_id
from latros.knowledge.adapter_v1 import adapt_v1_tables
from latros.knowledge.candidates import (
    CandidateAssertion,
    ExtractionProvenance,
    MappingProposal,
    make_candidate_assertion_id,
)
from latros.knowledge.frequency import Frequency
from latros.knowledge.importers import import_registry
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.medlineplus import MedlinePlusTopicRecord, parse_medlineplus_topics
from latros.knowledge.mesh import parse_mesh_descriptors
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
    SourceArtifactV2,
    SourceAssertion,
    SourceDependency,
    SourceRecordV2,
    SourceReleaseV2,
    make_canonical_assertion_id,
    make_source_assertion_id,
)
from latros.knowledge.monarch import (
    MonarchDiseasePhenotypeRecord,
    iter_monarch_disease_phenotypes,
)
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.sources.registry import load_registry
from latros.sources.registry_v2 import RegistryArtifactV2, RegistryV2, SourcePackageV2

GENERAL_SNAPSHOT_ID = "v0.7.0-general-dev-unreviewed"
GENERAL_PROFILE_ID = "general_v1-general-unreviewed"
EXTRACTOR_ID = "latros.medlineplus.exact-term"
EXTRACTOR_VERSION = "1"
T = TypeVar("T")


def build_general_snapshot(
    root: Path,
    registry: RegistryV2,
    snapshot: str,
    *,
    allow_unreviewed_research_data: bool,
) -> KnowledgeSnapshotManifestV2:
    if snapshot != GENERAL_SNAPSHOT_ID:
        raise LatrosError(f"General factory requires snapshot {GENERAL_SNAPSHOT_ID}")
    if not allow_unreviewed_research_data:
        raise LatrosError("General DEV snapshot requires the explicit unreviewed research override")
    required = {"hpo", "mondo", "doid", "orphadata", "mesh", "medlineplus", "monarch"}
    if {source.source_id for source in registry.sources} != required:
        raise LatrosError(f"General registry must pin exactly: {sorted(required)}")

    knowledge, candidates, metrics = import_general_knowledge(root, registry)
    candidate_path = root / "data/staging/general" / snapshot / "candidate_assertions.jsonl"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    with candidate_path.open("wb") as handle:
        for candidate in sorted(candidates, key=lambda item: item.candidate_assertion_id):
            handle.write(
                orjson.dumps(candidate.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS) + b"\n"
            )
    unreviewed_mappings = sorted(mapping.mapping_id for mapping in knowledge.concept_mappings)
    if not unreviewed_mappings:
        raise LatrosError("General DEV snapshot unexpectedly contains no mapping candidates")
    research_metadata = {
        "validation_status": "unreviewed",
        "intended_use": "local_research_only",
        "clinical_validation": False,
        "human_review_complete": False,
        "publishable": False,
        "research_override_used": True,
        "unreviewed_assertion_ids": sorted(
            candidate.candidate_assertion_id for candidate in candidates
        ),
        "unreviewed_mapping_ids": unreviewed_mappings,
        "reviewer_count": 0,
        "limitations": [
            "No candidate assertion has completed clinical or mapping review.",
            "MedlinePlus extraction uses exact deterministic terminology matches only.",
            "Monarch is aggregated knowledge; primary sources are retained and are not "
            "independent by default.",
            "The compatibility score is deterministic engineering output, never a probability.",
            "No safety, triage, laboratory, medication, pediatric, pregnancy or "
            "treatment coverage.",
        ],
        "metrics": metrics,
    }
    return build_snapshot_v2(
        root, registry, snapshot, knowledge, research_metadata=research_metadata
    )


def import_general_knowledge(
    root: Path, registry: RegistryV2
) -> tuple[CanonicalKnowledgeV2, list[CandidateAssertion], dict[str, Any]]:
    """Import all pinned artifacts. This function performs no network operation."""
    legacy_registry = load_registry(root / "sources/registry.yaml")
    legacy = import_registry(root, legacy_registry)
    legacy_manifest = {
        "schema_version": 1,
        "sources": legacy_registry.model_dump(mode="json")["sources"],
    }
    adapted = adapt_v1_tables(
        legacy_manifest,
        {table: list(rows.values()) for table, rows in legacy.rows.items()},
    )

    releases = {item.source_release_id: item for item in adapted.source_releases}
    artifacts = {item.artifact_id: item for item in adapted.source_artifacts}
    records = {item.source_record_id: item for item in adapted.source_records}
    concepts = {
        item.concept_id: item.model_copy(update={"kind": "condition"})
        if item.kind == "disease"
        else item
        for item in adapted.concepts
    }
    designations = {item.designation_id: item for item in adapted.designations}
    identifiers = {item.external_identifier_id: item for item in adapted.external_identifiers}
    hierarchy = {item.hierarchy_edge_id: item for item in adapted.hierarchy_edges}
    mappings = {item.mapping_id: item for item in adapted.concept_mappings}
    source_assertions = {item.source_assertion_id: item for item in adapted.source_assertions}
    canonical = {item.canonical_assertion_id: item for item in adapted.canonical_assertions}
    derivations = {item.derivation_id: item for item in adapted.assertion_derivations}
    families = {
        "orphanet-shared-upstream": EvidenceFamily(
            evidence_family_id="orphanet-shared-upstream",
            source_release_ids=["orphadata:2026-07"],
            source_assertion_ids=sorted(
                item.source_assertion_id
                for item in adapted.source_assertions
                if item.source_release_id.startswith("orphadata:")
            ),
            dependency_type="shared_upstream",
            primary_reference="Orphanet",
        )
    }

    source_by_id = {source.source_id: source for source in registry.sources}
    for source in registry.sources:
        release, source_artifacts = _source_models(source)
        releases[release.source_release_id] = release
        for artifact in source_artifacts:
            artifacts[artifact.artifact_id] = artifact

    _import_ontology(
        _raw_path(root, source_by_id["doid"], source_by_id["doid"].artifacts[0]),
        source_by_id["doid"],
        concepts,
        designations,
        identifiers,
        hierarchy,
    )
    _import_ontology_xrefs(
        _raw_path(root, source_by_id["mondo"], source_by_id["mondo"].artifacts[0]),
        source_by_id["mondo"],
        concepts,
        identifiers,
        mappings,
    )
    _import_ontology_xrefs(
        _raw_path(root, source_by_id["doid"], source_by_id["doid"].artifacts[0]),
        source_by_id["doid"],
        concepts,
        identifiers,
        mappings,
    )
    _import_mesh(
        root,
        source_by_id["mesh"],
        concepts,
        designations,
        identifiers,
        hierarchy,
        records,
    )

    candidates, candidate_rejections = _import_medlineplus(
        root,
        source_by_id["medlineplus"],
        concepts,
        designations,
        records,
        source_assertions,
        canonical,
        derivations,
        families,
    )
    monarch_count, monarch_by_primary = _import_monarch(
        root,
        source_by_id["monarch"],
        concepts,
        records,
        source_assertions,
        canonical,
        derivations,
        families,
    )
    dependencies = _source_dependencies(registry)
    knowledge = CanonicalKnowledgeV2(
        source_releases=_values(releases),
        source_artifacts=_values(artifacts),
        source_records=_values(records),
        concepts=_values(concepts),
        designations=_values(designations),
        external_identifiers=_values(identifiers),
        hierarchy_edges=_values(hierarchy),
        concept_mappings=_values(mappings),
        source_assertions=_values(source_assertions),
        canonical_assertions=_values(canonical),
        assertion_derivations=_values(derivations),
        evidence_families=_values(families),
        source_dependencies=dependencies,
    )
    source_diseases: dict[str, set[str]] = defaultdict(set)
    for assertion in knowledge.source_assertions:
        source_diseases[assertion.source_release_id].add(assertion.subject_concept_id)
    usable_candidates = [item for item in candidates if item.technically_eligible]
    unknown_releases = {
        item.source_release_id
        for item in knowledge.source_dependencies
        if item.dependency_type == "unknown"
    }
    aggregatable_source_assertions = {
        assertion_id
        for family in knowledge.evidence_families
        if family.dependency_type != "unknown"
        and not unknown_releases.intersection(family.source_release_ids)
        for assertion_id in family.source_assertion_ids
    }
    usable_canonical_assertions = {
        item.canonical_assertion_id
        for item in knowledge.assertion_derivations
        if item.source_assertion_id in aggregatable_source_assertions
    }
    metrics: dict[str, Any] = {
        "source_count": len(knowledge.source_releases),
        "artifact_count": len(knowledge.source_artifacts),
        "concept_count": len(knowledge.concepts),
        "disease_count": sum(item.kind == "condition" for item in knowledge.concepts),
        "finding_concept_count": len(
            {
                assertion.object.concept_id
                for assertion in knowledge.canonical_assertions
                if isinstance(assertion.object, ConceptObject)
            }
        ),
        "designation_count": len(knowledge.designations),
        "mapping_count": len(knowledge.concept_mappings),
        "exact_or_equivalent_mapping_count": sum(
            item.relation in {"exact", "equivalent"} and item.resolution_status == "resolved"
            for item in knowledge.concept_mappings
        ),
        "source_record_count": len(knowledge.source_records),
        "source_assertion_count": len(knowledge.source_assertions),
        "canonical_assertion_count": len(knowledge.canonical_assertions),
        "deduplicated_source_assertion_count": len(knowledge.source_assertions)
        - len(knowledge.canonical_assertions),
        "candidate_assertion_count": len(candidates),
        "medlineplus_topic_count": sum(
            item.source_release_id.startswith("medlineplus:") for item in knowledge.source_records
        ),
        "medlineplus_candidate_language": "English",
        "medlineplus_exact_hpo_candidate_count": sum(
            item.object_mapping is not None
            and item.object_mapping.relation == "exact"
            and item.object_mapping.status == "resolved"
            for item in candidates
        ),
        "normalized_assertion_count": len(usable_candidates),
        "candidate_technically_eligible_count": len(usable_candidates),
        "usable_assertion_count": len(usable_canonical_assertions),
        "clinically_approved_assertion_count": 0,
        "rejected_assertion_count": len(candidates) - len(usable_candidates),
        "candidate_rejection_reasons": dict(sorted(candidate_rejections.items())),
        "evidence_family_count": len(knowledge.evidence_families),
        "dependency_count": len(knowledge.source_dependencies),
        "monarch_imported_assertion_count": monarch_count,
        "monarch_primary_sources": dict(sorted(monarch_by_primary.items())),
        "diseases_with_assertions_by_source": {
            key: len(value) for key, value in sorted(source_diseases.items())
        },
    }
    return knowledge, candidates, metrics


def _source_models(
    source: SourcePackageV2,
) -> tuple[SourceReleaseV2, list[SourceArtifactV2]]:
    release_id = _release_id(source)
    release = SourceReleaseV2(
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
    artifacts = [
        SourceArtifactV2(
            artifact_id=_artifact_id(source, artifact),
            source_release_id=release_id,
            filename=artifact.filename,
            sha256=artifact.sha256,
            format=artifact.format,
            language=artifact.language,
            source_url=artifact.source_url,
        )
        for artifact in source.artifacts
    ]
    return release, artifacts


def _import_ontology(
    path: Path,
    source: SourcePackageV2,
    concepts: dict[str, ConceptV2],
    designations: dict[str, DesignationV2],
    identifiers: dict[str, ExternalIdentifierV2],
    hierarchy: dict[str, HierarchyEdgeV2],
) -> None:
    document = orjson.loads(path.read_bytes())
    release_id = _release_id(source)
    prefix = "DOID:" if source.source_id == "doid" else ""
    code_to_concept: dict[str, str] = {}
    for graph in document.get("graphs", []):
        for node in graph.get("nodes", []):
            code = _compact_code(str(node.get("id", "")))
            if node.get("type") != "CLASS" or not code.startswith(prefix):
                continue
            meta = node.get("meta", {})
            concept_id = stable_id("concept", code)
            code_to_concept[code] = concept_id
            concepts[concept_id] = ConceptV2(
                concept_id=concept_id,
                kind="condition",
                status="obsolete" if meta.get("deprecated") else "active",
                primary_code=code,
                source_release_id=release_id,
            )
            _designation(
                designations,
                concept_id,
                str(node.get("lbl") or code),
                "preferred",
                release_id,
            )
            for synonym in meta.get("synonyms", []):
                if text := str(synonym.get("val", "")).strip():
                    _designation(
                        designations,
                        concept_id,
                        text,
                        str(synonym.get("pred") or "related"),
                        release_id,
                    )
            _identifier(identifiers, concept_id, code, "identity", release_id)
    for graph in document.get("graphs", []):
        for edge in graph.get("edges", []):
            child = _compact_code(str(edge.get("sub", "")))
            parent = _compact_code(str(edge.get("obj", "")))
            if edge.get("pred") != "is_a" or child not in code_to_concept:
                continue
            if parent not in code_to_concept:
                continue
            item = HierarchyEdgeV2(
                hierarchy_edge_id=stable_id("edge", child, parent, release_id),
                child_concept_id=code_to_concept[child],
                parent_concept_id=code_to_concept[parent],
                source_release_id=release_id,
            )
            hierarchy[item.hierarchy_edge_id] = item


def _import_ontology_xrefs(
    path: Path,
    source: SourcePackageV2,
    concepts: dict[str, ConceptV2],
    identifiers: dict[str, ExternalIdentifierV2],
    mappings: dict[str, ConceptMappingV2],
) -> None:
    document = orjson.loads(path.read_bytes())
    release_id = _release_id(source)
    code_lookup = {item.primary_code: item.concept_id for item in concepts.values()}
    for graph in document.get("graphs", []):
        for node in graph.get("nodes", []):
            code = _compact_code(str(node.get("id", "")))
            concept_id = code_lookup.get(code)
            if concept_id is None:
                continue
            raw_xrefs = [item.get("val") for item in node.get("meta", {}).get("xrefs", [])]
            for raw in raw_xrefs:
                target_code = _compact_code(str(raw or ""))
                if not target_code or ":" not in target_code:
                    continue
                _identifier(identifiers, concept_id, target_code, "xref", release_id)
                if not target_code.startswith(("DOID:", "MESH:", "MONDO:")):
                    continue
                target_id = code_lookup.get(target_code)
                mapping_id = stable_id("mapping", concept_id, target_code, "xref", release_id)
                mappings[mapping_id] = ConceptMappingV2(
                    mapping_id=mapping_id,
                    source_concept_id=concept_id,
                    target_concept_id=target_id,
                    target_system=_system(target_code),
                    target_code=target_code,
                    direction="source_to_target",
                    relation="related" if target_id else "unresolved",
                    original_relation="xref",
                    source_release_id=release_id,
                    evidence={"source_node": code, "source_xref": str(raw)},
                    resolution_status="resolved" if target_id else "unresolved",
                )


def _import_mesh(
    root: Path,
    source: SourcePackageV2,
    concepts: dict[str, ConceptV2],
    designations: dict[str, DesignationV2],
    identifiers: dict[str, ExternalIdentifierV2],
    hierarchy: dict[str, HierarchyEdgeV2],
    records: dict[str, SourceRecordV2],
) -> None:
    artifact = source.artifacts[0]
    artifact_id = _artifact_id(source, artifact)
    release_id = _release_id(source)
    parsed = parse_mesh_descriptors(_raw_path(root, source, artifact))
    tree_index: dict[str, str] = {}
    for record in parsed:
        code = f"MESH:{record.descriptor_ui}"
        concept_id = stable_id("concept", code)
        concepts[concept_id] = ConceptV2(
            concept_id=concept_id,
            kind="terminology",
            primary_code=code,
            source_release_id=release_id,
        )
        _identifier(identifiers, concept_id, code, "identity", release_id)
        for term in record.terms:
            _designation(
                designations,
                concept_id,
                term,
                "preferred" if term == record.name else "entry_term",
                release_id,
            )
        source_record_id = stable_id("source_record", release_id, record.descriptor_ui)
        records[source_record_id] = SourceRecordV2(
            source_record_id=source_record_id,
            source_release_id=release_id,
            artifact_ids=[artifact_id],
            record_locator=record.source_locator,
            raw_value=record.model_dump(mode="json"),
        )
        for tree in record.tree_numbers:
            tree_index[tree] = concept_id
    for record in parsed:
        child_id = stable_id("concept", f"MESH:{record.descriptor_ui}")
        for tree in record.tree_numbers:
            if "." not in tree:
                continue
            parent_id = tree_index.get(tree.rsplit(".", 1)[0])
            if parent_id is None or parent_id == child_id:
                continue
            edge_id = stable_id("edge", child_id, parent_id, release_id, tree)
            hierarchy[edge_id] = HierarchyEdgeV2(
                hierarchy_edge_id=edge_id,
                child_concept_id=child_id,
                parent_concept_id=parent_id,
                source_release_id=release_id,
            )


def _import_medlineplus(
    root: Path,
    source: SourcePackageV2,
    concepts: dict[str, ConceptV2],
    designations: dict[str, DesignationV2],
    records: dict[str, SourceRecordV2],
    source_assertions: dict[str, SourceAssertion],
    canonical: dict[str, CanonicalAssertion],
    derivations: dict[str, AssertionDerivation],
    families: dict[str, EvidenceFamily],
) -> tuple[list[CandidateAssertion], Counter[str]]:
    artifact = source.artifacts[0]
    artifact_id = _artifact_id(source, artifact)
    release_id = _release_id(source)
    topics = parse_medlineplus_topics(_raw_path(root, source, artifact))
    concept_by_id = concepts
    condition_index = _condition_label_index(concepts, designations)
    hpo_index = _hpo_label_index(concepts, designations)
    candidates: list[CandidateAssertion] = []
    rejections: Counter[str] = Counter()
    family_id = "medlineplus-health-topics-editorial-unknown"
    family_assertions: list[str] = []
    for topic in topics:
        source_record_id = stable_id("source_record", release_id, topic.topic_id)
        records[source_record_id] = SourceRecordV2(
            source_record_id=source_record_id,
            source_release_id=release_id,
            artifact_ids=[artifact_id],
            record_locator=topic.source_locator,
            raw_value=topic.model_dump(mode="json"),
        )
        # The first deterministic extractor uses English HPO designations only. Keep every
        # bilingual source record, but do not silently apply an English matcher to Spanish text.
        if topic.language.casefold() != "english":
            continue
        subject_mapping = _map_subject(topic, condition_index, concept_by_id)
        seen_objects: set[str] = set()
        ordinal = 0
        for summary_index, summary in enumerate(topic.summaries):
            for phrase, object_ids in _matches(summary, hpo_index):
                signature = f"{phrase}|{'|'.join(sorted(object_ids))}"
                if signature in seen_objects:
                    continue
                seen_objects.add(signature)
                object_mapping = _mapping_proposal(phrase, object_ids, concepts, "HPO exact term")
                locator = f"{topic.source_locator}/full-summary[{summary_index + 1}]/{phrase}"
                candidate = CandidateAssertion(
                    candidate_assertion_id=make_candidate_assertion_id(
                        release_id, source_record_id, locator, ordinal
                    ),
                    source_release_id=release_id,
                    source_record_id=source_record_id,
                    source_locator=locator,
                    artifact_sha256=[artifact.sha256],
                    subject_text=topic.title,
                    subject_type="condition",
                    predicate="has_symptom",
                    object_text=phrase,
                    object_type="symptom",
                    evidence_family=family_id,
                    dependency_group="medlineplus-editorial-unknown",
                    subject_mapping=subject_mapping,
                    object_mapping=object_mapping,
                    extraction=ExtractionProvenance(
                        extractor_id=EXTRACTOR_ID,
                        extractor_version=EXTRACTOR_VERSION,
                        method="rule_based",
                    ),
                    transformation_chain=[
                        "local MedlinePlus XML",
                        "summary text normalization",
                        "exact unique HPO designation match",
                        "exact unique Mondo/DOID title match",
                    ],
                )
                candidates.append(candidate)
                ordinal += 1
                if not candidate.technically_eligible:
                    rejections[_candidate_rejection(candidate)] += 1
                    continue
                assert candidate.subject_mapping is not None
                assert candidate.subject_mapping.concept_id is not None
                assert candidate.object_mapping is not None
                assert candidate.object_mapping.concept_id is not None
                source_assertion = _candidate_source_assertion(
                    candidate, artifact_id, source, ordinal
                )
                source_assertions[source_assertion.source_assertion_id] = source_assertion
                canonical_id = _canonicalize(source_assertion, canonical)
                derivation = AssertionDerivation(
                    derivation_id=stable_id(
                        "derivation", source_assertion.source_assertion_id, canonical_id
                    ),
                    source_assertion_id=source_assertion.source_assertion_id,
                    canonical_assertion_id=canonical_id,
                    rule_id=EXTRACTOR_ID,
                    rule_version=EXTRACTOR_VERSION,
                    transformations=candidate.transformation_chain,
                )
                derivations[derivation.derivation_id] = derivation
                family_assertions.append(source_assertion.source_assertion_id)
    if family_assertions:
        families[family_id] = EvidenceFamily(
            evidence_family_id=family_id,
            source_release_ids=[release_id],
            source_assertion_ids=sorted(family_assertions),
            dependency_type="unknown",
            primary_reference="MedlinePlus editorial source dependency not asserted",
        )
    return candidates, rejections


def _import_monarch(
    root: Path,
    source: SourcePackageV2,
    concepts: dict[str, ConceptV2],
    records: dict[str, SourceRecordV2],
    source_assertions: dict[str, SourceAssertion],
    canonical: dict[str, CanonicalAssertion],
    derivations: dict[str, AssertionDerivation],
    families: dict[str, EvidenceFamily],
) -> tuple[int, Counter[str]]:
    artifact = source.artifacts[0]
    artifact_id = _artifact_id(source, artifact)
    release_id = _release_id(source)
    condition_by_code = {
        item.primary_code: item.concept_id
        for item in concepts.values()
        if item.kind == "condition" and item.status == "active"
    }
    hpo_by_code = {
        item.primary_code: item.concept_id
        for item in concepts.values()
        if item.primary_code.startswith("HP:") and item.status == "active"
    }
    family_members: dict[str, list[str]] = defaultdict(list)
    family_releases: dict[str, set[str]] = defaultdict(set)
    family_primary: dict[str, str] = {}
    family_dependency: dict[str, str] = {}
    primary_counts: Counter[str] = Counter()
    count = 0
    iterator = iter_monarch_disease_phenotypes(
        _raw_path(root, source, artifact),
        accepted_subjects=set(condition_by_code),
        accepted_objects=set(hpo_by_code),
    )
    for row in iterator:
        count += 1
        primary_counts[row.primary_knowledge_source] += 1
        source_record_id = stable_id("source_record", release_id, row.edge_id)
        records[source_record_id] = SourceRecordV2(
            source_record_id=source_record_id,
            source_release_id=release_id,
            artifact_ids=[artifact_id],
            record_locator=row.source_locator,
            raw_value=row.model_dump(mode="json"),
        )
        qualifiers = AssertionQualifiers(
            polarity="excluded" if row.negated else "present",
            frequency=_monarch_frequency(row),
            temporal_context=row.onset_qualifier,
            clinical_context=(f"Monarch primary knowledge source: {row.primary_knowledge_source}"),
        )
        source_assertion_id = make_source_assertion_id(
            source.source_id,
            source.release,
            [artifact.sha256],
            row.source_locator,
            0,
        )
        assertion = SourceAssertion(
            source_assertion_id=source_assertion_id,
            subject_concept_id=condition_by_code[row.subject],
            relation="has_sign",
            object=ConceptObject(concept_id=hpo_by_code[row.object]),
            qualifiers=qualifiers,
            source_release_id=release_id,
            source_record_id=source_record_id,
            artifact_ids=[artifact_id],
            record_ordinal=0,
            raw_value=row.model_dump(mode="json"),
        )
        source_assertions[source_assertion_id] = assertion
        canonical_id = _canonicalize(assertion, canonical)
        derivation = AssertionDerivation(
            derivation_id=stable_id("derivation", source_assertion_id, canonical_id),
            source_assertion_id=source_assertion_id,
            canonical_assertion_id=canonical_id,
            rule_id="monarch_disease_phenotype_direct_resolution",
            rule_version="1",
            transformations=[
                "filter DiseaseToPhenotypicFeatureAssociation",
                "require direct local disease identifier",
                "require direct HPO identifier",
                "preserve primary knowledge source",
            ],
        )
        derivations[derivation.derivation_id] = derivation
        if row.primary_knowledge_source == "infores:orphanet":
            family_id = "orphanet-shared-upstream"
            family_dependency[family_id] = "shared_upstream"
            family_primary[family_id] = "Orphanet"
        else:
            family_id = stable_id(
                "evidence_family", "monarch-upstream", row.primary_knowledge_source
            )
            family_dependency[family_id] = "derived_from"
            family_primary[family_id] = row.primary_knowledge_source
        family_members[family_id].append(source_assertion_id)
        family_releases[family_id].add(release_id)
    for family_id, members in family_members.items():
        existing = families.get(family_id)
        if existing is not None:
            members = [*existing.source_assertion_ids, *members]
            family_releases[family_id].update(existing.source_release_ids)
        families[family_id] = EvidenceFamily(
            evidence_family_id=family_id,
            source_release_ids=sorted(family_releases[family_id]),
            source_assertion_ids=sorted(set(members)),
            dependency_type=family_dependency[family_id],  # type: ignore[arg-type]
            primary_reference=family_primary[family_id],
        )
    return count, primary_counts


def _candidate_source_assertion(
    candidate: CandidateAssertion,
    artifact_id: str,
    source: SourcePackageV2,
    ordinal: int,
) -> SourceAssertion:
    assert candidate.subject_mapping is not None
    assert candidate.subject_mapping.concept_id is not None
    assert candidate.object_mapping is not None
    assert candidate.object_mapping.concept_id is not None
    return SourceAssertion(
        source_assertion_id=make_source_assertion_id(
            source.source_id,
            source.release,
            candidate.artifact_sha256,
            candidate.source_locator,
            ordinal,
        ),
        subject_concept_id=candidate.subject_mapping.concept_id,
        relation="has_symptom",
        object=ConceptObject(concept_id=candidate.object_mapping.concept_id),
        qualifiers=AssertionQualifiers(polarity=candidate.polarity),
        source_release_id=candidate.source_release_id,
        source_record_id=candidate.source_record_id,
        artifact_ids=[artifact_id],
        record_ordinal=ordinal,
        raw_value={"candidate": candidate.model_dump(mode="json")},
    )


def _canonicalize(assertion: SourceAssertion, canonical: dict[str, CanonicalAssertion]) -> str:
    canonical_id = make_canonical_assertion_id(
        assertion.subject_concept_id,
        assertion.relation,
        assertion.object,
        assertion.qualifiers,
    )
    canonical.setdefault(
        canonical_id,
        CanonicalAssertion(
            canonical_assertion_id=canonical_id,
            subject_concept_id=assertion.subject_concept_id,
            relation=assertion.relation,
            object=assertion.object,
            qualifiers=assertion.qualifiers,
        ),
    )
    return canonical_id


def _condition_label_index(
    concepts: dict[str, ConceptV2], designations: dict[str, DesignationV2]
) -> dict[str, tuple[str, ...]]:
    mondo: dict[str, set[str]] = defaultdict(set)
    doid: dict[str, set[str]] = defaultdict(set)
    for item in designations.values():
        concept = concepts.get(item.concept_id)
        if concept is None or concept.kind != "condition" or concept.status != "active":
            continue
        target = mondo if concept.primary_code.startswith("MONDO:") else doid
        if concept.primary_code.startswith(("MONDO:", "DOID:")):
            target[_normalize(item.text)].add(item.concept_id)
    result: dict[str, tuple[str, ...]] = {}
    for label in set(mondo) | set(doid):
        preferred = mondo.get(label) or doid.get(label) or set()
        result[label] = tuple(sorted(preferred))
    return result


def _hpo_label_index(
    concepts: dict[str, ConceptV2], designations: dict[str, DesignationV2]
) -> dict[int, dict[str, tuple[str, ...]]]:
    values: dict[str, set[str]] = defaultdict(set)
    for item in designations.values():
        concept = concepts.get(item.concept_id)
        if (
            concept is None
            or concept.status != "active"
            or not concept.primary_code.startswith("HP:")
        ):
            continue
        normalized = _normalize(item.text)
        words = normalized.split()
        if 1 <= len(words) <= 8 and len(normalized) >= 4:
            values[normalized].add(item.concept_id)
    by_size: dict[int, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for phrase, concept_ids in values.items():
        by_size[len(phrase.split())][phrase] = tuple(sorted(concept_ids))
    return dict(by_size)


def _map_subject(
    topic: MedlinePlusTopicRecord,
    index: dict[str, tuple[str, ...]],
    concepts: dict[str, ConceptV2],
) -> MappingProposal:
    matches: set[str] = set()
    provenance: list[str] = []
    for label in [topic.title, *topic.synonyms]:
        found = index.get(_normalize(label), ())
        if found:
            matches.update(found)
            provenance.append(label)
    return _mapping_proposal(
        topic.title,
        tuple(sorted(matches)),
        concepts,
        "exact unique Mondo-first/DOID-fallback designation: " + ", ".join(provenance),
    )


def _mapping_proposal(
    text: str,
    concept_ids: Iterable[str],
    concepts: dict[str, ConceptV2],
    provenance: str,
) -> MappingProposal:
    values = tuple(sorted(set(concept_ids)))
    if len(values) == 1:
        concept = concepts[values[0]]
        return MappingProposal(
            system=_system(concept.primary_code),
            code=concept.primary_code,
            concept_id=concept.concept_id,
            relation="exact",
            status="resolved",
            provenance=provenance,
        )
    return MappingProposal(
        system="urn:latros:unresolved",
        code=_normalize(text),
        relation="unresolved",
        status="ambiguous" if values else "unresolved",
        provenance=provenance or "no exact unique designation",
    )


def _matches(
    text: str, index: dict[int, dict[str, tuple[str, ...]]]
) -> Iterable[tuple[str, tuple[str, ...]]]:
    words = _normalize(text).split()
    found: dict[str, tuple[str, ...]] = {}
    for size in sorted(index, reverse=True):
        if size > len(words):
            continue
        choices = index[size]
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start : start + size])
            if phrase in choices:
                found.setdefault(phrase, choices[phrase])
    return sorted(found.items())


def _candidate_rejection(candidate: CandidateAssertion) -> str:
    if candidate.subject_mapping is None or candidate.subject_mapping.status == "unresolved":
        return "subject_unresolved"
    if candidate.subject_mapping.status == "ambiguous":
        return "subject_ambiguous"
    if candidate.object_mapping is None or candidate.object_mapping.status == "unresolved":
        return "object_unresolved"
    if candidate.object_mapping.status == "ambiguous":
        return "object_ambiguous"
    return "non_exact_or_equivalent_mapping"


def _monarch_frequency(row: MonarchDiseasePhenotypeRecord) -> Frequency | None:
    if row.negated:
        return Frequency(
            kind="excluded",
            raw="HP:0040285",
            category="HP:0040285",
            lower=0,
            upper=0,
        )
    if row.has_count is not None and row.has_total is not None and row.has_total > 0:
        if row.has_count <= row.has_total:
            value = row.has_count / row.has_total
            return Frequency(
                kind="count",
                raw=f"{row.has_count}/{row.has_total}",
                numerator=row.has_count,
                denominator=row.has_total,
                lower=value,
                upper=value,
            )
    if row.has_percentage is not None and 0 <= row.has_percentage <= 100:
        value = row.has_percentage / 100
        return Frequency(
            kind="percentage",
            raw=f"{row.has_percentage}%",
            lower=value,
            upper=value,
        )
    return None


def _source_dependencies(registry: RegistryV2) -> list[SourceDependency]:
    result: list[SourceDependency] = []
    for source in sorted(registry.sources, key=lambda item: item.source_id):
        release_id = _release_id(source)
        if not source.dependencies:
            result.append(
                SourceDependency(
                    source_dependency_id=stable_id("source_dependency", release_id, release_id),
                    source_release_id=release_id,
                    upstream_reference=release_id,
                    dependency_type="primary",
                    evidence="Registry declares no upstream dependency",
                )
            )
        for dependency in source.dependencies:
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


def _designation(
    target: dict[str, DesignationV2],
    concept_id: str,
    text: str,
    scope: str,
    release_id: str,
) -> None:
    designation_id = stable_id("designation", concept_id, "en", text, scope, release_id)
    target[designation_id] = DesignationV2(
        designation_id=designation_id,
        concept_id=concept_id,
        language="en",
        text=text,
        scope=scope,
        source_release_id=release_id,
    )


def _identifier(
    target: dict[str, ExternalIdentifierV2],
    concept_id: str,
    code: str,
    relation: str,
    release_id: str,
) -> None:
    identifier_id = stable_id("identifier", concept_id, code, release_id)
    target[identifier_id] = ExternalIdentifierV2(
        external_identifier_id=identifier_id,
        concept_id=concept_id,
        system=_system(code),
        code=code,
        relation=relation,
        source_release_id=release_id,
    )


def _compact_code(value: str) -> str:
    match = re.search(r"(?:/obo/|^)(HP|MONDO|DOID)[_:](\d+)$", value)
    if match:
        return f"{match[1]}:{match[2]}"
    match = re.fullmatch(r"(?:MESH|MeSH):?(D\d+)", value)
    if match:
        return f"MESH:{match[1]}"
    match = re.search(r"(?:Orphanet[_:]|ORPHA:)(\d+)$", value)
    if match:
        return f"ORPHA:{match[1]}"
    return value.strip()


def _system(code: str) -> str:
    prefix = code.split(":", 1)[0]
    return {
        "HP": "http://purl.obolibrary.org/obo/hp.owl",
        "MONDO": "http://purl.obolibrary.org/obo/mondo.owl",
        "DOID": "http://purl.obolibrary.org/obo/doid.owl",
        "MESH": "https://id.nlm.nih.gov/mesh/",
        "ORPHA": "https://www.orpha.net",
    }.get(prefix, f"urn:latros:code-system:{prefix}")


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value))


def _release_id(source: SourcePackageV2) -> str:
    return f"{source.source_id}:{source.release}"


def _artifact_id(source: SourcePackageV2, artifact: RegistryArtifactV2) -> str:
    return stable_id("source_artifact", _release_id(source), artifact.filename, artifact.sha256)


def _raw_path(root: Path, source: SourcePackageV2, artifact: RegistryArtifactV2) -> Path:
    if artifact.local_path is not None:
        return root / artifact.local_path
    return root / "data/raw" / source.source_id / source.release / artifact.filename


def _values(values: dict[str, T]) -> list[T]:
    return [values[key] for key in sorted(values)]
