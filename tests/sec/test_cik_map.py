"""Tests for :mod:`src.sec.cik_map` — CIK <-> ticker resolution."""

from __future__ import annotations

from typing import ClassVar

import pytest
from src.sec import cik_map
from src.sec.cik_map import CikRecord, lookup_record


@pytest.fixture
def _stub_edgar(monkeypatch: pytest.MonkeyPatch, edgar_tickers_fixture: dict) -> None:
    """Stub ``_fetch_json`` to return the committed EDGAR fixture."""
    monkeypatch.setattr(cik_map, "_fetch_json", lambda: edgar_tickers_fixture)


@pytest.mark.usefixtures("_stub_edgar")
def test_lookup_record_returns_full_record_for_aapl() -> None:
    """``lookup_record('AAPL')`` resolves Apple's complete EDGAR entry."""
    record = lookup_record("AAPL")

    assert record is not None
    assert isinstance(record, CikRecord)
    assert record.ticker == "AAPL"
    assert record.title == "Apple Inc."
    assert record.exchange == "Nasdaq"


@pytest.mark.usefixtures("_stub_edgar")
def test_resolve_cik_returns_ten_digit_zero_padded_string() -> None:
    """EDGAR ships CIKs as un-padded ints; resolver must left-zero-pad to 10."""
    from src.sec.cik_map import resolve_cik

    cik = resolve_cik("AAPL")

    assert cik == "0000320193"
    assert cik is not None
    assert len(cik) == 10


@pytest.mark.usefixtures("_stub_edgar")
@pytest.mark.parametrize("symbol", ["BTC-USD", "EURUSD=X", "^VIX", "GC=F"])
def test_resolve_cik_returns_none_for_non_equity_symbols(symbol: str) -> None:
    """Non-SEC-registered Yahoo symbols resolve to None, not raise."""
    from src.sec.cik_map import resolve_cik

    assert resolve_cik(symbol) is None


@pytest.mark.usefixtures("_stub_edgar")
def test_lookup_is_case_insensitive() -> None:
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


def test_fetch_json_persists_response_to_disk_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold cache: ``_fetch_json`` writes the response body to ``_CACHE_PATH``."""
    import urllib.request
    from io import BytesIO

    body = b'{"fields": ["cik","name","ticker","exchange"], "data": []}'

    def fake_urlopen(_req: object, *args: object, **kwargs: object) -> BytesIO:
        return BytesIO(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert not cik_map._CACHE_PATH.is_file()

    cik_map._fetch_json()

    assert cik_map._CACHE_PATH.is_file()
    assert cik_map._CACHE_PATH.read_bytes() == body


def test_fetch_json_sets_cache_mtime_from_last_modified_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache file mtime mirrors the server's ``Last-Modified`` HTTP-date."""
    import urllib.request
    from email.utils import parsedate_to_datetime
    from io import BytesIO

    last_modified = "Wed, 21 Oct 2026 07:28:00 GMT"

    class _FakeResponse(BytesIO):
        headers: ClassVar[dict[str, str]] = {"Last-Modified": last_modified}

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(_req: object, *_a: object, **_k: object) -> _FakeResponse:
        return _FakeResponse(b'{"fields": [], "data": []}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    cik_map._fetch_json()

    expected_ts = parsedate_to_datetime(last_modified).timestamp()
    assert cik_map._CACHE_PATH.stat().st_mtime == expected_ts


def test_fetch_json_returns_cached_body_on_304(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``urlopen`` raises ``HTTPError(304)``, return parsed cached JSON."""
    import urllib.error
    import urllib.request

    cached_body = b'{"fields": ["cached"], "data": [["from disk"]]}'
    cik_map._CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cik_map._CACHE_PATH.write_bytes(cached_body)

    def fake_urlopen(_req: object, *_a: object, **_k: object) -> None:
        raise urllib.error.HTTPError(
            url=cik_map.settings.edgar_tickers_url,
            code=304,
            msg="Not Modified",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = cik_map._fetch_json()

    assert result == {"fields": ["cached"], "data": [["from disk"]]}


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
