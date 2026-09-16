"""Tiny invented concepts and disorders; no source extracts or patient data."""

import socket
from pathlib import Path

import orjson
import pytest
import yaml
from lxml import etree

from latros.common import sha256
from latros.knowledge.store import build_snapshot
from latros.sources.registry import Registry


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
