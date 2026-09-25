"""Point-in-time backfilled best/worst 25 + backtested long/short 25/25 (ADR-0013).

**Two series, never spliced (D15, ADR-0013 amendment 2026-09-24):**

- **Series B** (the original PR C output) — the reconstructed backfill: every
  base universe ranked by a point-in-time-only reduction of the qte77 Score
  (D2, ``score_at``) at each weekly rank date since inception. Labelled an
  approximation — 6 of the 9 live qte77 Score inputs are reconstructable;
  `forward_pe`/`trailing_peg_ratio`/`beta` are always `None`.
- **Series A** (D16) — the genuine decisions: each rank date is an actual
  `data`-branch snapshot date, ranked with the **full live qte77 Score** by
  reusing :func:`aggregated_scores_best_and_worst.build_universe` unchanged.
  Sparse and irregular (weekly demo-cron dates); the book holds across a
  snapshot gap. No look-ahead or reconstruction — these are the lists a real
  viewer would have seen that day.

Both series apply the same book (D5), costs (D8), metrics (D9) and five
cadences (D7) — D15 headline: "Series B" -> "Series A" in later PRs.

**Freeze, append-only (D17):** once a date's list or a day's return row is
written to either series, it is never recomputed on a later run — only new
dates are appended, and the summary/metrics are recomputed from the frozen
rows. A ``method_version`` bump is the only way to force a one-time full
rebuild (used once, 2026-09-24, for the start-trim fix below + D18's lag).

**Start-trim fix (found 2026-09-24):** `simulate` marks every day in the full
union-of-price-history calendar (which can start decades before a book's
first holding), so its raw output must be trimmed to the book's own first
trade date (:func:`_trim_to_first_trade`) before it is persisted or fed to
`metrics` — otherwise every metric is diluted by thousands of pre-inception
zero-return days.

Public API (pure, individually testable — see the plan's PR C/E test lists):

- :func:`pit_fundamentals` — D2/D3 point-in-time statement ratios.
- :func:`score_at` — D2/D4 point-in-time ``screener_score``.
- :func:`rank_dates` — D6 weekly rank grid.
- :func:`rebalance_dates` — D7 per-cadence rebalance dates.
- :func:`select` — the D7 monthly-buffer selection rule.
- :func:`simulate` — D5/D8 daily-marked drift + cost simulation.
- :func:`metrics` — D9 per-cadence gross/net metrics.
- :func:`null_percentile` — D10 seeded random-book benchmark.
- :func:`fidelity` — D11 Spearman check against genuine live snapshots.

I/O layer: :func:`fetch_frames` (yfinance statements, one immutable file
per ticker per fetch date under the gitignored
``results/prices/statements/<ticker>/<fetch-date>.json``, merged
first-fetch-wins per period — a layout a future PR can sync to a private
repo so history outgrows yfinance's ~4-5 FY window), :func:`write_closes_cache`
(``results/prices/closes/<ticker>.csv``, same sync-target posture), the
``write_*``/``read_*`` contract persistence helpers, and :func:`main`
(cron entrypoint — full deterministic recompute, D13).

Never commits raw prices or statement line items — only returns, scores,
ranks, weights and metrics reach the ``data`` branch (see
``docs/data-sources.md`` guardrails).
"""

from __future__ import annotations

import bisect
import itertools
import json
import logging
import math
import random
import re
import statistics
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast

import numpy as np
import pandas as pd
import yfinance as yf
from pydantic import BaseModel, ConfigDict
from tqdm import tqdm

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.equity_spy import _fetch_history_closes
from analyze_stock_kpi.data_sources.fundamentals import (
    FundamentalsSnapshot,
    _batch_close_prices,
    _close_between,
    _compute_sortino,
    _find_row,
    _read_rd_revenue,
    _safe_ratio,
)
from analyze_stock_kpi.domain.composite_scores import screener_score
from analyze_stock_kpi.domain.universe import PRESET_DIR, _read_symbol_file
from analyze_stock_kpi.orchestrators.aggregated_scores_best_and_worst import build_universe

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

logger = logging.getLogger(__name__)

Frames = tuple["pd.DataFrame | None", "pd.DataFrame | None"]
"""One ticker's ``(income_stmt, balance_sheet)`` as yfinance returns them."""

Cadence = Literal["monthly", "quarterly_filings", "monthly_buffer", "weekly", "yearly", "buy_hold"]
CADENCES: tuple[Cadence, ...] = (
    "monthly",
    "quarterly_filings",
    "monthly_buffer",
    "weekly",
    "yearly",
    "buy_hold",
)
PRIMARY_CADENCE: Cadence = "monthly"

_BOOK_SIZE = 25
"""Long/short leg size (D5)."""

_BUFFER_RANK = 40
"""D7 monthly-buffer: a held name is kept while its rank stays inside this band."""

_US_FILING_LAG_DAYS = 90
"""D3/D18: a US ticker's (no exchange suffix) statement column is usable at
``as_of`` iff ``period_end + 90d <= as_of``."""

_NON_US_FILING_LAG_DAYS = 120
"""D18: a non-US ticker (any ``.XX`` exchange suffix, e.g. ``.DE``/``.SA``/``.T``/``.KS``)
files later (20-F etc.), so its statement columns need a longer lag."""

_METHOD_VERSION_B = "2"
"""D17/D18: series B's method version. Bumped once (2026-09-24) to apply the
start-trim fix (:func:`_trim_to_first_trade`) and the D18 non-US filing lag —
this single bump triggers series B's one-time full rebuild (:func:`_reset_year_files`)."""

_METHOD_VERSION_A = "1"
"""D16: series A's method version (its first-ever run)."""

_GENUINE_START = date(2026, 5, 31)
"""D16: the first date every D1 base universe has a genuine `data`-branch
demo snapshot (verified via the committed `results/demo/<universe>/*.json`
file set) — series A's rank dates start here."""

_COST_BPS = 10.0
"""D8: one-way-turnover trading cost, in basis points."""

_MIN_MONTHS_FOR_METRICS = 12
"""D9: nothing is annualized from fewer than 12 months of monthly returns."""

_CI90_Z = 1.645
"""Two-sided 90% normal critical value, used for the D9 mean-monthly-return CI."""

_MIN_ELIGIBLE_START = 200
"""D6: the backfill starts at the first grid date with at least this many
eligible tickers (`score_bt` not `None` and >= 1y of closes)."""

_NULL_DRAWS = 1000
"""D10: number of seeded random 25/25 books in the null benchmark."""

_NULL_SEED = 42

_SORTINO_LOOKBACK_YEARS = 1

_BACKTEST_SYMBOL = "_backtest_"
"""Placeholder `FundamentalsSnapshot.symbol` for `score_at` — the score
formula never reads `symbol`, so any constant value is equivalent."""

_SCORE_INPUT_FIELDS: tuple[str, ...] = (
    "return_on_equity",
    "return_on_assets",
    "operating_margins",
    "rd_to_revenue",
    "current_ratio",
    "sortino_ratio",
)
"""D2: the only point-in-time-reconstructable inputs `score_at` feeds into
`screener_score` — `forward_pe`/`trailing_peg_ratio`/`beta` are always `None`."""

_LIVE_SCORE_INPUT_FIELDS: tuple[str, ...] = (
    "return_on_equity",
    "return_on_assets",
    "operating_margins",
    "rd_to_revenue",
    "forward_pe",
    "trailing_peg_ratio",
    "beta",
    "current_ratio",
    "sortino_ratio",
)
"""D16: all 9 `screener_score` inputs series A ranks with (the full live qte77
Score, as stored in the genuine snapshot — no inputs forced to `None`)."""

_DERIVED_UNIVERSE_PREFIXES = ("aggregated-scores-", "enhanced-kpi-screener-", "crypto-")

_CAVEATS: tuple[str, ...] = (
    "Survivorship bias: the universe is each preset's CURRENT membership, not "
    "the historical constituent list, so delisted/removed names never appear "
    "in the backfill.",
    "The `sp500` preset is today's top-100-by-cap tickers, not the S&P 500's "
    "actual historical membership — a size look-ahead.",
    "Point-in-time fundamentals use yfinance's LATEST-RESTATED annual figures, "
    "not the as-originally-reported values a contemporaneous investor would "
    "have seen.",
    "No SEC filing dates are available from yfinance; a statement column is "
    "treated as usable 90 days after its period end for a US ticker, 120 "
    "days for non-US (D18) — both an approximation of the real filing lag.",
    "A ticker with no price on a given day is treated as flat (0% return) "
    "that day; a name that stops trading entirely after entry is held at its "
    "last known close rather than dropped.",
    "A rebalance trades on the first day after its rank date on which every "
    "name in the old and new books has its own close, so each fill is at the "
    "ticker's own closing price; a rebalance can therefore wait a day or two "
    "across mismatched exchange holidays.",
    "Non-US filing-lag classification (D18) is suffix-based plus a small "
    "disclosed exception list for known no-suffix foreign issuers and an "
    "OTC-ADR ticker-shape heuristic — not a full country lookup, so some "
    "no-suffix foreign names may still be misclassified as US.",
    "Returns are local-currency, gross of FX, financing and borrow costs; "
    "only the 10 bp one-way-turnover trading cost is modelled.",
    "Any single-day move above ±50 % is treated as a data glitch and set to "
    "0 %. That also removes a few genuine small-cap moves (e.g. a biotech "
    "jump), and a ticker with any non-positive adjusted close is excluded.",
    "The `yearly` cadence rebalances once a year; nothing is annualized from "
    "fewer than 12 months of monthly returns (D9), so its metrics stay "
    "`null` far longer than the other cadences'.",
    "The null benchmark's random books use the same fill rule and are "
    "annualized by calendar span, like the strategy's own metrics.",
    "This is a hypothetical, backward-looking construction — not a live "
    "track record and not investment advice.",
)

_CAVEATS_GENUINE: tuple[str, ...] = (
    "Survivorship bias: the universe is each preset's CURRENT membership, not "
    "the historical constituent list, so delisted/removed names never appear "
    "in the ranking.",
    "The `sp500` preset is today's top-100-by-cap tickers, not the S&P 500's "
    "actual historical membership — a size look-ahead.",
    "Rank dates are the irregular dates the live aggregator actually "
    "snapshotted (the weekly demo cron), not a fixed grid; across a gap "
    "between two snapshot dates (e.g. 2026-07-12 -> 2026-09-21) the book is "
    "held unchanged.",
    "A ticker with no price on a given day is treated as flat (0% return) "
    "that day; a name that stops trading entirely after entry is held at its "
    "last known close rather than dropped.",
    "A rebalance trades on the first day after its rank date on which every "
    "name in the old and new books has its own close, so each fill is at the "
    "ticker's own closing price; a rebalance can therefore wait a day or two "
    "across mismatched exchange holidays.",
    "Returns are local-currency, gross of FX, financing and borrow costs; "
    "only the 10 bp one-way-turnover trading cost is modelled.",
    "Any single-day move above ±50 % is treated as a data glitch and set to "
    "0 %. That also removes a few genuine small-cap moves (e.g. a biotech "
    "jump), and a ticker with any non-positive adjusted close is excluded.",
    "The `monthly_buffer` cadence has no buffer effect here: the live "
    "aggregator publishes only the top/bottom 25 each run, so every "
    "rebalance is a fresh selection identical to the `monthly` cadence's "
    "holdings.",
    "Null benchmark and fidelity are not yet published for series A (fewer "
    "than 12 monthly rebalances so far) — both stay `null` until enough "
    "history accumulates.",
    "The `yearly` cadence rebalances once a year; nothing is annualized from "
    "fewer than 12 months of monthly returns (D9), so its metrics stay "
    "`null` far longer than the other cadences'.",
    "This is a hypothetical, backward-looking construction — not a live "
    "track record and not investment advice.",
)


