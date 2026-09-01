from app.schemas import Order, Scenario


def test_legacy_order_defaults_remain_backward_compatible() -> None:
    order = Order(
        id="O-LEGACY",
        node_id="V-001",
        weight_kg=100,
        window_start=0,
        window_end=120,
    )
    assert order.flow_direction == "downward"
    assert order.cargo_category == "agricultural"
    assert order.origin_node_id is None
    assert order.destination_node_id is None


def test_scenario_flow_profile_defaults_to_standard() -> None:
    payload = {
        "id": "demo",
        "name": "测试场景",
        "nodes": [],
        "orders": [],
        "vehicles": [],
    }
    assert Scenario.model_validate(payload).flow_profile == "standard"
