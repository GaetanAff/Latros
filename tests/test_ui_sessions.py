from pathlib import Path

import pytest

from latros.common import LatrosError
from latros.ui.models import SessionSelection
from latros.ui.sessions import SessionStore

PROFILE_HASH = "a" * 64


def _selected(session):
    return session.model_copy(
        update={
            "selection": SessionSelection(
                snapshot_id="test",
                strategy_id="semantic_v1",
                profile_id="semantic_v1-default",
                profile_sha256=PROFILE_HASH,
            )
        }
    )


def test_sessions_are_resumable_and_runs_are_immutable(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = store.create("Investigation locale")
    selected = store.update(session.session_id, 0, _selected)
    result = {
        "schema_version": 2,
        "run_receipt": {"receipt_id": f"run_receipt:{'b' * 64}"},
    }

    updated, run = store.record_run(selected.session_id, 1, "diagnose", result)

    assert updated.revision == 2
    assert updated.latest_diagnose is not None
    assert store.load(updated.session_id) == updated
    assert store.load_run(updated.session_id, run.run_id) == run
    assert (tmp_path / "sessions" / updated.session_id / "session.json").is_file()
    assert len(list((tmp_path / "sessions" / updated.session_id / "runs").glob("*.json"))) == 1


def test_session_revision_conflicts_and_path_traversal_are_refused(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = store.create("Conflit")

    with pytest.raises(LatrosError, match="revision conflict"):
        store.update(session.session_id, 1, _selected)
    with pytest.raises(LatrosError, match="Invalid identifier"):
        store.load("../outside")


def test_session_directory_is_local_and_not_created_until_first_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)

    assert store.list() == []
    assert not (tmp_path / "sessions").exists()

    store.create("Locale")
    assert (tmp_path / "sessions").is_dir()