# ----- Frozen data contract (pydantic) -----


class BacktestDailyRow(BaseModel):
    """One trading day's marked return + turnover for one cadence (D5/D8)."""

    model_config = ConfigDict(frozen=True)

    date: date
    ret_long: float
    ret_short: float
    ret_ls_gross: float
    ret_ls_net: float
    turnover: float


class RankEntry(BaseModel):
    """One ticker's point-in-time score at a rank date."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    score: float


class BacktestListEntry(BaseModel):
    """One weekly rank date's backfilled best/worst 25 (D6)."""

    model_config = ConfigDict(frozen=True)

    date: date
    eligible: int
    best: list[RankEntry]
    worst: list[RankEntry]


TradeReason = Literal[
    "initial",
    "scheduled_weekly",
    "scheduled_monthly",
    "quarterly_after_filings",
    "scheduled_yearly",
    "buffer_exit",
    "buy_hold_initial",
]
"""D21: why a rebalance happened. `buffer_exit` is `monthly_buffer`-only, and only
when this rebalance actually dropped a held name for exceeding the buffer rank;
`initial` is every other cadence's first-ever rebalance; `buy_hold_initial` is
`buy_hold`'s single (and only) rebalance."""


class RankedTicker(BaseModel):
    """One entered/exited ticker's rank + score AT THE RANK DATE (D21).

    `rank` follows `aggregated_scores_best_and_worst.AuditRow`'s signed
    convention: `+1` is the single best-ranked ticker, `-1` the single
    worst-ranked. Both `rank` and `score` are `None` when not determinable —
    series A has no full ranked pool to look an EXITED ticker's current
    rank up in (D16), so its exits are always `(None, None)`; series B
    always populates both.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    rank: int | None
    score: float | None


class LegChange(BaseModel):
    """One leg's (long or short) entered/exited tickers at a rebalance (D21)."""

    model_config = ConfigDict(frozen=True)

    entered: list[RankedTicker]
    exited: list[RankedTicker]


class TradeLogEntry(BaseModel):
    """One rebalance's WHEN/WHY/WHAT (D21) — the rebalance log.

    `turnover` here is the STATIC target-to-target one-way turnover (ignores
    the intraperiod price drift `simulate`'s cost-bearing turnover factors
    in) — a simpler, informational figure for the log, not the exact
    cost-driving value in the daily series.
    """

    model_config = ConfigDict(frozen=True)

    rank_date: date
    trade_date: date
    reason: TradeReason
    long: LegChange
    short: LegChange
    turnover: float


class MetricsBlock(BaseModel):
    """D9 metrics for one gross/net leg of one cadence.

    Every field is `None` when fewer than `_MIN_MONTHS_FOR_METRICS` months
    of returns are available (nothing is annualized from a too-short run).
    """

    model_config = ConfigDict(frozen=True)

    ann_return: float | None = None
    ann_vol: float | None = None
    max_drawdown: float | None = None
    ann_turnover: float | None = None
    long_ann_return: float | None = None
    short_ann_return: float | None = None
    beta: float | None = None
    hit_rate: float | None = None
    mean_monthly_return: float | None = None
    ci90: tuple[float, float] | None = None
    t_stat: float | None = None


class CadenceMetrics(BaseModel):
    """One cadence's gross + net `MetricsBlock` plus its rebalance count."""

    model_config = ConfigDict(frozen=True)

    gross: MetricsBlock
    net: MetricsBlock
    rebalances: int


class NullBenchmark(BaseModel):
    """D10: the seeded random-book null benchmark result."""

    model_config = ConfigDict(frozen=True)

    n: int
    percentile: float
    median_net_ann: float


class FidelityDate(BaseModel):
    """One genuine-snapshot date's Spearman rho (D11)."""

    model_config = ConfigDict(frozen=True)

    date: date
    rho: float | None
    n: int


class Fidelity(BaseModel):
    """D11: per-date fidelity checks + their median."""

    model_config = ConfigDict(frozen=True)

    per_date: list[FidelityDate]
    median_rho: float | None


class BacktestSummary(BaseModel):
    """The full frozen-contract summary, one per series.

    Series B writes `results/backtest/summary.json`; series A writes
    `results/backtest_genuine/summary.json`. `null`/`fidelity` are `None`
    for series A until it has >= 12 monthly rebalances (D16) — series B
    always populates both.
    """

    model_config = ConfigDict(frozen=True)

    method_version: str
    as_of: date
    start: date
    universes: list[str]
    score_inputs: list[str]
    cost_bps: float
    primary: str
    cadences: dict[str, CadenceMetrics]
    null: NullBenchmark | None
    fidelity: Fidelity | None
    caveats: list[str]


# ----- D2/D3/D4: point-in-time fundamentals + score -----


_KNOWN_NON_US_NO_SUFFIX: frozenset[str] = frozenset(
    {"ASML", "TSM", "NVO", "SAP", "UL", "NTES", "BIP"}
)
"""D18/finding-#8 (2026-09-24): well-known non-US issuers that trade on a US exchange
without an exchange suffix (ADRs/ordinaries), so the plain suffix rule misclassifies
them as US (90d lag). Not exhaustive — a `FundamentalsSnapshot.country`-based
classification is a documented follow-up (would need a new fetch this module doesn't
otherwise make); this is a disclosed, bounded interim fix for the audit's named
examples not already covered by `_is_otc_adr_shaped`."""


def _is_otc_adr_shaped(ticker: str) -> bool:
    """A 5-letter, all-alpha, `Y`-ending ticker — the conventional OTC ADR shape.

    E.g. `DANOY`, `RHHBY`, `LVMUY`. Verified against this repo's actual
    universe 2026-09-24: every no-suffix 5-letter `Y`-ender in it is a
    genuine foreign ADR; 4-letter US tickers ending in `Y` (e.g. `ORLY`)
    are excluded by the length check.
    """
    return len(ticker) == 5 and ticker.isalpha() and ticker.endswith("Y")


def _filing_lag_days(ticker: str) -> int:
    """D18: 90 days for a US ticker, 120 for non-US.

    Non-US = any `.XX` exchange suffix, a known no-suffix foreign issuer
    (`_KNOWN_NON_US_NO_SUFFIX`), or an OTC-ADR-shaped ticker
    (`_is_otc_adr_shaped`) — both interim fixes for finding #8 (2026-09-24),
    since yfinance exposes no per-ticker filing dates or country field here.
    """
    if "." in ticker or ticker in _KNOWN_NON_US_NO_SUFFIX or _is_otc_adr_shaped(ticker):
        return _NON_US_FILING_LAG_DAYS
    return _US_FILING_LAG_DAYS


def _usable_column(frame: pd.DataFrame | None, as_of: date, lag_days: int) -> pd.Timestamp | None:
    """Latest column whose ``period_end + lag_days <= as_of``, or `None` (D3/D18).

    D22 foresight guard, statement half: the ONLY function that may pick a
    statement column for a rank-date ``as_of`` computation (paired with
    ``_closes_as_of``, the price half).
    """
    if frame is None or frame.empty:
        return None
    usable = [
        c
        for c in frame.columns
        if isinstance(c, pd.Timestamp) and (c.date() + timedelta(days=lag_days)) <= as_of
    ]
    return max(usable) if usable else None


def pit_fundamentals(frames: Frames, as_of: date, ticker: str) -> dict[str, float | None]:
    """Point-in-time D2 ratios usable at ``as_of`` (D3/D18).

    ``frames`` is ``(income_stmt, balance_sheet)`` as yfinance returns them
    (columns = period-end Timestamps). A column is usable at ``as_of`` iff
    ``period_end + lag_days <= as_of`` — 90 days for a US ``ticker`` (no
    exchange suffix), 120 for non-US (D18; no filing dates in yfinance, so
    this is a documented approximation of the real filing lag) — the latest
    usable column of each frame is picked independently. Missing
    rows/frames yield `None` per field rather than raising.
    ``rd_to_revenue`` reuses ``fundamentals._read_rd_revenue`` unchanged
    (DRY); the other four ratios reuse ``fundamentals._find_row``.
    """
    income_stmt, balance_sheet = frames
    lag_days = _filing_lag_days(ticker)
    ic_col = _usable_column(income_stmt, as_of, lag_days)
    bs_col = _usable_column(balance_sheet, as_of, lag_days)
    out: dict[str, float | None] = dict.fromkeys(_SCORE_INPUT_FIELDS[:-1])

    net_income: float | None = None
    if ic_col is not None and income_stmt is not None:
        latest_ic = cast("pd.Series", income_stmt[ic_col])
        net_income = _find_row(latest_ic, "net income")
        total_revenue = _find_row(latest_ic, "total revenue")
        operating_income = _find_row(latest_ic, "operating income")
        out["operating_margins"] = _safe_ratio(operating_income, total_revenue)
        ic_single_col = cast("pd.DataFrame", income_stmt[[ic_col]])
        out["rd_to_revenue"] = _safe_ratio(*_read_rd_revenue(ic_single_col))

    if bs_col is not None and balance_sheet is not None:
        latest_bs = cast("pd.Series", balance_sheet[bs_col])
        stockholders_equity = _find_row(latest_bs, "stockholders equity")
        total_assets = _find_row(latest_bs, "total assets")
        current_assets = _find_row(latest_bs, "current assets")
        current_liabilities = _find_row(latest_bs, "current liabilities")
        out["return_on_equity"] = _safe_ratio(net_income, stockholders_equity)
        out["return_on_assets"] = _safe_ratio(net_income, total_assets)
        out["current_ratio"] = _safe_ratio(current_assets, current_liabilities)

    # Found 2026-09-24: `_find_row`/`_safe_ratio` can hand back `NaN` (a missing yfinance
    # row cast to float), which `screener_score`'s `_normalize_term` used to silently score
    # 100/0 instead of excluding — defense in depth alongside that fix, at this PIT
    # reconstruction's own boundary.
    return {k: (v if v is not None and math.isfinite(v) else None) for k, v in out.items()}


def _closes_as_of(closes: pd.Series, as_of: date) -> pd.Series:
    """D22 foresight guard: the ONLY function that may hand price data to `as_of`.

    Paired with `_usable_column` (the statement-side half of the same guard,
    D3/D18's `period_end + lag_days <= as_of` check) — together they are the
    single gate between raw yfinance data and a `score_at`/`pit_fundamentals`
    result, so an auditor only has two functions to check for a look-ahead
    leak. Returns `closes` with every observation dated strictly after
    `as_of` dropped, THEN `dropna()`-ed (found 2026-09-24: a batch-download
    column can carry interior `NaN` gaps — e.g. a non-US market closed on a
    US holiday the batch's calendar assumes is a trading day — and leaving
    them in means `pct_change()` compares across the gap as if it were one
    day, distorting the Sortino ratio; `fundamentals._windowed_sortinos`
    already applies the same `dropna()` for the same reason). Also matches
    `test_poisoning_data_after_rank_date_does_not_change_the_ranked_list`'s
    "byte-identical" guarantee.
    """
    as_of_ts = cast("pd.Timestamp", pd.Timestamp(as_of))
    sliced = cast("pd.Series", closes[closes.index <= as_of_ts])
    return cast("pd.Series", sliced.dropna())


