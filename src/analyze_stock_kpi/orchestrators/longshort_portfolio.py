"""Hypothetical long/short model portfolio orchestrator (ADR-0012).

Tracks two parallel, forward-only, dollar-neutral portfolios — one
rebalanced weekly, one monthly — long the `aggregated-scores-best` preset
and short `aggregated-scores-worst`, weighted by a joint Min Variance
optimizer (`domain.portfolio_optimizer`). No backtest is published; the
first run for a cadence writes state only (no return row).

Public API:

- :func:`load_pool` — long/short candidate tickers from the aggregated
  best/worst presets.
- :func:`fetch_closes` — batched 5y daily closes for a ticker list;
  wrap-degrades to ``{}`` and writes the D8 gitignored price cache.
- :func:`is_rebalance_due` — cadence-specific rebalance-timing rule.
- :func:`step` — pure state transition for one cron run.
- :func:`main` — cron entrypoint; runs both cadences and persists.

Frozen data contract (see the plan / ADR-0012): raw closes are never
committed — only weekly returns (`WeeklyReturn`) and target weights
(`PortfolioState`) reach the `data` branch.
"""

from __future__ import annotations

import itertools
import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd
import yfinance as yf
from pydantic import BaseModel, ConfigDict

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.domain.universe import PRESET_DIR, _read_symbol_file

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

Cadence = Literal["weekly", "monthly"]

_LOOKBACK_DAYS = 756
"""~3 trading years (ADR-0012 D4) — the covariance estimation window."""

_MIN_COVERAGE = 0.90
"""D6: tickers with less than this fraction of the lookback's daily returns
present are excluded from optimization rather than silently degrading the
covariance estimate with sparse data."""

_POOL_FREEZE_DAYS = 90
"""D6: the long/short candidate pool is frozen for this many days once set,
independent of each cadence's own rebalance timing."""


class HoldingWeight(BaseModel):
    """One ticker's target weight within a long or short leg."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    weight: float


class ExcludedTicker(BaseModel):
    """A pool candidate dropped from optimization, with why (D6)."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    reason: str


class PortfolioPool(BaseModel):
    """The frozen long/short candidate pool (D6)."""

    model_config = ConfigDict(frozen=True)

    long: list[str]
    short: list[str]


class PortfolioState(BaseModel):
    """Current targets for one cadence of the model portfolio (ADR-0012)."""

    model_config = ConfigDict(frozen=True)

    cadence: Cadence
    objective: Literal["min_variance"] = "min_variance"
    inception: date
    as_of: date
    last_rebalance: date
    pool_as_of: date
    lookback_days: int
    long: list[HoldingWeight]
    short: list[HoldingWeight]
    pool: PortfolioPool
    excluded: list[ExcludedTicker]
    ex_ante_vol_annual: float


class WeeklyReturn(BaseModel):
    """One cron run's realized return for a portfolio's long/short legs."""

    model_config = ConfigDict(frozen=True)

    date: date
    ret_long: float
    ret_short: float
    ret_ls: float


def load_pool() -> tuple[list[str], list[str]]:
    """Long/short candidate tickers from the aggregated best/worst presets."""
    long_pool = _read_symbol_file(PRESET_DIR / "aggregated-scores-best.txt")
    short_pool = _read_symbol_file(PRESET_DIR / "aggregated-scores-worst.txt")
    return long_pool, short_pool


def _extract_close_columns(df: pd.DataFrame, tickers: list[str]) -> dict[str, Any]:
    """Handle both single-ticker and multi-ticker ``yf.download`` shapes.

    Own helper, distinct from ``fundamentals._batch_close_prices`` — dedupe
    is deferred (see the plan's remaining-work table). Returned values are
    pandas Series of close prices; the loose ``Any`` annotation
    accommodates pyright's narrowing of ``DataFrame[...]`` lookups (mirrors
    ``fundamentals._batch_close_prices``).
    """
    if len(tickers) == 1:
        return {tickers[0]: df["Close"]} if "Close" in df.columns else {}
    try:
        close_block = df["Close"]
    except KeyError:
        return {}
    return {t: close_block[t] for t in tickers if t in close_block.columns}


