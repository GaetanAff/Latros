"""Loopback-only FastAPI shell for inspecting existing Latros capabilities."""

from __future__ import annotations

import webbrowser
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from latros import __version__
from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2, QuestionResponseV2
from latros.common import LatrosError
from latros.ui.models import (
    CaseRequest,
    CreateSessionRequest,
    ErrorDocument,
    QuestionAnswerRequest,
    RunRequest,
    SelectionRequest,
    SessionSelection,
)
from latros.ui.sessions import SessionStore

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(root: Path) -> FastAPI:
    """Create an internal transport bound by the launcher to loopback only."""
    resolved_root = root.resolve()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            application.state.service.close()

    app = FastAPI(
        title="Latros R&D local interface",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.service = ResearchApplicationService(resolved_root)
    app.state.sessions = SessionStore(resolved_root)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.mount("/assets", StaticFiles(directory=str(PACKAGE_ROOT / "assets")), name="assets")

    @app.middleware("http")
    async def local_security_headers(request: Request, call_next: Any) -> Any:
        origin = request.headers.get("origin")
        if request.method in MUTATING_METHODS and origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                return _error(403, "origin_refused", "Only a loopback origin is accepted")
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/internal/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(LatrosError)
    async def latros_error(_request: Request, exc: LatrosError) -> JSONResponse:
        status_code = 409 if "revision conflict" in str(exc).lower() else 400
        return _error(status_code, "latros_error", str(exc))

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error(
            422,
            "invalid_request",
            "Request validation failed",
            _validation_details(exc.errors()),
        )

    @app.exception_handler(ValidationError)
    async def model_validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
        return _error(
            422,
            "invalid_contract",
            "Clinical contract validation failed",
            _validation_details(exc.errors()),
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"version": __version__},
        )

    @app.get("/internal/v1/capabilities")
    async def capabilities(request: Request) -> dict[str, Any]:
        return _service(request).capabilities().model_dump(mode="json")

    @app.get("/internal/v1/concepts")
    async def concepts(
        request: Request,
        snapshot: str,
        strategy: str,
        q: str = "",
        limit: int = Query(default=20, ge=1, le=50),
    ) -> dict[str, Any]:
        items = _service(request).search_concepts(snapshot, strategy, q, limit=limit)
        return {"items": [item.model_dump(mode="json") for item in items]}

    @app.post("/internal/v1/sessions", status_code=201)
    async def create_session(request: Request, payload: CreateSessionRequest) -> dict[str, Any]:
        session = _sessions(request).create(payload.display_name)
        return session.model_dump(mode="json")

    @app.get("/internal/v1/sessions")
    async def list_sessions(request: Request) -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in _sessions(request).list()]}

    @app.get("/internal/v1/sessions/{session_id}")
    async def get_session(request: Request, session_id: str) -> dict[str, Any]:
        return _sessions(request).load(session_id).model_dump(mode="json")

    @app.put("/internal/v1/sessions/{session_id}/selection")
    async def select(
        request: Request, session_id: str, payload: SelectionRequest
    ) -> dict[str, Any]:
        service = _service(request)
        compatible = service.require_compatible(payload.snapshot_id, payload.strategy_id)
        selection = SessionSelection(
            snapshot_id=payload.snapshot_id,
            strategy_id=payload.strategy_id,
            profile_id=compatible.profile_id,
            profile_sha256=compatible.profile_sha256,
        )
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(update={"selection": selection}),
        )
        return session.model_dump(mode="json")

    @app.put("/internal/v1/sessions/{session_id}/case")
    async def save_case(request: Request, session_id: str, payload: CaseRequest) -> dict[str, Any]:
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(update={"clinical_case": payload.clinical_case}),
        )
        return session.model_dump(mode="json")

    @app.post("/internal/v1/sessions/{session_id}/analyses")
    async def run_analysis(
        request: Request, session_id: str, payload: RunRequest
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if session.selection is None:
            raise LatrosError("Select a compatible snapshot and strategy before running")
        selection = session.selection
        service = _service(request)
        _require_current_selection(service, selection)
        result = service.diagnose(
            selection.snapshot_id,
            session.clinical_case,
            selection.strategy_id,
            "v2",
        )
        if not hasattr(result, "model_dump"):
            raise LatrosError("The R&D interface requires the v2 result contract")
        updated, run = store.record_run(
            session_id,
            payload.revision,
            "diagnose",
            result.model_dump(mode="json"),
        )
        return {
            "session": updated.model_dump(mode="json"),
            "run": run.model_dump(mode="json"),
        }

    @app.post("/internal/v1/sessions/{session_id}/questions/next")
    async def next_question(
        request: Request, session_id: str, payload: RunRequest
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if session.selection is None:
            raise LatrosError("Select a compatible snapshot and strategy before running")
        selection = session.selection
        service = _service(request)
        _require_current_selection(service, selection)
        result = service.next_question(
            selection.snapshot_id,
            session.clinical_case,
            selection.strategy_id,
            "v2",
        )
        if not hasattr(result, "model_dump"):
            raise LatrosError("The R&D interface requires the v2 question contract")
        updated, run = store.record_run(
            session_id,
            payload.revision,
            "question",
            result.model_dump(mode="json"),
        )
        return {
            "session": updated.model_dump(mode="json"),
            "run": run.model_dump(mode="json"),
        }

    @app.post("/internal/v1/sessions/{session_id}/questions/answer")
    async def answer_question(
        request: Request, session_id: str, payload: QuestionAnswerRequest
    ) -> dict[str, Any]:
        store = _sessions(request)
        current = store.load(session_id)
        _require_request_revision(current.revision, payload.revision)
        if current.selection is None:
            raise LatrosError("The session has no snapshot/strategy selection")
        if (
            current.latest_question is None
            or current.latest_question.run_id != payload.question_run_id
        ):
            raise LatrosError("Question run is stale or is not the latest session question")
        run = store.load_run(session_id, payload.question_run_id)
        question = run.result.get("question")
        if run.result.get("status") != "question" or not isinstance(question, dict):
            raise LatrosError("The selected run contains no answerable question")
        question_id = question.get("question_id")
        concept = question.get("concept")
        if not isinstance(question_id, str) or not isinstance(concept, dict):
            raise LatrosError("Stored question contract is incomplete")
        if any(item.question_id == question_id for item in current.clinical_case.question_history):
            raise LatrosError("This adaptive question has already been answered")
        option = _service(request).resolve_question_concept(
            current.selection.snapshot_id,
            current.selection.strategy_id,
            str(concept.get("system", "")),
            str(concept.get("code", "")),
        )
        updated_case = _case_with_question_answer(
            current.clinical_case,
            question_id,
            option.model_dump(mode="json"),
            payload.answer,
        )
        session = store.update(
            session_id,
            payload.revision,
            lambda value: value.model_copy(update={"clinical_case": updated_case}),
        )
        return session.model_dump(mode="json")

    @app.get("/internal/v1/sessions/{session_id}/runs/{run_id}")
    async def get_run(request: Request, session_id: str, run_id: str) -> dict[str, Any]:
        return _sessions(request).load_run(session_id, run_id).model_dump(mode="json")

    return app


def run_ui(root: Path, port: int = 8765, *, open_browser: bool = True) -> None:
    if not 1 <= port <= 65535:
        raise LatrosError("UI port must be between 1 and 65535")
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(
        create_app(root),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
    )


def _case_with_question_answer(
    case: ClinicalCaseV2,
    question_id: str,
    concept_option: dict[str, Any],
    answer: str,
) -> ClinicalCaseV2:
    clinical_status, evaluation_status, uncertainty_reason = {
        "present": ("present", "assessed", None),
        "absent": ("absent", "assessed", None),
        "unknown": ("unknown", "assessed", "unknown_to_subject"),
        "not_assessed": ("unknown", "not_assessed", "not_asked"),
        "unable_to_assess": ("unknown", "unable_to_assess", "unable_to_assess"),
    }[answer]
    observation_id = f"observation-{uuid4()}"
    response_id = f"response-{uuid4()}"
    active_previous = _active_observation_for_concept(case, str(concept_option["concept_id"]))
    concept = {
        "concept_id": concept_option["concept_id"],
        "coding": {
            "system": concept_option["system"],
            "code": concept_option["code"],
            "display": concept_option["label"],
        },
    }
    observation = {
        "kind": concept_option["observation_kind"],
        "observation_id": observation_id,
        "concept": concept,
        "clinical_status": clinical_status,
        "evaluation_status": evaluation_status,
        "uncertainty_reason": uncertainty_reason,
        "acquisition_method": "question_answer",
        "provenance": {
            "provenance_id": f"provenance-{uuid4()}",
            "origin_type": "question_response",
            "recorded_at": datetime.now(UTC).isoformat(),
        },
        "supersedes": active_previous,
        "question_response_id": response_id,
    }
    response = QuestionResponseV2.model_validate(
        {
            "response_id": response_id,
            "question_id": question_id,
            "concept": concept,
            "clinical_status": clinical_status,
            "evaluation_status": evaluation_status,
            "uncertainty_reason": uncertainty_reason,
            "resulting_observation_id": observation_id,
            "answered_at": datetime.now(UTC).isoformat(),
            "provenance": {
                "provenance_id": f"provenance-{uuid4()}",
                "origin_type": "question_response",
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        }
    )
    payload = case.model_dump(mode="json")
    payload["observations"].append(observation)
    payload["question_history"].append(response.model_dump(mode="json"))
    return ClinicalCaseV2.model_validate(payload)


def _active_observation_for_concept(case: ClinicalCaseV2, concept_id: str) -> str | None:
    superseded = {item.supersedes for item in case.observations if item.supersedes is not None}
    active = [
        item
        for item in case.observations
        if item.observation_id not in superseded and item.concept.concept_id == concept_id
    ]
    if len(active) > 1:
        raise LatrosError("Question answer cannot resolve multiple active observations")
    return active[0].observation_id if active else None


def _require_request_revision(current: int, expected: int) -> None:
    if current != expected:
        raise LatrosError(f"Session revision conflict: expected {expected}, current {current}")


def _require_current_selection(
    service: ResearchApplicationService, selection: SessionSelection
) -> None:
    current = service.require_compatible(selection.snapshot_id, selection.strategy_id)
    if (
        current.profile_id != selection.profile_id
        or current.profile_sha256 != selection.profile_sha256
    ):
        raise LatrosError("Reasoning profile changed; reapply the session selection before running")


def _service(request: Request) -> ResearchApplicationService:
    return cast(ResearchApplicationService, request.app.state.service)


def _sessions(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.sessions)


def _error(
    status_code: int,
    error: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    document = ErrorDocument(error=error, message=message, details=details or [])
    return JSONResponse(status_code=status_code, content=document.model_dump(mode="json"))


def _validation_details(errors: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "location": [str(part) for part in item.get("loc", ())],
            "message": str(item.get("msg", "invalid value")),
            "type": str(item.get("type", "validation_error")),
        }
        for item in errors
        if isinstance(item, dict)
    ]
