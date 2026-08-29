from datetime import datetime, timezone

from app.data.qidong_reference import build_reference_demo_orders
from app.schemas import Node, Order, Scenario, Vehicle

NODES = [
    Node(id="D-01", name="祁东县县域共配中心", longitude=112.1112, latitude=26.7871, kind="depot"),
    Node(id="P-HUANG", name="黄土铺镇黄花菜加工点", longitude=111.8610, latitude=26.8730, kind="processor"),
    Node(id="V-001", name="砖塘镇石山堰村服务站", longitude=112.916362, latitude=26.031622, kind="village"),
    Node(id="V-002", name="砖塘镇先锋村服务站", longitude=112.863461, latitude=26.074900, kind="village"),
    Node(id="V-003", name="河洲镇市门村服务站", longitude=112.790117, latitude=25.537430, kind="village"),
    Node(id="V-004", name="河洲镇三河村服务站", longitude=112.823451, latitude=25.489134, kind="village"),
    Node(id="V-005", name="步云桥镇拔茅冲村服务站", longitude=111.744691, latitude=27.030974, kind="village"),
    Node(id="V-006", name="石亭子镇梅塘村服务站", longitude=112.568725, latitude=26.316017, kind="village"),
    Node(id="V-007", name="城连圩乡永隆村服务站", longitude=111.906358, latitude=26.831572, kind="village"),
    Node(id="V-008", name="黄土铺镇双溪村服务站", longitude=113.045665, latitude=25.169133, kind="village"),
    Node(id="V-009", name="金桥镇金城村服务站", longitude=112.198416, latitude=26.618960, kind="village"),
    Node(id="V-010", name="灵官镇兴龙村服务站", longitude=112.372234, latitude=26.476762, kind="village"),
    Node(id="V-011", name="河洲镇定丰村服务站", longitude=112.756779, latitude=25.585366, kind="village"),
    Node(id="V-012", name="步云桥镇梅下村服务站", longitude=111.869347, latitude=26.872635, kind="village"),
    Node(id="V-013", name="太和堂镇罗口町村服务站", longitude=112.765216, latitude=26.155272, kind="village"),
    Node(id="V-014", name="灵官镇禄桥村服务站", longitude=112.311776, latitude=26.526222, kind="village"),
    Node(id="V-015", name="过水坪镇福缘村服务站", longitude=112.656780, latitude=25.729134, kind="village"),
    Node(id="V-016", name="白鹤街道罗云村服务站", longitude=112.141826, latitude=26.793541, kind="village"),
]

ORDERS = [
    # 参考需求只提供汇总量，不提供逐单时窗；演示场景统一使用当日 360 分钟服务窗，
    # 同时保留分批开始时间，确保 OSRM 矩阵下 16 单仍可审计、可重复求解。
    Order(id="O-001", node_id="V-001", weight_kg=1000, window_start=10, window_end=360, cold_chain=False),
    Order(id="O-002", node_id="V-002", weight_kg=1055, window_start=20, window_end=360, cold_chain=False),
    Order(id="O-003", node_id="V-003", weight_kg=794, window_start=30, window_end=360, cold_chain=True),
    Order(id="O-004", node_id="V-004", weight_kg=925, window_start=40, window_end=360, cold_chain=False),
    Order(id="O-005", node_id="V-005", weight_kg=975, window_start=50, window_end=360, cold_chain=False),
    Order(id="O-006", node_id="V-006", weight_kg=1040, window_start=60, window_end=360, cold_chain=True),
    Order(id="O-007", node_id="V-007", weight_kg=939, window_start=70, window_end=360, cold_chain=False),
    Order(id="O-008", node_id="V-008", weight_kg=860, window_start=80, window_end=360, cold_chain=False),
    Order(id="O-009", node_id="V-009", weight_kg=810, window_start=90, window_end=360, cold_chain=True),
    Order(id="O-010", node_id="V-010", weight_kg=630, window_start=100, window_end=360, cold_chain=False),
    Order(id="O-011", node_id="V-011", weight_kg=1205, window_start=110, window_end=360, cold_chain=False),
    Order(id="O-012", node_id="V-012", weight_kg=1364, window_start=120, window_end=360, cold_chain=True),
    Order(id="O-013", node_id="V-013", weight_kg=1390, window_start=130, window_end=360, cold_chain=False),
    Order(id="O-014", node_id="V-014", weight_kg=1255, window_start=140, window_end=360, cold_chain=False),
    Order(id="O-015", node_id="V-015", weight_kg=1395, window_start=150, window_end=360, cold_chain=True),
    Order(id="O-016", node_id="V-016", weight_kg=635, window_start=160, window_end=360, cold_chain=False),
]

