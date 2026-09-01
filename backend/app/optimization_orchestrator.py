from __future__ import annotations

from app.ai_service import (
    AIServiceError,
    rank_optimization_candidates,
    recommend_optimization_policy,
)
from app.models import AIProviderConfigRecord
from app.schemas import (
    AIOrchestrationInfo,
    CandidateSummary,
    OptimizeRequest,
    OptimizeResponse,
    Order,
    Scenario,
)
from app.solver import solve_bidirectional_scenario, solve_scenario


STRATEGIES = ("balanced", "distance", "cost", "fleet")


def _solve_profile(
    scenario: Scenario,
    *,
    profile: str | None,
    time_limit_seconds: int,
    unavailable_vehicle_ids: set[str],
    extra_orders: list[Order],
    strategy: str,
    deterministic: bool = False,
) -> OptimizeResponse:
    solver = (
        solve_bidirectional_scenario
        if profile == "bidirectional-v2" or scenario.flow_profile == "bidirectional"
        else solve_scenario
    )
    return solver(
        scenario,
        time_limit_seconds=time_limit_seconds,
        unavailable_vehicle_ids=unavailable_vehicle_ids,
        extra_orders=extra_orders,
        strategy=strategy,
        deterministic=deterministic,
    )


def _scenario_summary(
    scenario: Scenario,
    *,
    unavailable_vehicle_ids: set[str],
    extra_orders: list[Order],
) -> dict:
    orders = [order for order in scenario.orders if not order.completed] + extra_orders
    available = [
        vehicle
        for vehicle in scenario.vehicles
        if vehicle.available and vehicle.id not in unavailable_vehicle_ids
    ]
    total_weight = sum(order.weight_kg for order in orders)
    cold_weight = sum(order.weight_kg for order in orders if order.cold_chain)
    urgent_count = sum(order.priority == "urgent" for order in orders)
    return {
        "scenario_id": scenario.id,
        "order_count": len(orders),
        "total_weight_kg": total_weight,
        "cold_chain_share_pct": round(cold_weight / max(1, total_weight) * 100, 1),
        "urgent_order_count": urgent_count,
        "available_vehicle_count": len(available),
        "cold_chain_vehicle_count": sum(vehicle.cold_chain for vehicle in available),
        "total_capacity_kg": sum(vehicle.capacity_kg for vehicle in available),
        "objective_guardrails": [
            "capacity",
            "cold_chain_compatibility",
            "time_windows",
            "vehicle_shifts",
        ],
    }


def _strategy_order(preferred: str, count: int) -> list[str]:
    ordered = [preferred, "balanced", "distance", "cost", "fleet"]
    unique: list[str] = []
    for strategy in ordered:
        if strategy in STRATEGIES and strategy not in unique:
            unique.append(strategy)
    return unique[:count]


