"""Loopback-only FastAPI shell for inspecting existing Latros capabilities."""

from __future__ import annotations

import webbrowser
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256 as hash_bytes
from pathlib import Path
from typing import Annotated, Any, Literal, cast
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
from latros.common import LatrosError, sha256
from latros.knowledge.presentation_repository import load_display_lexicon
from latros.ui.anatomy import load_navigation
from latros.ui.huatuo_analysis import (
    HuatuoAnalysisV1,
    HuatuoRequest,
    case_digest,
    huatuo_messages,
    independent_case_payload,
    parse_huatuo_output,
)
from latros.ui.local_llm import LocalLlamaServer
from latros.ui.models import (
    CaseRequest,
    ConsultationWorkflow,
    CreateSessionRequest,
    ErrorDocument,
    QuestionAnswerRequest,
    ResearchSession,
    RunRequest,
    SelectionRequest,
    SessionSelection,
)
from latros.ui.patient_context import PatientContextRequest, project_age
from latros.ui.refinements import (
    RefinementAnswerRequest,
    apply_refinement,
    refinement_definitions,
)
from latros.ui.result_verification import (
    MAX_VERIFICATION_QUESTIONS,
    TOP_CANDIDATES,
    VerificationAnswerRequest,
    VerificationItem,
    VerificationPlanV1,
    next_item,
    plan_matches_case,
    ranked_findings,
)
from latros.ui.run_transport import summary_projection
from latros.ui.sessions import SessionStore
from latros.ui.symptom_interpretation import (
    SYSTEM_PROMPT,
    ConfirmInterpretationRequest,
    SymptomInterpretationRequest,
    confirm_mentions,
    map_mentions,
    parse_mentions,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _asset_urls() -> dict[str, str]:
    """Bind local UI resources to their content, not a stale browser cache entry."""
    return {
        path.name: f"/assets/{path.name}?v={sha256(path)}"
        for path in (PACKAGE_ROOT / "assets").iterdir()
        if path.is_file() and path.suffix in {".js", ".css", ".svg"}
    }


def create_app(root: Path) -> FastAPI:
    """Create an internal transport bound by the launcher to loopback only."""
    resolved_root = root.resolve()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            application.state.local_llm.close()
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
    app.state.local_llm = LocalLlamaServer(resolved_root)
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
        if request.url.path.startswith("/internal/") or request.url.path in {"/", "/expert"}:
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
            name="checker.html",
            context={"version": __version__, "assets": _asset_urls()},
        )

    @app.get("/expert", response_class=HTMLResponse)
    async def expert(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"version": __version__, "assets": _asset_urls()},
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

    @app.get("/internal/v1/presentation/concepts")
    async def display_concepts(
        request: Request,
        snapshot: str,
        strategy: str,
        q: str = Query(default="", max_length=120),
        language: Literal["fr", "de", "en"] = "en",
        limit: int = Query(default=20, ge=1, le=50),
    ) -> dict[str, Any]:
        return {
            "items": _service(request).search_display_concepts(
                snapshot, strategy, q, language, limit=limit
            )
        }

    @app.get("/internal/v1/presentation/labels")
    async def display_labels(
        request: Request,
        snapshot: str,
        strategy: str,
        ids: Annotated[list[str] | None, Query()] = None,
        language: Literal["fr", "de", "en"] = "en",
    ) -> dict[str, Any]:
        return {"items": _service(request).display_labels(snapshot, strategy, ids or [], language)}

    @app.get("/internal/v1/presentation/question")
    async def display_question(
        request: Request,
        snapshot: str,
        strategy: str,
        system: str,
        code: str,
        language: Literal["fr", "de", "en"] = "en",
    ) -> dict[str, Any]:
        return _service(request).display_question(snapshot, strategy, system, code, language)

    @app.get("/internal/v1/presentation/anatomy")
    async def anatomical_navigation(
        request: Request,
        snapshot: str,
        strategy: str,
        region: str = "body",
        language: Literal["fr", "de", "en"] = "en",
    ) -> dict[str, Any]:
        config = load_navigation()
        node = config["nodes"].get(region)
        if node is None:
            raise LatrosError("Unknown anatomical navigation region")
        # Empty navigation nodes never initialize the medical repository at startup.
        items = (
            _service(request).navigation_concepts(
                snapshot, strategy, config["system"], node.get("codes", []), language
            )
            if node.get("codes")
            else []
        )
        return {"config": config, "region": region, "items": items}

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
        if payload.strategy_id == "rare_question_v1":
            raise LatrosError("Rare consultation requires explicit opt-in after general results")
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
            lambda current: current.model_copy(
                update={
                    "selection": selection,
                    "consultation": ConsultationWorkflow()
                    if payload.strategy_id == "general_question_v2"
                    else None,
                }
            ),
        )
        return session.model_dump(mode="json")

    @app.post("/internal/v1/sessions/{session_id}/consultation/rare")
    async def rare_opt_in(request: Request, session_id: str, payload: RunRequest) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        workflow = session.consultation
        if (
            session.selection is None
            or workflow is None
            or workflow.general_run is None
            or workflow.phase != "general"
            or session.selection.strategy_id != "general_question_v2"
        ):
            raise LatrosError("Complete the general analysis before optional rare exploration")
        general_run = store.load_run(session_id, workflow.general_run.run_id)
        if general_run.clinical_case != session.clinical_case:
            raise LatrosError("General results are stale; analyse the changed case first")
        compatible = _service(request).require_compatible(
            session.selection.snapshot_id, "rare_question_v1"
        )
        selection = SessionSelection(
            snapshot_id=compatible.snapshot_id,
            strategy_id=compatible.strategy_id,
            profile_id=compatible.profile_id,
            profile_sha256=compatible.profile_sha256,
        )
        updated = store.update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(
                update={
                    "selection": selection,
                    "consultation": workflow.model_copy(
                        update={
                            "phase": "rare",
                            "rare_opted_in_at": datetime.now(UTC),
                        }
                    ),
                    "latest_question": None,
                    "latest_diagnose": None,
                }
            ),
        )
        return updated.model_dump(mode="json")

    @app.put("/internal/v1/sessions/{session_id}/case")
    async def save_case(request: Request, session_id: str, payload: CaseRequest) -> dict[str, Any]:
        active_refinements = {
            (item.observation_id, item.concept_id)
            for item in refinement_definitions(payload.clinical_case)
        }
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(
                update={
                    "clinical_case": payload.clinical_case,
                    "refinement_answers": [
                        item
                        for item in current.refinement_answers
                        if (item.observation_id, item.concept_id) in active_refinements
                    ],
                }
            ),
        )
        return session.model_dump(mode="json")

    @app.put("/internal/v1/sessions/{session_id}/patient-context")
    async def save_patient_context(
        request: Request, session_id: str, payload: PatientContextRequest
    ) -> dict[str, Any]:
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(
                update={
                    "patient_context": payload.patient_context,
                    "clinical_case": project_age(current.clinical_case, payload.patient_context),
                }
            ),
        )
        return session.model_dump(mode="json")

    @app.get("/internal/v1/local-models")
    async def local_models(request: Request) -> dict[str, Any]:
        return {"available": request.app.state.local_llm.status(), "offline_only": True}

    @app.get("/internal/v1/sessions/{session_id}/local-ai/huatuo/latest")
    async def latest_huatuo(request: Request, session_id: str) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        analysis = store.latest_ai_analysis(session_id)
        return {
            "analysis": analysis.model_dump(
                mode="json", exclude={"input_case", "raw_model_response"}
            )
            if analysis
            else None,
            "stale": bool(
                analysis and analysis.case_sha256 != case_digest(independent_case_payload(session))
            ),
        }

    @app.post("/internal/v1/sessions/{session_id}/local-ai/huatuo")
    async def analyze_with_huatuo(
        request: Request, session_id: str, payload: HuatuoRequest
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if session.latest_diagnose is None:
            raise LatrosError("Finish a Latros result before requesting local AI analysis")
        # Deliberately never call load_run / load_run_summary / load_candidate_detail here.
        case_input = independent_case_payload(session)
        digest = case_digest(case_input)
        raw = await request.app.state.local_llm.complete(
            "huatuo", huatuo_messages(case_input, payload.language)
        )
        output = parse_huatuo_output(raw)
        analysis = HuatuoAnalysisV1(
            analysis_id=f"huatuo-{uuid4()}",
            session_id=session_id,
            created_at=datetime.now(UTC),
            output_language=payload.language,
            case_sha256=digest,
            input_case=case_input,
            output=output,
            raw_model_response=raw,
        )
        updated = store.record_ai_analysis(session_id, payload.revision, analysis)
        return {
            "session": updated.model_dump(mode="json"),
            "analysis": analysis.model_dump(
                mode="json", exclude={"input_case", "raw_model_response"}
            ),
            "stale": False,
        }

    @app.post("/internal/v1/sessions/{session_id}/symptom-interpretations")
    async def interpret_symptoms(
        request: Request, session_id: str, payload: SymptomInterpretationRequest
    ) -> dict[str, Any]:
        session = _sessions(request).load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if session.selection is None or session.patient_context is None:
            raise LatrosError("Select a snapshot and save patient information first")
        narrative = (session.patient_context.symptom_narrative or "").strip()
        if not narrative:
            raise LatrosError("No patient symptom description has been saved")
        raw = await request.app.state.local_llm.complete(
            "qwen",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": narrative},
            ],
        )
        extracted = parse_mentions(raw, narrative)
        service = _service(request)
        selection = session.selection
        mentions = map_mentions(
            extracted,
            lambda phrase: service.search_display_concepts(
                selection.snapshot_id,
                selection.strategy_id,
                phrase,
                payload.language,
                limit=3,
            ),
            selection.snapshot_id,
            selection.strategy_id,
        )
        return {
            "revision": session.revision,
            "narrative": narrative,
            "mentions": [item.model_dump(mode="json") for item in mentions],
            "model": "Qwen3.5-9B-local",
            "requires_confirmation": True,
        }

    @app.post("/internal/v1/sessions/{session_id}/symptom-interpretations/confirm")
    async def confirm_symptoms(
        request: Request, session_id: str, payload: ConfirmInterpretationRequest
    ) -> dict[str, Any]:
        current = _sessions(request).load(session_id)
        _require_request_revision(current.revision, payload.revision)
        if current.selection is None or current.patient_context is None:
            raise LatrosError("The session has no saved patient information or snapshot")
        if payload.narrative != (current.patient_context.symptom_narrative or "").strip():
            raise LatrosError("The patient symptom description changed before confirmation")
        service = _service(request)
        selection = current.selection
        updated_case = confirm_mentions(
            current.clinical_case,
            payload,
            lambda system, code: service.resolve_question_concept(
                selection.snapshot_id, selection.strategy_id, system, code
            ),
        )
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda value: value.model_copy(update={"clinical_case": updated_case}),
        )
        return session.model_dump(mode="json")

    @app.get("/internal/v1/sessions/{session_id}/refinements")
    async def get_refinements(request: Request, session_id: str) -> dict[str, Any]:
        session = _sessions(request).load(session_id)
        return {
            "items": [
                item.model_dump(mode="json")
                for item in refinement_definitions(session.clinical_case)
            ],
            "answers": [item.model_dump(mode="json") for item in session.refinement_answers],
        }

    @app.put("/internal/v1/sessions/{session_id}/refinements")
    async def save_refinement(
        request: Request, session_id: str, payload: RefinementAnswerRequest
    ) -> dict[str, Any]:
        current = _sessions(request).load(session_id)
        _require_request_revision(current.revision, payload.revision)
        if any(
            item.observation_id == payload.answer.observation_id
            for item in current.refinement_answers
        ):
            raise LatrosError("This observation already has a captured refinement")
        session = _sessions(request).update(
            session_id,
            payload.revision,
            lambda current: current.model_copy(
                update={
                    "clinical_case": apply_refinement(current.clinical_case, payload.answer),
                    "refinement_answers": [*current.refinement_answers, payload.answer],
                }
            ),
        )
        return session.model_dump(mode="json")

    @app.post("/internal/v1/sessions/{session_id}/analyses")
    async def run_analysis(
        request: Request,
        session_id: str,
        payload: RunRequest,
        view: str = Query(default="full", pattern="^(full|summary)$"),
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if session.selection is None:
            raise LatrosError("Select a compatible snapshot and strategy before running")
        selection = session.selection
        _require_consultation_phase(session)
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
            "run": summary_projection(run) if view == "summary" else run.model_dump(mode="json"),
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
        _require_consultation_phase(session)
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
        if run.selection != current.selection or run.clinical_case != current.clinical_case:
            raise LatrosError("Question run belongs to an outdated case or consultation phase")
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

    @app.post("/internal/v1/sessions/{session_id}/runs/{run_id}/verification")
    async def start_verification(
        request: Request, session_id: str, run_id: str, payload: RunRequest
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        if (
            session.consultation is None
            or session.consultation.phase != "general"
            or session.selection is None
            or session.selection.strategy_id != "general_question_v2"
            or session.latest_diagnose is None
            or session.latest_diagnose.run_id != run_id
        ):
            raise LatrosError("Verification requires the current general result")
        plan = store.load_verification_plan(session_id, run_id)
        if plan is None:
            summary = store.load_run_summary(session_id, run_id)
            top = summary["result"].get("candidates", [])[:TOP_CANDIDATES]
            top_ids = [str(item["candidate_id"]) for item in top]
            details = [
                item["candidate"]
                for item in store.load_candidate_details(session_id, run_id, top_ids)
            ]
            service = _service(request)
            items: list[VerificationItem] = []
            user_facing_codes = {
                entry["code"]: entry["source_label"] for entry in load_display_lexicon()["entries"]
            }
            already_verified = max(
                session.verification_answered_count,
                sum(
                    item.question_id.startswith("result_verification_v1:")
                    for item in session.clinical_case.question_history
                ),
            )
            remaining_budget = max(0, MAX_VERIFICATION_QUESTIONS - already_verified)
            ranked = ranked_findings(session.clinical_case, details) if remaining_budget else []
            for finding, candidate_ids in ranked:
                if finding in session.verification_asked_concept_ids:
                    continue
                try:
                    option = service.supported_observation_for_concept(
                        session.selection.snapshot_id, session.selection.strategy_id, finding
                    )
                except LatrosError:
                    continue
                if option.observation_kind not in {"symptom", "sign", "exam"}:
                    continue
                if user_facing_codes.get(option.code) != option.label:
                    continue
                token = hash_bytes(f"{run_id}:{finding}".encode()).hexdigest()[:20]
                items.append(
                    VerificationItem(
                        question_id=f"result_verification_v1:{token}",
                        concept_id=finding,
                        system=option.system,
                        code=option.code,
                        label=option.label,
                        observation_kind=cast(
                            Literal["symptom", "sign", "exam"], option.observation_kind
                        ),
                        candidate_ids=candidate_ids,
                    )
                )
                if len(items) == remaining_budget:
                    break
            plan = VerificationPlanV1(
                base_run_id=run_id,
                case_id=session.clinical_case.case_id,
                baseline_observation_ids=[
                    item.observation_id for item in session.clinical_case.observations
                ],
                baseline_question_ids=[
                    item.question_id for item in session.clinical_case.question_history
                ],
                top_candidate_ids=top_ids,
                items=items,
            )
            store.save_verification_plan(session_id, plan)
        else:
            summary = store.load_run_summary(session_id, run_id)
            if plan.top_candidate_ids != [
                str(item["candidate_id"])
                for item in summary["result"].get("candidates", [])[:TOP_CANDIDATES]
            ]:
                raise LatrosError("Verification plan no longer matches the immutable run")
        if not plan_matches_case(plan, session.clinical_case):
            raise LatrosError("Verification plan is stale after case changes")
        return _verification_view(plan, session)

    @app.post("/internal/v1/sessions/{session_id}/runs/{run_id}/verification/answer")
    async def answer_verification(
        request: Request,
        session_id: str,
        run_id: str,
        payload: VerificationAnswerRequest,
    ) -> dict[str, Any]:
        store = _sessions(request)
        session = store.load(session_id)
        _require_request_revision(session.revision, payload.revision)
        plan = store.load_verification_plan(session_id, run_id)
        if plan is None or not plan_matches_case(plan, session.clinical_case):
            raise LatrosError("Missing or stale verification plan")
        if (
            session.consultation is None
            or session.consultation.phase != "general"
            or session.selection is None
            or session.latest_diagnose is None
            or session.latest_diagnose.run_id != run_id
        ):
            raise LatrosError("Verification belongs to an outdated general result")
        item = next_item(plan, session.clinical_case)
        if session.verification_answered_count >= MAX_VERIFICATION_QUESTIONS:
            raise LatrosError("Verification question budget has been reached")
        if item is None or item.question_id != payload.question_id:
            raise LatrosError("Verification question is already answered or out of order")
        option = _service(request).resolve_question_concept(
            session.selection.snapshot_id,
            session.selection.strategy_id,
            item.system,
            item.code,
        )
        if option.concept_id != item.concept_id:
            raise LatrosError("Verification concept no longer resolves exactly")
        updated_case = _case_with_question_answer(
            session.clinical_case,
            item.question_id,
            option.model_dump(mode="json"),
            payload.answer,
        )
        updated = store.update(
            session_id,
            payload.revision,
            lambda value: value.model_copy(
                update={
                    "clinical_case": updated_case,
                    "verification_answered_count": value.verification_answered_count + 1,
                    "verification_asked_concept_ids": [
                        *value.verification_asked_concept_ids,
                        item.concept_id,
                    ],
                }
            ),
        )
        return _verification_view(plan, updated)

    @app.get("/internal/v1/sessions/{session_id}/runs/{run_id}")
    async def get_run(request: Request, session_id: str, run_id: str) -> dict[str, Any]:
        return _sessions(request).load_run(session_id, run_id).model_dump(mode="json")

    @app.get("/internal/v1/sessions/{session_id}/runs/{run_id}/summary")
    async def get_run_summary(request: Request, session_id: str, run_id: str) -> dict[str, Any]:
        return _sessions(request).load_run_summary(session_id, run_id)

    @app.get("/internal/v1/sessions/{session_id}/runs/{run_id}/candidates/{candidate_id:path}")
    async def get_candidate_detail(
        request: Request, session_id: str, run_id: str, candidate_id: str
    ) -> dict[str, Any]:
        return _sessions(request).load_candidate_detail(session_id, run_id, candidate_id)

    return app


def _verification_view(plan: VerificationPlanV1, session: ResearchSession) -> dict[str, Any]:
    question = next_item(plan, session.clinical_case)
    answered_ids = {item.question_id for item in session.clinical_case.question_history}
    return {
        "plan": plan.model_dump(mode="json"),
        "session": session.model_dump(mode="json"),
        "question": question.model_dump(mode="json") if question else None,
        "answered": sum(item.question_id in answered_ids for item in plan.items),
        "maximum": MAX_VERIFICATION_QUESTIONS,
    }


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


def _require_consultation_phase(session: ResearchSession) -> None:
    if session.selection is not None and session.selection.strategy_id == "rare_question_v1":
        workflow = session.consultation
        if (
            workflow is None
            or workflow.phase != "rare"
            or workflow.rare_opted_in_at is None
            or workflow.general_run is None
        ):
            raise LatrosError("Rare consultation requires explicit opt-in after general results")


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
