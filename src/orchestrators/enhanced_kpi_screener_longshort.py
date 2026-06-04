"""Long/short conjunctive-gate screener (Phase 2a of issue #192).

The aggregator (``aggregated_scores_best_and_worst``) ranks by mean of
composites — useful as a meta-screening starting point, but mean-of-
composites blends signals and can paper over real weaknesses. The
hedging-grade signal is a conjunctive-gate filter: a long candidate must
pass *every* long-side criterion, a short candidate must pass *every*
short-side criterion. Sets are disjoint by construction.

Phase 2a ships 13 of the issue's 16 criteria — every gate that reads a
field already on ``FundamentalsSnapshot`` (no new yfinance fetches).
Deferred to Phase 2b: FCF margin (criterion 12; needs ``Ticker.cashflow``)
and tech rating (criterion 15; blocked on TradingView decision #21).

| # | Field                       | Long gate         | Short gate (inverted) |
|---|-----------------------------|-------------------|-----------------------|
| 1 | market_cap                  | >= 2e9            | >= 2e9 (liquidity)    |
| 2 | forward_pe                  | <= 25             | > 25                  |
| 3 | earnings_growth             | > 0.10            | < 0                   |
| 4 | revenue_growth              | > 0.10            | < 0                   |
| 5 | trailing_peg_ratio          | < 1               | >= 1                  |
| 6 | return_on_equity            | > 0.10            | < 0.05                |
| 7 | beta                        | > 1               | > 1 (hedge wants vol) |
| 8 | return_on_assets            | > 0.10            | < 0.02                |
| 9 | roi (ADR-0004 proxy)        | > 0.10            | < 0.05                |
| 10 | current_ratio              | > 1               | < 1                   |
| 11 | quick_ratio                | > 1               | < 1                   |
| 13 | profit_margins             | > 0.10            | < 0                   |
| 14 | analyst_recommendation     | buy / strong_buy  | sell / strong_sell    |
| 16 | rd_to_revenue              | > 0.05            | (long-only)           |

Mirrors :mod:`src.orchestrators.aggregated_scores_best_and_worst` for
shape: returns ``(longs, shorts, audit)`` from ``build_universe``;
per-ticker audit captures pass/fail per criterion plus the assigned tier.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from ._shared import dedup_by_ticker, is_stale

if TYPE_CHECKING:
    from src.data_sources.fundamentals import FundamentalsSnapshot


Tier = Literal["long", "short", "neither"]

_LONG_BUY_KEYS = frozenset({"buy", "strong_buy"})
_SHORT_SELL_KEYS = frozenset({"sell", "strong_sell"})


_Predicate = Callable[[float], bool]


def _passes(value: float | None, predicate: _Predicate) -> bool:
    """Numeric-gate helper: ``False`` when the value is missing."""
    return value is not None and predicate(value)


# Declarative gate table: (field, long_predicate, short_predicate). Two
# entries are special-cased outside the table — `analyst_recommendation`
# (string-set membership rather than numeric) and `rd_to_revenue`
# (long-only; no short-side gate). Keeping the table flat lets `_evaluate`
# stay a simple iteration.
_NUMERIC_GATES: tuple[tuple[str, _Predicate, _Predicate], ...] = (
    ("market_cap", lambda v: v >= 2e9, lambda v: v >= 2e9),
    ("forward_pe", lambda v: v <= 25, lambda v: v > 25),
    ("earnings_growth", lambda v: v > 0.10, lambda v: v < 0),
    ("revenue_growth", lambda v: v > 0.10, lambda v: v < 0),
    ("trailing_peg_ratio", lambda v: v < 1, lambda v: v >= 1),
    ("return_on_equity", lambda v: v > 0.10, lambda v: v < 0.05),
    ("beta", lambda v: v > 1, lambda v: v > 1),
    ("return_on_assets", lambda v: v > 0.10, lambda v: v < 0.02),
    ("roi", lambda v: v > 0.10, lambda v: v < 0.05),
    ("current_ratio", lambda v: v > 1, lambda v: v < 1),
    ("quick_ratio", lambda v: v > 1, lambda v: v < 1),
    ("profit_margins", lambda v: v > 0.10, lambda v: v < 0),
)


class AuditRow(BaseModel):
    """Per-ticker decision trail for the long/short screener."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    source_universes: list[str]
    snapshot_dates: dict[str, str]
    populated_criteria: int
    long_breakdown: dict[str, bool]
    short_breakdown: dict[str, bool]
    tier: Tier = "neither"
    eligible: bool = False
    excluded_reason: str | None = None


