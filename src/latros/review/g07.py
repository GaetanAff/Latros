"""Local, append-only human review of the immutable v0.7-G1/G2 exports."""

from __future__ import annotations

import csv
import hashlib
import os
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import orjson
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from latros.common import LatrosError

SNAPSHOT = "v0.7.0-general-dev-unreviewed"
SNAPSHOT_SHA256 = "bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0"
EXPORTS = {
    "g1": (
        "g1-mapping-review.csv",
        "bc85491cdec33ca32d551e6a2c0b308646843a72dd99f8e38e813a79785d6bcf",
    ),
    "g2_medline": (
        "g2-medline-assertion-review.csv",
        "ff2bf6bea15950f3d4463bb51daaee6a6753b4e50462a6e7974423e44f677ddb",
    ),
    "g2_upstream": (
        "g2-upstream-dependency-review.csv",
        "3c3eb46452cfadfa902cc057ee552ffb5878627a1122be71c9654c5344fd46e2",
    ),
}
MAPPING_ACTIONS = {
    "approve_exact",
    "approve_equivalent",
    "reject",
    "ambiguous",
    "invalid_candidate",
}
ASSERTION_ACTIONS = {"approve_for_review", "reject", "ambiguous", "invalid_candidate"}
ASSET_ROOT = Path(__file__).resolve().parent / "assets"
LOGO = Path(__file__).resolve().parents[1] / "ui/assets/latros-logo.svg"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: dict[str, Any]) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: Literal["g1", "g2_medline", "g2_upstream"]
    index: int = Field(ge=0)
    row_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: Literal[
        "approve_exact",
        "approve_equivalent",
        "approve_for_review",
        "reject",
        "ambiguous",
        "invalid_candidate",
    ]
    reviewer_name: str = Field(min_length=3, max_length=160)
    reviewer_id: str = Field(min_length=2, max_length=160)
    attests_identity: Literal[True]
    comment: str = Field(default="", max_length=2000)


