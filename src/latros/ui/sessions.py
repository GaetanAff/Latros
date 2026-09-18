"""Atomic local persistence for resumable, non-versioned R&D sessions."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, safe_id, write_json
from latros.ui.models import (
    ResearchSession,
    SessionRunReference,
    StoredRun,
)


def _now() -> datetime:
    return datetime.now(UTC)


class SessionStore:
    """Store current state plus immutable result history under ``sessions/``."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.sessions_root = self.root / "sessions"
        self._lock = threading.RLock()

    def create(self, display_name: str) -> ResearchSession:
        with self._lock:
            session_id = f"session-{uuid.uuid4()}"
            case_id = f"case-{uuid.uuid4()}"
            now = _now()
            session = ResearchSession(
                session_id=session_id,
                display_name=display_name,
                created_at=now,
                updated_at=now,
                revision=0,
                clinical_case=ClinicalCaseV2(case_id=case_id),
            )
            path = self._session_path(session_id)
            if path.exists():  # pragma: no cover - UUID collision protection
                raise LatrosError("Generated session identifier already exists")
            write_json(path, session.model_dump(mode="json"))
            return session

    def list(self) -> list[ResearchSession]:
        if not self.sessions_root.is_dir():
            return []
        sessions = [
            ResearchSession.model_validate_json(path.read_bytes())
            for path in self.sessions_root.glob("*/session.json")
        ]
        return sorted(sessions, key=lambda item: (item.updated_at, item.session_id), reverse=True)

    def load(self, session_id: str) -> ResearchSession:
        path = self._session_path(session_id)
        if not path.is_file():
            raise LatrosError(f"Unknown local research session: {session_id}")
        return ResearchSession.model_validate_json(path.read_bytes())

    def update(
        self,
        session_id: str,
        expected_revision: int,
        change: Callable[[ResearchSession], ResearchSession],
    ) -> ResearchSession:
        with self._lock:
            current = self.load(session_id)
            self._require_revision(current, expected_revision)
            changed = change(current)
            if changed.session_id != current.session_id or changed.created_at != current.created_at:
                raise LatrosError("Session identity is immutable")
            updated = changed.model_copy(
                update={"revision": current.revision + 1, "updated_at": _now()}
            )
            write_json(self._session_path(session_id), updated.model_dump(mode="json"))
            return updated

    def record_run(
        self,
        session_id: str,
        expected_revision: int,
        operation: Literal["diagnose", "question"],
        result: dict[str, Any],
    ) -> tuple[ResearchSession, StoredRun]:
        with self._lock:
            current = self.load(session_id)
            self._require_revision(current, expected_revision)
            if current.selection is None:
                raise LatrosError("Select a compatible snapshot and strategy before running")
            receipt = result.get("run_receipt")
            if not isinstance(receipt, dict) or not isinstance(receipt.get("receipt_id"), str):
                raise LatrosError("A v2 run receipt is required for session history")
            counter = current.run_counter + 1
            receipt_id = str(receipt["receipt_id"])
            receipt_token = receipt_id.split(":", 1)[-1]
            run_id = f"{counter:06d}-{operation}-{receipt_token}"
            safe_id(run_id)
            created = _now()
            run = StoredRun(
                run_id=run_id,
                session_id=session_id,
                operation=operation,
                created_at=created,
                session_revision=current.revision,
                selection=current.selection,
                clinical_case=current.clinical_case,
                result=result,
            )
            reference = SessionRunReference(
                run_id=run_id,
                operation=operation,
                created_at=created,
                receipt_id=receipt_id,
            )
            updates: dict[str, Any] = {
                "run_counter": counter,
                "revision": current.revision + 1,
                "updated_at": created,
            }
            updates["latest_diagnose" if operation == "diagnose" else "latest_question"] = reference
            updated = current.model_copy(update=updates)
            run_path = self._run_path(session_id, run_id)
            if run_path.exists():
                raise LatrosError("Immutable session run already exists")
            write_json(run_path, run.model_dump(mode="json"))
            try:
                write_json(self._session_path(session_id), updated.model_dump(mode="json"))
            except Exception:
                run_path.unlink(missing_ok=True)
                raise
            return updated, run

    def load_run(self, session_id: str, run_id: str) -> StoredRun:
        path = self._run_path(session_id, run_id)
        if not path.is_file():
            raise LatrosError(f"Unknown immutable session run: {run_id}")
        return StoredRun.model_validate_json(path.read_bytes())

    @staticmethod
    def _require_revision(session: ResearchSession, expected: int) -> None:
        if session.revision != expected:
            raise LatrosError(
                f"Session revision conflict: expected {expected}, current {session.revision}"
            )

    def _session_path(self, session_id: str) -> Path:
        safe_id(session_id)
        return self.sessions_root / session_id / "session.json"

    def _run_path(self, session_id: str, run_id: str) -> Path:
        safe_id(session_id)
        safe_id(run_id)
        return self.sessions_root / session_id / "runs" / f"{run_id}.json"
