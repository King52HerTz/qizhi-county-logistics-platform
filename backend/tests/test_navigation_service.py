from app.models import DriverAssignmentRecord
from app.navigation_service import NavigationRouteError, build_assignment_navigation
from app.schemas import DriverNavigationRequest


def _assignment(*, status: str = "accepted") -> DriverAssignmentRecord:
    return DriverAssignmentRecord(
        id=21,
        route_index=2,
        vehicle_id="V-NORM-01",
        plate="湘D·B5612",
        status=status,
        route_payload={
            "stops": [
                {
                    "order_id": None,
                    "node_id": "D-01",
                    "node_name": "祁东县县域共配中心",
                    "longitude": 112.058674,
                    "latitude": 26.769788,
                    "status": "depot",
                    "action": "depot",
                },
                {
                    "order_id": "DOWN-001",
                    "node_id": "V-001",
                    "node_name": "砖塘镇石山堰村服务站",
                    "longitude": 111.830925,
                    "latitude": 26.812125,
                    "status": "planned",
                    "action": "pickup",
                },
                {
                    "order_id": "DOWN-001",
                    "node_id": "V-001",
                    "node_name": "砖塘镇石山堰村服务站",
                    "longitude": 111.830925,
                    "latitude": 26.812125,
                    "status": "planned",
                    "action": "delivery",
                },
            ]
        },
    )


def test_navigation_uses_gps_origin_and_osrm_route(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "routing_provider", "osrm")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "code": "Ok",
                "routes": [
                    {
                        "distance": 4200,
                        "duration": 780,
                        "geometry": {
                            "coordinates": [
                                [112.058674, 26.769788],
                                [112.0, 26.79],
                                [111.830925, 26.812125],
                            ]
                        },
                        "legs": [
                            {
                                "steps": [
                                    {
                                        "distance": 3200,
                                        "duration": 600,
                                        "name": "县道X001",
                                        "maneuver": {"type": "depart"},
                                    },
                                    {
                                        "distance": 1000,
                                        "duration": 180,
                                        "name": "村道",
                                        "maneuver": {"type": "arrive"},
                                    },
                                ]
                            }
                        ],
                    }
                ],
            }

    monkeypatch.setattr("app.navigation_service.httpx.get", lambda *args, **kwargs: FakeResponse())
    result = build_assignment_navigation(
        _assignment(),
        DriverNavigationRequest(
            origin_longitude=112.05,
            origin_latitude=26.77,
            origin_name="车辆当前位置",
            origin_source="gps",
            origin_coordinate_system="wgs84",
        ),
    )

    assert result.origin_source == "gps"
    assert result.origin.name == "车辆当前位置"
    assert result.routing_source == "osrm"
    assert result.fallback_used is False
    assert result.stop_sequence == 1
    assert result.destination.name == "砖塘镇石山堰村服务站"
    assert result.distance_km == 4.2
    assert result.duration_minutes == 13
    assert len(result.geometry) == 3
    assert result.steps[0].instruction.startswith("从车辆当前位置出发")
    assert result.steps[-1].instruction == "到达砖塘镇石山堰村服务站"


def test_navigation_falls_back_to_planned_origin_when_osrm_unavailable(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "routing_provider", "osrm")

    monkeypatch.setattr(
        "app.navigation_service.httpx.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("network unavailable")),
    )
    result = build_assignment_navigation(
        _assignment(),
        DriverNavigationRequest(),
    )

    assert result.origin_source == "planned"
    assert result.origin.name == "祁东县县域共配中心"
    assert result.routing_source == "haversine"
    assert result.fallback_used is True
    assert "network unavailable" in (result.fallback_reason or "")
    assert result.geometry[0] == (112.058674, 26.769788)


def test_navigation_rejects_pending_assignment() -> None:
    try:
        build_assignment_navigation(_assignment(status="pending"), DriverNavigationRequest())
    except NavigationRouteError as exc:
        assert "接收并开始执行" in str(exc)
    else:
        raise AssertionError("pending assignment should not produce navigation")
