"""冷链仓储共享调度与全程温控监测预警服务。

模块边界：演示库容与温度读数均来自稳定演示样本和受控模拟数据流，
不代表实时库存或真实车载传感数据；预警只作为调度参考信号，
冷链订单与冷链车辆的硬约束仍由确定性求解器校验。
"""

from __future__ import annotations

import hashlib
import statistics
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ColdStoreBookingRecord,
    ColdStoreRecord,
    NodeRecord,
    TemperatureAlertRecord,
    TemperatureReadingRecord,
    TemperatureSensorRecord,
    VehicleRecord,
)
from app.schemas import (
    ColdStoreBookingCreate,
    ColdStoreView,
    TemperatureAlertView,
    TemperatureOverview,
    TemperatureReadingView,
    TemperatureSensorView,
)

MAX_READING_POINTS = 240
ANOMALY_WINDOW = 8
ANOMALY_TRIGGER_SIGMA = 2.5


class ColdStoreBookingError(ValueError):
    """共享预约参数或库容校验失败。"""


# ---------------------------------------------------------------------------
# 确定性扰动序列
# ---------------------------------------------------------------------------


def _deterministic_unit(seed: str, index: int) -> float:
    """由 SHA-256 摘要派生 [0, 1) 区间的确定性伪随机数。

    温度模拟曲线需要同一传感器多次模拟形态一致，因此使用摘要派生
    序列而不是随机模块；该序列仅用于演示扰动，不承担任何安全职责。
    """
    digest = hashlib.sha256(f"{seed}:{index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(0x1_0000_0000_0000_0000)


def _deterministic_range(seed: str, index: int, low: float, high: float) -> float:
    return low + (high - low) * _deterministic_unit(seed, index)


# ---------------------------------------------------------------------------
# 演示资产种子
# ---------------------------------------------------------------------------

_DEMO_COLD_STORES = [
    ("CS-01", "祁东县冷链共享中心库", "county_hub", "D-01", "chilled", 800, "0734-6300001"),
    ("CS-02", "祁东县冷链共享中心库（冷冻区）", "county_hub", "D-01", "frozen", 400, "0734-6300001"),
    ("CS-03", "黄土铺黄花菜预冷共享库", "township", "P-HUANG", "chilled", 120, "0734-6300002"),
    ("CS-04", "砖塘镇村级共配冷存点", "field_precool", "V-001", "chilled", 30, "0734-6300003"),
    ("CS-05", "河洲镇村级共配冷存点", "field_precool", "V-003", "chilled", 30, "0734-6300004"),
    ("CS-06", "石亭子镇村级共配冷存点", "field_precool", "V-006", "ambient", 20, "0734-6300005"),
]

_VEHICLE_TARGET_RANGES = {
    "refrigerated": (Decimal("0.0"), Decimal("4.0")),
    "truck": (Decimal("0.0"), Decimal("4.0")),
    "van": (Decimal("2.0"), Decimal("8.0")),
}


def ensure_demo_assets(session: Session) -> None:
    """幂等补种冷链演示资产：共享冷库台账与温控采集点。

    冷库绑定标准场景节点；传感器一部分挂在冷库，一部分挂接冷链车辆。
    演示重置会清空这些表，下一次启动或页面访问时自动恢复。
    """
    existing_stores = session.scalar(select(func.count()).select_from(ColdStoreRecord)) or 0
    if existing_stores == 0:
        node_ids = set(session.scalars(select(NodeRecord.id)))
        for store_id, name, store_type, node_id, zone, capacity, contact in _DEMO_COLD_STORES:
            session.add(
                ColdStoreRecord(
                    id=store_id,
                    name=name,
                    store_type=store_type,
                    node_id=node_id if node_id in node_ids else None,
                    temperature_zone=zone,
                    capacity_tons=capacity,
                    shared=True,
                    contact=contact,
                    status="active",
                    remark="演示样本：库容来自研究资料汇总口径，非实时库存",
                )
            )
        # Session 配置为 autoflush=False，先显式刷新，保证下方按库建传感器可见。
        session.flush()

    existing_sensors = session.scalar(select(func.count()).select_from(TemperatureSensorRecord)) or 0
    if existing_sensors == 0:
        stores = session.scalars(select(ColdStoreRecord)).all()
        for store in stores:
            low, high = (
                (Decimal("-2.0"), Decimal("2.0"))
                if store.temperature_zone == "frozen"
                else (Decimal("0.0"), Decimal("4.0"))
            )
            session.add(
                TemperatureSensorRecord(
                    id=f"TS-{store.id}",
                    name=f"{store.name}·库内测温",
                    sensor_type="storage",
                    cold_store_id=store.id,
                    target_low_c=low,
                    target_high_c=high,
                    status="active",
                )
            )
        cold_vehicles = session.scalars(
            select(VehicleRecord).where(VehicleRecord.cold_chain.is_(True))
        ).all()
        for index, vehicle in enumerate(cold_vehicles, start=1):
            low, high = _VEHICLE_TARGET_RANGES.get(
                vehicle.vehicle_type, (Decimal("0.0"), Decimal("4.0"))
            )
            session.add(
                TemperatureSensorRecord(
                    id=f"TS-VEH-{index:02d}",
                    name=f"{vehicle.plate}·车载温控",
                    sensor_type="vehicle",
                    vehicle_id=vehicle.id,
                    target_low_c=low,
                    target_high_c=high,
                    status="active",
                )
            )
    session.commit()


# ---------------------------------------------------------------------------
# 冷链仓储共享调度
# ---------------------------------------------------------------------------


def _booking_tons_for_date(session: Session, cold_store_id: str, booking_date: str) -> Decimal:
    rows = session.scalars(
        select(ColdStoreBookingRecord.tons)
        .filter_by(cold_store_id=cold_store_id, booking_date=booking_date)
        .filter(ColdStoreBookingRecord.status.in_(("reserved", "active")))
    ).all()
    return sum((Decimal(value) for value in rows), Decimal("0"))


def _latest_reading(session: Session, sensor_id: str) -> TemperatureReadingRecord | None:
    return session.scalar(
        select(TemperatureReadingRecord)
        .filter_by(sensor_id=sensor_id)
        .order_by(TemperatureReadingRecord.recorded_at.desc())
        .limit(1)
    )


def _cold_store_view(session: Session, store: ColdStoreRecord) -> ColdStoreView:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    booked = _booking_tons_for_date(session, store.id, today)
    latest_reading = _latest_reading(session, f"TS-{store.id}")
    return ColdStoreView(
        id=store.id,
        name=store.name,
        store_type=store.store_type,
        node_id=store.node_id,
        node_name=store.node.name if store.node else None,
        temperature_zone=store.temperature_zone,
        capacity_tons=store.capacity_tons,
        booked_tons=float(booked),
        available_tons=float(max(Decimal(store.capacity_tons) - booked, Decimal("0"))),
        shared=store.shared,
        contact=store.contact,
        status=store.status,
        remark=store.remark,
        latest_temperature_c=float(latest_reading.temperature_c) if latest_reading else None,
        latest_recorded_at=latest_reading.recorded_at if latest_reading else None,
    )


def list_cold_stores(session: Session) -> list[ColdStoreView]:
    stores = session.scalars(select(ColdStoreRecord).order_by(ColdStoreRecord.id)).all()
    return [_cold_store_view(session, store) for store in stores]


def list_bookings(session: Session, limit: int = 50) -> list[dict]:
    rows = session.scalars(
        select(ColdStoreBookingRecord)
        .order_by(ColdStoreBookingRecord.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    items = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "cold_store_id": row.cold_store_id,
                "cold_store_name": row.cold_store.name if row.cold_store else row.cold_store_id,
                "order_id": row.order_id,
                "booking_date": row.booking_date,
                "purpose": row.purpose,
                "tons": float(row.tons),
                "status": row.status,
                "note": row.note,
                "created_by": row.created_by,
                "created_at": row.created_at,
            }
        )
    return items


def create_booking(
    session: Session, payload: ColdStoreBookingCreate, actor_username: str | None
) -> dict:
    store = session.get(ColdStoreRecord, payload.cold_store_id)
    if store is None or store.status != "active":
        raise ColdStoreBookingError("冷库不存在或未启用共享")
    if store.temperature_zone == "ambient" and payload.purpose != "transit":
        raise ColdStoreBookingError("常温存点仅支持中转占库")
    booked = _booking_tons_for_date(session, store.id, payload.booking_date)
    if booked + Decimal(str(payload.tons)) > Decimal(store.capacity_tons):
        raise ColdStoreBookingError("预约吨位超出该库当日剩余共享库容")
    row = ColdStoreBookingRecord(
        cold_store_id=store.id,
        order_id=payload.order_id,
        booking_date=payload.booking_date,
        purpose=payload.purpose,
        tons=Decimal(str(payload.tons)),
        status="reserved",
        note=payload.note,
        created_by=actor_username,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "id": row.id,
        "cold_store_id": row.cold_store_id,
        "cold_store_name": store.name,
        "order_id": row.order_id,
        "booking_date": row.booking_date,
        "purpose": row.purpose,
        "tons": float(row.tons),
        "status": row.status,
        "note": row.note,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# 全程温控监测与预警
# ---------------------------------------------------------------------------


def _sensor_view(
    sensor: TemperatureSensorRecord, latest: TemperatureReadingRecord | None
) -> TemperatureSensorView:
    return TemperatureSensorView(
        id=sensor.id,
        name=sensor.name,
        sensor_type=sensor.sensor_type,
        vehicle_id=sensor.vehicle_id,
        vehicle_plate=sensor.vehicle.plate if sensor.vehicle else None,
        cold_store_id=sensor.cold_store_id,
        cold_store_name=sensor.cold_store.name if sensor.cold_store else None,
        target_low_c=float(sensor.target_low_c),
        target_high_c=float(sensor.target_high_c),
        status=sensor.status,
        latest_temperature_c=float(latest.temperature_c) if latest else None,
        latest_recorded_at=latest.recorded_at if latest else None,
    )


def list_sensors(session: Session) -> list[TemperatureSensorView]:
    sensors = session.scalars(select(TemperatureSensorRecord).order_by(TemperatureSensorRecord.id)).all()
    latest_times = dict(
        session.execute(
            select(
                TemperatureReadingRecord.sensor_id,
                func.max(TemperatureReadingRecord.recorded_at),
            ).group_by(TemperatureReadingRecord.sensor_id)
        ).all()
    )
    latest_map: dict[str, TemperatureReadingRecord] = {}
    for sensor_id, recorded_at in latest_times.items():
        latest_map[sensor_id] = session.scalar(
            select(TemperatureReadingRecord).filter_by(sensor_id=sensor_id, recorded_at=recorded_at)
        )
    return [_sensor_view(sensor, latest_map.get(sensor.id)) for sensor in sensors]


def list_readings(session: Session, sensor_id: str, limit: int = 120) -> list[TemperatureReadingView]:
    limit = min(limit, MAX_READING_POINTS)
    rows = session.scalars(
        select(TemperatureReadingRecord)
        .filter_by(sensor_id=sensor_id)
        .order_by(TemperatureReadingRecord.recorded_at.desc())
        .limit(limit)
    ).all()
    rows.reverse()
    return [
        TemperatureReadingView(
            sensor_id=row.sensor_id,
            recorded_at=row.recorded_at,
            temperature_c=float(row.temperature_c),
            humidity_pct=float(row.humidity_pct) if row.humidity_pct is not None else None,
            context=row.context,
        )
        for row in rows
    ]


def _alert_view(alert: TemperatureAlertRecord) -> TemperatureAlertView:
    return TemperatureAlertView(
        id=alert.id,
        sensor_id=alert.sensor_id,
        reading_id=alert.reading_id,
        level=alert.level,
        alert_type=alert.alert_type,
        message=alert.message,
        measured_c=float(alert.measured_c) if alert.measured_c is not None else None,
        threshold_c=float(alert.threshold_c) if alert.threshold_c is not None else None,
        deviation_c=float(alert.deviation_c) if alert.deviation_c is not None else None,
        status=alert.status,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        created_at=alert.created_at,
    )


def list_alerts(session: Session, status: str | None = None, limit: int = 80) -> list[TemperatureAlertView]:
    query = select(TemperatureAlertRecord).order_by(TemperatureAlertRecord.created_at.desc())
    if status in ("open", "acknowledged", "resolved"):
        query = query.filter_by(status=status)
    rows = session.scalars(query.limit(min(limit, 200))).all()
    return [_alert_view(row) for row in rows]


def acknowledge_alert(session: Session, alert_id: int, actor_username: str) -> TemperatureAlertView | None:
    alert = session.get(TemperatureAlertRecord, alert_id)
    if alert is None:
        return None
    if alert.status == "open":
        alert.status = "acknowledged"
        alert.acknowledged_by = actor_username
        alert.acknowledged_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(alert)
    return _alert_view(alert)


def temperature_overview(session: Session) -> TemperatureOverview:
    sensor_total = session.scalar(select(func.count()).select_from(TemperatureSensorRecord)) or 0
    active_sensors = (
        session.scalar(
            select(func.count())
            .select_from(TemperatureSensorRecord)
            .where(TemperatureSensorRecord.status == "active")
        )
        or 0
    )
    reading_total = session.scalar(select(func.count()).select_from(TemperatureReadingRecord)) or 0
    open_alerts = (
        session.scalar(
            select(func.count())
            .select_from(TemperatureAlertRecord)
            .where(TemperatureAlertRecord.status == "open")
        )
        or 0
    )
    critical_alerts = (
        session.scalar(
            select(func.count())
            .select_from(TemperatureAlertRecord)
            .where(TemperatureAlertRecord.status == "open", TemperatureAlertRecord.level == "critical")
        )
        or 0
    )
    stores = session.scalar(select(func.count()).select_from(ColdStoreRecord)) or 0
    return TemperatureOverview(
        sensor_total=sensor_total,
        active_sensors=active_sensors,
        reading_total=reading_total,
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        shared_stores=stores,
    )


def _anomaly_score(window: list[float], value: float) -> float | None:
    """滚动残差 z 分数：对最近窗口均值/方差的偏离程度。

    这是统计学习基线；样本量达到门槛后可替换为时序模型，
    训练样本门槛与时间切分验证复用需求预测模块已有的门控约定。
    """
    if len(window) < 6:
        return None
    mean = statistics.fmean(window)
    stdev = statistics.pstdev(window)
    if stdev < 1e-6:
        return None
    return abs(value - mean) / stdev


def simulate_temperature_stream(session: Session, hours: int = 6) -> dict:
    """为全部启用传感器生成近 N 小时的演示温度曲线并评估预警。

    扰动序列由传感器 ID 经 SHA-256 摘要派生，同一传感器多次模拟
    形态一致；其中一台冷链车会经历一段可控升温过程，用于完整展示
    "阈值越限 + 趋势异常"两类预警与后续处置闭环。演示数据不代表
    真实车载或库内传感读数。
    """
    hours = max(1, min(int(hours), 48))
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    step_minutes = 20
    points = int(hours * 60 // step_minutes)
    sensors = session.scalars(
        select(TemperatureSensorRecord).where(TemperatureSensorRecord.status == "active")
    ).all()
    created_readings = 0
    created_alerts = 0

    for sensor in sensors:
        low, high = float(sensor.target_low_c), float(sensor.target_high_c)
        span = high - low
        last_recorded = session.scalar(
            select(TemperatureReadingRecord.recorded_at)
            .filter_by(sensor_id=sensor.id)
            .order_by(TemperatureReadingRecord.recorded_at.desc())
            .limit(1)
        )
        start_index = 0
        if last_recorded is not None:
            # SQLite 测试库返回 naive 时间，统一按 UTC 对齐后再计算间隔。
            last_at = (
                last_recorded if last_recorded.tzinfo else last_recorded.replace(tzinfo=timezone.utc)
            )
            elapsed = (now - last_at).total_seconds() / 60
            start_index = int(elapsed // step_minutes) + 1
        if start_index >= points:
            continue

        base_context = "storage" if sensor.sensor_type == "storage" else "in_transit"
        values: list[float] = []
        window: list[float] = []
        excite = sensor.id == "TS-VEH-01"
        for index in range(start_index, points):
            recorded_at = now - timedelta(minutes=step_minutes * (points - 1 - index))
            ratio = index / points if points else 0.0
            if excite and 0.55 <= ratio <= 0.8:
                # 受控升温段：从目标区间爬升并越过上限，触发越限与趋势预警。
                progress = (ratio - 0.55) / 0.25
                base = high + span * 0.9 * progress + _deterministic_range(
                    f"{sensor.id}-excursion", index, -0.2, 0.3
                )
                context = "in_transit"
            else:
                base = _deterministic_range(
                    f"{sensor.id}-base", index, low + span * 0.15, high - span * 0.1
                )
                context = base_context
            temperature = round(base, 2)
            window.append(temperature)
            values.append(temperature)
            humidity = _deterministic_range(f"{sensor.id}-humidity", index, 60.0, 90.0)
            reading = TemperatureReadingRecord(
                sensor_id=sensor.id,
                recorded_at=recorded_at,
                temperature_c=Decimal(str(temperature)),
                humidity_pct=Decimal(str(round(humidity, 1))),
                context=context,
            )
            session.add(reading)
            created_readings += 1
            session.flush()

            low_breach = temperature < low
            high_breach = temperature > high
            if low_breach or high_breach:
                threshold = low if low_breach else high
                deviation = abs(temperature - threshold)
                level = "critical" if deviation > span * 0.5 + 1.0 else "warning"
                direction = "低于下限" if low_breach else "高于上限"
                session.add(
                    TemperatureAlertRecord(
                        sensor_id=sensor.id,
                        reading_id=reading.id,
                        level=level,
                        alert_type="threshold_breach",
                        message=(
                            f"{sensor.name} 温度 {temperature}℃ {direction}目标区间 [{low}, {high}]℃"
                        ),
                        measured_c=Decimal(str(temperature)),
                        threshold_c=Decimal(str(threshold)),
                        deviation_c=Decimal(str(round(deviation, 2))),
                        status="open",
                    )
                )
                created_alerts += 1
            else:
                score = _anomaly_score(window[-ANOMALY_WINDOW:], temperature)
                if score is not None and score > ANOMALY_TRIGGER_SIGMA and len(values) >= 2:
                    rising = temperature > values[-2]
                    session.add(
                        TemperatureAlertRecord(
                            sensor_id=sensor.id,
                            reading_id=reading.id,
                            level="info",
                            alert_type="anomaly_trend",
                            message=(
                                f"{sensor.name} 温度变化速率异常（滚动残差 {score:.1f}σ），"
                                f"{'升温' if rising else '降温'}趋势建议提前复核制冷设备"
                            ),
                            measured_c=Decimal(str(temperature)),
                            deviation_c=Decimal(str(round(score, 2))),
                            status="open",
                        )
                    )
                    created_alerts += 1

    session.commit()
    return {
        "sensors": len(sensors),
        "readings_created": created_readings,
        "alerts_created": created_alerts,
        "window_hours": hours,
        "note": "演示温度数据由受控模拟过程生成，不代表真实车载或库内传感读数",
    }
