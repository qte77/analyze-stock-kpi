"""Cross-universe composite-mean aggregator.

Reads the latest snapshot per bundled universe from the ``data`` branch,
ranks tickers by the mean of their 7 composite scores
(``quality / dividend / growth / big_call / aaqs / hgi / screener_score``),
and emits a 50-ticker preset combining the top 25 + bottom 25.

The ranking primitive is composite-mean — explicit signal that this is
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

from datetime import date  # noqa: TC003  # pydantic needs runtime access for model fields
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

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


def build_universe(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    *,
    top_n: int = 25,
    min_composites: int = 5,
    max_stale_days: int = 14,
    as_of: date | None = None,
) -> tuple[list[str], list[AuditRow]]:
    """Build the aggregated-scores-best-and-worst preset + per-ticker audit.

    Args:
        snapshots_by_universe: Mapping of universe id to its latest
            snapshot list. First-seen universe wins on per-ticker dedup.
        snapshot_dates_by_universe: Per-universe ISO ``YYYY-MM-DD``
            snapshot date used for freshness gating.
        top_n: Each side of the ranking (default 25). Output is 2*top_n.
        min_composites: Minimum populated composites for eligibility
            (default 5/7, mirrors :func:`composite_scores.screener_score`
            L3 gate).
        max_stale_days: Snapshots older than this are excluded.
        as_of: Reference date for the freshness gate. Defaults to today
            UTC; injected for deterministic tests.

    Returns:
        ``(tickers, audit_rows)`` where ``tickers`` is the deduped
        preset (top 25 + bottom 25), and ``audit_rows`` is one entry
        per ticker encountered (including excluded ones).
    """
    raise NotImplementedError("C1 in progress")
