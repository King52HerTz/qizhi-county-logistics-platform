from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlgorithmExperimentRecord, ScenarioVersionRecord, UserRecord
from app.repository import load_scenario
from app.schemas import ExperimentCreate, ExperimentView, Scenario
from app.solver import solve_scenario


CASE_DEFINITIONS = (
    {
        "case_key": "standard",
        "case_name": "标准负荷",
        "description": "使用当前激活场景的原始订单货量。",
        "demand_multiplier": 1.0,
    },
    {
        "case_key": "peak",
        "case_name": "旺季峰值",
        "description": "全部订单货量提升 18%，验证旺季运力弹性。",
        "demand_multiplier": 1.18,
    },
    {
        "case_key": "cold_chain",
        "case_name": "冷链压力",
        "description": "冷链订单提升 22%，常温订单提升 8%，验证冷链兼容约束。",
        "demand_multiplier": 1.08,
    },
)


def _fingerprint(scenario: Scenario) -> str:
    canonical = json.dumps(
        scenario.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _scenario_variant(scenario: Scenario, case_key: str) -> Scenario:
    variant = scenario.model_copy(deep=True)
    variant.orders = [
        order.model_copy(
            update={
                "weight_kg": round(
                    order.weight_kg
                    * (
                        1.22
                        if case_key == "cold_chain" and order.cold_chain
                        else 1.08
                        if case_key == "cold_chain"
                        else 1.18
                        if case_key == "peak"
                        else 1.0
                    )
                )
            }
        )
        for order in variant.orders
    ]
    return variant


def _percent_reduction(baseline: float, optimized: float) -> float:
    if baseline <= 0:
        return 0.0
    return round((baseline - optimized) / baseline * 100, 1)


def experiment_view(record: AlgorithmExperimentRecord) -> ExperimentView:
    return ExperimentView(
        id=record.id,
        experiment_code=record.experiment_code,
        name=record.name,
        scenario_key=record.scenario_key,
        scenario_fingerprint=record.scenario_fingerprint,
        status=record.status,
        solver=record.solver,
        baseline=record.baseline,
        time_limit_seconds=record.time_limit_seconds,
        case_count=record.case_count,
        summary=record.summary or None,
        results=record.results or [],
        error_message=record.error_message,
        created_by=record.creator.username if record.creator else None,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


def list_experiments(session: Session, limit: int = 20) -> list[AlgorithmExperimentRecord]:
    return list(
        session.scalars(
            select(AlgorithmExperimentRecord)
            .order_by(
                AlgorithmExperimentRecord.created_at.desc(),
                AlgorithmExperimentRecord.id.desc(),
            )
            .limit(limit)
        )
    )


def get_experiment(session: Session, experiment_id: int) -> AlgorithmExperimentRecord:
    record = session.get(AlgorithmExperimentRecord, experiment_id)
    if record is None:
        raise LookupError("算法实验不存在")
    return record


def run_experiment(
    session: Session,
    request: ExperimentCreate,
    user: UserRecord,
) -> AlgorithmExperimentRecord:
    scenario = load_scenario(session, request.scenario_id)
    scenario_record = session.scalar(
        select(ScenarioVersionRecord).where(
            ScenarioVersionRecord.version_key == scenario.id
        )
    )
    record = AlgorithmExperimentRecord(
        experiment_code=f"TMP-{uuid4().hex[:20]}",
        name=request.name,
        scenario_version_id=scenario_record.id if scenario_record else None,
        scenario_key=scenario.id,
        scenario_fingerprint=_fingerprint(scenario),
        status="running",
        solver="ortools-routing",
        baseline="round-robin-heuristic",
        time_limit_seconds=request.time_limit_seconds,
        case_count=len(CASE_DEFINITIONS),
        summary={},
        results=[],
        created_by=user.id,
    )
    session.add(record)
    session.flush()
    record.experiment_code = (
        f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{record.id:04d}"
    )
    session.commit()

    try:
        results: list[dict] = []
        for definition in CASE_DEFINITIONS:
            variant = _scenario_variant(scenario, definition["case_key"])
            solved = solve_scenario(
                variant,
                time_limit_seconds=request.time_limit_seconds,
            )
            baseline_distance = solved.baseline_metrics.distance_km
            optimized_distance = solved.metrics.distance_km
            baseline_cost = solved.baseline_metrics.estimated_cost_cny
            optimized_cost = solved.metrics.estimated_cost_cny
            results.append(
                {
                    **definition,
                    "demand_tons": round(
                        sum(order.weight_kg for order in variant.orders) / 1000,
                        2,
                    ),
                    "status": solved.status,
                    "solve_time_ms": solved.solve_time_ms,
                    "baseline_distance_km": baseline_distance,
                    "optimized_distance_km": optimized_distance,
                    "distance_reduction_pct": _percent_reduction(
                        baseline_distance, optimized_distance
                    ),
                    "baseline_cost_cny": baseline_cost,
                    "optimized_cost_cny": optimized_cost,
                    "cost_saving_cny": round(baseline_cost - optimized_cost, 0),
                    "cost_reduction_pct": _percent_reduction(
                        baseline_cost, optimized_cost
                    ),
                    "vehicles_used": solved.metrics.vehicles_used,
                    "service_rate": solved.metrics.on_time_rate,
                    "unassigned_orders": len(solved.unassigned_order_ids),
                    "routing_source": solved.routing.source,
                }
            )

        completed = [item for item in results if item["status"] != "infeasible"]
        divisor = len(completed) or 1
        record.results = results
        record.summary = {
            "average_distance_reduction_pct": round(
                sum(item["distance_reduction_pct"] for item in completed) / divisor,
                1,
            ),
            "total_cost_saving_cny": round(
                sum(item["cost_saving_cny"] for item in completed),
                0,
            ),
            "average_cost_reduction_pct": round(
                sum(item["cost_reduction_pct"] for item in completed) / divisor,
                1,
            ),
            "average_service_rate": round(
                sum(item["service_rate"] for item in completed) / divisor,
                1,
            ),
            "average_vehicles_used": round(
                sum(item["vehicles_used"] for item in completed) / divisor,
                1,
            ),
            "total_solve_time_ms": sum(item["solve_time_ms"] for item in results),
            "completed_cases": len(completed),
        }
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(record)
        return record
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)[:2000]
        record.completed_at = datetime.now(timezone.utc)
        session.commit()
        raise
