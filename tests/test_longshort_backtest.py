"""Tests for :mod:`analyze_stock_kpi.orchestrators.longshort_backtest` (ADR-0013).

Non-trivial behaviours only, no network: the D3 period-end+90d usability
boundary, `score_at`'s reuse of `screener_score`, the D5 rank-at-t /
trade-at-t+1 no-look-ahead rule, equal-weight drift math, the D8 turnover
cost, the D7 monthly-buffer rule, the quarterly-after-filings date rule,
the D6 start-date threshold, a seeded-deterministic D10 null benchmark,
D9 metrics on a known series, and per-year persistence round-trip +
same-run idempotence (mirrors `tests/test_equity_spy.py`'s convention).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from analyze_stock_kpi.data_sources.fundamentals import (
    FundamentalsSnapshot,
    _close_between,
    _compute_sortino,
)
from analyze_stock_kpi.domain.composite_scores import CompositeScores, screener_score
from analyze_stock_kpi.orchestrators.longshort_backtest import (
    BacktestDailyRow,
    BacktestListEntry,
    BacktestSummary,
    CadenceMetrics,
    Fidelity,
    FidelityDate,
    MetricsBlock,
    NullBenchmark,
    RankEntry,
    _beta,
    _cost,
    _drift_leg,
    _drop_bad_tickers,
    _find_start_date,
    _genuine_weights_for_cadence,
    _rank_genuine,
    _reindex_returns,
    _reset_year_files,
    _trim_to_first_trade,
    _turnover,
    fidelity,
    metrics,
    null_percentile,
    pit_fundamentals,
    read_lists_year,
    read_series_year,
    read_summary,
    rebalance_dates,
    score_at,
    select,
    simulate,
    write_lists_years,
    write_series_years,
    write_summary,
)

if TYPE_CHECKING:
    from pathlib import Path


def _empty_close_series() -> pd.Series:
    """An empty close series with a real `DatetimeIndex` (`_batch_close_prices`'s shape)."""
    return pd.Series([], index=pd.DatetimeIndex([]), dtype=float)


def _toy_frames(
    period_end: pd.Timestamp, *, net_income: float = 100.0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    income_stmt = pd.DataFrame(
        {period_end: [net_income, 1000.0, 150.0, 50.0]},
        index=["Net Income", "Total Revenue", "Operating Income", "Research And Development"],
    )
    balance_sheet = pd.DataFrame(
        {period_end: [500.0, 2000.0, 300.0, 100.0]},
        index=["Stockholders Equity", "Total Assets", "Current Assets", "Current Liabilities"],
    )
    return income_stmt, balance_sheet


# ----- pit_fundamentals: D3 period-end+90d boundary -----


def test_pit_fundamentals_not_usable_at_day_89() -> None:
    period_end = pd.Timestamp("2023-12-31")
    frames = _toy_frames(period_end)
    boundary = period_end.date() + timedelta(days=90)

    result = pit_fundamentals(frames, boundary - timedelta(days=1), "AAPL")

    assert result == dict.fromkeys(
        (
            "return_on_equity",
            "return_on_assets",
            "operating_margins",
            "rd_to_revenue",
            "current_ratio",
        )
    )


def test_pit_fundamentals_usable_at_day_90() -> None:
    period_end = pd.Timestamp("2023-12-31")
    frames = _toy_frames(period_end)
    boundary = period_end.date() + timedelta(days=90)

    result = pit_fundamentals(frames, boundary, "AAPL")

    assert result["return_on_equity"] == pytest.approx(100.0 / 500.0)
    assert result["return_on_assets"] == pytest.approx(100.0 / 2000.0)
    assert result["operating_margins"] == pytest.approx(150.0 / 1000.0)
    assert result["current_ratio"] == pytest.approx(300.0 / 100.0)
    assert result["rd_to_revenue"] == pytest.approx(50.0 / 1000.0)


# ----- pit_fundamentals: D18 US 90d / non-US 120d filing lag -----


def test_pit_fundamentals_us_ticker_lag_is_90_days() -> None:
    period_end = pd.Timestamp("2023-12-31")
    frames = _toy_frames(period_end)
    boundary = period_end.date() + timedelta(days=90)

    assert (
        pit_fundamentals(frames, boundary - timedelta(days=1), "AAPL")["return_on_equity"] is None
    )
    assert pit_fundamentals(frames, boundary, "AAPL")["return_on_equity"] is not None


def test_pit_fundamentals_non_us_ticker_lag_is_120_days() -> None:
    period_end = pd.Timestamp("2023-12-31")
    frames = _toy_frames(period_end)
    boundary_90 = period_end.date() + timedelta(days=90)
    boundary_120 = period_end.date() + timedelta(days=120)

    # Still not usable at the US 90d boundary...
    assert pit_fundamentals(frames, boundary_90, "SAP.DE")["return_on_equity"] is None
    # ...but is at 120d - 1 is not, exactly 120d is.
    assert (
        pit_fundamentals(frames, boundary_120 - timedelta(days=1), "SAP.DE")["return_on_equity"]
        is None
    )
    assert pit_fundamentals(frames, boundary_120, "SAP.DE")["return_on_equity"] is not None


# ----- score_at: D2/D4 reuses screener_score unchanged -----


def test_score_at_equals_screener_score_with_valuation_and_beta_none() -> None:
    fund = {
        "return_on_equity": 0.15,
        "return_on_assets": 0.08,
        "operating_margins": 0.20,
        "rd_to_revenue": 0.05,
        "current_ratio": 1.5,
    }
    closes = pd.Series(
        [100.0 + i * 0.1 for i in range(400)],
        index=pd.date_range("2023-01-01", periods=400, freq="D"),
    )
    as_of = date(2024, 1, 1)

    result = score_at(fund, closes, as_of)

    as_of_ts = pd.Timestamp(as_of)
    window = _close_between(closes, as_of_ts - pd.DateOffset(years=1), as_of_ts)
    hand_built = FundamentalsSnapshot(
        symbol="X",
        return_on_equity=0.15,
        return_on_assets=0.08,
        operating_margins=0.20,
        rd_to_revenue=0.05,
        current_ratio=1.5,
        sortino_ratio=_compute_sortino(window),
        forward_pe=None,
        trailing_peg_ratio=None,
        beta=None,
    )
    assert result == screener_score(hand_built)


# ----- simulate: D5 rank-at-t / trade-at-t+1, no same-close look-ahead -----


def test_simulate_new_weights_apply_the_day_after_the_trade_date() -> None:
    d0, d1, d2 = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)
    returns = {
        "A": {d0: 0.0, d1: 0.10, d2: 0.20},
        "B": {d0: 0.0, d1: -0.10, d2: -0.20},
    }
    weights_by_trade_date = {d1: ({"A": 1.0}, {"B": 1.0})}

    rows = simulate(weights_by_trade_date, returns)
    by_date = {r.date: r for r in rows}

    # d1 is the trade date itself: still the OLD (empty) book all day, so no
    # return yet — only the swap (and its turnover/cost) happens at the close.
    assert by_date[d1].ret_long == pytest.approx(0.0)
    assert by_date[d1].ret_short == pytest.approx(0.0)
    assert by_date[d1].turnover > 0.0
    # d2 is the first day the NEW book actually earns a return.
    assert by_date[d2].ret_long == pytest.approx(0.20)
    assert by_date[d2].ret_short == pytest.approx(-0.20)
    assert by_date[d2].turnover == pytest.approx(0.0)


# ----- _drift_leg: equal weights + drift math on a 3-ticker toy -----


def test_drift_leg_equal_weight_three_ticker_toy() -> None:
    weights = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    day_returns = {"A": 0.10, "B": 0.0, "C": -0.10}

    drifted = _drift_leg(weights, day_returns)

    assert sum(drifted.values()) == pytest.approx(1.0)
    assert drifted["A"] == pytest.approx((1 / 3) * 1.10)
    assert drifted["B"] == pytest.approx(1 / 3)
    assert drifted["C"] == pytest.approx((1 / 3) * 0.90)


# ----- _turnover / _cost: D8 10bp one-way turnover -----


def test_turnover_and_cost_10bp_one_way() -> None:
    target_long = {"A": 0.5, "B": 0.5}
    target_short = {"C": 0.5, "D": 0.5}

    turnover = _turnover(target_long, target_short, {}, {})

    assert turnover == pytest.approx(1.0)  # full inception turnover: 0.5 * (1.0 + 1.0)
    assert _cost(turnover) == pytest.approx(0.001)  # 10 bp


# ----- select: D7 monthly-buffer keeps rank 30, drops rank 41 -----


def test_select_monthly_buffer_keeps_rank_30_drops_rank_41() -> None:
    ranks = [f"T{i:02d}" for i in range(1, 51)]  # T01 (best) .. T50 (worst)
    prev_long = ["T30", "T41"]
    prev_short: list[str] = []

    long_names, _short_names = select(ranks, "monthly_buffer", (prev_long, prev_short))

    assert "T30" in long_names  # rank 30 <= buffer(40) -> kept
    assert "T41" not in long_names  # rank 41 > buffer(40) -> dropped
    assert len(long_names) == 25


# ----- _rank_genuine: D16 series A ranks via build_universe (pure) -----


def _snap_with_score(symbol: str, score: float) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol, composite_scores=CompositeScores(screener_score=score)
    )


