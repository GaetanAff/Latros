"""Navigation-only anatomy cannot create concepts, assertions or clinical decisions."""

import hashlib
import socket
from xml.etree import ElementTree

import orjson
import pytest
from fastapi.testclient import TestClient
from test_ui_presentation import display_snapshot  # noqa: F401

from latros.common import LatrosError
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
    assert config["version"] == "ui-anatomy-3"
    assert sum(node["implemented"] for node in config["nodes"].values()) == 47
    assert config["nodes"]["kidneys"]["parent"] == "urinary"
    assert config["nodes"]["cervical-back"]["parent"] == "back"
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
        assert client.app.state.service._general_cache == {}  # No slow startup warm-up.
        for region in ("body", "head"):
            response = client.get(
                "/internal/v1/presentation/anatomy", params={**params, "region": region}
            )
            assert response.status_code == 200
            if region == "body":
                assert response.json()["items"] == []
            else:
                assert [item["code"] for item in response.json()["items"]] == ["HP:0002321"]
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
            "atlas-overlay.svg",
            "illustrations.json",
            "body-atlas-v1.png",
        ):
            assert client.get("/assets/anatomy/" + filename).status_code == 200
        assert client.get("/expert").status_code == 200
    assert hashlib.sha256(runtime.read_bytes()).hexdigest() == digest


def test_independent_generated_images_and_bounded_overlays():
    config = load_navigation()
    manifest = orjson.loads((CONFIG_PATH.parent / "illustrations.json").read_bytes())
    assert manifest["anatomical_validation"] is False
    assert len(manifest["images"]) == 37
    for image in manifest["images"]:
        assert image["human_reviewer"] is None
        assert image["review_status"] == "not_anatomically_validated"
        assert (
            hashlib.sha256((CONFIG_PATH.parent / image["filename"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    for key in (
        "ear-external",
        "ear-middle",
        "ear-inner",
        "lungs",
        "heart",
        "intestines",
        "urinary",
        "knee",
        "hands",
    ):
        assert config["nodes"][key]["implemented"]
    assert config["nodes"]["lungs"]["image"] != config["nodes"]["body"]["image"]
    assert all(
        node["image"] in {image["filename"] for image in manifest["images"]}
        for node in config["nodes"].values()
    )
    assert "body_site" not in orjson.dumps(config).decode()


def test_modified_image_hash_and_external_navigation_rejected(tmp_path, monkeypatch):
    import shutil

    import latros.ui.anatomy as module

    for file in CONFIG_PATH.parent.iterdir():
        if file.is_file():
            shutil.copyfile(file, tmp_path / file.name)
    monkeypatch.setattr(module, "CONFIG_PATH", tmp_path / "navigation.json")
    path = tmp_path / "body-atlas-v1.png"
    payload = path.read_bytes()
    path.write_bytes(b"x" + payload[1:])
    with pytest.raises(LatrosError, match="integrity"):
        module.load_navigation()
    path.write_bytes(payload)
    config = orjson.loads((tmp_path / "navigation.json").read_bytes())
    config["nodes"]["body"]["image"] = "https://external/atlas.png"
    (tmp_path / "navigation.json").write_bytes(orjson.dumps(config))
    with pytest.raises(LatrosError, match="local"):
        module.load_navigation()


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
        assert f"assets['{module}.js']" in html
        assert (assets / f"{module}.js").exists()
    assert "https://" not in html
    css = (assets / "anatomy.css").read_text(encoding="utf-8")
    assert 'data-theme="dark"' in css
    assert "prefers-reduced-motion" in css
    assert "@media(max-width:800px)" in css
    assert ".region-link.is-hovered" in css
    anatomy_js = (assets / "anatomy.js").read_text(encoding="utf-8")
    assert "function setHoveredRegion(region)" in anatomy_js
    assert "addObservation(item,'present')" in anatomy_js


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
