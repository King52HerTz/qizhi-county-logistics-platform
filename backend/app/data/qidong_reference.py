"""Curated, source-free reference facts for the Qidong planning baseline.

The raw research files remain outside the repository.  This module contains only
the small, reviewable aggregates that are safe to use at runtime: the latest
30-minute AHP-GIS weights, candidate station ranking, and township demand
summary.  It deliberately does not import the station workbook coordinates;
that workbook contains a suspicious monotonic coordinate sequence that requires
manual/geocoded verification before it can drive a map or a route matrix.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.data.bidirectional_reference import (
    BIDIRECTIONAL_DATASET_VERSION,
    DOWNWARD_MONTHLY_TONS,
    UPWARD_MONTHLY_TONS,
    annual_total,
    township_summary,
)
from app.schemas import Order, Scenario
from app.spatial import inside_qidong_bounds


REFERENCE_DATASET_VERSION = "qidong-ahp-gis-30min-2026-v1"
REFERENCE_SOURCE_SCOPE = (
    "三级物流设施研究（第一版/第四章优化版） + 最新 AHP-GIS 选址结果 + 乡镇需求汇总"
)
SERVICE_CIRCLE_MINUTES = 30
TOWNSHIP_COUNT = 24
VILLAGE_UNITS = 367
TOWN_LOGISTICS_STATIONS = 24
TOWNSHIP_ECOMMERCE_STATIONS = 24
FIELD_COLD_STORES = 95
VILLAGE_SERVICE_STATIONS = 300
CO_DELIVERY_STATIONS = 197
COUNTY_FACILITY_COUNT = 5
ROAD_TOTAL_KM = 3836.743
ROAD_DENSITY_KM_PER_SQ_KM = 1.93
VILLAGE_COVERAGE_PERCENT = round(VILLAGE_SERVICE_STATIONS / VILLAGE_UNITS * 100, 2)

# These are the operational facts that can be safely surfaced from the two
# newly supplied facility-study documents.  They describe the existing network
# and its gaps; they are not additional route nodes or fabricated coordinates.
FACILITY_SUMMARY: tuple[dict[str, int | float | str], ...] = (
    {
        "level": "县级",
        "name": "县级综合物流设施",
        "count": COUNTY_FACILITY_COUNT,
        "status": "4个运营/1个在建",
        "function": "综合枢纽、寄递共配、电商服务、冷链和现代农业物流园",
    },
    {
        "level": "乡镇级",
        "name": "乡镇寄递物流综合服务站",
        "count": TOWN_LOGISTICS_STATIONS,
        "status": "24个乡镇（街道）全覆盖",
        "function": "快递收寄、农产品上行、工业品下乡和客货邮接驳",
    },
    {
        "level": "乡镇级",
        "name": "乡镇电商物流站",
        "count": TOWNSHIP_ECOMMERCE_STATIONS,
        "status": "24个乡镇（街道）全覆盖",
        "function": "电商销售、直播带货、代收代发和农资下乡",
    },
    {
        "level": "村级",
        "name": "村级寄递物流综合服务站",
        "count": VILLAGE_SERVICE_STATIONS,
        "coverage_percent": VILLAGE_COVERAGE_PERCENT,
        "status": "已完成县级验收",
        "function": "快递收发、农产品代收代销和农资配送",
    },
    {
        "level": "末端冷链",
        "name": "产地保鲜仓/田间冷库",
        "count": FIELD_COLD_STORES,
        "status": "覆盖13个农业重点乡镇",
        "function": "田头预冷、保鲜仓储、分级分拣和干线外销",
    },
)

FACILITY_GAPS: tuple[str, ...] = (
    "约20%的行政村尚未配置标准化村级综合服务站（按300/367测算）。",
    "95座田间冷库主要覆盖13个农业重点乡镇，其余乡镇仍需补充冷链节点。",
    "县级电商公共服务中心偏重孵化展示，大规模农产品中转、仓配和加工能力仍需补强。",
)

# The supplied workbook is an aggregate demand baseline rather than a stream of
# same-day orders.  For the deterministic demo scenario we normalize it to
# 0.15% of the reference period (about 8.3 t), which keeps the load realistic
# for the seeded five-vehicle fleet without presenting the aggregate as a live
# dispatch quantity.
DEMO_LOAD_RATIO = 0.0015
DEMO_LOAD_PERCENT = DEMO_LOAD_RATIO * 100

# The current scenario already has a stable set of 16 route nodes.  These
# groups map all 24 township aggregates onto that stable route skeleton.  A
# town can be split between two existing route nodes, but the fractions below
# always sum to one for each town.  The mapping is intentionally explicit and
# reviewable; it does not import the raw station workbook or invent new
# coordinates for towns whose rows need geocoding verification.
REFERENCE_ORDER_TOWN_ALLOCATIONS: dict[str, dict[str, float]] = {
    "V-001": {"砖塘镇": 0.5, "鸟江镇": 1.0},
    "V-002": {"砖塘镇": 0.5, "白地市镇": 1.0},
    "V-003": {"河洲镇": 0.4, "归阳镇": 1.0},
    "V-004": {"河洲镇": 0.3, "双桥镇": 1.0},
    "V-005": {"步云桥镇": 0.5, "凤歧坪乡": 1.0},
    "V-006": {"石亭子镇": 1.0, "官家嘴镇": 1.0},
    "V-007": {"城连圩乡": 1.0, "风石堰镇": 1.0},
    "V-008": {"黄土铺镇": 1.0},
    "V-009": {"金桥镇": 1.0, "粮市镇": 1.0, "洪桥街道": 1.0},
    "V-010": {"灵官镇": 0.5, "马杜桥乡": 1.0},
    "V-011": {"河洲镇": 0.3, "蒋家桥镇": 1.0},
    "V-012": {"步云桥镇": 0.5, "永昌街道": 1.0},
    "V-013": {"太和堂镇": 1.0, "玉合街道": 1.0},
    "V-014": {"灵官镇": 0.5},
    "V-015": {"过水坪镇": 1.0},
    "V-016": {"白鹤街道": 1.0},
}

COLD_CHAIN_TOWNS = frozenset(
    {
        "太和堂镇",
        "步云桥镇",
        "白地市镇",
        "过水坪镇",
        "石亭子镇",
        "黄土铺镇",
        "凤歧坪乡",
    }
)


# Deterministic, non-personal demo customer profiles for the 16 standard
# orders.  Names and contact numbers are fictional, while products and
# delivery locations follow the county service-node context.
REFERENCE_ORDER_PROFILES: dict[str, dict[str, str]] = {
    "O-001": {"cargo_name": "鲜黄花菜", "customer_name": "石山堰黄花菜种植合作社", "customer_phone": "0734-6001001", "delivery_address": "祁东县砖塘镇石山堰村综合服务站"},
    "O-002": {"cargo_name": "油茶籽", "customer_name": "先锋村农副产品服务部", "customer_phone": "0734-6001002", "delivery_address": "祁东县砖塘镇先锋村便民服务点"},
    "O-003": {"cargo_name": "生鲜蔬菜", "customer_name": "市门村蔬菜产销合作社", "customer_phone": "0734-6001003", "delivery_address": "祁东县河洲镇市门村冷链收货区"},
    "O-004": {"cargo_name": "优质稻米", "customer_name": "三河村粮食加工合作社", "customer_phone": "0734-6001004", "delivery_address": "祁东县河洲镇三河村粮食服务点"},
    "O-005": {"cargo_name": "高山果蔬", "customer_name": "拔茅冲村果蔬合作社", "customer_phone": "0734-6001005", "delivery_address": "祁东县步云桥镇拔茅冲村集配点"},
    "O-006": {"cargo_name": "黄花菜鲜品", "customer_name": "梅塘村黄花菜合作社", "customer_phone": "0734-6001006", "delivery_address": "祁东县石亭子镇梅塘村产地预冷点"},
    "O-007": {"cargo_name": "油茶籽", "customer_name": "永隆村油茶产业合作社", "customer_phone": "0734-6001007", "delivery_address": "祁东县城连圩乡永隆村综合服务站"},
    "O-008": {"cargo_name": "黄花菜干品", "customer_name": "双溪村黄花菜加工点", "customer_phone": "0734-6001008", "delivery_address": "祁东县黄土铺镇双溪村加工区"},
    "O-009": {"cargo_name": "农资用品", "customer_name": "金城村农资配送服务点", "customer_phone": "0734-6001009", "delivery_address": "祁东县金桥镇金城村农资服务站"},
    "O-010": {"cargo_name": "油茶制品", "customer_name": "兴龙村油茶产销合作社", "customer_phone": "0734-6001010", "delivery_address": "祁东县灵官镇兴龙村综合服务站"},
    "O-011": {"cargo_name": "优质稻米", "customer_name": "定丰村优质稻合作社", "customer_phone": "0734-6001011", "delivery_address": "祁东县河洲镇定丰村粮食收储点"},
    "O-012": {"cargo_name": "生鲜果蔬", "customer_name": "梅下村生鲜集配服务点", "customer_phone": "0734-6001012", "delivery_address": "祁东县步云桥镇梅下村冷链交付区"},
    "O-013": {"cargo_name": "黄花菜鲜品", "customer_name": "罗口町村黄花菜合作社", "customer_phone": "0734-6001013", "delivery_address": "祁东县太和堂镇罗口町村产地仓"},
    "O-014": {"cargo_name": "粮油产品", "customer_name": "禄桥村粮油综合服务站", "customer_phone": "0734-6001014", "delivery_address": "祁东县灵官镇禄桥村综合服务站"},
    "O-015": {"cargo_name": "时令果蔬", "customer_name": "福缘村果蔬产销合作社", "customer_phone": "0734-6001015", "delivery_address": "祁东县过水坪镇福缘村冷链收货点"},
    "O-016": {"cargo_name": "社区团购商品", "customer_name": "罗云村社区配送服务点", "customer_phone": "0734-6001016", "delivery_address": "祁东县白鹤街道罗云村综合服务站"},
}


def reference_order_profile(order_id: str) -> dict[str, str] | None:
    """Return a copy so callers cannot mutate the reference baseline."""

    profile = REFERENCE_ORDER_PROFILES.get(order_id)
    return dict(profile) if profile else None


# Fixed, fictional customer applications used to demonstrate the approval
# workflow.  They intentionally remain pending so an administrator can review
# them without changing the standard operating orders.
REFERENCE_ORDER_REQUESTS: tuple[dict[str, object], ...] = (
    {
        "request_code": "UR-20260831-D001",
        "node_id": "V-006",
        "cargo_name": "鲜黄花菜",
        "customer_name": "金源黄花菜产销合作社",
        "customer_phone": "0734-6102001",
        "delivery_address": "祁东县石亭子镇梅塘村冷链收货点",
        "weight_kg": 280,
        "window_start": 480,
        "window_end": 660,
        "service_minutes": 12,
        "cold_chain": True,
        "priority": "urgent",
    },
    {
        "request_code": "UR-20260831-D002",
        "node_id": "V-009",
        "cargo_name": "优质稻米",
        "customer_name": "金城粮食产销合作社",
        "customer_phone": "0734-6102002",
        "delivery_address": "祁东县金桥镇金城村粮食服务站",
        "weight_kg": 420,
        "window_start": 540,
        "window_end": 780,
        "service_minutes": 10,
        "cold_chain": False,
        "priority": "normal",
    },
    {
        "request_code": "UR-20260831-D003",
        "node_id": "V-015",
        "cargo_name": "时令果蔬",
        "customer_name": "福缘生鲜集配中心",
        "customer_phone": "0734-6102003",
        "delivery_address": "祁东县过水坪镇福缘村冷链收货点",
        "weight_kg": 360,
        "window_start": 450,
        "window_end": 630,
        "service_minutes": 15,
        "cold_chain": True,
        "priority": "normal",
    },
    {
        "request_code": "UR-20260831-D004",
        "node_id": "V-016",
        "cargo_name": "农资用品",
        "customer_name": "罗云村便民服务站",
        "customer_phone": "0734-6102004",
        "delivery_address": "祁东县白鹤街道罗云村综合服务站",
        "weight_kg": 160,
        "window_start": 600,
        "window_end": 840,
        "service_minutes": 8,
        "cold_chain": False,
        "priority": "normal",
    },
)


AHP_WEIGHTS: tuple[dict[str, float | str], ...] = (
    {"code": "C1", "label": "坡度", "weight": 0.109},
    {"code": "C2", "label": "海拔", "weight": 0.055},
    {"code": "C3", "label": "路网密度", "weight": 0.359},
    {"code": "C4", "label": "服务半径", "weight": 0.180},
    {"code": "C5", "label": "农业覆盖", "weight": 0.223},
    {"code": "C6", "label": "工业布局", "weight": 0.074},
)


# Demand values are the aggregate sample values from the supplied township
# demand workbook and are expressed in tonnes.  They are reference baselines,
# not live order totals.
TOWNSHIP_DEMAND: tuple[dict[str, float | int | str], ...] = (
    {"town_name": "太和堂镇", "village_count": 27, "demand_tons": 562.5},
    {"town_name": "步云桥镇", "village_count": 23, "demand_tons": 457.0},
    {"town_name": "白地市镇", "village_count": 20, "demand_tons": 408.8},
    {"town_name": "过水坪镇", "village_count": 19, "demand_tons": 401.1},
    {"town_name": "金桥镇", "village_count": 16, "demand_tons": 352.1},
    {"town_name": "砖塘镇", "village_count": 15, "demand_tons": 307.5},
    {"town_name": "蒋家桥镇", "village_count": 15, "demand_tons": 300.3},
    {"town_name": "黄土铺镇", "village_count": 15, "demand_tons": 289.6},
    {"town_name": "河洲镇", "village_count": 16, "demand_tons": 288.7},
    {"town_name": "风石堰镇", "village_count": 16, "demand_tons": 288.2},
    {"town_name": "官家嘴镇", "village_count": 13, "demand_tons": 249.9},
    {"town_name": "归阳镇", "village_count": 11, "demand_tons": 245.1},
    {"town_name": "白鹤街道", "village_count": 18, "demand_tons": 221.9},
    {"town_name": "石亭子镇", "village_count": 12, "demand_tons": 213.2},
    {"town_name": "灵官镇", "village_count": 13, "demand_tons": 194.0},
    {"town_name": "鸟江镇", "village_count": 10, "demand_tons": 182.1},
    {"town_name": "城连圩乡", "village_count": 9, "demand_tons": 139.2},
    {"town_name": "粮市镇", "village_count": 8, "demand_tons": 120.8},
    {"town_name": "双桥镇", "village_count": 5, "demand_tons": 88.6},
    {"town_name": "永昌街道", "village_count": 5, "demand_tons": 79.5},
    {"town_name": "马杜桥乡", "village_count": 6, "demand_tons": 63.0},
    {"town_name": "凤歧坪乡", "village_count": 5, "demand_tons": 60.9},
    {"town_name": "洪桥街道", "village_count": 2, "demand_tons": 27.2},
    {"town_name": "玉合街道", "village_count": 1, "demand_tons": 15.3},
)


def build_reference_demo_orders(orders: Iterable[Order]) -> list[Order]:
    """Apply the reference demand baseline to the stable route-node skeleton.

    This function is deliberately pure: it returns copies and leaves the
    scenario constants untouched, so reset/test runs always produce the same
    order ids, windows and mapping.  Orders whose node is not part of the
    explicit mapping are preserved, which keeps imported/custom scenarios
    backwards compatible.
    """

    demand_by_town = {
        str(item["town_name"]): float(item["demand_tons"])
        for item in TOWNSHIP_DEMAND
    }
    reference_orders: list[Order] = []
    for order in orders:
        town_allocations = REFERENCE_ORDER_TOWN_ALLOCATIONS.get(order.node_id)
        if not town_allocations:
            reference_orders.append(order.model_copy(deep=True))
            continue
        aggregate_tons = sum(
            demand_by_town[town] * share
            for town, share in town_allocations.items()
        )
        weight_kg = max(1, round(aggregate_tons * 1000 * DEMO_LOAD_RATIO))
        reference_orders.append(
            order.model_copy(
                deep=True,
                update={
                    "weight_kg": weight_kg,
                    "cold_chain": any(
                        town in COLD_CHAIN_TOWNS for town in town_allocations
                    ),
                },
            )
        )
    return reference_orders


CANDIDATE_STATIONS: tuple[dict[str, float | int | str], ...] = (
    {"rank": 1, "town_name": "石亭子镇", "score": 7.631, "level": "I级极适宜", "candidate_type": "core", "rationale": "农业覆盖高，黄花菜核心产区，服务半径优"},
    {"rank": 2, "town_name": "鸟江镇", "score": 7.544, "level": "I级极适宜", "candidate_type": "core", "rationale": "路网密度高，邻近归阳高新区，工业协同好"},
    {"rank": 3, "town_name": "砖塘镇", "score": 7.541, "level": "I级极适宜", "candidate_type": "core", "rationale": "农业覆盖与路网条件较好，适合中部节点"},
    {"rank": 4, "town_name": "河洲镇", "score": 7.499, "level": "I级极适宜", "candidate_type": "core", "rationale": "东南沿江区位，路网与高程条件优"},
    {"rank": 5, "town_name": "过水坪镇", "score": 7.484, "level": "I级极适宜", "candidate_type": "core", "rationale": "南部岗地路网较高，农业需求较大"},
    {"rank": 6, "town_name": "金桥镇", "score": 7.480, "level": "I级极适宜", "candidate_type": "core", "rationale": "路网密度较高，邻近归阳园区，区位适中"},
    {"rank": 7, "town_name": "白地市镇", "score": 7.406, "level": "I级极适宜", "candidate_type": "core", "rationale": "工业集聚区所在地，需求量大，农产覆盖高"},
    {"rank": 8, "town_name": "双桥镇", "score": 7.321, "level": "I级极适宜", "candidate_type": "core", "rationale": "地形平缓，指标均衡，适合中部节点"},
    {"rank": 9, "town_name": "归阳镇", "score": 7.209, "level": "I级极适宜", "candidate_type": "core", "rationale": "高新区所在地，路网和工业协同最强"},
    {"rank": 10, "town_name": "城连圩乡", "score": 6.663, "level": "II级适宜", "candidate_type": "core", "rationale": "西部农业带，农产覆盖和服务半径较好"},
    {"rank": 11, "town_name": "风石堰镇", "score": 6.409, "level": "II级适宜", "candidate_type": "core", "rationale": "距离白地市园区较近，具备区域集散价值"},
    {"rank": 12, "town_name": "蒋家桥镇", "score": 6.077, "level": "II级适宜", "candidate_type": "core", "rationale": "西部山区农业节点，服务半径和货源较好"},
    {"rank": 13, "town_name": "官家嘴镇", "score": 5.464, "level": "III级一般适宜", "candidate_type": "remote_safeguard", "rationale": "偏远山区核心油茶产区，承担兜底保障"},
    {"rank": 14, "town_name": "步云桥镇", "score": 5.073, "level": "III级一般适宜", "candidate_type": "remote_safeguard", "rationale": "西北区域中心，辖村多，服务半径广"},
    {"rank": 15, "town_name": "凤歧坪乡", "score": 3.323, "level": "V级不适宜", "candidate_type": "remote_safeguard", "rationale": "最偏远乡镇，保留基本公共物流服务"},
)


def _coordinate_quality(scenario: Scenario) -> dict[str, object]:
    coordinate_groups: defaultdict[tuple[float, float], list[str]] = defaultdict(list)
    outside_ids: list[str] = []
    for node in scenario.nodes:
        coordinate = (round(node.longitude, 6), round(node.latitude, 6))
        coordinate_groups[coordinate].append(node.id)
        if not inside_qidong_bounds(node.longitude, node.latitude):
            outside_ids.append(node.id)

    duplicate_ids = sorted(
        node_id
        for node_ids in coordinate_groups.values()
        if len(node_ids) > 1
        for node_id in node_ids
    )
    flagged_ids = sorted(set(outside_ids).union(duplicate_ids))
    if outside_ids and duplicate_ids:
        note = "当前场景存在超出祁东县边界或重复坐标，请在空间校准中核验。"
    elif outside_ids:
        note = "当前场景存在超出祁东县边界的坐标，请在空间校准中核验。"
    elif duplicate_ids:
        note = "当前场景存在重复坐标，请在空间校准中核验网点是否应合并。"
    else:
        note = "当前场景坐标均在祁东县边界内且无重复。"
    return {
        "total_nodes": len(scenario.nodes),
        "inside_bounds": len(scenario.nodes) - len(outside_ids),
        "outside_bounds": len(outside_ids),
        "duplicate_nodes": len(duplicate_ids),
        "flagged_node_ids": flagged_ids,
        "status": "needs_review" if flagged_ids else "verified",
        "note": note,
    }


def build_qidong_reference_summary(scenario: Scenario) -> dict[str, object]:
    total_demand = sum(float(item["demand_tons"]) for item in TOWNSHIP_DEMAND)
    demand_by_town = {
        str(item["town_name"]): float(item["demand_tons"])
        for item in TOWNSHIP_DEMAND
    }
    demand_summary = [
        {
            **item,
            "share_percent": round(float(item["demand_tons"]) / total_demand * 100, 2),
        }
        for item in sorted(
            TOWNSHIP_DEMAND,
            key=lambda value: float(value["demand_tons"]),
            reverse=True,
        )[:6]
    ]
    candidates = [
        {**candidate, "demand_tons": demand_by_town.get(str(candidate["town_name"]))}
        for candidate in CANDIDATE_STATIONS
    ]
    return {
        "dataset_version": REFERENCE_DATASET_VERSION,
        "source_scope": REFERENCE_SOURCE_SCOPE,
        "service_circle_minutes": SERVICE_CIRCLE_MINUTES,
        "township_count": TOWNSHIP_COUNT,
        "village_units": VILLAGE_UNITS,
        "town_logistics_stations": TOWN_LOGISTICS_STATIONS,
        "township_ecommerce_stations": TOWNSHIP_ECOMMERCE_STATIONS,
        "field_cold_stores": FIELD_COLD_STORES,
        "village_service_stations": VILLAGE_SERVICE_STATIONS,
        "co_delivery_stations": CO_DELIVERY_STATIONS,
        "county_facility_count": COUNTY_FACILITY_COUNT,
        "village_coverage_percent": VILLAGE_COVERAGE_PERCENT,
        "road_total_km": ROAD_TOTAL_KM,
        "road_density_km_per_sq_km": ROAD_DENSITY_KM_PER_SQ_KM,
        "demand_unit": "吨",
        "reference_demand_tons": round(total_demand, 1),
        "bidirectional_dataset_version": BIDIRECTIONAL_DATASET_VERSION,
        "upward_reference_tons": annual_total("upward"),
        "downward_reference_tons": annual_total("downward"),
        "upward_monthly_tons": list(UPWARD_MONTHLY_TONS),
        "downward_monthly_tons": list(DOWNWARD_MONTHLY_TONS),
        "directional_demand_summary": township_summary(),
        "demo_load_ratio": DEMO_LOAD_RATIO,
        "demo_order_count": len(scenario.orders),
        "demo_order_weight_kg": sum(order.weight_kg for order in scenario.orders),
        "demo_mapped_town_count": len(
            {
                town
                for town_allocations in REFERENCE_ORDER_TOWN_ALLOCATIONS.values()
                for town in town_allocations
            }
        ),
        "demand_summary": demand_summary,
        "ahp_weights": list(AHP_WEIGHTS),
        "candidates": candidates,
        "facility_summary": [dict(item) for item in FACILITY_SUMMARY],
        "facility_gaps": list(FACILITY_GAPS),
        "coordinate_quality": _coordinate_quality(scenario),
        "notes": [
            "选址基线采用最新资料中的30分钟服务圈；旧版60分钟口径不作为当前运行基线。",
            "设施现状采用新增两份研究资料中的县、乡、村三级统计口径；共配站点197个是300个村级站点中的运营协同子集。",
            f"县域公路总里程 {ROAD_TOTAL_KM:.3f} km，平均路网密度 {ROAD_DENSITY_KM_PER_SQ_KM:.2f} km/km²，作为研究基线展示，不直接替代实时路网矩阵。",
            "站点表中的可疑经纬度序列未直接导入地图或路网矩阵。",
            f"运营演示订单按资料汇总的 {DEMO_LOAD_PERCENT:.2f}% 归一化为当日载荷（{sum(order.weight_kg for order in scenario.orders)} kg），用于稳定求解，不代表原始期间总量。",
            "24 个乡镇需求通过显式映射汇总到稳定路线节点；坐标仍以已校准场景节点为准。",
            "双向事实层来自2024年乡镇/月度汇总与村级明细对账：农产品上行685000吨、工业品下行523000吨。",
        ],
    }
