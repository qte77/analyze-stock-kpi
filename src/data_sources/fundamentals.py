"""Fundamentals fetched from Yahoo Finance via yfinance.

Public API:
    - :func:`fetch_fundamentals` returns a :class:`FundamentalsSnapshot`
    - :func:`fetch_price_history` returns OHLCV as a pandas ``DataFrame``
    - :func:`fetch_universe_fundamentals` runs sequential fetches with a
      progress bar; per-ticker errors are logged and the ticker is skipped
      so the run does not crash on a single bad symbol.

All numeric snapshot fields are ``Optional[float]`` because yfinance
returns sparse ``info`` for non-equities (FX ``EURUSD=X``, futures
``GC=F``, crypto ``BTC-USD``). Sparse snapshots are valid by design.

Enrichment fields (``roi``, ``rd_to_revenue``, ``sortino_ratio``,
``composite_scores``) are attached post-validate via ``model_copy``.
``sortino_ratio`` is the first composite input derived from price
history rather than ``Ticker.info``; see ADR-0004 for the rationale.
"""

from __future__ import annotations

import logging
from datetime import date  # noqa: TC003  # pydantic needs runtime access for model fields
from typing import TYPE_CHECKING, Any

import yfinance as yf
from pydantic import BaseModel, ConfigDict, Field
from src.domain.composite_scores import (
    CompositeScores,  # noqa: TC002  # pydantic runtime requirement
)
from tqdm import tqdm

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import pandas as pd

logger = logging.getLogger(__name__)


class FundamentalsSnapshot(BaseModel):
    """Point-in-time fundamentals for a single Yahoo Finance ticker.

    Field aliases mirror yfinance ``info`` keys (camelCase) so a snapshot
    can be built with ``model_validate(yf.Ticker(t).info)``. Tests construct
    via snake_case kwargs because ``populate_by_name=True``.
    """

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    # -- identity --
    symbol: str
    long_name: str | None = Field(default=None, alias="longName")
    short_name: str | None = Field(default=None, alias="shortName")
    quote_type: str | None = Field(default=None, alias="quoteType")
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    exchange: str | None = None

    # -- valuation --
    market_cap: float | None = Field(default=None, alias="marketCap")
    trailing_pe: float | None = Field(default=None, alias="trailingPE")
    forward_pe: float | None = Field(default=None, alias="forwardPE")
    price_to_book: float | None = Field(default=None, alias="priceToBook")
    price_to_sales_ttm: float | None = Field(
        default=None, alias="priceToSalesTrailing12Months"
    )
    enterprise_value: float | None = Field(default=None, alias="enterpriseValue")
    enterprise_to_ebitda: float | None = Field(default=None, alias="enterpriseToEbitda")
    trailing_peg_ratio: float | None = Field(default=None, alias="trailingPegRatio")

    # -- profitability --
    return_on_equity: float | None = Field(default=None, alias="returnOnEquity")
    return_on_assets: float | None = Field(default=None, alias="returnOnAssets")
    profit_margins: float | None = Field(default=None, alias="profitMargins")
    gross_margins: float | None = Field(default=None, alias="grossMargins")
    operating_margins: float | None = Field(default=None, alias="operatingMargins")

    # -- financial health --
    debt_to_equity: float | None = Field(default=None, alias="debtToEquity")
    current_ratio: float | None = Field(default=None, alias="currentRatio")
    quick_ratio: float | None = Field(default=None, alias="quickRatio")

    # -- growth --
    revenue_growth: float | None = Field(default=None, alias="revenueGrowth")
    earnings_growth: float | None = Field(default=None, alias="earningsGrowth")

    # -- dividends --
    dividend_yield: float | None = Field(default=None, alias="dividendYield")
    payout_ratio: float | None = Field(default=None, alias="payoutRatio")

    # -- per-share --
    trailing_eps: float | None = Field(default=None, alias="trailingEps")
    forward_eps: float | None = Field(default=None, alias="forwardEps")
    book_value: float | None = Field(default=None, alias="bookValue")

    # -- 52-week range --
    fifty_two_week_high: float | None = Field(default=None, alias="fiftyTwoWeekHigh")
    fifty_two_week_low: float | None = Field(default=None, alias="fiftyTwoWeekLow")

    # -- volatility --
    beta: float | None = None

    # -- analyst sentiment --
    # yfinance ships this inside the existing `info` payload (no extra HTTP).
    # Values are lowercase Yahoo Finance recommendation buckets:
    # "strong_buy" / "buy" / "hold" / "sell" / "strong_sell" / None.
    analyst_recommendation: str | None = Field(
        default=None, alias="recommendationKey",
    )

    # -- enrichment (attached post-fetch via ``model_copy``) --
    composite_scores: CompositeScores | None = None
    roi: float | None = None
    rd_to_revenue: float | None = None
    fcf_margin: float | None = None
    sortino_ratio: float | None = None
    sec_last_10k_date: date | None = None
    sec_last_10q_date: date | None = None
    sec_last_8k_date: date | None = None


