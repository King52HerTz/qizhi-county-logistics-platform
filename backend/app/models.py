from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="dispatcher")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "role in ('admin','dispatcher','driver','viewer','user')",
            name="users_role_check",
        ),
        Index("users_role_active_idx", "role", "is_active"),
    )


class NodeRecord(Base):
    __tablename__ = "logistics_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    wgs84_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    wgs84_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(16), nullable=False, default="gcj02")
    coordinate_source: Mapped[str] = mapped_column(String(24), nullable=False, default="seed")
    coordinate_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unverified"
    )
    coordinate_accuracy_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calibrated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    service_radius_km: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("15.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        CheckConstraint("kind in ('depot','town','village','processor')", name="nodes_kind_check"),
        CheckConstraint("service_radius_km > 0", name="nodes_service_radius_positive"),
        CheckConstraint("coordinate_system in ('gcj02')", name="nodes_coordinate_system_check"),
        CheckConstraint(
            "coordinate_source in ('seed','imported','geocoded','manual')",
            name="nodes_coordinate_source_check",
        ),
        CheckConstraint(
            "coordinate_status in ('unverified','verified','needs_review')",
            name="nodes_coordinate_status_check",
        ),
        CheckConstraint(
            "coordinate_accuracy_m is null or coordinate_accuracy_m >= 0",
            name="nodes_coordinate_accuracy_check",
        ),
        Index("nodes_active_kind_idx", "is_active", "kind"),
        Index("nodes_coordinate_status_idx", "coordinate_status", "updated_at"),
        Index("nodes_calibrated_by_idx", "calibrated_by"),
    )


class NodeCoordinateRevisionRecord(Base):
    __tablename__ = "node_coordinate_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("logistics_nodes.id", ondelete="CASCADE"), nullable=False
    )
    before_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    before_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    wgs84_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    wgs84_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    coordinate_source: Mapped[str] = mapped_column(String(24), nullable=False)
    coordinate_status: Mapped[str] = mapped_column(String(20), nullable=False)
    coordinate_accuracy_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        CheckConstraint(
            "coordinate_source in ('seed','imported','geocoded','manual')",
            name="node_coordinate_revisions_source_check",
        ),
        CheckConstraint(
            "coordinate_status in ('unverified','verified','needs_review')",
            name="node_coordinate_revisions_status_check",
        ),
        CheckConstraint(
            "coordinate_accuracy_m is null or coordinate_accuracy_m >= 0",
            name="node_coordinate_revisions_accuracy_check",
        ),
        Index("node_coordinate_revisions_node_created_idx", "node_id", "created_at"),
        Index("node_coordinate_revisions_actor_idx", "actor_id"),
    )


class VehicleRecord(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plate: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    capacity_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    cold_chain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    vehicle_type: Mapped[str] = mapped_column(String(24), nullable=False, default="van")
    driver_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    cost_per_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    shift_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shift_end: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        CheckConstraint("capacity_kg > 0", name="vehicles_capacity_positive"),
        CheckConstraint("shift_end > shift_start", name="vehicles_shift_check"),
        CheckConstraint(
            "vehicle_type in ('van','truck','refrigerated')",
            name="vehicles_type_check",
        ),
        CheckConstraint(
            "status in ('available','assigned','maintenance','offline')",
            name="vehicles_status_check",
        ),
        Index("vehicles_status_cold_idx", "status", "cold_chain"),
    )


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("logistics_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    weight_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[int] = mapped_column(Integer, nullable=False)
    window_end: Mapped[int] = mapped_column(Integer, nullable=False)
    service_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    cold_chain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    flow_direction: Mapped[str] = mapped_column(
        String(16), nullable=False, default="downward"
    )
    cargo_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="agricultural"
    )
    origin_node_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_node_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    cargo_name: Mapped[str] = mapped_column(Text, nullable=False, default="农产品")
    customer_name: Mapped[str] = mapped_column(Text, nullable=False, default="未登记客户")
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    node: Mapped[NodeRecord] = relationship()

    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="orders_weight_positive"),
        CheckConstraint("window_end > window_start", name="orders_window_check"),
        CheckConstraint("priority in ('normal','urgent')", name="orders_priority_check"),
        CheckConstraint(
            "flow_direction in ('upward','downward')",
            name="orders_flow_direction_check",
        ),
        CheckConstraint(
            "cargo_category in ('agricultural','industrial')",
            name="orders_cargo_category_check",
        ),
        CheckConstraint("status in ('pending','planned','completed','cancelled')", name="orders_status_check"),
        Index("orders_node_id_idx", "node_id"),
        Index("orders_status_created_idx", "status", "created_at"),
        Index("orders_priority_cold_updated_idx", "priority", "cold_chain", "updated_at"),
        Index("orders_pending_time_idx", "window_start", postgresql_where=(status == "pending")),
    )


