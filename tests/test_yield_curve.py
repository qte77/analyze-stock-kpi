"""Tests for :mod:`src.data_sources.yield_curve` (#165).

Non-trivial cases only: slope computation invariants, multi-year UTC
grouping, wrap-degrade boundary policy on the yfinance ``^TNX`` /
``^FVX`` fetch. One ``@pytest.mark.network`` smoke confirms the live
integration still talks to Yahoo correctly.
"""

from __future__ import annotations

from datetime import date as date_cls
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pandas as pd
import pytest
from src.data_sources.yield_curve import (
    YieldCurveSnapshot,
    fetch_yield_curve_snapshot,
    merge_payload_into_years,
)

if TYPE_CHECKING:
    from pathlib import Path


# ----- YieldCurveSnapshot -----


def test_snapshot_computes_slope_when_both_legs_present() -> None:
    snap = YieldCurveSnapshot(
        date=date_cls(2026, 5, 30), tnx_yield=4.453, fvx_yield=4.149
    )
    assert snap.slope_5s10s == pytest.approx(0.304, abs=1e-9)


def test_snapshot_slope_is_none_when_either_leg_missing() -> None:
    only_tnx = YieldCurveSnapshot(
        date=date_cls(2026, 5, 30), tnx_yield=4.453, fvx_yield=None
    )
    only_fvx = YieldCurveSnapshot(
        date=date_cls(2026, 5, 30), tnx_yield=None, fvx_yield=4.149
    )
    neither = YieldCurveSnapshot(date=date_cls(2026, 5, 30))

    assert only_tnx.slope_5s10s is None
    assert only_fvx.slope_5s10s is None
    assert neither.slope_5s10s is None


def test_snapshot_slope_negative_on_inverted_curve() -> None:
    """During curve inversion TNX < FVX; slope must surface as negative."""
    snap = YieldCurveSnapshot(
        date=date_cls(2023, 7, 3), tnx_yield=3.85, fvx_yield=4.40
    )
    assert snap.slope_5s10s == pytest.approx(-0.55, abs=1e-9)


def test_snapshot_is_frozen() -> None:
    snap = YieldCurveSnapshot(
        date=date_cls(2026, 5, 30), tnx_yield=4.453, fvx_yield=4.149
    )
    with pytest.raises(Exception):
        snap.tnx_yield = 0.0  # type: ignore[misc]


# ----- merge_payload_into_years -----


def test_merge_groups_snapshots_by_utc_year(tmp_path: Path) -> None:
    snaps = [
        YieldCurveSnapshot(
            date=date_cls(2025, 12, 31), tnx_yield=4.0, fvx_yield=3.8
        ),
        YieldCurveSnapshot(
            date=date_cls(2026, 1, 2), tnx_yield=4.1, fvx_yield=3.9
        ),
    ]

    by_year = merge_payload_into_years(snaps, root=tmp_path)

    assert set(by_year.keys()) == {2025, 2026}
    assert "2025-12-31" in by_year[2025]
    assert "2026-01-02" in by_year[2026]


def test_merge_replaces_existing_same_date_with_newer_payload(
    tmp_path: Path,
) -> None:
    """A re-run should refresh a same-date entry, not duplicate it."""
    initial = [
        YieldCurveSnapshot(
            date=date_cls(2026, 5, 30), tnx_yield=4.0, fvx_yield=3.8
        )
    ]
    refresh = [
        YieldCurveSnapshot(
            date=date_cls(2026, 5, 30), tnx_yield=4.453, fvx_yield=4.149
        )
    ]
    merge_payload_into_years(initial, root=tmp_path)

    by_year = merge_payload_into_years(refresh, root=tmp_path)

    assert by_year[2026]["2026-05-30"].tnx_yield == 4.453
    assert by_year[2026]["2026-05-30"].fvx_yield == 4.149


# ----- fetch_yield_curve_snapshot — wrap-degrade boundary -----


def _fake_history(close_value: float | None) -> pd.DataFrame:
    """Mimic a one-row yfinance Ticker.history(period='1d') frame."""
    if close_value is None:
        return pd.DataFrame()
    return pd.DataFrame(
        {"Close": [close_value]},
        index=pd.to_datetime([date_cls(2026, 5, 30)]),
    )


def test_fetch_returns_snapshot_with_both_legs_on_happy_path() -> None:
    def _ticker_side_effect(sym: str) -> SimpleNamespace:
        closes = {"^TNX": 4.453, "^FVX": 4.149}
        return SimpleNamespace(history=lambda period: _fake_history(closes[sym]))

    with patch(
        "src.data_sources.yield_curve.yf.Ticker", side_effect=_ticker_side_effect
    ):
        snap = fetch_yield_curve_snapshot()

    assert snap is not None
    assert snap.tnx_yield == pytest.approx(4.453, abs=1e-9)
    assert snap.fvx_yield == pytest.approx(4.149, abs=1e-9)
    assert snap.slope_5s10s == pytest.approx(0.304, abs=1e-9)


def test_fetch_wrap_degrades_to_none_on_network_error() -> None:
    """Per docs/architecture.md boundary policy: yfinance failure must
    wrap-degrade (return None), never raise — daily cron then skips
    today's write rather than aborting."""
    with patch(
        "src.data_sources.yield_curve.yf.Ticker",
        side_effect=ConnectionError("yahoo timed out"),
    ):
        snap = fetch_yield_curve_snapshot()

    assert snap is None


def test_fetch_returns_sparse_snapshot_when_only_one_leg_responds() -> None:
    """If one leg returns and the other 404s, surface the partial reading
    rather than discarding everything — slope falls through to None."""

    def _ticker_side_effect(sym: str) -> SimpleNamespace:
        if sym == "^TNX":
            return SimpleNamespace(history=lambda period: _fake_history(4.453))
        return SimpleNamespace(history=lambda period: _fake_history(None))

    with patch(
        "src.data_sources.yield_curve.yf.Ticker", side_effect=_ticker_side_effect
    ):
        snap = fetch_yield_curve_snapshot()

    assert snap is not None
    assert snap.tnx_yield == pytest.approx(4.453, abs=1e-9)
    assert snap.fvx_yield is None
    assert snap.slope_5s10s is None


@pytest.mark.network
def test_live_fetch_yield_curve_snapshot() -> None:
    """One live round-trip — pins the contract that yfinance still ships
    ^TNX / ^FVX as percentage-point Close values."""
    snap = fetch_yield_curve_snapshot()
    assert snap is not None
    assert snap.tnx_yield is not None
    assert snap.fvx_yield is not None
    # 10y UST yield has been between 0.5% and 6.0% for the last 25 years;
    # anything outside that is a unit-shape drift (e.g. decimal not %).
    assert 0.1 < snap.tnx_yield < 10.0
    assert 0.1 < snap.fvx_yield < 10.0
