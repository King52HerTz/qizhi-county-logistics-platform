from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    DispatchPlanRecord,
    DispatchTransitionRecord,
    DriverAssignmentRecord,
    OptimizationRunRecord,
    OrderRecord,
    UserRecord,
)
from app.schemas import (
    DispatchPlanView,
    DriverAssignmentView,
    DriverNavigationStop,
)


class DispatchWorkflowError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log_transition(
    session: Session,
    *,
    plan_id: int,
    actor_id: int,
    from_status: str | None,
    to_status: str,
    assignment_id: int | None = None,
    note: str | None = None,
) -> None:
    session.add(
        DispatchTransitionRecord(
            plan_id=plan_id,
            assignment_id=assignment_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            note=note,
        )
    )


def _update_route_orders(session: Session, route_payload: dict, status: str) -> None:
    """Keep master orders aligned with the operational execution lifecycle."""
    order_ids = {
        str(stop.get("order_id"))
        for stop in route_payload.get("stops", [])
        if stop.get("order_id")
    }
    if not order_ids:
        return
    records = session.scalars(
        select(OrderRecord).where(OrderRecord.id.in_(order_ids))
    ).all()
    for record in records:
        if status == "planned" and record.status == "pending":
            record.status = "planned"
        elif status == "completed" and record.status in {"pending", "planned"}:
            record.status = "completed"


def get_plan(session: Session, plan_id: int, *, lock: bool = False) -> DispatchPlanRecord:
    statement = (
        select(DispatchPlanRecord)
        .where(DispatchPlanRecord.id == plan_id)
        .execution_options(populate_existing=True)
        .options(
            selectinload(DispatchPlanRecord.assignments).selectinload(
                DriverAssignmentRecord.driver
            ),
            selectinload(DispatchPlanRecord.run),
        )
    )
    if lock:
        statement = statement.with_for_update()
    plan = session.scalar(statement)
    if plan is None:
        raise LookupError("调度执行方案不存在")
    return plan


def list_plans(session: Session, limit: int = 30) -> list[DispatchPlanRecord]:
    return list(
        session.scalars(
            select(DispatchPlanRecord)
            .options(
                selectinload(DispatchPlanRecord.assignments).selectinload(
                    DriverAssignmentRecord.driver
                ),
                selectinload(DispatchPlanRecord.run),
            )
            .order_by(DispatchPlanRecord.updated_at.desc(), DispatchPlanRecord.id.desc())
            .limit(limit)
        )
    )


def create_plan(session: Session, run_id: str, actor: UserRecord) -> DispatchPlanRecord:
    run = session.get(OptimizationRunRecord, run_id)
    if run is None:
        raise LookupError("调度求解方案不存在")
    if run.status == "infeasible":
        raise DispatchWorkflowError("不可行求解结果不能提交执行审批")
    existing = session.scalar(
        select(DispatchPlanRecord).where(DispatchPlanRecord.run_id == run_id)
    )
    if existing is not None:
        return get_plan(session, existing.id)
    plan = DispatchPlanRecord(
        run_id=run_id,
        status="pending_approval",
        submitted_by=actor.id,
    )
    session.add(plan)
    session.flush()
    _log_transition(
        session,
        plan_id=plan.id,
        actor_id=actor.id,
        from_status=None,
        to_status="pending_approval",
        note="方案提交审批",
    )
    session.commit()
    return get_plan(session, plan.id)


def review_plan(
    session: Session,
    plan_id: int,
    actor: UserRecord,
    *,
    approve: bool,
    note: str | None,
) -> DispatchPlanRecord:
    plan = get_plan(session, plan_id, lock=True)
    if plan.status != "pending_approval":
        raise DispatchWorkflowError("只有待审批方案可以审核")
    target = "approved" if approve else "rejected"
    previous = plan.status
    plan.status = target
    plan.reviewed_by = actor.id
    plan.reviewed_at = _now()
    plan.rejection_reason = None if approve else (note or "审批未通过")
    _log_transition(
        session,
        plan_id=plan.id,
        actor_id=actor.id,
        from_status=previous,
        to_status=target,
        note=note,
    )
    session.commit()
    return get_plan(session, plan.id)


def dispatch_plan(
    session: Session,
    plan_id: int,
    actor: UserRecord,
) -> DispatchPlanRecord:
    plan = get_plan(session, plan_id, lock=True)
    if plan.status != "approved":
        raise DispatchWorkflowError("只有已批准方案可以下发")
    driver = session.scalar(
        select(UserRecord).where(
            UserRecord.username == get_settings().driver_username,
            UserRecord.role == "driver",
            UserRecord.is_active.is_(True),
        )
    )
    if driver is None:
        raise DispatchWorkflowError("没有可用驾驶员账号")
    routes = plan.run.output.get("routes", [])
    if not routes:
        raise DispatchWorkflowError("方案没有可下发路线")
    for route_index, route in enumerate(routes):
        _update_route_orders(session, route, "planned")
        session.add(
            DriverAssignmentRecord(
                plan_id=plan.id,
                route_index=route_index,
                vehicle_id=str(route.get("vehicle_id", "")),
                plate=str(route.get("plate", "")),
                assigned_driver_id=driver.id,
                status="pending",
                route_payload=route,
            )
        )
    previous = plan.status
    plan.status = "dispatched"
    plan.dispatched_at = _now()
    session.flush()
    _log_transition(
        session,
        plan_id=plan.id,
        actor_id=actor.id,
        from_status=previous,
        to_status="dispatched",
        note=f"下发 {len(routes)} 条车辆任务",
    )
    session.commit()
    return get_plan(session, plan.id)