class ReviewStore:
    """Read pinned exports and maintain a hash-chained local audit log."""

    def __init__(
        self,
        root: Path,
        exports_dir: Path,
        *,
        expected_exports: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        staging = (root / "data/staging").resolve()
        self.exports_dir = exports_dir.resolve()
        if not self.exports_dir.is_relative_to(staging):
            raise LatrosError("Review exports must remain under data/staging")
        self.expected_exports = expected_exports if expected_exports is not None else EXPORTS
        summary_path = self.exports_dir / "summary.json"
        summary = orjson.loads(summary_path.read_bytes())
        if summary.get("snapshot") != SNAPSHOT or summary.get("snapshot_sha256") != SNAPSHOT_SHA256:
            raise LatrosError("Review export is not for the pinned v0.7 snapshot")
        self.rows: dict[str, list[dict[str, str]]] = {}
        self.row_ids: dict[str, list[str]] = {}
        self.hashes: dict[str, str] = {}
        for dataset, (filename, expected_hash) in self.expected_exports.items():
            path = self.exports_dir / filename
            actual = _digest(path.read_bytes())
            if actual != expected_hash or summary.get("files_sha256", {}).get(filename) != actual:
                raise LatrosError(f"Review export hash mismatch: {filename}")
            with path.open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            if any(
                any(value for key, value in row.items() if key.startswith("human_")) for row in rows
            ):
                raise LatrosError(
                    f"Review decisions must not be embedded in source CSV: {filename}"
                )
            self.rows[dataset] = rows
            self.row_ids[dataset] = [
                _digest(_canonical({"dataset": dataset, "index": index, "row": row}))
                for index, row in enumerate(rows)
            ]
            self.hashes[filename] = actual
        self.audit_path = self.exports_dir / "review-events.jsonl"
        self.lock = threading.RLock()
        self._events()  # Fail closed if an existing audit log is incomplete or altered.

    def _assert_exports_unchanged(self) -> None:
        for filename, expected_hash in self.hashes.items():
            path = self.exports_dir / filename
            if not path.is_file() or _digest(path.read_bytes()) != expected_hash:
                raise LatrosError(f"Review export changed after startup: {filename}")

    def _events(self) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        content = self.audit_path.read_bytes()
        if content and not content.endswith(b"\n"):
            raise LatrosError("Review audit log has an incomplete final line")
        events: list[dict[str, Any]] = []
        previous = "0" * 64
        for sequence, line in enumerate(content.splitlines(), 1):
            event: dict[str, Any] = orjson.loads(line)
            claimed_hash = event.pop("event_hash", None)
            if (
                event.get("sequence") != sequence
                or event.get("previous_hash") != previous
                or claimed_hash != _digest(_canonical(event))
            ):
                raise LatrosError("Review audit chain is invalid")
            dataset = event.get("dataset")
            index = event.get("index")
            if (
                dataset not in self.rows
                or not isinstance(index, int)
                or index < 0
                or index >= len(self.rows[dataset])
                or event.get("row_id") != self.row_ids[dataset][index]
            ):
                raise LatrosError("Review audit row no longer matches the pinned export")
            event["event_hash"] = claimed_hash
            events.append(event)
            previous = claimed_hash
        return events

    def metadata(self) -> dict[str, Any]:
        with self.lock:
            self._assert_exports_unchanged()
            latest = {(item["dataset"], item["row_id"]) for item in self._events()}
            return {
                "snapshot": SNAPSHOT,
                "snapshot_sha256": SNAPSHOT_SHA256,
                "datasets": {
                    dataset: {
                        "count": len(rows),
                        "decided": sum(key == dataset for key, _ in latest),
                    }
                    for dataset, rows in self.rows.items()
                },
            }

    def item(self, dataset: str, index: int) -> dict[str, Any]:
        if dataset not in self.rows or index < 0 or index >= len(self.rows[dataset]):
            raise LatrosError("Unknown review item")
        with self.lock:
            self._assert_exports_unchanged()
            events = [
                item
                for item in self._events()
                if item["dataset"] == dataset and item["index"] == index
            ]
        return {
            "dataset": dataset,
            "index": index,
            "count": len(self.rows[dataset]),
            "row_id": self.row_ids[dataset][index],
            "row": self.rows[dataset][index],
            "history": events,
            "allowed_actions": sorted(MAPPING_ACTIONS if dataset == "g1" else ASSERTION_ACTIONS),
        }

    def record(self, decision: DecisionInput) -> dict[str, Any]:
        dataset = decision.dataset
        index = decision.index
        if index >= len(self.rows[dataset]) or decision.row_id != self.row_ids[dataset][index]:
            raise LatrosError("Review item changed or is stale")
        allowed = MAPPING_ACTIONS if dataset == "g1" else ASSERTION_ACTIONS
        if decision.action not in allowed:
            raise LatrosError("Decision action is not valid for this review set")
        if dataset == "g1" and decision.action in {"approve_exact", "approve_equivalent"}:
            if not self.rows[dataset][index].get("candidate_disease_code"):
                raise LatrosError("A mapping cannot be approved without a proposed disease code")
        if not decision.reviewer_name.strip() or not decision.reviewer_id.strip():
            raise LatrosError("Real reviewer name and identifier are required")
        with self.lock:
            self._assert_exports_unchanged()
            events = self._events()
            event: dict[str, Any] = {
                "sequence": len(events) + 1,
                "previous_hash": events[-1]["event_hash"] if events else "0" * 64,
                "dataset": dataset,
                "index": index,
                "row_id": decision.row_id,
                "source_csv_sha256": self.hashes[self.expected_exports[dataset][0]],
                "action": decision.action,
                "reviewer_name": decision.reviewer_name.strip(),
                "reviewer_id": decision.reviewer_id.strip(),
                "attests_identity": True,
                "comment": decision.comment.strip(),
                "timestamp_utc": datetime.now(UTC).isoformat(),
            }
            event["event_hash"] = _digest(_canonical(event))
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("ab") as stream:
                stream.write(_canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            return event

    def export(self) -> bytes:
        with self.lock:
            self._assert_exports_unchanged()
            events = self._events()
        current = {(item["dataset"], item["row_id"]): item for item in events}
        payload = {
            "schema_version": 1,
            "snapshot": SNAPSHOT,
            "snapshot_sha256": SNAPSHOT_SHA256,
            "source_exports_sha256": self.hashes,
            "events": events,
            "current_decisions": [
                current[key] for key in sorted(current, key=lambda value: (value[0], value[1]))
            ],
            "clinical_validation": False,
            "publishable": False,
            "applies_to_snapshot": False,
        }
        return _canonical(payload) + b"\n"


def create_review_app(
    root: Path,
    exports_dir: Path,
    *,
    expected_exports: dict[str, tuple[str, str]] | None = None,
) -> FastAPI:
    """Create a separate local review app; no Latros runtime or snapshot write path."""
    store = ReviewStore(root, exports_dir, expected_exports=expected_exports)
    token = secrets.token_urlsafe(32)
    app = FastAPI(
        title="Latros G1/G2 local human review", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    app.mount("/assets", StaticFiles(directory=str(ASSET_ROOT)), name="assets")

    def require_token(request: Request) -> None:
        supplied = request.headers.get("x-latros-review-token", "")
        if not secrets.compare_digest(supplied, token):
            raise LatrosError("Review token is required")

    @app.middleware("http")
    async def local_headers(request: Request, call_next: Any) -> Any:
        origin = request.headers.get("origin")
        if request.method != "GET" and origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.netloc != request.headers.get("host"):
                return JSONResponse(
                    {"message": "Only same-origin local review is allowed"}, status_code=403
                )
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(LatrosError)
    async def review_error(_request: Request, exc: LatrosError) -> JSONResponse:
        return JSONResponse({"message": str(exc)}, status_code=400)

    @app.get("/", response_class=HTMLResponse)
    async def home() -> HTMLResponse:
        return HTMLResponse((ASSET_ROOT / "review.html").read_text(encoding="utf-8"))

    @app.get("/logo.svg")
    async def logo() -> FileResponse:
        return FileResponse(LOGO, media_type="image/svg+xml")

    @app.get("/api/token")
    async def get_token() -> dict[str, str]:
        return {"token": token}

    @app.get("/api/metadata")
    async def metadata() -> dict[str, Any]:
        return store.metadata()

    @app.get("/api/item")
    async def item(dataset: str, index: int = Query(ge=0)) -> dict[str, Any]:
        return store.item(dataset, index)

    @app.post("/api/decision")
    async def decision(request: Request, payload: DecisionInput) -> dict[str, Any]:
        require_token(request)
        return store.record(payload)

    @app.get("/api/export")
    async def export(request: Request) -> Response:
        require_token(request)
        return Response(
            store.export(),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="latros-v07-g-decisions.json"'},
        )

    return app
