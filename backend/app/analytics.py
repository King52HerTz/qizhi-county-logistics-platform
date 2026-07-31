from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import ceil
from statistics import mean
from typing import Iterable

from app.schemas import DemandForecast, ForecastPoint, Scenario, TownshipDemand


WEEKDAY_FACTORS = (0.94, 0.98, 1.02, 1.06, 1.12, 0.91, 0.86)
RECENT_FACTORS = (0.88, 0.96, 1.04, 0.93, 1.08, 1.02, 0.97)
ML_MIN_HISTORY_DAYS = 28
FEATURE_NAMES = [
    "day_of_week",
    "month",
    "day_of_month",
    "lag_1",
    "lag_7",
    "rolling_mean_7",
    "trend_index",
]


def _normalized_history(
    observations: Iterable[tuple[date, float]],
) -> list[tuple[date, float]]:
    daily: dict[date, float] = {}
    for observed_date, tons in observations:
        daily[observed_date] = daily.get(observed_date, 0.0) + max(0.0, float(tons))
    if not daily:
        return []
    current = min(daily)
    end = max(daily)
    normalized: list[tuple[date, float]] = []
    while current <= end:
        normalized.append((current, round(daily.get(current, 0.0), 3)))
        current += timedelta(days=1)
    return normalized


def _feature_row(
    target_date: date,
    values: list[float],
    trend_index: int,
) -> list[float]:
    return [
        target_date.weekday(),
        target_date.month,
        target_date.day,
        values[-1],
        values[-7],
        mean(values[-7:]),
        trend_index,
    ]


