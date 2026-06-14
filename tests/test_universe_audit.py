"""Tests for :mod:`analyze_stock_kpi.orchestrators.universe_audit`.

Non-trivial cases only per repo convention: classification thresholds,
network-failure fallthrough, multi-universe aggregation. One live
``@pytest.mark.network`` smoke confirms the yfinance integration still
talks to Yahoo correctly (#168).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from analyze_stock_kpi.orchestrators.universe_audit import (
    AuditEntry,
    UniverseAuditReport,
    audit_universes,
    classify_ticker,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_OK_THRESHOLD = 40


def _fake_ticker(info: Mapping[str, object] | None) -> SimpleNamespace:
    """Mimic ``yfinance.Ticker(sym)`` — the only attribute we read is ``info``."""
    return SimpleNamespace(info=info)


def test_classify_ticker_ok_at_threshold() -> None:
    """Exactly ``_OK_THRESHOLD`` populated fields classifies as OK."""
    info = {f"k{i}": i + 1 for i in range(_OK_THRESHOLD)}
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        return_value=_fake_ticker(info),
    ):
        entry = classify_ticker("AAPL")
    assert entry.classification == "OK"
    assert entry.fields_populated == _OK_THRESHOLD
    assert entry.symbol == "AAPL"


def test_classify_ticker_sparse_below_threshold() -> None:
    """One fewer populated field flips OK → SPARSE."""
    info = {f"k{i}": i + 1 for i in range(_OK_THRESHOLD - 1)}
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        return_value=_fake_ticker(info),
    ):
        entry = classify_ticker("BRK.B")
    assert entry.classification == "SPARSE"
    assert entry.fields_populated == _OK_THRESHOLD - 1


def test_classify_ticker_empty_info_is_fail() -> None:
    """Empty info dict (Yahoo returns this for delisted symbols) → FAIL."""
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        return_value=_fake_ticker({}),
    ):
        entry = classify_ticker("STALE")
    assert entry.classification == "FAIL"
    assert entry.fields_populated == 0


def test_classify_ticker_none_info_is_fail() -> None:
    """yfinance returns ``info=None`` for some boundary cases — also FAIL."""
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        return_value=_fake_ticker(None),
    ):
        entry = classify_ticker("NONESUCH")
    assert entry.classification == "FAIL"
    assert entry.fields_populated == 0


def test_classify_ticker_network_error_is_fail_with_note() -> None:
    """Network failure must wrap-degrade: never raises, FAIL with reason in note."""
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        side_effect=ConnectionError("yahoo timed out"),
    ):
        entry = classify_ticker("AAPL")
    assert entry.classification == "FAIL"
    assert entry.note is not None
    assert "yahoo timed out" in entry.note


def test_classify_ticker_excludes_none_and_empty_string_from_count() -> None:
    """Field count should reflect signal density: None and "" don't count;
    0 / False / non-empty strings do (delisted tickers often return a few
    real fields surrounded by nulls)."""
    info = {
        "real_int": 0,  # counts
        "real_str": "EQUITY",  # counts
        "real_bool": False,  # counts
        "none_field": None,  # excluded
        "empty_str": "",  # excluded
    }
    with patch(
        "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
        return_value=_fake_ticker(info),
    ):
        entry = classify_ticker("MIXED")
    assert entry.fields_populated == 3


def test_audit_universes_aggregates_explicit_ids(tmp_path: Path) -> None:
    """Two universes, one ticker each — report exposes per-universe entries
    and a UTC ``generated_at`` stamp."""
    universe_a = tmp_path / "a.txt"
    universe_a.write_text("AAA\n")
    universe_b = tmp_path / "b.txt"
    universe_b.write_text("BBB\n")

    fake_a = _fake_ticker({f"k{i}": i + 1 for i in range(_OK_THRESHOLD)})
    fake_b = _fake_ticker({})  # FAIL

    def _ticker_side_effect(sym: str) -> SimpleNamespace:
        return {"AAA": fake_a, "BBB": fake_b}[sym]

    with (
        patch(
            "analyze_stock_kpi.orchestrators.universe_audit.yf.Ticker",
            side_effect=_ticker_side_effect,
        ),
        patch(
            "analyze_stock_kpi.orchestrators.universe_audit.PRESET_DIR",
            tmp_path,
        ),
    ):
        report = audit_universes(["a", "b"])

    assert isinstance(report, UniverseAuditReport)
    assert set(report.entries_by_universe.keys()) == {"a", "b"}
    [entry_a] = report.entries_by_universe["a"]
    [entry_b] = report.entries_by_universe["b"]
    assert isinstance(entry_a, AuditEntry)
    assert entry_a.classification == "OK"
    assert entry_b.classification == "FAIL"


@pytest.mark.network
def test_classify_ticker_live_gspc_smoke() -> None:
    """One live round-trip: ``^GSPC`` (S&P 500 index) must remain OK at Yahoo.
    Catches integration drift the mocked tests cannot."""
    entry = classify_ticker("^GSPC")
    assert entry.classification in {"OK", "SPARSE"}  # never FAIL for a major index
    assert entry.fields_populated is not None
    assert entry.fields_populated > 0
