from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from threading import Lock

import httpx

from app.config import get_settings
from app.schemas import RoutingMatrixInfo


@dataclass(frozen=True)
class RoutingMatrix:
    distance_m: list[list[int]]
    duration_min: list[list[int]]
    info: RoutingMatrixInfo


_cache: OrderedDict[str, RoutingMatrix] = OrderedDict()
_cache_lock = Lock()
_STANDARD_MATRIX_PATH = Path(__file__).parent / "data" / "standard_demo_matrix.json"


def _load_standard_snapshots() -> dict:
    with _STANDARD_MATRIX_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


_STANDARD_SNAPSHOTS = _load_standard_snapshots()


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(radians, a)
    lon2, lat2 = map(radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def _fingerprint(coords: list[tuple[float, float]], provider: str) -> str:
    normalized = ";".join(f"{longitude:.6f},{latitude:.6f}" for longitude, latitude in coords)
    return sha256(f"{provider}|{normalized}".encode()).hexdigest()


def _standard_snapshot_matrix(
    coords: list[tuple[float, float]],
) -> RoutingMatrix | None:
    normalized = [
        f"{longitude:.6f},{latitude:.6f}" for longitude, latitude in coords
    ]
    for snapshot_name in ("base", "event"):
        snapshot = _STANDARD_SNAPSHOTS[snapshot_name]
        if normalized != snapshot["coordinates"]:
            continue
        return RoutingMatrix(
            distance_m=[row[:] for row in snapshot["distance_m"]],
            duration_min=[row[:] for row in snapshot["duration_min"]],
            info=RoutingMatrixInfo(
                requested_provider="osrm",
                source="osrm",
                data_version=(
                    f"{_STANDARD_SNAPSHOTS['profile']}-"
                    f"{_STANDARD_SNAPSHOTS['captured_at'][:10].replace('-', '')}"
                ),
                coordinate_count=len(coords),
            ),
        )
    return None


def _cache_get(key: str) -> RoutingMatrix | None:
    with _cache_lock:
        cached = _cache.get(key)
        if cached is None:
            return None
        _cache.move_to_end(key)
        return replace(cached, info=cached.info.model_copy(update={"cache_hit": True}))


def _cache_put(key: str, matrix: RoutingMatrix) -> None:
    capacity = max(1, get_settings().routing_cache_size)
    with _cache_lock:
        _cache[key] = matrix
        _cache.move_to_end(key)
        while len(_cache) > capacity:
            _cache.popitem(last=False)


def cache_status() -> tuple[int, int]:
    with _cache_lock:
        return len(_cache), max(1, get_settings().routing_cache_size)


def clear_matrix_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _haversine_matrix(
    coords: list[tuple[float, float]],
    *,
    requested_provider: str,
    fallback_reason: str | None = None,
) -> RoutingMatrix:
    settings = get_settings()
    distance_m: list[list[int]] = []
    duration_min: list[list[int]] = []
    for origin in coords:
        distance_row: list[int] = []
        duration_row: list[int] = []
        for destination in coords:
            km = haversine_km(origin, destination) * settings.rural_detour_factor
            distance_row.append(round(km * 1000))
            duration_row.append(round(km / settings.rural_average_speed_kmh * 60))
        distance_m.append(distance_row)
        duration_min.append(duration_row)
    return RoutingMatrix(
        distance_m=distance_m,
        duration_min=duration_min,
        info=RoutingMatrixInfo(
            requested_provider=requested_provider,
            source="haversine",
            fallback_used=fallback_reason is not None,
            fallback_reason=fallback_reason,
            coordinate_count=len(coords),
        ),
    )


def _osrm_matrix(coords: list[tuple[float, float]]) -> RoutingMatrix:
    settings = get_settings()
    coordinates = ";".join(f"{longitude:.6f},{latitude:.6f}" for longitude, latitude in coords)
    url = (
        f"{settings.osrm_base_url.rstrip('/')}/table/v1/"
        f"{settings.osrm_profile}/{coordinates}"
    )
    response = httpx.get(
        url,
        params={
            "annotations": "distance,duration",
            "fallback_speed": settings.rural_average_speed_kmh,
            "skip_waypoints": "true",
        },
        timeout=settings.osrm_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok":
        raise ValueError(payload.get("message") or f"OSRM 返回状态 {payload.get('code')}")
    distances = payload.get("distances")
    durations = payload.get("durations")
    size = len(coords)
    if (
        not isinstance(distances, list)
        or not isinstance(durations, list)
        or len(distances) != size
        or len(durations) != size
        or any(len(row) != size for row in distances)
        or any(len(row) != size for row in durations)
    ):
        raise ValueError("OSRM 返回的矩阵维度不完整")
    if any(value is None for row in distances for value in row):
        raise ValueError("OSRM 距离矩阵包含不可达路段")
    if any(value is None for row in durations for value in row):
        raise ValueError("OSRM 时间矩阵包含不可达路段")
    return RoutingMatrix(
        distance_m=[[round(float(value)) for value in row] for row in distances],
        duration_min=[
            [max(0, round(float(value) / 60)) for value in row]
            for row in durations
        ],
        info=RoutingMatrixInfo(
            requested_provider="osrm",
            source="osrm",
            data_version=payload.get("data_version"),
            coordinate_count=size,
        ),
    )


def build_routing_matrix(coords: list[tuple[float, float]]) -> RoutingMatrix:
    requested = get_settings().routing_provider.strip().lower()
    provider = "osrm" if requested == "osrm" else "haversine"
    snapshot = _standard_snapshot_matrix(coords)
    cache_provider = "standard-snapshot" if snapshot is not None else provider
    key = _fingerprint(coords, cache_provider)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    if snapshot is not None:
        matrix = snapshot
    elif provider == "osrm":
        try:
            matrix = _osrm_matrix(coords)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            matrix = _haversine_matrix(
                coords,
                requested_provider="osrm",
                fallback_reason=f"{type(exc).__name__}: {str(exc)[:180]}",
            )
    else:
        matrix = _haversine_matrix(coords, requested_provider=requested)
    _cache_put(key, matrix)
    return matrix