def _normalize_yfinance_info(info: dict[str, Any]) -> dict[str, Any]:
    """Apply yfinance schema-drift normalizations at the fetch boundary.

    Current yfinance ships ``info["dividendYield"]`` as a **percentage**
    value (e.g. ``0.37`` for AAPL's actual 0.37 % yield); the rest of
    the codebase assumes the older fractional convention
    (``_format_percent`` multiplies by 100 for display;
    ``composite_scores._YIELD_HI = 0.07`` is a 7 % fractional ceiling).
    Divide by 100 unconditionally so every downstream consumer sees one
    convention.

    Placed at the fetch boundary rather than as a pydantic
    ``field_validator`` so tests constructing ``FundamentalsSnapshot``
    directly with fractional snake_case kwargs (``dividend_yield=0.07``)
    keep working without going through this normalization.
    """
    out = dict(info)
    raw_yield = out.get("dividendYield")
    if raw_yield is not None:
        out["dividendYield"] = raw_yield / 100
    return out


def _safe_ratio(num: float | None, den: float | None) -> float | None:
    """Divide ``num / den`` with a None / zero-denominator guard.

    Returns ``None`` when either operand is missing or the denominator
    is zero; a zero *numerator* yields a valid ``0.0``. Centralises the
    guard repeated by ``_compute_roi`` and the EQUITY-gated ratio fetchers.
    """
    if num is None or den is None or den == 0:
        return None
    return num / den


def _compute_roi(info: dict[str, Any]) -> float | None:
    """Simplified ROIC = ``netIncomeToCommon / invested_capital``.

    Invested capital is approximated as ``book_equity + totalDebt -
    totalCash`` where ``book_equity = marketCap / priceToBook``. This
    is the screener-style ROI used by finviz et al. — not the
    company-filed ROIC (which would use NOPAT and adjusted invested
    capital). Returns ``None`` whenever any of the five inputs is
    missing, ``priceToBook`` is zero, or invested capital sums to
    zero. Inputs are transient — only the ratio lands on the snapshot.
    """
    net_income = info.get("netIncomeToCommon")
    market_cap = info.get("marketCap")
    price_to_book = info.get("priceToBook")
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    if (
        net_income is None
        or market_cap is None
        or price_to_book is None
        or total_debt is None
        or total_cash is None
    ):
        return None
    if price_to_book == 0:
        return None
    book_equity = market_cap / price_to_book
    invested_capital = book_equity + total_debt - total_cash
    return _safe_ratio(net_income, invested_capital)


_TRADING_DAYS = 252
_MIN_SORTINO_DATAPOINTS = 30


