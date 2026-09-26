"""Navigation-only anatomy cannot create concepts, assertions or clinical decisions."""

import hashlib
import socket
from xml.etree import ElementTree

from fastapi.testclient import TestClient
from test_ui_presentation import display_snapshot  # noqa: F401

from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2
from latros.knowledge.store_v2 import build_snapshot_v2, snapshot_path_v2
from latros.ui.anatomy import CONFIG_PATH, load_navigation
from latros.ui.server import create_app


def test_tree_and_local_svg_keyboard_regions():
    config = load_navigation()
    assert config["role"] == "navigation_only_not_clinical_knowledge"
    assert config["nodes"]["head"]["parent"] == "body"
    assert config["nodes"]["sinuses"]["parent"] == "head"
    assert sum(node["implemented"] for node in config["nodes"].values()) == 3
    for asset in ("body-front.svg", "head-front.svg", "sinuses-front.svg"):
        svg = ElementTree.parse(CONFIG_PATH.parent / asset)
        zones = [element for element in svg.iter() if "data-region" in element.attrib]
        assert zones
        assert len({element.attrib["id"] for element in zones}) == len(zones)
        for zone in zones:
            assert zone.attrib["tabindex"] == "0"
            assert zone.attrib["role"] == "button"
            assert zone.attrib["aria-label"]
            assert zone.attrib["data-region"] in config["nodes"]


def test_anatomy_and_search_same_supported_coding_offline(display_snapshot, monkeypatch):  # noqa: F811
    root, _ = display_snapshot
    original_connect = socket.socket.connect

    def blocked(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError("External network forbidden")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    runtime = snapshot_path_v2(root, "test-v2")
    digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
    params = {"snapshot": "test-v2", "strategy": "general_v1"}
    with TestClient(create_app(root)) as client:
        for region in ("body", "head"):
            response = client.get(
                "/internal/v1/presentation/anatomy", params={**params, "region": region}
            )
            assert response.status_code == 200
            assert response.json()["items"] == []
        assert client.app.state.service._general_cache == {}  # No slow warm-up at startup.
        for language, query in (("fr", "nez qui coule"), ("de", "Schnupfen"), ("en", "runny nose")):
            anatomy = client.get(
                "/internal/v1/presentation/anatomy",
                params={**params, "region": "sinuses", "language": language},
            ).json()["items"]
            assert len(anatomy) == 1  # Missing concepts not fabricated or shown.
            search = client.get(
                "/internal/v1/presentation/concepts",
                params={**params, "language": language, "q": query},
            ).json()["items"]
            for key in (
                "concept_id",
                "system",
                "code",
                "label",
                "observation_kind",
                "display_label",
            ):
                assert anatomy[0][key] == search[0][key]
        assert (
            client.get(
                "/internal/v1/presentation/anatomy", params={**params, "region": "invalid"}
            ).status_code
            == 400
        )
        assert (
            client.get(
                "/internal/v1/presentation/anatomy", params={**params, "language": "xx"}
            ).status_code
            == 422
        )
        for filename in (
            "body-front.svg",
            "head-front.svg",
            "sinuses-front.svg",
            "navigation.json",
        ):
            assert client.get("/assets/anatomy/" + filename).status_code == 200
        assert client.get("/expert").status_code == 200
    assert hashlib.sha256(runtime.read_bytes()).hexdigest() == digest


def test_simple_template_modular_permanent_search_and_theme():
    assets = CONFIG_PATH.parent.parent
    html = (assets.parent / "templates/checker.html").read_text(encoding="utf-8")
    assert html.index('id="symptom-search"') > html.index("</main>")
    assert 'id="theme-toggle"' in html
    for module in (
        "state",
        "api",
        "i18n",
        "search",
        "observations",
        "anatomy",
        "questions",
        "results",
        "history",
    ):
        assert f"/assets/{module}.js" in html
        assert (assets / f"{module}.js").exists()
    assert "https://" not in html
    css = (assets / "anatomy.css").read_text(encoding="utf-8")
    assert 'data-theme="dark"' in css
    assert "prefers-reduced-motion" in css
    assert "@media(max-width:800px)" in css


def test_ambiguous_navigation_identifier_fails_closed(display_snapshot, synthetic_v2):  # noqa: F811
    root, knowledge = display_snapshot
    _, registry, _ = synthetic_v2
    # Two actual concepts claim the same external identity; do not choose arbitrarily.
    for identifier in knowledge.external_identifiers:
        if identifier.concept_id == "test:finding-2":
            identifier.code = "HP:0031417"
    build_snapshot_v2(root, registry, "ambiguous-navigation", knowledge)
    with CanonicalKnowledgeRepositoryV2(root, "ambiguous-navigation") as repository:
        presentation = ObservationPresentationRepository(repository)
        assert (
            presentation.navigation_options(presentation.lexicon["system"], ["HP:0031417"], "fr")
            == []
        )
        assert presentation.search("nez qui coule", "fr", 12) == []