def test_rank_genuine_ranks_via_build_universe_across_two_universes() -> None:
    snapshots_by_universe = {
        "u1": [_snap_with_score("AAPL", 90.0), _snap_with_score("XOM", 10.0)],
        "u2": [_snap_with_score("MSFT", 80.0), _snap_with_score("F", 20.0)],
    }
    snapshot_dates_by_universe = {"u1": "2026-05-31", "u2": "2026-05-31"}

    entry = _rank_genuine(
        snapshots_by_universe, snapshot_dates_by_universe, date(2026, 5, 31), top_n=2
    )

    assert [r.ticker for r in entry.best] == ["AAPL", "MSFT"]
    assert [r.ticker for r in entry.worst] == ["F", "XOM"]
    assert entry.eligible == 4
    assert entry.date == date(2026, 5, 31)
    best_by_ticker = {r.ticker: r.score for r in entry.best}
    assert best_by_ticker["AAPL"] == pytest.approx(90.0)


# ----- _genuine_weights_for_cadence: D16 trade-at-t+1, holds across a gap -----


def test_genuine_weights_trade_date_is_strictly_after_the_rank_date() -> None:
    d0 = date(2026, 5, 29)
    d1 = date(2026, 6, 1)
    calendar = [d0, d1]
    ranked_by_date = {d0: (["A"], ["B"])}

    weights = _genuine_weights_for_cadence("weekly", [d0], ranked_by_date, calendar, book_size=1)

    assert d0 not in weights
    assert weights[d1] == ({"A": 1.0}, {"B": 1.0})


