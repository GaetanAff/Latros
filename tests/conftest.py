"""Tiny invented concepts and disorders; no source extracts or patient data."""

import socket
from pathlib import Path

import orjson
import pytest
import yaml
from lxml import etree

from latros.common import sha256, stable_id
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
from latros.knowledge.store import build_snapshot
from latros.sources.registry import Registry
from latros.sources.registry_v2 import RegistryV2


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


def uri(identifier):
    return "http://purl.obolibrary.org/obo/" + identifier.replace(":", "_")


def synthetic_registry(root: Path) -> Registry:
    def node(identifier, label, meta=None):
        return {"id": uri(identifier), "type": "CLASS", "lbl": label, "meta": meta or {}}

    hp_nodes = [node("HP:0000118", "Phenotypic abnormality")]
    for index in range(1, 16):
        hp_nodes.append(node(f"HP:90000{index:02}", f"Invented sign {index}"))
    hp_nodes[1]["meta"] = {
        "synonyms": [{"pred": "hasExactSynonym", "val": "Invented alias"}],
        "basicPropertyValues": [{"pred": "oboInOwl#hasAlternativeId", "val": "HP:9999901"}],
    }
    hp_nodes.append(
        node(
            "HP:9999998",
            "Old sign",
            {
                "deprecated": True,
                "basicPropertyValues": [{"pred": uri("IAO:0100001"), "val": uri("HP:9000001")}],
            },
        )
    )
    hp_nodes.append(node("HP:9999999", "Retired sign", {"deprecated": True}))
    hp = {
        "graphs": [
            {
                "nodes": hp_nodes,
                "edges": [
                    {"sub": n["id"], "pred": "is_a", "obj": uri("HP:0000118")}
                    for n in hp_nodes[1:16]
                ]
                + [{"sub": uri("HP:9000004"), "pred": "is_a", "obj": uri("HP:9000001")}],
            }
        ]
    }
    mondo = {
        "graphs": [
            {
                "nodes": [
                    node(
                        "MONDO:9000001",
                        "Invented disease A",
                        {
                            "xrefs": [{"val": "Orphanet:900001"}, {"val": "Orphanet:900003"}],
                            "basicPropertyValues": [
                                {
                                    "pred": "http://www.w3.org/2004/02/skos/core#exactMatch",
                                    "val": "http://www.orpha.net/ORDO/Orphanet_900001",
                                }
                            ],
                        },
                    ),
                    node("MONDO:9000002", "Invented disease B"),
                ],
                "edges": [],
            }
        ]
    }
    contents = {
        "hpo": {"hp.json": orjson.dumps(hp)},
        "mondo": {"mondo.json": orjson.dumps(mondo)},
        "orphadata": {},
    }
    # Two candidates share sign 1, but sign 2 discriminates using different frequencies.
    associations = {
        "900001": [
            ("1", "HP:9000001", "28405"),
            ("2", "HP:9000002", "28412"),
            ("3", "HP:9000003", None),
            ("4", "HP:9000005", "28440"),
        ],
        "900002": [
            ("5", "HP:9000001", "28405"),
            ("6", "HP:9000002", "28433"),
            ("7", "HP:9000003", None),
        ],
        "900003": [("8", "HP:9000003", "28405")],
    }
    for lang in ("en", "fr"):
        document = etree.Element("JDBOR")
        for disease, records in associations.items():
            disorder = etree.SubElement(document, "Disorder")
            etree.SubElement(disorder, "OrphaCode").text = disease
            etree.SubElement(disorder, "Name").text = f"{lang} invented disorder {disease}"
            etree.SubElement(disorder, "ExpertLink").text = f"https://example.test/{disease}"
            container = etree.SubElement(disorder, "HPODisorderAssociationList")
            for aid, phenotype, freq in records:
                entry = etree.SubElement(container, "HPODisorderAssociation", id=aid)
                hpo = etree.SubElement(entry, "HPO")
                etree.SubElement(hpo, "HPOId").text = phenotype
                etree.SubElement(hpo, "HPOTerm").text = f"{lang} invented {phenotype}"
                if freq:
                    frequency = etree.SubElement(entry, "HPOFrequency", id=freq)
                    etree.SubElement(frequency, "Name").text = f"{lang} category {freq}"
        contents["orphadata"][f"{lang}_product4.xml"] = etree.tostring(document)
    sources = []
    for source_id, files in contents.items():
        artifacts = []
        for filename, content in files.items():
            path = root / "data/raw" / source_id / "test-v1" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            artifacts.append(
                dict(
                    filename=filename,
                    product="Synthetic test fixture",
                    format="orphadata-product4-xml"
                    if source_id == "orphadata"
                    else "obographs-json",
                    language="fr" if filename.startswith("fr_") else "en",
                    url=f"https://example.test/test-v1/{filename}",
                    sha256=sha256(path),
                )
            )
        sources.append(
            dict(
                id=source_id,
                role=["synthetic"],
                homepage="https://example.test",
                release="test-v1",
                release_date="2026-09-16",
                license=dict(
                    name="CC0-1.0",
                    url="https://example.test/license",
                    attribution="Invented Latros test fixtures",
                    redistribution="allowed_with_attribution",
                ),
                authentication_required=False,
                upstream_dependencies=[],
                artifacts=artifacts,
            )
        )
    registry = Registry.model_validate({"sources": sources})
    (root / "sources").mkdir()
    (root / "sources/registry.yaml").write_text(
        yaml.safe_dump(registry.model_dump()), encoding="utf-8"
    )
    return registry


