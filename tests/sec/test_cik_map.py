"""Tests for :mod:`src.sec.cik_map` — CIK <-> ticker resolution."""

from __future__ import annotations

import pytest
from src.sec import cik_map
from src.sec.cik_map import CikRecord, lookup_record


@pytest.fixture
def _stub_edgar(monkeypatch: pytest.MonkeyPatch, edgar_tickers_fixture: dict) -> None:
    """Stub ``_fetch_json`` to return the committed EDGAR fixture."""
    monkeypatch.setattr(cik_map, "_fetch_json", lambda: edgar_tickers_fixture)


def test_lookup_record_returns_full_record_for_aapl(_stub_edgar: None) -> None:
    """``lookup_record('AAPL')`` resolves Apple's complete EDGAR entry."""
    record = lookup_record("AAPL")

    assert record is not None
    assert isinstance(record, CikRecord)
    assert record.ticker == "AAPL"
    assert record.title == "Apple Inc."
    assert record.exchange == "Nasdaq"


def test_resolve_cik_returns_ten_digit_zero_padded_string(_stub_edgar: None) -> None:
    """EDGAR ships CIKs as un-padded ints; resolver must left-zero-pad to 10."""
    from src.sec.cik_map import resolve_cik

    cik = resolve_cik("AAPL")

    assert cik == "0000320193"
    assert cik is not None
    assert len(cik) == 10


@pytest.mark.parametrize("symbol", ["BTC-USD", "EURUSD=X", "^VIX", "GC=F"])
def test_resolve_cik_returns_none_for_non_equity_symbols(_stub_edgar: None, symbol: str) -> None:
    """Non-SEC-registered Yahoo symbols resolve to None, not raise."""
    from src.sec.cik_map import resolve_cik

    assert resolve_cik(symbol) is None


def test_lookup_is_case_insensitive(_stub_edgar: None) -> None:
    """Ticker case doesn't matter — ``aapl`` and ``AAPL`` resolve identically."""
    from src.sec.cik_map import resolve_cik

    assert resolve_cik("aapl") == resolve_cik("AAPL")
    assert resolve_cik("aapl") == "0000320193"


def test_records_cache_fetches_json_only_once(
    monkeypatch: pytest.MonkeyPatch, edgar_tickers_fixture: dict
) -> None:
    """Two ``resolve_cik`` calls trigger exactly one underlying ``_fetch_json``."""
    from src.sec import cik_map

    call_count = 0

    def counting_fetch() -> dict:
        nonlocal call_count
        call_count += 1
        return edgar_tickers_fixture

    monkeypatch.setattr(cik_map, "_fetch_json", counting_fetch)

    cik_map.resolve_cik("AAPL")
    cik_map.resolve_cik("MSFT")

    assert call_count == 1


def test_fetch_json_sends_browser_shape_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_fetch_json`` GETs the EDGAR URL with User-Agent + Accept headers."""
    import urllib.request
    from io import BytesIO

    from src.http_ua import USER_AGENTS
    from src.sec import cik_map

    expected_accept = "application/json, text/plain, */*"
    expected_url = "https://www.sec.gov/files/company_tickers_exchange.json"

    captured: dict[str, urllib.request.Request] = {}

    def fake_urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> BytesIO:
        captured["req"] = req
        return BytesIO(b'{"fields": [], "data": []}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    cik_map._fetch_json()

    req = captured["req"]
    assert req.full_url == expected_url
    assert req.get_header("User-agent") in USER_AGENTS
    assert req.get_header("Accept") == expected_accept


@pytest.mark.network
def test_resolve_cik_live_aapl_returns_apple_cik() -> None:
    """End-to-end against real EDGAR — AAPL must resolve to 0000320193."""
    from src.sec.cik_map import resolve_cik

    assert resolve_cik("AAPL") == "0000320193"


@pytest.mark.network
def test_resolve_cik_live_returns_none_for_non_equity() -> None:
    """End-to-end: ``BTC-USD`` is not in EDGAR; resolver returns None."""
    from src.sec.cik_map import resolve_cik

    assert resolve_cik("BTC-USD") is None