def _ml_forecast(
    history: list[tuple[date, float]],
    horizon_days: int,
) -> tuple[list[float], float]:
    from xgboost import XGBRegressor

    values = [value for _, value in history]
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(7, len(history)):
        features.append(_feature_row(history[index][0], values[:index], index))
        targets.append(values[index])
    validation_size = max(5, min(14, len(targets) // 4))
    split = len(targets) - validation_size
    if split < 10:
        raise ValueError("可训练窗口不足")
    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=400,
        learning_rate=0.04,
        max_depth=3,
        subsample=0.85,
        colsample_bytree=0.9,
        reg_lambda=1.5,
        random_state=42,
        n_jobs=2,
        early_stopping_rounds=25,
    )
    model.fit(
        features[:split],
        targets[:split],
        eval_set=[(features[split:], targets[split:])],
        verbose=False,
    )
    validation_predictions = model.predict(features[split:])
    validation_mae = mean(
        abs(float(prediction) - actual)
        for prediction, actual in zip(
            validation_predictions,
            targets[split:],
            strict=True,
        )
    )
    rolling_values = list(values)
    predictions: list[float] = []
    last_date = history[-1][0]
    for offset in range(1, horizon_days + 1):
        target_date = last_date + timedelta(days=offset)
        prediction = max(
            0.05,
            float(
                model.predict(
                    [_feature_row(target_date, rolling_values, len(rolling_values))]
                )[0]
            ),
        )
        predictions.append(round(prediction, 2))
        rolling_values.append(prediction)
    return predictions, round(validation_mae, 3)


def _seasonal_baseline(
    base_tons: float,
    today: date,
    horizon_days: int,
) -> list[float]:
    recent = [
        base_tons
        * WEEKDAY_FACTORS[(today + timedelta(days=offset)).weekday()]
        * RECENT_FACTORS[offset + 6]
        for offset in range(-6, 1)
    ]
    weighted_average = sum(
        value * weight
        for value, weight in zip(
            recent[-4:],
            (0.1, 0.2, 0.3, 0.4),
            strict=True,
        )
    )
    return [
        round(
            weighted_average
            * WEEKDAY_FACTORS[(today + timedelta(days=offset)).weekday()]
            / WEEKDAY_FACTORS[today.weekday()],
            2,
        )
        for offset in range(horizon_days)
    ]


def build_demand_forecast(
    scenario: Scenario,
    horizon_days: int = 7,
    *,
    demand_history: Iterable[tuple[date, float]] = (),
) -> DemandForecast:
    today = date.today()
    base_tons = max(
        sum(order.weight_kg for order in scenario.orders) / 1000,
        0.1,
    )
    history = _normalized_history(demand_history)
    points = [
        ForecastPoint(date=observed_date.isoformat(), actual_tons=round(actual, 2))
        for observed_date, actual in history[-7:]
    ]

    method = "梯度提升时序回归"
    model_family = "XGBoostRegressor"
    validation_mae: float | None = None
    fallback_used = False
    fallback_reason: str | None = None
    if len(history) >= ML_MIN_HISTORY_DAYS:
        try:
            forecast_values, validation_mae = _ml_forecast(history, horizon_days)
        except (ImportError, ValueError, RuntimeError) as exc:
            forecast_values = _seasonal_baseline(base_tons, today, horizon_days)
            method = "星期季节基线"
            model_family = "deterministic-seasonal-baseline"
            fallback_used = True
            fallback_reason = (
                f"机器学习模型不可用：{type(exc).__name__}: {str(exc)[:120]}"
            )
    else:
        forecast_values = _seasonal_baseline(base_tons, today, horizon_days)
        method = "星期季节基线"
        model_family = "deterministic-seasonal-baseline"
        fallback_used = True
        fallback_reason = (
            f"真实历史仅 {len(history)} 天，少于机器学习最低要求 "
            f"{ML_MIN_HISTORY_DAYS} 天"
        )

    for offset, forecast in enumerate(forecast_values):
        current = today + timedelta(days=offset)
        spread = max(
            validation_mae or 0.18,
            forecast * (0.08 + offset * 0.006),
        )
        points.append(
            ForecastPoint(
                date=current.isoformat(),
                forecast_tons=forecast,
                lower_tons=round(max(0, forecast - spread), 2),
                upper_tons=round(forecast + spread, 2),
            )
        )

    node_names = {node.id: node.name for node in scenario.nodes}
    demand_by_node: dict[str, int] = {}
    for order in scenario.orders:
        demand_by_node[order.node_id] = (
            demand_by_node.get(order.node_id, 0) + order.weight_kg
        )
    total_weight = max(1, sum(demand_by_node.values()))
    ranking = [
        TownshipDemand(
            node_id=node_id,
            node_name=node_names.get(node_id, node_id),
            demand_tons=round(weight / 1000, 2),
            share=round(weight / total_weight * 100, 1),
        )
        for node_id, weight in sorted(
            demand_by_node.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ][:8]

    cold_ratio = (
        sum(order.weight_kg for order in scenario.orders if order.cold_chain)
        / max(1, sum(order.weight_kg for order in scenario.orders))
    )
    today_forecast = forecast_values[0]
    peak = max(forecast_values)
    peak_index = forecast_values.index(peak)
    usable_capacities = [
        vehicle.capacity_kg
        for vehicle in scenario.vehicles
        if vehicle.available
    ]
    average_capacity = sum(usable_capacities) / max(1, len(usable_capacities))
    recommended = min(
        len(usable_capacities),
        max(
            1,
            ceil(today_forecast * 1000 / max(1, average_capacity * 0.82)),
        ),
    )
    capacity_tons = sum(usable_capacities) / 1000
    peak_utilization = peak / max(0.1, capacity_tons)
    risk_level = (
        "high"
        if peak_utilization > 0.9
        else "medium"
        if peak_utilization > 0.72
        else "low"
    )
    return DemandForecast(
        scenario_id=scenario.id,
        generated_at=datetime.now(timezone.utc),
        horizon_days=horizon_days,
        method=method,
        history_basis=(
            f"数据库连续日需求序列，共 {len(history)} 天"
            if history
            else "当前数据库尚未形成连续真实日需求序列"
        ),
        model_family=model_family,
        training_samples=len(history),
        validation_mae_tons=validation_mae,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        feature_names=FEATURE_NAMES if not fallback_used else [],
        points=points,
        township_ranking=ranking,
        today_forecast_tons=today_forecast,
        peak_forecast_tons=peak,
        peak_date=(today + timedelta(days=peak_index)).isoformat(),
        cold_chain_tons=round(today_forecast * cold_ratio, 2),
        recommended_vehicles=recommended,
        risk_level=risk_level,
        notes=[
            "预测用于运营决策辅助，不替代实际订单承诺。",
            (
                "机器学习模型已按时间切分验证，未随机打乱历史序列。"
                if not fallback_used
                else fallback_reason or "当前使用确定性季节基线。"
            ),
            f"峰值日预计需求 {peak:.2f} 吨，建议提前锁定冷链运力。",
        ],
    )
