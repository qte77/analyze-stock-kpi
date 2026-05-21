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


def test_extract_last_filed_extracts_all_three_us_forms(
    aapl_submissions_fixture: dict,
) -> None:
    """All three US form fields populated from the same parallel arrays."""
    snap = _extract_last_filed(aapl_submissions_fixture)

    # Fixture row 0 = 10-K (2024-11-01), row 1 = 8-K (2024-10-31),
    # row 2 = 10-Q (2024-08-02). Each is the first/most-recent of its form.
    assert snap.last_10k_date == date(2024, 11, 1)
    assert snap.last_10q_date == date(2024, 8, 2)
    assert snap.last_8k_date == date(2024, 10, 31)


def test_extract_last_filed_foreign_filer_returns_all_none() -> None:
    """Form 20-F (foreign filer) — all three US-form fields stay None."""
    payload = {
        "filings": {
            "recent": {
                "form": ["20-F", "6-K", "6-K"],
                "filingDate": ["2024-04-30", "2024-08-15", "2024-02-15"],
            }
        }
    }

    snap = _extract_last_filed(payload)

    assert snap.last_10k_date is None
    assert snap.last_10q_date is None
    assert snap.last_8k_date is None


def test_extract_last_filed_empty_recent_returns_all_none() -> None:
    """Companies with no recent filings yield an all-None snapshot."""
    payload = {"filings": {"recent": {"form": [], "filingDate": []}}}

    snap = _extract_last_filed(payload)

    assert snap.last_10k_date is None
    assert snap.last_10q_date is None
    assert snap.last_8k_date is None


def test_enrich_snapshot_sec_resolves_dates_for_sec_registered_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``resolve_cik`` returns a CIK, the three date fields are populated."""
    from src.sec import submissions
    from src.sec.submissions import LastFiledSnapshot

    fake_snap = LastFiledSnapshot(
        last_10k_date=date(2024, 11, 1),
        last_10q_date=date(2024, 8, 2),
        last_8k_date=date(2024, 10, 31),
    )
    monkeypatch.setattr(submissions, "resolve_cik", lambda _ticker: "0000320193")
    monkeypatch.setattr(submissions, "fetch_last_filed", lambda _cik: fake_snap)

    result = submissions.enrich_snapshot_sec("AAPL")

    assert result == {
        "sec_last_10k_date": date(2024, 11, 1),
        "sec_last_10q_date": date(2024, 8, 2),
        "sec_last_8k_date": date(2024, 10, 31),
    }


def test_enrich_snapshot_sec_no_cik_returns_empty_no_fetch_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-SEC-registered symbols return ``{}`` and skip the EDGAR fetch."""
    from src.sec import submissions
    from src.sec.submissions import LastFiledSnapshot

    fetch_call_count = 0

    def counting_fetch(_cik: str) -> LastFiledSnapshot:
        nonlocal fetch_call_count
        fetch_call_count += 1
        return LastFiledSnapshot()

    monkeypatch.setattr(submissions, "resolve_cik", lambda _ticker: None)
    monkeypatch.setattr(submissions, "fetch_last_filed", counting_fetch)

    result = submissions.enrich_snapshot_sec("BTC-USD")

    assert result == {}
    assert fetch_call_count == 0
