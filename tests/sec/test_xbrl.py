"""Tests for :mod:`analyze_stock_kpi.data_sources.sec.xbrl` — XBRL companyconcept crossval."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

import pytest

from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot
from analyze_stock_kpi.data_sources.sec import xbrl
from analyze_stock_kpi.data_sources.sec.xbrl import (
    _delta_pct,
    _extract_latest_value,
    enrich_snapshot_xbrl,
    fetch_eps,
    fetch_revenue,
    fetch_xbrl_concept,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def aapl_xbrl_fixture() -> dict:
    """AAPL companyconcept fixture — ``units.USD`` with 3 facts, distinct ``end`` dates."""
    return json.loads((_FIXTURES_DIR / "aapl_xbrl_companyconcept.json").read_text())


@pytest.fixture
def aapl_xbrl_eps_fixture() -> dict:
    """AAPL companyconcept fixture — ``units["USD/shares"]``, 2 facts."""
    return json.loads((_FIXTURES_DIR / "aapl_xbrl_eps.json").read_text())


def test_extract_latest_value_picks_latest_end_date(aapl_xbrl_fixture: dict) -> None:
    """Latest fact is picked by ``(end, filed)``, not array order."""
    value = _extract_latest_value(aapl_xbrl_fixture, "USD")

    assert value == 93736000000.0


def test_extract_latest_value_empty_units_returns_none() -> None:
    """No facts for the requested unit -> ``None``."""
    assert _extract_latest_value({"units": {"USD": []}}, "USD") is None
    assert _extract_latest_value({"units": {}}, "USD") is None


def test_fetch_xbrl_concept_sends_correct_url_and_headers(
    monkeypatch: pytest.MonkeyPatch,
    aapl_xbrl_fixture: dict,
) -> None:
    """GET companyconcept/CIK<10>/us-gaap/<concept>.json with UA + Accept + Referer."""
    expected_url = (
        "https://data.sec.gov/api/xbrl/companyconcept/"
        "CIK0000320193/us-gaap/NetIncomeLoss.json"
    )
    captured: dict[str, urllib.request.Request] = {}

    def fake_urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> BytesIO:
        captured["req"] = req
        return BytesIO(json.dumps(aapl_xbrl_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_xbrl_concept("0000320193", "NetIncomeLoss")

    req = captured["req"]
    assert req.full_url == expected_url
    assert req.get_header("User-agent") == xbrl.settings.sec_user_agent
    assert req.get_header("Accept") == "application/json, text/plain, */*"
    assert req.get_header("Referer") == "https://www.sec.gov/"


def test_fetch_xbrl_concept_zero_pads_short_cik(
    monkeypatch: pytest.MonkeyPatch,
    aapl_xbrl_fixture: dict,
) -> None:
    """A short CIK (``"320193"``) must be left-zero-padded to 10 digits in the URL."""
    captured: dict[str, str] = {}

    def fake_urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> BytesIO:
        captured["url"] = req.full_url
        return BytesIO(json.dumps(aapl_xbrl_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_xbrl_concept("320193", "NetIncomeLoss")

    assert captured["url"] == (
        "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/NetIncomeLoss.json"
    )


def test_fetch_xbrl_concept_404_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A filer that never reported ``concept`` -> 404 -> ``None``, not an error."""

    def raising_404(_req: object, *args: object, **kwargs: object) -> BytesIO:
        raise urllib.error.HTTPError(
            url="https://data.sec.gov/", code=404, msg="Not Found", hdrs=None, fp=None
        )

    monkeypatch.setattr(urllib.request, "urlopen", raising_404)

    assert fetch_xbrl_concept("0000320193", "Revenues") is None


def test_fetch_xbrl_concept_non_404_http_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-404 HTTP error (e.g. 503) is not swallowed."""

    def raising_503(_req: object, *args: object, **kwargs: object) -> BytesIO:
        raise urllib.error.HTTPError(
            url="https://data.sec.gov/", code=503, msg="Service Unavailable", hdrs=None, fp=None
        )

    monkeypatch.setattr(urllib.request, "urlopen", raising_503)

    with pytest.raises(urllib.error.HTTPError):
        fetch_xbrl_concept("0000320193", "Revenues")


def test_fetch_revenue_fallback_chain_short_circuits_at_first_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First concept that returns a value wins; later concepts are never fetched."""
    calls: list[str] = []

    def fake_fetch(_cik: str, concept: str, unit: str = "USD") -> float | None:
        calls.append(concept)
        return None if concept == "Revenues" else 100.0

    monkeypatch.setattr(xbrl, "fetch_xbrl_concept", fake_fetch)

    value = fetch_revenue("0000320193")

    assert value == 100.0
    assert calls == ["Revenues", "SalesRevenueNet"]