def test_genuine_book_holds_across_a_snapshot_gap() -> None:
    d0 = date(2026, 5, 31)
    trade0 = date(2026, 6, 1)
    later = date(2026, 9, 21)
    calendar = [trade0, date(2026, 6, 2), later]
    ranked_by_date = {d0: (["A"], ["B"])}
    weights = _genuine_weights_for_cadence("monthly", [d0], ranked_by_date, calendar, book_size=1)
    returns = {
        "A": {trade0: 0.0, date(2026, 6, 2): 0.05, later: 0.10},
        "B": {trade0: 0.0, date(2026, 6, 2): 0.0, later: 0.0},
    }

    rows = simulate(weights, returns)
    by_date = {r.date: r for r in rows}

    # No rebalance between trade0 and `later` (the 07-12 -> 09-21 style snapshot
    # gap) -- the book is still holding "A" / "B" from the first rebalance.
    assert by_date[later].ret_long == pytest.approx(0.10)


# ----- _trim_to_first_trade: the start-trim fix (found 2026-09-24) -----


def test_trim_to_first_trade_drops_rows_before_the_first_trade_date() -> None:
    weights_by_trade_date = {date(2026, 4, 3): ({}, {})}
    rows = [
        BacktestDailyRow(
            date=date(2026, 1, 1),
            ret_long=0.0,
            ret_short=0.0,
            ret_ls_gross=0.0,
            ret_ls_net=0.0,
            turnover=0.0,
        ),
        BacktestDailyRow(
            date=date(2026, 4, 3),
            ret_long=0.01,
            ret_short=0.0,
            ret_ls_gross=0.01,
            ret_ls_net=0.01,
            turnover=0.1,
        ),
    ]

    trimmed = _trim_to_first_trade(rows, weights_by_trade_date)

    assert trimmed == rows[1:]


