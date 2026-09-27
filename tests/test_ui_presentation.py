"""Display translations/aliases cannot change scientific concepts or results."""

import copy
import hashlib
import runpy
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from latros.application.service import ResearchApplicationService
from latros.common import LatrosError
from latros.knowledge.models_v2 import DesignationV2
from latros.knowledge.presentation_repository import (
    ObservationPresentationRepository,
    load_display_lexicon,
    normalize_search,
)
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2
from latros.knowledge.store_v2 import build_snapshot_v2, snapshot_path_v2
from latros.ui.server import create_app


@pytest.fixture
def display_snapshot(synthetic_v2):
    root, registry, knowledge = synthetic_v2
    lexicon = load_display_lexicon()
    codes = ("HP:0031417", "HP:0033050", "HP:0002027", "HP:0002321")
    for index, code in enumerate(codes, 1):
        concept_id = f"test:finding-{index}"
        entry = next(row for row in lexicon["entries"] if row["code"] == code)
        for concept in knowledge.concepts:
            if concept.concept_id == concept_id:
                concept.primary_code = code
        for identifier in knowledge.external_identifiers:
            if identifier.concept_id == concept_id:
                identifier.code = code
                identifier.system = lexicon["system"]
        for designation in knowledge.designations:
            if designation.concept_id == concept_id:
                designation.text = entry["source_label"]
    release = knowledge.designations[0].source_release_id
    knowledge.designations.append(
        DesignationV2(
            designation_id="test:alternate",
            concept_id="test:finding-1",
            text="Nasal discharge",
            language="en",
            scope="hasExactSynonym",
            source_release_id=release,
        )
    )
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    return root, knowledge


@pytest.mark.parametrize(
    "queries,code",
    [
        (("nez qui coule", "Schnupfen", "runny nose"), "HP:0031417"),
        (("mal à la gorge", "Halsschmerzen", "sore throat"), "HP:0033050"),
        (("mal au ventre", "Bauchschmerzen", "stomach pain"), "HP:0002027"),
        (("tête qui tourne", "mir ist schwindelig", "dizzy"), "HP:0002321"),
    ],
)
def test_multilingual_same_supported_id(display_snapshot, queries, code):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        repository = ObservationPresentationRepository(base)
        ids = []
        for language, query in zip(("fr", "de", "en"), queries, strict=True):
            row = repository.search(query, language, 12)[0]
            assert row["code"] == code
            assert row["display_language"] == language
            assert not row["fallback_english"]
            ids.append(row["concept_id"])
        assert len(set(ids)) == 1


def test_synonyms_accents_plural_prefix_tokens_fuzzy_prudent(display_snapshot):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        repository = ObservationPresentationRepository(base)
        for query in ("RHINORRHÉE", "rhinorrhees", "nez-qui-coule", "nez coule", "nez qui"):
            assert repository.search(query, "fr", 12)[0]["code"] == "HP:0031417"
        assert repository.search("nasal discharge", "fr", 12)[0]["code"] == "HP:0031417"
        assert repository.search("runnny nose", "en", 12)[0]["match_rank"] == 4
        assert repository.search("unrelated distant term", "en", 12) == []
        assert repository.search("", "en", 12) == []
        assert repository.search("pain", "en", 1)  # Strict limit, no preload.
        assert len(repository.search("pain", "en", 1)) == 1
        with pytest.raises(LatrosError, match="limit"):
            repository.search("pain", "en", 51)


def test_local_source_language_precedence_and_visible_fallback(synthetic_v2):
    root, registry, knowledge = synthetic_v2
    knowledge.designations.append(
        DesignationV2(
            designation_id="test:french",
            concept_id="test:finding-1",
            text="Libellé source français",
            language="fr",
            scope="preferred",
            source_release_id=knowledge.designations[0].source_release_id,
        )
    )
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        repository = ObservationPresentationRepository(base)
        french = repository.display_labels(["test:finding-1"], "fr")["test:finding-1"]
        assert french["display_label"] == "Libellé source français"
        assert french["display_origin"] == "source_designation"
        german = repository.display_labels(["test:finding-1"], "de")["test:finding-1"]
        assert german["fallback_english"]
        assert german["display_language"] == "en"
        assert repository.search("libelle source", "fr", 12)[0]["concept_id"] == "test:finding-1"


