"""Tests for :mod:`src.sec.submissions` — EDGAR last-filed extraction."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.sec.submissions import _extract_last_filed

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def aapl_submissions_fixture() -> dict:
    """AAPL ``submissions.json`` fixture (trimmed to one year of filings)."""
    return json.loads((_FIXTURES_DIR / "aapl_submissions.json").read_text())


def test_extract_last_filed_picks_zipped_date_for_10k(
    aapl_submissions_fixture: dict,
) -> None:
    """Position ``i`` of ``filingDate`` matches position ``i`` of ``form``."""
    snap = _extract_last_filed(aapl_submissions_fixture)

    # Fixture's row 0 is form=10-K, filingDate=2024-11-01 → must zip there.
    assert snap.last_10k_date == date(2024, 11, 1)
