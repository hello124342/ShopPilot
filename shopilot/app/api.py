from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..harness import Evaluator, SCENARIOS
from ..schemas import CampaignInput
from ..settings import Settings
from ..store import RunStore
from ..workflows import CampaignWorkflow
from .errors import AppError, from_value_error
from .observability import configure_logging


class DecisionRequest(BaseModel):
    feedback: str = ""


def create_app(app_settings: Settings | None = None, workflow_override: CampaignWorkflow | None = None) -> FastAPI:
    settings = app_settings or Settings()
    logger = configure_logging(settings.log_level)
    store = workflow_override.store if workflow_override else RunStore(settings.data_dir)
    runtime_error: str | None = settings.readiness_error
    active_workflow = workflow_override
    if active_workflow is None and runtime_error is None:
        try:
            active_workflow = CampaignWorkflow(store, settings.runtime_settings())
        except Exception as exc:  # Keep liveness available for configuration diagnosis.
            runtime_error = getattr(exc, "code", "runtime_initialization_failed")

    application = FastAPI(
        title="ShopPilot AI Operations",
        version="0.2.0",
        description="Agno-powered ecommerce AI operations workspace",
    )
    application.state.settings = settings
    application.state.store = store
    application.state.workflow = active_workflow
    application.state.runtime_error = runtime_error
    application.state.logger = logger

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    @application.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "runtime_mode": settings.runtime_mode.value,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    def error_payload(request: Request, code: str, message: str) -> dict:
        return {"error_code": code, "message": message, "request_id": getattr(request.state, "request_id", "unknown")}

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_payload(request, exc.error_code, exc.message))

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={**error_payload(request, "validation_error", "请求参数校验失败"), "details": exc.errors()})

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = str(exc.detail) if isinstance(exc.detail, str) else "http_error"
        return JSONResponse(status_code=exc.status_code, content=error_payload(request, code, "请求未能完成"))

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled_error", extra={"request_id": getattr(request.state, "request_id", "unknown")})
        return JSONResponse(status_code=500, content=error_payload(request, "internal_error", "服务暂时不可用"))

    def require_workflow() -> CampaignWorkflow:
        if application.state.workflow is None:
            raise AppError(application.state.runtime_error or "runtime_not_ready", "运行时配置尚未就绪", 503)
        return application.state.workflow

    def require_run(run_id: str) -> dict:
        result = store.get_run(run_id)
        if result is None:
            raise AppError("run_not_found", "运行记录不存在", 404)
        return result

    @application.get("/", include_in_schema=False)
    def home():
        index = static_dir / "index.html"
        if not index.exists():
            raise AppError("ui_not_installed", "前端资源不存在", 503)
        return FileResponse(index)

    @application.get("/health/live")
    def health_live():
        return {"status": "live", "service": "shopilot"}

    @application.get("/health/ready")
    def health_ready():
        storage = store.health()
        error = application.state.runtime_error or (None if storage["writable"] else "data_directory_not_writable")
        payload = {"status": "ready" if error is None else "not_ready", "error_code": error, "runtime": settings.safe_diagnostics(), "storage": storage}
        return JSONResponse(status_code=200 if error is None else 503, content=payload)

    @application.get("/api/runtime")
    def runtime_diagnostics():
        return settings.safe_diagnostics()

    @application.get("/api/scenarios")
    def scenarios():
        return [{"id": item.id, "campaign": item.campaign, "expected_status": item.expected_status, "failure": bool(item.inject)} for item in SCENARIOS.values()]

    @application.get("/api/runs")
    def list_runs(limit: int = Query(default=50, ge=1, le=200)):
        items = store.list_runs(limit)
        return {"items": items, "count": len(items)}

    @application.post("/api/runs", status_code=201)
    def create_run(campaign: CampaignInput):
        result = require_workflow().run(campaign)
        logger.info("run_created", extra={"run_id": result["run_id"], "status": result["status"], "runtime_mode": settings.runtime_mode.value})
        return result

    @application.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return require_run(run_id)

    @application.get("/api/runs/{run_id}/artifacts")
    def artifacts(run_id: str):
        require_run(run_id)
        return store.read(run_id, "artifacts.jsonl")

    @application.get("/api/runs/{run_id}/trace")
    def trace(run_id: str):
        require_run(run_id)
        return store.read(run_id, "trace.jsonl")

    @application.get("/api/runs/{run_id}/approvals")
    def approvals(run_id: str):
        require_run(run_id)
        return store.read(run_id, "approvals.jsonl")

    @application.get("/api/runs/{run_id}/evaluation")
    def evaluation(run_id: str):
        require_run(run_id)
        report = store.get_evaluation(run_id)
        if report is None:
            raise AppError("evaluation_not_found", "该运行尚未评估", 404)
        return report

    def execute(action):
        try:
            return action()
        except ValueError as exc:
            raise from_value_error(exc) from exc

    @application.post("/api/runs/{run_id}/approve")
    def approve(run_id: str, request: DecisionRequest):
        require_run(run_id)
        return execute(lambda: require_workflow().approve_and_analyze(run_id, feedback=request.feedback))

    @application.post("/api/runs/{run_id}/reject")
    def reject(run_id: str, request: DecisionRequest):
        require_run(run_id)
        return execute(lambda: require_workflow().reject(run_id, feedback=request.feedback or "需要修改"))

    @application.post("/api/runs/{run_id}/replay", status_code=201)
    def replay(run_id: str):
        require_run(run_id)
        return execute(lambda: require_workflow().replay(run_id))

    @application.post("/api/runs/{run_id}/evaluate")
    def evaluate(run_id: str):
        require_run(run_id)
        return Evaluator(store).evaluate(run_id)

    return application


settings = Settings()
app = create_app(settings)
workflow = app.state.workflow