def list_driver_assignments(
    session: Session,
    actor: UserRecord,
) -> list[DriverAssignmentRecord]:
    statement = (
        select(DriverAssignmentRecord)
        .options(
            selectinload(DriverAssignmentRecord.driver),
            selectinload(DriverAssignmentRecord.plan),
        )
        .order_by(DriverAssignmentRecord.updated_at.desc(), DriverAssignmentRecord.id.desc())
    )
    if actor.role == "driver":
        statement = statement.where(DriverAssignmentRecord.assigned_driver_id == actor.id)
    return list(session.scalars(statement))


def advance_assignment(
    session: Session,
    assignment_id: int,
    actor: UserRecord,
    action: str,
    note: str | None,
) -> DispatchPlanRecord:
    assignment = session.scalar(
        select(DriverAssignmentRecord)
        .where(DriverAssignmentRecord.id == assignment_id)
        .with_for_update()
    )
    if assignment is None:
        raise LookupError("驾驶员任务不存在")
    if actor.role == "driver" and assignment.assigned_driver_id != actor.id:
        raise PermissionError("不能操作其他驾驶员的任务")
    transitions = {
        "accept": ("pending", "accepted"),
        "start": ("accepted", "executing"),
        "complete": ("executing", "completed"),
    }
    expected, target = transitions[action]
    if assignment.status != expected:
        raise DispatchWorkflowError(f"任务当前为 {assignment.status}，不能执行 {action}")
    previous = assignment.status
    assignment.status = target
    moment = _now()
    if target == "accepted":
        assignment.accepted_at = moment
    elif target == "executing":
        assignment.started_at = moment
    else:
        assignment.completed_at = moment
        assignment.completion_note = note or "配送任务已完成"
        _update_route_orders(session, assignment.route_payload, "completed")
    session.flush()
    _log_transition(
        session,
        plan_id=assignment.plan_id,
        assignment_id=assignment.id,
        actor_id=actor.id,
        from_status=previous,
        to_status=target,
        note=note,
    )

    plan = get_plan(session, assignment.plan_id, lock=True)
    statuses = [item.status for item in plan.assignments]
    if statuses and all(status == "completed" for status in statuses):
        plan_target = "completed"
        plan.completed_at = moment
    elif any(status in {"executing", "completed"} for status in statuses):
        plan_target = "executing"
    elif statuses and all(status == "accepted" for status in statuses):
        plan_target = "accepted"
    else:
        plan_target = "dispatched"
    if plan.status != plan_target:
        old_plan_status = plan.status
        plan.status = plan_target
        _log_transition(
            session,
            plan_id=plan.id,
            actor_id=actor.id,
            from_status=old_plan_status,
            to_status=plan_target,
            note="驾驶员任务状态汇总",
        )
    session.commit()
    return get_plan(session, plan.id)


def assignment_view(record: DriverAssignmentRecord) -> DriverAssignmentView:
    route = record.route_payload
    stops = route.get("stops", [])
    navigation_stops = [
        DriverNavigationStop(
            sequence=sequence,
            order_id=stop.get("order_id"),
            node_id=str(stop.get("node_id", "")),
            node_name=str(stop.get("node_name", "")),
            longitude=float(stop.get("longitude", 0)),
            latitude=float(stop.get("latitude", 0)),
            arrival_minute=int(stop.get("arrival_minute", 0)),
            load_kg=int(stop.get("load_kg", 0)),
            status=(
                "completed"
                if stop.get("status") == "completed"
                else "planned"
            ),
            action=(
                stop.get("action")
                if stop.get("action") in {"pickup", "delivery"}
                else "delivery"
            ),
            flow_direction=(
                stop.get("flow_direction")
                if stop.get("flow_direction") in {"upward", "downward"}
                else None
            ),
            cargo_category=(
                stop.get("cargo_category")
                if stop.get("cargo_category") in {"agricultural", "industrial"}
                else None
            ),
        )
        for sequence, stop in enumerate(
            (item for item in stops if item.get("status") != "depot"),
            start=1,
        )
    ]
    next_stop = next(
        (stop for stop in navigation_stops if stop.status != "completed"),
        None,
    )
    return DriverAssignmentView(
        id=record.id,
        plan_id=record.plan_id,
        route_index=record.route_index,
        vehicle_id=record.vehicle_id,
        plate=record.plate,
        status=record.status,
        driver_username=record.driver.username if record.driver else None,
        distance_km=float(route.get("distance_km", 0)),
        duration_minutes=int(route.get("duration_minutes", 0)),
        load_kg=int(route.get("load_kg", 0)),
        stop_count=max(0, len(stops) - 2),
        next_stop_name=next_stop.node_name if next_stop else None,
        next_stop=next_stop,
        navigation_stops=navigation_stops,
        accepted_at=record.accepted_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        completion_note=record.completion_note,
        updated_at=record.updated_at,
    )


def plan_view(session: Session, record: DispatchPlanRecord) -> DispatchPlanView:
    submitted = session.get(UserRecord, record.submitted_by) if record.submitted_by else None
    reviewed = session.get(UserRecord, record.reviewed_by) if record.reviewed_by else None
    return DispatchPlanView(
        id=record.id,
        run_id=record.run_id,
        scenario_id=record.run.scenario_id,
        status=record.status,
        submitted_by=submitted.username if submitted else None,
        reviewed_by=reviewed.username if reviewed else None,
        rejection_reason=record.rejection_reason,
        route_count=len(record.run.output.get("routes", [])),
        distance_km=float(record.run.distance_km),
        estimated_cost_cny=float(record.run.estimated_cost_cny),
        submitted_at=record.submitted_at,
        reviewed_at=record.reviewed_at,
        dispatched_at=record.dispatched_at,
        completed_at=record.completed_at,
        updated_at=record.updated_at,
        assignments=[assignment_view(item) for item in record.assignments],
    )
