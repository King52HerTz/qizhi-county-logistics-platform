"""Normalized, source-free demand facts for the county bidirectional flow.

The supplied workbooks are kept outside the repository.  This module stores
only the reconciled township aggregates and monthly totals needed by the
application.  Values are expressed in tonnes; the operational demo converts
them to a small, deterministic same-day load separately.
"""

from __future__ import annotations

from collections.abc import Iterable


BIDIRECTIONAL_DATASET_VERSION = "qidong-bidirectional-2024-v1"
MONTH_KEYS: tuple[str, ...] = tuple(f"2024-{month:02d}" for month in range(1, 13))

# The order follows the township summary workbooks and is shared by both
# directions.  It includes the four county streets and twenty townships.
TOWNSHIP_NAMES: tuple[str, ...] = (
    "洪桥街道",
    "玉合街道",
    "永昌街道",
    "白鹤街道",
    "步云桥镇",
    "白地市镇",
    "风石堰镇",
    "太和堂镇",
    "黄土铺镇",
    "过水坪镇",
    "金桥镇",
    "蒋家桥镇",
    "归阳镇",
    "砖塘镇",
    "灵官镇",
    "官家嘴镇",
    "双桥镇",
    "河洲镇",
    "鸟江镇",
    "石亭子镇",
    "城连圩乡",
    "粮市镇",
    "马杜桥乡",
    "凤歧坪乡",
)

# Annual totals from the township aggregate sheets.  They reconcile to the
# village detail sheets after converting tonnes to 10,000-tonne units.
UPWARD_ANNUAL_TONS: tuple[float, ...] = (
    31700,
    11800,
    12600,
    19400,
    52100,
    79600,
    37400,
    37900,
    61000,
    31900,
    38100,
    26200,
    27400,
    37100,
    21900,
    40600,
    21000,
    18400,
    16800,
    25200,
    14200,
    9300,
    8000,
    5400,
)

DOWNWARD_ANNUAL_TONS: tuple[float, ...] = (
    24200,
    9000,
    9600,
    14800,
    39800,
    60800,
    28500,
    29000,
    46600,
    24400,
    29100,
    20000,
    20900,
    28300,
    16700,
    31000,
    16000,
    14100,
    12800,
    19200,
    10900,
    7100,
    6100,
    4100,
)

# Monthly totals in tonnes.  These are kept independently of the township
# rows so the forecast layer can use the original rounded monthly series.
UPWARD_MONTHLY_TONS: tuple[float, ...] = (
    67900,
    41500,
    41500,
    48300,
    47500,
    54600,
    90200,
    82200,
    60900,
    54200,
    48100,
    48100,
)

DOWNWARD_MONTHLY_TONS: tuple[float, ...] = (
    57700,
    37000,
    47000,
    41500,
    41700,
    41800,
    41700,
    41300,
    46900,
    42000,
    42000,
    42400,
)


def _validate_dimensions() -> None:
    if len(TOWNSHIP_NAMES) != len(UPWARD_ANNUAL_TONS):
        raise RuntimeError("上行乡镇与年度数据行数不一致")
    if len(TOWNSHIP_NAMES) != len(DOWNWARD_ANNUAL_TONS):
        raise RuntimeError("下行乡镇与年度数据行数不一致")
    if len(MONTH_KEYS) != len(UPWARD_MONTHLY_TONS) or len(MONTH_KEYS) != len(
        DOWNWARD_MONTHLY_TONS
    ):
        raise RuntimeError("双向月度数据必须覆盖完整 12 个月")


_validate_dimensions()


def annual_total(direction: str) -> float:
    values = UPWARD_ANNUAL_TONS if direction == "upward" else DOWNWARD_ANNUAL_TONS
    return float(sum(values))


def monthly_series(direction: str) -> list[dict[str, float | str]]:
    values = UPWARD_MONTHLY_TONS if direction == "upward" else DOWNWARD_MONTHLY_TONS
    return [
        {"month": month, "tons": float(value)}
        for month, value in zip(MONTH_KEYS, values, strict=True)
    ]


def township_summary() -> list[dict[str, float | str]]:
    return [
        {
            "town_name": town_name,
            "upward_tons": float(upward),
            "downward_tons": float(downward),
            "combined_tons": float(upward + downward),
        }
        for town_name, upward, downward in zip(
            TOWNSHIP_NAMES,
            UPWARD_ANNUAL_TONS,
            DOWNWARD_ANNUAL_TONS,
            strict=True,
        )
    ]


def top_townships(direction: str, limit: int = 6) -> list[dict[str, float | str]]:
    key = "upward_tons" if direction == "upward" else "downward_tons"
    return sorted(township_summary(), key=lambda item: float(item[key]), reverse=True)[:limit]


def combined_monthly_series() -> list[dict[str, float | str]]:
    return [
        {
            "month": month,
            "upward_tons": float(upward),
            "downward_tons": float(downward),
            "combined_tons": float(upward + downward),
        }
        for month, upward, downward in zip(
            MONTH_KEYS,
            UPWARD_MONTHLY_TONS,
            DOWNWARD_MONTHLY_TONS,
            strict=True,
        )
    ]


def reconcile_totals(values: Iterable[float]) -> float:
    """Return a rounded total for import/reconciliation checks."""

    return round(sum(float(value) for value in values), 1)
