"""Next-stop navigation planning for the driver execution workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.models import DriverAssignmentRecord
from app.schemas import (
    DriverNavigationRequest,
    DriverNavigationRouteView,
    NavigationPosition,
    NavigationStep,
)
from app.spatial import gcj02_to_wgs84, haversine_m, wgs84_to_gcj02


class NavigationRouteError(ValueError):
    """Raised when an assignment cannot provide a next-stop route."""


_MANEUVER_LABELS = {
    "depart": "出发",
    "arrive": "到达",
    "continue": "直行",
    "turn": "转弯",
    "merge": "并入道路",
    "on ramp": "驶入匝道",
    "off ramp": "驶出匝道",
    "fork": "选择分叉",
    "roundabout": "进入环岛",
    "rotary": "进入环岛",
    "end of road": "到达路口",
    "new name": "继续行驶",
    "notification": "继续行驶",
}
_MODIFIER_LABELS = {
    "left": "左转",
    "right": "右转",
    "slight left": "向左前方",
    "slight right": "向右前方",
    "sharp left": "向左急转",
    "sharp right": "向右急转",
    "straight": "直行",
    "uturn": "掉头",
}


def _is_depot(stop: dict[str, Any]) -> bool:
    return stop.get("status") == "depot" or stop.get("action") == "depot"


def _stop_position(stop: dict[str, Any]) -> NavigationPosition:
    node_id = str(stop.get("node_id") or "")
    node_name = str(stop.get("node_name") or node_id or "路线节点")
    return NavigationPosition(
        name=node_name,
        longitude=float(stop.get("longitude", 0)),
        latitude=float(stop.get("latitude", 0)),
    )


def _origin_from_request(
    request: DriverNavigationRequest,
) -> tuple[NavigationPosition, tuple[float, float]] | None:
    if request.origin_longitude is None or request.origin_latitude is None:
        return None
    longitude = float(request.origin_longitude)
    latitude = float(request.origin_latitude)
    if request.origin_coordinate_system == "wgs84":
        display_longitude, display_latitude = wgs84_to_gcj02(longitude, latitude)
        osrm_coordinates = (longitude, latitude)
    else:
        display_longitude, display_latitude = longitude, latitude
        osrm_coordinates = gcj02_to_wgs84(longitude, latitude)
    return (
        NavigationPosition(
            name=request.origin_name
            or ("当前位置" if request.origin_source == "gps" else "计划起点"),
            longitude=display_longitude,
            latitude=display_latitude,
        ),
        osrm_coordinates,
    )


def _planned_origin(
    stops: list[dict[str, Any]],
    target_index: int,
) -> NavigationPosition:
    non_depot = [stop for stop in stops if not _is_depot(stop)]
    if target_index > 0 and target_index - 1 < len(non_depot):
        return _stop_position(non_depot[target_index - 1])
    depot = next((stop for stop in stops if _is_depot(stop)), None)
    if depot is not None:
        return _stop_position(depot)
    if non_depot:
        return _stop_position(non_depot[0])
    raise NavigationRouteError("当前任务没有可用路线起点")


def _instruction(
    maneuver: dict[str, Any],
    road_name: str | None,
    *,
    origin_name: str,
    destination_name: str,
) -> str:
    maneuver_type = str(maneuver.get("type") or "").strip().lower()
    modifier = str(maneuver.get("modifier") or "").strip().lower()
    if maneuver_type == "depart":
        return f"从{origin_name}出发"
    if maneuver_type == "arrive":
        return f"到达{destination_name}"
    direction = _MODIFIER_LABELS.get(modifier)
    action = _MANEUVER_LABELS.get(maneuver_type, "继续行驶")
    if direction and maneuver_type in {"turn", "continue", "end of road"}:
        action = direction
    if road_name:
        return f"{action}进入{road_name}"
    return action


def _steps_from_osrm(
    payload: dict[str, Any],
    *,
    origin_name: str,
    destination_name: str,
) -> list[NavigationStep]:
    steps: list[NavigationStep] = []
    for leg in payload.get("legs", []):
        for raw in leg.get("steps", []):
            if not isinstance(raw, dict):
                continue
            maneuver = raw.get("maneuver") or {}
            road_name = str(raw.get("name") or "").strip() or None
            distance_m = max(0.0, float(raw.get("distance") or 0))
            duration_seconds = max(0, round(float(raw.get("duration") or 0)))
            steps.append(
                NavigationStep(
                    sequence=len(steps) + 1,
                    instruction=_instruction(
                        maneuver,
                        road_name,
                        origin_name=origin_name,
                        destination_name=destination_name,
                    ),
                    distance_m=distance_m,
                    duration_seconds=duration_seconds,
                    road_name=road_name,
                    maneuver=str(maneuver.get("type") or "") or None,
                )
            )
    return steps


def _thin_geometry(
    coordinates: list[list[float]],
    *,
    max_points: int = 500,
) -> list[tuple[float, float]]:
    points = [
        (float(item[0]), float(item[1]))
        for item in coordinates
        if isinstance(item, (list, tuple)) and len(item) >= 2
    ]
    if len(points) <= max_points:
        return points
    last_index = len(points) - 1
    indexes = {
        round(index * last_index / (max_points - 1))
        for index in range(max_points)
    }
    return [point for index, point in enumerate(points) if index in indexes]


def _request_osrm_route(
    origin_wgs84: tuple[float, float],
    destination_wgs84: tuple[float, float],
) -> tuple[float, int, list[tuple[float, float]], list[NavigationStep]]:
    settings = get_settings()
    coordinates = (
        f"{origin_wgs84[0]:.6f},{origin_wgs84[1]:.6f};"
        f"{destination_wgs84[0]:.6f},{destination_wgs84[1]:.6f}"
    )
    url = (
        f"{settings.osrm_base_url.rstrip('/')}/route/v1/"
        f"{settings.osrm_profile}/{coordinates}"
    )
    response = httpx.get(
        url,
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "alternatives": "false",
        },
        timeout=settings.osrm_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok":
        raise ValueError(payload.get("message") or "OSRM 路径规划失败")
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("OSRM 未返回可行路线")
    route = routes[0]
    geometry = (route.get("geometry") or {}).get("coordinates")
    if not isinstance(geometry, list) or len(geometry) < 2:
        raise ValueError("OSRM 未返回路线几何")
    display_geometry = [
        wgs84_to_gcj02(float(point[0]), float(point[1]))
        for point in _thin_geometry(geometry)
    ]
    distance_km = max(0.0, float(route.get("distance") or 0)) / 1000
    duration_minutes = max(0, round(float(route.get("duration") or 0) / 60))
    return distance_km, duration_minutes, display_geometry, _steps_from_osrm(
        route,
        origin_name="当前位置",
        destination_name="目标站点",
    )


def _fallback_route(
    origin: NavigationPosition,
    destination: NavigationPosition,
    *,
    reason: str,
) -> tuple[float, int, list[tuple[float, float]], list[NavigationStep]]:
    settings = get_settings()
    distance_m = haversine_m(
        origin.longitude,
        origin.latitude,
        destination.longitude,
        destination.latitude,
    ) * settings.rural_detour_factor
    duration_seconds = (
        round(distance_m / 1000 / settings.rural_average_speed_kmh * 3600)
        if distance_m
        else 0
    )
    instruction = (
        f"已到达{destination.name}"
        if distance_m == 0
        else f"沿计划路线前往{destination.name}"
    )
    return (
        distance_m / 1000,
        max(0, round(duration_seconds / 60)),
        [
            (origin.longitude, origin.latitude),
            (destination.longitude, destination.latitude),
        ],
        [
            NavigationStep(
                sequence=1,
                instruction=instruction,
                distance_m=distance_m,
                duration_seconds=duration_seconds,
            )
        ],
    )


def build_assignment_navigation(
    assignment: DriverAssignmentRecord,
    request: DriverNavigationRequest,
) -> DriverNavigationRouteView:
    if assignment.status not in {"accepted", "executing"}:
        raise NavigationRouteError("请先接收并开始执行车辆任务")
    stops = [
        stop
        for stop in assignment.route_payload.get("stops", [])
        if isinstance(stop, dict) and not _is_depot(stop)
    ]
    target_index = next(
        (index for index, stop in enumerate(stops) if stop.get("status") != "completed"),
        None,
    )
    if target_index is None:
        raise NavigationRouteError("当前任务没有待导航站点")
    target = stops[target_index]
    destination = _stop_position(target)
    requested_origin = _origin_from_request(request)
    if requested_origin is None:
        origin = _planned_origin(
            [
                stop
                for stop in assignment.route_payload.get("stops", [])
                if isinstance(stop, dict)
            ],
            target_index,
        )
        origin_source = "planned"
        origin_wgs84 = gcj02_to_wgs84(origin.longitude, origin.latitude)
    else:
        origin, origin_wgs84 = requested_origin
        origin_source = request.origin_source
    destination_wgs84 = gcj02_to_wgs84(destination.longitude, destination.latitude)

    routing_source = "osrm"
    fallback_used = False
    fallback_reason: str | None = None
    settings = get_settings()
    try:
        if settings.routing_provider.strip().lower() != "osrm":
            raise ValueError("当前未启用 OSRM 路网服务")
        distance_km, duration_minutes, geometry, steps = _request_osrm_route(
            origin_wgs84,
            destination_wgs84,
        )
        if steps:
            steps[0] = steps[0].model_copy(
                update={
                    "instruction": _instruction(
                        {
                            "type": steps[0].maneuver or "depart",
                        },
                        steps[0].road_name,
                        origin_name=origin.name,
                        destination_name=destination.name,
                    )
                }
            )
            steps[-1] = steps[-1].model_copy(
                update={
                    "instruction": (
                        f"到达{destination.name}"
                        if steps[-1].maneuver == "arrive"
                        else steps[-1].instruction
                    )
                }
            )
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        routing_source = "haversine"
        fallback_used = True
        fallback_reason = f"{type(exc).__name__}: {str(exc)[:180]}"
        distance_km, duration_minutes, geometry, steps = _fallback_route(
            origin,
            destination,
            reason=fallback_reason,
        )

    return DriverNavigationRouteView(
        assignment_id=assignment.id,
        route_index=assignment.route_index,
        stop_sequence=target_index + 1,
        origin_source=origin_source,
        origin=origin,
        destination=destination,
        distance_km=round(distance_km, 2),
        duration_minutes=duration_minutes,
        routing_source=routing_source,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        geometry=geometry,
        steps=steps,
        generated_at=datetime.now(timezone.utc),
    )
