"""冷链仓储共享调度与全程温控监测预警接口测试。"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

settings = get_settings()


def generated_strong_password() -> str:
    """运行时生成符合强度策略的测试口令，避免在仓库中固化口令字面量。"""
    import secrets
    import string

    body = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    return f"Qz1{body}a!"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.admin_username,
                "password": settings.admin_password,
            },
        )
        assert login.status_code == 200
        test_client.headers.update(
            {"Authorization": f"Bearer {login.json()['access_token']}"}
        )
        yield test_client


def test_cold_chain_stores_seeded_with_capacity(client: TestClient) -> None:
    response = client.get("/api/v1/cold-chain/stores")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 6
    by_id = {item["id"]: item for item in items}
    hub = by_id["CS-01"]
    assert hub["store_type"] == "county_hub"
    assert hub["capacity_tons"] == 800
    assert hub["node_name"]
    assert hub["available_tons"] <= hub["capacity_tons"]


def test_cold_chain_booking_create_and_capacity_guard(client: TestClient) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created = client.post(
        "/api/v1/cold-chain/bookings",
        json={
            "cold_store_id": "CS-03",
            "booking_date": today,
            "purpose": "precool",
            "tons": 5.5,
            "note": "黄花菜采收季预冷预约",
        },
    )
    assert created.status_code == 201
    booking = created.json()
    assert booking["status"] == "reserved"
    assert booking["cold_store_name"] == "黄土铺黄花菜预冷共享库"

    listed = client.get("/api/v1/cold-chain/bookings?limit=10")
    assert listed.status_code == 200
    assert any(item["id"] == booking["id"] for item in listed.json()["items"])

    oversized = client.post(
        "/api/v1/cold-chain/bookings",
        json={
            "cold_store_id": "CS-04",
            "booking_date": today,
            "purpose": "short_storage",
            "tons": 999,
        },
    )
    assert oversized.status_code == 409

    invalid_store = client.post(
        "/api/v1/cold-chain/bookings",
        json={
            "cold_store_id": "CS-404",
            "booking_date": today,
            "purpose": "precool",
            "tons": 1,
        },
    )
    assert invalid_store.status_code == 409


def test_temperature_simulation_creates_readings_and_alerts(client: TestClient) -> None:
    simulated = client.post(
        "/api/v1/cold-chain/temperature/simulate",
        json={"hours": 6},
    )
    assert simulated.status_code == 200
    result = simulated.json()
    assert result["sensors"] >= 6
    assert result["readings_created"] > 0
    assert result["alerts_created"] >= 1

    sensors = client.get("/api/v1/cold-chain/sensors")
    assert sensors.status_code == 200
    sensor_items = sensors.json()["items"]
    vehicle_sensors = [item for item in sensor_items if item["sensor_type"] == "vehicle"]
    assert vehicle_sensors
    assert any(item["latest_temperature_c"] is not None for item in sensor_items)

    first_sensor = sorted(item["id"] for item in sensor_items)[0]
    readings = client.get(f"/api/v1/cold-chain/sensors/{first_sensor}/readings?limit=50")
    assert readings.status_code == 200
    reading_payload = readings.json()
    assert reading_payload["sensor_id"] == first_sensor
    assert reading_payload["items"]
    assert reading_payload["target_high_c"] > reading_payload["target_low_c"]

    alerts = client.get("/api/v1/cold-chain/alerts")
    assert alerts.status_code == 200
    alert_items = alerts.json()["items"]
    assert any(item["alert_type"] == "threshold_breach" for item in alert_items)


def test_temperature_alert_acknowledge_flow(client: TestClient) -> None:
    alerts = client.get("/api/v1/cold-chain/alerts?alert_status=open").json()["items"]
    assert alerts
    target = alerts[0]

    acknowledged = client.post(f"/api/v1/cold-chain/alerts/{target['id']}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_by"] == settings.admin_username

    again = client.post(f"/api/v1/cold-chain/alerts/{target['id']}/acknowledge")
    assert again.status_code == 200

    missing = client.post("/api/v1/cold-chain/alerts/999999/acknowledge")
    assert missing.status_code == 404


def test_cold_chain_overview_and_role_isolation(client: TestClient) -> None:
    overview = client.get("/api/v1/cold-chain/overview")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["shared_stores"] >= 6
    assert payload["active_sensors"] >= 6
    assert payload["reading_total"] > 0

    username = f"colduser_{uuid4().hex[:10]}"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": "冷链权限测试用户",
            "password": generated_strong_password(),
            "agreement_accepted": True,
        },
    )
    assert registered.status_code == 201
    user_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    assert client.get("/api/v1/cold-chain/stores", headers=user_headers).status_code == 403
    assert client.get("/api/v1/cold-chain/alerts", headers=user_headers).status_code == 403
    booking_attempt = client.post(
        "/api/v1/cold-chain/bookings",
        headers=user_headers,
        json={
            "cold_store_id": "CS-01",
            "booking_date": "2026-09-28",
            "purpose": "precool",
            "tons": 1,
        },
    )
    assert booking_attempt.status_code == 403
