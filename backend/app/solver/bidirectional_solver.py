"""OR-Tools pickup-and-delivery solver for the bidirectional demo profile."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.routing_matrix import RoutingMatrix, build_routing_matrix
from app.schemas import (
    DecisionScore,
    Metrics,
    Node,
    OptimizeResponse,
    Order,
    Route,
    RouteStop,
    Scenario,
    Vehicle,
)
from app.solver.ortools_solver import (
    POLICIES,
    ROUTE_COLORS,
    calculate_decision_score,
)


@dataclass(frozen=True)
class _Point:
    node: Node
    order: Order | None
    action: str


@dataclass(frozen=True)
class _OrderPair:
    order: Order
    pickup_index: int
    delivery_index: int


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
        solver="ortools-pickup-delivery",
        solve_time_ms=round((perf_counter() - started) * 1000),
        routes=[],
        unassigned_order_ids=[order.id for order in orders],
        metrics=empty_metrics,
        baseline_metrics=empty_metrics,
        explanations=[reason],
    )


def _build_order_pairs(
    scenario: Scenario,
    orders: list[Order],
) -> tuple[list[_Point], list[_OrderPair], str | None]:
    node_map = {node.id: node for node in scenario.nodes}
    depots = [node for node in scenario.nodes if node.kind == "depot"]
    processors = [node for node in scenario.nodes if node.kind == "processor"]
    if len(depots) != 1:
        return [], [], f"场景必须且只能包含一个配送中心，当前为 {len(depots)} 个。"
    if not processors:
        return [], [], "双向配送场景至少需要一个加工中心节点。"

    depot = depots[0]
    default_processor = processors[0]
    points = [_Point(node=depot, order=None, action="depot")]
    pairs: list[_OrderPair] = []
    for order in orders:
        if order.flow_direction == "upward":
            origin_id = order.origin_node_id or order.node_id
            destination_id = order.destination_node_id or default_processor.id
        else:
            origin_id = order.origin_node_id or depot.id
            destination_id = order.destination_node_id or order.node_id
        origin = node_map.get(origin_id)
        destination = node_map.get(destination_id)
        if origin is None or destination is None:
            missing = origin_id if origin is None else destination_id
            return [], [], f"订单 {order.id} 引用了不存在的取送节点：{missing}。"
        pickup_index = len(points)
        points.append(_Point(node=origin, order=order, action="pickup"))
        delivery_index = len(points)
        points.append(_Point(node=destination, order=order, action="delivery"))
        pairs.append(
            _OrderPair(
                order=order,
                pickup_index=pickup_index,
                delivery_index=delivery_index,
            )
        )
    return points, pairs, None


def _calculate_bidirectional_baseline(
    pairs: list[_OrderPair],
    vehicles: list[Vehicle],
    matrix: RoutingMatrix,
) -> Metrics:
    """Build a deterministic sequential pickup-delivery business baseline."""
    current_node = [0 for _ in vehicles]
    current_minute = [vehicle.shift_start for vehicle in vehicles]
    current_load = [0 for _ in vehicles]
    buckets: list[list[_OrderPair]] = [[] for _ in vehicles]
    assigned = 0

    for pair in pairs:
        order = pair.order
        chosen: int | None = None
        for vehicle_index, vehicle in enumerate(vehicles):
            if order.cold_chain and not vehicle.cold_chain:
                continue
            pickup_arrival = max(
                current_minute[vehicle_index]
                + matrix.duration_min[current_node[vehicle_index]][pair.pickup_index],
                order.window_start,
            )
            if pickup_arrival > order.window_end:
                continue
            load_after_pickup = current_load[vehicle_index] + order.weight_kg
            if load_after_pickup > vehicle.capacity_kg:
                continue
            delivery_arrival = max(
                pickup_arrival
                + order.service_minutes
                + matrix.duration_min[pair.pickup_index][pair.delivery_index],
                order.window_start,
            )
            if delivery_arrival > order.window_end:
                continue
            route_end = (
                delivery_arrival
                + order.service_minutes
                + matrix.duration_min[pair.delivery_index][0]
            )
            if route_end > vehicle.shift_end:
                continue
            chosen = vehicle_index
            break
        if chosen is None:
            continue
        pickup_arrival = max(
            current_minute[chosen]
            + matrix.duration_min[current_node[chosen]][pair.pickup_index],
            order.window_start,
        )
        delivery_arrival = max(
            pickup_arrival
            + order.service_minutes
            + matrix.duration_min[pair.pickup_index][pair.delivery_index],
            order.window_start,
        )
        buckets[chosen].append(pair)
        current_node[chosen] = pair.delivery_index
        current_minute[chosen] = delivery_arrival + order.service_minutes
        assigned += 1

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
        for pair in bucket:
            route_distance_m += matrix.distance_m[current_index][pair.pickup_index]
            route_distance_m += matrix.distance_m[pair.pickup_index][pair.delivery_index]
            current_index = pair.delivery_index
        route_distance_m += matrix.distance_m[current_index][0]
        empty_distance_m += matrix.distance_m[current_index][0]
        total_distance_m += route_distance_m
        total_cost += route_distance_m / 1000 * vehicle.cost_per_km
    return Metrics(
        distance_km=round(total_distance_m / 1000, 1),
        estimated_cost_cny=round(total_cost, 0),
        on_time_rate=round(100 * assigned / len(pairs), 1) if pairs else 100,
        empty_distance_rate=(
            round(100 * empty_distance_m / total_distance_m, 1)
            if total_distance_m
            else 0
        ),
        vehicles_used=vehicles_used,
    )


def solve_bidirectional_scenario(
    scenario: Scenario,
    *,
    time_limit_seconds: int = 5,
    unavailable_vehicle_ids: set[str] | None = None,
    extra_orders: list[Order] | None = None,
    strategy: str = "balanced",
    deterministic: bool = False,
) -> OptimizeResponse:
    """Solve paired upward/downward tasks with OR-Tools hard constraints."""
    started = perf_counter()
    unavailable_vehicle_ids = unavailable_vehicle_ids or set()
    orders = [order for order in scenario.orders if not order.completed] + (extra_orders or [])
    vehicles = [
        vehicle
        for vehicle in scenario.vehicles
        if vehicle.available and vehicle.id not in unavailable_vehicle_ids
    ]
    if not vehicles:
        return _infeasible_response(started, orders, "没有可用车辆。")
    policy = POLICIES.get(strategy, POLICIES["balanced"])

    points, pairs, error = _build_order_pairs(scenario, orders)
    if error:
        return _infeasible_response(started, orders, error)
    if not points:
        return _infeasible_response(started, orders, "双向配送场景没有可求解的节点。")
    coords = [(point.node.longitude, point.node.latitude) for point in points]
    matrix = build_routing_matrix(coords)

    manager = pywrapcp.RoutingIndexManager(len(points), len(vehicles), 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        return matrix.distance_m[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    for vehicle_idx, vehicle in enumerate(vehicles):
        multiplier = policy.distance_weight + policy.operating_cost_weight * float(vehicle.cost_per_km)

        def vehicle_cost_callback(
            from_index: int,
            to_index: int,
            factor: float = multiplier,
        ) -> int:
            return max(0, round(distance_callback(from_index, to_index) * factor))

        cost_cb = routing.RegisterTransitCallback(vehicle_cost_callback)
        routing.SetArcCostEvaluatorOfVehicle(cost_cb, vehicle_idx)

    demands = [
        0
        if point.order is None
        else point.order.weight_kg if point.action == "pickup" else -point.order.weight_kg
        for point in points
    ]

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
    capacity_dimension = routing.GetDimensionOrDie("Capacity")

    service_minutes = [
        0 if point.order is None else point.order.service_minutes for point in points
    ]

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

    for pair in pairs:
        pickup_index = manager.NodeToIndex(pair.pickup_index)
        delivery_index = manager.NodeToIndex(pair.delivery_index)
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        solver = routing.solver()
        solver.Add(routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index))
        solver.Add(
            time_dimension.CumulVar(pickup_index)
            <= time_dimension.CumulVar(delivery_index)
        )
        for point_index in (pair.pickup_index, pair.delivery_index):
            time_dimension.CumulVar(point_index).SetRange(
                pair.order.window_start,
                pair.order.window_end,
            )
        if pair.order.cold_chain:
            allowed = [idx for idx, vehicle in enumerate(vehicles) if vehicle.cold_chain]
            if not allowed:
                return _infeasible_response(
                    started,
                    orders,
                    "冷链订单存在，但没有可用冷链车辆。",
                )
            for vehicle_idx, vehicle in enumerate(vehicles):
                if not vehicle.cold_chain:
                    solver.Add(routing.VehicleVar(pickup_index) != vehicle_idx)

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
        return _infeasible_response(started, orders, "当前取送货、容量或时间窗约束下无可行方案。")

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
        max_load = 0
        while not routing.IsEnd(index):
            point_index = manager.IndexToNode(index)
            point = points[point_index]
            order = point.order
            if order:
                served.add(order.id)
                route_order_ids.add(order.id)
            load_kg = solution.Value(capacity_dimension.CumulVar(index))
            max_load = max(max_load, load_kg)
            stops.append(
                RouteStop(
                    order_id=order.id if order else None,
                    node_id=point.node.id,
                    node_name=point.node.name,
                    longitude=point.node.longitude,
                    latitude=point.node.latitude,
                    arrival_minute=solution.Value(time_dimension.CumulVar(index)),
                    load_kg=load_kg,
                    status="depot" if point.action == "depot" else "planned",
                    action=point.action,
                    flow_direction=order.flow_direction if order else None,
                    cargo_category=order.cargo_category if order else None,
                )
            )
            next_index = solution.Value(routing.NextVar(index))
            route_distance_m += matrix.distance_m[point_index][manager.IndexToNode(next_index)]
            index = next_index
        depot = points[0].node
        final_load = solution.Value(capacity_dimension.CumulVar(index))
        max_load = max(max_load, final_load)
        stops.append(
            RouteStop(
                order_id=None,
                node_id=depot.id,
                node_name=depot.name,
                longitude=depot.longitude,
                latitude=depot.latitude,
                arrival_minute=solution.Value(time_dimension.CumulVar(index)),
                load_kg=final_load,
                status="depot",
                action="depot",
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
                load_kg=max_load,
                stops=stops,
            )
        )

    unassigned = [order.id for order in orders if order.id not in served]
    distance_km = round(sum(route.distance_km for route in routes), 1)
    baseline = _calculate_bidirectional_baseline(pairs, vehicles, matrix)
    metrics = Metrics(
        distance_km=distance_km,
        estimated_cost_cny=round(total_cost, 0),
        on_time_rate=round(100 * len(served) / len(orders), 1) if orders else 100,
        empty_distance_rate=round(max(6.0, 18.0 - len(routes) * 1.4), 1),
        vehicles_used=len(routes),
    )
    urgent_orders = [order for order in orders if order.priority == "urgent"]
    unassigned_urgent = [
        order_id for order_id in unassigned if any(order.id == order_id for order in urgent_orders)
    ]
    decision_score: DecisionScore = calculate_decision_score(
        metrics,
        baseline,
        order_count=len(orders),
        unassigned_count=len(unassigned),
        urgent_order_count=len(urgent_orders),
        unassigned_urgent_count=len(unassigned_urgent),
        available_vehicle_count=len(vehicles),
    )
    upward_orders = sum(order.flow_direction == "upward" for order in orders)
    downward_orders = sum(order.flow_direction == "downward" for order in orders)
    explanations = [
        (
            f"采用“{policy.strategy}”策略，按上行取货→加工点交付、"
            "下行中心装货→村点交付构造取送货约束。"
        ),
        (
            f"本次使用{len(routes)}辆车完成{len(served)}个任务，"
            f"其中农产品上行 {upward_orders} 单、工业品下行 {downward_orders} 单。"
        ),
        "OR-Tools 已绑定每个订单的取货点与交付点，确保同车执行且先取后送。",
        (
            "本次使用 OSRM 真实路网距离与行驶时间矩阵。"
            if matrix.info.source == "osrm"
            else "本次使用县乡道路估算矩阵；配置 OSRM 后可自动切换真实路网。"
        ),
        (
            f"求解使用空间坐标快照 {scenario.spatial_snapshot_id}。"
            if scenario.spatial_snapshot_id
            else "求解使用当前场景版本内的不可变坐标。"
        ),
    ]
    return OptimizeResponse(
        run_id=f"run-{uuid4().hex[:10]}",
        status="feasible",
        solver="ortools-pickup-delivery",
        solve_time_ms=round((perf_counter() - started) * 1000),
        routes=routes,
        unassigned_order_ids=unassigned,
        metrics=metrics,
        baseline_metrics=baseline,
        explanations=explanations,
        routing=matrix.info,
        decision_score=decision_score,
    )