class OrderRequestRecord(Base):
    """A customer-facing order request before it becomes an operational order."""

    __tablename__ = "order_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    requester_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("logistics_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    cargo_name: Mapped[str] = mapped_column(Text, nullable=False)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[int] = mapped_column(Integer, nullable=False)
    window_end: Mapped[int] = mapped_column(Integer, nullable=False)
    service_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    cold_chain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    flow_direction: Mapped[str] = mapped_column(
        String(16), nullable=False, default="downward"
    )
    cargo_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="agricultural"
    )
    origin_node_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_node_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operational_order_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    requester: Mapped[UserRecord] = relationship(foreign_keys=[requester_id])
    reviewer: Mapped[UserRecord | None] = relationship(foreign_keys=[reviewed_by])
    node: Mapped[NodeRecord] = relationship()
    operational_order: Mapped[OrderRecord | None] = relationship(
        foreign_keys=[operational_order_id]
    )

    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="order_requests_weight_positive"),
        CheckConstraint("window_end > window_start", name="order_requests_window_check"),
        CheckConstraint("service_minutes >= 0", name="order_requests_service_nonnegative"),
        CheckConstraint("priority in ('normal','urgent')", name="order_requests_priority_check"),
        CheckConstraint(
            "flow_direction in ('upward','downward')",
            name="order_requests_flow_direction_check",
        ),
        CheckConstraint(
            "cargo_category in ('agricultural','industrial')",
            name="order_requests_cargo_category_check",
        ),
        CheckConstraint(
            "status in ('pending_review','needs_info','rejected','converted','cancelled')",
            name="order_requests_status_check",
        ),
        Index("order_requests_requester_created_idx", "requester_id", "created_at"),
        Index("order_requests_status_created_idx", "status", "created_at"),
        Index("order_requests_node_id_idx", "node_id"),
        Index("order_requests_operational_order_idx", "operational_order_id"),
    )


class DataImportBatchRecord(Base):
    __tablename__ = "data_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    import_type: Mapped[str] = mapped_column(String(24), nullable=False, default="orders")
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="validated")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    committed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[UserRecord | None] = relationship(foreign_keys=[created_by])
    committer: Mapped[UserRecord | None] = relationship(foreign_keys=[committed_by])

    __table_args__ = (
        CheckConstraint("import_type in ('orders')", name="data_import_type_check"),
        CheckConstraint(
            "status in ('validated','rejected','committed')",
            name="data_import_status_check",
        ),
        CheckConstraint(
            "total_rows >= 0 and valid_rows >= 0 and error_rows >= 0 and warning_rows >= 0",
            name="data_import_counts_nonnegative",
        ),
        Index("data_import_creator_id_idx", "created_by"),
        Index("data_import_committer_id_idx", "committed_by"),
        Index("data_import_status_created_idx", "status", "created_at"),
    )


class DataQualityRuleRecord(Base):
    __tablename__ = "data_quality_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    updater: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "entity_type in ('order','vehicle','node','scenario')",
            name="data_quality_entity_check",
        ),
        CheckConstraint(
            "severity in ('error','warning')",
            name="data_quality_severity_check",
        ),
        Index("data_quality_updated_by_idx", "updated_by"),
        Index("data_quality_enabled_entity_idx", "enabled", "entity_type"),
    )


class OptimizationRunRecord(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    solver: Mapped[str] = mapped_column(String(40), nullable=False)
    solve_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 1), nullable=False)
    estimated_cost_cny: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vehicles_used: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_vehicle_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    creator: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        CheckConstraint("status in ('optimal','feasible','infeasible')", name="runs_status_check"),
        Index("runs_creator_id_idx", "created_by"),
        Index("runs_scenario_created_idx", "scenario_id", "created_at"),
        Index("runs_status_created_idx", "status", "created_at"),
        Index("runs_created_id_idx", "created_at", "id"),
    )


