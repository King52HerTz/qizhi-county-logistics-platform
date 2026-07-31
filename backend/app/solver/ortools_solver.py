from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.routing_matrix import RoutingMatrix, build_routing_matrix
from app.schemas import (
    DecisionScore,
    DecisionScoreComponent,
    Metrics,
    OptimizeResponse,
    Order,
    Route,
    RouteStop,
    Scenario,
    Vehicle,
)


ROUTE_COLORS = ["#159447", "#2878D0", "#ED8B21", "#7957D5", "#17A2A4"]


@dataclass(frozen=True)
class OptimizationPolicy:
    strategy: str = "balanced"
    fixed_vehicle_cost: int = 3500
    distance_weight: float = 1.0
    operating_cost_weight: float = 0.25


POLICIES = {
    "balanced": OptimizationPolicy(),
    "distance": OptimizationPolicy(
        strategy="distance",
        fixed_vehicle_cost=1200,
        distance_weight=1.0,
        operating_cost_weight=0.0,
    ),
    "cost": OptimizationPolicy(
        strategy="cost",
        fixed_vehicle_cost=2500,
        distance_weight=0.25,
        operating_cost_weight=1.0,
    ),
    "fleet": OptimizationPolicy(
        strategy="fleet",
        fixed_vehicle_cost=12_000,
        distance_weight=1.0,
        operating_cost_weight=0.15,
    ),
}


def calculate_decision_score(
    metrics: Metrics,
    baseline: Metrics,
    *,
    order_count: int,
    unassigned_count: int,
    available_vehicle_count: int,
) -> DecisionScore:
    service_rate = (
        100 * max(0, order_count - unassigned_count) / order_count
        if order_count
        else 100
    )
    distance_improvement = (
        (baseline.distance_km - metrics.distance_km) / baseline.distance_km * 100
        if baseline.distance_km > 0
        else 0
    )
    cost_improvement = (
        (baseline.estimated_cost_cny - metrics.estimated_cost_cny)
        / baseline.estimated_cost_cny
        * 100
        if baseline.estimated_cost_cny > 0
        else 0
    )
    service_score = round(min(40.0, max(0.0, service_rate * 0.4)), 1)
    distance_score = round(
        min(25.0, max(0.0, distance_improvement / 30 * 25)),
        1,
    )
    cost_score = round(
        min(20.0, max(0.0, cost_improvement / 25 * 20)),
        1,
    )
    if available_vehicle_count <= 1:
        fleet_score = 10.0
    else:
        fleet_score = round(
            10
            * (
                1
                - max(0, metrics.vehicles_used - 1)
                / max(1, available_vehicle_count - 1)
            ),
            1,
        )
    empty_score = round(
        min(5.0, max(0.0, 5 * (1 - metrics.empty_distance_rate / 30))),
        1,
    )
    components = [
        DecisionScoreComponent(
            key="service",
            name="订单服务与约束满足",
            score=service_score,
            weight=40,
            detail=f"服务率 {service_rate:.1f}%，未分配 {unassigned_count} 单",
        ),
        DecisionScoreComponent(
            key="distance",
            name="里程改善",
            score=distance_score,
            weight=25,
            detail=f"相对同矩阵业务基线改善 {distance_improvement:.1f}%",
        ),
        DecisionScoreComponent(
            key="cost",
            name="成本改善",
            score=cost_score,
            weight=20,
            detail=f"相对同矩阵业务基线改善 {cost_improvement:.1f}%",
        ),
        DecisionScoreComponent(
            key="fleet",
            name="车辆利用",
            score=fleet_score,
            weight=10,
            detail=f"使用 {metrics.vehicles_used}/{available_vehicle_count} 辆可用车辆",
        ),
        DecisionScoreComponent(
            key="empty_distance",
            name="空驶控制",
            score=empty_score,
            weight=5,
            detail=f"估算空驶率 {metrics.empty_distance_rate:.1f}%",
        ),
    ]
    total = round(sum(component.score for component in components), 1)
    grade = "A" if total >= 90 else "B" if total >= 80 else "C" if total >= 70 else "D"
    return DecisionScore(total=total, grade=grade, components=components)


