"""Build the aggregated-scores best + worst universe pair.

Reads the latest snapshot per bundled universe (from ``results/demo/<u>/``
on the data branch, pulled into the workspace by the CI workflow), runs
the aggregator's single ranking pass, then writes:

- ``src/analyze_stock_kpi/assets/universes/aggregated-scores-best.txt``  (top 25)
- ``src/analyze_stock_kpi/assets/universes/aggregated-scores-worst.txt`` (bottom 25)
- ``results/aggregated_scores_best_and_worst/audit/<UTC-date>.json``

The two preset files are emitted together from one ranking pass; the
universe-builder workflow runs this script per-leg (matrix dispatches
``-best`` and ``-worst`` separately) and each leg commits only its own
preset via pathspec, leaving the other preset file harmless on disk.
Audit JSON is shared (one ranking, one audit); the data-branch commit
helper handles the matrix race on the audit-file ref.

Invoked by ``.github/workflows/universe-builder.yaml`` on a Sunday cron;
can also be run ad-hoc locally if you have ``results/demo/`` populated
(typically by checking out the ``data`` branch).

Snapshot loading + paired-preset/audit writes live in
``scripts/_demo_snapshot_loader.py`` (shared with the longshort screener
build script and the upcoming Phase 2b FCF build script per #192).
"""

from __future__ import annotations

from _demo_snapshot_loader import (
    load_all_snapshots,
    write_paired_universe_and_audit,
)

from analyze_stock_kpi.orchestrators.aggregated_scores_best_and_worst import build_universe


def main() -> None:
    """Build the preset pair + audit."""
    snapshots_by_universe, snapshot_dates_by_universe = load_all_snapshots()
    best, worst, audit_rows = build_universe(
        snapshots_by_universe,
        snapshot_dates_by_universe,
    )
    write_paired_universe_and_audit(
        best,
        worst,
        audit_rows,
        preset_a_name="aggregated-scores-best",
        preset_b_name="aggregated-scores-worst",
        audit_dir="aggregated_scores_best_and_worst",
    )


if __name__ == "__main__":
    main()
