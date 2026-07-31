from datetime import datetime, timezone

from app.schemas import Node, Order, Scenario, Vehicle


NODES = [
    Node(id="D-01", name="祁东县县域共配中心", longitude=112.1112, latitude=26.7871, kind="depot"),
    Node(id="T-HONG", name="洪桥街道集散点", longitude=112.0900, latitude=26.8030, kind="town"),
    Node(id="T-HUANG", name="黄土铺镇加工点", longitude=111.8610, latitude=26.8730, kind="processor"),
    Node(id="T-BAIDI", name="白地市镇服务站", longitude=111.9970, latitude=26.9150, kind="town"),
    Node(id="T-GUAN", name="官家嘴镇产业园", longitude=111.7800, latitude=26.9440, kind="processor"),
    Node(id="T-BUYUN", name="步云桥镇服务站", longitude=111.6600, latitude=26.9180, kind="town"),
    Node(id="V-YINXING", name="银星村", longitude=111.8160, latitude=26.8870, kind="village"),
    Node(id="V-YANGMEI", name="杨梅村", longitude=111.7060, latitude=26.8460, kind="village"),
    Node(id="V-YOUSI", name="油丝塘村", longitude=111.6220, latitude=26.8990, kind="village"),
    Node(id="V-BAILA", name="白腊村", longitude=111.6480, latitude=26.9420, kind="village"),
    Node(id="V-GAOYE", name="高也塘村", longitude=111.7480, latitude=26.9730, kind="village"),
    Node(id="V-HUANGHUA", name="黄花町村", longitude=111.7350, latitude=26.8050, kind="village"),
    Node(id="V-LONGFENG", name="龙丰村", longitude=111.8920, latitude=26.8210, kind="village"),
    Node(id="V-CAIZI", name="彩子村", longitude=112.1800, latitude=26.7300, kind="village"),
    Node(id="V-TANJIA", name="谭家村", longitude=112.2050, latitude=26.6800, kind="village"),
    Node(id="V-CHANGYU", name="长玉村", longitude=112.0450, latitude=26.7000, kind="village"),
    Node(id="V-XINWAN", name="新湾村", longitude=112.2350, latitude=26.8030, kind="village"),
    Node(id="V-SHANGYI", name="尚义村", longitude=111.7650, latitude=26.8350, kind="village"),
]

ORDERS = [
    Order(id="O-001", node_id="V-YINXING", weight_kg=780, window_start=20, window_end=160, cold_chain=True),
    Order(id="O-002", node_id="V-YANGMEI", weight_kg=620, window_start=30, window_end=190),
    Order(id="O-003", node_id="V-YOUSI", weight_kg=560, window_start=0, window_end=180, cold_chain=True),
    Order(id="O-004", node_id="V-BAILA", weight_kg=460, window_start=50, window_end=230),
    Order(id="O-005", node_id="V-GAOYE", weight_kg=920, window_start=40, window_end=210, cold_chain=True),
    Order(id="O-006", node_id="V-HUANGHUA", weight_kg=680, window_start=60, window_end=260),
    Order(id="O-007", node_id="V-LONGFENG", weight_kg=510, window_start=20, window_end=210),
    Order(id="O-008", node_id="V-CAIZI", weight_kg=740, window_start=80, window_end=300),
    Order(id="O-009", node_id="V-TANJIA", weight_kg=590, window_start=100, window_end=330),
    Order(id="O-010", node_id="V-CHANGYU", weight_kg=870, window_start=60, window_end=260, cold_chain=True),
    Order(id="O-011", node_id="V-XINWAN", weight_kg=540, window_start=80, window_end=300),
    Order(id="O-012", node_id="V-SHANGYI", weight_kg=640, window_start=40, window_end=240),
]

VEHICLES = [
    Vehicle(id="V-COLD-01", plate="湘D·A1234", capacity_kg=2200, cold_chain=True, cost_per_km=4.3),
    # 预留故障演练余量：1 号冷链车故障后，2 号车仍能承接全部冷链订单。
    Vehicle(id="V-COLD-02", plate="湘D·C2088", capacity_kg=4000, cold_chain=True, cost_per_km=4.1),
    Vehicle(id="V-NORM-01", plate="湘D·B5612", capacity_kg=2400, cost_per_km=3.2),
    Vehicle(id="V-NORM-02", plate="湘D·D3706", capacity_kg=2200, cost_per_km=3.1),
    Vehicle(id="V-NORM-03", plate="湘D·E9120", capacity_kg=1800, cost_per_km=2.9),
]

CALIBRATED_COORDINATES = {
    "D-01": (112.058674, 26.769788),
    "T-HONG": (112.123865, 26.784523),
    "T-HUANG": (111.878265, 26.886139),
    "T-BAIDI": (111.951373, 26.779692),
    "T-GUAN": (111.844705, 26.935000),
    "T-BUYUN": (111.762612, 26.923266),
    "V-YINXING": (111.850833, 26.870851),
    "V-YANGMEI": (111.830925, 26.812125),
    "V-YOUSI": (111.783743, 26.884902),
    "V-BAILA": (111.795279, 26.898810),
    "V-GAOYE": (111.767924, 26.965734),
    "V-HUANGHUA": (111.854113, 26.851275),
    "V-LONGFENG": (111.778131, 26.863189),
    "V-CAIZI": (112.266339, 26.578509),
    "V-TANJIA": (112.287473, 26.578338),
    "V-CHANGYU": (111.963495, 26.713014),
    "V-XINWAN": (112.270012, 26.515686),
    "V-SHANGYI": (111.842611, 26.826567),
}


def get_scenario() -> Scenario:
    return Scenario(
        id="qidong-demo-001",
        name="祁东县黄花菜采收期城乡双向配送基础场景",
        nodes=[
            node.model_copy(
                deep=True,
                update={
                    "longitude": CALIBRATED_COORDINATES[node.id][0],
                    "latitude": CALIBRATED_COORDINATES[node.id][1],
                },
            )
            for node in NODES
        ],
        orders=[order.model_copy(deep=True) for order in ORDERS],
        vehicles=[vehicle.model_copy(deep=True) for vehicle in VEHICLES],
        spatial_snapshot_id="spatial-demo-20260729",
        spatial_snapshot_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        spatial_verified_nodes=len(NODES),
    )
