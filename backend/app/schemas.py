from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FlowDirection = Literal["upward", "downward"]
CargoCategory = Literal["agricultural", "industrial"]


class Node(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    kind: Literal["depot", "town", "village", "processor"]
    coordinate_system: Literal["gcj02"] = "gcj02"
    coordinate_source: Literal["seed", "imported", "geocoded", "manual"] = "seed"
    coordinate_status: Literal["unverified", "verified", "needs_review"] = "unverified"
    wgs84_longitude: float | None = Field(default=None, ge=-180, le=180)
    wgs84_latitude: float | None = Field(default=None, ge=-90, le=90)
    coordinate_accuracy_m: int | None = Field(default=None, ge=0)
    calibrated_at: datetime | None = None


class Order(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    node_id: str = Field(min_length=1, max_length=32)
    weight_kg: int = Field(gt=0)
    window_start: int = Field(ge=0)
    window_end: int = Field(gt=0)
    service_minutes: int = Field(default=8, ge=0)
    cold_chain: bool = False
    priority: Literal["normal", "urgent"] = "normal"
    completed: bool = False
    flow_direction: FlowDirection = "downward"
    cargo_category: CargoCategory = "agricultural"
    origin_node_id: str | None = None
    destination_node_id: str | None = None


class Vehicle(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    plate: str = Field(min_length=1, max_length=64)
    capacity_kg: int = Field(gt=0)
    cold_chain: bool = False
    available: bool = True
    cost_per_km: float = Field(default=3.2, gt=0)
    shift_start: int = 0
    shift_end: int = 600

    @model_validator(mode="after")
    def validate_shift(self) -> "Vehicle":
        if self.shift_start < 0 or self.shift_end <= self.shift_start:
            raise ValueError("车辆班次结束时间必须大于非负的开始时间")
        return self


class Scenario(BaseModel):
    id: str
    name: str
    nodes: list[Node]
    orders: list[Order]
    vehicles: list[Vehicle]
    flow_profile: Literal["standard", "bidirectional"] = "standard"
    spatial_snapshot_id: str | None = None
    spatial_snapshot_at: datetime | None = None
    spatial_verified_nodes: int = 0


class MasterOrderInput(BaseModel):
    node_id: str = Field(min_length=1, max_length=32)
    cargo_name: str = Field(min_length=1, max_length=120)
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str | None = Field(default=None, max_length=32)
    delivery_address: str | None = Field(default=None, max_length=300)
    weight_kg: int = Field(gt=0, le=100000)
    window_start: int = Field(ge=0, le=1439)
    window_end: int = Field(gt=0, le=1440)
    service_minutes: int = Field(default=8, ge=0, le=240)
    cold_chain: bool = False
    priority: Literal["normal", "urgent"] = "normal"
    flow_direction: FlowDirection = "downward"
    cargo_category: CargoCategory = "agricultural"
    origin_node_id: str | None = Field(default=None, min_length=1, max_length=32)
    destination_node_id: str | None = Field(default=None, min_length=1, max_length=32)
    status: Literal["pending", "planned", "completed", "cancelled"] = "pending"

    @model_validator(mode="after")
    def validate_time_window(self) -> "MasterOrderInput":
        if self.window_end <= self.window_start:
            raise ValueError("服务时间窗结束时间必须晚于开始时间")
        return self


class MasterOrderCreate(MasterOrderInput):
    id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")


class MasterOrderView(MasterOrderInput):
    id: str
    node_name: str
    created_at: datetime
    updated_at: datetime


class MasterOrderList(BaseModel):
    items: list[MasterOrderView]
    total: int


OrderRequestStatus = Literal[
    "pending_review",
    "needs_info",
    "rejected",
    "converted",
    "cancelled",
]


class OrderRequestCreate(BaseModel):
    node_id: str = Field(min_length=1, max_length=32)
    cargo_name: str = Field(min_length=1, max_length=120)
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str | None = Field(default=None, max_length=32)
    delivery_address: str | None = Field(default=None, max_length=300)
    weight_kg: int = Field(gt=0, le=100000)
    window_start: int = Field(ge=0, le=1439)
    window_end: int = Field(gt=0, le=1440)
    service_minutes: int = Field(default=8, ge=0, le=240)
    cold_chain: bool = False
    priority: Literal["normal", "urgent"] = "normal"
    flow_direction: FlowDirection = "downward"
    cargo_category: CargoCategory = "agricultural"
    origin_node_id: str | None = Field(default=None, min_length=1, max_length=32)
    destination_node_id: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_time_window(self) -> "OrderRequestCreate":
        if self.window_end <= self.window_start:
            raise ValueError("服务时间窗结束时间必须晚于开始时间")
        return self


class OrderRequestReviewRequest(BaseModel):
    action: Literal["approve", "reject", "needs_info"]
    note: str | None = Field(default=None, max_length=500)


class OrderRequestNodeOption(BaseModel):
    id: str
    name: str
    address: str | None = None
    kind: Literal["depot", "town", "village", "processor"]


class OrderRequestNodeOptionList(BaseModel):
    items: list[OrderRequestNodeOption]


class OrderRequestView(BaseModel):
    id: int
    request_code: str
    requester_username: str
    requester_name: str
    node_id: str
    node_name: str
    cargo_name: str
    customer_name: str
    customer_phone: str | None
    delivery_address: str | None
    weight_kg: int
    window_start: int
    window_end: int
    service_minutes: int
    cold_chain: bool
    priority: Literal["normal", "urgent"]
    flow_direction: FlowDirection
    cargo_category: CargoCategory
    origin_node_id: str | None
    destination_node_id: str | None
    status: OrderRequestStatus
    review_note: str | None
    reviewer_username: str | None
    reviewed_at: datetime | None
    operational_order_id: str | None
    operational_status: str | None
    created_at: datetime
    updated_at: datetime


class OrderRequestList(BaseModel):
    items: list[OrderRequestView]
    total: int


class MasterVehicleInput(BaseModel):
    plate: str = Field(min_length=2, max_length=32)
    capacity_kg: int = Field(gt=0, le=100000)
    cold_chain: bool = False
    vehicle_type: Literal["van", "truck", "refrigerated"] = "van"
    driver_name: str | None = Field(default=None, max_length=120)
    driver_phone: str | None = Field(default=None, max_length=32)
    status: Literal["available", "assigned", "maintenance", "offline"] = "available"
    cost_per_km: float = Field(gt=0, le=1000)
    shift_start: int = Field(ge=0, le=1439)
    shift_end: int = Field(gt=0, le=1440)

    @model_validator(mode="after")
    def validate_shift_window(self) -> "MasterVehicleInput":
        if self.shift_end <= self.shift_start:
            raise ValueError("车辆班次结束时间必须晚于开始时间")
        if self.vehicle_type == "refrigerated" and not self.cold_chain:
            raise ValueError("冷藏车辆必须启用冷链能力")
        return self


class MasterVehicleCreate(MasterVehicleInput):
    id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")


class MasterVehicleView(MasterVehicleInput):
    id: str
    available: bool
    created_at: datetime
    updated_at: datetime


class MasterVehicleList(BaseModel):
    items: list[MasterVehicleView]
    total: int


class MasterNodeInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    kind: Literal["depot", "town", "village", "processor"]
    address: str | None = Field(default=None, max_length=300)
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=32)
    service_radius_km: float = Field(gt=0, le=500)
    is_active: bool = True


class MasterNodeCreate(MasterNodeInput):
    id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")


class MasterNodeView(MasterNodeInput):
    id: str
    wgs84_longitude: float | None = None
    wgs84_latitude: float | None = None
    coordinate_system: Literal["gcj02"] = "gcj02"
    coordinate_source: Literal["seed", "imported", "geocoded", "manual"] = "seed"
    coordinate_status: Literal["unverified", "verified", "needs_review"] = "unverified"
    coordinate_accuracy_m: int | None = None
    calibrated_at: datetime | None = None
    calibrated_by: int | None = None
    spatial_issue: Literal["none", "outside_bounds", "duplicate"] = "none"
    created_at: datetime
    updated_at: datetime


class MasterNodeList(BaseModel):
    items: list[MasterNodeView]
    total: int


class NodeCoordinateUpdate(BaseModel):
    longitude: float = Field(ge=72.004, le=137.8347)
    latitude: float = Field(ge=0.8293, le=55.8271)
    address: str | None = Field(default=None, max_length=300)
    coordinate_source: Literal["geocoded", "manual"] = "manual"
    coordinate_accuracy_m: int | None = Field(default=None, ge=0, le=100_000)
    coordinate_status: Literal["verified", "needs_review"] = "verified"
    note: str | None = Field(default=None, max_length=500)


class NodeCoordinateRevisionView(BaseModel):
    id: int
    node_id: str
    before_longitude: float | None
    before_latitude: float | None
    longitude: float
    latitude: float
    wgs84_longitude: float
    wgs84_latitude: float
    coordinate_source: str
    coordinate_status: str
    coordinate_accuracy_m: int | None
    address: str | None
    note: str | None
    actor_username: str | None
    created_at: datetime


class NodeCoordinateRevisionList(BaseModel):
    items: list[NodeCoordinateRevisionView]


class SpatialQualitySummary(BaseModel):
    total: int
    verified: int
    needs_review: int
    unverified: int
    outside_bounds: int
    duplicate: int
    missing_address: int
    display_coordinate_system: Literal["GCJ-02"] = "GCJ-02"
    storage_coordinate_system: Literal["WGS-84"] = "WGS-84"


class MasterDataSummary(BaseModel):
    order_total: int
    pending_orders: int
    cold_chain_orders: int
    invalid_orders: int
    vehicle_total: int
    available_vehicles: int
    node_total: int
    active_nodes: int


class ReferenceWeightView(BaseModel):
    code: str
    label: str
    weight: float = Field(ge=0, le=1)


class ReferenceDemandPoint(BaseModel):
    town_name: str
    village_count: int = Field(ge=0)
    demand_tons: float = Field(ge=0)
    share_percent: float = Field(ge=0, le=100)


class ReferenceDirectionalDemandPoint(BaseModel):
    town_name: str
    upward_tons: float = Field(ge=0)
    downward_tons: float = Field(ge=0)
    combined_tons: float = Field(ge=0)


class ReferenceCandidateView(BaseModel):
    rank: int = Field(ge=1)
    town_name: str
    score: float = Field(ge=0, le=10)
    level: str
    candidate_type: Literal["core", "remote_safeguard"]
    demand_tons: float | None = Field(default=None, ge=0)
    rationale: str


class ReferenceCoordinateQuality(BaseModel):
    total_nodes: int = Field(ge=0)
    inside_bounds: int = Field(ge=0)
    outside_bounds: int = Field(ge=0)
    duplicate_nodes: int = Field(ge=0)
    flagged_node_ids: list[str] = []
    status: Literal["verified", "needs_review"]
    note: str


class ReferenceFacilityView(BaseModel):
    level: str
    name: str
    count: int = Field(ge=0)
    status: str
    function: str
    coverage_percent: float | None = Field(default=None, ge=0, le=100)


class QidongReferenceSummary(BaseModel):
    dataset_version: str
    source_scope: str
    service_circle_minutes: int = Field(gt=0)
    township_count: int = Field(gt=0)
    village_units: int = Field(gt=0)
    town_logistics_stations: int = Field(ge=0)
    township_ecommerce_stations: int = Field(ge=0)
    field_cold_stores: int = Field(ge=0)
    village_service_stations: int = Field(ge=0)
    co_delivery_stations: int = Field(ge=0)
    county_facility_count: int = Field(ge=0)
    village_coverage_percent: float = Field(ge=0, le=100)
    road_total_km: float = Field(ge=0)
    road_density_km_per_sq_km: float = Field(ge=0)
    demand_unit: str
    reference_demand_tons: float = Field(ge=0)
    bidirectional_dataset_version: str | None = None
    upward_reference_tons: float = Field(default=0, ge=0)
    downward_reference_tons: float = Field(default=0, ge=0)
    upward_monthly_tons: list[float] = []
    downward_monthly_tons: list[float] = []
    directional_demand_summary: list[ReferenceDirectionalDemandPoint] = []
    demo_load_ratio: float = Field(gt=0, le=1)
    demo_order_count: int = Field(ge=0)
    demo_order_weight_kg: int = Field(ge=0)
    demo_mapped_town_count: int = Field(ge=0)
    demand_summary: list[ReferenceDemandPoint]
    ahp_weights: list[ReferenceWeightView]
    candidates: list[ReferenceCandidateView]
    facility_summary: list[ReferenceFacilityView]
    facility_gaps: list[str]
    coordinate_quality: ReferenceCoordinateQuality
    notes: list[str] = []


class DataImportErrorView(BaseModel):
    row: int
    field: str
    message: str


class DataImportBatchView(BaseModel):
    id: int
    batch_code: str
    import_type: str
    filename: str
    status: Literal["validated", "rejected", "committed"]
    total_rows: int
    valid_rows: int
    error_rows: int
    warning_rows: int
    errors: list[DataImportErrorView]
    created_by: str | None
    committed_by: str | None
    created_at: datetime
    committed_at: datetime | None


class DataImportBatchList(BaseModel):
    items: list[DataImportBatchView]
    total: int


class DataQualityRuleUpdate(BaseModel):
    enabled: bool
    severity: Literal["error", "warning"]


class DataQualityRuleView(BaseModel):
    id: int
    rule_code: str
    name: str
    description: str
    entity_type: str
    severity: Literal["error", "warning"]
    enabled: bool
    config: dict[str, Any]
    issue_count: int
    status: Literal["passed", "warning", "blocked", "disabled"]
    detail: str
    updated_at: datetime


class DataQualityReport(BaseModel):
    items: list[DataQualityRuleView]
    blocked_count: int
    warning_count: int
    publish_ready: bool


class MasterDataPublishRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    activate: bool = False


class OptimizeOptions(BaseModel):
    cold_chain_first: bool = True
    backhaul_enabled: bool = True


class OptimizeRequest(BaseModel):
    scenario_id: str | None = None
    profile: Literal["standard-v1", "bidirectional-v2"] | None = None
    solver: Literal["ortools", "pyvrp"] = "ortools"
    time_limit_seconds: int = Field(default=5, ge=1, le=30)
    strategy: Literal["auto", "balanced", "distance", "cost", "fleet"] = "auto"
    ai_assisted: bool = True
    candidate_count: int = Field(default=3, ge=1, le=4)
    options: OptimizeOptions = OptimizeOptions()


class Event(BaseModel):
    type: Literal["vehicle_breakdown", "road_closure", "urgent_order"]
    vehicle_id: str | None = None
    occurred_at_minute: int = Field(default=90, ge=0)
    node_id: str | None = Field(default=None, max_length=32)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    location_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_location_pair(self) -> "Event":
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("事件经度与纬度必须同时提供")
        return self


class ReoptimizeRequest(BaseModel):
    base_run_id: str | None = None
    profile: Literal["standard-v1", "bidirectional-v2"] | None = None
    event: Event
    lock_completed: bool = True
    urgent_orders: list[str] = Field(default_factory=list)
    ai_assisted: bool = True
    candidate_count: int = Field(default=3, ge=1, le=4)


class RouteStop(BaseModel):
    order_id: str | None
    node_id: str
    node_name: str
    longitude: float
    latitude: float
    arrival_minute: int
    load_kg: int
    status: Literal["depot", "planned", "completed"] = "planned"
    action: Literal["depot", "pickup", "delivery"] = "delivery"
    flow_direction: FlowDirection | None = None
    cargo_category: CargoCategory | None = None


class Route(BaseModel):
    vehicle_id: str
    plate: str
    cold_chain: bool
    color: str
    distance_km: float
    duration_minutes: int
    load_kg: int
    stops: list[RouteStop]


class Metrics(BaseModel):
    distance_km: float
    estimated_cost_cny: float
    on_time_rate: float
    empty_distance_rate: float
    vehicles_used: int


class RoutingMatrixInfo(BaseModel):
    requested_provider: str = "haversine"
    source: str = "haversine"
    cache_hit: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    data_version: str | None = None
    coordinate_count: int = 0


class DecisionScoreComponent(BaseModel):
    key: str
    name: str
    score: float
    weight: int
    detail: str


class DecisionScore(BaseModel):
    total: float
    grade: Literal["A", "B", "C", "D"]
    formula_version: str = "dispatch-score-v1"
    components: list[DecisionScoreComponent]


class CandidateSummary(BaseModel):
    strategy: Literal["balanced", "distance", "cost", "fleet"]
    status: Literal["feasible", "infeasible"]
    score: float
    distance_km: float
    estimated_cost_cny: float
    vehicles_used: int
    unassigned_orders: int
    selected: bool = False


class AIOrchestrationInfo(BaseModel):
    requested: bool = False
    used: bool = False
    provider: str | None = None
    model_name: str | None = None
    stages: list[str] = Field(default_factory=list)
    recommended_strategy: str | None = None
    selection_reason: str | None = None
    fallback_reason: str | None = None
    candidate_count: int = 1


class EventLocationView(BaseModel):
    node_id: str | None = None
    location_name: str
    longitude: float
    latitude: float
    coordinate_system: Literal["gcj02"] = "gcj02"
    source: Literal["request", "scenario_node", "route_stop"]


class OptimizeResponse(BaseModel):
    run_id: str
    status: Literal["optimal", "feasible", "infeasible"]
    solver: str
    solve_time_ms: int
    routes: list[Route]
    unassigned_order_ids: list[str]
    metrics: Metrics
    baseline_metrics: Metrics
    explanations: list[str]
    routing: RoutingMatrixInfo = Field(default_factory=RoutingMatrixInfo)
    event_location: EventLocationView | None = None
    decision_score: DecisionScore | None = None
    candidate_summaries: list[CandidateSummary] = Field(default_factory=list)
    ai_orchestration: AIOrchestrationInfo = Field(default_factory=AIOrchestrationInfo)


class ScenarioSpatialStatus(BaseModel):
    scenario_id: str
    snapshot_id: str | None
    snapshot_at: datetime | None
    snapshot_verified_nodes: int
    scenario_node_count: int
    current_verified_nodes: int
    aligned: bool
    changed_node_ids: list[str]
    missing_node_ids: list[str]
    unverified_node_ids: list[str]
    message: str


class RoutingStatus(BaseModel):
    requested_provider: str
    osrm_base_url: str | None
    fallback_enabled: bool = True
    cache_entries: int
    cache_capacity: int


class CurrentWeather(BaseModel):
    location: str
    temperature_c: float
    apparent_temperature_c: float
    humidity_percent: int
    weather_code: int
    weather_label: str
    wind_speed_kmh: float
    observed_at: str
    fetched_at: datetime
    source: str
    cached: bool = False
    stale: bool = False


class ForecastPoint(BaseModel):
    date: str
    actual_tons: float | None = None
    forecast_tons: float | None = None
    lower_tons: float | None = None
    upper_tons: float | None = None


class TownshipDemand(BaseModel):
    node_id: str
    node_name: str
    demand_tons: float
    share: float


class DemandForecast(BaseModel):
    scenario_id: str
    generated_at: datetime
    horizon_days: int
    method: str
    history_basis: str
    model_family: str
    training_samples: int = 0
    validation_mae_tons: float | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    feature_names: list[str] = Field(default_factory=list)
    points: list[ForecastPoint]
    township_ranking: list[TownshipDemand]
    today_forecast_tons: float
    peak_forecast_tons: float
    peak_date: str
    cold_chain_tons: float
    recommended_vehicles: int
    risk_level: Literal["low", "medium", "high"]
    notes: list[str]


class DispatchPlanCreate(BaseModel):
    run_id: str = Field(min_length=6, max_length=32)


class DispatchReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AssignmentActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class DriverNavigationStop(BaseModel):
    sequence: int
    order_id: str | None
    node_id: str
    node_name: str
    longitude: float
    latitude: float
    arrival_minute: int
    load_kg: int
    status: Literal["planned", "completed"] = "planned"
    action: Literal["pickup", "delivery"] = "delivery"
    flow_direction: FlowDirection | None = None
    cargo_category: CargoCategory | None = None


class DriverAssignmentView(BaseModel):
    id: int
    plan_id: int
    route_index: int
    vehicle_id: str
    plate: str
    status: str
    driver_username: str | None
    distance_km: float
    duration_minutes: int
    load_kg: int
    stop_count: int
    next_stop_name: str | None
    next_stop: DriverNavigationStop | None
    navigation_stops: list[DriverNavigationStop]
    accepted_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    completion_note: str | None
    updated_at: datetime


class DispatchPlanView(BaseModel):
    id: int
    run_id: str
    scenario_id: str
    status: str
    submitted_by: str | None
    reviewed_by: str | None
    rejection_reason: str | None
    route_count: int
    distance_km: float
    estimated_cost_cny: float
    submitted_at: datetime
    reviewed_at: datetime | None
    dispatched_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    assignments: list[DriverAssignmentView]


class DispatchPlanList(BaseModel):
    items: list[DispatchPlanView]


class DriverAssignmentList(BaseModel):
    items: list[DriverAssignmentView]


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{2,63}$")
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    agreement_accepted: Literal[True]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    display_name: str
    expires_in: int


class CurrentUserView(BaseModel):
    username: str
    display_name: str
    role: str
    last_login_at: datetime | None


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{2,63}$")
    display_name: str = Field(min_length=2, max_length=100)
    role: Literal["admin", "dispatcher", "driver", "viewer", "user"]
    password: str = Field(min_length=12, max_length=128)
    is_active: bool = True


class UserUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    role: Literal["admin", "dispatcher", "driver", "viewer", "user"]
    is_active: bool
    unlock: bool = False


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class UserView(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    is_locked: bool
    locked_until: datetime | None
    failed_login_count: int
    last_login_at: datetime | None
    last_login_ip: str | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserList(BaseModel):
    items: list[UserView]
    total: int
    active_count: int
    admin_count: int
    locked_count: int


class AuditLogView(BaseModel):
    id: int
    category: str
    action: str
    outcome: str
    resource_type: str | None
    resource_id: str | None
    actor_username: str | None
    ip_address: str | None
    user_agent: str | None
    detail: dict[str, Any]
    created_at: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogView]
    total: int


class RunSummary(BaseModel):
    run_id: str
    scenario_id: str
    status: str
    solver: str
    solve_time_ms: int
    distance_km: float
    estimated_cost_cny: float
    vehicles_used: int
    event_type: str | None
    event_vehicle_id: str | None
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummary]
    next_cursor: datetime | None


class AsyncJobResponse(BaseModel):
    task_id: str
    status: str


class AsyncJobStatus(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class AIConfigUpsert(BaseModel):
    name: str = Field(default="AI 服务连接", min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    provider: str = Field(default="openai-compatible", min_length=2, max_length=48)
    base_url: str = Field(min_length=8, max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=1000)
    enabled: bool = True
    temperature: float = Field(default=0.2, ge=0, le=2)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("接口地址必须使用 http:// 或 https://")
        return normalized

    @model_validator(mode="after")
    def validate_provider_endpoint_match(self) -> "AIConfigUpsert":
        host = (urlparse(self.base_url).hostname or "").lower()
        known_hosts = {
            "openai": "api.openai.com",
            "deepseek": "api.deepseek.com",
        }
        conflicting_provider = next(
            (provider for provider, provider_host in known_hosts.items() if host == provider_host),
            None,
        )
        if self.provider in known_hosts and conflicting_provider and conflicting_provider != self.provider:
            expected = known_hosts[self.provider]
            raise ValueError(
                f"服务类型与接口地址不匹配：{self.provider} 应使用 {expected}，"
                f"当前地址属于 {conflicting_provider}"
            )
        if self.provider == "qwen" and host in known_hosts.values():
            raise ValueError("服务类型与接口地址不匹配：通义千问应使用阿里云百炼兼容接口")
        return self


class AIConfigView(BaseModel):
    id: int
    name: str
    description: str | None
    provider: str
    base_url: str
    model_name: str
    enabled: bool
    temperature: float
    has_api_key: bool
    api_key_masked: str
    last_test_status: str
    last_test_message: str | None
    last_tested_at: datetime | None
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime


class AIConfigList(BaseModel):
    items: list[AIConfigView]


class AIConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int


class MapConfigUpsert(BaseModel):
    name: str = Field(default="高德地图服务", min_length=2, max_length=120)
    provider: str = Field(default="amap", pattern="^amap$")
    web_key: str | None = Field(default=None, max_length=500)
    security_code: str | None = Field(default=None, max_length=500)
    map_style: str = Field(default="whitesmoke", pattern="^(normal|whitesmoke|fresh|light)$")
    enabled: bool = True


class MapConfigView(BaseModel):
    id: int
    name: str
    provider: str
    map_style: str
    enabled: bool
    has_web_key: bool
    web_key_masked: str
    has_security_code: bool
    security_code_masked: str
    last_test_status: str
    last_test_message: str | None
    last_tested_at: datetime | None
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime


class MapConfigList(BaseModel):
    items: list[MapConfigView]


class MapRuntimeConfig(BaseModel):
    provider: str
    mode: str
    web_key: str | None = None
    map_style: str = "whitesmoke"
    service_host: str | None = None


class AIExplanationResponse(BaseModel):
    run_id: str
    provider: str
    model_name: str
    explanation: str


class ScenarioVersionView(BaseModel):
    id: int
    scenario_code: str
    version_no: int
    version_key: str
    name: str
    county_name: str
    status: str
    source_type: str
    source_filename: str | None
    node_count: int
    order_count: int
    vehicle_count: int
    validation_summary: dict[str, Any]
    fingerprint: str | None = None
    release_note: str | None = None
    created_by: str | None = None
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    activated_at: datetime | None


class ScenarioGovernanceSummary(BaseModel):
    total: int = 0
    active: int = 0
    pending_review: int = 0
    draft: int = 0
    rejected: int = 0
    archived: int = 0


class ScenarioVersionList(BaseModel):
    items: list[ScenarioVersionView]
    total: int = 0
    summary: ScenarioGovernanceSummary = ScenarioGovernanceSummary()


class ScenarioTransitionView(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    note: str | None
    actor: str | None
    created_at: datetime


class ScenarioVersionDetail(ScenarioVersionView):
    transitions: list[ScenarioTransitionView] = []


class ScenarioActionRequest(BaseModel):
    note: str = Field(min_length=2, max_length=500)


class ScenarioDiffItem(BaseModel):
    object_id: str
    change_type: Literal["added", "removed", "changed"]
    description: str


class ScenarioDiffGroup(BaseModel):
    added: int
    removed: int
    changed: int
    details: list[ScenarioDiffItem]


class ScenarioDiffMetrics(BaseModel):
    node_count: int
    order_count: int
    vehicle_count: int
    total_weight_kg: int
    cold_chain_capacity_kg: int


class ScenarioCompareResponse(BaseModel):
    base: ScenarioVersionView
    target: ScenarioVersionView
    base_metrics: ScenarioDiffMetrics
    target_metrics: ScenarioDiffMetrics
    deltas: ScenarioDiffMetrics
    nodes: ScenarioDiffGroup
    orders: ScenarioDiffGroup
    vehicles: ScenarioDiffGroup


class ScenarioImportResponse(BaseModel):
    scenario: ScenarioVersionView
    warnings: list[str] = []


class OperationsReadinessDimension(BaseModel):
    key: str
    name: str
    score: int
    ready: bool
    checks: list[str]
    gaps: list[str]


class OperationsWorkflowStep(BaseModel):
    step: int
    title: str
    duration_seconds: int
    description: str
    route: str
    ready: bool


class OperationsKPI(BaseModel):
    key: str
    name: str
    value: float
    unit: str
    source_id: str | None = None


class OperationsComparisonRow(BaseModel):
    key: str
    name: str
    baseline: float
    optimized: float
    unit: str
    improvement: float


class OperationsEvidenceItem(BaseModel):
    requirement: str
    capability: str
    evidence_id: str | None
    status: Literal["verified", "attention"]
    route: str


class OperationsReference(BaseModel):
    label: str
    value: str | None
    detail: str
    route: str
    ready: bool


class OperationsReadinessResponse(BaseModel):
    generated_at: datetime
    overall_score: int
    dimensions: list[OperationsReadinessDimension]
    script: list[OperationsWorkflowStep]
    kpis: list[OperationsKPI]
    comparison: list[OperationsComparisonRow]
    evidence: list[OperationsEvidenceItem]
    references: list[OperationsReference]
    tips: list[str]
    total_duration_seconds: int


class MasterDataPublishResponse(BaseModel):
    scenario: ScenarioVersionView
    warnings: list[str] = []


class ExperimentCreate(BaseModel):
    name: str = Field(default="县域物流三压力算法对照实验", min_length=2, max_length=120)
    scenario_id: str | None = Field(default=None, max_length=96)
    time_limit_seconds: int = Field(default=1, ge=1, le=10)


class ExperimentCaseResult(BaseModel):
    case_key: Literal["standard", "peak", "cold_chain"]
    case_name: str
    description: str
    demand_multiplier: float
    demand_tons: float
    status: Literal["optimal", "feasible", "infeasible"]
    solve_time_ms: int
    baseline_distance_km: float
    optimized_distance_km: float
    distance_reduction_pct: float
    baseline_cost_cny: float
    optimized_cost_cny: float
    cost_saving_cny: float
    cost_reduction_pct: float
    vehicles_used: int
    service_rate: float
    unassigned_orders: int
    routing_source: str


class ExperimentSummary(BaseModel):
    average_distance_reduction_pct: float
    total_cost_saving_cny: float
    average_cost_reduction_pct: float
    average_service_rate: float
    average_vehicles_used: float
    total_solve_time_ms: int
    completed_cases: int


class ExperimentView(BaseModel):
    id: int
    experiment_code: str
    name: str
    scenario_key: str
    scenario_fingerprint: str
    status: Literal["running", "completed", "failed"]
    solver: str
    baseline: str
    time_limit_seconds: int
    case_count: int
    summary: ExperimentSummary | None
    results: list[ExperimentCaseResult]
    error_message: str | None
    created_by: str | None
    created_at: datetime
    completed_at: datetime | None


class ExperimentList(BaseModel):
    items: list[ExperimentView]
