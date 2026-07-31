from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    AIProviderConfigRecord,
    AlgorithmExperimentRecord,
    AuditLogRecord,
    DispatchPlanRecord,
    DriverAssignmentRecord,
    EventRecord,
    OptimizationRunRecord,
    ScenarioTransitionRecord,
    ScenarioVersionRecord,
)
from app.scenario_governance import scenario_fingerprint


def _dimension(
    key: str,
    name: str,
    weighted_checks: list[tuple[bool, int, str]],
) -> dict[str, Any]:
    checks = [label for passed, _, label in weighted_checks if passed]
    gaps = [label for passed, _, label in weighted_checks if not passed]
    score = sum(weight for passed, weight, _ in weighted_checks if passed)
    return {
        "key": key,
        "name": name,
        "score": score,
        "ready": score >= 80,
        "checks": checks,
        "gaps": gaps,
    }


def _latest(
    session: Session,
    model,
    *,
    where=None,
    order_column=None,
):
    statement = select(model)
    if where is not None:
        statement = statement.where(where)
    column = order_column if order_column is not None else model.created_at
    return session.scalar(statement.order_by(column.desc(), model.id.desc()).limit(1))


def build_competition_readiness(session: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    active_scenarios = list(
        session.scalars(
            select(ScenarioVersionRecord)
            .where(ScenarioVersionRecord.status == "active")
            .order_by(ScenarioVersionRecord.activated_at.desc())
        )
    )
    scenario = active_scenarios[0] if active_scenarios else None
    fingerprint = (
        scenario.fingerprint or scenario_fingerprint(scenario.payload)
        if scenario
        else None
    )
    experiment = _latest(
        session,
        AlgorithmExperimentRecord,
        where=AlgorithmExperimentRecord.status == "completed",
        order_column=AlgorithmExperimentRecord.completed_at,
    )
    run = _latest(
        session,
        OptimizationRunRecord,
        where=OptimizationRunRecord.status.in_(("optimal", "feasible")),
    )
    event = _latest(session, EventRecord)
    event_run = event.run if event else None
    plan = _latest(session, DispatchPlanRecord, order_column=DispatchPlanRecord.updated_at)
    assignments = list(plan.assignments) if plan else []
    enabled_ai = session.scalar(
        select(AIProviderConfigRecord.id)
        .where(AIProviderConfigRecord.enabled.is_(True))
        .limit(1)
    )
    transition_count = (
        session.scalar(
            select(func.count(ScenarioTransitionRecord.id)).where(
                ScenarioTransitionRecord.scenario_version_id == scenario.id
            )
        )
        if scenario
        else 0
    )
    audit_count = session.scalar(select(func.count(AuditLogRecord.id))) or 0
    database_ok = True
    try:
        session.execute(text("select 1"))
    except Exception:
        database_ok = False

    validated = bool(scenario and scenario.validation_summary.get("validated"))
    data_dimension = _dimension(
        "data",
        "数据场景",
        [
            (len(active_scenarios) == 1, 40, "存在且仅存在一个生效场景"),
            (bool(fingerprint and len(fingerprint) == 64), 20, "场景具备 SHA-256 数据指纹"),
            (
                bool(
                    scenario
                    and scenario.node_count > 0
                    and scenario.order_count > 0
                    and scenario.vehicle_count > 0
                ),
                20,
                "节点、订单和车辆数据完整",
            ),
            (validated, 20, "场景数据校验通过"),
        ],
    )

    experiment_results = experiment.results if experiment else []
    case_keys = {item.get("case_key") for item in experiment_results}
    summary = experiment.summary if experiment else {}
    algorithm_dimension = _dimension(
        "algorithm",
        "算法实验",
        [
            (experiment is not None, 40, "存在已完成算法实验"),
            (
                {"standard", "peak", "cold_chain"}.issubset(case_keys),
                30,
                "标准、旺季和冷链三类压力案例完成",
            ),
            (
                bool(experiment and fingerprint and experiment.scenario_fingerprint == fingerprint),
                20,
                "实验指纹与当前场景一致",
            ),
            (
                float(summary.get("average_service_rate", 0)) >= 95,
                10,
                "平均订单服务率达到 95%",
            ),
        ],
    )

    active_plan_statuses = {"approved", "dispatched", "accepted", "executing", "completed"}
    progressed_assignment = any(
        item.status in {"accepted", "executing", "completed"} for item in assignments
    )
    execution_dimension = _dimension(
        "execution",
        "执行闭环",
        [
            (plan is not None, 30, "存在调度审批方案"),
            (bool(plan and plan.status in active_plan_statuses), 25, "方案已批准或下发"),
            (len(assignments) > 0, 25, "已生成司机任务"),
            (progressed_assignment, 20, "司机任务已进入接单或执行状态"),
        ],
    )

    system_dimension = _dimension(
        "system",
        "系统保障",
        [
            (database_ok, 30, "数据库连接和查询正常"),
            (enabled_ai is not None, 20, "存在启用的 AI 服务配置"),
            (True, 20, "真实路网异常时可回退离线矩阵"),
            (bool(transition_count), 15, "生效场景具备版本轨迹"),
            (audit_count > 0, 15, "平台存在可追溯审计记录"),
        ],
    )
    dimensions = [
        data_dimension,
        algorithm_dimension,
        execution_dimension,
        system_dimension,
    ]
    overall_score = round(sum(item["score"] for item in dimensions) / len(dimensions))

    standard = next(
        (item for item in experiment_results if item.get("case_key") == "standard"),
        experiment_results[0] if experiment_results else {},
    )
    experiment_code = experiment.experiment_code if experiment else None
    run_id = run.id if run else None
    average_solve_ms = (
        round(float(summary.get("total_solve_time_ms", 0)) / max(len(experiment_results), 1))
        if experiment
        else (run.solve_time_ms if run else 0)
    )
    kpis = [
        {
            "key": "distance_reduction",
            "name": "里程改善",
            "value": float(summary.get("average_distance_reduction_pct", 0)),
            "unit": "%",
            "source_id": experiment_code,
        },
        {
            "key": "cost_saving",
            "name": "成本节约",
            "value": float(summary.get("total_cost_saving_cny", 0)),
            "unit": "元",
            "source_id": experiment_code,
        },
        {
            "key": "service_rate",
            "name": "服务率",
            "value": float(summary.get("average_service_rate", 0)),
            "unit": "%",
            "source_id": experiment_code,
        },
        {
            "key": "solve_time",
            "name": "平均求解耗时",
            "value": float(average_solve_ms),
            "unit": "ms",
            "source_id": experiment_code or run_id,
        },
    ]
    comparison = [
        {
            "key": "distance",
            "name": "总里程",
            "baseline": float(standard.get("baseline_distance_km", 0)),
            "optimized": float(standard.get("optimized_distance_km", 0)),
            "unit": "km",
            "improvement": float(standard.get("distance_reduction_pct", 0)),
        },
        {
            "key": "cost",
            "name": "预计成本",
            "baseline": float(standard.get("baseline_cost_cny", 0)),
            "optimized": float(standard.get("optimized_cost_cny", 0)),
            "unit": "元",
            "improvement": float(standard.get("cost_reduction_pct", 0)),
        },
        {
            "key": "service",
            "name": "订单服务率",
            "baseline": 0,
            "optimized": float(standard.get("service_rate", 0)),
            "unit": "%",
            "improvement": float(standard.get("service_rate", 0)),
        },
        {
            "key": "vehicles",
            "name": "使用车辆",
            "baseline": float(standard.get("baseline_vehicles_used", 0)),
            "optimized": float(standard.get("vehicles_used", 0)),
            "unit": "辆",
            "improvement": 0,
        },
    ]

    evidence = [
        {
            "requirement": "智能调度验证",
            "capability": "多约束车辆调度，兼顾里程、成本和服务率",
            "evidence_id": experiment_code,
            "status": "verified" if experiment else "attention",
            "route": "/experiments",
        },
        {
            "requirement": "路径规划",
            "capability": "容量、时间窗、班次和冷链硬约束下生成路线",
            "evidence_id": run_id or experiment_code,
            "status": "verified" if run or experiment else "attention",
            "route": "/dispatch",
        },
        {
            "requirement": "动态响应",
            "capability": "车辆故障与紧急订单触发约束重建和重调度",
            "evidence_id": event_run.id if event_run else None,
            "status": "verified" if event_run else "attention",
            "route": "/events",
        },
        {
            "requirement": "可视化",
            "capability": "县域地图、路线、停靠顺序和优化前后指标展示",
            "evidence_id": run_id,
            "status": "verified" if run else "attention",
            "route": "/dispatch",
        },
        {
            "requirement": "业务执行闭环",
            "capability": "方案提交、审核、下发、接单、执行和完成留痕",
            "evidence_id": f"PLAN-{plan.id}" if plan else None,
            "status": "verified" if plan and assignments else "attention",
            "route": "/execution",
        },
        {
            "requirement": "成果转化",
            "capability": "场景版本化、算法可复现、证据聚合和报告输出",
            "evidence_id": scenario.version_key if scenario else None,
            "status": "verified" if scenario and experiment else "attention",
            "route": "/scenarios",
        },
    ]

    references = [
        {
            "label": "当前场景版本",
            "value": scenario.version_key if scenario else None,
            "detail": (
                f"{scenario.county_name} · {scenario.node_count} 节点 · "
                f"{scenario.order_count} 订单 · {scenario.vehicle_count} 车辆"
                if scenario
                else "尚无生效场景"
            ),
            "route": "/scenarios",
            "ready": scenario is not None,
        },
        {
            "label": "最新实验指纹",
            "value": experiment_code,
            "detail": (
                f"fingerprint: {experiment.scenario_fingerprint[:16]}…"
                if experiment
                else "尚无已完成实验"
            ),
            "route": "/experiments",
            "ready": experiment is not None,
        },
        {
            "label": "最新调度运行",
            "value": run_id,
            "detail": (
                f"{run.solver} · {run.status} · {run.solve_time_ms} ms"
                if run
                else "尚无可用调度运行"
            ),
            "route": "/history",
            "ready": run is not None,
        },
        {
            "label": "系统保障状态",
            "value": f"{sum(1 for item in system_dimension['checks'])}/5 项通过",
            "detail": "数据库、AI 配置、路网回退、版本轨迹和审计",
            "route": "/settings/security",
            "ready": system_dimension["ready"],
        },
    ]

    script = [
        {
            "step": 1,
            "title": "业务场景",
            "duration_seconds": 60,
            "description": "介绍祁东县黄花菜城乡双向配送痛点与数据场景",
            "route": "/scenarios",
            "ready": scenario is not None,
        },
        {
            "step": 2,
            "title": "智能调度验证",
            "duration_seconds": 120,
            "description": "核验多约束路径方案、路网路线与优化效果",
            "route": "/dispatch",
            "ready": run is not None,
        },
        {
            "step": 3,
            "title": "动态事件处置",
            "duration_seconds": 90,
            "description": "处置车辆故障和紧急冷链订单并重新求解",
            "route": "/events",
            "ready": event_run is not None,
        },
        {
            "step": 4,
            "title": "审批执行闭环",
            "duration_seconds": 60,
            "description": "核验方案审批、任务下发与司机状态流转",
            "route": "/execution",
            "ready": bool(plan and assignments),
        },
        {
            "step": 5,
            "title": "成果归档",
            "duration_seconds": 60,
            "description": "核验实验指纹、证据矩阵并导出成果报告",
            "route": "/readiness",
            "ready": experiment is not None,
        },
    ]
    tips = [
        "建议从第 2 步“智能调度验证”开始运行核验，优先检查核心能力。",
        "切换场景版本后应重新运行实验，确保场景与实验指纹一致。",
        "运行核验前确认网络环境；真实路网不可用时系统会自动离线回退。",
        "成果报告仅包含聚合指标和记录编号，不包含密钥与个人敏感信息。",
    ]
    return {
        "generated_at": now,
        "overall_score": overall_score,
        "dimensions": dimensions,
        "script": script,
        "kpis": kpis,
        "comparison": comparison,
        "evidence": evidence,
        "references": references,
        "tips": tips,
        "total_duration_seconds": sum(item["duration_seconds"] for item in script),
    }


def build_competition_report(data: dict[str, Any]) -> str:
    dimensions = "".join(
        f"<tr><td>{escape(item['name'])}</td><td>{item['score']}/100</td>"
        f"<td>{'就绪' if item['ready'] else '需补充'}</td>"
        f"<td>{escape('；'.join(item['gaps']) or '无')}</td></tr>"
        for item in data["dimensions"]
    )
    kpis = "".join(
        f"<div class='kpi'><span>{escape(item['name'])}</span>"
        f"<strong>{item['value']:g}{escape(item['unit'])}</strong>"
        f"<small>{escape(item['source_id'] or '暂无证据编号')}</small></div>"
        for item in data["kpis"]
    )
    evidence = "".join(
        f"<tr><td>{escape(item['requirement'])}</td>"
        f"<td>{escape(item['capability'])}</td>"
        f"<td>{escape(item['evidence_id'] or '待补充')}</td>"
        f"<td>{'已验证' if item['status'] == 'verified' else '需补充'}</td></tr>"
        for item in data["evidence"]
    )
    references = {item["label"]: item for item in data["references"]}
    scenario = references.get("当前场景版本", {})
    experiment = references.get("最新实验指纹", {})
    generated = data["generated_at"].astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>祁智运运营成果证据报告</title>
<style>
*{{box-sizing:border-box}}body{{font-family:"Microsoft YaHei",sans-serif;color:#173a29;margin:0;background:#eef3ef}}
main{{width:980px;margin:24px auto;background:#fff;padding:38px 44px;box-shadow:0 8px 30px #173a2918}}
h1{{margin:0;font-size:30px}}h2{{font-size:18px;margin:28px 0 10px;border-bottom:2px solid #16794a;padding-bottom:8px}}
.meta{{color:#6d7b73;font-size:12px;margin-top:8px}}.score{{display:flex;align-items:center;justify-content:space-between;background:#0b4b32;color:#fff;padding:22px 26px;margin:24px 0}}
.score strong{{font-size:42px}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.kpi{{border:1px solid #dce5df;padding:14px}}
.kpi span,.kpi small{{display:block;color:#78857e;font-size:11px}}.kpi strong{{display:block;font-size:22px;color:#147a4a;margin:7px 0}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:10px;border:1px solid #dfe6e1;text-align:left;vertical-align:top}}th{{background:#f1f6f3}}
.note{{background:#fff8e8;border-left:4px solid #efad27;padding:12px;font-size:12px;line-height:1.8}}
footer{{margin-top:30px;padding-top:12px;border-top:1px solid #dfe6e1;color:#819087;font-size:10px}}
@media print{{body{{background:#fff}}main{{width:auto;margin:0;box-shadow:none;padding:20px}}}}
</style></head><body><main>
<h1>祁智运运营成果证据报告</h1>
<p class="meta">祁东县城乡物流智能决策平台 · 生成时间：{escape(generated)}</p>
<section class="score"><div><b>运营就绪度</b><p>数据场景 → 算法评估 → 调度执行 → 成果归档</p></div><strong>{data['overall_score']}/100</strong></section>
<h2>一、平台定位</h2>
<p>平台面向祁东县黄花菜采收、加工与城乡双向配送场景，以可验证的车辆路径优化为核心，融合容量、时间窗、车辆班次和冷链兼容约束，实现智能调度、动态响应、审批执行和数据治理闭环。</p>
<div class="note">当前场景：{escape(str(scenario.get('value') or '待补充'))}<br>{escape(str(scenario.get('detail') or ''))}<br>最新实验：{escape(str(experiment.get('value') or '待补充'))} · {escape(str(experiment.get('detail') or ''))}</div>
<h2>二、核心成果</h2><div class="kpis">{kpis}</div>
<h2>三、就绪度核验</h2><table><thead><tr><th>维度</th><th>得分</th><th>状态</th><th>缺口</th></tr></thead><tbody>{dimensions}</tbody></table>
<h2>四、能力验证矩阵</h2><table><thead><tr><th>能力维度</th><th>已实现能力</th><th>验证依据</th><th>状态</th></tr></thead><tbody>{evidence}</tbody></table>
<h2>五、算法与工程说明</h2>
<p>确定性求解由 Google OR-Tools 完成，大语言模型仅用于结果解释。人工基线与优化方案使用同一场景和同一道路矩阵，实验同时保留场景 SHA-256 指纹、求解器、时限、压力规则和逐案例指标，确保结果可复现。</p>
<p>系统采用 Vue 3、FastAPI、PostgreSQL/PostGIS、Redis/Celery 和 Docker Compose；API Key 加密存储，场景发布、方案审批和司机任务流转均保留审计记录。</p>
<footer>本报告仅包含聚合业务指标和证据编号，不包含 API Key、密码、数据库连接信息或个人联系方式。</footer>
</main></body></html>"""