def _evaluate(
    snap: FundamentalsSnapshot,
) -> tuple[dict[str, bool], dict[str, bool], int]:
    """Apply 14 long + 13 short gates; return ``(long_pass, short_pass, populated)``.

    A criterion is "populated" when its underlying field is non-None; an
    unpopulated criterion implicitly fails both gates so a sparse snapshot
    can never pass a conjunctive gate by accident.
    """
    long_pass: dict[str, bool] = {}
    short_pass: dict[str, bool] = {}
    populated = 0
    for field, long_pred, short_pred in _NUMERIC_GATES:
        v = getattr(snap, field)
        long_pass[field] = _passes(v, long_pred)
        short_pass[field] = _passes(v, short_pred)
        if v is not None:
            populated += 1
    rec = snap.analyst_recommendation
    long_pass["analyst_recommendation"] = rec in _LONG_BUY_KEYS
    short_pass["analyst_recommendation"] = rec in _SHORT_SELL_KEYS
    if rec is not None:
        populated += 1
    rdr = snap.rd_to_revenue
    long_pass["rd_to_revenue"] = _passes(rdr, lambda v: v > 0.05)
    if rdr is not None:
        populated += 1
    return long_pass, short_pass, populated


def _classify(
    ticker: str,
    info: dict[str, Any],
    as_of: date,
    max_stale_days: int,
    min_criteria: int,
) -> AuditRow:
    """Build the AuditRow and assign the ticker to ``long`` / ``short`` / ``neither``."""
    snap: FundamentalsSnapshot = info["snapshot"]
    source_universes = info["source_universes"]
    snapshot_dates = info["snapshot_dates"]
    long_pass, short_pass, populated = _evaluate(snap)
    first_date = snapshot_dates[source_universes[0]]
    base = {
        "ticker": ticker,
        "source_universes": source_universes,
        "snapshot_dates": snapshot_dates,
        "populated_criteria": populated,
        "long_breakdown": long_pass,
        "short_breakdown": short_pass,
    }
    if is_stale(first_date, as_of, max_stale_days):
        return AuditRow(**base, eligible=False, excluded_reason="stale")
    if populated < min_criteria:
        return AuditRow(
            **base, eligible=False, excluded_reason="insufficient_criteria",
        )
    # 14 long-side gates (incl. rd_to_revenue), 13 short-side (no R&D).
    tier: Tier
    if all(long_pass.values()):
        tier = "long"
    elif all(v for k, v in short_pass.items() if k != "rd_to_revenue"):
        tier = "short"
    else:
        tier = "neither"
    return AuditRow(**base, eligible=True, tier=tier)


def build_universe(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    *,
    min_criteria: int = 10,
    max_stale_days: int = 14,
    as_of: date | None = None,
) -> tuple[list[str], list[str], list[AuditRow]]:
    """Build the long-candidate + short-candidate presets + per-ticker audit.

    Args:
        snapshots_by_universe: Mapping of universe id to latest snapshot
            list. First-seen universe wins on per-ticker dedup.
        snapshot_dates_by_universe: Per-universe ISO ``YYYY-MM-DD``
            snapshot date used for the freshness gate.
        min_criteria: Minimum populated criteria for eligibility (10 of 14
            evaluable; matches the aggregator's 5-of-7 ratio).
        max_stale_days: Snapshots older than this are excluded.
        as_of: Reference date for the freshness gate. Defaults to today
            UTC; injected for deterministic tests.

    Returns:
        ``(longs, shorts, audit_rows)``. Long ∩ short empty by
        construction. Both lists sorted ASCII ascending. ``audit_rows``
        has one entry per ticker encountered (including excluded ones);
        ``tier`` is ``"long"`` / ``"short"`` / ``"neither"`` for eligible
        tickers, ``"neither"`` for excluded.
    """
    if as_of is None:
        as_of = datetime.now(UTC).date()
    if not snapshots_by_universe:
        return [], [], []

    per_ticker = dedup_by_ticker(
        snapshots_by_universe, snapshot_dates_by_universe,
    )

    longs: list[str] = []
    shorts: list[str] = []
    audit: list[AuditRow] = []
    for ticker, info in per_ticker.items():
        row = _classify(ticker, info, as_of, max_stale_days, min_criteria)
        audit.append(row)
        if row.tier == "long":
            longs.append(ticker)
        elif row.tier == "short":
            shorts.append(ticker)

    return sorted(longs), sorted(shorts), audit
