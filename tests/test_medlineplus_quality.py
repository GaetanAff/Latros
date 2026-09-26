"""Deterministic, offline extraction-role checks; none are clinical approvals."""

from __future__ import annotations

import pytest

from latros.knowledge.candidates import CandidateAssertion, ExtractionProvenance
from latros.knowledge.medlineplus import MedlinePlusTopicRecord
from latros.knowledge.medlineplus_quality import (
    classify_candidate,
    overlapping_hpo_term,
    visible_occurrences,
)


def _case(
    title: str, finding: str, summary: str
) -> tuple[CandidateAssertion, MedlinePlusTopicRecord]:
    topic = MedlinePlusTopicRecord(
        topic_id="123",
        title=title,
        language="English",
        url="https://medlineplus.gov/example.html",
        summaries=[summary],
        source_locator="health-topic[@id='123']",
    )
    candidate = CandidateAssertion(
        candidate_assertion_id="candidate-test",
        source_release_id="medlineplus:2026-09-19",
        source_record_id="record-test",
        source_locator=f"health-topic[@id='123']/full-summary[1]/{finding}",
        artifact_sha256=["0" * 64],
        subject_text=title,
        subject_type="condition",
        predicate="has_symptom",
        object_text=finding,
        object_type="phenotype",
        evidence_family="family-test",
        dependency_group="dependency-test",
        extraction=ExtractionProvenance(
            extractor_id="historical-exact-term",
            extractor_version="1",
            method="rule_based",
        ),
    )
    return candidate, topic


@pytest.mark.parametrize(
    ("title", "finding", "summary", "status", "rule"),
    [
        (
            "Tonsillitis",
            "right",
            "<p>Get help right away.</p>",
            "reject_from_auto_extraction",
            "laterality_modifier",
        ),
        (
            "Common Cold",
            "chronic",
            "<p>People with chronic medical conditions may be at risk.</p>",
            "reject_from_auto_extraction",
            "temporal_modifier",
        ),
        (
            "Sinusitis",
            "acute",
            "<p>Acute sinusitis is one type.</p>",
            "reject_from_auto_extraction",
            "temporal_modifier",
        ),
        (
            "Sinusitis",
            "recurrent",
            "<p>Recurrent sinusitis can occur.</p>",
            "reject_from_auto_extraction",
            "temporal_modifier",
        ),
        (
            "Nasal Cancer",
            "cancer",
            "<p>There are different types of cancer.</p>",
            "reject_from_auto_extraction",
            "disease_self_reference",
        ),
        (
            "Atrial Fibrillation",
            "frequent",
            "<h2>Symptoms</h2><p>Symptoms may be more frequent.</p>",
            "reject_from_auto_extraction",
            "generic_descriptor",
        ),
        (
            "Infectious Arthritis",
            "arthritis",
            "<p>Symptoms of infectious arthritis include pain.</p>",
            "reject_from_auto_extraction",
            "disease_self_reference",
        ),
        (
            "Aphasia",
            "expressive aphasia",
            "<h2>Types</h2><p>Expressive aphasia is a form.</p>",
            "reject_from_auto_extraction",
            "disease_self_reference",
        ),
        (
            "Cold",
            "fever",
            "<p>Cold does not cause fever.</p>",
            "needs_human_review",
            "negation_context",
        ),
        (
            "Cold",
            "fever",
            "<h2>Family history</h2><p>Family history of fever is relevant.</p>",
            "needs_human_review",
            "family_history_context",
        ),
        (
            "Cold",
            "fever",
            "<p>It may be confused with conditions that cause fever.</p>",
            "needs_human_review",
            "differential_context",
        ),
        (
            "Cold",
            "fever",
            "<h2>Screening</h2><p>Test for fever.</p>",
            "needs_human_review",
            "procedure_section",
        ),
        (
            "Cold",
            "fever",
            "<h2>Treatment</h2><p>Medicines may reduce fever.</p>",
            "needs_human_review",
            "treatment_section",
        ),
        (
            "Cold",
            "fever",
            "<h2>Prevention</h2><p>Avoid fever.</p>",
            "needs_human_review",
            "prevention_section",
        ),
        (
            "Cold",
            "fever",
            "<p>The risk of fever is greater.</p>",
            "needs_human_review",
            "risk_sentence",
        ),
        (
            "Cold",
            "fever",
            "<h2>Types</h2><p>One type includes fever.</p>",
            "needs_human_review",
            "classification_section",
        ),
        (
            "Cold",
            "fever",
            '<p><a href="https://example.org/fever">More information</a></p>',
            "needs_human_review",
            "not_in_visible_text",
        ),
        (
            "Tonsillitis",
            "fever",
            "<h2>Symptoms</h2><ul><li>Fever</li></ul>",
            "auto_keep",
            "explicit_manifestation_context",
        ),
        (
            "Common Cold",
            "runny nose",
            "<h2>Symptoms</h2><p>Runny nose</p>",
            "auto_keep",
            "explicit_manifestation_context",
        ),
        (
            "Motion Sickness",
            "nausea",
            "<p>It can then lead to dizziness and nausea and vomiting.</p>",
            "auto_keep",
            "explicit_manifestation_context",
        ),
        (
            "Motion Sickness",
            "dizziness",
            "<p>It can then lead to dizziness and nausea and vomiting.</p>",
            "auto_keep",
            "explicit_manifestation_context",
        ),
        (
            "Cold",
            "fever",
            "<p>No fever occurs.</p><h2>Symptoms</h2><p>Fever may occur.</p>",
            "auto_keep",
            "explicit_manifestation_context",
        ),
        (
            "Cold",
            "fever",
            "<p>The risk is high. These include fever.</p>",
            "needs_human_review",
            "descriptive_without_manifestation",
        ),
        (
            "Cold",
            "fever",
            "<ul><li>Your risk is higher. These include fever.</li></ul>",
            "needs_human_review",
            "risk_sentence",
        ),
    ],
)
def test_context_filter(title: str, finding: str, summary: str, status: str, rule: str) -> None:
    candidate, topic = _case(title, finding, summary)
    decision = classify_candidate(candidate, topic)
    assert (decision.status, decision.rule_id) == (status, rule)
    assert candidate.review_status == "unreviewed"
    assert candidate.polarity == "present"


