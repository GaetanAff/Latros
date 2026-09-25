"""Safety invariants for the offline, unreviewed v0.7-G review export."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def review_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("prepare_v07_g_review")


def test_mapping_review_never_prepopulates_human_decision(review_module: ModuleType) -> None:
    blocked = {
        "topic_id": "10",
        "title": "Example condition",
        "source_label": "Example condition",
        "synonyms": ["Example alias"],
        "mesh_headings": [{"descriptor_id": "D000001"}],
        "candidate_count": 3,
        "mapping_status": "ambiguous",
        "mapping_relation": "unresolved",
        "source_record_id": "record:10",
        "locator": "health-topic[@id='10']",
        "url": "https://example.invalid/topic",
        "artifact_ids": ["artifact:1"],
    }
    resolved = {**blocked, "topic_id": "11", "mapping_status": "resolved"}
    suggestion = {
        "code": "MONDO:1",
        "label": "Example condition",
        "lexical_basis": "title",
        "mesh_basis": "MESH:D000001 (unresolved/unresolved)",
    }
    rows = review_module._g1_rows([blocked, resolved], {"10": [suggestion]})
    assert len(rows) == 1
    assert rows[0]["hypothesis_type"] == "lexical_plus_mesh_review"
    assert rows[0]["current_mapping_status"] == "ambiguous"
    assert rows[0]["current_mapping_relation"] == "unresolved"
    assert rows[0]["human_mapping_decision"] == ""
    assert rows[0]["human_reviewer_id"] == ""


def test_csv_review_cells_cannot_execute_spreadsheet_formulas(review_module: ModuleType) -> None:
    assert review_module._csv_value("=HYPERLINK('bad')") == "'=HYPERLINK('bad')"
    assert review_module._csv_value("@code") == "'@code"
    assert review_module._csv_value("ordinary label") == "ordinary label"
    assert review_module._csv_value(0) == 0


def test_label_normalization_is_technical_only(review_module: ModuleType) -> None:
    assert review_module._normalize_label("Épilepsie – rare") == "epilepsie rare"
    assert review_module._normalize_label("  Maladie   A  ") == "maladie a"
