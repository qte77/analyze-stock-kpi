"""Cross-universe composite-mean aggregator.

Reads the latest snapshot per bundled universe from the ``data`` branch,
ranks tickers by the mean of their 7 composite scores
(``quality / dividend / growth / big_call / aaqs / hgi / screener_score``),
and emits a 50-ticker preset combining the top 25 + bottom 25.

The ranking primitive is composite-mean -- explicit signal that this is
a meta-screening *starting point*, NOT a hedging primitive. Top-25 by
composite-mean is not equivalent to "fundamentally strong long
candidate"; the hedging-grade signal lives in
:mod:`src.orchestrators.enhanced_kpi_screener_longshort` (issue #192).

Mirrors :mod:`src.orchestrators.federal_contractors` for orchestrator
shape: returns ``(list[ticker], list[AuditRow])``; per-ticker decisions
captured in the audit JSON committed to the ``data`` branch.

See ADR-0005 for tier classification (Tier-0; pure aggregation of
already-Tier-0 snapshots; no new external boundary).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from ._shared import dedup_by_ticker, is_stale

if TYPE_CHECKING:
    from src.data_sources.fundamentals import FundamentalsSnapshot


_COMPOSITE_FIELDS = (
    "quality",
    "dividend",
    "growth",
    "big_call",
    "aaqs",
    "hgi",
    "screener_score",
)


class AuditRow(BaseModel):
    """Per-ticker decision trail for the aggregator."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    source_universes: list[str]
    snapshot_dates: dict[str, str]
    populated_composites: int
    composite_breakdown: dict[str, float | None]
    mean_composite: float | None = None
    eligible: bool = False
    excluded_reason: str | None = None
    rank: int | None = None


def _extract_composites(snap: FundamentalsSnapshot) -> dict[str, float | None]:
    """Pull the 7 composite scores into a name->value dict."""
    cs = snap.composite_scores
    if cs is None:
        return dict.fromkeys(_COMPOSITE_FIELDS)
    return {f: getattr(cs, f) for f in _COMPOSITE_FIELDS}


def _mean_of_populated(values: dict[str, float | None]) -> float | None:
    """Mean of non-None values; None if all are None."""
    populated = [v for v in values.values() if v is not None]
    return sum(populated) / len(populated) if populated else None


def _classify(
    ticker: str,
    info: dict[str, Any],
    as_of: date,
    max_stale_days: int,
    min_composites: int,
) -> tuple[AuditRow, float | None]:
    """Build the AuditRow and return ``(row, mean_for_ranking)``.

    ``mean_for_ranking`` is ``None`` for excluded tickers (won't be ranked).
    """
    snap = info["snapshot"]
    source_universes = info["source_universes"]
    snapshot_dates = info["snapshot_dates"]
    composites = _extract_composites(snap)
    populated = sum(1 for v in composites.values() if v is not None)
    first_date = snapshot_dates[source_universes[0]]
    base = {
        "ticker": ticker,
        "source_universes": source_universes,
        "snapshot_dates": snapshot_dates,
        "populated_composites": populated,
        "composite_breakdown": composites,
    }
    if is_stale(first_date, as_of, max_stale_days):
        return AuditRow(**base, eligible=False, excluded_reason="stale"), None
    if populated < min_composites:
        return (
            AuditRow(**base, eligible=False, excluded_reason="insufficient_composites"),
            None,
        )
    mean = _mean_of_populated(composites)
    return AuditRow(**base, mean_composite=mean, eligible=True), mean


def build_universe(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    *,
    top_n: int = 25,
    min_composites: int = 5,
    max_stale_days: int = 14,
    as_of: date | None = None,
) -> tuple[list[str], list[str], list[AuditRow]]:
    """Build the aggregated-scores best + worst preset pair + per-ticker audit.

    Args:
        snapshots_by_universe: Mapping of universe id to its latest
            snapshot list. First-seen universe wins on per-ticker dedup.
        snapshot_dates_by_universe: Per-universe ISO ``YYYY-MM-DD``
            snapshot date used for freshness gating.
        top_n: Each side of the ranking (default 25). Output is two
            lists, each up to ``top_n``.
        min_composites: Minimum populated composites for eligibility
            (default 5/7, mirrors :func:`composite_scores.screener_score`
            L3 gate).
        max_stale_days: Snapshots older than this are excluded.
        as_of: Reference date for the freshness gate. Defaults to today
            UTC; injected for deterministic tests.

    Returns:
        ``(best_tickers, worst_tickers, audit_rows)``. ``best_tickers``
        is the top-``top_n`` by composite-mean; ``worst_tickers`` is the
        bottom-``top_n``. Both sorted ASCII ascending. Disjoint sets.
        ``audit_rows`` has one entry per ticker encountered (including
        excluded ones); rank is ``+1..+top_n`` for best, ``-top_n..-1``
        for worst, ``None`` for excluded.
    """
    if as_of is None:
        as_of = datetime.now(UTC).date()
    if not snapshots_by_universe:
        return [], [], []

    per_ticker = dedup_by_ticker(snapshots_by_universe, snapshot_dates_by_universe)

    rows_by_ticker: dict[str, AuditRow] = {}
    eligible_with_mean: list[tuple[str, float]] = []
    for ticker, info in per_ticker.items():
        row, mean = _classify(ticker, info, as_of, max_stale_days, min_composites)
        rows_by_ticker[ticker] = row
        if mean is not None:
            eligible_with_mean.append((ticker, mean))

    eligible_with_mean.sort(key=lambda x: (-x[1], x[0]))

    n = len(eligible_with_mean)
    top_count = min(top_n, n)
    bottom_count = min(top_n, n - top_count)
    best_tickers: list[str] = []
    worst_tickers: list[str] = []
    for i in range(top_count):
        ticker, _ = eligible_with_mean[i]
        rows_by_ticker[ticker] = rows_by_ticker[ticker].model_copy(
            update={"rank": i + 1},
        )
        best_tickers.append(ticker)
    for j in range(bottom_count):
        ticker, _ = eligible_with_mean[n - 1 - j]
        rows_by_ticker[ticker] = rows_by_ticker[ticker].model_copy(
            update={"rank": -(j + 1)},
        )
        worst_tickers.append(ticker)

    return sorted(best_tickers), sorted(worst_tickers), list(rows_by_ticker.values())