def _compute_sortino(
    close_series: pd.Series, target_annual: float = 0.0
) -> float | None:
    """Annualized Sortino ratio ``S = (R - T) / DR`` from daily closes.

    Canonical Wikipedia definition with ``T`` = user-supplied annual
    target / MAR / risk-free rate. Subtracts ``T / _TRADING_DAYS`` from
    every daily return before computing both the mean and the downside
    deviation; annualises mean by ``_TRADING_DAYS`` and downside dev by
    ``sqrt(_TRADING_DAYS)``. Default ``target_annual = 0.0`` preserves
    the prior T=0 behaviour byte-for-byte.

    Returns ``None`` when the sample has fewer than
    ``_MIN_SORTINO_DATAPOINTS`` returns, no losing days vs the target
    (downside deviation is undefined), or the input series is empty /
    all-NaN.

    Price-history-derived; see ADR-0004 for the rationale on
    extending composite-score inputs beyond point-in-time ``info``.
    """
    try:
        returns = close_series.pct_change().dropna()
    except Exception:
        return None
    if len(returns) < _MIN_SORTINO_DATAPOINTS:
        return None
    excess = returns - (target_annual / _TRADING_DAYS)
    downside = excess.where(excess < 0, 0.0)
    downside_dev_daily = float((downside**2).mean() ** 0.5)
    if downside_dev_daily == 0:
        return None
    downside_dev_annual = downside_dev_daily * (_TRADING_DAYS**0.5)
    mean_annual = float(excess.mean()) * _TRADING_DAYS
    return mean_annual / downside_dev_annual


def _find_row(latest: pd.Series, needle: str) -> float | None:
    """Case-insensitive whitespace-tolerant row lookup.

    Yahoo's income-statement labels drift across yfinance versions and
    diverge for IFRS filers (``"Research Development"`` without the
    ``"And"``, lower-case variants, stray whitespace). Substring-on-
    normalized-label catches all observed shapes without enumerating
    them one by one. ``needle`` must already be lower-cased. NaN cells
    propagate as ``float('nan')`` so the caller's identity-equality NaN
    check still fires.
    """
    for label in latest.index:
        if needle in str(label).strip().lower():
            value = latest.at[label]
            return None if value is None else float(value)
    return None


def _extract_two_rows(
    pairs: Sequence[tuple[pd.DataFrame | None, str]],
) -> tuple[float | None, float | None]:
    """Read two latest-column rows from ``(frame, needle)`` pairs.

    All-or-nothing: returns ``(None, None)`` on any structural issue in
    either pair — ``None`` / empty frame, missing row (case-insensitive
    fuzzy match via ``_find_row``), or a NaN cell. Both values are
    returned only when both are present and non-NaN. Callers may pass the
    same frame twice (R&D + revenue from one income_stmt) or two distinct
    frames (FCF from cashflow, revenue from income_stmt).
    """
    values: list[float] = []
    for frame, needle in pairs:
        if frame is None or frame.empty:
            return None, None
        value = _find_row(frame.iloc[:, 0], needle)
        if value is None or value != value:  # NaN propagates via identity check
            return None, None
        values.append(value)
    return values[0], values[1]


def _read_rd_revenue(income_stmt: pd.DataFrame | None) -> tuple[float | None, float | None]:
    """Extract latest R&D + Total Revenue from one income_stmt DataFrame.

    Thin wrapper over ``_extract_two_rows`` — both rows come from the same
    frame. Returns ``(None, None)`` on any structural issue.
    """
    return _extract_two_rows(
        [(income_stmt, "research"), (income_stmt, "total revenue")]
    )


def _equity_ratio(
    info: dict[str, Any],
    fetch: Callable[[], tuple[float | None, float | None]],
) -> float | None:
    """EQUITY-gated ``num / den`` from a fault-tolerant ``(num, den)`` thunk.

    Non-EQUITY ``quoteType`` (including a missing key) returns ``None``
    WITHOUT invoking ``fetch`` — so ETFs / FX / futures / crypto skip the
    extra yfinance HTTP entirely. ``fetch`` is a thunk so the yfinance
    property access happens inside the ``try`` (those properties can raise);
    any exception is swallowed to ``None``. The returned pair is divided via
    ``_safe_ratio`` (``None`` on a missing operand or zero denominator).
    """
    if info.get("quoteType") != "EQUITY":
        return None
    try:
        num, den = fetch()
    except Exception:
        return None
    return _safe_ratio(num, den)


def _fetch_rd_to_revenue(
    yf_ticker: yf.Ticker, info: dict[str, Any]
) -> float | None:
    """R&D-as-share-of-revenue from ``Ticker.income_stmt`` latest column.

    EQUITY-only (see ``_equity_ratio``); ``None`` on any missing data or
    fetch error.
    """
    return _equity_ratio(
        info, lambda: _read_rd_revenue(yf_ticker.income_stmt)
    )