def test_trim_to_first_trade_empty_weights_yields_no_rows() -> None:
    rows = [
        BacktestDailyRow(
            date=date(2026, 1, 1),
            ret_long=0.0,
            ret_short=0.0,
            ret_ls_gross=0.0,
            ret_ls_net=0.0,
            turnover=0.0,
        )
    ]

    assert _trim_to_first_trade(rows, {}) == []


# ----- _drop_bad_tickers: the 2026-03-18 ICTEF bad-tick fix (found 2026-09-24) -----


def test_drop_bad_tickers_excludes_a_ticker_with_any_non_positive_close() -> None:
    closes = {
        "GOOD": pd.Series([10.0, 11.0, 12.0], index=pd.date_range("2026-01-01", periods=3)),
        # ICTEF's actual shape: negative "closes" scattered through most of its history.
        "ICTEF": pd.Series([-5.9, -6.1, 11.9], index=pd.date_range("2026-03-16", periods=3)),
        "ZERO": pd.Series([1.0, 0.0, 2.0], index=pd.date_range("2026-02-01", periods=3)),
    }

    cleaned = _drop_bad_tickers(closes)

    assert set(cleaned) == {"GOOD"}
    assert list(cleaned["GOOD"]) == [10.0, 11.0, 12.0]


def test_drop_bad_tickers_prevents_the_negative_to_positive_return_spike() -> None:
    """Patching just the negative points (instead of dropping the ticker) would still
    manufacture a huge `ffill`-gap "return" once a positive price reappears; dropping the
    whole ticker means it never reaches `_reindex_returns` at all."""
    closes = {
        "ICTEF": pd.Series([10.0, -5.9, -6.1, 11.9], index=pd.date_range("2026-03-15", periods=4)),
        "GOOD": pd.Series([10.0, 10.1, 10.2, 10.3], index=pd.date_range("2026-03-15", periods=4)),
    }
    calendar = [d.date() for d in pd.date_range("2026-03-15", periods=4)]

    cleaned = _drop_bad_tickers(closes)
    returns = _reindex_returns(cleaned, calendar)

    assert "ICTEF" not in returns
    for r in returns["GOOD"].values():
        assert abs(r) < 1.0


# ----- rebalance_dates: quarterly-after-filings date rule -----


def test_quarterly_filing_dates_picks_first_grid_date_on_or_after_trigger() -> None:
    grid = [date(2026, 2, 13), date(2026, 2, 20), date(2026, 5, 15), date(2026, 5, 22)]

    result = rebalance_dates("quarterly_filings", grid)

    assert date(2026, 2, 20) in result  # first grid date on/after Feb 15
    assert date(2026, 5, 15) in result  # an exact trigger-date match counts
    assert date(2026, 2, 13) not in result
    assert date(2026, 5, 22) not in result


# ----- _find_start_date: D6 start-date rule with a small threshold param -----


