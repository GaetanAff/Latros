"""Local, deterministic context audit for MedlinePlus candidate assertions.

This experimental module is deliberately outside the historical v0.7 snapshot
pipeline hash. It never changes canonical knowledge or human review status.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
from lxml import html

from latros.common import LatrosError
from latros.knowledge.candidates import CandidateAssertion
from latros.knowledge.general_factory import _normalize
from latros.knowledge.medlineplus import MedlinePlusTopicRecord

_LOCATOR = re.compile(r"^health-topic\[@id='([^']+)'\]/full-summary\[(\d+)\]/(.+)$")
_TEMPORAL = frozenset(
    {"acute", "chronic", "recurrent", "episodic", "intermittent", "persistent", "progressive"}
)
_LATERALITY = frozenset({"right", "left", "bilateral", "unilateral"})
_GENERIC = frozenset({"severe", "mild", "healthy", "normal", "abnormal", "frequent"})
_DISEASE_NOUNS = frozenset(
    {"cancer", "infection", "disease", "disorder", "syndrome", "tumor", "tumour"}
)
_NEGATION = re.compile(r"\b(?:no|nor|not|never|without|doesn t|don t|can t|cannot|absence of)\b")
_FAMILY_HISTORY = re.compile(r"\b(?:family history|familial history|hereditary risk)\b")
_DIFFERENTIAL = re.compile(
    r"\b(?:confused with|mistaken for|different from|other conditions?|"
    r"other diseases?|differential diagnosis)\b"
)
_PROCEDURE = re.compile(r"\b(?:screen\w*|test\w*|diagnos\w*|scan\w*|imaging)\b")
_TREATMENT = re.compile(r"\b(?:treat\w*|therap\w*|surgery|medicine|medication)\b")
_RISK = re.compile(r"\b(?:risk|more likely to|chance of)\b")
_EXAMPLE_OR_SUBTYPE = re.compile(r"\b(?:such as|for example|examples? include|type of|form of)\b")
_MANIFESTATION = re.compile(
    r"\b(?:symptoms?|signs?|lead to|leads to|can cause|may cause|"
    r"causes|characterized by|experience|experiences|develop|develops|may have|can have|"
    r"often have|often has|results? in|sets? in)\b"
)
_MANIFESTATION_HEADING = re.compile(r"\b(?:symptoms?|signs?|manifestations?)\b")
_CLASSIFICATION = re.compile(r"\b(?:types?|forms?|kinds?|subtypes?|categories)\b")


@dataclass(frozen=True, slots=True)
class TextOccurrence:
    summary_index: int
    section: str
    text: str
    block_tag: str
    matched_phrase: str


@dataclass(frozen=True, slots=True)
class QualityDecision:
    status: str
    rule_id: str
    section: str
    context: str
    signals: tuple[str, ...]


def load_condition_terms(runtime_path: Path) -> set[str]:
    """Use only active disease designations from the same immutable snapshot."""
    with duckdb.connect(str(runtime_path), read_only=True) as connection:
        rows = connection.execute(
            "SELECT DISTINCT json_extract_string(d.payload_json, '$.text') "
            "FROM designation d JOIN concept c ON "
            "json_extract_string(d.payload_json, '$.concept_id')=c.id "
            "WHERE json_extract_string(c.payload_json, '$.kind')='condition' "
            "AND json_extract_string(c.payload_json, '$.status')='active'"
        ).fetchall()
    return {_normalize(text) for (text,) in rows if text}


def locator_parts(candidate: CandidateAssertion) -> tuple[str, int]:
    match = _LOCATOR.fullmatch(candidate.source_locator)
    if match is None or _normalize(match.group(3)) != _normalize(candidate.object_text):
        raise LatrosError("MedlinePlus candidate has an unexpected source locator")
    return match.group(1), int(match.group(2)) - 1


def visible_occurrences(
    topic: MedlinePlusTopicRecord, summary_index: int, phrase: str
) -> list[TextOccurrence]:
    """Match whole normalized terms within visible HTML blocks, never URLs or markup."""
    if summary_index < 0 or summary_index >= len(topic.summaries):
        raise LatrosError("MedlinePlus candidate summary index is out of range")
    root = html.fragment_fromstring(topic.summaries[summary_index], create_parent="div")
    needle = f" {_normalize(phrase)} "
    occurrences: list[TextOccurrence] = []
    section = ""
    preceding_paragraph = ""
    for element in root.iter():
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            section = " ".join(element.text_content().split())
            preceding_paragraph = ""
            continue
        if tag not in {"p", "li"}:
            continue
        # A nested paragraph or list item must not duplicate its parent's text.
        if any(
            ancestor.tag in {"p", "li"}
            for ancestor in element.iterancestors()
            if isinstance(ancestor.tag, str)
        ):
            continue
        block = " ".join(element.text_content().split())
        effective_section = section
        lead_in = _normalize(preceding_paragraph)
        final_lead_sentence = re.split(r"[.!?]", lead_in)[-1]
        section_kind = _normalize(section)
        list_describes_manifestations = bool(
            _MANIFESTATION_HEADING.search(final_lead_sentence)
        ) or (
            preceding_paragraph.rstrip().endswith(":")
            and any(
                cue in final_lead_sentence for cue in ("notice", "affect many organs", "may have")
            )
        )
        if (
            tag == "li"
            and list_describes_manifestations
            and not any(cue in section_kind for cue in ("risk", "treat", "prevent", "caus"))
            and not _CLASSIFICATION.search(lead_in)
        ):
            effective_section = "Symptoms list: " + preceding_paragraph[:120]
        for sentence in re.split(r"(?<=[.!?;])\s+", block):
            if needle in f" {_normalize(sentence)} ":
                occurrences.append(
                    TextOccurrence(
                        summary_index,
                        effective_section,
                        block if tag == "li" else sentence.strip(),
                        tag,
                        _normalize(phrase),
                    )
                )
        if tag == "p":
            preceding_paragraph = block
    return occurrences


def audit_signals(
    candidate: CandidateAssertion,
    topic: MedlinePlusTopicRecord,
    *,
    condition_terms: set[str] | None = None,
) -> tuple[set[str], list[TextOccurrence]]:
    """Return non-exclusive error signals; this function makes no clinical decision."""
    topic_id, summary_index = locator_parts(candidate)
    if topic_id != topic.topic_id or candidate.subject_text != topic.title:
        raise LatrosError("MedlinePlus candidate/source topic mismatch")
    phrase = _normalize(candidate.object_text)
    title = _normalize(topic.title)
    occurrences = visible_occurrences(topic, summary_index, candidate.object_text)
    flags: set[str] = set()
    if phrase in _TEMPORAL:
        flags.add("temporal_modifier")
    if phrase in _LATERALITY:
        flags.add("laterality_modifier")
    if phrase in _GENERIC:
        flags.add("generic_descriptor")
    if (
        phrase == title
        or (phrase in _DISEASE_NOUNS and phrase in title.split())
        or (phrase in title.split() and len(phrase) >= 6)
        or (title in phrase.split() and len(title) >= 6)
    ):
        flags.add("disease_self_reference")
    if phrase in _DISEASE_NOUNS and "disease_self_reference" not in flags:
        flags.add("other_disease_mention")
    if condition_terms is not None and phrase in condition_terms:
        flags.add("condition_term_as_finding")
    if not occurrences:
        flags.add("not_in_visible_text")
    for occurrence in occurrences:
        flags.update(_context_signals(occurrence))
        if "condition_term_as_finding" in flags and _EXAMPLE_OR_SUBTYPE.search(
            _normalize(occurrence.text)
        ):
            flags.add("condition_example_or_subtype")
    return flags, occurrences


def _context_signals(occurrence: TextOccurrence) -> set[str]:
    text = _normalize(occurrence.text)
    section = _normalize(occurrence.section)
    flags: set[str] = set()
    if _negates_finding(text, occurrence):
        flags.add("negation_context")
    if _FAMILY_HISTORY.search(text) or "family history" in section:
        flags.add("family_history_context")
    if _DIFFERENTIAL.search(text) or "differential" in section:
        flags.add("differential_context")
    if _CLASSIFICATION.search(section):
        flags.add("classification_section")
    elif any(value in section for value in ("diagnos", "screen", "test")):
        flags.add("procedure_section")
    elif any(value in section for value in ("treat", "manag", "medicin", "therap")):
        flags.add("treatment_section")
    elif "prevent" in section:
        flags.add("prevention_section")
    elif any(value in section for value in ("risk", "caus")):
        flags.add("risk_or_cause_section")
    elif _MANIFESTATION_HEADING.search(section):
        flags.add("manifestation_section")
    if _PROCEDURE.search(text):
        flags.add("procedure_sentence")
    if _TREATMENT.search(text):
        flags.add("treatment_sentence")
    if _RISK.search(text):
        flags.add("risk_sentence")
    if _MANIFESTATION.search(text):
        flags.add("manifestation_sentence")
    return flags


def _negates_finding(normalized_text: str, occurrence: TextOccurrence) -> bool:
    # A sentence may mention a positive finding before an unrelated clause such
    # as "a runny nose that doesn't get better". Only a nearby preceding cue
    # negates the matched finding; uncertain scope is left to human review.
    words = normalized_text.split()
    needle = occurrence.matched_phrase.split()
    for index in range(len(words) - len(needle) + 1):
        if words[index : index + len(needle)] != needle:
            continue
        before = words[max(0, index - 4) : index]
        if "or" in before:
            before = before[before.index("or") + 1 :]
        if _NEGATION.search(" ".join(before)):
            return True
    return False


def overlapping_hpo_term(phrase: str, other_phrases: set[str]) -> bool:
    """Flag a shorter exact term nested in another match; do not reject it alone."""
    normalized = _normalize(phrase)
    return any(normalized != other and f" {normalized} " in f" {other} " for other in other_phrases)


def classify_candidate(
    candidate: CandidateAssertion,
    topic: MedlinePlusTopicRecord,
    *,
    other_phrases: set[str] | None = None,
    condition_terms: set[str] | None = None,
) -> QualityDecision:
    """Select conservative auto-extraction, never clinical approval or new polarity."""
    flags, occurrences = audit_signals(candidate, topic, condition_terms=condition_terms)
    if other_phrases and overlapping_hpo_term(candidate.object_text, other_phrases):
        flags.add("overlapping_hpo_term")
    first = occurrences[0] if occurrences else TextOccurrence(0, "", "", "", "")
    for rule in (
        "temporal_modifier",
        "laterality_modifier",
        "generic_descriptor",
        "disease_self_reference",
    ):
        if rule in flags:
            return QualityDecision(
                "reject_from_auto_extraction",
                rule,
                first.section,
                first.text,
                tuple(sorted(flags)),
            )
    if "not_in_visible_text" in flags:
        return QualityDecision(
            "needs_human_review", "not_in_visible_text", "", "", tuple(sorted(flags))
        )
    blocked_context = (
        "negation_context",
        "family_history_context",
        "differential_context",
        "procedure_section",
        "treatment_section",
        "prevention_section",
        "risk_or_cause_section",
        "classification_section",
        "procedure_sentence",
        "treatment_sentence",
        "risk_sentence",
    )
    if "other_disease_mention" not in flags and "condition_example_or_subtype" not in flags:
        for occurrence in occurrences:
            local = _context_signals(occurrence)
            if not any(item in local for item in blocked_context) and (
                "manifestation_section" in local or "manifestation_sentence" in local
            ):
                return QualityDecision(
                    "auto_keep",
                    "explicit_manifestation_context",
                    occurrence.section,
                    occurrence.text,
                    tuple(sorted(flags)),
                )
    for rule in ("condition_example_or_subtype", "other_disease_mention", *blocked_context):
        if rule in flags:
            trigger = next(
                (
                    occurrence
                    for occurrence in occurrences
                    if rule in _context_signals(occurrence)
                    or (
                        rule == "condition_example_or_subtype"
                        and _EXAMPLE_OR_SUBTYPE.search(_normalize(occurrence.text))
                    )
                ),
                first,
            )
            return QualityDecision(
                "needs_human_review",
                rule,
                trigger.section,
                trigger.text,
                tuple(sorted(flags)),
            )
    return QualityDecision(
        "needs_human_review",
        "descriptive_without_manifestation",
        first.section,
        first.text,
        tuple(sorted(flags)),
    )
