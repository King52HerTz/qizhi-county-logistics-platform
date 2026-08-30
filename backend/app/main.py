from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import redis
from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.ai_service import AIServiceError, explain_optimization, test_ai_connection
from app.analytics import build_demand_forecast
from app.celery_app import celery_app
from app.competition_service import build_competition_readiness, build_competition_report
from app.config import get_settings
from app.data.qidong_reference import build_qidong_reference_summary
from app.db import SessionLocal, get_db, initialize_database
from app.dispatch_service import (
    DispatchWorkflowError,
    advance_assignment,
    create_plan,
    dispatch_plan as dispatch_approved_plan,
    get_plan,
    list_driver_assignments,
    list_plans,
    plan_view,
    review_plan,
    assignment_view,
)
from app.experiment_service import (
    experiment_view,
    get_experiment,
    list_experiments,
    run_experiment,
)
from app.models import (
    AIProviderConfigRecord,
    AuditLogRecord,
    DataImportBatchRecord,
    DataQualityRuleRecord,
    DriverAssignmentRecord,
    MapProviderConfigRecord,
    NodeCoordinateRevisionRecord,
    NodeRecord,
    OptimizationRunRecord,
    OrderRecord,
    OrderRequestRecord,
    ScenarioTransitionRecord,
    ScenarioVersionRecord,
    UserRecord,
    VehicleRecord,
)
from app.optimization_orchestrator import orchestrate_optimization
from app.master_data_service import (
    OrderImportError,
    build_order_import_template,
    build_scenario_from_master,
    commit_order_import,
    preview_order_import,
    quality_report,
)
from app.repository import (
    activate_scenario_version,
    create_scenario_version,
    list_runs,
    list_scenario_versions,
    load_scenario,
    get_scenario_spatial_status,
    save_run,
    seed_demo_data,
)
from app.scenario_import import ScenarioImportError, parse_scenario_workbook
from app.scenario_governance import (
    ScenarioGovernanceError,
    approve_scenario as approve_scenario_version,
    compare_scenarios,
    reject_scenario as reject_scenario_version,
    rollback_scenario as rollback_scenario_version,
    scenario_fingerprint,
    submit_scenario as submit_scenario_version,
)
from app.routing_matrix import cache_status
from app.schemas import (
    AsyncJobResponse,
    AsyncJobStatus,
    AIConfigUpsert,
    AIConfigList,
    AIConfigView,
    AIConnectionTestResponse,
    AIExplanationResponse,
    AssignmentActionRequest,
    DemandForecast,
    DispatchPlanCreate,
    DispatchPlanList,
    DispatchPlanView,
    DispatchReviewRequest,
    DriverAssignmentList,
    ExperimentCreate,
    ExperimentList,
    ExperimentView,
    Event,
    EventLocationView,
    LoginRequest,
    RegisterRequest,
    MapConfigList,
    MapConfigUpsert,
    MapConfigView,
    MapRuntimeConfig,
    CurrentUserView,
    CurrentWeather,
    OperationsReadinessResponse,
    UserCreate,
    UserUpdate,
    UserView,
    UserList,
    PasswordResetRequest,
    AuditLogView,
    AuditLogList,
    DataImportBatchList,
    DataImportBatchView,
    DataQualityReport,
    DataQualityRuleUpdate,
    DataQualityRuleView,
    MasterDataSummary,
    QidongReferenceSummary,
    MasterDataPublishRequest,
    MasterDataPublishResponse,
    MasterNodeCreate,
    MasterNodeInput,
    MasterNodeList,
    MasterNodeView,
    NodeCoordinateRevisionList,
    NodeCoordinateRevisionView,
    NodeCoordinateUpdate,
    SpatialQualitySummary,
    MasterOrderCreate,
    MasterOrderInput,
    MasterOrderList,
    MasterOrderView,
    OrderRequestCreate,
    OrderRequestList,
    OrderRequestNodeOption,
    OrderRequestNodeOptionList,
    OrderRequestReviewRequest,
    OrderRequestView,
    MasterVehicleCreate,
    MasterVehicleInput,
    MasterVehicleList,
    MasterVehicleView,
    OptimizeRequest,
    OptimizeResponse,
    Order,
    ReoptimizeRequest,
    RunListResponse,
    RunSummary,
    ScenarioImportResponse,
    ScenarioActionRequest,
    ScenarioCompareResponse,
    ScenarioGovernanceSummary,
    ScenarioTransitionView,
    ScenarioVersionDetail,
    ScenarioVersionList,
    ScenarioVersionView,
    ScenarioSpatialStatus,
    RoutingStatus,
    TokenResponse,
)
from app.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.spatial import gcj02_to_wgs84, haversine_m, inside_qidong_bounds
from app.tasks import optimize_scenario_task
from app.weather import WeatherServiceError, get_current_weather


settings = get_settings()
SCENARIO_TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "祁智运场景导入模板.xlsx"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with SessionLocal() as session:
        seed_demo_data(session)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.6.0",
    description="祁东县县域物流智能调度、算法实验、审批下发、驾驶员执行与动态重优化服务",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db),
) -> UserRecord:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少访问令牌")
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效") from exc
    user = session.scalar(select(UserRecord).where(UserRecord.username == payload.get("sub")))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不可用")
    return user


