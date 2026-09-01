from collections import defaultdict

from app.data.bidirectional_scenario import get_bidirectional_scenario
from app.optimization_orchestrator import orchestrate_optimization
from app.schemas import OptimizeRequest
from app.solver import solve_bidirectional_scenario


def test_bidirectional_solver_serves_pickup_and_delivery_pairs() -> None:
    scenario = get_bidirectional_scenario()
    response = solve_bidirectional_scenario(
        scenario,
        time_limit_seconds=5,
        deterministic=True,
    )

    assert response.status == "feasible"
    assert response.solver == "ortools-pickup-delivery"
    assert response.unassigned_order_ids == []
    assert response.metrics.on_time_rate == 100
    assert response.routing.coordinate_count == 65

    order_by_id = {order.id: order for order in scenario.orders}
    occurrences: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    vehicle_by_id = {vehicle.id: vehicle for vehicle in scenario.vehicles}
    for route in response.routes:
        vehicle = vehicle_by_id[route.vehicle_id]
        assert route.load_kg <= vehicle.capacity_kg
        for position, stop in enumerate(route.stops):
            if stop.order_id is None:
                assert stop.action == "depot"
                continue
            occurrences[stop.order_id].append((position, route.cold_chain, stop.action))

    assert set(occurrences) == set(order_by_id)
    for order_id, stops in occurrences.items():
        assert len(stops) == 2
        pickup, delivery = sorted(stops)
        assert pickup[2] == "pickup"
        assert delivery[2] == "delivery"
        assert pickup[1] == delivery[1]
        if order_by_id[order_id].cold_chain:
            assert pickup[1] is True


def test_bidirectional_solver_reports_missing_nodes_without_crashing() -> None:
    scenario = get_bidirectional_scenario()
    broken = scenario.model_copy(
        deep=True,
        update={
            "orders": [
                scenario.orders[0].model_copy(update={"destination_node_id": "missing"})
            ]
        },
    )

    response = solve_bidirectional_scenario(broken, time_limit_seconds=1)

    assert response.status == "infeasible"
    assert response.unassigned_order_ids == [scenario.orders[0].id]
    assert "不存在的取送节点" in response.explanations[0]


def test_bidirectional_profile_uses_pickup_delivery_solver() -> None:
    response = orchestrate_optimization(
        get_bidirectional_scenario(),
        OptimizeRequest(
            profile="bidirectional-v2",
            strategy="balanced",
            ai_assisted=False,
            candidate_count=1,
            time_limit_seconds=5,
        ),
    )

    assert response.status == "feasible"
    assert response.solver == "ortools-pickup-delivery"
    assert response.candidate_summaries[0].selected is True
    assert response.ai_orchestration.used is False