def orchestrate_optimization(
    scenario: Scenario,
    request: OptimizeRequest,
    *,
    ai_config: AIProviderConfigRecord | None = None,
    unavailable_vehicle_ids: set[str] | None = None,
    extra_orders: list[Order] | None = None,
) -> OptimizeResponse:
    unavailable = unavailable_vehicle_ids or set()
    additional_orders = extra_orders or []
    if request.profile in {"standard-v1", "bidirectional-v2"}:
        selected = _solve_profile(
            scenario,
            profile=request.profile,
            time_limit_seconds=request.time_limit_seconds,
            unavailable_vehicle_ids=unavailable,
            extra_orders=additional_orders,
            strategy="balanced",
            deterministic=True,
        )
        selection_reason = (
            "标准运营基线 v1 已锁定 balanced 策略、路网快照与确定性搜索参数；"
            "AI 仅用于结果解释，不参与路线选择。"
            if request.profile == "standard-v1"
            else "双向运营场景 v2 已锁定 balanced 策略、取送货约束与确定性搜索参数；"
            "AI 仅用于结果解释，不参与路线选择。"
        )
        selected.candidate_summaries = [
            CandidateSummary(
                strategy="balanced",
                status=(
                    "infeasible" if selected.status == "infeasible" else "feasible"
                ),
                score=selected.decision_score.total if selected.decision_score else 0,
                distance_km=selected.metrics.distance_km,
                estimated_cost_cny=selected.metrics.estimated_cost_cny,
                vehicles_used=selected.metrics.vehicles_used,
                unassigned_orders=len(selected.unassigned_order_ids),
                selected=True,
            )
        ]
        selected.ai_orchestration = AIOrchestrationInfo(
            requested=request.ai_assisted,
            used=False,
            provider=ai_config.provider if ai_config else None,
            model_name=ai_config.model_name if ai_config else None,
            recommended_strategy="balanced",
            selection_reason=selection_reason,
            candidate_count=1,
            stages=[],
        )
        selected.explanations.insert(0, selection_reason)
        return selected

    ai_info = AIOrchestrationInfo(
        requested=request.ai_assisted,
        provider=ai_config.provider if ai_config else None,
        model_name=ai_config.model_name if ai_config else None,
        candidate_count=request.candidate_count,
    )
    preferred = request.strategy if request.strategy != "auto" else "balanced"
    policy_reason = "使用系统默认的均衡策略。"
    risk_flags: list[str] = []

    if request.ai_assisted and ai_config:
        try:
            recommendation, _ = recommend_optimization_policy(
                ai_config,
                _scenario_summary(
                    scenario,
                    unavailable_vehicle_ids=unavailable,
                    extra_orders=additional_orders,
                ),
            )
            preferred = recommendation["strategy"]
            policy_reason = recommendation["reason"] or "AI 已完成策略建议。"
            risk_flags = recommendation["risk_flags"]
            ai_info.used = True
            ai_info.stages.append("policy_recommendation")
            ai_info.recommended_strategy = preferred
        except AIServiceError as exc:
            ai_info.fallback_reason = f"AI 策略建议失败，已确定性降级：{exc}"
    elif request.ai_assisted:
        ai_info.fallback_reason = "未启用可用的 AI 服务，已使用确定性策略。"

    strategies = _strategy_order(preferred, request.candidate_count)
    per_candidate_seconds = max(1, request.time_limit_seconds // len(strategies))
    candidates = [
        _solve_profile(
            scenario,
            profile=request.profile,
            time_limit_seconds=per_candidate_seconds,
            unavailable_vehicle_ids=unavailable,
            extra_orders=additional_orders,
            strategy=strategy,
        )
        for strategy in strategies
    ]
    feasible = [
        (strategy, result)
        for strategy, result in zip(strategies, candidates, strict=True)
        if result.status != "infeasible"
    ]
    if not feasible:
        selected_strategy, selected = strategies[0], candidates[0]
    else:
        selected_strategy, selected = max(
            feasible,
            key=lambda item: (
                item[1].decision_score.total if item[1].decision_score else 0,
                -len(item[1].unassigned_order_ids),
                -item[1].metrics.distance_km,
            ),
        )

    selection_reason = (
        f"透明评分选择 {selected_strategy} 策略；{policy_reason}"
    )
    if request.ai_assisted and ai_config and len(feasible) > 1:
        rank_input = [
            {
                "strategy": strategy,
                "score": result.decision_score.total if result.decision_score else 0,
                "distance_km": result.metrics.distance_km,
                "estimated_cost_cny": result.metrics.estimated_cost_cny,
                "vehicles_used": result.metrics.vehicles_used,
                "unassigned_orders": len(result.unassigned_order_ids),
            }
            for strategy, result in feasible
        ]
        try:
            ranking, _ = rank_optimization_candidates(ai_config, rank_input)
            ai_choice = next(
                item
                for item in feasible
                if item[0] == ranking["selected_strategy"]
            )
            best_score = selected.decision_score.total if selected.decision_score else 0
            ai_score = (
                ai_choice[1].decision_score.total
                if ai_choice[1].decision_score
                else 0
            )
            if ai_score >= best_score - 5:
                selected_strategy, selected = ai_choice
                selection_reason = (
                    f"AI 在安全候选集中选择 {selected_strategy} 策略："
                    f"{ranking['reason'] or '综合业务目标更匹配'}"
                )
                ai_info.used = True
                ai_info.stages.append("candidate_review")
            else:
                suffix = "AI 推荐与透明最优评分差距超过 5 分，系统保留透明评分最优方案。"
                ai_info.fallback_reason = (
                    f"{ai_info.fallback_reason}；{suffix}"
                    if ai_info.fallback_reason
                    else suffix
                )
        except (AIServiceError, StopIteration) as exc:
            suffix = f"AI 候选复核失败，保留透明评分最优方案：{exc}"
            ai_info.fallback_reason = (
                f"{ai_info.fallback_reason}；{suffix}"
                if ai_info.fallback_reason
                else suffix
            )

    ai_info.selection_reason = selection_reason
    ai_info.candidate_count = len(candidates)
    selected.candidate_summaries = [
        CandidateSummary(
            strategy=strategy,
            status=(
                "infeasible" if result.status == "infeasible" else "feasible"
            ),
            score=result.decision_score.total if result.decision_score else 0,
            distance_km=result.metrics.distance_km,
            estimated_cost_cny=result.metrics.estimated_cost_cny,
            vehicles_used=result.metrics.vehicles_used,
            unassigned_orders=len(result.unassigned_order_ids),
            selected=strategy == selected_strategy,
        )
        for strategy, result in zip(strategies, candidates, strict=True)
    ]
    selected.ai_orchestration = ai_info
    selected.explanations.insert(0, selection_reason)
    if risk_flags:
        selected.explanations.append("AI 风险提示：" + "；".join(risk_flags))
    if ai_info.fallback_reason:
        selected.explanations.append(ai_info.fallback_reason)
    return selected