def admin_user(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可维护 AI 配置")
    return user


def dispatcher_user(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role not in {"admin", "dispatcher"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅调度员可执行此操作")
    return user


def driver_user(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role not in {"admin", "driver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅驾驶员可执行此操作")
    return user


def operations_reader(user: UserRecord = Depends(current_user)) -> UserRecord:
    """Read-only operational data is limited to internal operations roles."""
    if user.role not in {"admin", "dispatcher", "driver", "viewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权查看运营数据")
    return user


def customer_user(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅注册用户可提交订单申请")
    return user


def order_request_reader(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role not in {"admin", "user"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权查看用户订单")
    return user


def _active_ai_config(session: Session) -> AIProviderConfigRecord | None:
    return session.scalar(
        select(AIProviderConfigRecord)
        .where(AIProviderConfigRecord.enabled.is_(True))
        .order_by(AIProviderConfigRecord.updated_at.desc())
    )


def _latest_ai_config(session: Session) -> AIProviderConfigRecord | None:
    return session.scalar(
        select(AIProviderConfigRecord).order_by(AIProviderConfigRecord.updated_at.desc())
    )


def _active_map_config(session: Session) -> MapProviderConfigRecord | None:
    return session.scalar(
        select(MapProviderConfigRecord)
        .where(MapProviderConfigRecord.enabled.is_(True))
        .order_by(MapProviderConfigRecord.updated_at.desc())
    )


def _masked_encrypted_secret(value: str) -> tuple[bool, str]:
    """Render a secret safely even when an old encryption key is unavailable."""
    try:
        secret = decrypt_secret(value)
    except ValueError:
        # Keep the settings page usable after an operator rotates the
        # encryption key.  The ciphertext is still treated as configured, but
        # it is never exposed or used until the connection is re-saved.
        return bool(value), "••••••••" if value else ""
    return bool(secret), mask_secret(secret)


def _map_config_view(record: MapProviderConfigRecord) -> MapConfigView:
    has_web_key, web_key_masked = _masked_encrypted_secret(record.encrypted_web_key)
    has_security_code, security_code_masked = _masked_encrypted_secret(
        record.encrypted_security_code
    )
    return MapConfigView(
        id=record.id,
        name=record.name,
        provider=record.provider,
        map_style=record.map_style,
        enabled=record.enabled,
        has_web_key=has_web_key,
        web_key_masked=web_key_masked,
        has_security_code=has_security_code,
        security_code_masked=security_code_masked,
        last_test_status=record.last_test_status,
        last_test_message=record.last_test_message,
        last_tested_at=record.last_tested_at,
        created_by=record.creator.username if record.creator else None,
        updated_by=record.updater.username if record.updater else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _ai_config_view(record: AIProviderConfigRecord) -> AIConfigView:
    has_api_key, api_key_masked = _masked_encrypted_secret(record.encrypted_api_key)
    return AIConfigView(
        id=record.id,
        name=record.name,
        description=record.description,
        provider=record.provider,
        base_url=record.base_url,
        model_name=record.model_name,
        enabled=record.enabled,
        temperature=float(record.temperature),
        has_api_key=has_api_key,
        api_key_masked=api_key_masked,
        last_test_status=record.last_test_status,
        last_test_message=record.last_test_message,
        last_tested_at=record.last_tested_at,
        created_by=record.creator.username if record.creator else None,
        updated_by=record.updater.username if record.updater else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _request_metadata(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("x-forwarded-for")
    ip_address = forwarded.split(",")[0].strip() if forwarded else None
    if not ip_address and request.client:
        ip_address = request.client.host
    return ip_address, request.headers.get("user-agent")


def _audit(
    session: Session,
    *,
    category: str,
    action: str,
    outcome: str = "success",
    actor: UserRecord | None = None,
    actor_username: str | None = None,
    request: Request | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
) -> None:
    ip_address, user_agent = _request_metadata(request) if request else (None, None)
    session.add(
        AuditLogRecord(
            category=category,
            action=action,
            outcome=outcome,
            actor_id=actor.id if actor else None,
            actor_username=actor.username if actor else actor_username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
        )
    )


def _user_view(record: UserRecord) -> UserView:
    now = datetime.now(timezone.utc)
    locked_until = record.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return UserView(
        id=record.id,
        username=record.username,
        display_name=record.display_name or record.username,
        role=record.role,
        is_active=record.is_active,
        is_locked=bool(locked_until and locked_until > now),
        locked_until=record.locked_until,
        failed_login_count=record.failed_login_count,
        last_login_at=record.last_login_at,
        last_login_ip=record.last_login_ip,
        password_changed_at=record.password_changed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _sanitize_audit_detail(value):
    sensitive_terms = ("key", "password", "token", "secret", "authorization", "credential")
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(term in key.lower() for term in sensitive_terms)
                else _sanitize_audit_detail(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_audit_detail(item) for item in value]
    return value


def _audit_view(record: AuditLogRecord) -> AuditLogView:
    return AuditLogView(
        id=record.id,
        category=record.category,
        action=record.action,
        outcome=record.outcome,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        actor_username=record.actor_username,
        ip_address=record.ip_address,
        user_agent=record.user_agent,
        detail=_sanitize_audit_detail(record.detail),
        created_at=record.created_at,
    )


def _master_order_view(record: OrderRecord) -> MasterOrderView:
    return MasterOrderView(
        id=record.id,
        node_id=record.node_id,
        node_name=record.node.name,
        cargo_name=record.cargo_name,
        customer_name=record.customer_name,
        customer_phone=record.customer_phone,
        delivery_address=record.delivery_address,
        weight_kg=record.weight_kg,
        window_start=record.window_start,
        window_end=record.window_end,
        service_minutes=record.service_minutes,
        cold_chain=record.cold_chain,
        priority=record.priority,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _order_request_view(record: OrderRequestRecord) -> OrderRequestView:
    operational = record.operational_order
    return OrderRequestView(
        id=record.id,
        request_code=record.request_code,
        requester_username=record.requester.username,
        requester_name=record.requester.display_name or record.requester.username,
        node_id=record.node_id,
        node_name=record.node.name,
        cargo_name=record.cargo_name,
        customer_name=record.customer_name,
        customer_phone=record.customer_phone,
        delivery_address=record.delivery_address,
        weight_kg=record.weight_kg,
        window_start=record.window_start,
        window_end=record.window_end,
        service_minutes=record.service_minutes,
        cold_chain=record.cold_chain,
        priority=record.priority,
        status=record.status,
        review_note=record.review_note,
        reviewer_username=record.reviewer.username if record.reviewer else None,
        reviewed_at=record.reviewed_at,
        operational_order_id=record.operational_order_id,
        operational_status=operational.status if operational else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _master_vehicle_view(record: VehicleRecord) -> MasterVehicleView:
    return MasterVehicleView(
        id=record.id,
        plate=record.plate,
        capacity_kg=record.capacity_kg,
        cold_chain=record.cold_chain,
        vehicle_type=record.vehicle_type,
        driver_name=record.driver_name,
        driver_phone=record.driver_phone,
        status=record.status,
        available=record.available,
        cost_per_km=float(record.cost_per_km),
        shift_start=record.shift_start,
        shift_end=record.shift_end,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _master_node_view(record: NodeRecord) -> MasterNodeView:
    return MasterNodeView(
        id=record.id,
        name=record.name,
        longitude=float(record.longitude),
        latitude=float(record.latitude),
        wgs84_longitude=(
            float(record.wgs84_longitude) if record.wgs84_longitude is not None else None
        ),
        wgs84_latitude=(
            float(record.wgs84_latitude) if record.wgs84_latitude is not None else None
        ),
        coordinate_system=record.coordinate_system,
        coordinate_source=record.coordinate_source,
        coordinate_status=record.coordinate_status,
        coordinate_accuracy_m=record.coordinate_accuracy_m,
        calibrated_at=record.calibrated_at,
        calibrated_by=record.calibrated_by,
        spatial_issue=(
            "outside_bounds"
            if not inside_qidong_bounds(float(record.longitude), float(record.latitude))
            else "none"
        ),
        kind=record.kind,
        address=record.address,
        contact_name=record.contact_name,
        contact_phone=record.contact_phone,
        service_radius_km=float(record.service_radius_km),
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _coordinate_revision_view(
    record: NodeCoordinateRevisionRecord,
) -> NodeCoordinateRevisionView:
    return NodeCoordinateRevisionView(
        id=record.id,
        node_id=record.node_id,
        before_longitude=(
            float(record.before_longitude) if record.before_longitude is not None else None
        ),
        before_latitude=(
            float(record.before_latitude) if record.before_latitude is not None else None
        ),
        longitude=float(record.longitude),
        latitude=float(record.latitude),
        wgs84_longitude=float(record.wgs84_longitude),
        wgs84_latitude=float(record.wgs84_latitude),
        coordinate_source=record.coordinate_source,
        coordinate_status=record.coordinate_status,
        coordinate_accuracy_m=record.coordinate_accuracy_m,
        address=record.address,
        note=record.note,
        actor_username=record.actor_username,
        created_at=record.created_at,
    )


def _require_active_node(session: Session, node_id: str) -> NodeRecord:
    node = session.get(NodeRecord, node_id)
    if node is None:
        raise HTTPException(status_code=422, detail="所选服务网点不存在")
    if not node.is_active:
        raise HTTPException(status_code=422, detail="所选服务网点已停用，不能承接订单")
    return node


def _ensure_not_last_admin(
    session: Session,
    record: UserRecord,
    *,
    next_role: str,
    next_active: bool,
) -> None:
    removes_admin = record.role == "admin" and (next_role != "admin" or not next_active)
    if not removes_admin:
        return
    active_admins = session.scalar(
        select(func.count(UserRecord.id)).where(
            UserRecord.role == "admin",
            UserRecord.is_active.is_(True),
        )
    )
    if active_admins and active_admins <= 1:
        raise HTTPException(status_code=409, detail="系统必须保留至少一个已启用的管理员账号")


def _scenario_version_view(record: ScenarioVersionRecord) -> ScenarioVersionView:
    return ScenarioVersionView(
        id=record.id,
        scenario_code=record.scenario_code,
        version_no=record.version_no,
        version_key=record.version_key,
        name=record.name,
        county_name=record.county_name,
        status=record.status,
        source_type=record.source_type,
        source_filename=record.source_filename,
        node_count=record.node_count,
        order_count=record.order_count,
        vehicle_count=record.vehicle_count,
        validation_summary=record.validation_summary,
        fingerprint=record.fingerprint or scenario_fingerprint(record.payload),
        release_note=record.release_note,
        created_by=record.creator.display_name if record.creator else None,
        submitted_by=record.submitter.display_name if record.submitter else None,
        submitted_at=record.submitted_at,
        reviewed_by=record.reviewer.display_name if record.reviewer else None,
        reviewed_at=record.reviewed_at,
        review_note=record.review_note,
        created_at=record.created_at,
        activated_at=record.activated_at,
    )


def _scenario_detail_view(
    record: ScenarioVersionRecord,
    transitions: list[ScenarioTransitionRecord],
) -> ScenarioVersionDetail:
    base = _scenario_version_view(record).model_dump()
    return ScenarioVersionDetail(
        **base,
        transitions=[
            ScenarioTransitionView(
                id=item.id,
                from_status=item.from_status,
                to_status=item.to_status,
                note=item.note,
                actor=item.actor.display_name if item.actor else None,
                created_at=item.created_at,
            )
            for item in transitions
        ],
    )


def _data_import_batch_view(record: DataImportBatchRecord) -> DataImportBatchView:
    return DataImportBatchView(
        id=record.id,
        batch_code=record.batch_code,
        import_type=record.import_type,
        filename=record.filename,
        status=record.status,
        total_rows=record.total_rows,
        valid_rows=record.valid_rows,
        error_rows=record.error_rows,
        warning_rows=record.warning_rows,
        errors=record.errors,
        created_by=record.creator.display_name if record.creator else None,
        committed_by=record.committer.display_name if record.committer else None,
        created_at=record.created_at,
        committed_at=record.committed_at,
    )


@app.get("/api/v1/health")
def health(session: Session = Depends(get_db)) -> dict:
    database_ok = True
    try:
        session.execute(text("select 1"))
    except Exception:
        database_ok = False
    return {
        "status": "ok" if database_ok else "degraded",
        "version": app.version,
        "database": database_ok,
        "solvers": {"ortools": True, "pyvrp": True},
    }


@app.get("/api/v1/health/live")
def health_live() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/v1/health/ready")
def health_ready(session: Session = Depends(get_db)) -> dict:
    checks = {"database": False, "redis": False, "migrations": False}
    try:
        session.execute(text("select 1"))
        checks["database"] = True
        checks["migrations"] = bool(
            session.scalar(text("select version_num from alembic_version limit 1"))
        )
    except Exception:
        pass
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        checks["redis"] = bool(client.ping())
        client.close()
    except redis.RedisError:
        pass
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "version": app.version, "checks": checks},
        )
    return {"status": "ready", "version": app.version, "checks": checks}


@app.get("/api/v1/map/runtime", response_model=MapRuntimeConfig)
def map_runtime(
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> MapRuntimeConfig:
    record = _active_map_config(session)
    if not record:
        return MapRuntimeConfig(provider="offline", mode="offline")
    return MapRuntimeConfig(
        provider=record.provider,
        mode="online",
        web_key=decrypt_secret(record.encrypted_web_key),
        map_style=record.map_style,
        service_host="/_AMapService",
    )


@app.get("/_AMapService/{service_path:path}")
@app.get(
    "/api/v1/map/amap-service/{service_path:path}",
    include_in_schema=False,
)
async def amap_service_proxy(
    service_path: str,
    request: Request,
    session: Session = Depends(get_db),
) -> Response:
    record = _active_map_config(session)
    if not record:
        raise HTTPException(status_code=404, detail="未启用高德地图服务")
    if ".." in service_path or service_path.startswith(("http:", "https:")):
        raise HTTPException(status_code=400, detail="地图代理路径无效")
    security_code = decrypt_secret(record.encrypted_security_code)
    if service_path.startswith("v4/map/styles"):
        upstream = f"https://webapi.amap.com/{service_path}"
    else:
        upstream = f"https://restapi.amap.com/{service_path}"
    params = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key.lower() != "jscode"
    ]
    params.append(("jscode", security_code))
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            result = await client.get(upstream, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="地图服务暂时不可用") from exc
    headers = {
        key: value
        for key, value in result.headers.items()
        if key.lower() in {"content-type", "cache-control", "etag", "last-modified"}
    }
    return Response(content=result.content, status_code=result.status_code, headers=headers)


@app.get("/api/v1/map/configs", response_model=MapConfigList)
def list_map_configs(
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MapConfigList:
    records = session.scalars(
        select(MapProviderConfigRecord).order_by(
            MapProviderConfigRecord.enabled.desc(),
            MapProviderConfigRecord.updated_at.desc(),
        )
    ).all()
    return MapConfigList(items=[_map_config_view(record) for record in records])


@app.post("/api/v1/map/configs", response_model=MapConfigView, status_code=status.HTTP_201_CREATED)
def create_map_config(
    payload: MapConfigUpsert,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MapConfigView:
    if not payload.web_key or not payload.web_key.strip():
        raise HTTPException(status_code=422, detail="新建地图连接必须填写 Web JS Key")
    if not payload.security_code or not payload.security_code.strip():
        raise HTTPException(status_code=422, detail="新建地图连接必须填写安全密钥")
    if payload.enabled:
        session.query(MapProviderConfigRecord).update({"enabled": False})
    record = MapProviderConfigRecord(
        name=payload.name.strip(),
        provider=payload.provider,
        encrypted_web_key=encrypt_secret(payload.web_key.strip()),
        encrypted_security_code=encrypt_secret(payload.security_code.strip()),
        map_style=payload.map_style,
        enabled=payload.enabled,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(record)
    session.flush()
    _audit(
        session,
        category="map_configuration",
        action="create",
        actor=user,
        request=request,
        resource_type="map_connection",
        resource_id=str(record.id),
        detail={"provider": record.provider, "enabled": record.enabled},
    )
    session.commit()
    session.refresh(record)
    return _map_config_view(record)


@app.put("/api/v1/map/configs/{config_id}", response_model=MapConfigView)
def update_map_config(
    config_id: int,
    payload: MapConfigUpsert,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MapConfigView:
    record = session.get(MapProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="地图连接不存在")
    if payload.enabled:
        session.query(MapProviderConfigRecord).filter(
            MapProviderConfigRecord.id != config_id
        ).update({"enabled": False})
    record.name = payload.name.strip()
    record.provider = payload.provider
    record.map_style = payload.map_style
    record.enabled = payload.enabled
    record.updated_by = user.id
    record.last_test_status = "untested"
    record.last_test_message = None
    if payload.web_key and payload.web_key.strip():
        record.encrypted_web_key = encrypt_secret(payload.web_key.strip())
    if payload.security_code and payload.security_code.strip():
        record.encrypted_security_code = encrypt_secret(payload.security_code.strip())
    _audit(
        session,
        category="map_configuration",
        action="update",
        actor=user,
        request=request,
        resource_type="map_connection",
        resource_id=str(record.id),
        detail={"provider": record.provider, "enabled": record.enabled},
    )
    session.commit()
    session.refresh(record)
    return _map_config_view(record)


@app.post("/api/v1/map/configs/{config_id}/activate", response_model=MapConfigView)
def activate_map_config(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MapConfigView:
    record = session.get(MapProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="地图连接不存在")
    session.query(MapProviderConfigRecord).filter(
        MapProviderConfigRecord.id != config_id
    ).update({"enabled": False})
    record.enabled = True
    record.updated_by = user.id
    _audit(
        session,
        category="map_configuration",
        action="activate",
        actor=user,
        request=request,
        resource_type="map_connection",
        resource_id=str(record.id),
    )
    session.commit()
    session.refresh(record)
    return _map_config_view(record)


@app.post("/api/v1/map/configs/{config_id}/disable", response_model=MapConfigView)
def disable_map_config(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MapConfigView:
    record = session.get(MapProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="地图连接不存在")
    record.enabled = False
    record.updated_by = user.id
    _audit(
        session,
        category="map_configuration",
        action="disable",
        actor=user,
        request=request,
        resource_type="map_connection",
        resource_id=str(record.id),
    )
    session.commit()
    session.refresh(record)
    return _map_config_view(record)


@app.post("/api/v1/map/configs/{config_id}/test", response_model=AIConnectionTestResponse)
def test_map_config(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConnectionTestResponse:
    record = session.get(MapProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="地图连接不存在")
    web_key = decrypt_secret(record.encrypted_web_key)
    started_at = datetime.now(timezone.utc)
    success = False
    try:
        result = httpx.get(
            "https://webapi.amap.com/maps",
            params={"v": "2.0", "key": web_key},
            timeout=8,
            follow_redirects=True,
        )
        result.raise_for_status()
        invalid_markers = ("INVALID_USER_KEY", "USERKEY_PLAT_NOMATCH")
        success = not any(marker in result.text for marker in invalid_markers)
        message = "地图脚本连接正常，域名与安全代理将在地图加载时继续校验" if success else "Web JS Key 无效或平台类型不匹配"
    except httpx.HTTPError:
        message = "无法连接高德地图脚本服务"
    latency_ms = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000))
    record.last_test_status = "success" if success else "failed"
    record.last_test_message = message
    record.last_tested_at = datetime.now(timezone.utc)
    record.updated_by = user.id
    _audit(
        session,
        category="map_configuration",
        action="test",
        outcome="success" if success else "failed",
        actor=user,
        request=request,
        resource_type="map_connection",
        resource_id=str(record.id),
        detail={"latency_ms": latency_ms},
    )
    session.commit()
    return AIConnectionTestResponse(success=success, message=message, latency_ms=latency_ms)


@app.get("/api/v1/operations/readiness", response_model=OperationsReadinessResponse)
def operations_readiness(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> OperationsReadinessResponse:
    return OperationsReadinessResponse(**build_competition_readiness(session))


@app.get("/api/v1/operations/report")
def operations_report(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> HTMLResponse:
    data = build_competition_readiness(session)
    stamp = data["generated_at"].strftime("%Y%m%d-%H%M%S")
    return HTMLResponse(
        build_competition_report(data),
        headers={
            "Content-Disposition": (
                f'attachment; filename="qizhi-operational-evidence-{stamp}.html"'
            )
        },
    )


@app.get(
    "/api/v1/competition/readiness",
    response_model=OperationsReadinessResponse,
    include_in_schema=False,
)
def legacy_readiness(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> OperationsReadinessResponse:
    return OperationsReadinessResponse(**build_competition_readiness(session))


@app.get("/api/v1/competition/report", include_in_schema=False)
def legacy_operations_report(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> HTMLResponse:
    data = build_competition_readiness(session)
    stamp = data["generated_at"].strftime("%Y%m%d-%H%M%S")
    return HTMLResponse(
        build_competition_report(data),
        headers={
            "Content-Disposition": (
                f'attachment; filename="qizhi-operational-evidence-{stamp}.html"'
            )
        },
    )


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> TokenResponse:
    now = datetime.now(timezone.utc)
    user = session.scalar(select(UserRecord).where(UserRecord.username == credentials.username))
    locked_until = user.locked_until if user else None
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if user and locked_until and locked_until > now:
        _audit(
            session,
            category="authentication",
            action="login",
            outcome="blocked",
            actor=user,
            request=request,
            detail={"reason": "account_locked"},
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"登录失败次数过多，请在 {settings.login_lock_minutes} 分钟后重试",
        )
    if not user or not user.is_active or not verify_password(credentials.password, user.password_hash):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        _audit(
            session,
            category="authentication",
            action="login",
            outcome="failed",
            actor=user,
            actor_username=credentials.username,
            request=request,
            detail={"reason": "invalid_credentials"},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    ip_address, _ = _request_metadata(request)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = ip_address
    if not user.display_name:
        user.display_name = "系统管理员" if user.role == "admin" else user.username
    _audit(
        session,
        category="authentication",
        action="login",
        actor=user,
        request=request,
    )
    session.commit()
    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        role=user.role,
        username=user.username,
        display_name=user.display_name,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@app.post(
    "/api/v1/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> TokenResponse:
    username = payload.username.strip()
    display_name = payload.display_name.strip()
    if len(display_name) < 2:
        raise HTTPException(status_code=422, detail="姓名或称呼至少需要 2 个字符")
    if session.scalar(select(UserRecord).where(UserRecord.username == username)):
        _audit(
            session,
            category="authentication",
            action="register",
            outcome="failed",
            actor_username=username,
            request=request,
            detail={"reason": "username_exists"},
        )
        session.commit()
        raise HTTPException(status_code=409, detail="该登录账号已被使用")
    try:
        validate_password_policy(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    ip_address, _ = _request_metadata(request)
    record = UserRecord(
        username=username,
        display_name=display_name,
        password_hash=hash_password(payload.password),
        role="user",
        is_active=True,
        failed_login_count=0,
        last_login_at=now,
        last_login_ip=ip_address,
        password_changed_at=now,
    )
    session.add(record)
    session.flush()
    _audit(
        session,
        category="authentication",
        action="register",
        actor=record,
        request=request,
        resource_type="user",
        resource_id=str(record.id),
        detail={"assigned_role": "user", "agreement_accepted": True},
    )
    session.commit()
    return TokenResponse(
        access_token=create_access_token(record.username, record.role),
        role=record.role,
        username=record.username,
        display_name=record.display_name,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@app.get("/api/v1/auth/me", response_model=CurrentUserView)
def me(user: UserRecord = Depends(current_user)) -> CurrentUserView:
    return CurrentUserView(
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
        last_login_at=user.last_login_at,
    )


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    user: UserRecord = Depends(current_user),
    session: Session = Depends(get_db),
) -> None:
    _audit(session, category="authentication", action="logout", actor=user, request=request)
    session.commit()


@app.get("/api/v1/users", response_model=UserList)
def list_users(
    search: str | None = Query(default=None, max_length=100),
    role: str | None = Query(default=None),
    account_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> UserList:
    statement = select(UserRecord)
    count_statement = select(func.count(UserRecord.id))
    conditions = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                UserRecord.username.ilike(pattern),
                UserRecord.display_name.ilike(pattern),
            )
        )
    if role:
        conditions.append(UserRecord.role == role)
    if account_status == "active":
        conditions.append(UserRecord.is_active.is_(True))
    elif account_status == "disabled":
        conditions.append(UserRecord.is_active.is_(False))
    elif account_status == "locked":
        conditions.append(UserRecord.locked_until > datetime.now(timezone.utc))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = session.scalar(count_statement) or 0
    records = session.scalars(
        statement.order_by(UserRecord.created_at.asc(), UserRecord.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    now = datetime.now(timezone.utc)
    active_count = session.scalar(
        select(func.count(UserRecord.id)).where(UserRecord.is_active.is_(True))
    ) or 0
    admin_count = session.scalar(
        select(func.count(UserRecord.id)).where(
            UserRecord.role == "admin",
            UserRecord.is_active.is_(True),
        )
    ) or 0
    locked_count = session.scalar(
        select(func.count(UserRecord.id)).where(UserRecord.locked_until > now)
    ) or 0
    return UserList(
        items=[_user_view(record) for record in records],
        total=total,
        active_count=active_count,
        admin_count=admin_count,
        locked_count=locked_count,
    )


@app.post("/api/v1/users", response_model=UserView, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> UserView:
    if session.scalar(select(UserRecord).where(UserRecord.username == payload.username)):
        raise HTTPException(status_code=409, detail="登录账号已存在")
    try:
        validate_password_policy(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)
    record = UserRecord(
        username=payload.username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        password_changed_at=now,
    )
    session.add(record)
    session.flush()
    _audit(
        session,
        category="user_management",
        action="create_user",
        actor=actor,
        request=request,
        resource_type="user",
        resource_id=str(record.id),
        detail={"username": record.username, "role": record.role},
    )
    session.commit()
    session.refresh(record)
    return _user_view(record)


@app.put("/api/v1/users/{user_id}", response_model=UserView)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> UserView:
    record = session.get(UserRecord, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="用户不存在")
    if record.id == actor.id and (not payload.is_active or payload.role != "admin"):
        raise HTTPException(status_code=409, detail="不能停用当前账号或移除自己的管理员角色")
    _ensure_not_last_admin(
        session,
        record,
        next_role=payload.role,
        next_active=payload.is_active,
    )
    changes = {
        "display_name": [record.display_name, payload.display_name.strip()],
        "role": [record.role, payload.role],
        "is_active": [record.is_active, payload.is_active],
    }
    record.display_name = payload.display_name.strip()
    record.role = payload.role
    record.is_active = payload.is_active
    if payload.unlock:
        record.failed_login_count = 0
        record.locked_until = None
    _audit(
        session,
        category="user_management",
        action="update_user",
        actor=actor,
        request=request,
        resource_type="user",
        resource_id=str(record.id),
        detail={
            "username": record.username,
            "changes": changes,
            "unlocked": payload.unlock,
        },
    )
    session.commit()
    session.refresh(record)
    return _user_view(record)


@app.post("/api/v1/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> None:
    record = session.get(UserRecord, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        validate_password_policy(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record.password_hash = hash_password(payload.password)
    record.password_changed_at = datetime.now(timezone.utc)
    record.failed_login_count = 0
    record.locked_until = None
    _audit(
        session,
        category="user_management",
        action="reset_password",
        actor=actor,
        request=request,
        resource_type="user",
        resource_id=str(record.id),
        detail={"username": record.username},
    )
    session.commit()


@app.get("/api/v1/order-requests/options", response_model=OrderRequestNodeOptionList)
def order_request_options(
    _: UserRecord = Depends(customer_user),
    session: Session = Depends(get_db),
) -> OrderRequestNodeOptionList:
    records = session.scalars(
        select(NodeRecord)
        .where(NodeRecord.is_active.is_(True), NodeRecord.kind != "depot")
        .order_by(NodeRecord.kind, NodeRecord.name, NodeRecord.id)
    ).all()
    return OrderRequestNodeOptionList(
        items=[
            OrderRequestNodeOption(
                id=record.id,
                name=record.name,
                address=record.address,
                kind=record.kind,
            )
            for record in records
        ]
    )


@app.post(
    "/api/v1/order-requests",
    response_model=OrderRequestView,
    status_code=status.HTTP_201_CREATED,
)
def create_order_request(
    payload: OrderRequestCreate,
    request: Request,
    actor: UserRecord = Depends(customer_user),
    session: Session = Depends(get_db),
) -> OrderRequestView:
    _require_active_node(session, payload.node_id)
    request_code = f"UR-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}"
    record = OrderRequestRecord(
        request_code=request_code,
        requester_id=actor.id,
        **payload.model_dump(),
    )
    session.add(record)
    session.flush()
    _audit(
        session,
        category="order_request",
        action="submit",
        actor=actor,
        request=request,
        resource_type="order_request",
        resource_id=str(record.id),
        detail={"request_code": record.request_code, "node_id": record.node_id},
    )
    session.commit()
    session.refresh(record)
    return _order_request_view(record)


@app.get("/api/v1/order-requests/mine", response_model=OrderRequestList)
def list_my_order_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: UserRecord = Depends(customer_user),
    session: Session = Depends(get_db),
) -> OrderRequestList:
    statement = select(OrderRequestRecord).where(
        OrderRequestRecord.requester_id == actor.id
    )
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    records = session.scalars(
        statement.order_by(
            OrderRequestRecord.created_at.desc(), OrderRequestRecord.id.desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return OrderRequestList(
        items=[_order_request_view(record) for record in records], total=total
    )


@app.get("/api/v1/order-requests", response_model=OrderRequestList)
def list_order_requests(
    request_status: str | None = Query(default=None, alias="status", max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> OrderRequestList:
    statement = select(OrderRequestRecord)
    if request_status:
        statement = statement.where(OrderRequestRecord.status == request_status)
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    records = session.scalars(
        statement.order_by(
            OrderRequestRecord.created_at.desc(), OrderRequestRecord.id.desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return OrderRequestList(
        items=[_order_request_view(record) for record in records], total=total
    )


@app.get("/api/v1/order-requests/{request_id}", response_model=OrderRequestView)
def get_order_request(
    request_id: int,
    actor: UserRecord = Depends(order_request_reader),
    session: Session = Depends(get_db),
) -> OrderRequestView:
    record = session.get(OrderRequestRecord, request_id)
    if record is None or (actor.role == "user" and record.requester_id != actor.id):
        raise HTTPException(status_code=404, detail="订单申请不存在")
    return _order_request_view(record)


def _approve_order_request(
    session: Session,
    record: OrderRequestRecord,
    actor: UserRecord,
    note: str | None = None,
) -> str:
    if record.operational_order_id:
        raise HTTPException(status_code=409, detail="该订单申请已经纳入运营订单")
    _require_active_node(session, record.node_id)
    operational_order_id = f"ORD-{record.request_code.removeprefix('UR-')}"
    if session.get(OrderRecord, operational_order_id):
        raise HTTPException(status_code=409, detail="运营订单编号冲突，请联系管理员")
    session.add(
        OrderRecord(
            id=operational_order_id,
            node_id=record.node_id,
            weight_kg=record.weight_kg,
            window_start=record.window_start,
            window_end=record.window_end,
            service_minutes=record.service_minutes,
            cold_chain=record.cold_chain,
            priority=record.priority,
            status="pending",
            cargo_name=record.cargo_name,
            customer_name=record.customer_name,
            customer_phone=record.customer_phone,
            delivery_address=record.delivery_address,
        )
    )
    record.operational_order_id = operational_order_id
    record.status = "converted"
    record.reviewed_by = actor.id
    record.reviewed_at = datetime.now(timezone.utc)
    record.review_note = note or "审核通过，已纳入运营调度"
    session.flush()
    try:
        scenario, warnings = build_scenario_from_master(
            session, name="祁东县用户订单运营场景"
        )
    except OrderImportError:
        session.rollback()
        raise
    version = create_scenario_version(
        session,
        scenario_code="master-data",
        county_name="祁东县",
        scenario=scenario,
        source_filename=f"用户订单申请 {record.request_code}",
        warnings=warnings,
        created_by=actor.id,
    )
    activate_scenario_version(
        session,
        version,
        actor_id=actor.id,
        note=f"订单申请 {record.request_code} 审核通过并自动纳入调度",
    )
    return version.version_key


@app.post(
    "/api/v1/order-requests/{request_id}/review",
    response_model=OrderRequestView,
)
def review_order_request(
    request_id: int,
    payload: OrderRequestReviewRequest,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> OrderRequestView:
    record = session.get(OrderRequestRecord, request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="订单申请不存在")
    if record.status not in {"pending_review", "needs_info"}:
        raise HTTPException(status_code=409, detail="当前申请状态不允许重复审核")
    note = (payload.note or "").strip()
    scenario_key: str | None = None
    try:
        if payload.action == "approve":
            scenario_key = _approve_order_request(session, record, actor, note)
        else:
            record.status = "needs_info" if payload.action == "needs_info" else "rejected"
            record.reviewed_by = actor.id
            record.reviewed_at = datetime.now(timezone.utc)
            record.review_note = note or (
                "请补充配送信息后重新提交" if payload.action == "needs_info" else "申请未通过审核"
            )
    except OrderImportError as exc:
        raise HTTPException(status_code=409, detail=f"申请暂不能纳入调度：{exc}") from exc
    _audit(
        session,
        category="order_request",
        action="review",
        actor=actor,
        request=request,
        resource_type="order_request",
        resource_id=str(record.id),
        detail={
            "request_code": record.request_code,
            "action": payload.action,
            "status": record.status,
            "operational_order_id": record.operational_order_id,
            "scenario_key": scenario_key,
        },
    )
    session.commit()
    session.refresh(record)
    return _order_request_view(record)


@app.post("/api/v1/order-requests/{request_id}/cancel", response_model=OrderRequestView)
def cancel_order_request(
    request_id: int,
    request: Request,
    actor: UserRecord = Depends(customer_user),
    session: Session = Depends(get_db),
) -> OrderRequestView:
    record = session.get(OrderRequestRecord, request_id)
    if record is None or record.requester_id != actor.id:
        raise HTTPException(status_code=404, detail="订单申请不存在")
    if record.status not in {"pending_review", "needs_info"}:
        raise HTTPException(status_code=409, detail="当前申请状态不能撤回")
    record.status = "cancelled"
    record.review_note = "用户主动撤回申请"
    _audit(
        session,
        category="order_request",
        action="cancel",
        actor=actor,
        request=request,
        resource_type="order_request",
        resource_id=str(record.id),
        detail={"request_code": record.request_code},
    )
    session.commit()
    session.refresh(record)
    return _order_request_view(record)


def _audit_query(
    *,
    days: int,
    category: str | None,
    outcome: str | None,
    actor: str | None,
    search: str | None,
):
    statement = select(AuditLogRecord).where(
        AuditLogRecord.created_at >= datetime.now(timezone.utc) - timedelta(days=days)
    )
    if category:
        statement = statement.where(AuditLogRecord.category == category)
    if outcome:
        statement = statement.where(AuditLogRecord.outcome == outcome)
    if actor:
        statement = statement.where(AuditLogRecord.actor_username.ilike(f"%{actor.strip()}%"))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                AuditLogRecord.action.ilike(pattern),
                AuditLogRecord.resource_type.ilike(pattern),
                AuditLogRecord.resource_id.ilike(pattern),
            )
        )
    return statement


@app.get("/api/v1/audit-logs", response_model=AuditLogList)
def list_audit_logs(
    days: int = Query(default=7, ge=1, le=90),
    category: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    actor: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AuditLogList:
    statement = _audit_query(
        days=days,
        category=category,
        outcome=outcome,
        actor=actor,
        search=search,
    )
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    records = session.scalars(
        statement.order_by(AuditLogRecord.created_at.desc(), AuditLogRecord.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AuditLogList(items=[_audit_view(record) for record in records], total=total)


@app.get("/api/v1/audit-logs/export")
def export_audit_logs(
    days: int = Query(default=7, ge=1, le=90),
    category: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    actor: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=100),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    records = session.scalars(
        _audit_query(
            days=days,
            category=category,
            outcome=outcome,
            actor=actor,
            search=search,
        )
        .order_by(AuditLogRecord.created_at.desc(), AuditLogRecord.id.desc())
        .limit(5000)
    ).all()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["时间", "分类", "动作", "操作者", "资源类型", "资源", "来源 IP", "结果"])
    for record in records:
        writer.writerow(
            [
                record.created_at.isoformat(),
                record.category,
                record.action,
                record.actor_username or "",
                record.resource_type or "",
                record.resource_id or "",
                record.ip_address or "",
                record.outcome,
            ]
        )
    filename = f"audit-logs-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/master-data/summary", response_model=MasterDataSummary)
def master_data_summary(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterDataSummary:
    return MasterDataSummary(
        order_total=session.scalar(select(func.count(OrderRecord.id))) or 0,
        pending_orders=session.scalar(
            select(func.count(OrderRecord.id)).where(OrderRecord.status == "pending")
        )
        or 0,
        cold_chain_orders=session.scalar(
            select(func.count(OrderRecord.id)).where(OrderRecord.cold_chain.is_(True))
        )
        or 0,
        invalid_orders=session.scalar(
            select(func.count(OrderRecord.id))
            .join(NodeRecord, OrderRecord.node_id == NodeRecord.id)
            .where(NodeRecord.is_active.is_(False))
        )
        or 0,
        vehicle_total=session.scalar(select(func.count(VehicleRecord.id))) or 0,
        available_vehicles=session.scalar(
            select(func.count(VehicleRecord.id)).where(VehicleRecord.status == "available")
        )
        or 0,
        node_total=session.scalar(select(func.count(NodeRecord.id))) or 0,
        active_nodes=session.scalar(
            select(func.count(NodeRecord.id)).where(NodeRecord.is_active.is_(True))
        )
        or 0,
    )


@app.get("/api/v1/reference/qidong-summary", response_model=QidongReferenceSummary)
def qidong_reference_summary(
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> QidongReferenceSummary:
    """Return the curated research baseline without exposing raw source files."""
    return QidongReferenceSummary.model_validate(
        build_qidong_reference_summary(load_scenario(session))
    )


@app.get("/api/v1/master-data/orders/import/template")
def order_import_template(_: UserRecord = Depends(dispatcher_user)) -> StreamingResponse:
    content = build_order_import_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="qizhi-order-import-template.xlsx"'
        },
    )


@app.post(
    "/api/v1/master-data/orders/import/preview",
    response_model=DataImportBatchView,
    status_code=status.HTTP_201_CREATED,
)
async def preview_master_order_import(
    request: Request,
    file: UploadFile = File(...),
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DataImportBatchView:
    filename = Path(file.filename or "").name
    try:
        record = preview_order_import(
            session,
            filename=filename,
            content=await file.read(),
            created_by=actor.id,
        )
    except OrderImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(
        session,
        category="master_data",
        action="preview_order_import",
        actor=actor,
        request=request,
        resource_type="data_import_batch",
        resource_id=str(record.id),
        detail={
            "batch_code": record.batch_code,
            "filename": record.filename,
            "total_rows": record.total_rows,
            "error_rows": record.error_rows,
        },
    )
    session.commit()
    return _data_import_batch_view(record)


@app.get("/api/v1/master-data/imports", response_model=DataImportBatchList)
def master_data_import_batches(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DataImportBatchList:
    total = session.scalar(select(func.count(DataImportBatchRecord.id))) or 0
    records = list(
        session.scalars(
            select(DataImportBatchRecord)
            .order_by(
                DataImportBatchRecord.created_at.desc(),
                DataImportBatchRecord.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return DataImportBatchList(
        items=[_data_import_batch_view(record) for record in records],
        total=total,
    )


@app.get("/api/v1/master-data/imports/{batch_id}/errors")
def master_data_import_errors(
    batch_id: int,
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    record = session.get(DataImportBatchRecord, batch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="导入批次不存在")
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["批次号", "文件名", "行号", "错误字段", "错误说明"])
    for item in record.errors:
        writer.writerow(
            [
                record.batch_code,
                record.filename,
                item.get("row", ""),
                item.get("field", ""),
                item.get("message", ""),
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{record.batch_code}-errors.csv"'
            )
        },
    )


@app.post(
    "/api/v1/master-data/imports/{batch_id}/commit",
    response_model=DataImportBatchView,
)
def commit_master_data_import(
    batch_id: int,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DataImportBatchView:
    record = session.get(DataImportBatchRecord, batch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="导入批次不存在")
    try:
        record = commit_order_import(session, record, committed_by=actor.id)
    except OrderImportError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        category="master_data",
        action="commit_order_import",
        actor=actor,
        request=request,
        resource_type="data_import_batch",
        resource_id=str(record.id),
        detail={"batch_code": record.batch_code, "rows": record.valid_rows},
    )
    session.commit()
    return _data_import_batch_view(record)


@app.get("/api/v1/master-data/quality-report", response_model=DataQualityReport)
def master_data_quality_report(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DataQualityReport:
    items = [DataQualityRuleView.model_validate(item) for item in quality_report(session)]
    blocked_count = sum(item.status == "blocked" for item in items)
    warning_count = sum(item.status == "warning" for item in items)
    return DataQualityReport(
        items=items,
        blocked_count=blocked_count,
        warning_count=warning_count,
        publish_ready=blocked_count == 0,
    )


@app.put(
    "/api/v1/master-data/quality-rules/{rule_id}",
    response_model=DataQualityRuleView,
)
def update_master_data_quality_rule(
    rule_id: int,
    payload: DataQualityRuleUpdate,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> DataQualityRuleView:
    record = session.get(DataQualityRuleRecord, rule_id)
    if record is None:
        raise HTTPException(status_code=404, detail="数据质量规则不存在")
    record.enabled = payload.enabled
    record.severity = payload.severity
    record.updated_by = actor.id
    _audit(
        session,
        category="master_data",
        action="update_quality_rule",
        actor=actor,
        request=request,
        resource_type="data_quality_rule",
        resource_id=str(record.id),
        detail={"enabled": record.enabled, "severity": record.severity},
    )
    session.commit()
    session.refresh(record)
    item = next(
        item for item in quality_report(session) if item["id"] == record.id
    )
    return DataQualityRuleView.model_validate(item)


@app.post(
    "/api/v1/master-data/publish",
    response_model=MasterDataPublishResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_master_data(
    payload: MasterDataPublishRequest,
    request: Request,
    actor: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> MasterDataPublishResponse:
    try:
        scenario, warnings = build_scenario_from_master(session, name=payload.name)
    except OrderImportError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record = create_scenario_version(
        session,
        scenario_code="master-data",
        county_name="祁东县",
        scenario=scenario,
        source_filename="基础数据中心发布",
        warnings=warnings,
        created_by=actor.id,
    )
    if payload.activate:
        record = activate_scenario_version(session, record)
    _audit(
        session,
        category="master_data",
        action="publish_scenario",
        actor=actor,
        request=request,
        resource_type="scenario_version",
        resource_id=str(record.id),
        detail={
            "version_key": record.version_key,
            "status": record.status,
            "order_count": record.order_count,
        },
    )
    session.commit()
    return MasterDataPublishResponse(
        scenario=_scenario_version_view(record),
        warnings=warnings,
    )


@app.get("/api/v1/master-data/orders", response_model=MasterOrderList)
def master_orders(
    search: str | None = Query(default=None, max_length=100),
    order_status: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    cold_chain: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterOrderList:
    statement = select(OrderRecord)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                OrderRecord.id.ilike(pattern),
                OrderRecord.cargo_name.ilike(pattern),
                OrderRecord.customer_name.ilike(pattern),
                OrderRecord.customer_phone.ilike(pattern),
            )
        )
    if order_status:
        statement = statement.where(OrderRecord.status == order_status)
    if priority:
        statement = statement.where(OrderRecord.priority == priority)
    if cold_chain is not None:
        statement = statement.where(OrderRecord.cold_chain.is_(cold_chain))
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    records = session.scalars(
        statement.order_by(OrderRecord.updated_at.desc(), OrderRecord.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MasterOrderList(items=[_master_order_view(record) for record in records], total=total)


@app.post(
    "/api/v1/master-data/orders",
    response_model=MasterOrderView,
    status_code=status.HTTP_201_CREATED,
)
def create_master_order(
    payload: MasterOrderCreate,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterOrderView:
    if session.get(OrderRecord, payload.id):
        raise HTTPException(status_code=409, detail="订单编号已存在")
    _require_active_node(session, payload.node_id)
    values = payload.model_dump()
    order_id = values.pop("id")
    record = OrderRecord(id=order_id, **values)
    session.add(record)
    _audit(
        session,
        category="master_data",
        action="create_order",
        actor=actor,
        request=request,
        resource_type="order",
        resource_id=record.id,
        detail={"node_id": record.node_id, "status": record.status},
    )
    session.commit()
    session.refresh(record)
    return _master_order_view(record)


@app.put("/api/v1/master-data/orders/{order_id}", response_model=MasterOrderView)
def update_master_order(
    order_id: str,
    payload: MasterOrderInput,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterOrderView:
    record = session.get(OrderRecord, order_id)
    if record is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    _require_active_node(session, payload.node_id)
    if record.status == "completed" and payload.status != "completed":
        raise HTTPException(status_code=409, detail="已完成订单不能回退状态")
    for field, value in payload.model_dump().items():
        setattr(record, field, value)
    _audit(
        session,
        category="master_data",
        action="update_order",
        actor=actor,
        request=request,
        resource_type="order",
        resource_id=record.id,
        detail={"node_id": record.node_id, "status": record.status},
    )
    session.commit()
    session.refresh(record)
    return _master_order_view(record)


@app.delete("/api/v1/master-data/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_order(
    order_id: str,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> None:
    record = session.get(OrderRecord, order_id)
    if record is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if record.status not in {"pending", "cancelled"}:
        raise HTTPException(status_code=409, detail="只有待调度或已取消订单可以删除")
    if session.scalar(
        select(OrderRequestRecord.id).where(
            OrderRequestRecord.operational_order_id == record.id
        )
    ):
        raise HTTPException(status_code=409, detail="该订单来自用户申请，请保留申请链路")
    session.delete(record)
    _audit(
        session,
        category="master_data",
        action="delete_order",
        actor=actor,
        request=request,
        resource_type="order",
        resource_id=order_id,
    )
    session.commit()


@app.get("/api/v1/master-data/vehicles", response_model=MasterVehicleList)
def master_vehicles(
    search: str | None = Query(default=None, max_length=100),
    vehicle_status: str | None = Query(default=None, alias="status"),
    cold_chain: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterVehicleList:
    statement = select(VehicleRecord)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                VehicleRecord.id.ilike(pattern),
                VehicleRecord.plate.ilike(pattern),
                VehicleRecord.driver_name.ilike(pattern),
            )
        )
    if vehicle_status:
        statement = statement.where(VehicleRecord.status == vehicle_status)
    if cold_chain is not None:
        statement = statement.where(VehicleRecord.cold_chain.is_(cold_chain))
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    records = session.scalars(
        statement.order_by(VehicleRecord.updated_at.desc(), VehicleRecord.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MasterVehicleList(
        items=[_master_vehicle_view(record) for record in records],
        total=total,
    )


@app.post(
    "/api/v1/master-data/vehicles",
    response_model=MasterVehicleView,
    status_code=status.HTTP_201_CREATED,
)
def create_master_vehicle(
    payload: MasterVehicleCreate,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterVehicleView:
    if session.get(VehicleRecord, payload.id):
        raise HTTPException(status_code=409, detail="车辆编号已存在")
    if session.scalar(select(VehicleRecord).where(VehicleRecord.plate == payload.plate)):
        raise HTTPException(status_code=409, detail="车牌号已存在")
    values = payload.model_dump()
    vehicle_id = values.pop("id")
    record = VehicleRecord(
        id=vehicle_id,
        available=payload.status == "available",
        **values,
    )
    session.add(record)
    _audit(
        session,
        category="master_data",
        action="create_vehicle",
        actor=actor,
        request=request,
        resource_type="vehicle",
        resource_id=record.id,
        detail={"plate": record.plate, "status": record.status},
    )
    session.commit()
    session.refresh(record)
    return _master_vehicle_view(record)


@app.put("/api/v1/master-data/vehicles/{vehicle_id}", response_model=MasterVehicleView)
def update_master_vehicle(
    vehicle_id: str,
    payload: MasterVehicleInput,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterVehicleView:
    record = session.get(VehicleRecord, vehicle_id)
    if record is None:
        raise HTTPException(status_code=404, detail="车辆不存在")
    plate_owner = session.scalar(
        select(VehicleRecord).where(
            VehicleRecord.plate == payload.plate,
            VehicleRecord.id != vehicle_id,
        )
    )
    if plate_owner:
        raise HTTPException(status_code=409, detail="车牌号已存在")
    for field, value in payload.model_dump().items():
        setattr(record, field, value)
    record.available = payload.status == "available"
    _audit(
        session,
        category="master_data",
        action="update_vehicle",
        actor=actor,
        request=request,
        resource_type="vehicle",
        resource_id=record.id,
        detail={"plate": record.plate, "status": record.status},
    )
    session.commit()
    session.refresh(record)
    return _master_vehicle_view(record)


@app.delete("/api/v1/master-data/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_vehicle(
    vehicle_id: str,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> None:
    record = session.get(VehicleRecord, vehicle_id)
    if record is None:
        raise HTTPException(status_code=404, detail="车辆不存在")
    assignment_count = session.scalar(
        select(func.count(DriverAssignmentRecord.id)).where(
            DriverAssignmentRecord.vehicle_id == vehicle_id
        )
    )
    if assignment_count:
        raise HTTPException(status_code=409, detail="车辆已有调度执行记录，不能删除，请改为停用")
    session.delete(record)
    _audit(
        session,
        category="master_data",
        action="delete_vehicle",
        actor=actor,
        request=request,
        resource_type="vehicle",
        resource_id=vehicle_id,
    )
    session.commit()


@app.get("/api/v1/master-data/nodes", response_model=MasterNodeList)
def master_nodes(
    search: str | None = Query(default=None, max_length=100),
    kind: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    coordinate_status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterNodeList:
    statement = select(NodeRecord)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                NodeRecord.id.ilike(pattern),
                NodeRecord.name.ilike(pattern),
                NodeRecord.address.ilike(pattern),
                NodeRecord.contact_name.ilike(pattern),
            )
        )
    if kind:
        statement = statement.where(NodeRecord.kind == kind)
    if active is not None:
        statement = statement.where(NodeRecord.is_active.is_(active))
    if coordinate_status:
        if coordinate_status not in {"unverified", "verified", "needs_review"}:
            raise HTTPException(status_code=422, detail="无效的坐标核验状态")
        statement = statement.where(NodeRecord.coordinate_status == coordinate_status)
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    records = session.scalars(
        statement.order_by(NodeRecord.updated_at.desc(), NodeRecord.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MasterNodeList(items=[_master_node_view(record) for record in records], total=total)


@app.post(
    "/api/v1/master-data/nodes",
    response_model=MasterNodeView,
    status_code=status.HTTP_201_CREATED,
)
def create_master_node(
    payload: MasterNodeCreate,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterNodeView:
    if session.get(NodeRecord, payload.id):
        raise HTTPException(status_code=409, detail="网点编号已存在")
    values = payload.model_dump()
    node_id = values.pop("id")
    wgs84_longitude, wgs84_latitude = gcj02_to_wgs84(
        values["longitude"], values["latitude"]
    )
    record = NodeRecord(
        id=node_id,
        **values,
        wgs84_longitude=wgs84_longitude,
        wgs84_latitude=wgs84_latitude,
        coordinate_status="unverified",
        coordinate_source="manual",
    )
    session.add(record)
    _audit(
        session,
        category="master_data",
        action="create_node",
        actor=actor,
        request=request,
        resource_type="node",
        resource_id=record.id,
        detail={"kind": record.kind, "is_active": record.is_active},
    )
    session.commit()
    session.refresh(record)
    return _master_node_view(record)


@app.put("/api/v1/master-data/nodes/{node_id}", response_model=MasterNodeView)
def update_master_node(
    node_id: str,
    payload: MasterNodeInput,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterNodeView:
    record = session.get(NodeRecord, node_id)
    if record is None:
        raise HTTPException(status_code=404, detail="服务网点不存在")
    previous_longitude = float(record.longitude)
    previous_latitude = float(record.latitude)
    values = payload.model_dump()
    coordinate_changed = (
        abs(values["longitude"] - previous_longitude) > 0.0000005
        or abs(values["latitude"] - previous_latitude) > 0.0000005
    )
    for field, value in values.items():
        setattr(record, field, value)
    if coordinate_changed:
        wgs84_longitude, wgs84_latitude = gcj02_to_wgs84(
            values["longitude"], values["latitude"]
        )
        record.wgs84_longitude = wgs84_longitude
        record.wgs84_latitude = wgs84_latitude
        record.coordinate_source = "manual"
        record.coordinate_status = "needs_review"
        record.coordinate_accuracy_m = None
        record.calibrated_at = None
        record.calibrated_by = None
        session.add(
            NodeCoordinateRevisionRecord(
                node_id=record.id,
                before_longitude=previous_longitude,
                before_latitude=previous_latitude,
                longitude=values["longitude"],
                latitude=values["latitude"],
                wgs84_longitude=wgs84_longitude,
                wgs84_latitude=wgs84_latitude,
                coordinate_source="manual",
                coordinate_status="needs_review",
                address=values.get("address"),
                note="通过网点档案修改坐标，等待空间核验",
                actor_id=actor.id,
                actor_username=actor.username,
            )
        )
    _audit(
        session,
        category="master_data",
        action="update_node",
        actor=actor,
        request=request,
        resource_type="node",
        resource_id=record.id,
        detail={"kind": record.kind, "is_active": record.is_active},
    )
    session.commit()
    session.refresh(record)
    return _master_node_view(record)


@app.get(
    "/api/v1/master-data/spatial-quality",
    response_model=SpatialQualitySummary,
)
def master_spatial_quality(
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> SpatialQualitySummary:
    records = session.scalars(select(NodeRecord)).all()
    coordinate_counts: dict[tuple[float, float], int] = {}
    for record in records:
        coordinate = (float(record.longitude), float(record.latitude))
        coordinate_counts[coordinate] = coordinate_counts.get(coordinate, 0) + 1
    duplicate = sum(
        count for count in coordinate_counts.values() if count > 1
    )
    return SpatialQualitySummary(
        total=len(records),
        verified=sum(record.coordinate_status == "verified" for record in records),
        needs_review=sum(record.coordinate_status == "needs_review" for record in records),
        unverified=sum(record.coordinate_status == "unverified" for record in records),
        outside_bounds=sum(
            not inside_qidong_bounds(float(record.longitude), float(record.latitude))
            for record in records
        ),
        duplicate=duplicate,
        missing_address=sum(not (record.address or "").strip() for record in records),
    )


@app.get(
    "/api/v1/master-data/nodes/{node_id}/coordinate-revisions",
    response_model=NodeCoordinateRevisionList,
)
def node_coordinate_revisions(
    node_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> NodeCoordinateRevisionList:
    if session.get(NodeRecord, node_id) is None:
        raise HTTPException(status_code=404, detail="服务网点不存在")
    records = session.scalars(
        select(NodeCoordinateRevisionRecord)
        .where(NodeCoordinateRevisionRecord.node_id == node_id)
        .order_by(NodeCoordinateRevisionRecord.created_at.desc())
        .limit(limit)
    ).all()
    return NodeCoordinateRevisionList(
        items=[_coordinate_revision_view(record) for record in records]
    )


@app.put(
    "/api/v1/master-data/nodes/{node_id}/coordinate",
    response_model=MasterNodeView,
)
def calibrate_node_coordinate(
    node_id: str,
    payload: NodeCoordinateUpdate,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> MasterNodeView:
    record = session.get(NodeRecord, node_id)
    if record is None:
        raise HTTPException(status_code=404, detail="服务网点不存在")
    previous_longitude = float(record.longitude)
    previous_latitude = float(record.latitude)
    wgs84_longitude, wgs84_latitude = gcj02_to_wgs84(
        payload.longitude, payload.latitude
    )
    shift_m = haversine_m(
        previous_longitude,
        previous_latitude,
        payload.longitude,
        payload.latitude,
    )
    record.longitude = payload.longitude
    record.latitude = payload.latitude
    record.wgs84_longitude = wgs84_longitude
    record.wgs84_latitude = wgs84_latitude
    record.coordinate_system = "gcj02"
    record.coordinate_source = payload.coordinate_source
    record.coordinate_status = payload.coordinate_status
    record.coordinate_accuracy_m = payload.coordinate_accuracy_m
    if payload.address is not None:
        record.address = payload.address.strip() or None
    record.calibrated_at = datetime.now(timezone.utc)
    record.calibrated_by = actor.id
    revision = NodeCoordinateRevisionRecord(
        node_id=record.id,
        before_longitude=previous_longitude,
        before_latitude=previous_latitude,
        longitude=payload.longitude,
        latitude=payload.latitude,
        wgs84_longitude=wgs84_longitude,
        wgs84_latitude=wgs84_latitude,
        coordinate_source=payload.coordinate_source,
        coordinate_status=payload.coordinate_status,
        coordinate_accuracy_m=payload.coordinate_accuracy_m,
        address=record.address,
        note=payload.note,
        actor_id=actor.id,
        actor_username=actor.username,
    )
    session.add(revision)
    _audit(
        session,
        category="master_data",
        action="calibrate_node_coordinate",
        actor=actor,
        request=request,
        resource_type="node",
        resource_id=record.id,
        detail={
            "coordinate_system": "gcj02",
            "storage_coordinate_system": "wgs84",
            "coordinate_status": payload.coordinate_status,
            "coordinate_source": payload.coordinate_source,
            "shift_m": round(shift_m, 2),
            "inside_qidong_bounds": inside_qidong_bounds(
                payload.longitude, payload.latitude
            ),
        },
    )
    session.commit()
    session.refresh(record)
    return _master_node_view(record)


@app.delete("/api/v1/master-data/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_node(
    node_id: str,
    request: Request,
    actor: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> None:
    record = session.get(NodeRecord, node_id)
    if record is None:
        raise HTTPException(status_code=404, detail="服务网点不存在")
    order_count = session.scalar(
        select(func.count(OrderRecord.id)).where(OrderRecord.node_id == node_id)
    )
    if order_count:
        raise HTTPException(status_code=409, detail="网点已被订单引用，不能删除，请改为停用")
    session.delete(record)
    _audit(
        session,
        category="master_data",
        action="delete_node",
        actor=actor,
        request=request,
        resource_type="node",
        resource_id=node_id,
    )
    session.commit()


@app.get("/api/v1/ai/config", response_model=AIConfigView | None)
def get_ai_config(
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView | None:
    record = _latest_ai_config(session)
    return _ai_config_view(record) if record else None


@app.get("/api/v1/ai/configs", response_model=AIConfigList)
def list_ai_configs(
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigList:
    records = session.scalars(
        select(AIProviderConfigRecord).order_by(
            AIProviderConfigRecord.enabled.desc(),
            AIProviderConfigRecord.updated_at.desc(),
        )
    ).all()
    return AIConfigList(items=[_ai_config_view(record) for record in records])


@app.post("/api/v1/ai/configs", response_model=AIConfigView, status_code=status.HTTP_201_CREATED)
def create_ai_config(
    payload: AIConfigUpsert,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView:
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(status_code=422, detail="新建连接必须填写 API Key")
    if payload.enabled:
        session.query(AIProviderConfigRecord).update({"enabled": False})
    record = AIProviderConfigRecord(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        provider=payload.provider.strip(),
        base_url=payload.base_url,
        model_name=payload.model_name.strip(),
        encrypted_api_key=encrypt_secret(payload.api_key.strip()),
        enabled=payload.enabled,
        temperature=payload.temperature,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(record)
    session.flush()
    _audit(
        session,
        category="ai_configuration",
        action="create",
        actor=user,
        request=request,
        resource_type="ai_connection",
        resource_id=str(record.id),
        detail={"provider": record.provider, "enabled": record.enabled},
    )
    session.commit()
    session.refresh(record)
    return _ai_config_view(record)


@app.put("/api/v1/ai/configs/{config_id}", response_model=AIConfigView)
def update_ai_config(
    config_id: int,
    payload: AIConfigUpsert,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView:
    record = session.get(AIProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="AI 连接不存在")
    if payload.enabled:
        session.query(AIProviderConfigRecord).filter(
            AIProviderConfigRecord.id != config_id
        ).update({"enabled": False})
    record.name = payload.name.strip()
    record.description = payload.description.strip() if payload.description else None
    record.provider = payload.provider.strip()
    record.base_url = payload.base_url
    record.model_name = payload.model_name.strip()
    record.enabled = payload.enabled
    record.temperature = payload.temperature
    record.updated_by = user.id
    record.last_test_status = "untested"
    record.last_test_message = None
    if payload.api_key and payload.api_key.strip():
        record.encrypted_api_key = encrypt_secret(payload.api_key.strip())
    _audit(
        session,
        category="ai_configuration",
        action="update",
        actor=user,
        request=request,
        resource_type="ai_connection",
        resource_id=str(record.id),
        detail={"provider": record.provider, "enabled": record.enabled},
    )
    session.commit()
    session.refresh(record)
    return _ai_config_view(record)


@app.post("/api/v1/ai/configs/{config_id}/activate", response_model=AIConfigView)
def activate_ai_config(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView:
    record = session.get(AIProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="AI 连接不存在")
    session.query(AIProviderConfigRecord).filter(
        AIProviderConfigRecord.id != config_id
    ).update({"enabled": False})
    record.enabled = True
    record.updated_by = user.id
    _audit(
        session,
        category="ai_configuration",
        action="activate",
        actor=user,
        request=request,
        resource_type="ai_connection",
        resource_id=str(record.id),
    )
    session.commit()
    session.refresh(record)
    return _ai_config_view(record)


@app.post("/api/v1/ai/configs/{config_id}/disable", response_model=AIConfigView)
def disable_ai_config(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView:
    record = session.get(AIProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="AI 连接不存在")
    record.enabled = False
    record.updated_by = user.id
    _audit(
        session,
        category="ai_configuration",
        action="disable",
        actor=user,
        request=request,
        resource_type="ai_connection",
        resource_id=str(record.id),
    )
    session.commit()
    session.refresh(record)
    return _ai_config_view(record)


@app.post("/api/v1/ai/configs/{config_id}/test", response_model=AIConnectionTestResponse)
def test_ai_config_by_id(
    config_id: int,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConnectionTestResponse:
    record = session.get(AIProviderConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="AI 连接不存在")
    try:
        message, latency_ms = test_ai_connection(record)
        record.last_test_status = "success"
        record.last_test_message = message[:240]
        response = AIConnectionTestResponse(success=True, message=message, latency_ms=latency_ms)
    except AIServiceError as exc:
        latency_ms = exc.latency_ms
        record.last_test_status = "failed"
        record.last_test_message = str(exc)[:500]
        response = AIConnectionTestResponse(
            success=False, message=str(exc), latency_ms=latency_ms
        )
    record.last_tested_at = datetime.now(timezone.utc)
    record.updated_by = user.id
    _audit(
        session,
        category="ai_configuration",
        action="test",
        outcome="success" if response.success else "failed",
        actor=user,
        request=request,
        resource_type="ai_connection",
        resource_id=str(record.id),
        detail={"latency_ms": latency_ms},
    )
    session.commit()
    return response


@app.put("/api/v1/ai/config", response_model=AIConfigView)
def upsert_ai_config(
    request: AIConfigUpsert,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConfigView:
    record = _latest_ai_config(session)
    if request.enabled:
        enabled_query = session.query(AIProviderConfigRecord)
        if record is not None:
            enabled_query = enabled_query.filter(AIProviderConfigRecord.id != record.id)
        enabled_query.update({"enabled": False}, synchronize_session=False)

    if record is None:
        if not request.api_key or not request.api_key.strip():
            raise HTTPException(status_code=422, detail="首次配置必须填写 API Key")
        record = AIProviderConfigRecord(
            name=request.name.strip(),
            description=request.description.strip() if request.description else None,
            provider=request.provider.strip(),
            base_url=request.base_url,
            model_name=request.model_name.strip(),
            encrypted_api_key=encrypt_secret(request.api_key.strip()),
            enabled=request.enabled,
            temperature=request.temperature,
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(record)
    else:
        record.name = request.name.strip()
        record.description = request.description.strip() if request.description else None
        record.provider = request.provider.strip()
        record.base_url = request.base_url
        record.model_name = request.model_name.strip()
        record.enabled = request.enabled
        record.temperature = request.temperature
        record.updated_by = user.id
        record.last_test_status = "untested"
        record.last_test_message = None
        if request.api_key and request.api_key.strip():
            record.encrypted_api_key = encrypt_secret(request.api_key.strip())

    session.flush()
    session.commit()
    session.refresh(record)
    return _ai_config_view(record)


@app.post("/api/v1/ai/config/test", response_model=AIConnectionTestResponse)
def test_saved_ai_config(
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> AIConnectionTestResponse:
    record = _active_ai_config(session)
    if not record:
        raise HTTPException(status_code=404, detail="尚未配置并启用 AI 服务")
    try:
        message, latency_ms = test_ai_connection(record)
        record.last_test_status = "success"
        record.last_test_message = message[:240]
        response = AIConnectionTestResponse(success=True, message=message, latency_ms=latency_ms)
    except AIServiceError as exc:
        latency_ms = exc.latency_ms
        record.last_test_status = "failed"
        record.last_test_message = str(exc)[:500]
        response = AIConnectionTestResponse(success=False, message=str(exc), latency_ms=latency_ms)
    record.last_tested_at = datetime.now(timezone.utc)
    session.commit()
    return response


@app.post("/api/v1/ai/explain/{run_id}", response_model=AIExplanationResponse)
def explain_saved_run(
    run_id: str,
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> AIExplanationResponse:
    record = session.get(OptimizationRunRecord, run_id)
    if not record:
        raise HTTPException(status_code=404, detail="调度方案不存在")
    config = _active_ai_config(session)
    if not config:
        raise HTTPException(status_code=409, detail="请先在系统设置中启用 AI 服务")
    try:
        explanation, _ = explain_optimization(config, record.output)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AIExplanationResponse(
        run_id=run_id,
        provider=config.provider,
        model_name=config.model_name,
        explanation=explanation,
    )


@app.get("/api/v1/scenarios/template")
def scenario_template(_: UserRecord = Depends(admin_user)) -> FileResponse:
    if not SCENARIO_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=503, detail="场景模板尚未生成")
    return FileResponse(
        SCENARIO_TEMPLATE_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="祁智运场景导入模板.xlsx",
    )


@app.get("/api/v1/scenarios", response_model=ScenarioVersionList)
def scenario_versions(
    search: str | None = Query(default=None, max_length=100),
    version_status: str | None = Query(default=None, alias="status", max_length=20),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionList:
    statement = select(ScenarioVersionRecord)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                ScenarioVersionRecord.name.ilike(term),
                ScenarioVersionRecord.version_key.ilike(term),
                ScenarioVersionRecord.scenario_code.ilike(term),
                ScenarioVersionRecord.county_name.ilike(term),
            )
        )
    if version_status:
        statement = statement.where(ScenarioVersionRecord.status == version_status)
    records = list(
        session.scalars(
            statement.order_by(
                ScenarioVersionRecord.created_at.desc(),
                ScenarioVersionRecord.id.desc(),
            )
        )
    )
    counts = dict(
        session.execute(
            select(ScenarioVersionRecord.status, func.count(ScenarioVersionRecord.id)).group_by(
                ScenarioVersionRecord.status
            )
        ).all()
    )
    total = sum(int(value) for value in counts.values())
    return ScenarioVersionList(
        items=[_scenario_version_view(record) for record in records],
        total=total,
        summary=ScenarioGovernanceSummary(
            total=total,
            active=counts.get("active", 0),
            pending_review=counts.get("pending_review", 0),
            draft=counts.get("draft", 0),
            rejected=counts.get("rejected", 0),
            archived=counts.get("archived", 0),
        ),
    )


@app.post("/api/v1/scenarios/import", response_model=ScenarioImportResponse)
async def import_scenario(
    request: Request,
    file: UploadFile = File(...),
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioImportResponse:
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="只支持 .xlsx 场景文件")
    content = await file.read()
    try:
        scenario_code, county_name, imported_scenario, warnings = parse_scenario_workbook(content)
    except ScenarioImportError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    record = create_scenario_version(
        session,
        scenario_code=scenario_code,
        county_name=county_name,
        scenario=imported_scenario,
        source_filename=filename,
        warnings=warnings,
        created_by=user.id,
    )
    _audit(
        session,
        category="scenario_management",
        action="import_scenario",
        actor=user,
        request=request,
        resource_type="scenario_version",
        resource_id=str(record.id),
        detail={"version_key": record.version_key, "filename": filename},
    )
    session.commit()
    return ScenarioImportResponse(scenario=_scenario_version_view(record), warnings=warnings)


@app.get("/api/v1/scenarios/compare", response_model=ScenarioCompareResponse)
def compare_scenario_versions(
    base_id: int = Query(gt=0),
    target_id: int = Query(gt=0),
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioCompareResponse:
    if base_id == target_id:
        raise HTTPException(status_code=422, detail="请选择两个不同的场景版本")
    base = session.get(ScenarioVersionRecord, base_id)
    target = session.get(ScenarioVersionRecord, target_id)
    if base is None or target is None:
        raise HTTPException(status_code=404, detail="场景版本不存在")
    result = compare_scenarios(base, target)
    result["base"] = _scenario_version_view(base)
    result["target"] = _scenario_version_view(target)
    return ScenarioCompareResponse(
        **result,
    )


@app.get("/api/v1/scenarios/{scenario_id}", response_model=ScenarioVersionDetail)
def scenario_version_detail(
    scenario_id: int,
    _: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionDetail:
    record = session.get(ScenarioVersionRecord, scenario_id)
    if record is None:
        raise HTTPException(status_code=404, detail="场景版本不存在")
    transitions = list(
        session.scalars(
            select(ScenarioTransitionRecord)
            .where(ScenarioTransitionRecord.scenario_version_id == scenario_id)
            .order_by(ScenarioTransitionRecord.created_at.desc(), ScenarioTransitionRecord.id.desc())
        )
    )
    return _scenario_detail_view(record, transitions)


def _governance_action(
    *,
    action: str,
    service,
    scenario_id: int,
    payload: ScenarioActionRequest,
    user: UserRecord,
    request: Request,
    session: Session,
) -> ScenarioVersionView:
    record = session.get(ScenarioVersionRecord, scenario_id)
    if record is None:
        raise HTTPException(status_code=404, detail="场景版本不存在")
    try:
        updated = service(session, record, actor_id=user.id, note=payload.note)
    except ScenarioGovernanceError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        category="scenario_management",
        action=action,
        actor=user,
        request=request,
        resource_type="scenario_version",
        resource_id=str(updated.id),
        detail={"version_key": updated.version_key, "note": payload.note},
    )
    session.commit()
    return _scenario_version_view(updated)


@app.post("/api/v1/scenarios/{scenario_id}/submit", response_model=ScenarioVersionView)
def submit_scenario(
    scenario_id: int,
    payload: ScenarioActionRequest,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionView:
    return _governance_action(
        action="submit_scenario",
        service=submit_scenario_version,
        scenario_id=scenario_id,
        payload=payload,
        user=user,
        request=request,
        session=session,
    )


@app.post("/api/v1/scenarios/{scenario_id}/approve", response_model=ScenarioVersionView)
def approve_scenario(
    scenario_id: int,
    payload: ScenarioActionRequest,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionView:
    return _governance_action(
        action="approve_scenario",
        service=approve_scenario_version,
        scenario_id=scenario_id,
        payload=payload,
        user=user,
        request=request,
        session=session,
    )


@app.post("/api/v1/scenarios/{scenario_id}/reject", response_model=ScenarioVersionView)
def reject_scenario(
    scenario_id: int,
    payload: ScenarioActionRequest,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionView:
    return _governance_action(
        action="reject_scenario",
        service=reject_scenario_version,
        scenario_id=scenario_id,
        payload=payload,
        user=user,
        request=request,
        session=session,
    )


@app.post("/api/v1/scenarios/{scenario_id}/rollback", response_model=ScenarioVersionView)
def rollback_scenario(
    scenario_id: int,
    payload: ScenarioActionRequest,
    request: Request,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionView:
    return _governance_action(
        action="rollback_scenario",
        service=rollback_scenario_version,
        scenario_id=scenario_id,
        payload=payload,
        user=user,
        request=request,
        session=session,
    )


@app.post("/api/v1/scenarios/{scenario_id}/activate", response_model=ScenarioVersionView)
def activate_scenario(
    scenario_id: int,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ScenarioVersionView:
    record = session.get(ScenarioVersionRecord, scenario_id)
    if record is None:
        raise HTTPException(status_code=404, detail="场景版本不存在")
    return _scenario_version_view(
        activate_scenario_version(session, record, actor_id=user.id)
    )


@app.get("/api/v1/scenario")
def scenario(
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
):
    return load_scenario(session)


@app.get(
    "/api/v1/scenario/spatial-status",
    response_model=ScenarioSpatialStatus,
)
def scenario_spatial_status(
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> ScenarioSpatialStatus:
    current = load_scenario(session)
    return get_scenario_spatial_status(session, current)


@app.get("/api/v1/dashboard")
def dashboard(
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> dict:
    current = load_scenario(session)
    return {
        "scenario_id": current.id,
        "orders": {
            "total": 128,
            "demo_tasks": len(current.orders),
            "cold_chain": sum(order.cold_chain for order in current.orders),
            "urgent": sum(order.priority == "urgent" for order in current.orders),
        },
        "vehicles": {"available": 12, "demo_vehicles": len(current.vehicles), "cold_chain": 4},
        "data_note": "内置基准数据",
    }


@app.get("/api/v1/routing/status", response_model=RoutingStatus)
def routing_status(_: UserRecord = Depends(operations_reader)) -> RoutingStatus:
    entries, capacity = cache_status()
    return RoutingStatus(
        requested_provider=settings.routing_provider,
        osrm_base_url=settings.osrm_base_url if settings.routing_provider == "osrm" else None,
        cache_entries=entries,
        cache_capacity=capacity,
    )


@app.get("/api/v1/weather/current", response_model=CurrentWeather)
async def current_weather(_: UserRecord = Depends(operations_reader)) -> CurrentWeather:
    try:
        return await get_current_weather()
    except WeatherServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.get("/api/v1/analytics/forecast", response_model=DemandForecast)
def demand_forecast(
    days: int = Query(default=7, ge=3, le=30),
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> DemandForecast:
    order_date = func.date(OrderRecord.created_at)
    rows = session.execute(
        select(order_date, func.sum(OrderRecord.weight_kg))
        .where(OrderRecord.status != "cancelled")
        .group_by(order_date)
        .order_by(order_date)
    ).all()
    history = [
        (
            value if isinstance(value, date) else date.fromisoformat(str(value)),
            float(weight or 0) / 1000,
        )
        for value, weight in rows
        if value is not None
    ]
    return build_demand_forecast(
        load_scenario(session),
        horizon_days=days,
        demand_history=history,
    )


@app.post("/api/v1/optimize", response_model=OptimizeResponse)
def optimize(
    request: OptimizeRequest,
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> OptimizeResponse:
    try:
        current = load_scenario(session, request.scenario_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = orchestrate_optimization(
        current,
        request,
        ai_config=_active_ai_config(session),
    )
    save_run(session, result, scenario_id=current.id)
    return result


@app.post("/api/v1/events/reoptimize", response_model=OptimizeResponse)
def reoptimize(
    request: ReoptimizeRequest,
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> OptimizeResponse:
    if request.profile == "standard-v1":
        request = request.model_copy(
            update={
                "event": Event(
                    type="vehicle_breakdown",
                    vehicle_id="V-COLD-01",
                    occurred_at_minute=90,
                    node_id="V-SHANGYI",
                    longitude=111.842611,
                    latitude=26.826567,
                    location_name="尚义村",
                ),
                "urgent_orders": ["O-URGENT-01"],
                "candidate_count": 1,
            }
        )
    current = load_scenario(session)
    node_map = {node.id: node for node in current.nodes}
    if request.event.type == "vehicle_breakdown" and request.event.vehicle_id:
        if request.event.vehicle_id not in {
            vehicle.id for vehicle in current.vehicles
        }:
            raise HTTPException(status_code=422, detail="事件车辆不在当前场景中")
    unavailable = {
        request.event.vehicle_id
        for _ in [0]
        if request.event.type == "vehicle_breakdown" and request.event.vehicle_id
    }
    fallback_target = next(
        (order.node_id for order in current.orders if order.cold_chain),
        current.orders[0].node_id,
    )
    if request.event.longitude is not None and request.event.latitude is not None:
        event_node = node_map.get(request.event.node_id or "")
        event_location = EventLocationView(
            node_id=request.event.node_id,
            location_name=(
                request.event.location_name
                or (event_node.name if event_node else "事件上报位置")
            ),
            longitude=request.event.longitude,
            latitude=request.event.latitude,
            source="request",
        )
    else:
        event_node_id = request.event.node_id or fallback_target
        event_node = node_map.get(event_node_id)
        if event_node is None:
            raise HTTPException(status_code=422, detail="事件位置网点不在当前场景中")
        event_location = EventLocationView(
            node_id=event_node.id,
            location_name=request.event.location_name or event_node.name,
            longitude=event_node.longitude,
            latitude=event_node.latitude,
            source="scenario_node",
        )
    urgent_target = event_location.node_id or fallback_target
    if urgent_target not in node_map:
        urgent_target = fallback_target
    urgent_id = "O-URGENT-01"
    existing_order_ids = {order.id for order in current.orders}
    while urgent_id in existing_order_ids:
        urgent_id = f"{urgent_id}-E"
    urgent = Order(
        id=urgent_id,
        node_id=urgent_target,
        weight_kg=360,
        window_start=request.event.occurred_at_minute,
        window_end=request.event.occurred_at_minute + 180,
        service_minutes=8,
        cold_chain=True,
        priority="urgent",
    )
    # 故障场景启用县域应急冷藏备用车，仍保持冷链兼容为硬约束。
    emergency_vehicle_id = (
        "V-NORM-03"
        if request.profile == "standard-v1"
        else next(
        (
            vehicle.id
            for vehicle in sorted(current.vehicles, key=lambda item: item.cost_per_km)
            if vehicle.available and vehicle.id not in unavailable and not vehicle.cold_chain
        ),
        None,
        )
    )
    current.vehicles = [
        vehicle.model_copy(
            update={
                "cold_chain": True,
                "capacity_kg": 2600,
                "plate": f"{vehicle.plate}（应急冷藏）",
            }
        )
        if vehicle.id == emergency_vehicle_id
        else vehicle
        for vehicle in current.vehicles
    ]
    result = orchestrate_optimization(
        current,
        OptimizeRequest(
            profile=request.profile,
            time_limit_seconds=5,
            ai_assisted=request.ai_assisted,
            candidate_count=request.candidate_count,
        ),
        ai_config=_active_ai_config(session),
        unavailable_vehicle_ids=unavailable,
        extra_orders=[urgent],
    )
    result.event_location = event_location
    result.explanations = [
        f"事件车辆 {request.event.vehicle_id or '未指定'} 已从可用运力中移除。",
        (
            f"事件位置已锁定为 {event_location.location_name}"
            f"（{event_location.longitude:.6f}, {event_location.latitude:.6f}，GCJ-02）。"
        ),
        "已执行路段视为冻结，并启用县域应急冷藏备用车承接紧急订单。",
        "剩余冷链车辆承接受影响订单，冷链兼容与时间窗约束均已重新校验。",
    ]
    save_run(
        session,
        result,
        scenario_id=current.id,
        event_type=request.event.type,
        event_vehicle_id=request.event.vehicle_id,
        event_location=event_location,
        occurred_at_minute=request.event.occurred_at_minute,
    )
    return result


@app.get("/api/v1/runs", response_model=RunListResponse)
def run_history(
    limit: int = Query(default=20, ge=1, le=100),
    before: datetime | None = Query(default=None),
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> RunListResponse:
    records = list_runs(session, limit=limit, before=before)
    items = [
        RunSummary(
            run_id=record.id,
            scenario_id=record.scenario_id,
            status=record.status,
            solver=record.solver,
            solve_time_ms=record.solve_time_ms,
            distance_km=float(record.distance_km),
            estimated_cost_cny=float(record.estimated_cost_cny),
            vehicles_used=record.vehicles_used,
            event_type=record.event_type,
            event_vehicle_id=record.event_vehicle_id,
            created_at=record.created_at,
        )
        for record in records
    ]
    return RunListResponse(items=items, next_cursor=records[-1].created_at if len(records) == limit else None)


@app.get("/api/v1/runs/latest", response_model=OptimizeResponse | None)
def latest_run(
    scenario_id: str | None = Query(default=None, max_length=64),
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> dict | None:
    active_scenario_id = scenario_id or load_scenario(session).id
    record = session.scalar(
        select(OptimizationRunRecord)
        .where(
            OptimizationRunRecord.scenario_id == active_scenario_id,
            OptimizationRunRecord.status.in_(("optimal", "feasible")),
        )
        .order_by(
            OptimizationRunRecord.created_at.desc(),
            OptimizationRunRecord.id.desc(),
        )
        .limit(1)
    )
    return record.output if record else None


@app.get("/api/v1/runs/{run_id}", response_model=OptimizeResponse)
def run_detail(
    run_id: str,
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> dict:
    record = session.get(OptimizationRunRecord, run_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调度方案不存在")
    return record.output


@app.get("/api/v1/experiments", response_model=ExperimentList)
def experiments(
    limit: int = Query(default=20, ge=1, le=100),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> ExperimentList:
    return ExperimentList(
        items=[experiment_view(item) for item in list_experiments(session, limit)]
    )


@app.post("/api/v1/experiments", response_model=ExperimentView)
def create_experiment(
    request: ExperimentCreate,
    user: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> ExperimentView:
    try:
        return experiment_view(run_experiment(session, request, user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"算法实验执行失败：{exc}",
        ) from exc


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentView)
def experiment_detail(
    experiment_id: int,
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> ExperimentView:
    try:
        return experiment_view(get_experiment(session, experiment_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/experiments/{experiment_id}/report", response_class=HTMLResponse)
def experiment_report(
    experiment_id: int,
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        record = get_experiment(session, experiment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    summary = record.summary or {}
    rows = "".join(
        (
            "<tr>"
            f"<td>{escape(str(item['case_name']))}</td>"
            f"<td>{escape(str(item['status']))}</td>"
            f"<td>{float(item['demand_tons']):.2f} t</td>"
            f"<td>{float(item['baseline_distance_km']):.1f} km</td>"
            f"<td>{float(item['optimized_distance_km']):.1f} km</td>"
            f"<td>{float(item['distance_reduction_pct']):.1f}%</td>"
            f"<td>¥ {float(item['cost_saving_cny']):,.0f}</td>"
            f"<td>{int(item['vehicles_used'])}</td>"
            f"<td>{int(item['unassigned_orders'])}</td>"
            "</tr>"
        )
        for item in record.results
    )
    content = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>祁智运算法对照实验报告</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;color:#173426;margin:36px}}h1{{margin:0 0 6px}}
.meta{{color:#68786f;margin-bottom:24px}}.summary{{display:flex;gap:36px;padding:16px;background:#edf6f0;border-left:5px solid #17834f}}
.summary b{{display:block;font-size:22px;margin-top:4px}}table{{width:100%;border-collapse:collapse;margin-top:24px}}
th,td{{padding:9px;border:1px solid #dce5df;text-align:left}}th{{background:#0d5737;color:white}}
.method{{margin-top:22px;padding:14px;background:#fff8e9;border-left:4px solid #d79a26;font-size:13px;line-height:1.8}}
footer{{margin-top:28px;color:#78867e;font-size:12px}}@media print{{body{{margin:18mm}}}}
</style></head><body>
<h1>祁智运算法对照实验报告</h1>
<div class="meta">{escape(record.experiment_code)} · {escape(record.name)} · 场景 {escape(record.scenario_key)}</div>
<div class="summary">
<div>平均里程降低<b>{float(summary.get('average_distance_reduction_pct', 0)):.1f}%</b></div>
<div>累计成本差额<b>¥ {float(summary.get('total_cost_saving_cny', 0)):,.0f}</b></div>
<div>平均服务率<b>{float(summary.get('average_service_rate', 0)):.1f}%</b></div>
<div>总求解耗时<b>{int(summary.get('total_solve_time_ms', 0))} ms</b></div>
</div>
<table><thead><tr><th>压力案例</th><th>状态</th><th>货量</th><th>业务基线</th><th>OR-Tools</th><th>里程改善</th><th>成本差额</th><th>车辆</th><th>未分配</th></tr></thead>
<tbody>{rows or '<tr><td colspan="9">暂无实验结果</td></tr>'}</tbody></table>
<div class="method"><b>复现实验口径</b><br>
求解器：{escape(record.solver)}；业务基线：轮询启发式；单案例时限：{record.time_limit_seconds} 秒；
场景 SHA-256：{escape(record.scenario_fingerprint)}。基线用于表示未优化的固定轮询业务策略，不代表数学最优解。
</div>
<footer>生成时间：{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} · 本报告可使用浏览器打印为 PDF。</footer>
</body></html>"""
    return HTMLResponse(
        content=content,
        headers={
            "Content-Disposition": (
                f'attachment; filename="algorithm-experiment-{record.id}.html"'
            )
        },
    )


@app.get("/api/v1/dispatch/plans", response_model=DispatchPlanList)
def dispatch_plans(
    limit: int = Query(default=30, ge=1, le=100),
    _: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DispatchPlanList:
    return DispatchPlanList(items=[plan_view(session, item) for item in list_plans(session, limit)])


@app.post("/api/v1/dispatch/plans", response_model=DispatchPlanView)
def submit_dispatch_plan(
    request: DispatchPlanCreate,
    user: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    try:
        record = create_plan(session, request.run_id, user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DispatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return plan_view(session, record)


@app.post("/api/v1/dispatch/plans/{plan_id}/approve", response_model=DispatchPlanView)
def approve_dispatch_plan(
    plan_id: int,
    request: DispatchReviewRequest,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    try:
        record = review_plan(session, plan_id, user, approve=True, note=request.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DispatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return plan_view(session, record)


@app.post("/api/v1/dispatch/plans/{plan_id}/reject", response_model=DispatchPlanView)
def reject_dispatch_plan(
    plan_id: int,
    request: DispatchReviewRequest,
    user: UserRecord = Depends(admin_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    try:
        record = review_plan(session, plan_id, user, approve=False, note=request.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DispatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return plan_view(session, record)


@app.post("/api/v1/dispatch/plans/{plan_id}/dispatch", response_model=DispatchPlanView)
def issue_dispatch_plan(
    plan_id: int,
    user: UserRecord = Depends(dispatcher_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    try:
        record = dispatch_approved_plan(session, plan_id, user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DispatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return plan_view(session, record)


@app.get("/api/v1/driver/assignments", response_model=DriverAssignmentList)
def driver_assignments(
    user: UserRecord = Depends(driver_user),
    session: Session = Depends(get_db),
) -> DriverAssignmentList:
    return DriverAssignmentList(
        items=[assignment_view(item) for item in list_driver_assignments(session, user)]
    )


def _assignment_action(
    assignment_id: int,
    action: str,
    request: AssignmentActionRequest,
    user: UserRecord,
    session: Session,
) -> DispatchPlanView:
    try:
        record = advance_assignment(session, assignment_id, user, action, request.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DispatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return plan_view(session, record)


@app.post("/api/v1/driver/assignments/{assignment_id}/accept", response_model=DispatchPlanView)
def accept_driver_assignment(
    assignment_id: int,
    request: AssignmentActionRequest,
    user: UserRecord = Depends(driver_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    return _assignment_action(assignment_id, "accept", request, user, session)


@app.post("/api/v1/driver/assignments/{assignment_id}/start", response_model=DispatchPlanView)
def start_driver_assignment(
    assignment_id: int,
    request: AssignmentActionRequest,
    user: UserRecord = Depends(driver_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    return _assignment_action(assignment_id, "start", request, user, session)


@app.post("/api/v1/driver/assignments/{assignment_id}/complete", response_model=DispatchPlanView)
def complete_driver_assignment(
    assignment_id: int,
    request: AssignmentActionRequest,
    user: UserRecord = Depends(driver_user),
    session: Session = Depends(get_db),
) -> DispatchPlanView:
    return _assignment_action(assignment_id, "complete", request, user, session)


@app.get("/api/v1/dispatch/plans/{plan_id}/report", response_class=HTMLResponse)
def dispatch_plan_report(
    plan_id: int,
    _: UserRecord = Depends(operations_reader),
    session: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        plan = get_plan(session, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = "".join(
        (
            "<tr>"
            f"<td>{escape(item.plate)}</td>"
            f"<td>{escape(item.driver.username if item.driver else '未分配')}</td>"
            f"<td>{escape(item.status)}</td>"
            f"<td>{float(item.route_payload.get('distance_km', 0)):.1f} km</td>"
            f"<td>{int(item.route_payload.get('load_kg', 0))} kg</td>"
            f"<td>{max(0, len(item.route_payload.get('stops', [])) - 2)}</td>"
            "</tr>"
        )
        for item in plan.assignments
    )
    content = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>祁智运调度执行报告</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;color:#173426;margin:36px}}
h1{{margin:0 0 6px}} .meta{{color:#68786f;margin-bottom:24px}}
.summary{{display:flex;gap:36px;padding:16px;background:#edf6f0;border-left:5px solid #17834f}}
.summary b{{display:block;font-size:22px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin-top:24px}}th,td{{padding:10px;border:1px solid #dce5df;text-align:left}}
th{{background:#0d5737;color:white}}footer{{margin-top:28px;color:#78867e;font-size:12px}}
@media print{{body{{margin:18mm}}}}
</style></head><body>
<h1>祁智运调度执行报告</h1>
<div class="meta">执行单 #{plan.id} · 求解方案 {escape(plan.run_id)} · 状态 {escape(plan.status)}</div>
<div class="summary">
<div>路线数量<b>{len(plan.assignments) or len(plan.run.output.get("routes", []))}</b></div>
<div>总里程<b>{float(plan.run.distance_km):.1f} km</b></div>
<div>预计成本<b>¥ {float(plan.run.estimated_cost_cny):,.0f}</b></div>
<div>场景版本<b>{escape(plan.run.scenario_id)}</b></div>
</div>
<table><thead><tr><th>车辆</th><th>驾驶员</th><th>执行状态</th><th>里程</th><th>载重</th><th>停靠点</th></tr></thead>
<tbody>{rows or '<tr><td colspan="6">方案尚未下发</td></tr>'}</tbody></table>
<footer>生成时间：{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} · 本报告可使用浏览器打印为 PDF。</footer>
</body></html>"""
    return HTMLResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="dispatch-plan-{plan.id}.html"'},
    )


@app.post("/api/v1/jobs/optimize", response_model=AsyncJobResponse, status_code=202)
def enqueue_optimization(
    request: OptimizeRequest,
    _: UserRecord = Depends(dispatcher_user),
) -> AsyncJobResponse:
    try:
        task = optimize_scenario_task.delay(request.time_limit_seconds, request.scenario_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="异步任务服务暂不可用，请检查 Redis 与 Worker",
        ) from exc
    return AsyncJobResponse(task_id=task.id, status="PENDING")


@app.get("/api/v1/jobs/{task_id}", response_model=AsyncJobStatus)
def job_status(
    task_id: str,
    _: UserRecord = Depends(dispatcher_user),
) -> AsyncJobStatus:
    task = AsyncResult(task_id, app=celery_app)
    result = task.result if task.successful() and isinstance(task.result, dict) else None
    error = str(task.result) if task.failed() else None
    return AsyncJobStatus(task_id=task_id, status=task.status, result=result, error=error)
