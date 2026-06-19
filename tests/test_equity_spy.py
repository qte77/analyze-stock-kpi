"""Tests for :mod:`analyze_stock_kpi.data_sources.equity_spy` (#288).

Non-trivial cases only: the indexed-return transform (rebase to epoch = 100),
the pre-`_START` window + NaN-drop on the yfinance fetch, the wrap-degrade
boundary, and multi-year UTC grouping. One ``@pytest.mark.network`` smoke pins
the live SPY contract. Derived-only (ADR-0011): snapshots carry ``ret_indexed``,
never the raw close.
"""

from __future__ import annotations

from datetime import date as date_cls
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pandas as pd
import pytest
from pydantic import ValidationError

from analyze_stock_kpi.data_sources.equity_spy import (
    EquitySpySnapshot,
    fetch_equity_spy_history,
    index_returns,
    merge_payload_into_years,
)

if TYPE_CHECKING:
    from pathlib import Path


# ----- index_returns: rebase-to-100 transform -----


def test_index_returns_rebases_earliest_close_to_100() -> None:
    out = index_returns({date_cls(2011, 1, 3): 127.05})
    assert len(out) == 1
    assert out[0].ret_indexed == pytest.approx(100.0, abs=1e-9)


def test_index_returns_scales_relative_to_epoch() -> None:
    # earliest (epoch) close 50 -> 100; doubling -> 200; halving -> 50.
    out = index_returns(
        {
            date_cls(2011, 1, 3): 50.0,
            date_cls(2015, 6, 1): 100.0,
            date_cls(2020, 6, 1): 25.0,
        }
    )
    by_date = {s.date: s.ret_indexed for s in out}
    assert by_date[date_cls(2011, 1, 3)] == pytest.approx(100.0)
    assert by_date[date_cls(2015, 6, 1)] == pytest.approx(200.0)
    assert by_date[date_cls(2020, 6, 1)] == pytest.approx(50.0)


def test_index_returns_epoch_is_earliest_date_regardless_of_input_order() -> None:
    out = index_returns({date_cls(2020, 1, 1): 200.0, date_cls(2011, 1, 1): 100.0})
    assert [s.date for s in out] == [date_cls(2011, 1, 1), date_cls(2020, 1, 1)]
    assert out[0].ret_indexed == pytest.approx(100.0)
    assert out[-1].ret_indexed == pytest.approx(200.0)


def test_index_returns_empty_input_returns_empty() -> None:
    assert index_returns({}) == []


def test_index_returns_guards_nonpositive_epoch() -> None:
    # A zero/negative epoch close can't define a ratio; return empty rather
    # than dividing by zero or emitting inf.
    assert index_returns({date_cls(2011, 1, 1): 0.0, date_cls(2012, 1, 1): 10.0}) == []


def test_snapshot_is_frozen() -> None:
    snap = EquitySpySnapshot(date=date_cls(2011, 1, 3), ret_indexed=100.0)
    with pytest.raises(ValidationError, match="frozen"):
        snap.ret_indexed = 0.0  # type: ignore[misc]


# ----- fetch_equity_spy_history: window + NaN-drop + wrap-degrade -----


def _history_frame(rows: list[tuple[date_cls, float | None]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    dates = pd.to_datetime([d for d, _ in rows])
    closes = [c for _, c in rows]
    return pd.DataFrame({"Close": closes}, index=dates)


def test_fetch_history_wrap_degrades_to_empty_on_network_error() -> None:
    """yfinance failure must wrap-degrade (return []), never raise — the cron
    then skips the write rather than aborting (docs/architecture.md)."""
    with patch(
        "analyze_stock_kpi.data_sources.equity_spy.yf.Ticker",
        side_effect=ConnectionError("yahoo timed out"),
    ):
        assert fetch_equity_spy_history() == []


def test_fetch_history_drops_pre_2011_rows_then_rebases_to_2011_epoch() -> None:
    """SPY history reaches 1993, but the series aligns to ~2011 — the epoch is
    the first close >= _START, so pre-2011 rows are dropped before indexing."""

    def _ticker(_sym: str) -> SimpleNamespace:
        frame = _history_frame(
            [
                (date_cls(1993, 1, 29), 25.0),  # pre-2011 -> dropped
                (date_cls(2011, 1, 3), 100.0),  # epoch -> 100
                (date_cls(2020, 1, 2), 300.0),  # -> 300
            ]
        )
        return SimpleNamespace(history=lambda period: frame)

    with patch("analyze_stock_kpi.data_sources.equity_spy.yf.Ticker", side_effect=_ticker):
        snaps = fetch_equity_spy_history()

    by_date = {s.date: s.ret_indexed for s in snaps}
    assert date_cls(1993, 1, 29) not in by_date
    assert by_date[date_cls(2011, 1, 3)] == pytest.approx(100.0)
    assert by_date[date_cls(2020, 1, 2)] == pytest.approx(300.0)


def test_fetch_history_drops_nan_close_rows() -> None:
    """yfinance ships NaN Close on illiquid days; those dates drop out entirely
    rather than carrying NaN into the index."""

    def _ticker(_sym: str) -> SimpleNamespace:
        frame = _history_frame(
            [
                (date_cls(2011, 1, 3), 100.0),
                (date_cls(2011, 1, 4), None),
                (date_cls(2011, 1, 5), 110.0),
            ]
        )
        return SimpleNamespace(history=lambda period: frame)

    with patch("analyze_stock_kpi.data_sources.equity_spy.yf.Ticker", side_effect=_ticker):
        snaps = fetch_equity_spy_history()

    assert [s.date for s in snaps] == [date_cls(2011, 1, 3), date_cls(2011, 1, 5)]
    assert snaps[-1].ret_indexed == pytest.approx(110.0)


# ----- merge_payload_into_years -----


def test_merge_groups_snapshots_by_utc_year(tmp_path: Path) -> None:
    snaps = [
        EquitySpySnapshot(date=date_cls(2025, 12, 31), ret_indexed=500.0),
        EquitySpySnapshot(date=date_cls(2026, 1, 2), ret_indexed=505.0),
    ]
    by_year = merge_payload_into_years(snaps, root=tmp_path)
    assert set(by_year) == {2025, 2026}
    assert "2025-12-31" in by_year[2025]
    assert "2026-01-02" in by_year[2026]


def test_merge_replaces_existing_same_date_with_newer_payload(tmp_path: Path) -> None:
    merge_payload_into_years(
        [EquitySpySnapshot(date=date_cls(2026, 5, 30), ret_indexed=500.0)], root=tmp_path
    )
    by_year = merge_payload_into_years(
        [EquitySpySnapshot(date=date_cls(2026, 5, 30), ret_indexed=512.0)], root=tmp_path
    )
    assert by_year[2026]["2026-05-30"].ret_indexed == pytest.approx(512.0)


@pytest.mark.network
def test_live_fetch_equity_spy_history() -> None:
    """One live round-trip — pins that yfinance still ships SPY closes and the
    series rebases to 100 at the 2011 epoch."""
    snaps = fetch_equity_spy_history()
    assert snaps
    assert snaps[0].ret_indexed == pytest.approx(100.0, abs=1e-6)
    assert all(s.ret_indexed > 0 for s in snaps)
    assert snaps[-1].date.year >= 2024
