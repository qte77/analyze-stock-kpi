"""Build the enhanced-kpi-screener long + short universe pair.

Phase 2a of issue #192. Reads the latest snapshot per bundled universe
from `results/demo/<u>/` on the data branch (pulled into the workspace
by the CI workflow), runs the conjunctive-gate screener, then writes:
  - `src/assets/universes/enhanced-kpi-screener-longs.txt`
  - `src/assets/universes/enhanced-kpi-screener-shorts.txt`
  - `results/enhanced_kpi_screener_longshort/audit/<UTC-date>.json`

Mirrors `scripts/build_aggregated_scores_best_and_worst.py`: one
ranking pass per cron tick produces both presets; the universe-builder
workflow runs this script per-leg (matrix dispatches `-longs` and
`-shorts` separately) and each leg commits only its own preset via
pathspec.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.data_sources.fundamentals import FundamentalsSnapshot
from src.orchestrators.enhanced_kpi_screener_longshort import build_universe

# Source universes the screener consumes. Same set as the aggregator
# (#199) — don't include the aggregator's own outputs (avoid feedback).
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
    """Read latest snapshot for one universe; returns ``None`` if absent."""
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
    """Build long + short presets + audit."""
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

    longs, shorts, audit_rows = build_universe(
        snapshots_by_universe,
        snapshot_dates_by_universe,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    longs_path = Path("src/assets/universes/enhanced-kpi-screener-longs.txt")
    shorts_path = Path("src/assets/universes/enhanced-kpi-screener-shorts.txt")
    audit_path = Path(
        f"results/enhanced_kpi_screener_longshort/audit/{today}.json",
    )

    longs_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    longs_path.write_text("\n".join(longs) + "\n" if longs else "")
    shorts_path.write_text("\n".join(shorts) + "\n" if shorts else "")
    audit_path.write_text(
        json.dumps([row.model_dump() for row in audit_rows], indent=2),
    )
    print(f"Wrote {len(longs)} tickers to {longs_path}")
    print(f"Wrote {len(shorts)} tickers to {shorts_path}")
    print(f"Wrote {len(audit_rows)} audit rows to {audit_path}")


if __name__ == "__main__":
    main()