class EventRecord(Base):
    __tablename__ = "dispatch_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    vehicle_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    optimization_run_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("optimization_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    run: Mapped[OptimizationRunRecord | None] = relationship()

    __table_args__ = (
        Index("events_run_id_idx", "optimization_run_id"),
        Index("events_type_created_idx", "event_type", "created_at"),
    )


class AIProviderConfigRecord(Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="AI 服务连接")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(48), nullable=False, default="openai-compatible")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.20"))
    last_test_status: Mapped[str] = mapped_column(String(20), nullable=False, default="untested")
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped[UserRecord | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[UserRecord | None] = relationship(foreign_keys=[updated_by])

    __table_args__ = (
        CheckConstraint("temperature >= 0 and temperature <= 2", name="ai_config_temperature_check"),
        CheckConstraint(
            "last_test_status in ('untested','success','failed')",
            name="ai_config_test_status_check",
        ),
        Index("ai_config_enabled_idx", "updated_at", postgresql_where=(enabled.is_(True))),
        Index("ai_config_creator_id_idx", "created_by"),
        Index("ai_config_updated_by_idx", "updated_by"),
        Index(
            "ai_config_single_enabled_idx",
            "enabled",
            unique=True,
            postgresql_where=(enabled.is_(True)),
            sqlite_where=(enabled.is_(True)),
        ),
    )


class MapProviderConfigRecord(Base):
    __tablename__ = "map_provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="高德地图服务")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="amap")
    encrypted_web_key: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_security_code: Mapped[str] = mapped_column(Text, nullable=False)
    map_style: Mapped[str] = mapped_column(String(32), nullable=False, default="whitesmoke")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str] = mapped_column(String(20), nullable=False, default="untested")
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped[UserRecord | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[UserRecord | None] = relationship(foreign_keys=[updated_by])

    __table_args__ = (
        CheckConstraint("provider in ('amap')", name="map_config_provider_check"),
        CheckConstraint(
            "map_style in ('normal','whitesmoke','fresh','light')",
            name="map_config_style_check",
        ),
        CheckConstraint(
            "last_test_status in ('untested','success','failed')",
            name="map_config_test_status_check",
        ),
        Index("map_config_creator_id_idx", "created_by"),
        Index("map_config_updated_by_idx", "updated_by"),
        Index(
            "map_config_single_enabled_idx",
            "enabled",
            unique=True,
            postgresql_where=(enabled.is_(True)),
            sqlite_where=(enabled.is_(True)),
        ),
    )


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    resource_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    actor: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "outcome in ('success','failed','blocked')",
            name="audit_logs_outcome_check",
        ),
        Index("audit_logs_actor_created_idx", "actor_id", "created_at"),
        Index("audit_logs_category_created_idx", "category", "created_at"),
        Index("audit_logs_resource_idx", "resource_type", "resource_id", "created_at"),
    )


class ScenarioVersionRecord(Base):
    __tablename__ = "scenario_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_key: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    county_name: Mapped[str] = mapped_column(Text, nullable=False, default="祁东县")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="excel")
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[UserRecord | None] = relationship(foreign_keys=[created_by])
    submitter: Mapped[UserRecord | None] = relationship(foreign_keys=[submitted_by])
    reviewer: Mapped[UserRecord | None] = relationship(foreign_keys=[reviewed_by])

    __table_args__ = (
        UniqueConstraint("scenario_code", "version_no", name="scenario_versions_code_version_key"),
        CheckConstraint("version_no > 0", name="scenario_versions_version_positive"),
        CheckConstraint(
            "status in ('draft','pending_review','rejected','active','archived')",
            name="scenario_versions_status_check",
        ),
        CheckConstraint(
            "source_type in ('demo','excel')",
            name="scenario_versions_source_type_check",
        ),
        CheckConstraint(
            "node_count > 0 and order_count > 0 and vehicle_count > 0",
            name="scenario_versions_counts_positive",
        ),
        Index("scenario_versions_creator_id_idx", "created_by"),
        Index("scenario_versions_submitted_by_idx", "submitted_by"),
        Index("scenario_versions_reviewed_by_idx", "reviewed_by"),
        Index("scenario_versions_created_idx", "created_at", "id"),
        Index("scenario_versions_status_created_idx", "status", "created_at"),
        Index(
            "scenario_versions_active_idx",
            "status",
            unique=True,
            postgresql_where=(status == "active"),
            sqlite_where=(status == "active"),
        ),
    )


