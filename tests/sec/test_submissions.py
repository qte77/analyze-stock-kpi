"""Tests for :mod:`analyze_stock_kpi.data_sources.sec.submissions` — EDGAR last-filed extraction."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from analyze_stock_kpi.data_sources.sec.submissions import _extract_last_filed

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
    from analyze_stock_kpi.data_sources.sec import submissions
    from analyze_stock_kpi.data_sources.sec.submissions import LastFiledSnapshot

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


@pytest.mark.parametrize(
    "exc_factory",
    [
        pytest.param(
            lambda: __import__("urllib.error", fromlist=["URLError"]).URLError("net"),
            id="urlerror",
        ),
        pytest.param(
            lambda: __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                url="https://data.sec.gov/",
                code=503,
                msg="Service Unavailable",
                hdrs=None,
                fp=None,
            ),
            id="httperror",
        ),
    ],
)
def test_enrich_snapshot_sec_returns_empty_on_network_failure(
    monkeypatch: pytest.MonkeyPatch,
    exc_factory: object,
) -> None:
    """Network/HTTP error from ``fetch_last_filed`` → caller gets ``{}``.

    Wrap-degrade policy: one ticker's SEC failure leaves enrichment
    empty, snapshot survives.
    """
    from analyze_stock_kpi.data_sources.sec import submissions
    from analyze_stock_kpi.data_sources.sec.submissions import LastFiledSnapshot

    def raising_fetch(_cik: str) -> LastFiledSnapshot:
        raise exc_factory()  # type: ignore[operator]

    monkeypatch.setattr(submissions, "resolve_cik", lambda _ticker: "0000320193")
    monkeypatch.setattr(submissions, "fetch_last_filed", raising_fetch)

    assert submissions.enrich_snapshot_sec("AAPL") == {}


def test_enrich_snapshot_sec_no_cik_returns_empty_no_fetch_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-SEC-registered symbols return ``{}`` and skip the EDGAR fetch."""
    from analyze_stock_kpi.data_sources.sec import submissions
    from analyze_stock_kpi.data_sources.sec.submissions import LastFiledSnapshot

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


def test_fetch_last_filed_sends_browser_shape_headers_to_cik_url(
    monkeypatch: pytest.MonkeyPatch,
    aapl_submissions_fixture: dict,
) -> None:
    """GET https://data.sec.gov/submissions/CIK<10>.json with UA + Accept."""
    import urllib.request
    from io import BytesIO

    from analyze_stock_kpi.data_sources.sec import submissions
    from analyze_stock_kpi.data_sources.sec.submissions import fetch_last_filed

    expected_accept = "application/json, text/plain, */*"
    expected_url = "https://data.sec.gov/submissions/CIK0000320193.json"

    captured: dict[str, urllib.request.Request] = {}

    def fake_urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> BytesIO:
        captured["req"] = req
        return BytesIO(json.dumps(aapl_submissions_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_last_filed("0000320193")

    req = captured["req"]
    assert req.full_url == expected_url
    assert req.get_header("User-agent") == submissions.settings.sec_user_agent
    assert req.get_header("Accept") == expected_accept
    assert req.get_header("Referer") == "https://www.sec.gov/"


def test_fetch_last_filed_returns_parsed_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    aapl_submissions_fixture: dict,
) -> None:
    """Stubbed ``urlopen`` → returned ``LastFiledSnapshot`` carries fixture dates."""
    import urllib.request
    from io import BytesIO

    from analyze_stock_kpi.data_sources.sec.submissions import fetch_last_filed

    def fake_urlopen(_req: object, *args: object, **kwargs: object) -> BytesIO:
        return BytesIO(json.dumps(aapl_submissions_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    snap = fetch_last_filed("0000320193")

    assert snap.last_10k_date == date(2024, 11, 1)
    assert snap.last_10q_date == date(2024, 8, 2)
    assert snap.last_8k_date == date(2024, 10, 31)


def test_fetch_last_filed_zero_pads_short_cik(
    monkeypatch: pytest.MonkeyPatch,
    aapl_submissions_fixture: dict,
) -> None:
    """A short CIK (``"320193"``) must be left-zero-padded to 10 digits in the URL."""
    import urllib.request
    from io import BytesIO

    from analyze_stock_kpi.data_sources.sec.submissions import fetch_last_filed

    captured: dict[str, str] = {}

    def fake_urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> BytesIO:
        captured["url"] = req.full_url
        return BytesIO(json.dumps(aapl_submissions_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_last_filed("320193")

    assert captured["url"] == "https://data.sec.gov/submissions/CIK0000320193.json"


@pytest.mark.network
def test_fetch_last_filed_live_aapl_returns_recent_10q_date() -> None:
    """End-to-end against real EDGAR — AAPL must yield a real 10-Q date."""
    from analyze_stock_kpi.data_sources.sec.submissions import fetch_last_filed

    snap = fetch_last_filed("0000320193")

    assert snap.last_10q_date is not None
    assert snap.last_10q_date.year >= 2024
