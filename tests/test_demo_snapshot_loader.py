"""Tests for ``scripts/_demo_snapshot_loader.py``'s demo-display write path.

Owner requirement: the aggregated / derived-universe demo-display JSON
(``results/demo/<preset>/<date>.json``, what the dashboard actually
fetches) must carry the EXACT snapshot records the orchestrator ranked or
classified -- never a second, independent yfinance fetch. Non-trivial
behaviour only: the new demo-write side effect of
``write_paired_universe_and_audit`` and its ``index.json`` manifest
rebuild. ``scripts/`` is repo infrastructure (ADR-0007), imported here the
same way the build scripts import it -- via the script directory on
``sys.path``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot
from analyze_stock_kpi.domain.composite_scores import CompositeScores

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import _demo_snapshot_loader as loader  # noqa: E402


def _snap(symbol: str, score: float) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol, composite_scores=CompositeScores(screener_score=score)
    )


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every write in the module is a relative path -- isolate per test."""
    monkeypatch.chdir(tmp_path)


def test_write_paired_universe_and_audit_writes_demo_snapshot_from_source_records() -> None:
    """Demo JSON for each preset is written from the caller's own snapshot
    objects -- identical ``model_dump()`` (incl. ``screener_score``), not a
    re-fetch -- plus a rebuilt ``index.json`` manifest.
    """
    best_snap = _snap("AAPL", 80.0)
    worst_snap = _snap("XOM", 30.0)

    loader.write_paired_universe_and_audit(
        ["AAPL"],
        ["XOM"],
        [],
        snapshots_a=[best_snap],
        snapshots_b=[worst_snap],
        preset_a_name="aggregated-scores-best",
        preset_b_name="aggregated-scores-worst",
        audit_dir="aggregated_scores_best_and_worst",
    )

    demo_best = Path("results/demo/aggregated-scores-best")
    manifest = json.loads((demo_best / "index.json").read_text())
    dated = json.loads((demo_best / f"{manifest['latest']}.json").read_text())

    assert dated == [best_snap.model_dump(by_alias=False, mode="json")]
    assert manifest["dates"] == [manifest["latest"]]

    demo_worst = Path("results/demo/aggregated-scores-worst")
    worst_manifest = json.loads((demo_worst / "index.json").read_text())
    worst_dated = json.loads((demo_worst / f"{worst_manifest['latest']}.json").read_text())
    assert worst_dated == [worst_snap.model_dump(by_alias=False, mode="json")]


def test_write_paired_universe_and_audit_writes_empty_demo_snapshot_for_empty_list() -> None:
    """An empty side (e.g. no eligible shorts yet) still gets a valid, empty
    demo snapshot + manifest -- never a missing file the dashboard 404s on.
    """
    loader.write_paired_universe_and_audit(
        [],
        [],
        [],
        snapshots_a=[],
        snapshots_b=[],
        preset_a_name="enhanced-kpi-screener-longs",
        preset_b_name="enhanced-kpi-screener-shorts",
        audit_dir="enhanced_kpi_screener_longshort",
    )

    demo_longs = Path("results/demo/enhanced-kpi-screener-longs")
    manifest = json.loads((demo_longs / "index.json").read_text())
    dated = json.loads((demo_longs / f"{manifest['latest']}.json").read_text())
    assert dated == []
