from __future__ import annotations

import math


QIDONG_BOUNDS = {
    "min_longitude": 111.52,
    "max_longitude": 112.36,
    "min_latitude": 26.44,
    "max_latitude": 27.09,
}


def gcj02_to_wgs84(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert mainland GCJ-02 display coordinates to WGS-84 storage coordinates."""
    if not _inside_china(longitude, latitude):
        return longitude, latitude
    adjusted_longitude, adjusted_latitude = _wgs84_to_gcj02(longitude, latitude)
    return 2 * longitude - adjusted_longitude, 2 * latitude - adjusted_latitude


def haversine_m(
    first_longitude: float,
    first_latitude: float,
    second_longitude: float,
    second_latitude: float,
) -> float:
    radius_m = 6_371_008.8
    first_latitude_rad = math.radians(first_latitude)
    second_latitude_rad = math.radians(second_latitude)
    delta_latitude = math.radians(second_latitude - first_latitude)
    delta_longitude = math.radians(second_longitude - first_longitude)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first_latitude_rad)
        * math.cos(second_latitude_rad)
        * math.sin(delta_longitude / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def inside_qidong_bounds(longitude: float, latitude: float) -> bool:
    return (
        QIDONG_BOUNDS["min_longitude"] <= longitude <= QIDONG_BOUNDS["max_longitude"]
        and QIDONG_BOUNDS["min_latitude"] <= latitude <= QIDONG_BOUNDS["max_latitude"]
    )


def _inside_china(longitude: float, latitude: float) -> bool:
    return 72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271


def _wgs84_to_gcj02(longitude: float, latitude: float) -> tuple[float, float]:
    axis = 6_378_245.0
    eccentricity = 0.006693421622965943
    delta_latitude = _transform_latitude(longitude - 105.0, latitude - 35.0)
    delta_longitude = _transform_longitude(longitude - 105.0, latitude - 35.0)
    latitude_rad = math.radians(latitude)
    magic = math.sin(latitude_rad)
    magic = 1 - eccentricity * magic * magic
    sqrt_magic = math.sqrt(magic)
    delta_latitude = (
        delta_latitude * 180.0
        / ((axis * (1 - eccentricity)) / (magic * sqrt_magic) * math.pi)
    )
    delta_longitude = (
        delta_longitude * 180.0
        / (axis / sqrt_magic * math.cos(latitude_rad) * math.pi)
    )
    return longitude + delta_longitude, latitude + delta_latitude


def _transform_latitude(longitude: float, latitude: float) -> float:
    value = (
        -100.0
        + 2.0 * longitude
        + 3.0 * latitude
        + 0.2 * latitude * latitude
        + 0.1 * longitude * latitude
        + 0.2 * math.sqrt(abs(longitude))
    )
    value += (
        20.0 * math.sin(6.0 * longitude * math.pi)
        + 20.0 * math.sin(2.0 * longitude * math.pi)
    ) * 2.0 / 3.0
    value += (
        20.0 * math.sin(latitude * math.pi)
        + 40.0 * math.sin(latitude / 3.0 * math.pi)
    ) * 2.0 / 3.0
    value += (
        160.0 * math.sin(latitude / 12.0 * math.pi)
        + 320 * math.sin(latitude * math.pi / 30.0)
    ) * 2.0 / 3.0
    return value


def _transform_longitude(longitude: float, latitude: float) -> float:
    value = (
        300.0
        + longitude
        + 2.0 * latitude
        + 0.1 * longitude * longitude
        + 0.1 * longitude * latitude
        + 0.1 * math.sqrt(abs(longitude))
    )
    value += (
        20.0 * math.sin(6.0 * longitude * math.pi)
        + 20.0 * math.sin(2.0 * longitude * math.pi)
    ) * 2.0 / 3.0
    value += (
        20.0 * math.sin(longitude * math.pi)
        + 40.0 * math.sin(longitude / 3.0 * math.pi)
    ) * 2.0 / 3.0
    value += (
        150.0 * math.sin(longitude / 12.0 * math.pi)
        + 300.0 * math.sin(longitude / 30.0 * math.pi)
    ) * 2.0 / 3.0
    return value