def score_at(fund: dict[str, float | None], closes: pd.Series, as_of: date) -> float | None:
    """D2/D4: `screener_score` on a point-in-time-only snapshot.

    Builds a `FundamentalsSnapshot` from `fund`'s five D3 ratios plus a 1y
    trailing Sortino sliced from `closes` up to `as_of`
    (`fundamentals._compute_sortino`, unchanged). `forward_pe`,
    `trailing_peg_ratio` and `beta` stay `None` forever (D2), so Valuation
    always drops from `screener_score` and Risk degrades to the current
    ratio alone. Reuses `screener_score` unchanged (DRY) — no seam, because
    the input set never changes. `closes` is routed through `_closes_as_of`
    first (D22): nothing dated after `as_of` can reach the Sortino window.
    """
    as_of_ts = cast("pd.Timestamp", pd.Timestamp(as_of))
    guarded = _closes_as_of(closes, as_of)
    cutoff = as_of_ts - pd.DateOffset(years=_SORTINO_LOOKBACK_YEARS)
    window = _close_between(guarded, cutoff, as_of_ts)
    snap = FundamentalsSnapshot.model_validate(
        {
            "symbol": _BACKTEST_SYMBOL,
            "return_on_equity": fund.get("return_on_equity"),
            "return_on_assets": fund.get("return_on_assets"),
            "operating_margins": fund.get("operating_margins"),
            "rd_to_revenue": fund.get("rd_to_revenue"),
            "current_ratio": fund.get("current_ratio"),
            "sortino_ratio": _compute_sortino(window),
        }
    )
    return screener_score(snap)


# ----- D6/D7: rank grid + cadence rebalance dates -----


def rank_dates(calendar: list[date]) -> list[date]:
    """D6: the last trading day of each ISO week present in `calendar`."""
    by_week: dict[tuple[int, int], date] = {}
    for d in calendar:
        key = d.isocalendar()[:2]
        if key not in by_week or d > by_week[key]:
            by_week[key] = d
    return sorted(by_week.values())


def _monthly_dates(grid: list[date]) -> list[date]:
    """First grid date of each calendar month."""
    out: list[date] = []
    seen: set[tuple[int, int]] = set()
    for d in grid:
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _yearly_dates(grid: list[date]) -> list[date]:
    """D20: first grid date of each calendar year."""
    out: list[date] = []
    seen: set[int] = set()
    for d in grid:
        if d.year not in seen:
            seen.add(d.year)
            out.append(d)
    return out


_QUARTERLY_TRIGGER_MD: tuple[tuple[int, int], ...] = ((2, 15), (5, 15), (8, 15), (11, 15))


def _quarterly_filing_dates(grid: list[date]) -> list[date]:
    """First grid date on/after each Feb/May/Aug/Nov 15 spanned by `grid`."""
    if not grid:
        return []
    years = range(grid[0].year, grid[-1].year + 1)
    triggers = sorted(date(y, m, d) for y in years for m, d in _QUARTERLY_TRIGGER_MD)
    out: list[date] = []
    for trig in triggers:
        candidates = [d for d in grid if d >= trig]
        if candidates:
            out.append(min(candidates))
    return sorted(set(out))


def rebalance_dates(cadence: str, grid: list[date]) -> list[date]:
    """D7/D20: the subset of `grid` (D6's weekly rank dates) each cadence trades on."""
    if not grid:
        return []
    if cadence in ("weekly",):
        return list(grid)
    if cadence in ("monthly", "monthly_buffer"):
        return _monthly_dates(grid)
    if cadence == "yearly":
        return _yearly_dates(grid)
    if cadence == "quarterly_filings":
        return _quarterly_filing_dates(grid)
    if cadence == "buy_hold":
        return [grid[0]]
    raise ValueError(f"unknown cadence: {cadence}")


def _buffer_leg(ranks: list[str], prev: list[str], book_size: int, buffer: int) -> list[str]:
    """One leg's D7 buffer rule: keep-if-in-band, refill-from-the-top."""
    rank_of = {t: i + 1 for i, t in enumerate(ranks)}
    kept = [t for t in prev if rank_of.get(t, len(ranks) + 1) <= buffer]
    for t in ranks:
        if len(kept) >= book_size:
            break
        if t not in kept:
            kept.append(t)
    return kept[:book_size]


def select(
    ranks: list[str],
    cadence: str,
    prev_holdings: tuple[list[str], list[str]] | None,
    *,
    book_size: int = _BOOK_SIZE,
    buffer: int = _BUFFER_RANK,
) -> tuple[list[str], list[str]]:
    """The D7 selection rule for one rank date: `(long_tickers, short_tickers)`.

    `ranks` is every eligible ticker for the rank date, sorted best-to-worst
    by `score_at`. Every cadence except `"monthly_buffer"` takes a fresh
    top/bottom `book_size`. `"monthly_buffer"` keeps a `prev_holdings` name
    while its rank stays within `buffer` of its own end, refilling openings
    from the best-ranked names (worst-ranked for the short leg) not already
    held. Callers only invoke this once `len(ranks) >= 2 * book_size`, so
    the top/bottom slices never overlap.
    """
    if cadence != "monthly_buffer" or prev_holdings is None:
        return ranks[:book_size], list(reversed(ranks[-book_size:]))
    prev_long, prev_short = prev_holdings
    long_names = _buffer_leg(ranks, prev_long, book_size, buffer)
    short_names = _buffer_leg(list(reversed(ranks)), prev_short, book_size, buffer)
    return long_names, short_names


# ----- D21: the rebalance log -----


def _leg_diff(prev: list[str], new: list[str]) -> tuple[list[str], list[str]]:
    """D21: `(entered, exited)` — tickers newly in `new`, and tickers dropped from `prev`."""
    prev_set, new_set = set(prev), set(new)
    entered = [t for t in new if t not in prev_set]
    exited = [t for t in prev if t not in new_set]
    return entered, exited


def _rebalance_reason(cadence: str, *, is_first: bool, had_buffer_exit: bool) -> TradeReason:
    """D21: WHY this rebalance happened."""
    if cadence == "buy_hold":
        return "buy_hold_initial"
    if is_first:
        return "initial"
    if cadence == "monthly_buffer" and had_buffer_exit:
        return "buffer_exit"
    scheduled: dict[str, TradeReason] = {
        "weekly": "scheduled_weekly",
        "monthly": "scheduled_monthly",
        "monthly_buffer": "scheduled_monthly",
        "quarterly_filings": "quarterly_after_filings",
        "yearly": "scheduled_yearly",
    }
    return scheduled[cadence]


# ----- D5/D8: simulate -----


def _drift_leg(weights: dict[str, float], day_returns: dict[str, float]) -> dict[str, float]:
    """One day's weight drift within a self-financing leg (D5).

    ``new_w_i = old_w_i * (1 + r_i) / (1 + leg_return)`` where
    ``leg_return = sum(old_w_i * r_i)`` keeps the leg summing to 1 after any
    price move. An empty leg (no holdings yet) stays empty.
    """
    if not weights:
        return {}
    leg_return = sum(w * day_returns.get(t, 0.0) for t, w in weights.items())
    denom = 1.0 + leg_return
    if denom == 0:
        return dict(weights)
    return {t: w * (1.0 + day_returns.get(t, 0.0)) / denom for t, w in weights.items()}


def _turnover(
    target_long: dict[str, float],
    target_short: dict[str, float],
    drifted_long: dict[str, float],
    drifted_short: dict[str, float],
) -> float:
    """D8: one-way turnover, ``0.5 * sum(|w_new - w_drifted|)`` over both legs."""
    long_diff = sum(
        abs(target_long.get(t, 0.0) - drifted_long.get(t, 0.0))
        for t in set(target_long) | set(drifted_long)
    )
    short_diff = sum(
        abs(target_short.get(t, 0.0) - drifted_short.get(t, 0.0))
        for t in set(target_short) | set(drifted_short)
    )
    return 0.5 * (long_diff + short_diff)


def _cost(turnover: float) -> float:
    """D8: ``10 bp * one-way turnover``."""
    return (_COST_BPS / 10_000.0) * turnover


def simulate(
    weights_by_trade_date: dict[date, tuple[dict[str, float], dict[str, float]]],
    returns: dict[str, dict[date, float]],
) -> list[BacktestDailyRow]:
    """Daily-marked equal-weight long/short simulation with drift + costs (D5/D8).

    `weights_by_trade_date` maps each TRADE date — already the trading day
    after its rank date, so there is no same-close look-ahead — to that
    rebalance's `(long, short)` target weights, each leg summing to 1.
    `returns` is every ticker's per-calendar-day simple return (0.0 on a
    day it didn't trade — D5's union-calendar rule). The full calendar is
    the sorted union of every ticker's return dates.

    Weights drift day to day between rebalances (`_drift_leg`) and reset to
    the new target at each trade date; that day's own `ret_long`/`ret_short`
    still use the PRE-swap (drifted) weights — the swap happens at the
    day's close. One-way turnover (`_turnover`) and its cost (`_cost`) are
    charged on the trade date and only reduce `ret_ls_net`.
    """
    calendar = sorted({d for series in returns.values() for d in series})
    rows: list[BacktestDailyRow] = []
    current_long: dict[str, float] = {}
    current_short: dict[str, float] = {}
    for day in calendar:
        day_returns = {t: series.get(day, 0.0) for t, series in returns.items()}
        ret_long = sum(w * day_returns.get(t, 0.0) for t, w in current_long.items())
        ret_short = sum(w * day_returns.get(t, 0.0) for t, w in current_short.items())
        drifted_long = _drift_leg(current_long, day_returns)
        drifted_short = _drift_leg(current_short, day_returns)
        if day in weights_by_trade_date:
            target_long, target_short = weights_by_trade_date[day]
            turnover = _turnover(target_long, target_short, drifted_long, drifted_short)
            current_long, current_short = dict(target_long), dict(target_short)
        else:
            turnover = 0.0
            current_long, current_short = drifted_long, drifted_short
        ret_ls_gross = ret_long - ret_short
        rows.append(
            BacktestDailyRow(
                date=day,
                ret_long=ret_long,
                ret_short=ret_short,
                ret_ls_gross=ret_ls_gross,
                ret_ls_net=ret_ls_gross - _cost(turnover),
                turnover=turnover,
            )
        )
    return rows


# ----- D9: metrics -----


def _monthly_returns(dates: list[date], daily: list[float]) -> dict[tuple[int, int], float]:
    """Compound `daily` returns within each calendar month."""
    out: dict[tuple[int, int], float] = {}
    for d, r in zip(dates, daily, strict=True):
        key = (d.year, d.month)
        out[key] = (1.0 + out[key]) * (1.0 + r) - 1.0 if key in out else r
    return out


def _max_drawdown(daily: list[float]) -> float:
    """Peak-to-trough drawdown of the cumulative index built from `daily`."""
    peak = 1.0
    value = 1.0
    max_dd = 0.0
    for r in daily:
        value *= 1.0 + r
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1.0)
    return max_dd


def _span_years(dates: list[date]) -> float:
    """Calendar years covered by `dates` (each row is one period ending on its date).

    The union calendar has ~260 rows/year, not 252, so annualizing by row
    count would understate returns (foresight-audit #6).
    """
    n = len(dates)
    if n < 2:
        return 0.0
    return (dates[-1] - dates[0]).days * n / (n - 1) / 365.25