@pytest.fixture
def registry(tmp_path):
    return synthetic_registry(tmp_path)


@pytest.fixture
def built(tmp_path, registry):
    build_snapshot(tmp_path, registry, "test")
    return tmp_path, registry


def synthetic_registry_and_knowledge_v2(root: Path) -> tuple[RegistryV2, CanonicalKnowledgeV2]:
    terminology_content = b"Invented terminology fixture; no external codes or labels.\n"
    guidance_content = b"Invented assertions fixture; not medical knowledge.\n"
    artifacts: dict[str, tuple[Path, str]] = {}
    for source_id, filename, content in (
        ("invented-terminology", "concepts.tsv", terminology_content),
        ("invented-guidance", "assertions.jsonl", guidance_content),
    ):
        path = root / "data/raw" / source_id / "test-v2" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        artifacts[source_id] = (path, sha256(path))
    sources = []
    for source_id, role, filename, artifact_format in (
        ("invented-terminology", "terminology", "concepts.tsv", "rf2-concepts-tsv"),
        (
            "invented-guidance",
            "diagnostic_assertions",
            "assertions.jsonl",
            "curated-assertions-jsonl",
        ),
    ):
        _, artifact_hash = artifacts[source_id]
        sources.append(
            {
                "source_id": source_id,
                "roles": [role],
                "homepage": f"https://example.test/{source_id}/test-v2",
                "release": "test-v2",
                "release_date": "2026-09-01",
                "access_date": "2026-09-17",
                "license": {
                    "name": "Synthetic test fixture",
                    "url": "https://example.test/licenses/synthetic-v2",
                    "attribution": "Invented by Latros tests",
                    "redistribution": "allowed_with_attribution",
                    "implementation_rights_confirmed": True,
                    "notes": "No external medical or terminology content",
                },
                "upstream_dependencies": [],
                "artifacts": [
                    {
                        "filename": filename,
                        "product": "Synthetic v2 test fixture",
                        "format": artifact_format,
                        "language": "en",
                        "source_url": (
                            f"https://example.test/{source_id}/releases/test-v2/{filename}"
                        ),
                        "sha256": artifact_hash,
                        "access_mode": "manual_local",
                    }
                ],
            }
        )
    registry = RegistryV2.model_validate(
        {
            "schema_version": 2,
            "canonical_schema_version": 2,
            "scope": {
                "scope_id": "synthetic-adult-outpatient",
                "domain": "invented outpatient differential",
                "population": "synthetic adults aged 18 years or older",
                "observation_types": ["symptom", "sign", "exam", "vital"],
                "relations": ["has_symptom", "has_sign", "has_exam_finding"],
                "exclusions": ["not medical knowledge", "no treatment"],
            },
            "compatible_profiles": ["general_v1-default"],
            "sources": sources,
        }
    )
    terminology_release = "invented-terminology:test-v2"
    guidance_release = "invented-guidance:test-v2"
    source_releases = []
    source_artifacts = []
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
            source_artifacts.append(
                SourceArtifactV2(
                    artifact_id=stable_id("artifact", release_id, artifact.filename),
                    source_release_id=release_id,
                    filename=artifact.filename,
                    sha256=artifact.sha256,
                    format=artifact.format,
                    language=artifact.language,
                    source_url=artifact.source_url,
                )
            )
    concept_specs = [
        ("condition-root", "condition", "Invented condition root"),
        ("finding-root", "finding", "Invented finding root"),
        *[
            (f"condition-{index}", "condition", f"Invented condition {index}")
            for index in range(1, 5)
        ],
        *[(f"finding-{index}", "finding", f"Invented finding {index}") for index in range(1, 5)],
    ]
    concepts = [
        ConceptV2(
            concept_id=f"test:{code}",
            kind=kind,
            primary_code=f"TEST:{code}",
            source_release_id=terminology_release,
        )
        for code, kind, _ in concept_specs
    ]
    designations = [
        DesignationV2(
            designation_id=stable_id("designation", f"test:{code}", "en", label),
            concept_id=f"test:{code}",
            language="en",
            text=label,
            scope="preferred",
            source_release_id=terminology_release,
        )
        for code, _, label in concept_specs
    ]
    external_identifiers = [
        ExternalIdentifierV2(
            external_identifier_id=stable_id("external_identifier", f"test:{code}"),
            concept_id=f"test:{code}",
            system="urn:latros:test-terminology",
            code=f"TEST:{code}",
            relation="identity",
            source_release_id=terminology_release,
        )
        for code, _, _ in concept_specs
    ]
    hierarchy_edges = [
        HierarchyEdgeV2(
            hierarchy_edge_id=stable_id("hierarchy", f"test:condition-{index}"),
            child_concept_id=f"test:condition-{index}",
            parent_concept_id="test:condition-root",
            source_release_id=terminology_release,
        )
        for index in range(1, 5)
    ] + [
        HierarchyEdgeV2(
            hierarchy_edge_id=stable_id("hierarchy", f"test:finding-{index}"),
            child_concept_id=f"test:finding-{index}",
            parent_concept_id="test:finding-root",
            source_release_id=terminology_release,
        )
        for index in range(1, 5)
    ]
    concept_mappings = [
        ConceptMappingV2(
            mapping_id=stable_id("mapping", "test:finding-1", "ALT:F1"),
            source_concept_id="test:finding-1",
            target_concept_id="test:finding-1",
            target_system="urn:latros:test-alternate",
            target_code="ALT:F1",
            direction="bidirectional",
            relation="exact",
            original_relation="invented exact fixture",
            source_release_id=terminology_release,
            evidence={"fixture": True},
            resolution_status="resolved",
        )
    ]
    artifact = next(item for item in source_artifacts if item.source_release_id == guidance_release)
    assertion_specs = [
        (1, 1, "has_symptom", "present"),
        (1, 2, "has_symptom", "excluded"),
        (2, 1, "has_symptom", "present"),
        (2, 2, "has_symptom", "present"),
        (3, 3, "has_sign", "present"),
        (3, 4, "has_exam_finding", "present"),
        (4, 2, "has_symptom", "present"),
        (4, 3, "has_sign", "excluded"),
    ]
    source_records = []
    source_assertions = []
    canonical_assertions: dict[str, CanonicalAssertion] = {}
    derivations = []
    for ordinal, (condition, finding, relation, polarity) in enumerate(assertion_specs):
        locator = f"invented-record-{ordinal + 1}"
        record_id = stable_id("record", guidance_release, locator)
        source_records.append(
            SourceRecordV2(
                source_record_id=record_id,
                source_release_id=guidance_release,
                artifact_ids=[artifact.artifact_id],
                record_locator=locator,
                raw_value={
                    "fixture": True,
                    "curation": {
                        "curator": "invented-curator",
                        "reviewers": ["invented-clinical-reviewer", "invented-mapping-reviewer"],
                        "status": "approved_for_synthetic_test",
                    },
                },
            )
        )
        qualifiers = AssertionQualifiers(polarity=polarity)
        object_value = ConceptObject(concept_id=f"test:finding-{finding}")
        source_assertion_id = make_source_assertion_id(
            "invented-guidance",
            "test-v2",
            [artifact.sha256],
            locator,
            0,
        )
        source_assertions.append(
            SourceAssertion(
                source_assertion_id=source_assertion_id,
                subject_concept_id=f"test:condition-{condition}",
                relation=relation,
                object=object_value,
                qualifiers=qualifiers,
                source_release_id=guidance_release,
                source_record_id=record_id,
                artifact_ids=[artifact.artifact_id],
                record_ordinal=0,
                raw_value={"fixture": True, "polarity": polarity},
            )
        )
        canonical_id = make_canonical_assertion_id(
            f"test:condition-{condition}", relation, object_value, qualifiers
        )
        canonical_assertions.setdefault(
            canonical_id,
            CanonicalAssertion(
                canonical_assertion_id=canonical_id,
                subject_concept_id=f"test:condition-{condition}",
                relation=relation,
                object=object_value,
                qualifiers=qualifiers,
            ),
        )
        derivations.append(
            AssertionDerivation(
                derivation_id=stable_id("derivation", source_assertion_id, canonical_id),
                source_assertion_id=source_assertion_id,
                canonical_assertion_id=canonical_id,
                rule_id="synthetic-curation",
                rule_version="1",
                transformations=["identity"],
            )
        )
    evidence_family = EvidenceFamily(
        evidence_family_id="evidence-family:invented-guidance",
        source_release_ids=[guidance_release],
        source_assertion_ids=[item.source_assertion_id for item in source_assertions],
        dependency_type="primary",
        primary_reference="invented-guidance:test-v2",
    )
    dependencies = [
        SourceDependency(
            source_dependency_id=stable_id("source_dependency", release.source_release_id),
            source_release_id=release.source_release_id,
            upstream_reference=release.source_release_id,
            dependency_type="primary",
            evidence="Synthetic primary fixture",
        )
        for release in source_releases
    ]
    knowledge = CanonicalKnowledgeV2(
        source_releases=source_releases,
        source_artifacts=source_artifacts,
        source_records=source_records,
        concepts=concepts,
        designations=designations,
        external_identifiers=external_identifiers,
        hierarchy_edges=hierarchy_edges,
        concept_mappings=concept_mappings,
        source_assertions=source_assertions,
        canonical_assertions=list(canonical_assertions.values()),
        assertion_derivations=derivations,
        evidence_families=[evidence_family],
        source_dependencies=dependencies,
    )
    return registry, knowledge


@pytest.fixture
def synthetic_v2(tmp_path):
    registry, knowledge = synthetic_registry_and_knowledge_v2(tmp_path)
    return tmp_path, registry, knowledge
