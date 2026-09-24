from pathlib import Path
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from latros.common import LatrosError
from latros.knowledge.candidates import (
    CandidateAssertion,
    ExtractionProvenance,
    MappingProposal,
    make_candidate_assertion_id,
)
from latros.knowledge.medlineplus import parse_medlineplus_topics


def _mapping(concept_id: str = "concept:test") -> MappingProposal:
    return MappingProposal(
        system="urn:latros:test",
        code="TEST",
        concept_id=concept_id,
        relation="exact",
        status="resolved",
        provenance="invented deterministic test mapping",
    )


def _candidate(**changes: object) -> CandidateAssertion:
    payload: dict[str, object] = {
        "candidate_assertion_id": make_candidate_assertion_id(
            "release:test", "record:test", "section:1", 0
        ),
        "source_release_id": "release:test",
        "source_record_id": "record:test",
        "source_locator": "section:1",
        "artifact_sha256": ["a" * 64],
        "subject_text": "Invented condition",
        "subject_type": "disease",
        "predicate": "has_symptom",
        "object_text": "Invented symptom",
        "object_type": "symptom",
        "evidence_family": "invented-primary",
        "dependency_group": "invented-primary",
        "subject_mapping": _mapping("concept:condition"),
        "object_mapping": _mapping("concept:symptom"),
        "extraction": ExtractionProvenance(
            extractor_id="latros.tests",
            extractor_version="1",
            method="agent",
        ),
        "review_status": "agent_extracted",
        "transformation_chain": ["local fixture", "candidate extraction"],
    }
    payload.update(changes)
    return CandidateAssertion.model_validate(payload)


def test_agent_candidate_is_not_usable_without_review() -> None:
    candidate = _candidate()

    assert candidate.usable is False
    assert candidate.candidate_assertion_id == make_candidate_assertion_id(
        "release:test", "record:test", "section:1", 0
    )


def test_unreviewed_candidate_can_be_technically_eligible_without_being_approved() -> None:
    candidate = _candidate(review_status="unreviewed")

    assert candidate.technically_eligible is True
    assert candidate.usable is False


def test_approved_candidate_requires_reviewers_and_exact_resolved_mappings() -> None:
    with pytest.raises(ValidationError, match="recorded reviewers"):
        _candidate(review_status="approved")

    assert _candidate(review_status="approved", reviewer_ids=["reviewer:test"]).usable is True
    ambiguous = MappingProposal(
        system="urn:latros:test",
        code="TEST",
        relation="unresolved",
        status="ambiguous",
        provenance="invented ambiguous mapping",
    )
    assert (
        _candidate(
            review_status="approved",
            reviewer_ids=["reviewer:test"],
            object_mapping=ambiguous,
        ).usable
        is False
    )


def test_quantity_cannot_be_flattened_or_lose_its_unit() -> None:
    with pytest.raises(ValidationError, match="retained together"):
        _candidate(quantitative_value=84.0)

    candidate = _candidate(
        quantitative_value=84.0,
        unit_system="http://unitsofmeasure.org",
        unit_code="mg/L",
    )
    assert candidate.quantitative_value == 84.0
    assert candidate.unit_code == "mg/L"


def test_medlineplus_full_topic_parser_preserves_record_provenance(tmp_path: Path) -> None:
    xml = tmp_path / "medlineplus.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<health-topics total="1" date-generated="09/19/2026 01:00:00">
  <health-topic title="Invented Topic" url="https://example.test/topic" id="42"
      language="English" date-created="01/02/2003" meta-desc="Invented summary">
    <also-called>Invented synonym</also-called>
    <full-summary><p>Invented text, not approved clinical knowledge.</p></full-summary>
    <group id="1" url="https://example.test/group">Invented group</group>
    <mesh-heading><descriptor id="D000001">Invented MeSH term</descriptor></mesh-heading>
    <related-topic id="43" url="https://example.test/related">Related topic</related-topic>
    <site title="Invented source" url="https://example.test/source">
      <information-category>Start Here</information-category>
      <organization>Invented organization</organization>
      <standard-description>Invented description</standard-description>
    </site>
  </health-topic>
</health-topics>
""",
        encoding="utf-8",
    )

    records = parse_medlineplus_topics(xml)

    assert len(records) == 1
    record = records[0]
    assert record.topic_id == "42"
    assert record.synonyms == ["Invented synonym"]
    assert record.mesh_headings[0].descriptor_id == "D000001"
    assert record.mesh_headings[0].label == "Invented MeSH term"
    assert record.summaries == ["Invented text, not approved clinical knowledge."]
    assert record.related_topics[0].topic_id == "43"
    assert record.related_topics[0].title == "Related topic"
    assert record.links[0].organizations == ["Invented organization"]
    assert record.source_locator == "health-topic[@id='42']"

    zipped = tmp_path / "medlineplus.zip"
    with ZipFile(zipped, "w") as archive:
        archive.write(xml, "mplus_topics_2026-09-19.xml")
    assert parse_medlineplus_topics(zipped) == records


def test_medlineplus_parser_rejects_missing_duplicate_and_external_entities(tmp_path: Path) -> None:
    with pytest.raises(LatrosError, match="missing"):
        parse_medlineplus_topics(tmp_path / "missing.xml")

    duplicate = tmp_path / "duplicate.xml"
    duplicate.write_text(
        """<health-topics>
<health-topic title="One" url="https://example.test/1" id="1" language="English" />
<health-topic title="Two" url="https://example.test/2" id="1" language="English" />
</health-topics>""",
        encoding="utf-8",
    )
    with pytest.raises(LatrosError, match="Duplicate"):
        parse_medlineplus_topics(duplicate)

    empty = tmp_path / "empty.xml"
    empty.write_text("<health-topics />", encoding="utf-8")
    with pytest.raises(LatrosError, match="no health-topic"):
        parse_medlineplus_topics(empty)