def test_find_start_date_reaches_threshold_at_first_qualifying_date() -> None:
    period_end = pd.Timestamp("2023-01-01")
    frames_by_ticker = {"A": _toy_frames(period_end), "B": _toy_frames(period_end)}
    closes = {"A": _empty_close_series(), "B": _empty_close_series()}
    boundary = period_end.date() + timedelta(days=90)
    grid = [boundary - timedelta(days=1), boundary, boundary + timedelta(days=5)]

    start = _find_start_date(grid, frames_by_ticker, closes, threshold=2)

    assert start == boundary


def test_find_start_date_returns_none_below_threshold() -> None:
    period_end = pd.Timestamp("2023-01-01")
    frames_by_ticker = {"A": _toy_frames(period_end)}
    closes = {"A": _empty_close_series()}
    boundary = period_end.date() + timedelta(days=90)

    start = _find_start_date([boundary], frames_by_ticker, closes, threshold=2)

    assert start is None


# ----- null_percentile: D10 seeded null is deterministic -----


def _toy_close_series(seed: int, *, days: int = 150) -> pd.Series:
    rng = random.Random(seed)  # noqa: S311 -- synthetic toy fixture, not security-sensitive
    price = 100.0
    dates = pd.date_range("2025-10-01", periods=days, freq="D")
    prices = []
    for _ in range(days):
        price *= 1 + rng.gauss(0.0002, 0.01)
        prices.append(price)
    return pd.Series(prices, index=dates)


def test_null_percentile_is_deterministic_for_a_fixed_seed() -> None:
    rebal_dates = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    pool = [f"T{i}" for i in range(10)]
    eligible_by_date = dict.fromkeys(rebal_dates, pool)
    closes = {t: _toy_close_series(seed=i) for i, t in enumerate(pool)}

    first = null_percentile(0.05, rebal_dates, eligible_by_date, closes, n=20, seed=7, book_size=2)
    second = null_percentile(0.05, rebal_dates, eligible_by_date, closes, n=20, seed=7, book_size=2)

    assert first == second


# ----- metrics: D9 on a known series -----


def test_metrics_on_a_known_series() -> None:
    dates_ts = pd.bdate_range(start="2025-01-01", periods=252)
    dates = [ts.date() for ts in dates_ts]
    r = 0.0004
    seen_months: set[tuple[int, int]] = set()
    rows: list[BacktestDailyRow] = []
    for d in dates:
        key = (d.year, d.month)
        turnover = 0.02 if key not in seen_months else 0.0
        seen_months.add(key)
        rows.append(
            BacktestDailyRow(
                date=d, ret_long=r, ret_short=0.0, ret_ls_gross=r, ret_ls_net=r, turnover=turnover
            )
        )
    spy_returns = dict.fromkeys(dates, 0.0002)  # constant -> zero variance -> beta None

    gross, _net = metrics(rows, spy_returns)

    assert gross.ann_return == pytest.approx((1 + r) ** 252 - 1)
    assert gross.ann_vol == pytest.approx(0.0, abs=1e-12)
    assert gross.max_drawdown == pytest.approx(0.0)
    assert gross.ann_turnover == pytest.approx(0.02 * len(seen_months))
    assert gross.hit_rate == pytest.approx(1.0)
    assert gross.beta is None


def test_metrics_below_12_months_returns_all_none() -> None:
    dates = [date(2026, 1, 5), date(2026, 2, 5)]
    rows = [
        BacktestDailyRow(
            date=d, ret_long=0.01, ret_short=0.0, ret_ls_gross=0.01, ret_ls_net=0.01, turnover=0.0
        )
        for d in dates
    ]

    gross, net = metrics(rows, {})

    assert gross == MetricsBlock()
    assert net == MetricsBlock()


def test_beta_matches_the_ols_slope_for_a_linear_relationship() -> None:
    dates = [date(2026, 1, d) for d in range(1, 11)]
    spy = {d: 0.01 * (i - 5) for i, d in enumerate(dates)}
    daily = [2.0 * spy[d] + 0.001 for d in dates]  # exact y = 2x + const -> slope 2

    assert _beta(daily, dates, spy) == pytest.approx(2.0)