class ScenarioTransitionRecord(Base):
    __tablename__ = "scenario_version_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scenario_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    scenario_version: Mapped[ScenarioVersionRecord] = relationship()
    actor: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "from_status is null or from_status in "
            "('draft','pending_review','rejected','active','archived')",
            name="scenario_transition_from_status_check",
        ),
        CheckConstraint(
            "to_status in ('draft','pending_review','rejected','active','archived')",
            name="scenario_transition_to_status_check",
        ),
        Index("scenario_transition_version_created_idx", "scenario_version_id", "created_at"),
        Index("scenario_transition_actor_id_idx", "actor_id"),
    )


class AlgorithmExperimentRecord(Base):
    __tablename__ = "algorithm_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scenario_versions.id", ondelete="SET NULL"), nullable=True
    )
    scenario_key: Mapped[str] = mapped_column(String(96), nullable=False)
    scenario_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    solver: Mapped[str] = mapped_column(String(40), nullable=False, default="ortools-routing")
    baseline: Mapped[str] = mapped_column(
        String(48), nullable=False, default="round-robin-heuristic"
    )
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scenario_version: Mapped[ScenarioVersionRecord | None] = relationship()
    creator: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status in ('running','completed','failed')",
            name="algorithm_experiments_status_check",
        ),
        CheckConstraint(
            "time_limit_seconds >= 1 and time_limit_seconds <= 10",
            name="algorithm_experiments_time_limit_check",
        ),
        CheckConstraint("case_count > 0", name="algorithm_experiments_case_count_check"),
        Index("algorithm_experiments_scenario_version_id_idx", "scenario_version_id"),
        Index("algorithm_experiments_created_by_idx", "created_by"),
        Index(
            "algorithm_experiments_status_created_idx",
            "status",
            "created_at",
        ),
        Index(
            "algorithm_experiments_scenario_created_idx",
            "scenario_key",
            "created_at",
        ),
    )


class DispatchPlanRecord(Base):
    __tablename__ = "dispatch_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("optimization_runs.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_approval")
    submitted_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    run: Mapped[OptimizationRunRecord] = relationship()
    assignments: Mapped[list["DriverAssignmentRecord"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="DriverAssignmentRecord.route_index",
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('pending_approval','approved','rejected','dispatched','accepted','executing','completed')",
            name="dispatch_plans_status_check",
        ),
        Index("dispatch_plans_run_id_idx", "run_id"),
        Index("dispatch_plans_submitted_by_idx", "submitted_by"),
        Index("dispatch_plans_reviewed_by_idx", "reviewed_by"),
        Index("dispatch_plans_status_updated_idx", "status", "updated_at"),
        Index(
            "dispatch_plans_active_idx",
            "updated_at",
            postgresql_where=(status.in_(("approved", "dispatched", "accepted", "executing"))),
            sqlite_where=(status.in_(("approved", "dispatched", "accepted", "executing"))),
        ),
    )


class DriverAssignmentRecord(Base):
    __tablename__ = "driver_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatch_plans.id", ondelete="CASCADE"), nullable=False
    )
    route_index: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(32), nullable=False)
    plate: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_driver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    route_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    plan: Mapped[DispatchPlanRecord] = relationship(back_populates="assignments")
    driver: Mapped[UserRecord | None] = relationship()

    __table_args__ = (
        UniqueConstraint("plan_id", "route_index", name="driver_assignments_plan_route_key"),
        CheckConstraint("route_index >= 0", name="driver_assignments_route_index_check"),
        CheckConstraint(
            "status in ('pending','accepted','executing','completed')",
            name="driver_assignments_status_check",
        ),
        Index("driver_assignments_plan_id_idx", "plan_id"),
        Index("driver_assignments_driver_id_idx", "assigned_driver_id"),
        Index("driver_assignments_driver_status_idx", "assigned_driver_id", "status"),
    )


class DispatchTransitionRecord(Base):
    __tablename__ = "dispatch_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatch_plans.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("driver_assignments.id", ondelete="CASCADE"), nullable=True
    )
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("dispatch_transitions_plan_created_idx", "plan_id", "created_at"),
        Index("dispatch_transitions_assignment_id_idx", "assignment_id"),
        Index("dispatch_transitions_actor_id_idx", "actor_id"),
    )