def _write_price_cache(closes: dict[str, Any], today: date) -> Path:
    """Write raw closes to the gitignored local cache (D8) — never committed."""
    root = settings.portfolio_prices_cache_dir
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"closes_{today.isoformat()}.csv"
    pd.DataFrame(closes).to_csv(path)
    return path


def _series_to_date_map(series: pd.Series) -> dict[date, float]:
    """One ticker's close `pd.Series` -> a ``date -> close`` map, NaN-dropped."""
    out: dict[date, float] = {}
    for ts, v in series.dropna().items():
        if isinstance(ts, pd.Timestamp):
            out[ts.date()] = float(v)
    return out


def fetch_closes(
    tickers: list[str], *, today: date | None = None
) -> dict[str, dict[date, float]]:
    """Batched 5y daily closes for `tickers`.

    Wrap-degrades to `{}` on any failure so the caller skips today's mark
    rather than raising. On success, also writes the raw closes to the D8
    gitignored local cache.
    """
    if not tickers:
        return {}
    try:
        df = yf.download(tickers, period="5y", progress=False, auto_adjust=True)
    except Exception as exc:
        logger.warning("yfinance batch download failed: %s", exc)
        return {}
    if df is None or df.empty:
        return {}
    close_by_ticker = _extract_close_columns(df, tickers)
    if not close_by_ticker:
        return {}
    _write_price_cache(close_by_ticker, today or date.today())
    return {ticker: _series_to_date_map(series) for ticker, series in close_by_ticker.items()}


def _daily_returns(prices: dict[date, float]) -> dict[date, float]:
    """Simple day-over-day returns from a sorted ``date -> close`` map."""
    dates = sorted(prices)
    out: dict[date, float] = {}
    for prev_d, cur_d in itertools.pairwise(dates):
        prev_p = prices[prev_d]
        if prev_p:
            out[cur_d] = prices[cur_d] / prev_p - 1.0
    return out


def _eligible_returns(
    pool: list[str], closes: dict[str, dict[date, float]]
) -> tuple[dict[str, dict[date, float]], list[ExcludedTicker]]:
    """Split `pool` into eligible-vs-excluded tickers per the D6 coverage bar.

    Returns ``(ticker -> daily returns within the lookback)`` for tickers
    meeting the bar, plus the excluded ones with a reason.
    """
    eligible: dict[str, dict[date, float]] = {}
    excluded: list[ExcludedTicker] = []
    for ticker in pool:
        prices = closes.get(ticker)
        if not prices:
            excluded.append(ExcludedTicker(ticker=ticker, reason="no_price_data"))
            continue
        returns = _daily_returns(prices)
        window = dict(sorted(returns.items())[-_LOOKBACK_DAYS:])
        coverage = len(window) / _LOOKBACK_DAYS
        if coverage < _MIN_COVERAGE:
            excluded.append(ExcludedTicker(ticker=ticker, reason="insufficient_coverage"))
            continue
        eligible[ticker] = window
    return eligible, excluded


def _aligned_matrix(returns_by_ticker: dict[str, dict[date, float]]) -> np.ndarray:
    """Stack per-ticker daily returns into a ``(T, N)`` array.

    Rows are the common dates (intersection) across every ticker; columns
    are ordered by `returns_by_ticker`.
    """
    common_dates = set.intersection(*(set(r) for r in returns_by_ticker.values()))
    ordered_dates = sorted(common_dates)
    tickers = list(returns_by_ticker)
    return np.array([[returns_by_ticker[t][d] for t in tickers] for d in ordered_dates])


class LongShortPortfolioError(RuntimeError):
    """Raised when a leg has no eligible tickers left to optimize over."""