def _annualize_total(daily: list[float], years: float) -> float:
    """Compound `daily` returns then annualize over `years` calendar years."""
    total = 1.0
    for r in daily:
        total *= 1.0 + r
    return total ** (1.0 / years) - 1.0 if years > 0 else 0.0


_BETA_MIN_VARIANCE = 1e-12
"""Below this, SPY's variance is floating-point noise, not signal — `cov/var`
on two near-constant series is numerically meaningless even when it happens
to compute a determinate-looking ratio."""


def _beta(daily: list[float], dates: list[date], spy_returns: dict[date, float]) -> float | None:
    """Realized beta: `cov(daily, spy) / var(spy)` over overlapping dates."""
    paired = [(r, spy_returns[d]) for d, r in zip(dates, daily, strict=True) if d in spy_returns]
    if len(paired) < 2:
        return None
    ys = np.array([p[0] for p in paired])
    xs = np.array([p[1] for p in paired])
    var = xs.var()
    if var < _BETA_MIN_VARIANCE:
        return None
    return float(np.cov(ys, xs, bias=True)[0, 1] / var)


def _metrics_block(
    dates: list[date],
    daily: list[float],
    daily_long: list[float],
    daily_short: list[float],
    turnover: list[float],
    spy_returns: dict[date, float],
) -> MetricsBlock:
    """D9 metrics for one gross-or-net daily return series."""
    monthly = _monthly_returns(dates, daily)
    if len(monthly) < _MIN_MONTHS_FOR_METRICS:
        return MetricsBlock()
    monthly_values = list(monthly.values())
    n = len(monthly_values)
    mean_m = float(np.mean(monthly_values))
    std_m = float(np.std(monthly_values, ddof=1)) if n > 1 else 0.0
    se = std_m / (n**0.5) if n > 0 else 0.0
    years = _span_years(dates)
    periods_per_year = len(dates) / years if years > 0 else 0.0
    return MetricsBlock(
        ann_return=_annualize_total(daily, years),
        ann_vol=float(np.std(daily, ddof=1) * (periods_per_year**0.5)) if len(daily) > 1 else None,
        max_drawdown=_max_drawdown(daily),
        ann_turnover=sum(turnover) / years if years > 0 else None,
        long_ann_return=_annualize_total(daily_long, years),
        short_ann_return=_annualize_total(daily_short, years),
        beta=_beta(daily, dates, spy_returns),
        hit_rate=sum(1 for v in monthly_values if v > 0) / n,
        mean_monthly_return=mean_m,
        ci90=(mean_m - _CI90_Z * se, mean_m + _CI90_Z * se),
        t_stat=(mean_m / se) if se > 0 else None,
    )


def metrics(
    rows: list[BacktestDailyRow], spy_returns: dict[date, float]
) -> tuple[MetricsBlock, MetricsBlock]:
    """D9: `(gross, net)` metrics for one cadence's daily rows."""
    dates = [r.date for r in rows]
    daily_long = [r.ret_long for r in rows]
    daily_short = [r.ret_short for r in rows]
    turnover = [r.turnover for r in rows]
    gross = _metrics_block(
        dates, [r.ret_ls_gross for r in rows], daily_long, daily_short, turnover, spy_returns
    )
    net = _metrics_block(
        dates, [r.ret_ls_net for r in rows], daily_long, daily_short, turnover, spy_returns
    )
    return gross, net


# ----- D10: null benchmark -----


def _price_asof(series: pd.Series, d: date) -> float | None:
    """Last available close at or before `d` (drives the D5 held-at-last-close rule).

    `None` when `d` is before `series`' first observation — found 2026-09-24:
    `.asof()` then returns `NaT`, which the previous `isinstance(idx, float)`
    check never caught (`NaT` is not a `float`), so `series.loc[NaT]` raised
    an unhandled `KeyError` for any ticker whose history starts after `d`
    (a newer listing evaluated at an early null-benchmark draw date) — or
    when the located value itself is `NaN`. `pd.isna` covers both `NaT` and
    `NaN` uniformly.
    """
    idx = series.index.asof(pd.Timestamp(d))
    if bool(pd.isna(idx)):
        return None
    value = series.loc[idx]
    return None if bool(pd.isna(value)) else float(value)


def _ticker_period_return(series: pd.Series, start: date, end: date) -> float:
    """Total return of one ticker between two dates, via `_price_asof`."""
    p0, p1 = _price_asof(series, start), _price_asof(series, end)
    if p0 is None or p1 is None or p0 == 0:
        return 0.0
    return p1 / p0 - 1.0


def _leg_period_return(
    weights: dict[str, float], closes: dict[str, pd.Series], start: date, end: date
) -> float:
    """An equal-weight leg's period return.

    Equals the mean of its holdings' own period returns — exact for a
    static, no-interim-rebalance leg.
    """
    if not weights:
        return 0.0
    return sum(
        w * _ticker_period_return(closes[t], start, end) for t, w in weights.items() if t in closes
    )


def _drift_to_end(
    weights: dict[str, float], closes: dict[str, pd.Series], start: date, end: date
) -> dict[str, float]:
    """A leg's weights at `end`, drifted from `start` with no interim trades."""
    if not weights:
        return {}
    leg_ret = _leg_period_return(weights, closes, start, end)
    denom = 1.0 + leg_ret
    if denom == 0:
        return dict(weights)
    return {
        t: w * (1.0 + _ticker_period_return(closes[t], start, end)) / denom
        for t, w in weights.items()
        if t in closes
    }


def _random_book_net_ann(
    rng: random.Random,
    rebal_dates: list[date],
    eligible_by_date: dict[date, list[str]],
    closes: dict[str, pd.Series],
    cost_bps: float,
    book_size: int,
    calendar: list[date] | None = None,
    own_dates: dict[str, list[date]] | None = None,
) -> float | None:
    """One null draw's net annualized return via the period-return shortcut.

    Uses the exact period-total-return identity for a static equal-weight
    leg (no interim rebalancing) instead of a full daily simulation, so
    `_NULL_DRAWS` draws stay fast — this is a summary-only benchmark, not
    part of the persisted daily contract. Each book is drawn at its rank date,
    filled with the strategy's own `_trade_date` rule, and earns exactly the
    span to the next book's fill (foresight-audit #6).
    """
    books: list[tuple[date, dict[str, float], dict[str, float]]] = []
    prev_names: list[str] = []
    for t in rebal_dates:
        pool = eligible_by_date.get(t, [])
        if len(pool) < 2 * book_size:
            continue
        sample = rng.sample(pool, 2 * book_size)
        fill = _trade_date(calendar, t, sample + prev_names, own_dates) if calendar else t
        if fill is None:
            break
        books.append(
            (
                fill,
                dict.fromkeys(sample[:book_size], 1.0 / book_size),
                dict.fromkeys(sample[book_size:], 1.0 / book_size),
            )
        )
        prev_names = sample
    total = 1.0
    drifted_long: dict[str, float] = {}
    drifted_short: dict[str, float] = {}
    for (start, target_long, target_short), (end, _, _) in itertools.pairwise(books):
        cost = _cost(_turnover(target_long, target_short, drifted_long, drifted_short))
        period_ret = _leg_period_return(target_long, closes, start, end) - _leg_period_return(
            target_short, closes, start, end
        )
        total *= 1.0 + period_ret - cost
        drifted_long = _drift_to_end(target_long, closes, start, end)
        drifted_short = _drift_to_end(target_short, closes, start, end)
    years = (books[-1][0] - books[0][0]).days / 365.25 if len(books) > 1 else 0.0
    if years <= 0:
        return None
    return total ** (1.0 / years) - 1.0


def null_percentile(
    strategy_net_ann: float,
    rebal_dates: list[date],
    eligible_by_date: dict[date, list[str]],
    closes: dict[str, pd.Series],
    *,
    n: int = _NULL_DRAWS,
    seed: int = _NULL_SEED,
    cost_bps: float = _COST_BPS,
    book_size: int = _BOOK_SIZE,
    calendar: list[date] | None = None,
    own_dates: dict[str, list[date]] | None = None,
) -> tuple[float, float]:
    """D10: `n` seeded random 25/25 books on the primary cadence's rank dates.

    Returns `(percentile, median_net_ann)` — `percentile` is the share (out
    of 100) of the `n` draws at or below `strategy_net_ann`. Deterministic
    for a fixed `seed`.
    """
    rng = random.Random(seed)  # noqa: S311 -- deterministic benchmark draw, not security-sensitive
    draws = [
        d
        for d in (
            _random_book_net_ann(
                rng,
                rebal_dates,
                eligible_by_date,
                closes,
                cost_bps,
                book_size,
                calendar=calendar,
                own_dates=own_dates,
            )
            for _ in range(n)
        )
        if d is not None
    ]
    if not draws:
        return 0.0, 0.0
    percentile = sum(1 for d in draws if d <= strategy_net_ann) / len(draws) * 100
    return percentile, float(statistics.median(draws))


# ----- D11: fidelity -----


