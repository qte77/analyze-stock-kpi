"""Shared helpers for demo-snapshot-consuming orchestrators.

These started as duplicated private helpers inside
``aggregated_scores_best_and_worst`` (#184) and
``enhanced_kpi_screener_longshort`` (#192 Phase 2a). The two
copies stayed identical across the cycle; CodeFactor flagged the
duplication, and a 3rd orchestrator consuming the same input shape is
on the roadmap (Phase 2b's FCF-margin addition), so extracting now
follows AHA (rule-of-three) rather than fighting it.

Leading-underscore module name signals "internal to the orchestrators
package"; do not import from outside :mod:`analyze_stock_kpi.orchestrators`.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from analyze_stock_kpi.data_sources.fundamentals import (
    FundamentalsSnapshot,  # noqa: TC001  # pydantic runtime requirement
)


class DedupedSnapshot(BaseModel):
    """Per-ticker payload from :func:`dedup_by_ticker`.

    Replaces the prior ``dict[str, Any]`` shape — typed contract that
    consuming orchestrators access via attributes instead of string keys.
    ``source_universes`` is in insertion order; ``source_universes[0]`` is
    the first-seen universe whose snapshot was kept.
    """

    model_config = ConfigDict(extra="forbid")

    snapshot: FundamentalsSnapshot
    source_universes: list[str]
    snapshot_dates: dict[str, str]


class AuditRowBase(BaseModel):
    """Common decision-trail fields for demo-snapshot-consuming orchestrators.

    Subclassed by the aggregator + longshort audit rows so the shared
    semantic prefix (the ticker + its provenance + eligibility verdict) is
    one definition. Each child adds its own decision-specific fields
    (composite breakdown vs gate breakdown, mean composite vs tier, etc.).

    Not extended by ``federal_contractors.AuditRow`` — that's a different
    domain (per-recipient match audit, not per-ticker decision audit).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    source_universes: list[str]
    snapshot_dates: dict[str, str]
    eligible: bool = False
    excluded_reason: str | None = None


def is_stale(snapshot_date: str, as_of: date, max_stale_days: int) -> bool:
    """True if ``snapshot_date`` (ISO YYYY-MM-DD) is older than the window.

    Used by aggregator + longshort orchestrators to gate against ranking on
    a universe whose cron is paused or broken.
    """
    return (as_of - date.fromisoformat(snapshot_date)).days > max_stale_days


def dedup_by_ticker(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
) -> dict[str, DedupedSnapshot]:
    """First-seen universe wins for snapshot; every source universe recorded.

    The ranking / gating orchestrator iterates ``per_ticker.items()`` and
    uses ``source_universes[0]`` for the freshness gate (matches the
    snapshot it kept). The full membership list survives in the audit so
    cross-universe overlap stays visible.
    """
    per_ticker: dict[str, DedupedSnapshot] = {}
    for universe_id, snapshots in snapshots_by_universe.items():
        snap_date = snapshot_dates_by_universe.get(universe_id, "")
        for snap in snapshots:
            ticker = snap.symbol
            if ticker not in per_ticker:
                per_ticker[ticker] = DedupedSnapshot(
                    snapshot=snap,
                    source_universes=[universe_id],
                    snapshot_dates={universe_id: snap_date},
                )
            else:
                per_ticker[ticker].source_universes.append(universe_id)
                per_ticker[ticker].snapshot_dates[universe_id] = snap_date
    return per_ticker