def _optimize(
    long_pool: list[str], short_pool: list[str], closes: dict[str, dict[date, float]]
) -> tuple[list[HoldingWeight], list[HoldingWeight], list[ExcludedTicker], float]:
    """Build the covariance over the eligible pool and solve joint Min Variance.

    Imports `domain.portfolio_optimizer` lazily so `scipy` is only required
    when a rebalance actually runs.
    """
    from analyze_stock_kpi.domain.portfolio_optimizer import (
        ex_ante_vol,
        min_variance_longshort,
        shrunk_covariance,
    )

    long_returns, long_excluded = _eligible_returns(long_pool, closes)
    short_returns, short_excluded = _eligible_returns(short_pool, closes)
    if not long_returns or not short_returns:
        raise LongShortPortfolioError("no eligible tickers left on one or both legs")

    combined = {**long_returns, **short_returns}
    matrix = _aligned_matrix(combined)
    cov = shrunk_covariance(matrix)
    n_long = len(long_returns)
    w_long, w_short = min_variance_longshort(cov, n_long, len(short_returns))
    sign = np.concatenate([np.ones(n_long), -np.ones(len(short_returns))])
    vol = ex_ante_vol(cov, np.concatenate([w_long, w_short]) * sign)

    long_weights = [
        HoldingWeight(ticker=t, weight=float(w)) for t, w in zip(long_returns, w_long, strict=True)
    ]
    short_weights = [
        HoldingWeight(ticker=t, weight=float(w))
        for t, w in zip(short_returns, w_short, strict=True)
    ]
    return long_weights, short_weights, long_excluded + short_excluded, vol


def is_rebalance_due(state: PortfolioState | None, today: date, cadence: Cadence) -> bool:
    """Whether `cadence`'s weights should be re-optimized this run (D5).

    Weekly rebalances every run. Monthly rebalances only on the first run
    of a new calendar month. A missing `state` (first run) is always due.
    """
    if state is None or cadence == "weekly":
        return True
    return (today.year, today.month) != (state.last_rebalance.year, state.last_rebalance.month)


def _weighted_return(
    holdings: list[HoldingWeight], closes: dict[str, dict[date, float]], prev: date, today: date
) -> float | None:
    """Weighted return across `holdings` between `prev` and `today`.

    Sum of ``weight * (price_today / price_prev - 1)``. Returns `None` if
    any holding is missing a close on either date.
    """
    total = 0.0
    for h in holdings:
        prices = closes.get(h.ticker)
        if prices is None or prev not in prices or today not in prices or not prices[prev]:
            return None
        total += h.weight * (prices[today] / prices[prev] - 1.0)
    return total


def _compute_return(
    state: PortfolioState, closes: dict[str, dict[date, float]], today: date
) -> WeeklyReturn | None:
    """This run's realized return using the PRIOR state's target weights.

    D12 — an implicit weekly reset-to-target, noted in the UI caveat.
    """
    ret_long = _weighted_return(state.long, closes, state.as_of, today)
    ret_short = _weighted_return(state.short, closes, state.as_of, today)
    if ret_long is None or ret_short is None:
        logger.warning(
            "missing price data for %s as_of %s; skipping return row", state.cadence, today
        )
        return None
    return WeeklyReturn(
        date=today, ret_long=ret_long, ret_short=ret_short, ret_ls=ret_long - ret_short
    )


def _resolve_pool(state: PortfolioState | None, today: date) -> tuple[list[str], list[str], date]:
    """The pool to optimize over this run.

    Refreshes it only after the D6 90-day freeze window has elapsed, or on
    the very first run.
    """
    if state is None or (today - state.pool_as_of).days >= _POOL_FREEZE_DAYS:
        long_pool, short_pool = load_pool()
        return long_pool, short_pool, today
    return state.pool.long, state.pool.short, state.pool_as_of


def step(
    state: PortfolioState | None,
    closes: dict[str, dict[date, float]],
    today: date,
    cadence: Cadence,
) -> tuple[PortfolioState, WeeklyReturn | None]:
    """Advance one portfolio's state by one cron run (ADR-0012).

    Computes this run's `WeeklyReturn` from the prior state's target
    weights (skipped on the first run for `cadence` — no prior weights
    exist), then rebalances if due — either because the cadence calls for
    it (`is_rebalance_due`) or because the D6 pool freeze has expired.

    Args:
        state: Prior state for `cadence`, or `None` on the first run.
        closes: `date -> close` per ticker, covering every ticker `state`
            or the live presets might reference (see `fetch_closes`).
        today: The run's as-of date.
        cadence: `"weekly"` or `"monthly"`.

    Returns:
        The updated state, and this run's `WeeklyReturn` (`None` on the
        first run for `cadence`, or if a holding's price is missing).
    """
    row = _compute_return(state, closes, today) if state is not None else None
    long_pool, short_pool, pool_as_of = _resolve_pool(state, today)
    pool_refreshed = state is None or pool_as_of != state.pool_as_of
    if state is None or pool_refreshed or is_rebalance_due(state, today, cadence):
        long_w, short_w, excluded, vol = _optimize(long_pool, short_pool, closes)
        new_state = PortfolioState(
            cadence=cadence,
            inception=state.inception if state is not None else today,
            as_of=today,
            last_rebalance=today,
            pool_as_of=pool_as_of,
            lookback_days=_LOOKBACK_DAYS,
            long=long_w,
            short=short_w,
            pool=PortfolioPool(long=long_pool, short=short_pool),
            excluded=excluded,
            ex_ante_vol_annual=vol,
        )
    else:
        new_state = state.model_copy(update={"as_of": today})
    return new_state, row