# ----- fidelity -----


def test_fidelity_reports_spearman_rho_and_its_median() -> None:
    score_bt_by_date = {
        date(2026, 5, 22): {"AAPL": 80.0, "MSFT": 60.0, "XOM": 20.0},
        date(2026, 7, 12): {"AAPL": 70.0, "MSFT": 65.0, "XOM": 30.0},
    }
    live_score_by_date = {
        date(2026, 5, 22): {"AAPL": 85.0, "MSFT": 55.0, "XOM": 10.0},  # same rank order
        date(2026, 7, 12): {"AAPL": 30.0, "MSFT": 65.0, "XOM": 70.0},  # reversed rank order
    }

    result = fidelity(score_bt_by_date, live_score_by_date)

    by_date = {fd.date: fd for fd in result.per_date}
    assert by_date[date(2026, 5, 22)].rho == pytest.approx(1.0)
    assert by_date[date(2026, 7, 12)].rho == pytest.approx(-1.0)
    assert result.median_rho == pytest.approx(0.0)


# ----- persistence: round-trip + same-run idempotence -----


def test_series_persistence_round_trip(tmp_path: Path) -> None:
    rows = [
        BacktestDailyRow(
            date=date(2026, 1, 5),
            ret_long=0.01,
            ret_short=-0.02,
            ret_ls_gross=0.03,
            ret_ls_net=0.028,
            turnover=0.1,
        ),
        BacktestDailyRow(
            date=date(2026, 6, 1),
            ret_long=0.0,
            ret_short=0.0,
            ret_ls_gross=0.0,
            ret_ls_net=0.0,
            turnover=0.0,
        ),
    ]
    root = tmp_path / "monthly"

    write_series_years("monthly", rows, root=root)
    loaded = read_series_year("monthly", 2026, root=root)

    assert loaded == sorted(rows, key=lambda r: r.date)


def test_series_persistence_same_run_is_idempotent(tmp_path: Path) -> None:
    """D17: a re-run with no new dates writes nothing and leaves the file byte-identical."""
    rows = [
        BacktestDailyRow(
            date=date(2026, 3, 1),
            ret_long=0.01,
            ret_short=0.0,
            ret_ls_gross=0.01,
            ret_ls_net=0.009,
            turnover=0.05,
        )
    ]
    root = tmp_path / "weekly"

    paths_1 = write_series_years("weekly", rows, root=root)
    content_1 = paths_1[0].read_text()
    paths_2 = write_series_years("weekly", rows, root=root)
    content_2 = (root / "2026.json").read_text()

    assert paths_2 == []  # nothing new to append
    assert content_1 == content_2


def test_series_persistence_freezes_existing_rows_even_if_recompute_differs(tmp_path: Path) -> None:
    """D17: an already-frozen date is never overwritten, even if a re-run recomputes it."""
    root = tmp_path / "monthly"
    original = BacktestDailyRow(
        date=date(2026, 1, 5),
        ret_long=0.01,
        ret_short=0.0,
        ret_ls_gross=0.01,
        ret_ls_net=0.009,
        turnover=0.05,
    )
    write_series_years("monthly", [original], root=root)

    drifted = BacktestDailyRow(
        date=date(2026, 1, 5),
        ret_long=0.99,
        ret_short=0.0,
        ret_ls_gross=0.99,
        ret_ls_net=0.98,
        turnover=0.05,
    )
    new_row = BacktestDailyRow(
        date=date(2026, 1, 6),
        ret_long=0.02,
        ret_short=0.0,
        ret_ls_gross=0.02,
        ret_ls_net=0.018,
        turnover=0.0,
    )
    write_series_years("monthly", [drifted, new_row], root=root)

    loaded = read_series_year("monthly", 2026, root=root)

    assert loaded == [original, new_row]