VEHICLES = [
    Vehicle(id="V-COLD-01", plate="湘D·A1234", capacity_kg=2200, cold_chain=True, cost_per_km=4.3),
    Vehicle(id="V-COLD-02", plate="湘D·C2088", capacity_kg=4000, cold_chain=True, cost_per_km=4.1),
    Vehicle(id="V-NORM-01", plate="湘D·B5612", capacity_kg=2400, cost_per_km=3.2),
    Vehicle(id="V-NORM-02", plate="湘D·D3706", capacity_kg=2200, cost_per_km=3.1),
    Vehicle(id="V-NORM-03", plate="湘D·E9120", capacity_kg=1800, cost_per_km=2.9),
]

CALIBRATED_COORDINATES = {
    "D-01": (112.058674, 26.769788),
    "P-HUANG": (112.890116, 25.393251),
    "V-001": (112.916362, 26.031622),
    "V-002": (112.863461, 26.074900),
    "V-003": (112.790117, 25.537430),
    "V-004": (112.823451, 25.489134),
    "V-005": (111.744691, 27.030974),
    "V-006": (112.568725, 26.316017),
    "V-007": (111.906358, 26.831572),
    "V-008": (113.045665, 25.169133),
    "V-009": (112.198416, 26.618960),
    "V-010": (112.372234, 26.476762),
    "V-011": (112.756779, 25.585366),
    "V-012": (111.869347, 26.872635),
    "V-013": (112.765216, 26.155272),
    "V-014": (112.311776, 26.526222),
    "V-015": (112.656780, 25.729134),
    "V-016": (112.141826, 26.793541),
}

# The original user-editable coordinate table is retained for data-governance
# comparisons.  The standard route demo uses an in-county coordinate snapshot:
# valid township medians from the supplied station table are used where the
# table has trustworthy coverage, while the remaining points use the existing
# captured route snapshot.  This keeps the reference-driven order set on a
# coherent map instead of sending invalid source rows into the matrix.
ROUTE_DEMO_COORDINATES = {
    "D-01": (112.058674, 26.769788),
    "P-HUANG": (111.842611, 26.826567),
    "V-001": (111.830925, 26.812125),
    "V-002": (111.783743, 26.884902),
    "V-003": (111.795279, 26.898810),
    "V-004": (111.767924, 26.965734),
    "V-005": (111.814263, 26.927436),
    "V-006": (111.778131, 26.863189),
    "V-007": (111.937461, 26.776843),
    "V-008": (112.287473, 26.578338),
    "V-009": (112.179522, 26.634416),
    "V-010": (112.330669, 26.510766),
    "V-011": (112.081277, 26.714789),
    "V-012": (111.850833, 26.870851),
    "V-013": (112.078961, 26.561247),
    "V-014": (112.270012, 26.515686),
    "V-015": (111.936449, 26.789509),
    "V-016": (112.164195, 26.789895),
}

def get_scenario() -> Scenario:
    return Scenario(
        id="qidong-real-001",
        name="祁东县参考需求驱动城乡物流场景",
        nodes=[
            node.model_copy(
                deep=True,
                update={
                    "longitude": ROUTE_DEMO_COORDINATES.get(
                        node.id, CALIBRATED_COORDINATES[node.id]
                    )[0],
                    "latitude": ROUTE_DEMO_COORDINATES.get(
                        node.id, CALIBRATED_COORDINATES[node.id]
                    )[1],
                },
            )
            for node in NODES
        ],
        orders=build_reference_demo_orders(ORDERS),
        vehicles=[vehicle.model_copy(deep=True) for vehicle in VEHICLES],
        spatial_snapshot_id="spatial-real-20260823",
        spatial_snapshot_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        spatial_verified_nodes=len(NODES),
    )