def _spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rho, with a scipy-free rank+Pearson fallback (D11)."""
    if len(a) < 2:
        return None
    s1, s2 = pd.Series(a), pd.Series(b)
    try:
        rho = s1.corr(s2, method="spearman")
    except ImportError:
        rho = s1.rank().corr(s2.rank(), method="pearson")
    return None if rho is None or rho != rho else float(rho)


def fidelity(
    score_bt_by_date: dict[date, dict[str, float]],
    live_score_by_date: dict[date, dict[str, float]],
) -> Fidelity:
    """D11: per-date fidelity check + its median.

    Spearman rho between `score_bt` and the live `screener_score`, per
    genuine data-branch snapshot date.
    """
    per_date: list[FidelityDate] = []
    rhos: list[float] = []
    for d in sorted(set(score_bt_by_date) & set(live_score_by_date)):
        bt, live = score_bt_by_date[d], live_score_by_date[d]
        common = sorted(set(bt) & set(live))
        rho = _spearman([bt[t] for t in common], [live[t] for t in common])
        per_date.append(FidelityDate(date=d, rho=rho, n=len(common)))
        if rho is not None:
            rhos.append(rho)
    median_rho = float(statistics.median(rhos)) if rhos else None
    return Fidelity(per_date=per_date, median_rho=median_rho)


# ----- I/O layer -----


def _base_universe_ids() -> list[str]:
    """D1 scope: every bundled preset except the derived aggregated/screener/crypto ones."""
    return sorted(
        p.stem
        for p in PRESET_DIR.glob("*.txt")
        if not p.stem.startswith(_DERIVED_UNIVERSE_PREFIXES)
    )


def _universe_tickers() -> list[str]:
    """The union of every D1 base-universe ticker (~320)."""
    tickers: set[str] = set()
    for universe_id in _base_universe_ids():
        tickers.update(_read_symbol_file(PRESET_DIR / f"{universe_id}.txt"))
    return sorted(tickers)


def _statement_fetch_dir(ticker: str) -> Path:
    return settings.backtest_prices_cache_dir / "statements" / ticker


def _statement_fetch_path(ticker: str, fetch_date: date) -> Path:
    return _statement_fetch_dir(ticker) / f"{fetch_date.isoformat()}.json"


def _closes_cache_path(ticker: str) -> Path:
    return settings.backtest_prices_cache_dir / "closes" / f"{ticker}.csv"


def _frame_to_cache(frame: pd.DataFrame | None) -> dict | None:
    if frame is None or frame.empty:
        return None
    out: dict[str, dict[str, float | None]] = {}
    for col in frame.columns:
        column = cast("pd.Series", frame[col])
        out[col.isoformat()] = {
            str(idx): (None if v != v else float(v)) for idx, v in column.items()
        }
    return out


def _cache_to_frame(data: dict | None) -> pd.DataFrame | None:
    if not data:
        return None
    return pd.DataFrame({pd.Timestamp(col): pd.Series(rows) for col, rows in data.items()})


def _merge_first_seen(frames: list[pd.DataFrame]) -> pd.DataFrame | None:
    """Union of `frames`' period-end columns, EARLIEST frame's value wins per period.

    `frames` must already be ordered earliest-fetch-first. Reduces
    restatement bias (D3 caveat): a later fetch can only ADD periods this
    ticker didn't have before, never overwrite an already-cached one.
    """
    if not frames:
        return None
    merged = frames[0]
    for frame in frames[1:]:
        new_cols = [c for c in frame.columns if c not in merged.columns]
        if new_cols:
            merged = pd.concat([merged, frame[new_cols]], axis=1)
    return merged.reindex(sorted(merged.columns), axis=1)


def _merged_cached_frames(ticker: str) -> Frames:
    """Every cached fetch for `ticker`, merged first-seen-wins per period (D3)."""
    fetch_dir = _statement_fetch_dir(ticker)
    if not fetch_dir.is_dir():
        return None, None
    income_frames: list[pd.DataFrame] = []
    balance_frames: list[pd.DataFrame] = []
    for path in sorted(fetch_dir.glob("*.json")):  # filename = fetch date -> earliest first
        raw = json.loads(path.read_text())
        income = _cache_to_frame(raw.get("income_stmt"))
        balance = _cache_to_frame(raw.get("balance_sheet"))
        if income is not None:
            income_frames.append(income)
        if balance is not None:
            balance_frames.append(balance)
    return _merge_first_seen(income_frames), _merge_first_seen(balance_frames)


def fetch_frames(ticker: str, *, today: date | None = None) -> Frames:
    """Fetch + cache one ticker's annual `income_stmt` + `balance_sheet` (D3).

    Caches ONE IMMUTABLE file per ticker per fetch date under
    `results/prices/statements/<ticker>/<fetch-date>.json` (gitignored,
    never committed, never sent to `data`) — a sync-friendly layout so a
    future PR can mirror this directory to a private repo and statements
    accumulate beyond yfinance's ~4-5 FY window. A same-day re-run reuses
    today's file rather than re-fetching (idempotent). The columns
    returned are the union of every cached fetch, earliest-fetch-wins per
    period end (`_merge_first_seen`) — wrap-degrades to `(None, None)`
    when nothing has ever been cached and today's yfinance call fails.
    """
    today = today or date.today()
    fetch_path = _statement_fetch_path(ticker, today)
    if not fetch_path.exists():
        try:
            yf_ticker = yf.Ticker(ticker)
            income_stmt = yf_ticker.income_stmt
            balance_sheet = yf_ticker.balance_sheet
        except Exception as exc:
            logger.warning("fetch_frames(%s) failed: %s", ticker, exc)
            income_stmt, balance_sheet = None, None
        fetch_path.parent.mkdir(parents=True, exist_ok=True)
        fetch_path.write_text(
            json.dumps(
                {
                    "income_stmt": _frame_to_cache(income_stmt),
                    "balance_sheet": _frame_to_cache(balance_sheet),
                }
            )
        )
    return _merged_cached_frames(ticker)


def write_closes_cache(closes: dict[str, pd.Series]) -> None:
    """Write each ticker's raw daily closes to a sync-friendly per-ticker CSV.

    `results/prices/closes/<ticker>.csv` (gitignored, never committed,
    never sent to `data`) — same sync-target posture as the statement
    fetch files above.
    """
    root = settings.backtest_prices_cache_dir / "closes"
    root.mkdir(parents=True, exist_ok=True)
    for ticker, series in closes.items():
        series.to_csv(_closes_cache_path(ticker))


def _drop_bad_tickers(closes: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Exclude any ticker whose close series ever reports a non-positive value.

    Found 2026-09-24, `ICTEF`: its yfinance auto-adjusted closes are
    negative across roughly half of its post-2023 history, not a single
    isolated bad tick — patching just the negative points still leaves
    large `ffill` gaps that manufacture their own multi-hundred-percent
    "return" spikes once a positive price reappears (the 2026-09-24 bug:
    the short basket showed a one-day -13.3% move driven almost entirely
    by this one name reconnecting from a ~9-year negative run). A stock
    price can never be <= 0, and this magnitude/duration rules out a
    one-off split artefact (a split can never produce a negative price
    either) — the whole series is untrustworthy, so the ticker is dropped
    entirely (it simply won't be eligible for ranking, same as any other
    ticker `closes` doesn't cover) rather than patched point-by-point.
    """
    return {ticker: series for ticker, series in closes.items() if (series.dropna() > 0).all()}


def _union_calendar(closes: dict[str, pd.Series]) -> list[date]:
    """Sorted union of every ticker's close-history trading dates (D5)."""
    all_dates: set[date] = set()
    for series in closes.values():
        all_dates.update(ts.date() for ts in series.dropna().index if isinstance(ts, pd.Timestamp))
    return sorted(all_dates)


def _reindex_returns(
    closes: dict[str, pd.Series], calendar: list[date]
) -> dict[str, dict[date, float]]:
    """Per-ticker daily simple returns on the union `calendar`.

    Forward-fills each ticker onto `calendar` first, so a non-trading day
    (or a delisted-name gap) contributes a 0% return (D5) via the
    unmoved forward-filled price, rather than a missing observation.
    """
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in calendar])
    out: dict[str, dict[date, float]] = {}
    for ticker, series in closes.items():
        reindexed = series.reindex(index).ffill()
        pct = reindexed.pct_change().fillna(0.0)
        out[ticker] = dict(zip(calendar, (float(v) for v in pct.to_numpy()), strict=True))
    return out


_BAD_TICK_RETURN_THRESHOLD = 0.5
"""Foresight-audit finding #3 (2026-09-24): a single-day |return| this large is a data
glitch, not a real move — `_drop_bad_tickers` already excludes a ticker with any
non-positive close (e.g. `ICTEF`), but a still-positive bad print elsewhere would slip
through that check alone."""


def _filter_bad_ticks(
    returns_by_ticker: dict[str, dict[date, float]],
) -> dict[str, dict[date, float]]:
    """Zero out any single-day |return| over `_BAD_TICK_RETURN_THRESHOLD` (a glitch).

    Same "flat 0%" semantics D5 already uses for a missing price. Logs each
    filtered `(ticker, date, return)` for visibility.
    """
    out: dict[str, dict[date, float]] = {}
    for ticker, series in returns_by_ticker.items():
        cleaned = dict(series)
        for d, r in series.items():
            if abs(r) > _BAD_TICK_RETURN_THRESHOLD:
                logger.warning("bad tick filtered: %s %s %.1f%%", ticker, d, r * 100)
                cleaned[d] = 0.0
        out[ticker] = cleaned
    return out


def _next_trading_day(calendar: list[date], t: date) -> date | None:
    """First calendar date strictly after `t` (the D5 trade-at-t+1 rule)."""
    idx = bisect.bisect_right(calendar, t)
    return calendar[idx] if idx < len(calendar) else None


def _own_dates(closes: dict[str, pd.Series]) -> dict[str, list[date]]:
    """Each ticker's own sorted trading dates (the days it has a real close)."""
    return {
        ticker: sorted(ts.date() for ts in series.dropna().index if isinstance(ts, pd.Timestamp))
        for ticker, series in closes.items()
    }


def _has_close(dates: list[date], d: date) -> bool:
    i = bisect.bisect_left(dates, d)
    return i < len(dates) and dates[i] == d


def _trade_date(
    calendar: list[date],
    t: date,
    tickers: list[str],
    own_dates: dict[str, list[date]] | None,
) -> date | None:
    """First calendar date after `t` on which every still-trading name in `tickers` has a close.

    Foresight-audit #4: on a union-calendar day a name's own exchange was shut,
    its forward-filled price would fill it at the rank-date close it was picked
    on. A name with no close after `t` (delisted) is held at its last close and
    doesn't block. Without `own_dates` this is plain `_next_trading_day`.
    """
    if own_dates is None:
        return _next_trading_day(calendar, t)
    live = [own_dates[x] for x in tickers if own_dates.get(x) and own_dates[x][-1] > t]
    for d in calendar[bisect.bisect_right(calendar, t) :]:
        if all(_has_close(dates, d) for dates in live):
            return d
    return None


_ONE_YEAR_COVERAGE_GRACE_DAYS = 30
"""Mirrors `fundamentals._SORTINO_COVERAGE_GRACE_DAYS` — D6/finding-#7 (2026-09-24)."""


def _has_one_year_of_closes(closes: pd.Series, as_of: date) -> bool:
    """D6's documented `>= 1y of closes` eligibility gate, enforced explicitly.

    `score_at`'s own `_compute_sortino` call only requires
    `fundamentals._MIN_SORTINO_DATAPOINTS` (30) observations, which a
    ticker with a few months of trading history already satisfies —
    silently admitting it to the ranked pool despite D6's documented
    `>= 1y of closes` threshold (found 2026-09-24: e.g. `SEZL` was
    ranked/shorted with only ~4 months of price history).
    """
    guarded = _closes_as_of(closes, as_of)
    if guarded.empty:
        return False
    as_of_ts = cast("pd.Timestamp", pd.Timestamp(as_of))
    cutoff = as_of_ts - pd.DateOffset(years=1) + pd.Timedelta(days=_ONE_YEAR_COVERAGE_GRACE_DAYS)
    first_valid = cast("pd.Timestamp", guarded.index[0])
    return bool(first_valid <= cutoff)


def _eligible_count(
    d: date,
    frames_by_ticker: dict[str, Frames],
    closes: dict[str, pd.Series],
    threshold: int,
) -> int:
    """Count of D1 tickers eligible (`>= 1y closes` + `score_at` not `None`) at `d`."""
    count = 0
    for ticker, frames in frames_by_ticker.items():
        close = closes.get(ticker)
        if close is None or not _has_one_year_of_closes(close, d):
            continue
        if score_at(pit_fundamentals(frames, d, ticker), close, d) is None:
            continue
        count += 1
        if count >= threshold:
            break
    return count


def _find_start_date(
    grid: list[date],
    frames_by_ticker: dict[str, Frames],
    closes: dict[str, pd.Series],
    *,
    threshold: int = _MIN_ELIGIBLE_START,
) -> date | None:
    """D6: the first `grid` date with `>= threshold` eligible tickers."""
    for d in grid:
        if _eligible_count(d, frames_by_ticker, closes, threshold) >= threshold:
            return d
    return None


def _score_all_tickers(
    d: date, frames_by_ticker: dict[str, Frames], closes: dict[str, pd.Series]
) -> list[tuple[str, float]]:
    """Every ticker's `score_at` at `d`, sorted best-to-worst (D6: needs `>= 1y closes`)."""
    scored: list[tuple[str, float]] = []
    for ticker, frames in frames_by_ticker.items():
        close = closes.get(ticker)
        if close is None or not _has_one_year_of_closes(close, d):
            continue
        score = score_at(pit_fundamentals(frames, d, ticker), close, d)
        if score is not None:
            scored.append((ticker, score))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def _list_entry(d: date, scored: list[tuple[str, float]]) -> BacktestListEntry:
    """One rank date's `BacktestListEntry` — disjoint top/bottom `_BOOK_SIZE`."""
    n = len(scored)
    top_count = min(_BOOK_SIZE, n)
    bottom_count = min(_BOOK_SIZE, n - top_count)
    best = scored[:top_count]
    worst = list(reversed(scored[n - bottom_count :])) if bottom_count else []
    return BacktestListEntry(
        date=d,
        eligible=n,
        best=[RankEntry(ticker=t, score=round(s, 1)) for t, s in best],
        worst=[RankEntry(ticker=t, score=round(s, 1)) for t, s in worst],
    )


