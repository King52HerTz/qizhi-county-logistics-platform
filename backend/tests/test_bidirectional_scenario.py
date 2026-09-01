import pytest

from app.data.bidirectional_scenario import (
    BIDIRECTIONAL_DEMO_LOAD_RATIO,
    BIDIRECTIONAL_SCENARIO_ID,
    build_bidirectional_orders,
    get_bidirectional_scenario,
)
from app.data.scenario import get_scenario


def test_bidirectional_scenario_is_deterministic_and_balanced() -> None:
    first = get_bidirectional_scenario()
    second = get_bidirectional_scenario()
    assert first.id == BIDIRECTIONAL_SCENARIO_ID
    assert first.flow_profile == "bidirectional"
    assert len(first.orders) == 32
    assert [order.model_dump() for order in first.orders] == [
        order.model_dump() for order in second.orders
    ]
    assert sum(order.flow_direction == "upward" for order in first.orders) == 16
    assert sum(order.flow_direction == "downward" for order in first.orders) == 16
    assert sum(order.weight_kg for order in first.orders) == 9666
    assert sum(order.weight_kg for order in first.orders if order.flow_direction == "upward") == 5481
    assert sum(order.weight_kg for order in first.orders if order.flow_direction == "downward") == 4185
    assert BIDIRECTIONAL_DEMO_LOAD_RATIO < 0.001


def test_bidirectional_orders_keep_origin_and_destination() -> None:
    orders = build_bidirectional_orders(get_scenario().orders)
    for order in orders:
        assert order.origin_node_id
        assert order.destination_node_id
        if order.flow_direction == "upward":
            assert order.origin_node_id == order.node_id
            assert order.destination_node_id == "P-HUANG"
        else:
            assert order.origin_node_id == "D-01"
            assert order.destination_node_id == order.node_id
    assert all(order.window_end > order.window_start for order in orders)
    assert sum(order.cold_chain for order in orders if order.flow_direction == "downward") == 0
