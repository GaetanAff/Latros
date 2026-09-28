"""Local lexical retrieval is a display-only projection, not NLP or clinical mapping."""

from latros.knowledge.local_search import meaningful_tokens
from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2

pytest_plugins = ("test_ui_presentation",)


def test_bm25_retains_identity_and_safely_rejects_negation(display_snapshot):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        presentation = ObservationPresentationRepository(base)
        expected = presentation.search("nez qui coule", "fr", 5, search_mode="existing")[0]
        for mode in ("bm25", "bm25_fuzzy"):
            result = presentation.search("nez qui coule", "fr", 5, search_mode=mode)[0]
            assert result["concept_id"] == expected["concept_id"]
            assert result["code"] == expected["code"]
            for language, prefix in (
                ("fr", "nez qui cou"),
                ("de", "laufende Na"),
                ("en", "runny n"),
            ):
                partial = presentation.search(prefix, language, 5, search_mode=mode)
                assert partial, (mode, language, prefix)
                assert partial[0]["concept_id"] == expected["concept_id"]
            assert result["display_lexicon_version"] == "ui-display-4"
            assert presentation.search("no fever", "en", 5, search_mode=mode) == []
            assert presentation.search("pas de fièvre", "fr", 5, search_mode=mode) == []
            assert presentation.search("kein Fieber", "de", 5, search_mode=mode) == []
        assert base.connection.execute("SELECT count(*) FROM ui_search_documents").fetchone()[0] > 0


def test_fuzzy_requires_explicit_unique_alias_and_never_expands_negation(display_snapshot):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        presentation = ObservationPresentationRepository(base)
        assert presentation.search("runnny nose", "en", 5, search_mode="bm25") == []
        assert (
            presentation.search("runnny nose", "en", 5, search_mode="bm25_fuzzy")[0]["code"]
            == "HP:0031417"
        )
        assert presentation.search("unrelated distant term", "en", 5) == []
        assert meaningful_tokens("no fever") == []
        assert meaningful_tokens("sans douleur") == []
        assert meaningful_tokens("runny nose") == ["runny", "nose"]


def test_ambiguous_typo_suppressed(display_snapshot):
    root, _ = display_snapshot
    with CanonicalKnowledgeRepositoryV2(root, "test-v2") as base:
        presentation = ObservationPresentationRepository(base)
        presentation.search("runny nose", "en", 5)
        base.connection.execute(
            "INSERT INTO ui_search_terms VALUES ('test:finding-2','en','runny noses',"
            "'ui_alias','runny nose')"
        )
        assert presentation.search("runnny nose", "en", 5) == []