def _read_fcf_revenue(
    cashflow: pd.DataFrame | None,
    income_stmt: pd.DataFrame | None,
) -> tuple[float | None, float | None]:
    """Extract latest Free Cash Flow + Total Revenue from yfinance frames.

    Thin wrapper over ``_extract_two_rows`` — FCF from ``cashflow``,
    revenue from ``income_stmt``. Returns ``(None, None)`` on any
    structural issue.
    """
    return _extract_two_rows(
        [(cashflow, "free cash flow"), (income_stmt, "total revenue")]
    )


def _fetch_fcf_margin(
    yf_ticker: yf.Ticker, info: dict[str, Any]
) -> float | None:
    """Free-cash-flow margin from ``Ticker.cashflow`` / ``Ticker.income_stmt``.

    EQUITY-only (see ``_equity_ratio``); ``None`` on any missing data or
    fetch error.
    """
    return _equity_ratio(
        info,
        lambda: _read_fcf_revenue(yf_ticker.cashflow, yf_ticker.income_stmt),
    )


def fetch_fundamentals(ticker: str) -> FundamentalsSnapshot:
    """Fetch fundamentals for one ticker. Sparse for non-equities."""
    yf_ticker = yf.Ticker(ticker)
    info: dict[str, Any] = yf_ticker.info
    normalized = _normalize_yfinance_info(info)
    snap = FundamentalsSnapshot.model_validate({**normalized, "symbol": ticker})
    return snap.model_copy(
        update={
            "roi": _compute_roi(normalized),
            "rd_to_revenue": _fetch_rd_to_revenue(yf_ticker, info),
            "fcf_margin": _fetch_fcf_margin(yf_ticker, info),
        }
    )


def fetch_price_history(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Fetch OHLCV via ``yf.Ticker(ticker).history(period=period)``."""
    return yf.Ticker(ticker).history(period=period)


def _batch_close_prices(tickers: list[str]) -> dict[str, Any] | None:
    """One batched ``yf.download`` for the whole universe.

    Returns ``{ticker: close_series}`` so per-ticker Sortino can be
    computed without N HTTP roundtrips. ``None`` on any failure
    (network error, empty result, unexpected DataFrame shape).
    Handles both single-ticker (flat columns) and multi-ticker
    (multi-index columns) shapes that ``yf.download`` produces.
    Returned values are pandas Series of close prices; the loose
    ``Any`` annotation accommodates pyright's narrowing of
    ``DataFrame[...]`` lookups.
    """
    if not tickers:
        return None
    try:
        df = yf.download(
            tickers, period="1y", progress=False, auto_adjust=True
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if len(tickers) == 1:
        if "Close" in df.columns:
            return {tickers[0]: df["Close"]}
        return None
    try:
        close_block = df["Close"]
    except Exception:
        return None
    result: dict[str, Any] = {
        t: close_block[t] for t in tickers if t in close_block.columns
    }
    return result or None


def fetch_universe_fundamentals(
    tickers: list[str], *, show_progress: bool = True
) -> list[FundamentalsSnapshot]:
    """Sequential fetch with tqdm. Per-ticker errors are logged and skipped.

    Adds a single batched ``yf.download`` at the start to fetch 1y close
    prices for the whole universe; Sortino is then computed per-ticker
    from the matching column and attached via ``model_copy``. The batch
    call is fault-tolerant — failure simply leaves every ``sortino_ratio``
    as ``None``.
    """
    close_by_ticker = _batch_close_prices(tickers)
    iterable = tqdm(tickers, desc="fundamentals") if show_progress else tickers
    snapshots: list[FundamentalsSnapshot] = []
    for ticker in iterable:
        try:
            snap = fetch_fundamentals(ticker)
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            continue
        sortino: float | None = None
        if close_by_ticker is not None and ticker in close_by_ticker:
            sortino = _compute_sortino(close_by_ticker[ticker])
        snapshots.append(snap.model_copy(update={"sortino_ratio": sortino}))
    return snapshots
