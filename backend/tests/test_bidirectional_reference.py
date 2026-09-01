import pytest

from app.data.bidirectional_reference import (
    BIDIRECTIONAL_DATASET_VERSION,
    DOWNWARD_MONTHLY_TONS,
    TOWNSHIP_NAMES,
    UPWARD_MONTHLY_TONS,
    annual_total,
    combined_monthly_series,
    top_townships,
    township_summary,
)


def test_bidirectional_reference_totals_reconcile() -> None:
    assert BIDIRECTIONAL_DATASET_VERSION == "qidong-bidirectional-2024-v1"
    assert len(TOWNSHIP_NAMES) == 24
    assert annual_total("upward") == pytest.approx(685000)
    assert annual_total("downward") == pytest.approx(523000)
    assert sum(UPWARD_MONTHLY_TONS) == pytest.approx(685000)
    assert sum(DOWNWARD_MONTHLY_TONS) == pytest.approx(523000)


def test_bidirectional_reference_exposes_directional_rankings() -> None:
    rows = township_summary()
    assert len(rows) == 24
    assert rows[0]["town_name"] == "洪桥街道"
    assert top_townships("upward")[0]["town_name"] == "白地市镇"
    assert top_townships("downward")[0]["town_name"] == "白地市镇"
    months = combined_monthly_series()
    assert len(months) == 12
    assert months[6]["month"] == "2024-07"
    assert months[6]["combined_tons"] == pytest.approx(131900)