def test_fetch_revenue_all_concepts_miss_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Foreign filer / no revenue reported under any known tag -> ``None``."""
    monkeypatch.setattr(xbrl, "fetch_xbrl_concept", lambda _cik, _concept, unit="USD": None)

    assert fetch_revenue("0000320193") is None


def test_fetch_eps_uses_usd_per_shares_unit(
    monkeypatch: pytest.MonkeyPatch,
    aapl_xbrl_eps_fixture: dict,
) -> None:
    """EPS concept is fetched with the ``USD/shares`` unit, not ``USD``."""

    def fake_urlopen(_req: object, *args: object, **kwargs: object) -> BytesIO:
        return BytesIO(json.dumps(aapl_xbrl_eps_fixture).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    value = fetch_eps("0000320193")

    assert value == 6.11


@pytest.mark.parametrize(
    ("yf_value", "sec_value"),
    [
        pytest.param(10.0, 0.0, id="zero-sec-value"),
        pytest.param(None, 10.0, id="missing-yf"),
        pytest.param(10.0, None, id="missing-sec"),
    ],
)
def test_delta_pct_returns_none_for_undefined_ratio(
    yf_value: float | None, sec_value: float | None
) -> None:
    """Missing operand or zero denominator -> ``None``, never ``ZeroDivisionError``."""
    assert _delta_pct(yf_value, sec_value) is None


def test_delta_pct_computes_relative_difference() -> None:
    """``(yf - sec) / sec`` — yfinance 10% above the SEC figure."""
    assert _delta_pct(110.0, 100.0) == pytest.approx(0.1)


def test_enrich_snapshot_xbrl_computes_deltas_for_sec_registered_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CIK resolves -> three delta fields computed from snapshot + SEC values."""
    snap = FundamentalsSnapshot(
        symbol="AAPL",
        total_revenue=110.0,
        net_income_to_common=55.0,
        trailing_eps=6.0,
    )
    monkeypatch.setattr(xbrl, "resolve_cik", lambda _symbol: "0000320193")
    monkeypatch.setattr(xbrl, "fetch_revenue", lambda _cik: 100.0)
    monkeypatch.setattr(xbrl, "fetch_net_income", lambda _cik: 50.0)
    monkeypatch.setattr(xbrl, "fetch_eps", lambda _cik: 5.0)

    result = enrich_snapshot_xbrl(snap)

    assert result == {
        "sec_revenue_delta_pct": pytest.approx(0.1),
        "sec_net_income_delta_pct": pytest.approx(0.1),
        "sec_eps_delta_pct": pytest.approx(0.2),
    }


def test_enrich_snapshot_xbrl_no_cik_returns_empty_no_fetch_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-SEC-registered symbols return ``{}`` and skip the XBRL fetch."""
    fetch_call_count = 0

    def counting_fetch(_cik: str) -> float | None:
        nonlocal fetch_call_count
        fetch_call_count += 1
        return None

    monkeypatch.setattr(xbrl, "resolve_cik", lambda _symbol: None)
    monkeypatch.setattr(xbrl, "fetch_revenue", counting_fetch)
    monkeypatch.setattr(xbrl, "fetch_net_income", counting_fetch)
    monkeypatch.setattr(xbrl, "fetch_eps", counting_fetch)

    snap = FundamentalsSnapshot(symbol="BTC-USD")

    assert enrich_snapshot_xbrl(snap) == {}
    assert fetch_call_count == 0


def test_enrich_snapshot_xbrl_url_error_degrades_to_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Network/HTTP error from any of the three fetches -> ``{}``, snapshot survives."""

    def raising_fetch(_cik: str) -> float | None:
        raise urllib.error.URLError("net")

    monkeypatch.setattr(xbrl, "resolve_cik", lambda _symbol: "0000320193")
    monkeypatch.setattr(xbrl, "fetch_revenue", raising_fetch)

    snap = FundamentalsSnapshot(symbol="AAPL")

    assert enrich_snapshot_xbrl(snap) == {}


@pytest.mark.network
def test_fetch_revenue_live_aapl_returns_a_value() -> None:
    """End-to-end against real EDGAR XBRL — AAPL must report a revenue concept."""
    value = fetch_revenue("0000320193")

    assert value is not None
    assert value > 0
