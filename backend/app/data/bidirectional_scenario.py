"""Deterministic operational scenario for the county bidirectional flow."""

from __future__ import annotations

from app.data.bidirectional_reference import township_summary
from app.data.qidong_reference import (
    COLD_CHAIN_TOWNS,
    REFERENCE_ORDER_TOWN_ALLOCATIONS,
)
from app.data.scenario import get_scenario
from app.schemas import Order, Scenario


BIDIRECTIONAL_SCENARIO_ID = "qidong-bidirectional-v2"
BIDIRECTIONAL_SCENARIO_NAME = "祁东县农产品上行与工业品下行双向配送场景"

# The source workbooks describe annual demand, not same-day dispatch volume.
# This deterministic ratio produces a 9–10 tonne operational sample for the
# existing five-vehicle fleet while retaining the source totals in the facts
# layer.  It is deliberately separate from the legacy standard-v1 ratio.
BIDIRECTIONAL_DEMO_LOAD_RATIO = 0.000008


def _town_demand() -> dict[str, dict[str, float]]:
    return {
        str(item["town_name"]): {
            "upward": float(item["upward_tons"]),
            "downward": float(item["downward_tons"]),
        }
        for item in township_summary()
    }


def _mapped_weight(
    node_id: str,
    direction: str,
    demand_by_town: dict[str, dict[str, float]],
) -> int:
    allocations = REFERENCE_ORDER_TOWN_ALLOCATIONS.get(node_id, {})
    aggregate_tons = sum(
        demand_by_town[town][direction] * share
        for town, share in allocations.items()
    )
    return max(60, round(aggregate_tons * 1000 * BIDIRECTIONAL_DEMO_LOAD_RATIO))


def build_bidirectional_orders(standard_orders: list[Order]) -> list[Order]:
    demand_by_town = _town_demand()
    orders: list[Order] = []
    for order in standard_orders:
        allocations = REFERENCE_ORDER_TOWN_ALLOCATIONS.get(order.node_id)
        if not allocations:
            continue
        cold_chain = any(town in COLD_CHAIN_TOWNS for town in allocations)
        common = {
            "window_start": 0,
            "window_end": 600,
            "service_minutes": 10,
            "priority": "normal",
        }
        orders.append(
            Order(
                id=f"UP-{order.id.removeprefix('O-')}",
                node_id=order.node_id,
                weight_kg=_mapped_weight(order.node_id, "upward", demand_by_town),
                cold_chain=cold_chain,
                flow_direction="upward",
                cargo_category="agricultural",
                origin_node_id=order.node_id,
                destination_node_id="P-HUANG",
                **common,
            )
        )
        orders.append(
            Order(
                id=f"DOWN-{order.id.removeprefix('O-')}",
                node_id=order.node_id,
                weight_kg=_mapped_weight(order.node_id, "downward", demand_by_town),
                cold_chain=False,
                flow_direction="downward",
                cargo_category="industrial",
                origin_node_id="D-01",
                destination_node_id=order.node_id,
                **common,
            )
        )
    return orders


def get_bidirectional_scenario() -> Scenario:
    standard = get_scenario()
    return standard.model_copy(
        deep=True,
        update={
            "id": BIDIRECTIONAL_SCENARIO_ID,
            "name": BIDIRECTIONAL_SCENARIO_NAME,
            "orders": build_bidirectional_orders(standard.orders),
            "flow_profile": "bidirectional",
            "spatial_snapshot_id": "spatial-bidirectional-20260823",
        },
    )
