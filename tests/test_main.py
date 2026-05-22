"""Tests for :mod:`src.__main__` helpers (pure-function layer only).

The Rich-table printing side is not unit-tested by convention
(``src/__main__.py`` is excluded from coverage in ``pyproject.toml``).
``_summary_row`` is a pure list-builder and is the smallest unit
worth pinning so the website / CLI column parity contract doesn't
silently drift.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from src.__main__ import (
    _format_days_since,
    _persist_snapshots,
    _run_refresh_universe,
    _summary_row,
)
from src.config import settings
from src.data_sources.fundamentals import FundamentalsSnapshot
from src.domain.composite_scores import CompositeScores
from src.orchestrators.federal_contractors import AuditRow
from src.utils.parse_args import CliArgs

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _snap(**kwargs: object) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(symbol="X", **kwargs)  # type: ignore[arg-type]


def test_summary_row_matches_13_column_dashboard_order() -> None:
    """``_summary_row`` mirrors ``docs/demo/index.html`` column order.

    Inputs chosen so every field formats to a clean string.
    """
    snap = _snap(
        long_name="Test Co",
        sector="Technology",
        forward_pe=20.0,
        trailing_peg_ratio=1.5,
        beta=1.0,
        rd_to_revenue=0.10,
        operating_margins=0.20,
        return_on_equity=0.25,
        return_on_assets=0.10,
        current_ratio=2.0,
        sortino_ratio=1.5,
        composite_scores=CompositeScores(screener_score=72.4),
    )
    row = _summary_row(snap, show_scores=False)
    assert row == [
        "X",
        "Test Co",
        "Technology",
        "20.00",
        "1.50",
        "1.00",
        "10.00%",
        "20.00%",
        "25.00%",
        "10.00%",
        "2.00",
        "1.50",
        "72",
        "-",  # days-since-10-Q empty because sec_last_10q_date not set on snap
    ]


def test_summary_row_show_scores_appends_three_legacy_columns() -> None:
    """``--show-scores`` adds Quality / Dividend / Growth to the 13 base cols."""
    snap = _snap(
        composite_scores=CompositeScores(
            quality=80.0, dividend=60.0, growth=70.0, screener_score=72.5
        ),
    )
    base = _summary_row(snap, show_scores=False)
    extended = _summary_row(snap, show_scores=True)
    assert len(extended) == len(base) + 3
    assert extended[-3:] == ["80", "60", "70"]


def test_summary_row_sparse_snapshot_renders_dashes() -> None:
    """Sparse snapshot (FX / futures / crypto) renders dashes throughout."""
    row = _summary_row(_snap(), show_scores=False)
    assert row[0] == "X"
    # Every numeric column should be "-" when its input is missing.
    assert all(cell == "-" for cell in row[1:])


def test_format_days_since_returns_dash_when_none() -> None:
    """Missing filing date renders as '-'."""
    assert _format_days_since(None) == "-"


def test_format_days_since_returns_plain_n_for_fresh_filing() -> None:
    """Filing date within the 150d staleness window renders as 'Nd' (no markup)."""
    assert _format_days_since(date(2025, 12, 1), today=date(2026, 1, 1)) == "31d"


def test_format_days_since_wraps_red_when_stale() -> None:
    """Filing date >150d ago renders in Rich [red]…[/red] markup."""
    # 151 days from 2026-01-01 → 2025-08-03
    assert _format_days_since(date(2025, 8, 3), today=date(2026, 1, 1)) == "[red]151d[/red]"


def test_summary_row_appends_days_since_10q_column_when_populated() -> None:
    """``_summary_row`` appends a 14th column for the days-since-10-Q value."""
    snap = _snap(sec_last_10q_date=date(2024, 8, 2))
    row = _summary_row(snap, show_scores=False)

    assert len(row) == 14
    assert row[13] != "-"


def test_summary_row_days_since_10q_renders_dash_when_missing() -> None:
    """Sparse snapshot (no `sec_last_10q_date`) renders the column as '-'."""
    row = _summary_row(_snap(), show_scores=False)

    assert len(row) == 14
    assert row[13] == "-"


def test_persist_snapshots_serializes_sec_date_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Snapshot with populated SEC date fields serializes to valid JSON.

    Regression for run #26303499996: SEC enrichment now succeeds (PR #127),
    so ``sec_last_*_date`` are real ``date`` objects. Without ``mode="json"``,
    ``json.dumps`` raises ``TypeError: Object of type date is not JSON serializable``.
    """
    monkeypatch.setattr(
        "src.__main__.settings",
        settings.model_copy(update={"fundamentals_dir": tmp_path}),
    )
    snap = _snap(
        sec_last_10k_date=date(2024, 11, 1),
        sec_last_10q_date=date(2024, 8, 2),
        sec_last_8k_date=date(2024, 12, 15),
    )

    out_path = _persist_snapshots([snap])

    payload = json.loads(out_path.read_text())
    assert payload[0]["sec_last_10k_date"] == "2024-11-01"
    assert payload[0]["sec_last_10q_date"] == "2024-08-02"
    assert payload[0]["sec_last_8k_date"] == "2024-12-15"


def _stub_build_universe(
    tickers: list[str], audit: list[AuditRow]
) -> object:
    """Build a fake ``build_universe(...)`` returning the given tuple."""
    def _stub(*_a: object, **_kw: object) -> tuple[list[str], list[AuditRow]]:
        return (tickers, audit)
    return _stub


def test_run_refresh_universe_writes_to_explicit_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """``--output`` / ``--audit-output`` paths are honoured when set."""
    audit = [
        AuditRow(rank=1, recipient_name="LOCKHEED MARTIN CORPORATION", obligated_usd=1.0),
    ]
    monkeypatch.setattr(
        "src.__main__.build_universe",
        _stub_build_universe(["LMT", "RTX"], audit),
    )
    args = CliArgs.model_construct(
        refresh_universe="federal-contractors",
        output=tmp_path / "preset.txt",
        audit_output=tmp_path / "audit.json",
    )

    preset_path = _run_refresh_universe(args)

    assert preset_path == tmp_path / "preset.txt"
    assert preset_path.read_text() == "LMT\nRTX\n"
    audit_data = json.loads((tmp_path / "audit.json").read_text())
    assert audit_data[0]["recipient_name"] == "LOCKHEED MARTIN CORPORATION"


def test_run_refresh_universe_defaults_to_settings_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No overrides -> writes under ``settings.federal_contractors_dir``."""
    monkeypatch.setattr(
        "src.__main__.settings",
        settings.model_copy(update={"federal_contractors_dir": tmp_path}),
    )
    monkeypatch.setattr(
        "src.__main__.build_universe",
        _stub_build_universe(["LMT"], []),
    )
    args = CliArgs.model_construct(refresh_universe="federal-contractors")

    preset_path = _run_refresh_universe(args)

    assert preset_path == tmp_path / "universe.txt"
    assert preset_path.read_text() == "LMT\n"
    # Audit JSON sits under an audit/ subdirectory with a UTC-date filename
    audit_dir = tmp_path / "audit"
    assert audit_dir.is_dir()
    audit_files = list(audit_dir.glob("*.json"))
    assert len(audit_files) == 1
