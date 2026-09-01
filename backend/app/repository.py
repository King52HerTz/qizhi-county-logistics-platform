from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.bidirectional_scenario import BIDIRECTIONAL_SCENARIO_ID, get_bidirectional_scenario
from app.data.qidong_reference import REFERENCE_ORDER_REQUESTS, reference_order_profile
from app.data.scenario import get_scenario
from app.models import (
    EventRecord,
    NodeRecord,
    OptimizationRunRecord,
    OrderRecord,
    OrderRequestRecord,
    ScenarioVersionRecord,
    ScenarioTransitionRecord,
    UserRecord,
    VehicleRecord,
)
from app.scenario_governance import record_transition, scenario_fingerprint
from app.schemas import EventLocationView, OptimizeResponse, Scenario, ScenarioSpatialStatus
from app.security import hash_password


def seed_demo_data(session: Session) -> None:
    scenario = get_scenario()
    if session.scalar(select(ScenarioVersionRecord).limit(1)) is None:
        session.add(
            ScenarioVersionRecord(
                scenario_code="qidong-demo",
                version_no=1,
                version_key=scenario.id,
                name=scenario.name,
                county_name="祁东县",
                status="active",
                source_type="demo",
                payload=scenario.model_dump(mode="json"),
                validation_summary={"warnings": [], "validated": True},
                node_count=len(scenario.nodes),
                order_count=len(scenario.orders),
                vehicle_count=len(scenario.vehicles),
                activated_at=datetime.now(timezone.utc),
            )
        )
    # Existing databases can contain an older scenario's depot, so checking
    # only the first node would skip newly added route nodes and violate the
    # orders -> logistics_nodes foreign key. Add only missing master nodes and
    # preserve coordinates already maintained by the operator.
    for node in scenario.nodes:
        if session.get(NodeRecord, node.id) is None:
            session.add(
                NodeRecord(
                    id=node.id,
                    name=node.name,
                    longitude=node.longitude,
                    latitude=node.latitude,
                    coordinate_source="seed",
                    coordinate_status="verified",
                    coordinate_accuracy_m=500,
                    calibrated_at=scenario.spatial_snapshot_at,
                    kind=node.kind,
                )
            )
    session.flush()
    for vehicle in scenario.vehicles:
        if session.get(VehicleRecord, vehicle.id) is None:
            session.add(
                VehicleRecord(
                    id=vehicle.id,
                    plate=vehicle.plate,
                    capacity_kg=vehicle.capacity_kg,
                    cold_chain=vehicle.cold_chain,
                    available=vehicle.available,
                    cost_per_km=vehicle.cost_per_km,
                    shift_start=vehicle.shift_start,
                    shift_end=vehicle.shift_end,
                )
            )
    for order in scenario.orders:
        profile = reference_order_profile(order.id) or {}
        record = session.get(OrderRecord, order.id)
        if record is None:
            record = OrderRecord(
                id=order.id,
                node_id=order.node_id,
                weight_kg=order.weight_kg,
                window_start=order.window_start,
                window_end=order.window_end,
                service_minutes=order.service_minutes,
                cold_chain=order.cold_chain,
                priority=order.priority,
                status="completed" if order.completed else "pending",
                cargo_name=profile.get("cargo_name", "农产品"),
                customer_name=profile.get("customer_name", "未登记客户"),
                customer_phone=profile.get("customer_phone"),
                delivery_address=profile.get("delivery_address"),
            )
            session.add(record)
        elif profile:
            if record.cargo_name == "农产品":
                record.cargo_name = profile["cargo_name"]
            if record.customer_name == "未登记客户":
                record.customer_name = profile["customer_name"]
            if not record.customer_phone:
                record.customer_phone = profile["customer_phone"]
            if not record.delivery_address:
                record.delivery_address = profile["delivery_address"]
    settings = get_settings()
    if session.scalar(select(UserRecord).where(UserRecord.username == settings.admin_username)) is None:
        session.add(
            UserRecord(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
    if session.scalar(select(UserRecord).where(UserRecord.username == settings.driver_username)) is None:
        session.add(
            UserRecord(
                username=settings.driver_username,
                password_hash=hash_password(settings.driver_password),
                role="driver",
            )
        )
    session.flush()
    seed_demo_order_requests(session)
    for version in session.scalars(
        select(ScenarioVersionRecord).where(ScenarioVersionRecord.fingerprint.is_(None))
    ):
        version.fingerprint = scenario_fingerprint(version.payload)
        has_transition = session.scalar(
            select(ScenarioTransitionRecord.id)
            .where(ScenarioTransitionRecord.scenario_version_id == version.id)
            .limit(1)
        )
        if has_transition is None:
            record_transition(
                session,
                version,
                from_status=None,
                to_status=version.status,
                note="历史版本初始化",
                actor_id=version.created_by,
            )
    session.commit()


def seed_demo_order_requests(session: Session) -> None:
    """Add stable pending applications for the customer approval walkthrough."""

    requester = session.scalar(
        select(UserRecord).where(
            UserRecord.username == "customer_demo",
            UserRecord.role == "user",
            UserRecord.is_active.is_(True),
        )
    )
    if requester is None:
        requester = session.scalar(
            select(UserRecord)
            .where(UserRecord.role == "user", UserRecord.is_active.is_(True))
            .order_by(UserRecord.id)
        )
    if requester is None:
        return

    for item in REFERENCE_ORDER_REQUESTS:
        request_code = str(item["request_code"])
        if session.scalar(
            select(OrderRequestRecord.id).where(
                OrderRequestRecord.request_code == request_code
            )
        ):
            continue
        session.add(
            OrderRequestRecord(
                request_code=request_code,
                requester_id=requester.id,
                node_id=str(item["node_id"]),
                cargo_name=str(item["cargo_name"]),
                customer_name=str(item["customer_name"]),
                customer_phone=str(item["customer_phone"]),
                delivery_address=str(item["delivery_address"]),
                weight_kg=int(item["weight_kg"]),
                window_start=int(item["window_start"]),
                window_end=int(item["window_end"]),
                service_minutes=int(item["service_minutes"]),
                cold_chain=bool(item["cold_chain"]),
                priority=str(item["priority"]),
                status="pending_review",
            )
        )
    session.flush()


def load_scenario(session: Session, version_key: str | None = None) -> Scenario:
    if version_key == BIDIRECTIONAL_SCENARIO_ID:
        return get_bidirectional_scenario()
    statement = select(ScenarioVersionRecord)
    if version_key:
        statement = statement.where(ScenarioVersionRecord.version_key == version_key)
    else:
        statement = statement.where(ScenarioVersionRecord.status == "active")
    record = session.scalar(statement.order_by(ScenarioVersionRecord.created_at.desc()))
    if record is None:
        if version_key:
            raise LookupError(f"场景版本不存在：{version_key}")
        return get_scenario()
    return Scenario.model_validate(record.payload)


def get_scenario_spatial_status(
    session: Session,
    scenario: Scenario,
) -> ScenarioSpatialStatus:
    master_nodes = {
        record.id: record
        for record in session.scalars(
            select(NodeRecord).where(NodeRecord.is_active.is_(True))
        )
    }
    changed_node_ids: list[str] = []
    missing_node_ids: list[str] = []
    for node in scenario.nodes:
        current = master_nodes.get(node.id)
        if current is None:
            missing_node_ids.append(node.id)
            continue
        if (
            abs(float(current.longitude) - node.longitude) > 0.0000005
            or abs(float(current.latitude) - node.latitude) > 0.0000005
        ):
            changed_node_ids.append(node.id)
    scenario_ids = {node.id for node in scenario.nodes}
    missing_node_ids.extend(
        sorted(node_id for node_id in master_nodes if node_id not in scenario_ids)
    )
    unverified_node_ids = sorted(
        node_id
        for node_id, record in master_nodes.items()
        if record.coordinate_status != "verified"
    )
    changed_node_ids.sort()
    missing_node_ids = sorted(set(missing_node_ids))
    aligned = not changed_node_ids and not missing_node_ids and not unverified_node_ids
    if aligned:
        message = "当前场景已使用最新且全部核验通过的坐标快照"
    elif changed_node_ids:
        message = f"{len(changed_node_ids)} 个网点坐标已更新，需重新发布场景"
    elif missing_node_ids:
        message = f"{len(missing_node_ids)} 个网点与当前场景不一致，需重新发布场景"
    else:
        message = f"{len(unverified_node_ids)} 个网点尚未完成空间核验"
    return ScenarioSpatialStatus(
        scenario_id=scenario.id,
        snapshot_id=scenario.spatial_snapshot_id,
        snapshot_at=scenario.spatial_snapshot_at,
        snapshot_verified_nodes=scenario.spatial_verified_nodes,
        scenario_node_count=len(scenario.nodes),
        current_verified_nodes=sum(
            record.coordinate_status == "verified"
            for record in master_nodes.values()
        ),
        aligned=aligned,
        changed_node_ids=changed_node_ids,
        missing_node_ids=missing_node_ids,
        unverified_node_ids=unverified_node_ids,
        message=message,
    )


def list_scenario_versions(session: Session) -> list[ScenarioVersionRecord]:
    return list(
        session.scalars(
            select(ScenarioVersionRecord).order_by(
                ScenarioVersionRecord.created_at.desc(),
                ScenarioVersionRecord.id.desc(),
            )
        )
    )


def create_scenario_version(
    session: Session,
    *,
    scenario_code: str,
    county_name: str,
    scenario: Scenario,
    source_filename: str,
    warnings: list[str],
    created_by: int,
) -> ScenarioVersionRecord:
    latest_version = session.scalar(
        select(func.max(ScenarioVersionRecord.version_no)).where(
            ScenarioVersionRecord.scenario_code == scenario_code
        )
    )
    version_no = int(latest_version or 0) + 1
    version_key = f"{scenario_code}-v{version_no}"
    versioned_scenario = scenario.model_copy(update={"id": version_key})
    record = ScenarioVersionRecord(
        scenario_code=scenario_code,
        version_no=version_no,
        version_key=version_key,
        name=scenario.name,
        county_name=county_name,
        status="draft",
        source_type="excel",
        source_filename=source_filename,
        payload=versioned_scenario.model_dump(mode="json"),
        fingerprint=scenario_fingerprint(versioned_scenario.model_dump(mode="json")),
        validation_summary={"warnings": warnings, "validated": True},
        node_count=len(scenario.nodes),
        order_count=len(scenario.orders),
        vehicle_count=len(scenario.vehicles),
        created_by=created_by,
    )
    session.add(record)
    session.flush()
    record_transition(
        session,
        record,
        from_status=None,
        to_status="draft",
        note="导入场景版本",
        actor_id=created_by,
    )
    session.commit()
    session.refresh(record)
    return record


def activate_scenario_version(
    session: Session,
    record: ScenarioVersionRecord,
    *,
    actor_id: int | None = None,
    note: str = "兼容模式直接启用",
) -> ScenarioVersionRecord:
    if record.status == "active":
        return record
    for active in session.scalars(
        select(ScenarioVersionRecord).where(ScenarioVersionRecord.status == "active")
    ):
        if active.id == record.id:
            continue
        active.status = "archived"
        record_transition(
            session,
            active,
            from_status="active",
            to_status="archived",
            note=f"由 {record.version_key} 直接启用替换",
            actor_id=actor_id,
        )
    session.flush()
    previous = record.status
    record.status = "active"
    record.activated_at = datetime.now(timezone.utc)
    if actor_id is not None:
        record.reviewed_by = actor_id
        record.reviewed_at = datetime.now(timezone.utc)
        record.review_note = note
    record_transition(
        session,
        record,
        from_status=previous,
        to_status="active",
        note=note,
        actor_id=actor_id,
    )
    session.commit()
    session.refresh(record)
    return record


def save_run(
    session: Session,
    result: OptimizeResponse,
    *,
    scenario_id: str,
    event_type: str | None = None,
    event_vehicle_id: str | None = None,
    event_location: EventLocationView | None = None,
    occurred_at_minute: int = 90,
) -> OptimizationRunRecord:
    record = OptimizationRunRecord(
        id=result.run_id,
        scenario_id=scenario_id,
        status=result.status,
        solver=result.solver,
        solve_time_ms=result.solve_time_ms,
        distance_km=result.metrics.distance_km,
        estimated_cost_cny=result.metrics.estimated_cost_cny,
        vehicles_used=result.metrics.vehicles_used,
        event_type=event_type,
        event_vehicle_id=event_vehicle_id,
        output=result.model_dump(mode="json"),
    )
    session.add(record)
    session.flush()
    if event_type:
        session.add(
            EventRecord(
                event_type=event_type,
                vehicle_id=event_vehicle_id,
                occurred_at_minute=occurred_at_minute,
                detail={
                    "source": "api",
                    "run_status": result.status,
                    "location": (
                        event_location.model_dump(mode="json")
                        if event_location
                        else None
                    ),
                },
                optimization_run_id=result.run_id,
            )
        )
    session.commit()
    session.refresh(record)
    return record


def list_runs(
    session: Session,
    *,
    limit: int = 20,
    before: datetime | None = None,
) -> list[OptimizationRunRecord]:
    statement = select(OptimizationRunRecord)
    if before:
        statement = statement.where(OptimizationRunRecord.created_at < before)
    statement = statement.order_by(
        OptimizationRunRecord.created_at.desc(), OptimizationRunRecord.id.desc()
    ).limit(limit)
    return list(session.scalars(statement))
