"""Build the aggregated-scores best + worst universe pair.

Reads the latest snapshot per bundled universe (from `results/demo/<u>/`
on the data branch, pulled into the workspace by the CI workflow), runs
the aggregator's single ranking pass, then writes:
  - `src/assets/universes/aggregated-scores-best.txt`  (top 25)
  - `src/assets/universes/aggregated-scores-worst.txt` (bottom 25)
  - `results/aggregated_scores_best_and_worst/audit/<UTC-date>.json` (trail)

The two preset files are emitted together from one ranking pass; the
universe-builder workflow runs this script per-leg (matrix dispatches
`-best` and `-worst` separately) and each leg commits only its own
preset via pathspec, leaving the other preset file harmless on disk.
Audit JSON is shared (one ranking, one audit); the data-branch commit
helper handles the matrix race on the audit-file ref.

Invoked by `.github/workflows/universe-builder.yaml` on a Sunday cron;
can also be run ad-hoc locally if you have `results/demo/` populated
(typically by checking out the `data` branch).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.data_sources.fundamentals import FundamentalsSnapshot
from src.orchestrators.aggregated_scores_best_and_worst import build_universe

# Universes to aggregate over. Mirrors the bundled preset set MINUS the
# meta universe itself (don't feed the aggregator's output back into itself).
SOURCE_UNIVERSES: tuple[str, ...] = (
    "qte77-watchlist",
    "sp500",
    "eurostoxx",
    "federal-contractors",
    "japan",
    "south-america",
    "south-korea",
)


def _load_snapshots(
    universe_id: str,
) -> tuple[list[FundamentalsSnapshot], str] | None:
    """Read latest snapshot for one universe; returns ``None`` if absent.

    Uses the ``index.json`` manifest (written by `build_demo_manifest.py`)
    to discover the latest date so we don't need to ls the directory.
    """
    base = Path(f"results/demo/{universe_id}")
    index_path = base / "index.json"
    if not index_path.exists():
        return None
    manifest = json.loads(index_path.read_text())
    latest = manifest.get("latest")
    if not latest:
        return None
    snapshot_path = base / f"{latest}.json"
    if not snapshot_path.exists():
        return None
    raw = json.loads(snapshot_path.read_text())
    snapshots = [FundamentalsSnapshot.model_validate(item) for item in raw]
    return snapshots, latest


def main() -> None:
    """Build the preset + audit."""
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]] = {}
    snapshot_dates_by_universe: dict[str, str] = {}
    for universe_id in SOURCE_UNIVERSES:
        loaded = _load_snapshots(universe_id)
        if loaded is None:
            print(f"Skipping {universe_id}: no snapshot found.")
            continue
        snapshots, date_str = loaded
        snapshots_by_universe[universe_id] = snapshots
        snapshot_dates_by_universe[universe_id] = date_str

    best, worst, audit_rows = build_universe(
        snapshots_by_universe,
        snapshot_dates_by_universe,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    best_path = Path("src/assets/universes/aggregated-scores-best.txt")
    worst_path = Path("src/assets/universes/aggregated-scores-worst.txt")
    audit_path = Path(
        f"results/aggregated_scores_best_and_worst/audit/{today}.json",
    )

    best_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    best_path.write_text("\n".join(best) + "\n" if best else "")
    worst_path.write_text("\n".join(worst) + "\n" if worst else "")
    audit_path.write_text(
        json.dumps([row.model_dump() for row in audit_rows], indent=2),
    )
    print(f"Wrote {len(best)} tickers to {best_path}")
    print(f"Wrote {len(worst)} tickers to {worst_path}")
    print(f"Wrote {len(audit_rows)} audit rows to {audit_path}")


if __name__ == "__main__":
    main()