def load_state(path: Path) -> PortfolioState | None:
    """Load a cadence's `state.json`, or `None` before the first run."""
    if not path.exists():
        return None
    return PortfolioState.model_validate_json(path.read_text())


def save_state(state: PortfolioState, path: Path) -> None:
    """Persist a cadence's `state.json`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2) + "\n")


def _year_path(year: int, *, root: Path) -> Path:
    return root / f"{year}.json"


def _load_year_returns(year: int, *, root: Path) -> dict[str, WeeklyReturn]:
    """Load a per-year return-series file as a date-keyed dict, empty when missing."""
    path = _year_path(year, root=root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {item["date"][:10]: WeeklyReturn.model_validate(item) for item in raw}


def _write_year_returns(year: int, by_date: dict[str, WeeklyReturn], *, root: Path) -> Path:
    """Write a year's return rows as a date-sorted JSON array."""
    root.mkdir(parents=True, exist_ok=True)
    path = _year_path(year, root=root)
    payload = [by_date[k].model_dump(mode="json") for k in sorted(by_date)]
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def merge_return_into_years(row: WeeklyReturn, *, root: Path) -> dict[int, dict[str, WeeklyReturn]]:
    """Merge one run's return row onto its year's on-disk file, in memory only.

    A same-date re-run replaces the existing row rather than duplicating
    it. Mirrors `equity_spy.merge_payload_into_years`.
    """
    by_date = _load_year_returns(row.date.year, root=root)
    by_date[row.date.isoformat()] = row
    return {row.date.year: by_date}


def _resolve_tickers(state: PortfolioState | None) -> list[str]:
    """Every ticker `step` might need this run.

    Union of the live preset pool (in case a refresh is due) and the
    existing frozen pool (if any).
    """
    long_pool, short_pool = load_pool()
    tickers = set(long_pool) | set(short_pool)
    if state is not None:
        tickers |= set(state.pool.long) | set(state.pool.short)
    return sorted(tickers)


def _run_cadence(cadence: Cadence, series_root: Path, state_path: Path, today: date) -> None:
    state = load_state(state_path)
    tickers = _resolve_tickers(state)
    closes = fetch_closes(tickers, today=today)
    if not closes:
        logger.warning("%s portfolio: no price data fetched; skipping run", cadence)
        return
    try:
        new_state, row = step(state, closes, today, cadence)
    except LongShortPortfolioError as exc:
        logger.warning("%s portfolio: %s; skipping run", cadence, exc)
        return
    save_state(new_state, state_path)
    if row is not None:
        by_year = merge_return_into_years(row, root=series_root)
        for year, by_date in sorted(by_year.items()):
            _write_year_returns(year, by_date, root=series_root)
    logger.info("%s portfolio: as_of=%s row=%s", cadence, new_state.as_of, row is not None)


def main() -> None:
    """Cron entrypoint: advance both the weekly and monthly portfolios."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    today = date.today()
    _run_cadence(
        "weekly",
        settings.portfolio_weekly_series_dir,
        settings.portfolio_state_dir / "weekly" / "state.json",
        today,
    )
    _run_cadence(
        "monthly",
        settings.portfolio_monthly_series_dir,
        settings.portfolio_state_dir / "monthly" / "state.json",
        today,
    )


if __name__ == "__main__":
    main()
