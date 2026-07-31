from sqlalchemy import select

from app.celery_app import celery_app
from app.db import SessionLocal, initialize_database
from app.models import AIProviderConfigRecord
from app.optimization_orchestrator import orchestrate_optimization
from app.repository import load_scenario, save_run, seed_demo_data
from app.schemas import OptimizeRequest


@celery_app.task(name="app.tasks.optimize_scenario")
def optimize_scenario_task(time_limit_seconds: int = 5, scenario_id: str | None = None) -> dict:
    initialize_database()
    with SessionLocal() as session:
        seed_demo_data(session)
        scenario = load_scenario(session, scenario_id)
        ai_config = session.scalar(
            select(AIProviderConfigRecord)
            .where(AIProviderConfigRecord.enabled.is_(True))
            .order_by(AIProviderConfigRecord.updated_at.desc())
            .limit(1)
        )
        result = orchestrate_optimization(
            scenario,
            OptimizeRequest(time_limit_seconds=time_limit_seconds),
            ai_config=ai_config,
        )
        save_run(session, result, scenario_id=scenario.id)
        return result.model_dump(mode="json")
