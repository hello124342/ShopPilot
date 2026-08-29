from __future__ import annotations

import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..auth import AuthService
from ..infra import Database, RedisCoordinator, S3ObjectStorage

from ..assets import AssetReference
from ..capabilities import CapabilityConfigurationError, CapabilityRegistry, default_registry
from ..harness import Evaluator, SCENARIOS
from ..runtime import AgnoRuntimeFactory
from ..schemas import CampaignInput
from ..settings import Settings
from ..store import RunStore
from ..domain.stages import StageApproval, StageStatus, initial_stages, stage_graph
from ..domain.stage_store import StageStore
from ..workflows import CampaignWorkflow, StagedCampaignWorkflow
from .errors import AppError, from_value_error
from .observability import configure_logging

class DecisionRequest(BaseModel):
    feedback: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class BindingsRequest(BaseModel):
    skills: list[str] = []
    tools: list[str] = []
    mcp_servers: list[str] = []




def create_app(app_settings: Settings | None = None, workflow_override: CampaignWorkflow | None = None) -> FastAPI:
    settings = app_settings or Settings()
    logger = configure_logging(settings.log_level)
    store = workflow_override.store if workflow_override else RunStore(settings.data_dir)
    stage_store = StageStore(settings.data_dir)
    runtime_error: str | None = settings.readiness_error
    active_workflow = workflow_override
    capability_registry = None
    runtime_factory = None
    try:
        if workflow_override is not None:
            runtime_factory = workflow_override.runtime_factory
            capability_registry = runtime_factory.registry
        else:
            capability_registry = (
                CapabilityRegistry.load(settings.capability_registry_path)
                if settings.capability_registry_path
                else default_registry()
            )
            runtime_factory = AgnoRuntimeFactory(registry=capability_registry)
    except CapabilityConfigurationError as exc:
        runtime_error = exc.code

    if active_workflow is None and runtime_error is None:
        try:
            active_workflow = CampaignWorkflow(
                store, settings.runtime_settings(), runtime_factory=runtime_factory
            )
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
    application.state.capability_registry = capability_registry
    application.state.mcp_manager = runtime_factory.mcp_manager if runtime_factory else None
    application.state.assets = active_workflow.assets if active_workflow else None
    application.state.stage_store = stage_store
    from ..capabilities.bindings import AgentBindingStore
    application.state.binding_store = AgentBindingStore(settings.data_dir)
    application.state.staged_workflow = StagedCampaignWorkflow(active_workflow, stage_store) if active_workflow else None
    application.state.database = Database(settings.database_url)
    application.state.redis = RedisCoordinator(settings.redis_url)
    application.state.object_storage = S3ObjectStorage(
        settings.object_storage_endpoint,
        settings.object_storage_access_key,
        settings.object_storage_secret_key.get_secret_value(),
        settings.object_storage_bucket,
        secure=settings.object_storage_secure,
    )
    application.state.auth = None
    application.state.infrastructure_error = None

    @application.on_event("startup")
    def initialize_infrastructure():
        try:
            application.state.database.create_schema()
            application.state.auth = AuthService(application.state.database, ttl_hours=settings.session_ttl_hours)
            application.state.auth.ensure_admin(settings.admin_username, settings.admin_password.get_secret_value(), settings.tenant_id)
        except Exception as exc:
            application.state.infrastructure_error = type(exc).__name__
            logger.error("database_initialization_failed", extra={"error_code": type(exc).__name__})
            return
        for service_name, initializer in (("object_storage", application.state.object_storage.ensure_bucket), ("redis", application.state.redis.ensure_group)):
            try:
                initializer()
            except Exception as exc:
                logger.warning("optional_infrastructure_unavailable", extra={"service": service_name, "error_code": type(exc).__name__})
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    @application.middleware("http")
    async def authentication_middleware(request: Request, call_next):
        public = request.url.path in {"/", "/health/live", "/health/ready", "/api/auth/login", "/api/auth/session"} or request.url.path.startswith("/static/")
        if settings.auth_enabled and not public:
            auth = application.state.auth
            if auth is None:
                return JSONResponse(status_code=503, content={"error_code": "authentication_unavailable", "message": "认证服务未就绪"})
            session_id = request.cookies.get(AuthService.COOKIE)
            user = auth.authenticate(session_id)
            if user is None:
                return JSONResponse(status_code=401, content={"error_code": "authentication_required", "message": "请先登录"})
            request.state.user = user
            if request.method not in {"GET", "HEAD", "OPTIONS"} and not auth.validate_csrf(session_id, request.headers.get("X-CSRF-Token")):
                return JSONResponse(status_code=403, content={"error_code": "csrf_validation_failed", "message": "安全令牌无效，请刷新页面"})
        return await call_next(request)

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

    def ensure_stages(run_id: str):
        stages = stage_store.get(run_id)
        if not stages:
            stages = initial_stages(run_id)
            stage_store.save(run_id, stages)
        return stages

    def sync_legacy_stages(run_id: str, run: dict):
        stages = ensure_stages(run_id)
        if stage_store.approvals(run_id):
            return stages
        status = run.get("status")
        if status in {"waiting_review", "revision_required"}:
            for stage in stages:
                if stage.stage_id == "input":
                    stage.status = StageStatus.APPROVED
                elif stage.stage_id in {"research", "strategy", "creative", "compliance", "advertisement"}:
                    stage.status = StageStatus.APPROVED
                elif stage.stage_id == "publish_review":
                    stage.status = StageStatus.PENDING_REVIEW
                else:
                    stage.status = StageStatus.LOCKED
        elif status in {"optimized", "analyzed", "published", "approved"}:
            for stage in stages:
                stage.status = StageStatus.APPROVED
        elif status in {"failed", "human_handoff"}:
            current = next((item for item in stages if item.stage_id == "research"), stages[1])
            current.status = StageStatus.FAILED
        stage_store.save(run_id, stages)
        return stages

    def registry_items(kind: str):
        registry = capability_registry
        if not registry:
            return []
        values = getattr(registry, kind, {}).values()
        return [item.model_dump(mode="json") for item in values]

    @application.put("/api/agents/{agent_id}/bindings")
    def update_agent_bindings(agent_id: str, request: BindingsRequest):
        if not capability_registry:
            raise AppError("capability_registry_unavailable", "能力目录不可用", 503)
        try:
            agent = capability_registry.agent(agent_id)
            profile = capability_registry.profile(agent.capability_profile_ref)
        except Exception as exc:
            raise AppError("agent_not_found", "Agent 不存在", 404) from exc
        for ref in (*request.skills, *request.tools, *request.mcp_servers):
            collection = capability_registry.skills if ref in capability_registry.skills else capability_registry.tools if ref in capability_registry.tools else capability_registry.mcp_servers if ref in capability_registry.mcp_servers else None
            if collection is None:
                raise AppError("capability_not_registered", f"能力未注册：{ref}", 422)
        value = application.state.binding_store.put(agent_id, skills=request.skills, tools=request.tools, mcp_servers=request.mcp_servers)
        return {"agent_id": agent_id, "binding": value, "effective": {"base_profile": profile.ref, "skills": request.skills, "tools": request.tools, "mcp_servers": request.mcp_servers}}

    @application.get("/api/agents")
    def list_agents():
        items = registry_items("agents")
        for item in items:
            try:
                agent = capability_registry.agent(item["id"])
                profile = capability_registry.profile(agent.capability_profile_ref)
                binding = application.state.binding_store.get(item["id"]) or {}
                item["skills"] = binding.get("skills", list(profile.skill_refs))
                item["tools"] = binding.get("tools", list(profile.tool_refs))
                item["mcp_servers"] = binding.get("mcp_servers", list(profile.mcp_refs))
                item["binding_version"] = binding.get("binding_version", 0)
                item["status"] = "ready"
            except Exception:
                item["status"] = "invalid"
        return {"items": items, "count": len(items)}

    @application.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str):
        if not capability_registry:
            raise AppError("capability_registry_unavailable", "能力目录不可用", 503)
        try:
            agent = capability_registry.agent(agent_id)
            profile = capability_registry.profile(agent.capability_profile_ref)
        except Exception as exc:
            raise AppError("agent_not_found", "Agent 不存在", 404) from exc
        binding = application.state.binding_store.get(agent_id) or {}
        skill_refs = binding.get("skills", list(profile.skill_refs))
        tool_refs = binding.get("tools", list(profile.tool_refs))
        mcp_refs = binding.get("mcp_servers", list(profile.mcp_refs))
        return {"agent": agent.model_dump(mode="json"), "profile": profile.model_dump(mode="json"), "binding_version": binding.get("binding_version", 0), "skills": [capability_registry.skills[x].model_dump(mode="json") for x in skill_refs], "tools": [capability_registry.tools[x].model_dump(mode="json") for x in tool_refs], "mcp_servers": [capability_registry.mcp_servers[x].model_dump(mode="json") for x in mcp_refs]}

    @application.get("/api/skills")
    def list_skills():
        return {"items": registry_items("skills")}

    @application.get("/api/tools")
    def list_tools():
        return {"items": registry_items("tools")}

    @application.get("/api/mcp-servers")
    def list_mcp_servers():
        return {"items": registry_items("mcp_servers")}

    @application.get("/api/runs/{run_id}/stages")
    def run_stages(run_id: str):
        run = require_run(run_id)
        stages = application.state.staged_workflow.stage_store.get(run_id) if application.state.staged_workflow else sync_legacy_stages(run_id, run)
        return {"items": [item.model_dump(mode="json") for item in stages]}

    @application.get("/api/runs/{run_id}/stages/{stage_id}")
    def get_stage(run_id: str, stage_id: str):
        require_run(run_id)
        stages = application.state.staged_workflow.stage_store.get(run_id) if application.state.staged_workflow else ensure_stages(run_id)
        stage = next((item for item in stages if item.stage_id == stage_id), None)
        if stage is None:
            raise AppError("stage_not_found", "阶段不存在", 404)
        artifacts = store.read(run_id, "artifacts.jsonl")
        trace = store.read(run_id, "trace.jsonl")
        return {"stage": stage.model_dump(mode="json"), "artifacts": [item for item in artifacts if item.get("kind")], "trace": [item for item in trace if item.get("stage") == stage_id], "approvals": [item.model_dump(mode="json") for item in stage_store.approvals(run_id) if item.stage_id == stage_id]}

    @application.post("/api/runs/{run_id}/stages/{stage_id}/approve")
    def approve_stage(run_id: str, stage_id: str, request: DecisionRequest):
        require_run(run_id)
        if application.state.staged_workflow:
            return application.state.staged_workflow.approve(run_id, stage_id, request.feedback)
        raise AppError("stage_workflow_unavailable", "阶段工作流不可用", 503)

    @application.post("/api/runs/{run_id}/stages/{stage_id}/reject")
    def reject_stage(run_id: str, stage_id: str, request: DecisionRequest):
        require_run(run_id)
        if application.state.staged_workflow:
            return application.state.staged_workflow.reject(run_id, stage_id, request.feedback or "需要修改")
        raise AppError("stage_workflow_unavailable", "阶段工作流不可用", 503)
    @application.get("/api/runs/{run_id}/graph")
    def run_graph(run_id: str):
        run = require_run(run_id)
        stages = application.state.staged_workflow.stage_store.get(run_id) if application.state.staged_workflow else sync_legacy_stages(run_id, run)
        spans = active_workflow.trace_store.spans(run_id, tenant_id=settings.tenant_id) if active_workflow else []
        return {"run_id": run_id, "stages": stage_graph(stages), "spans": [item.model_dump(mode="json") for item in spans]}

    @application.get("/api/runs/{run_id}/events")
    def run_events(run_id: str, limit: int = Query(default=500, ge=1, le=2000), offset: int = Query(default=0, ge=0)):
        require_run(run_id)
        if active_workflow:
            events = active_workflow.trace_store.events(run_id, tenant_id=settings.tenant_id, limit=limit, offset=offset)
            if events:
                return {"items": [item.model_dump(mode="json") for item in events], "count": len(events)}
        return {"items": store.read(run_id, "trace.jsonl")[offset:offset + limit], "count": len(store.read(run_id, "trace.jsonl"))}

    @application.get("/api/runs/{run_id}/events/stream")
    def run_events_stream(run_id: str):
        require_run(run_id)
        events = active_workflow.trace_store.events(run_id, tenant_id=settings.tenant_id) if active_workflow else []
        if not events:
            events = store.read(run_id, "trace.jsonl")
        def stream():
            for event in events:
                payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\\n\\n"
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @application.get("/api/runs/{run_id}/metrics")
    def run_metrics(run_id: str):
        require_run(run_id)
        return active_workflow.trace_store.aggregate(tenant_id=settings.tenant_id) if active_workflow else {}

    @application.get("/api/runs/{run_id}/evidence")
    def run_evidence(run_id: str):
        require_run(run_id)
        items = active_workflow.evidence_reviewer.store.list_for_run(run_id, tenant_id=settings.tenant_id) if active_workflow else []
        return {"items": [item.model_dump(mode="json") for item in items], "count": len(items)}

    @application.get("/api/runs/{run_id}/citations")
    def run_citations(run_id: str):
        require_run(run_id)
        items = active_workflow.evidence_reviewer.store.list_citations(run_id, tenant_id=settings.tenant_id) if active_workflow else []
        return {"items": [item.model_dump(mode="json") for item in items], "count": len(items)}

    @application.get("/api/runs/{run_id}/conflicts")
    def run_conflicts(run_id: str):
        require_run(run_id)
        items = active_workflow.evidence_reviewer.store.list_conflicts(run_id, tenant_id=settings.tenant_id) if active_workflow else []
        return {"items": [item.model_dump(mode="json") for item in items], "count": len(items)}
    @application.post("/api/auth/login")
    def login(credentials: LoginRequest, response: Response):
        auth = application.state.auth
        if auth is None:
            raise AppError("authentication_unavailable", "认证服务未就绪", 503)
        try:
            user, session_id, csrf_token = auth.login(credentials.username, credentials.password)
        except ValueError as exc:
            raise AppError("invalid_credentials", "用户名或密码错误", 401) from exc
        secure = settings.environment == "production"
        response.set_cookie(AuthService.COOKIE, session_id, httponly=True, secure=secure, samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")
        response.set_cookie(AuthService.CSRF_COOKIE, csrf_token, httponly=False, secure=secure, samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")
        return {"user": {"id": user.id, "username": user.username, "must_change_password": user.must_change_password}}

    @application.get("/api/auth/session")
    def auth_session(request: Request):
        user = getattr(request.state, "user", None)
        return {"authenticated": bool(user), "user": {"id": user.id, "username": user.username, "must_change_password": user.must_change_password} if user else None}

    @application.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response):
        application.state.auth.logout(request.cookies.get(AuthService.COOKIE))
        response.delete_cookie(AuthService.COOKIE, path="/")
        response.delete_cookie(AuthService.CSRF_COOKIE, path="/")
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
        capabilities = capability_registry.safe_status() if capability_registry else {"valid": False}
        payload = {"status": "ready" if error is None else "not_ready", "error_code": error, "runtime": settings.safe_diagnostics(), "storage": storage, "capabilities": capabilities}
        return JSONResponse(status_code=200 if error is None else 503, content=payload)

    @application.get("/api/infra/health")
    def infrastructure_health():
        return {"database": application.state.database.health(), "redis": application.state.redis.health(), "object_storage": application.state.object_storage.health(), "auth": {"status": "ready" if application.state.auth else "not_ready"}}
    @application.get("/api/runtime")
    def runtime_diagnostics():
        return settings.safe_diagnostics()

    @application.get("/api/capabilities/health")
    def capability_health():
        registry_status = (
            capability_registry.safe_status()
            if capability_registry
            else {"valid": False, "error_code": runtime_error}
        )
        mcp_status = (
            application.state.mcp_manager.health()
            if application.state.mcp_manager
            else {"servers": []}
        )
        return {"registry": registry_status, "mcp": mcp_status}

    @application.get("/api/scenarios")
    def scenarios():
        return [{"id": item.id, "campaign": item.campaign, "expected_status": item.expected_status, "failure": bool(item.inject)} for item in SCENARIOS.values()]

    @application.get("/api/campaigns")
    def list_campaigns(limit: int = Query(default=50, ge=1, le=200)):
        runs = store.list_runs(limit)
        return {"items": [{"campaign_id": item["run_id"], "name": item["campaign"].get("product", "Campaign"), "input": item["campaign"], "latest_run_id": item["run_id"], "status": item["status"], "updated_at": item["updated_at"]} for item in runs], "count": len(runs)}

    @application.post("/api/campaigns", status_code=201)
    def create_campaign(campaign: CampaignInput):
        return {"campaign_id": uuid.uuid4().hex, "name": campaign.product, "input": campaign.model_dump(mode="json"), "status": "draft"}
    @application.get("/api/runs")
    def list_runs(limit: int = Query(default=50, ge=1, le=200)):
        items = store.list_runs(limit)
        return {"items": items, "count": len(items)}

    @application.post("/api/runs", status_code=201)
    def create_run(campaign: CampaignInput):
        staged = application.state.staged_workflow
        result = staged.start(campaign) if staged else require_workflow().run(campaign)
        if not staged:
            stage_store.save(result["run_id"], initial_stages(result["run_id"]))
            sync_legacy_stages(result["run_id"], result)
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

    @application.get("/api/runs/{run_id}/assets")
    def run_assets(run_id: str):
        require_run(run_id)
        assets = require_workflow().assets.catalog.list_for_run(
            run_id, tenant_id=settings.tenant_id
        )
        return [require_workflow().assets.safe_metadata(asset) for asset in assets]

    @application.get("/api/assets/{asset_id}/versions/{version}")
    def asset_metadata(asset_id: str, version: int):
        reference = AssetReference(asset_id=asset_id, version=version)
        return execute(
            lambda: require_workflow().assets.safe_metadata(
                require_workflow().assets.get(reference, tenant_id=settings.tenant_id)
            )
        )

    @application.get("/api/assets/{asset_id}/versions/{version}/lineage")
    def asset_lineage(asset_id: str, version: int):
        execute(
            lambda: require_workflow().assets.get(
                AssetReference(asset_id=asset_id, version=version),
                tenant_id=settings.tenant_id,
            )
        )
        return [
            item.model_dump(mode="json")
            for item in require_workflow().assets.catalog.lineage(
                asset_id, version, tenant_id=settings.tenant_id
            )
        ]

    def asset_response(asset_id: str, version: int, *, attachment: bool):
        reference = AssetReference(asset_id=asset_id, version=version)
        try:
            asset, content = require_workflow().assets.content(
                reference, tenant_id=settings.tenant_id
            )
        except ValueError as exc:
            raise from_value_error(exc) from exc
        disposition = "attachment" if attachment else "inline"
        return Response(
            content=content,
            media_type=asset.mime_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{asset.filename}"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=60",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @application.get("/api/assets/{asset_id}/versions/{version}/preview")
    def asset_preview(asset_id: str, version: int):
        return asset_response(asset_id, version, attachment=False)

    @application.get("/api/assets/{asset_id}/versions/{version}/download")
    def asset_download(asset_id: str, version: int):
        return asset_response(asset_id, version, attachment=True)

    @application.post("/api/runs/{run_id}/exports/markdown", status_code=201)
    def export_markdown(run_id: str):
        require_run(run_id)
        asset = require_workflow().document_exporter.export(
            {"artifacts": store.read(run_id, "artifacts.jsonl")},
            run_id=run_id,
            tenant_id=settings.tenant_id,
        )
        return require_workflow().assets.safe_metadata(asset)
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



