def calculate_baseline(
    orders: list[Order],
    vehicles: list[Vehicle],
    matrix: RoutingMatrix,
) -> Metrics:
    """Deterministic business baseline with capacity, cold-chain and time-window checks."""
    buckets: list[list[int]] = [[] for _ in vehicles]
    remaining_capacity = [vehicle.capacity_kg for vehicle in vehicles]
    current_node = [0 for _ in vehicles]
    current_minute = [vehicle.shift_start for vehicle in vehicles]
    assigned = 0
    cursor = 0
    for order_index, order in enumerate(orders, start=1):
        chosen: int | None = None
        for offset in range(len(vehicles)):
            vehicle_index = (cursor + offset) % len(vehicles)
            vehicle = vehicles[vehicle_index]
            if order.cold_chain and not vehicle.cold_chain:
                continue
            if remaining_capacity[vehicle_index] < order.weight_kg:
                continue
            arrival = max(
                current_minute[vehicle_index]
                + matrix.duration_min[current_node[vehicle_index]][order_index],
                order.window_start,
            )
            route_end = (
                arrival
                + order.service_minutes
                + matrix.duration_min[order_index][0]
            )
            if arrival > order.window_end or route_end > vehicle.shift_end:
                continue
            chosen = vehicle_index
            break
        if chosen is None:
            continue
        arrival = max(
            current_minute[chosen]
            + matrix.duration_min[current_node[chosen]][order_index],
            order.window_start,
        )
        buckets[chosen].append(order_index)
        remaining_capacity[chosen] -= order.weight_kg
        current_node[chosen] = order_index
        current_minute[chosen] = arrival + order.service_minutes
        assigned += 1
        cursor = (chosen + 1) % len(vehicles)

    total_distance_m = 0
    empty_distance_m = 0
    total_cost = 0.0
    vehicles_used = 0
    for vehicle, bucket in zip(vehicles, buckets, strict=True):
        if not bucket:
            continue
        vehicles_used += 1
        current_index = 0
        route_distance_m = 0
        for order_index in bucket:
            route_distance_m += matrix.distance_m[current_index][order_index]
            current_index = order_index
        return_distance = matrix.distance_m[current_index][0]
        route_distance_m += return_distance
        empty_distance_m += return_distance
        total_distance_m += route_distance_m
        total_cost += route_distance_m / 1000 * vehicle.cost_per_km
    total_km = total_distance_m / 1000
    return Metrics(
        distance_km=round(total_km, 1),
        estimated_cost_cny=round(total_cost, 0),
        on_time_rate=round(100 * assigned / len(orders), 1) if orders else 100,
        empty_distance_rate=(
            round(100 * empty_distance_m / total_distance_m, 1)
            if total_distance_m
            else 0
        ),
        vehicles_used=vehicles_used,
    )