def test_hpo_overlap_is_recorded_not_automatically_rejected() -> None:
    candidate, topic = _case(
        "Motion Sickness", "nausea", "<p>It can lead to nausea and vomiting.</p>"
    )
    assert overlapping_hpo_term("nausea", {"nausea", "nausea and vomiting"})
    decision = classify_candidate(candidate, topic, other_phrases={"nausea and vomiting"})
    assert decision.status == "auto_keep"
    assert "overlapping_hpo_term" in decision.signals


def test_condition_designation_cannot_become_auto_symptom() -> None:
    candidate, topic = _case(
        "Ankylosing Spondylitis",
        "psoriasis",
        "<h2>Symptoms</h2><p>Skin rashes, such as psoriasis.</p>",
    )
    decision = classify_candidate(candidate, topic, condition_terms={"psoriasis"})
    assert (decision.status, decision.rule_id) == (
        "needs_human_review",
        "condition_example_or_subtype",
    )


def test_condition_term_in_explicit_manifestation_is_not_blanket_rejected() -> None:
    candidate, topic = _case(
        "Kidney Disease", "anemia", "<h2>Symptoms</h2><p>Symptoms include anemia.</p>"
    )
    assert classify_candidate(candidate, topic, condition_terms={"anemia"}).status == "auto_keep"


def test_repeated_occurrences_and_markup_are_not_duplicate_matches() -> None:
    candidate, topic = _case(
        "Cold", "fever", "<p>Fever is a symptom.</p><p>Fever is another symptom.</p>"
    )
    assert len(visible_occurrences(topic, 0, candidate.object_text)) == 2
    assert classify_candidate(candidate, topic).status == "auto_keep"


def test_review_context_points_to_the_rule_trigger_not_first_occurrence() -> None:
    candidate, topic = _case(
        "Cold",
        "fever",
        "<p>Fever is mentioned.</p><h2>Screening</h2><p>Test for fever.</p>",
    )
    decision = classify_candidate(candidate, topic)
    assert decision.rule_id == "procedure_section"
    assert decision.section == "Screening"
    assert decision.context == "Test for fever."
