"""Tests for :mod:`analyze_stock_kpi.orchestrators.longshort_portfolio` (ADR-0012).

Non-trivial behaviours only: the first-run state-only contract, exact
return-row math from known price moves, monthly-cadence rebalance timing,
the D6 90-day pool freeze, exclusion reasons, and per-year persistence
round-tripping (mirrors `tests/test_equity_spy.py`'s convention). No
network — `load_pool` / `fetch_closes` are mocked or bypassed entirely;
`step` and the persistence helpers are pure/file-local.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from analyze_stock_kpi.orchestrators.longshort_portfolio import (
    ExcludedTicker,
    HoldingWeight,
    LongShortPortfolioError,
    PortfolioPool,
    PortfolioState,
    WeeklyReturn,
    _eligible_returns,
    is_rebalance_due,
    merge_return_into_years,
    step,
)

if TYPE_CHECKING:
    from pathlib import Path


def _prices(days: int, start: date = date(2020, 1, 1), seed: int = 0) -> dict[date, float]:
    """A random-walk `date -> close` map long enough to clear the D6
    90 %-of-756-day coverage bar (used wherever `step` triggers `_optimize`).
    """
    rng = random.Random(seed)  # noqa: S311 -- synthetic test fixture, not security-sensitive
    price = 100.0
    out: dict[date, float] = {}
    for i in range(days):
        price *= 1 + rng.gauss(0.0003, 0.01)
        out[start + timedelta(days=i)] = price
    return out


def _closes_for(tickers: list[str], days: int = 800) -> dict[str, dict[date, float]]:
    return {t: _prices(days, seed=i) for i, t in enumerate(tickers)}


def _state(**overrides: object) -> PortfolioState:
    base = {
        "cadence": "weekly",
        "inception": date(2026, 1, 2),
        "as_of": date(2026, 1, 2),
        "last_rebalance": date(2026, 1, 2),
        "pool_as_of": date(2026, 1, 2),
        "lookback_days": 756,
        "long": [
            HoldingWeight(ticker="AAPL", weight=0.5),
            HoldingWeight(ticker="MSFT", weight=0.5),
        ],
        "short": [
            HoldingWeight(ticker="XOM", weight=0.5),
            HoldingWeight(ticker="CVX", weight=0.5),
        ],
        "pool": PortfolioPool(long=["AAPL", "MSFT"], short=["XOM", "CVX"]),
        "excluded": [],
        "ex_ante_vol_annual": 0.1,
    }
    base.update(overrides)
    return PortfolioState.model_validate(base)


# ----- is_rebalance_due -----


def test_is_rebalance_due_none_state_is_always_due() -> None:
    assert is_rebalance_due(None, date(2026, 1, 1), "weekly") is True
    assert is_rebalance_due(None, date(2026, 1, 1), "monthly") is True


def test_weekly_is_always_due() -> None:
    state = _state(cadence="weekly", last_rebalance=date(2026, 1, 2))
    assert is_rebalance_due(state, date(2026, 1, 9), "weekly") is True


def test_monthly_not_due_mid_month() -> None:
    state = _state(cadence="monthly", last_rebalance=date(2026, 3, 6))
    assert is_rebalance_due(state, date(2026, 3, 13), "monthly") is False


def test_monthly_due_on_first_run_of_new_month() -> None:
    state = _state(cadence="monthly", last_rebalance=date(2026, 3, 27))
    assert is_rebalance_due(state, date(2026, 4, 3), "monthly") is True


# ----- step: first run -----


def test_first_run_writes_state_and_no_row() -> None:
    tickers = ["A", "B", "S1", "S2"]
    closes = _closes_for(tickers)
    with patch(
        "analyze_stock_kpi.orchestrators.longshort_portfolio.load_pool",
        return_value=(["A", "B"], ["S1", "S2"]),
    ):
        new_state, row = step(None, closes, date(2026, 1, 2), "weekly")

    assert row is None
    assert new_state.inception == date(2026, 1, 2)
    assert new_state.as_of == date(2026, 1, 2)
    assert new_state.pool_as_of == date(2026, 1, 2)
    assert pytest.approx(sum(h.weight for h in new_state.long)) == 1.0
    assert pytest.approx(sum(h.weight for h in new_state.short)) == 1.0
    assert new_state.pool.long == ["A", "B"]
    assert new_state.pool.short == ["S1", "S2"]


# ----- step: known price moves -----


def test_known_price_moves_give_exact_returns() -> None:
    prev, today = date(2026, 3, 6), date(2026, 3, 13)
    state = _state(
        cadence="monthly",
        as_of=prev,
        last_rebalance=date(2026, 3, 6),  # same month as `today` -> not due
        pool_as_of=date(2026, 3, 6),  # < 90 days before `today` -> not stale
    )
    closes = {
        "AAPL": {prev: 100.0, today: 110.0},  # +10%
        "MSFT": {prev: 200.0, today: 190.0},  # -5%
        "XOM": {prev: 50.0, today: 55.0},  # +10%
        "CVX": {prev: 80.0, today: 76.0},  # -5%
    }

    new_state, row = step(state, closes, today, "monthly")

    assert row is not None
    assert row.date == today
    assert row.ret_long == pytest.approx(0.5 * 0.10 + 0.5 * -0.05)
    assert row.ret_short == pytest.approx(0.5 * 0.10 + 0.5 * -0.05)
    assert row.ret_ls == pytest.approx(row.ret_long - row.ret_short)
    # Not due mid-month -> weights (and pool) carry forward unchanged.
    assert new_state.long == state.long
    assert new_state.short == state.short
    assert new_state.as_of == today


# ----- step: pool freeze (D6) -----


def test_pool_not_refreshed_before_90_days() -> None:
    today = date(2026, 3, 6) + timedelta(days=89)
    state = _state(
        cadence="monthly",
        as_of=date(2026, 3, 6),
        last_rebalance=date(2026, 3, 6),
        pool_as_of=date(2026, 3, 6),
    )
    closes = _closes_for(["AAPL", "MSFT", "XOM", "CVX"])

    with patch("analyze_stock_kpi.orchestrators.longshort_portfolio.load_pool") as mock_load:
        new_state, _row = step(state, closes, today, "monthly")

    mock_load.assert_not_called()
    assert new_state.pool.long == state.pool.long
    assert new_state.pool_as_of == state.pool_as_of


def test_pool_refreshes_after_90_days_and_forces_rebalance() -> None:
    """Even mid-month for a monthly cadence, a stale pool forces a rebalance
    (weights can't carry over onto a now-different ticker set)."""
    today = date(2026, 3, 6) + timedelta(days=90)
    state = _state(
        cadence="monthly",
        as_of=date(2026, 3, 6),
        last_rebalance=date(2026, 3, 6),
        pool_as_of=date(2026, 3, 6),
    )
    new_pool = (["NEWL1", "NEWL2"], ["NEWS1", "NEWS2"])
    closes = _closes_for(["AAPL", "MSFT", "XOM", "CVX", *new_pool[0], *new_pool[1]])

    with patch(
        "analyze_stock_kpi.orchestrators.longshort_portfolio.load_pool", return_value=new_pool
    ) as mock_load:
        new_state, _row = step(state, closes, today, "monthly")

    mock_load.assert_called_once()
    assert new_state.pool.long == new_pool[0]
    assert new_state.pool.short == new_pool[1]
    assert new_state.pool_as_of == today
    assert {h.ticker for h in new_state.long} == set(new_pool[0])


# ----- _eligible_returns: exclusion reasons (D6) -----


def test_excluded_tickers_carry_a_reason() -> None:
    closes = {
        "GOOD": _prices(800, seed=1),
        "SHORT_HISTORY": _prices(100, seed=2),  # < 90% of 756 -> insufficient_coverage
    }

    eligible, excluded = _eligible_returns(["GOOD", "SHORT_HISTORY", "MISSING"], closes)

    assert set(eligible) == {"GOOD"}
    reasons = {e.ticker: e.reason for e in excluded}
    assert reasons["SHORT_HISTORY"] == "insufficient_coverage"
    assert reasons["MISSING"] == "no_price_data"


def test_optimize_raises_when_a_leg_has_no_eligible_tickers() -> None:
    closes = {"A": _prices(800, seed=3)}
    with (
        patch(
            "analyze_stock_kpi.orchestrators.longshort_portfolio.load_pool",
            return_value=(["A"], ["MISSING"]),
        ),
        pytest.raises(LongShortPortfolioError),
    ):
        step(None, closes, date(2026, 1, 2), "weekly")


# ----- persistence round-trip -----


def test_merge_return_into_years_replaces_same_date_row(tmp_path: Path) -> None:
    row1 = WeeklyReturn(date=date(2026, 5, 8), ret_long=0.01, ret_short=-0.02, ret_ls=0.03)
    by_year = merge_return_into_years(row1, root=tmp_path)
    assert by_year[2026]["2026-05-08"].ret_ls == pytest.approx(0.03)
    from analyze_stock_kpi.orchestrators.longshort_portfolio import _write_year_returns

    _write_year_returns(2026, by_year[2026], root=tmp_path)

    row2 = WeeklyReturn(date=date(2026, 5, 8), ret_long=0.05, ret_short=0.0, ret_ls=0.05)
    by_year_2 = merge_return_into_years(row2, root=tmp_path)

    assert len(by_year_2[2026]) == 1
    assert by_year_2[2026]["2026-05-08"].ret_ls == pytest.approx(0.05)


def test_state_json_round_trip(tmp_path: Path) -> None:
    from analyze_stock_kpi.orchestrators.longshort_portfolio import load_state, save_state

    state = _state()
    path = tmp_path / "weekly" / "state.json"
    assert load_state(path) is None

    save_state(state, path)
    loaded = load_state(path)

    assert loaded == state


def test_excluded_ticker_model_fields() -> None:
    e = ExcludedTicker(ticker="X", reason="no_price_data")
    assert e.ticker == "X"
    assert e.reason == "no_price_data"
