"""Build the enhanced-kpi-screener long + short universe pair.

Phase 2a of issue #192. Reads the latest snapshot per bundled universe
from ``results/demo/<u>/`` on the data branch (pulled into the workspace
by the CI workflow), runs the conjunctive-gate screener, then writes:

- ``src/analyze_stock_kpi/assets/universes/enhanced-kpi-screener-longs.txt``
- ``src/analyze_stock_kpi/assets/universes/enhanced-kpi-screener-shorts.txt``
- ``results/enhanced_kpi_screener_longshort/audit/<UTC-date>.json``

Mirrors ``scripts/build_aggregated_scores_best_and_worst.py``: one
ranking pass per cron tick produces both presets; the universe-builder
workflow runs this script per-leg (matrix dispatches ``-longs`` and
``-shorts`` separately) and each leg commits only its own preset via
pathspec.

Snapshot loading + paired-preset/audit writes live in
``scripts/_demo_snapshot_loader.py`` (shared with the aggregator build
script and the upcoming Phase 2b FCF build script per #192).
"""

from __future__ import annotations

from _demo_snapshot_loader import (
    load_all_snapshots,
    write_paired_universe_and_audit,
)

from analyze_stock_kpi.orchestrators.enhanced_kpi_screener_longshort import build_universe


def main() -> None:
    """Build long + short presets + audit."""
    snapshots_by_universe, snapshot_dates_by_universe = load_all_snapshots()
    longs, shorts, audit_rows = build_universe(
        snapshots_by_universe,
        snapshot_dates_by_universe,
    )
    write_paired_universe_and_audit(
        longs,
        shorts,
        audit_rows,
        preset_a_name="enhanced-kpi-screener-longs",
        preset_b_name="enhanced-kpi-screener-shorts",
        audit_dir="enhanced_kpi_screener_longshort",
    )


if __name__ == "__main__":
    main()