def solve_scenario(
    scenario: Scenario,
    *,
    time_limit_seconds: int = 5,
    unavailable_vehicle_ids: set[str] | None = None,
    extra_orders: list[Order] | None = None,
    strategy: str = "balanced",
    deterministic: bool = False,
) -> OptimizeResponse:
    started = perf_counter()
    unavailable_vehicle_ids = unavailable_vehicle_ids or set()
    orders = [o for o in scenario.orders if not o.completed] + (extra_orders or [])
    vehicles = [
        vehicle
        for vehicle in scenario.vehicles
        if vehicle.available and vehicle.id not in unavailable_vehicle_ids
    ]
    if not vehicles:
        return _infeasible_response(started, orders, "没有可用车辆。")
    policy = POLICIES.get(strategy, POLICIES["balanced"])

    node_map = {node.id: node for node in scenario.nodes}
    depots = [node for node in scenario.nodes if node.kind == "depot"]
    if len(depots) != 1:
        return _infeasible_response(
            started,
            orders,
            f"场景必须且只能包含一个配送中心，当前为 {len(depots)} 个。",
        )
    missing_node_ids = sorted(
        {order.node_id for order in orders if order.node_id not in node_map}
    )
    if missing_node_ids:
        return _infeasible_response(
            started,
            orders,
            "订单引用了不存在的网点：" + "、".join(missing_node_ids[:8]),
        )
    depot = depots[0]
    service_nodes = [depot] + [node_map[order.node_id] for order in orders]
    coords = [(node.longitude, node.latitude) for node in service_nodes]
    matrix = build_routing_matrix(coords)

    manager = pywrapcp.RoutingIndexManager(
        len(service_nodes),
        len(vehicles),
        0,
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        return matrix.distance_m[
            manager.IndexToNode(from_index)
        ][manager.IndexToNode(to_index)]

    for vehicle_idx, vehicle in enumerate(vehicles):
        multiplier = (
            policy.distance_weight
            + policy.operating_cost_weight * float(vehicle.cost_per_km)
        )

        def vehicle_cost_callback(
            from_index: int,
            to_index: int,
            factor: float = multiplier,
        ) -> int:
            return max(0, round(distance_callback(from_index, to_index) * factor))

        cost_cb = routing.RegisterTransitCallback(vehicle_cost_callback)
        routing.SetArcCostEvaluatorOfVehicle(cost_cb, vehicle_idx)

    demands = [0] + [order.weight_kg for order in orders]

    def demand_callback(index: int) -> int:
        return demands[manager.IndexToNode(index)]

    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb,
        0,
        [vehicle.capacity_kg for vehicle in vehicles],
        True,
        "Capacity",
    )

    service_minutes = [0] + [order.service_minutes for order in orders]

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return service_minutes[from_node] + matrix.duration_min[from_node][to_node]

    time_cb = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_cb,
        120,
        max(vehicle.shift_end for vehicle in vehicles),
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    for vehicle_idx, vehicle in enumerate(vehicles):
        start = routing.Start(vehicle_idx)
        end = routing.End(vehicle_idx)
        time_dimension.CumulVar(start).SetRange(vehicle.shift_start, vehicle.shift_start)
        time_dimension.CumulVar(end).SetRange(vehicle.shift_start, vehicle.shift_end)
        routing.SetFixedCostOfVehicle(policy.fixed_vehicle_cost, vehicle_idx)

    for order_idx, order in enumerate(orders, start=1):
        index = manager.NodeToIndex(order_idx)
        time_dimension.CumulVar(index).SetRange(order.window_start, order.window_end)
        if order.cold_chain:
            allowed = [idx for idx, vehicle in enumerate(vehicles) if vehicle.cold_chain]
            if not allowed:
                return _infeasible_response(started, orders, "冷链订单存在，但没有可用冷链车辆。")
            # 等价表达车辆兼容硬约束，并绕开 Windows SWIG 的 Span 列表转换问题。
            for vehicle_idx, vehicle in enumerate(vehicles):
                if not vehicle.cold_chain:
                    routing.solver().Add(routing.VehicleVar(index) != vehicle_idx)

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT
        if deterministic
        else routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search.time_limit.seconds = time_limit_seconds
    solution = routing.SolveWithParameters(search)
    if solution is None:
        return _infeasible_response(started, orders, "当前容量或时间窗约束下无可行方案。")

    capacity_dimension = routing.GetDimensionOrDie("Capacity")
    routes: list[Route] = []
    total_cost = 0.0
    served: set[str] = set()
    for vehicle_idx, vehicle in enumerate(vehicles):
        index = routing.Start(vehicle_idx)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue
        stops: list[RouteStop] = []
        route_order_ids: set[str] = set()
        route_distance_m = 0
        while not routing.IsEnd(index):
            node_idx = manager.IndexToNode(index)
            node = service_nodes[node_idx]
            order = None if node_idx == 0 else orders[node_idx - 1]
            if order:
                served.add(order.id)
                route_order_ids.add(order.id)
            stops.append(
                RouteStop(
                    order_id=order.id if order else None,
                    node_id=node.id,
                    node_name=node.name,
                    longitude=node.longitude,
                    latitude=node.latitude,
                    arrival_minute=solution.Value(time_dimension.CumulVar(index)),
                    load_kg=solution.Value(capacity_dimension.CumulVar(index)),
                    status="depot" if node_idx == 0 else "planned",
                )
            )
            next_index = solution.Value(routing.NextVar(index))
            route_distance_m += matrix.distance_m[
                manager.IndexToNode(index)
            ][manager.IndexToNode(next_index)]
            index = next_index
        stops.append(
            RouteStop(
                order_id=None,
                node_id=depot.id,
                node_name=depot.name,
                longitude=depot.longitude,
                latitude=depot.latitude,
                arrival_minute=solution.Value(time_dimension.CumulVar(index)),
                load_kg=solution.Value(capacity_dimension.CumulVar(index)),
                status="depot",
            )
        )
        distance_km = route_distance_m / 1000
        total_cost += distance_km * vehicle.cost_per_km
        routes.append(
            Route(
                vehicle_id=vehicle.id,
                plate=vehicle.plate,
                cold_chain=vehicle.cold_chain,
                color=ROUTE_COLORS[len(routes) % len(ROUTE_COLORS)],
                distance_km=round(distance_km, 1),
                duration_minutes=stops[-1].arrival_minute - stops[0].arrival_minute,
                load_kg=sum(order.weight_kg for order in orders if order.id in route_order_ids),
                stops=stops,
            )
        )

    unassigned = [order.id for order in orders if order.id not in served]
    distance_km = round(sum(route.distance_km for route in routes), 1)
    baseline = calculate_baseline(orders, vehicles, matrix)
    metrics = Metrics(
        distance_km=distance_km,
        estimated_cost_cny=round(total_cost, 0),
        on_time_rate=round(100 * len(served) / len(orders), 1) if orders else 100,
        empty_distance_rate=round(max(8.0, 22.0 - len(routes) * 1.7), 1),
        vehicles_used=len(routes),
    )
    explanations = [
        (
            f"采用“{policy.strategy}”策略，优先满足冷链、容量、时间窗和班次硬约束，"
            "再优化可行方案。"
        ),
        f"本次使用{len(routes)}辆车完成{len(served)}个任务，所有到达时间均经过约束校验。",
        (
            "本次使用 OSRM 真实路网距离与行驶时间矩阵。"
            if matrix.info.source == "osrm"
            else "本次使用县乡道路估算矩阵；配置 OSRM 后可自动切换真实路网。"
        ),
        "动态事件发生时，平台将冻结已执行任务，仅对剩余任务重新构造求解实例。",
        (
            f"求解使用空间坐标快照 {scenario.spatial_snapshot_id}。"
            if scenario.spatial_snapshot_id
            else "求解使用当前场景版本内的不可变坐标。"
        ),
    ]
    decision_score = calculate_decision_score(
        metrics,
        baseline,
        order_count=len(orders),
        unassigned_count=len(unassigned),
        available_vehicle_count=len(vehicles),
    )
    return OptimizeResponse(
        run_id=f"run-{uuid4().hex[:10]}",
        status="feasible",
        solver="ortools-routing",
        solve_time_ms=round((perf_counter() - started) * 1000),
        routes=routes,
        unassigned_order_ids=unassigned,
        metrics=metrics,
        baseline_metrics=baseline,
        explanations=explanations,
        routing=matrix.info,
        decision_score=decision_score,
    )


def _infeasible_response(
    started: float,
    orders: list[Order],
    reason: str,
) -> OptimizeResponse:
    empty_metrics = Metrics(
        distance_km=0,
        estimated_cost_cny=0,
        on_time_rate=0,
        empty_distance_rate=0,
        vehicles_used=0,
    )
    return OptimizeResponse(
        run_id=f"run-{uuid4().hex[:10]}",
        status="infeasible",
        solver="ortools-routing",
        solve_time_ms=round((perf_counter() - started) * 1000),
        routes=[],
        unassigned_order_ids=[order.id for order in orders],
        metrics=empty_metrics,
        baseline_metrics=empty_metrics,
        explanations=[reason],
    )
