"""Shared demo-snapshot loader + paired-preset writer for build scripts.

Used by the orchestrator-build scripts that consume the demo-snapshot
files committed to the ``data`` branch:

- ``scripts/build_aggregated_scores_best_and_worst.py``
- ``scripts/build_enhanced_kpi_screener_longshort.py``

Phase 2b's FCF orchestrator (issue #192) will become the 3rd consumer;
rule-of-three extraction follows the same logic as
``src/orchestrators/_shared.py`` (PR #236).

Leading-underscore module name signals "internal to scripts/"; scripts/
is repo infrastructure per ADR-0007, not shipped in the wheel.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.data_sources.fundamentals import FundamentalsSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import BaseModel

# Universes the paired-orchestrator scripts aggregate over. Mirrors the
# bundled preset set MINUS the meta universes themselves (don't feed an
# aggregator's output back into itself).
SOURCE_UNIVERSES: tuple[str, ...] = (
    "qte77-watchlist",
    "sp500",
    "eurostoxx",
    "federal-contractors",
    "japan",
    "south-america",
    "south-korea",
)


def load_snapshots(
    universe_id: str,
) -> tuple[list[FundamentalsSnapshot], str] | None:
    """Read latest snapshot for one universe; returns ``None`` if absent.

    Uses the ``index.json`` manifest (written by ``build_demo_manifest.py``)
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


def load_all_snapshots() -> tuple[
    dict[str, list[FundamentalsSnapshot]], dict[str, str]
]:
    """Load every ``SOURCE_UNIVERSES`` entry; return two parallel dicts.

    Universes absent from ``results/demo/`` are printed to stdout and
    skipped — matches the prior per-script behaviour so the workflow log
    still surfaces missing inputs.
    """
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]] = {}
    snapshot_dates_by_universe: dict[str, str] = {}
    for universe_id in SOURCE_UNIVERSES:
        loaded = load_snapshots(universe_id)
        if loaded is None:
            print(f"Skipping {universe_id}: no snapshot found.")
            continue
        snapshots, date_str = loaded
        snapshots_by_universe[universe_id] = snapshots
        snapshot_dates_by_universe[universe_id] = date_str
    return snapshots_by_universe, snapshot_dates_by_universe


def write_paired_universe_and_audit(
    list_a: list[str],
    list_b: list[str],
    audit_rows: Sequence[BaseModel],
    *,
    preset_a_name: str,
    preset_b_name: str,
    audit_dir: str,
) -> None:
    """Write two preset files + one audit JSON for paired-orchestrator scripts.

    Path conventions:

    - ``src/assets/universes/<preset_name>.txt`` — preset files (one
      ticker per line; empty file when the corresponding list is empty).
    - ``results/<audit_dir>/audit/<UTC-date>.json`` — per-run audit trail
      (one JSON array of ``model_dump`` rows).

    Each preset and the audit are reported on stdout to match the prior
    per-script behaviour.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    path_a = Path(f"src/assets/universes/{preset_a_name}.txt")
    path_b = Path(f"src/assets/universes/{preset_b_name}.txt")
    audit_path = Path(f"results/{audit_dir}/audit/{today}.json")

    path_a.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    path_a.write_text("\n".join(list_a) + "\n" if list_a else "")
    path_b.write_text("\n".join(list_b) + "\n" if list_b else "")
    audit_path.write_text(
        json.dumps([row.model_dump() for row in audit_rows], indent=2),
    )
    print(f"Wrote {len(list_a)} tickers to {path_a}")
    print(f"Wrote {len(list_b)} tickers to {path_b}")
    print(f"Wrote {len(audit_rows)} audit rows to {audit_path}")