def test_lists_persistence_freezes_existing_entries_even_if_recompute_differs(
    tmp_path: Path,
) -> None:
    """D17: same freeze guarantee for the backfilled best/worst-25 lists."""
    root = tmp_path / "lists"
    original = BacktestListEntry(
        date=date(2026, 4, 3),
        eligible=210,
        best=[RankEntry(ticker="AAPL", score=88.5)],
        worst=[RankEntry(ticker="XOM", score=12.1)],
    )
    write_lists_years([original], root=root)

    drifted = BacktestListEntry(
        date=date(2026, 4, 3), eligible=999, best=[RankEntry(ticker="ZZZ", score=1.0)], worst=[]
    )
    new_entry = BacktestListEntry(
        date=date(2026, 4, 10),
        eligible=211,
        best=[RankEntry(ticker="MSFT", score=77.0)],
        worst=[RankEntry(ticker="F", score=9.0)],
    )
    write_lists_years([drifted, new_entry], root=root)

    loaded = read_lists_year(2026, root=root)

    assert loaded == [original, new_entry]


# ----- _reset_year_files: the D17/D18 explicit one-time rebuild mechanism -----


def test_reset_year_files_deletes_every_year_file(tmp_path: Path) -> None:
    root = tmp_path / "monthly"
    row = BacktestDailyRow(
        date=date(1962, 1, 2),
        ret_long=0.0,
        ret_short=0.0,
        ret_ls_gross=0.0,
        ret_ls_net=0.0,
        turnover=0.0,
    )
    write_series_years("monthly", [row], root=root)
    assert (root / "1962.json").exists()

    removed = _reset_year_files(root)

    assert removed == [root / "1962.json"]
    assert not (root / "1962.json").exists()


def test_reset_year_files_on_missing_dir_is_a_noop(tmp_path: Path) -> None:
    assert _reset_year_files(tmp_path / "missing") == []


def test_lists_persistence_round_trip(tmp_path: Path) -> None:
    entries = [
        BacktestListEntry(
            date=date(2026, 4, 3),
            eligible=210,
            best=[RankEntry(ticker="AAPL", score=88.5)],
            worst=[RankEntry(ticker="XOM", score=12.1)],
        )
    ]
    root = tmp_path / "lists"

    write_lists_years(entries, root=root)
    loaded = read_lists_year(2026, root=root)

    assert loaded == entries


def test_summary_persistence_round_trip(tmp_path: Path) -> None:
    block = MetricsBlock()
    summary = BacktestSummary(
        method_version="1",
        as_of=date(2026, 1, 1),
        start=date(2021, 6, 1),
        universes=["sp500"],
        score_inputs=["return_on_equity"],
        cost_bps=10.0,
        primary="monthly",
        cadences={"monthly": CadenceMetrics(gross=block, net=block, rebalances=0)},
        null=NullBenchmark(n=1000, percentile=50.0, median_net_ann=0.0),
        fidelity=Fidelity(
            per_date=[FidelityDate(date=date(2026, 1, 1), rho=0.9, n=10)], median_rho=0.9
        ),
        caveats=["test caveat"],
    )
    path = tmp_path / "summary.json"

    write_summary(summary, path=path)
    loaded = read_summary(path=path)

    assert loaded == summary


def test_summary_persistence_round_trip_with_null_and_fidelity_absent(tmp_path: Path) -> None:
    """D16: series A may publish `null`/`fidelity` as `None` until it has enough history."""
    block = MetricsBlock()
    summary = BacktestSummary(
        method_version="1",
        as_of=date(2026, 9, 24),
        start=date(2026, 5, 31),
        universes=["sp500"],
        score_inputs=["screener_score"],
        cost_bps=10.0,
        primary="monthly",
        cadences={"monthly": CadenceMetrics(gross=block, net=block, rebalances=1)},
        null=None,
        fidelity=None,
        caveats=["genuine caveat"],
    )
    path = tmp_path / "summary_genuine.json"

    write_summary(summary, path=path)
    loaded = read_summary(path=path)

    assert loaded == summary
    assert loaded is not None
    assert loaded.null is None
    assert loaded.fidelity is None
