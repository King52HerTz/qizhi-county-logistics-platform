from __future__ import annotations

import json

from sqlalchemy import delete, select, text

from app.config import get_settings
from app.db import SessionLocal, initialize_database
from app.experiment_service import run_experiment
from app.models import (
    AlgorithmExperimentRecord,
    AuditLogRecord,
    DataImportBatchRecord,
    DispatchPlanRecord,
    DispatchTransitionRecord,
    DriverAssignmentRecord,
    EventRecord,
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
from app.repository import load_scenario, save_run, seed_demo_data
from app.schemas import ExperimentCreate, OptimizeRequest
from app.security import hash_password


def reset_demo_data() -> dict[str, object]:
    settings = get_settings()
    preserved_users = (settings.admin_username, settings.driver_username)

    # The standalone reset command is also used by the local one-click demo
    # launcher.  Bring the schema to the current revision before touching any
    # rows so a fresh checkout can be restored without a separate migration
    # step.
    initialize_database()

    with SessionLocal() as session:
        for model in (
            DispatchTransitionRecord,
            DriverAssignmentRecord,
            DispatchPlanRecord,
            EventRecord,
            OptimizationRunRecord,
            AlgorithmExperimentRecord,
            ScenarioTransitionRecord,
            ScenarioVersionRecord,
            NodeCoordinateRevisionRecord,
            DataImportBatchRecord,
            OrderRequestRecord,
            OrderRecord,
            VehicleRecord,
            NodeRecord,
            AuditLogRecord,
        ):
            session.execute(delete(model))

        session.execute(
            delete(UserRecord).where(UserRecord.username.not_in(preserved_users))
        )
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            for sequence in (
                "data_import_batches_id_seq",
                "node_coordinate_revisions_id_seq",
                "dispatch_events_id_seq",
                "audit_logs_id_seq",
                "scenario_versions_id_seq",
                "scenario_version_transitions_id_seq",
                "algorithm_experiments_id_seq",
                "dispatch_plans_id_seq",
                "driver_assignments_id_seq",
                "dispatch_transitions_id_seq",
            ):
                session.execute(text(f"ALTER SEQUENCE {sequence} RESTART WITH 1"))
        session.commit()

        seed_demo_data(session)

        admin = session.scalar(
            select(UserRecord).where(UserRecord.username == settings.admin_username)
        )
        driver = session.scalar(
            select(UserRecord).where(UserRecord.username == settings.driver_username)
        )
        if admin is None or driver is None:
            raise RuntimeError("标准演示账号初始化失败")

        admin.password_hash = hash_password(settings.admin_password)
        admin.display_name = "系统管理员"
        admin.role = "admin"
        admin.is_active = True
        admin.failed_login_count = 0
        admin.locked_until = None
        admin.last_login_at = None
        admin.last_login_ip = None

        driver.password_hash = hash_password(settings.driver_password)
        driver.display_name = "配送驾驶员"
        driver.role = "driver"
        driver.is_active = True
        driver.failed_login_count = 0
        driver.locked_until = None
        driver.last_login_at = None
        driver.last_login_ip = None
        session.commit()

        scenario = load_scenario(session)
        initial_result = orchestrate_optimization(
            scenario,
            OptimizeRequest(
                profile="standard-v1",
                strategy="balanced",
                ai_assisted=False,
                candidate_count=1,
                time_limit_seconds=3,
            ),
            ai_config=None,
        )
        save_run(session, initial_result, scenario_id=scenario.id)
        experiment = run_experiment(
            session,
            ExperimentCreate(
                name="标准演示场景算法验证",
                scenario_id=scenario.id,
                time_limit_seconds=1,
            ),
            admin,
        )

        summary = {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "nodes": len(scenario.nodes),
            "orders": len(scenario.orders),
            "vehicles": len(scenario.vehicles),
            "initial_run_id": initial_result.run_id,
            "experiment_code": experiment.experiment_code,
            "preserved": [
                "ai_provider_configs",
                "map_provider_configs",
                "data_quality_rules",
            ],
        }
        print(json.dumps(summary, ensure_ascii=False))
        return summary


if __name__ == "__main__":
    reset_demo_data()
