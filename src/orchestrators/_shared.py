"""Shared helpers for demo-snapshot-consuming orchestrators.

These started as duplicated private helpers inside
``aggregated_scores_best_and_worst`` (#184) and
``enhanced_kpi_screener_longshort`` (#192 Phase 2a). The two
copies stayed identical across the cycle; CodeFactor flagged the
duplication, and a 3rd orchestrator consuming the same input shape is
on the roadmap (Phase 2b's FCF-margin addition), so extracting now
follows AHA (rule-of-three) rather than fighting it.

Leading-underscore module name signals "internal to the orchestrators
package"; do not import from outside :mod:`src.orchestrators`.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.data_sources.fundamentals import FundamentalsSnapshot


def is_stale(snapshot_date: str, as_of: date, max_stale_days: int) -> bool:
    """True if ``snapshot_date`` (ISO YYYY-MM-DD) is older than the window.

    Used by aggregator + longshort orchestrators to gate against ranking on
    a universe whose cron is paused or broken.
    """
    return (as_of - date.fromisoformat(snapshot_date)).days > max_stale_days


def dedup_by_ticker(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """First-seen universe wins for snapshot; every source universe recorded.

    Per-ticker payload shape::

        {
            "snapshot": FundamentalsSnapshot,           # first-seen universe
            "source_universes": list[str],              # insertion order
            "snapshot_dates": dict[str, str],           # per-universe ISO
        }

    The ranking / gating orchestrator iterates ``per_ticker.items()`` and
    uses ``source_universes[0]`` for the freshness gate (matches the
    snapshot it kept). The full membership list survives in the audit so
    cross-universe overlap stays visible.
    """
    per_ticker: dict[str, dict[str, Any]] = {}
    for universe_id, snapshots in snapshots_by_universe.items():
        snap_date = snapshot_dates_by_universe.get(universe_id, "")
        for snap in snapshots:
            ticker = snap.symbol
            if ticker not in per_ticker:
                per_ticker[ticker] = {
                    "snapshot": snap,
                    "source_universes": [universe_id],
                    "snapshot_dates": {universe_id: snap_date},
                }
            else:
                per_ticker[ticker]["source_universes"].append(universe_id)
                per_ticker[ticker]["snapshot_dates"][universe_id] = snap_date
    return per_ticker