def _rank_all_dates(
    grid: list[date],
    frames_by_ticker: dict[str, Frames],
    closes: dict[str, pd.Series],
) -> tuple[dict[date, list[tuple[str, float]]], list[BacktestListEntry]]:
    """Every grid date's full ranked-eligible list + its best/worst-25 entry."""
    ranked_by_date: dict[date, list[tuple[str, float]]] = {}
    entries: list[BacktestListEntry] = []
    for d in grid:
        scored = _score_all_tickers(d, frames_by_ticker, closes)
        ranked_by_date[d] = scored
        entries.append(_list_entry(d, scored))
    return ranked_by_date, entries


def _weights_for_cadence(
    cadence: str,
    rebal_dates: list[date],
    ranked_by_date: dict[date, list[tuple[str, float]]],
    calendar: list[date],
    *,
    own_dates: dict[str, list[date]] | None = None,
) -> dict[date, tuple[dict[str, float], dict[str, float]]]:
    """Every cadence rebalance date's target weights, keyed by TRADE date."""
    out: dict[date, tuple[dict[str, float], dict[str, float]]] = {}
    prev_holdings: tuple[list[str], list[str]] | None = None
    for t in rebal_dates:
        ranks = [ticker for ticker, _ in ranked_by_date.get(t, [])]
        if len(ranks) < 2 * _BOOK_SIZE:
            continue
        long_names, short_names = select(ranks, cadence, prev_holdings)
        prev_long, prev_short = prev_holdings if prev_holdings is not None else ([], [])
        trade_date = _trade_date(
            calendar, t, long_names + short_names + prev_long + prev_short, own_dates
        )
        if trade_date is None:
            continue
        out[trade_date] = (
            dict.fromkeys(long_names, 1.0 / len(long_names)),
            dict.fromkeys(short_names, 1.0 / len(short_names)),
        )
        prev_holdings = (long_names, short_names)
    return out


def _ranked_ticker(
    pos: dict[str, int], scores: dict[str, float], ticker: str, *, short: bool, n: int
) -> RankedTicker:
    """D21: one ticker's `RankedTicker`, from its position in the full ranked pool.

    `pos` maps ticker -> its 0-based best-to-worst index. `short=True` uses
    the worst-relative signed rank (`-1` = the single worst); otherwise the
    best-relative rank (`+1` = the single best) — `aggregated_scores_best_
    and_worst.AuditRow`'s convention. `None`/`None` when `ticker` isn't in
    `pos` at all (fell out of the ranked/eligible pool entirely).
    """
    idx = pos.get(ticker)
    if idx is None:
        return RankedTicker(ticker=ticker, rank=None, score=None)
    rank = -(n - idx) if short else idx + 1
    return RankedTicker(ticker=ticker, rank=rank, score=scores.get(ticker))


def _trade_log_for_cadence(
    cadence: str,
    rebal_dates: list[date],
    ranked_by_date: dict[date, list[tuple[str, float]]],
    calendar: list[date],
    *,
    book_size: int = _BOOK_SIZE,
    buffer: int = _BUFFER_RANK,
    own_dates: dict[str, list[date]] | None = None,
) -> list[TradeLogEntry]:
    """D21: series B's WHEN/WHY/WHAT rebalance log for one cadence.

    Mirrors `_weights_for_cadence`'s selection loop (same `select()` calls,
    same `prev_holdings` tracking) so the log always agrees with the actual
    simulated weights; kept as its own pass rather than folded into
    `_weights_for_cadence` to keep that function's return shape untouched.
    """
    entries: list[TradeLogEntry] = []
    prev_holdings: tuple[list[str], list[str]] | None = None
    for t in rebal_dates:
        scored = ranked_by_date.get(t, [])
        ranks = [ticker for ticker, _ in scored]
        if len(ranks) < 2 * book_size:
            continue
        long_names, short_names = select(
            ranks, cadence, prev_holdings, book_size=book_size, buffer=buffer
        )
        prev_long, prev_short = prev_holdings if prev_holdings is not None else ([], [])
        trade_date = _trade_date(
            calendar, t, long_names + short_names + prev_long + prev_short, own_dates
        )
        if trade_date is None:
            continue
        long_entered, long_exited = _leg_diff(prev_long, long_names)
        short_entered, short_exited = _leg_diff(prev_short, short_names)
        pos = {ticker: i for i, ticker in enumerate(ranks)}
        scores = dict(scored)
        n = len(ranks)
        had_buffer_exit = prev_holdings is not None and any(
            pos.get(ticker, n) >= buffer for ticker in long_exited + short_exited
        )
        entries.append(
            TradeLogEntry(
                rank_date=t,
                trade_date=trade_date,
                reason=_rebalance_reason(
                    cadence, is_first=prev_holdings is None, had_buffer_exit=had_buffer_exit
                ),
                long=LegChange(
                    entered=[
                        _ranked_ticker(pos, scores, tk, short=False, n=n) for tk in long_entered
                    ],
                    exited=[
                        _ranked_ticker(pos, scores, tk, short=False, n=n) for tk in long_exited
                    ],
                ),
                short=LegChange(
                    entered=[
                        _ranked_ticker(pos, scores, tk, short=True, n=n) for tk in short_entered
                    ],
                    exited=[
                        _ranked_ticker(pos, scores, tk, short=True, n=n) for tk in short_exited
                    ],
                ),
                turnover=_turnover(
                    dict.fromkeys(long_names, 1.0 / len(long_names)),
                    dict.fromkeys(short_names, 1.0 / len(short_names)),
                    dict.fromkeys(prev_long, 1.0 / len(prev_long)) if prev_long else {},
                    dict.fromkeys(prev_short, 1.0 / len(prev_short)) if prev_short else {},
                ),
            )
        )
        prev_holdings = (long_names, short_names)
    return entries


def _trim_to_first_trade(
    rows: list[BacktestDailyRow],
    weights_by_trade_date: dict[date, tuple[dict[str, float], dict[str, float]]],
    *,
    run_date: date | None = None,
) -> list[BacktestDailyRow]:
    """The start-trim fix (found 2026-09-24): drop pre-first-trade zero-return days.

    With `run_date`, also drops rows dated on or after it: that day's close may
    still be an intraday mark, and the append-only freeze (D17) would lock it in.

    `simulate` marks every day in the full price-history union calendar, which
    can start decades before this cadence's book had any holding — before its
    first trade date, `ret_long`/`ret_short` are always 0 (`current_long`/
    `current_short` start empty). Persisted rows and `metrics` should only
    ever cover the window the book actually existed, or every metric is
    diluted by the padding (the 2026-09-24 bug: 4.96% published ann. vol vs.
    ~21.2% over the real window). Empty `weights_by_trade_date` (the book
    never actually traded) yields no rows at all.
    """
    if not weights_by_trade_date:
        return []
    first_trade = min(weights_by_trade_date)
    return [r for r in rows if r.date >= first_trade and (run_date is None or r.date < run_date)]


def _pct_change_map(closes: dict[date, float]) -> dict[date, float]:
    """Day-over-day simple returns from a sorted `date -> close` map."""
    dates = sorted(closes)
    out: dict[date, float] = {}
    for prev_d, cur_d in itertools.pairwise(dates):
        prev_p = closes[prev_d]
        if prev_p:
            out[cur_d] = closes[cur_d] / prev_p - 1.0
    return out


_DATE_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def _load_snapshot_list(path: Path) -> list[FundamentalsSnapshot]:
    """One dated demo-snapshot file's full `FundamentalsSnapshot` list."""
    raw = json.loads(path.read_text())
    return [FundamentalsSnapshot.model_validate(item) for item in raw]


def _scores_from_snapshot_file(path: Path) -> dict[str, float]:
    """One dated demo-snapshot file's `ticker -> live screener_score` map."""
    scores: dict[str, float] = {}
    for snap in _load_snapshot_list(path):
        cs = snap.composite_scores
        if cs is not None and cs.screener_score is not None:
            scores[snap.symbol] = cs.screener_score
    return scores


def _load_demo_snapshot_scores(universe_id: str) -> dict[date, dict[str, float]]:
    """Every dated demo snapshot's `ticker -> live screener_score`, by date.

    Reads whatever `results/demo/<universe_id>/*.json` is present locally
    (the cron checks these out from `data` before running `main`; a local
    run without that checkout simply yields nothing here — D11 is a
    best-effort default, not a hard requirement).
    """
    base = settings.demo_dir / universe_id
    if not base.is_dir():
        return {}
    out: dict[date, dict[str, float]] = {}
    for path in base.glob("*.json"):
        if not _DATE_FILE_RE.match(path.name):
            continue
        scores = _scores_from_snapshot_file(path)
        if scores:
            out[date.fromisoformat(path.stem)] = scores
    return out


def _live_scores_by_date() -> dict[date, dict[str, float]]:
    """Every D1 base universe's genuine live `screener_score`, merged by date."""
    live_by_date: dict[date, dict[str, float]] = {}
    for universe_id in _base_universe_ids():
        for d, scores in _load_demo_snapshot_scores(universe_id).items():
            live_by_date.setdefault(d, {}).update(scores)
    return live_by_date


def _score_bt_for_tickers(
    d: date,
    tickers: Iterable[str],
    frames_by_ticker: dict[str, Frames],
    closes: dict[str, pd.Series],
) -> dict[str, float]:
    """`score_at` at `d` for exactly the given `tickers`."""
    out: dict[str, float] = {}
    for ticker in tickers:
        frames = frames_by_ticker.get(ticker)
        close = closes.get(ticker)
        if frames is None or close is None:
            continue
        score = score_at(pit_fundamentals(frames, d, ticker), close, d)
        if score is not None:
            out[ticker] = score
    return out


def _compute_fidelity(
    frames_by_ticker: dict[str, Frames], closes: dict[str, pd.Series]
) -> Fidelity:
    """D11 fidelity, sourced from whatever genuine snapshots are checked out locally."""
    live_by_date = _live_scores_by_date()
    bt_by_date = {
        d: _score_bt_for_tickers(d, live_scores, frames_by_ticker, closes)
        for d, live_scores in live_by_date.items()
    }
    return fidelity(bt_by_date, live_by_date)


# ----- D16: series A (genuine decisions) -----


def _rank_genuine(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    d: date,
    *,
    top_n: int = _BOOK_SIZE,
) -> BacktestListEntry:
    """D16: one genuine rank date's already-selected best/worst `top_n` via `build_universe`.

    Reuses `aggregated_scores_best_and_worst.build_universe` UNCHANGED (DRY) —
    the same dedup + 14-day staleness gate the live aggregated lists use.
    Pure: takes the per-universe snapshots directly, no file I/O.
    """
    best, worst, audit_rows = build_universe(
        snapshots_by_universe, snapshot_dates_by_universe, top_n=top_n, as_of=d
    )
    score_by_ticker = {
        row.ticker: row.screener_score for row in audit_rows if row.screener_score is not None
    }
    eligible = sum(1 for row in audit_rows if row.eligible)
    return BacktestListEntry(
        date=d,
        eligible=eligible,
        best=[RankEntry(ticker=t, score=round(score_by_ticker[t], 1)) for t in best],
        worst=[RankEntry(ticker=t, score=round(score_by_ticker[t], 1)) for t in worst],
    )