def test_fuzzy_collision_rejected_missing_wrong_identity_not_mapped(display_snapshot):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        repository = ObservationPresentationRepository(base)
        repository.search("runny nose", "en", 12)
        base.connection.execute(
            "INSERT INTO ui_search_terms VALUES ('test:finding-2','en','runny noses',"
            "'ui_alias','runny nose')"
        )
        assert repository.search("runnny nose", "en", 12) == []
        # Unsupported/missing HPO entries do not fabricate a concept or finding.
        assert repository.search("headache", "en", 12) == []
        base.connection.execute("UPDATE ui_observations SET kind='exam' WHERE code='HP:0002321'")
        assert repository.search("dizzy", "en", 12)[0]["observation_kind"] == "exam"


def test_offline_http_same_scientific_question_run_and_snapshot(display_snapshot, monkeypatch):
    root, _ = display_snapshot
    original_connect = socket.socket.connect

    def blocked(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError("External network forbidden")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    runtime = snapshot_path_v2(root, "test-v2")
    before = hashlib.sha256(runtime.read_bytes()).hexdigest()
    with TestClient(create_app(root)) as client:
        service: ResearchApplicationService = client.app.state.service
        # A synthetic case; no real patients or medical validation.
        from test_general_v1_lazy import _case

        scientific = service.next_question("test-v2", _case(), "general_v1", "v2")
        original = copy.deepcopy(scientific.model_dump(mode="json"))
        assert original["question"] is not None
        question = original["question"]
        params = {"snapshot": "test-v2", "strategy": "general_v1"}
        for language in ("fr", "de", "en"):
            rows = client.get(
                "/internal/v1/presentation/concepts",
                params={
                    **params,
                    "q": {"fr": "nez qui coule", "de": "Schnupfen", "en": "runny nose"}[language],
                    "language": language,
                },
            ).json()["items"]
            assert rows[0]["concept_id"] == "test:finding-1"
            display = client.get(
                "/internal/v1/presentation/question",
                params={
                    **params,
                    "system": question["concept"]["system"],
                    "code": question["concept"]["code"],
                    "language": language,
                },
            ).json()
            assert display["source_concept"]["code"] == question["concept"]["code"]
            assert display["display_language"] == language
            assert scientific.model_dump(mode="json") == original
        assert (
            client.get(
                "/internal/v1/presentation/concepts", params={**params, "language": "xx"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/internal/v1/presentation/concepts", params={**params, "limit": 51}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/internal/v1/presentation/labels", params={**params, "ids": ["x"] * 101}
            ).status_code
            == 400
        )
        assert client.get("/expert").status_code == 200
        assert client.get("/assets/i18n.js").status_code == 200
    assert hashlib.sha256(runtime.read_bytes()).hexdigest() == before


def test_alias_lexicon_unambiguous_and_presentation_only():
    lexicon = load_display_lexicon()
    assert lexicon["role"] == "display_and_explicit_selection_only"
    assert len(lexicon["entries"]) == 150
    assert normalize_search("TÊTE-qui-tourne") == "tete qui tourne"
    assert normalize_search("Übelkeit") == "ubelkeit"
    assert normalize_search("groß") == "gross"


def test_translation_review_export_is_deterministic_and_has_no_decisions(display_snapshot):
    review_rows = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/export_ui_translation_review.py")
    )["review_rows"]

    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        repository = ObservationPresentationRepository(base)
        first = review_rows(repository)
        assert first == review_rows(repository)
        assert len({row["concept_id"] for row in first}) == len(first)
        for row in first:
            assert row["language_reviewer"] is None
            assert row["decision_fr"] is None
            assert row["decision_de"] is None
        with pytest.raises(LatrosError, match="100"):
            repository.resolve_supported_codes(repository.lexicon["system"], ["HP:0031417"] * 101)


def test_new_translation_drafts_have_provenance_not_human_approval():
    lexicon = load_display_lexicon()
    drafts = [row for row in lexicon["entries"] if "translation_provenance" in row]
    assert len(drafts) == 80
    for row in drafts:
        provenance = row["translation_provenance"]
        assert provenance["status"] == "editorial_draft_requires_human_language_review"
        assert provenance["reviewer"] is None
        assert provenance["clinical_knowledge"] is False