def _genuine_rank_dates() -> list[date]:
    """D16: dates every D1 base universe has a genuine `data`-branch demo snapshot.

    Intersection (not union) of `results/demo/<universe>/*.json` dates across
    every base universe, from `_GENUINE_START` — matches the dates the real
    live aggregator actually ran (verified: this set equals the committed
    `results/demo/aggregated-scores-best/*.json` date list). An empty/missing
    universe directory yields no genuine dates at all (best-effort: the cron
    checks `results/demo/` out from `data` before running `main`).
    """
    universe_ids = _base_universe_ids()
    date_sets: list[set[date]] = []
    for universe_id in universe_ids:
        base = settings.demo_dir / universe_id
        if not base.is_dir():
            return []
        date_sets.append(
            {date.fromisoformat(p.stem) for p in base.glob("*.json") if _DATE_FILE_RE.match(p.name)}
        )
    if not date_sets:
        return []
    common = set.intersection(*date_sets)
    return sorted(d for d in common if d >= _GENUINE_START)


def _genuine_snapshots_at(
    d: date,
) -> tuple[dict[str, list[FundamentalsSnapshot]], dict[str, str]]:
    """D16: every base universe's exact `<d>.json` demo snapshot, for one genuine rank date."""
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]] = {}
    snapshot_dates_by_universe: dict[str, str] = {}
    for universe_id in _base_universe_ids():
        path = settings.demo_dir / universe_id / f"{d.isoformat()}.json"
        if not path.exists():
            continue
        snapshots_by_universe[universe_id] = _load_snapshot_list(path)
        snapshot_dates_by_universe[universe_id] = d.isoformat()
    return snapshots_by_universe, snapshot_dates_by_universe


def _genuine_rank_all_dates(
    grid: list[date],
) -> tuple[dict[date, tuple[list[str], list[str]]], list[BacktestListEntry]]:
    """D16: every genuine grid date's `(long_tickers, short_tickers)` + its list entry."""
    ranked_by_date: dict[date, tuple[list[str], list[str]]] = {}
    entries: list[BacktestListEntry] = []
    for d in grid:
        snapshots_by_universe, snapshot_dates_by_universe = _genuine_snapshots_at(d)
        entry = _rank_genuine(snapshots_by_universe, snapshot_dates_by_universe, d)
        ranked_by_date[d] = ([r.ticker for r in entry.best], [r.ticker for r in entry.worst])
        entries.append(entry)
    return ranked_by_date, entries


def _genuine_weights_for_cadence(
    cadence: str,
    rebal_dates: list[date],
    ranked_by_date: dict[date, tuple[list[str], list[str]]],
    calendar: list[date],
    *,
    book_size: int = _BOOK_SIZE,
    own_dates: dict[str, list[date]] | None = None,
) -> dict[date, tuple[dict[str, float], dict[str, float]]]:
    """D16: every series-A cadence rebalance date's target weights, keyed by TRADE date.

    Unlike series B's `_weights_for_cadence`, there is no buffer retention:
    `build_universe` already returns only the top/bottom `book_size` (the
    genuine decisions), so every rebalance — including `monthly_buffer` — is
    a fresh selection identical to `monthly`'s holdings (disclosed in
    `_CAVEATS_GENUINE`). Trade date is the first trading day strictly after
    the rank date (`_next_trading_day`, D5/D16) — no same-close look-ahead.
    """
    out: dict[date, tuple[dict[str, float], dict[str, float]]] = {}
    prev: list[str] = []
    for t in rebal_dates:
        long_names, short_names = ranked_by_date.get(t, ([], []))
        if len(long_names) < book_size or len(short_names) < book_size:
            continue
        trade_date = _trade_date(calendar, t, long_names + short_names + prev, own_dates)
        if trade_date is None:
            continue
        out[trade_date] = (
            dict.fromkeys(long_names, 1.0 / len(long_names)),
            dict.fromkeys(short_names, 1.0 / len(short_names)),
        )
        prev = long_names + short_names
    return out


def _genuine_ranked_ticker(scores: dict[str, float], rank: int, ticker: str) -> RankedTicker:
    """D21: an ENTERED series-A ticker's `RankedTicker` (rank + score at the rank date).

    `rank` is already signed the same way as `_ranked_ticker` (best-relative
    `+1..` or worst-relative `..-1`, computed by the caller); `score` comes
    from this rank date's own `BacktestListEntry`.
    """
    return RankedTicker(ticker=ticker, rank=rank, score=scores.get(ticker))


_EXITED_UNKNOWN = RankedTicker(ticker="", rank=None, score=None)
"""Placeholder shape for a series-A EXITED ticker (D21) — `build_universe` exposes
no full ranked pool to look an exited name's current rank/score up in, so this is
copied with the real ticker symbol rather than reused directly."""


def _genuine_trade_log_for_cadence(
    cadence: str,
    rebal_dates: list[date],
    ranked_by_date: dict[date, tuple[list[str], list[str]]],
    entries_by_date: dict[date, BacktestListEntry],
    calendar: list[date],
    *,
    book_size: int = _BOOK_SIZE,
    own_dates: dict[str, list[date]] | None = None,
) -> list[TradeLogEntry]:
    """D21: series A's WHEN/WHY/WHAT rebalance log for one cadence.

    Mirrors `_genuine_weights_for_cadence`'s loop. An exited ticker's rank/
    score are always `None` (D16: no full ranked pool to look them up in);
    an entered ticker's are looked up from `entries_by_date[t]`, the same
    `BacktestListEntry` `_genuine_rank_all_dates` already computed for `t`.
    """
    entries: list[TradeLogEntry] = []
    prev_long: list[str] = []
    prev_short: list[str] = []
    is_first = True
    for t in rebal_dates:
        long_names, short_names = ranked_by_date.get(t, ([], []))
        if len(long_names) < book_size or len(short_names) < book_size:
            continue
        trade_date = _trade_date(
            calendar, t, long_names + short_names + prev_long + prev_short, own_dates
        )
        if trade_date is None:
            continue
        entry = entries_by_date.get(t)
        scores = (
            {r.ticker: r.score for r in (entry.best + entry.worst)} if entry is not None else {}
        )
        long_rank = {ticker: i + 1 for i, ticker in enumerate(long_names)}
        short_rank = {ticker: -(i + 1) for i, ticker in enumerate(short_names)}
        long_entered, long_exited = _leg_diff(prev_long, long_names)
        short_entered, short_exited = _leg_diff(prev_short, short_names)
        entries.append(
            TradeLogEntry(
                rank_date=t,
                trade_date=trade_date,
                reason=_rebalance_reason(cadence, is_first=is_first, had_buffer_exit=False),
                long=LegChange(
                    entered=[
                        _genuine_ranked_ticker(scores, long_rank[tk], tk) for tk in long_entered
                    ],
                    exited=[
                        _EXITED_UNKNOWN.model_copy(update={"ticker": tk}) for tk in long_exited
                    ],
                ),
                short=LegChange(
                    entered=[
                        _genuine_ranked_ticker(scores, short_rank[tk], tk) for tk in short_entered
                    ],
                    exited=[
                        _EXITED_UNKNOWN.model_copy(update={"ticker": tk}) for tk in short_exited
                    ],
                ),
                turnover=_turnover(
                    dict.fromkeys(long_names, 1.0 / len(long_names)),
                    dict.fromkeys(short_names, 1.0 / len(short_names)),
                    dict.fromkeys(prev_long, 1.0 / len(prev_long)) if prev_long else {},
                    dict.fromkeys(prev_short, 1.0 / len(prev_short)) if prev_short else {},
                ),
            )
        )
        prev_long, prev_short = long_names, short_names
        is_first = False
    return entries


# ----- Persistence (per-year files, mirrors `equity_spy.py`) -----


def _year_path(root: Path, year: int) -> Path:
    return root / f"{year}.json"


def _existing_years(root: Path) -> list[int]:
    """Sorted year numbers already persisted under `root` (a cadence or lists dir)."""
    if not root.is_dir():
        return []
    return sorted(int(p.stem) for p in root.glob("*.json") if p.stem.isdigit())


def _reset_year_files(root: Path) -> list[Path]:
    """D17/D18: delete every existing `YYYY.json` year file under `root`.

    The one explicit full-rebuild mechanism D17 allows, triggered exactly
    once by a `method_version` bump — normal runs never call this; they only
    append. Returns the deleted paths (the workflow reports them as `data`-
    branch deletions via `scripts/data-branch-commit.cjs`'s `sha: null`
    tree-entry support).
    """
    if not root.is_dir():
        return []
    removed = []
    for path in sorted(root.glob("*.json")):
        if path.stem.isdigit():
            path.unlink()
            removed.append(path)
    return removed


def write_series_years(
    cadence: str, rows: list[BacktestDailyRow], *, root: Path | None = None
) -> list[Path]:
    """D17: append-only write of one cadence's daily rows as per-year files.

    Loads each affected year's ALREADY-STORED rows from disk and keeps them
    verbatim; only rows with a date after the last stored date are appended
    on top. A re-run with no new dates touches nothing (byte-identical); a
    stale/differently-recomputed value for an already-frozen date is always
    discarded in favour of what's on disk. `rows` is the full freshly-
    simulated series — the freeze happens here, at write time, not at
    compute time (D13's full recompute stays the compute strategy).
    """
    base = root if root is not None else settings.backtest_series_dir / cadence
    last_stored: date | None = None
    for year in reversed(_existing_years(base)):
        year_rows = read_series_year(cadence, year, root=base)
        if year_rows:
            last_stored = year_rows[-1].date
            break
    new_rows = rows if last_stored is None else [r for r in rows if r.date > last_stored]
    if not new_rows:
        return []
    by_year: dict[int, list[BacktestDailyRow]] = {}
    for r in new_rows:
        by_year.setdefault(r.date.year, []).append(r)
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    for year, yrows in sorted(by_year.items()):
        existing = read_series_year(cadence, year, root=base)
        merged = sorted([*existing, *yrows], key=lambda r: r.date)
        path = _year_path(base, year)
        payload = [r.model_dump(mode="json") for r in merged]
        path.write_text(json.dumps(payload, indent=2) + "\n")
        logger.info("wrote %s (%d new rows, %d total)", path, len(yrows), len(merged))
        paths.append(path)
    return paths


def read_series_year(
    cadence: str, year: int, *, root: Path | None = None
) -> list[BacktestDailyRow]:
    """Load one cadence's per-year daily-row file, empty when missing."""
    base = root if root is not None else settings.backtest_series_dir / cadence
    path = _year_path(base, year)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [BacktestDailyRow.model_validate(item) for item in raw]


def _read_all_series_years(cadence: str, *, root: Path | None = None) -> list[BacktestDailyRow]:
    """D17: every year's FROZEN (on-disk) rows for `cadence`, concatenated in date order.

    `metrics` must be computed from what's actually persisted, not from the
    ephemeral in-memory recompute — statement restatement drift means an old
    date's freshly-recomputed value can differ from its frozen one.
    """
    base = root if root is not None else settings.backtest_series_dir / cadence
    rows: list[BacktestDailyRow] = []
    for year in _existing_years(base):
        rows.extend(read_series_year(cadence, year, root=base))
    return rows


def write_lists_years(entries: list[BacktestListEntry], *, root: Path | None = None) -> list[Path]:
    """D17: append-only write of the backfilled best/worst-25 entries as per-year files.

    Same freeze guarantee as `write_series_years`: an already-stored rank
    date's entry is never rewritten, even if this run recomputes it
    differently.
    """
    base = root if root is not None else settings.backtest_dir / "lists"
    last_stored: date | None = None
    for year in reversed(_existing_years(base)):
        year_entries = read_lists_year(year, root=base)
        if year_entries:
            last_stored = year_entries[-1].date
            break
    new_entries = entries if last_stored is None else [e for e in entries if e.date > last_stored]
    if not new_entries:
        return []
    by_year: dict[int, list[BacktestListEntry]] = {}
    for e in new_entries:
        by_year.setdefault(e.date.year, []).append(e)
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    for year, yentries in sorted(by_year.items()):
        existing = read_lists_year(year, root=base)
        merged = sorted([*existing, *yentries], key=lambda e: e.date)
        path = _year_path(base, year)
        payload = [e.model_dump(mode="json") for e in merged]
        path.write_text(json.dumps(payload, indent=2) + "\n")
        paths.append(path)
    return paths


def read_lists_year(year: int, *, root: Path | None = None) -> list[BacktestListEntry]:
    """Load one year's backfilled best/worst-25 file, empty when missing."""
    base = root if root is not None else settings.backtest_dir / "lists"
    path = _year_path(base, year)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [BacktestListEntry.model_validate(item) for item in raw]


def write_trades_years(
    cadence: str, entries: list[TradeLogEntry], *, root: Path | None = None
) -> list[Path]:
    """D21/D17: append-only write of one cadence's rebalance log as per-year files.

    Same freeze guarantee as `write_series_years`/`write_lists_years`: an
    already-stored rank date's entry is never rewritten. Keyed by
    `rank_date` (not `trade_date`) for year bucketing + dedup, matching
    `results/backtest/lists/YYYY.json`'s own per-rank-date grouping.
    """
    base = root if root is not None else settings.backtest_dir / "trades" / cadence
    last_stored: date | None = None
    for year in reversed(_existing_years(base)):
        year_entries = read_trades_year(cadence, year, root=base)
        if year_entries:
            last_stored = year_entries[-1].rank_date
            break
    new_entries = (
        entries if last_stored is None else [e for e in entries if e.rank_date > last_stored]
    )
    if not new_entries:
        return []
    by_year: dict[int, list[TradeLogEntry]] = {}
    for e in new_entries:
        by_year.setdefault(e.rank_date.year, []).append(e)
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    for year, yentries in sorted(by_year.items()):
        existing = read_trades_year(cadence, year, root=base)
        merged = sorted([*existing, *yentries], key=lambda e: e.rank_date)
        path = _year_path(base, year)
        payload = [e.model_dump(mode="json") for e in merged]
        path.write_text(json.dumps(payload, indent=2) + "\n")
        paths.append(path)
    return paths


def read_trades_year(cadence: str, year: int, *, root: Path | None = None) -> list[TradeLogEntry]:
    """Load one cadence's per-year rebalance-log file, empty when missing."""
    base = root if root is not None else settings.backtest_dir / "trades" / cadence
    path = _year_path(base, year)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [TradeLogEntry.model_validate(item) for item in raw]


def write_summary(summary: BacktestSummary, *, path: Path | None = None) -> Path:
    """Write `results/backtest/summary.json`."""
    target = path if path is not None else settings.backtest_dir / "summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary.model_dump_json(indent=2) + "\n")
    return target


def read_summary(*, path: Path | None = None) -> BacktestSummary | None:
    """Load `results/backtest/summary.json`, `None` when missing."""
    target = path if path is not None else settings.backtest_dir / "summary.json"
    if not target.exists():
        return None
    return BacktestSummary.model_validate_json(target.read_text())


# ----- main() -----


def _maybe_rebuild_series_b() -> None:
    """D17/D18: on a `method_version` mismatch, wipe series B for its one-time full rebuild.

    Covers both the start-trim fix (pre-`start` daily rows) and the D18 lag
    (which can shift rankings/scores at any historical date, so the lists
    need rebuilding too) — a single bump handles both.
    """
    existing = read_summary()
    if existing is not None and existing.method_version == _METHOD_VERSION_B:
        return
    logger.info("method_version bump (-> %s): full one-time rebuild of series B", _METHOD_VERSION_B)
    for cadence in CADENCES:
        _reset_year_files(settings.backtest_series_dir / cadence)
        _reset_year_files(settings.backtest_dir / "trades" / cadence)
    _reset_year_files(settings.backtest_dir / "lists")


def _freeze_eligible(dates: list[date], run_date: date) -> list[date]:
    """Only freeze rank dates strictly BEFORE the run date (finding #5, 2026-09-24).

    A rank date equal to `run_date` (the day this run's price fetch
    actually happened) can be computed from intraday-partial data — e.g.
    mid-session European bars fetched before US markets even open — so it
    is excluded from ranking/persistence THIS run. It becomes eligible on
    a LATER run, once a full trading day's data is behind it.
    """
    return [d for d in dates if d < run_date]


def _run_series_b(
    frames_by_ticker: dict[str, Frames],
    closes: dict[str, pd.Series],
    calendar: list[date],
    returns_by_ticker: dict[str, dict[date, float]],
    spy_returns: dict[date, float],
    own_dates: dict[str, list[date]],
) -> None:
    """D17/D18: append-only recompute of series B (the reconstructed backfill)."""
    grid = rank_dates(calendar)
    start = _find_start_date(grid, frames_by_ticker, closes)
    if start is None:
        logger.warning("no grid date reaches the %d-eligible threshold", _MIN_ELIGIBLE_START)
        return
    active_grid = _freeze_eligible([d for d in grid if d >= start], calendar[-1])
    _maybe_rebuild_series_b()

    ranked_by_date, lists_entries = _rank_all_dates(active_grid, frames_by_ticker, closes)
    write_lists_years(lists_entries)

    cadence_metrics: dict[str, CadenceMetrics] = {}
    for cadence in CADENCES:
        rebal_dates = rebalance_dates(cadence, active_grid)
        weights_by_trade_date = _weights_for_cadence(
            cadence, rebal_dates, ranked_by_date, calendar, own_dates=own_dates
        )
        rows = _trim_to_first_trade(
            simulate(weights_by_trade_date, returns_by_ticker),
            weights_by_trade_date,
            run_date=datetime.now(UTC).date(),
        )
        write_series_years(cadence, rows)
        frozen_rows = _read_all_series_years(cadence)
        gross, net = metrics(frozen_rows, spy_returns)
        cadence_metrics[cadence] = CadenceMetrics(
            gross=gross, net=net, rebalances=len(weights_by_trade_date)
        )
        write_trades_years(
            cadence,
            _trade_log_for_cadence(
                cadence, rebal_dates, ranked_by_date, calendar, own_dates=own_dates
            ),
        )

    primary_rebal_dates = rebalance_dates(PRIMARY_CADENCE, active_grid)
    eligible_by_date = {d: [t for t, _ in ranked_by_date.get(d, [])] for d in primary_rebal_dates}
    strategy_net_ann = cadence_metrics[PRIMARY_CADENCE].net.ann_return or 0.0
    percentile, median_net_ann = null_percentile(
        strategy_net_ann,
        primary_rebal_dates,
        eligible_by_date,
        closes,
        calendar=calendar,
        own_dates=own_dates,
    )
    fid = _compute_fidelity(frames_by_ticker, closes)

    summary = BacktestSummary(
        method_version=_METHOD_VERSION_B,
        as_of=calendar[-1],
        start=start,
        universes=_base_universe_ids(),
        score_inputs=list(_SCORE_INPUT_FIELDS),
        cost_bps=_COST_BPS,
        primary=PRIMARY_CADENCE,
        cadences=cadence_metrics,
        null=NullBenchmark(n=_NULL_DRAWS, percentile=percentile, median_net_ann=median_net_ann),
        fidelity=fid,
        caveats=list(_CAVEATS),
    )
    logger.info("wrote %s", write_summary(summary))


def _run_series_a(
    calendar: list[date],
    returns_by_ticker: dict[str, dict[date, float]],
    spy_returns: dict[date, float],
    own_dates: dict[str, list[date]],
) -> None:
    """D15/D16: append-only recompute of series A (the genuine decisions)."""
    genuine_grid = _freeze_eligible(_genuine_rank_dates(), calendar[-1])
    if not genuine_grid:
        logger.warning("no genuine snapshot dates on/after %s; skipping series A", _GENUINE_START)
        return

    ranked_by_date, lists_entries = _genuine_rank_all_dates(genuine_grid)
    write_lists_years(lists_entries, root=settings.backtest_genuine_dir / "lists")
    entries_by_date = {e.date: e for e in lists_entries}

    cadence_metrics: dict[str, CadenceMetrics] = {}
    for cadence in CADENCES:
        rebal_dates = rebalance_dates(cadence, genuine_grid)
        weights_by_trade_date = _genuine_weights_for_cadence(
            cadence, rebal_dates, ranked_by_date, calendar, own_dates=own_dates
        )
        rows = _trim_to_first_trade(
            simulate(weights_by_trade_date, returns_by_ticker),
            weights_by_trade_date,
            run_date=datetime.now(UTC).date(),
        )
        series_root = settings.backtest_series_genuine_dir / cadence
        write_series_years(cadence, rows, root=series_root)
        frozen_rows = _read_all_series_years(cadence, root=series_root)
        gross, net = metrics(frozen_rows, spy_returns)
        cadence_metrics[cadence] = CadenceMetrics(
            gross=gross, net=net, rebalances=len(weights_by_trade_date)
        )
        write_trades_years(
            cadence,
            _genuine_trade_log_for_cadence(
                cadence,
                rebal_dates,
                ranked_by_date,
                entries_by_date,
                calendar,
                own_dates=own_dates,
            ),
            root=settings.backtest_genuine_dir / "trades" / cadence,
        )

    summary = BacktestSummary(
        method_version=_METHOD_VERSION_A,
        as_of=calendar[-1],
        start=min(genuine_grid),
        universes=_base_universe_ids(),
        score_inputs=list(_LIVE_SCORE_INPUT_FIELDS),
        cost_bps=_COST_BPS,
        primary=PRIMARY_CADENCE,
        cadences=cadence_metrics,
        null=None,
        fidelity=None,
        caveats=list(_CAVEATS_GENUINE),
    )
    logger.info(
        "wrote %s", write_summary(summary, path=settings.backtest_genuine_dir / "summary.json")
    )


def main() -> None:
    """Cron entrypoint: append-only recompute of both series (D15-D19).

    Statement/price fetches are shared across series A and B (same D1
    universe, same union calendar) — one network round-trip, two rankings.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tickers = _universe_tickers()
    frames_by_ticker = {t: fetch_frames(t) for t in tqdm(tickers, desc="statements")}
    closes = _drop_bad_tickers(_batch_close_prices(tickers) or {})
    write_closes_cache(closes)
    calendar = _union_calendar(closes)
    if not calendar:
        logger.warning("no price data fetched; nothing to compute")
        return

    returns_by_ticker = _filter_bad_ticks(_reindex_returns(closes, calendar))
    spy_returns = _pct_change_map(_fetch_history_closes("SPY", "max"))

    own_dates = _own_dates(closes)
    _run_series_b(frames_by_ticker, closes, calendar, returns_by_ticker, spy_returns, own_dates)
    _run_series_a(calendar, returns_by_ticker, spy_returns, own_dates)


if __name__ == "__main__":
    main()
