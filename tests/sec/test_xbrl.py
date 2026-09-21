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
    _extract_latest_annual_fact,
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


def test_extract_latest_annual_fact_picks_latest_end_date(aapl_xbrl_fixture: dict) -> None:
    """Latest annual (10-K, FY) fact is picked by ``(end, filed)``, not array order."""
    fact = _extract_latest_annual_fact(aapl_xbrl_fixture, "USD")

    assert fact == ("2024-09-28", 93736000000.0)


def test_extract_latest_annual_fact_skips_newer_non_annual_facts(aapl_xbrl_fixture: dict) -> None:
    """A later-dated 10-Q/quarterly fact must NOT beat an older annual (10-K/FY) one.

    Regression test: SEC's companyconcept API mixes quarterly, year-to-date,
    and annual facts for a concept in the same array. Picking by end-date
    alone (ignoring form/fp) previously returned a 9-month year-to-date
    figure from the newest 10-Q instead of the last full fiscal year.
    """
    payload = json.loads(json.dumps(aapl_xbrl_fixture))  # deep copy
    payload["units"]["USD"].append(
        {
            "end": "2025-06-28",
            "val": 999999999999,
            "fy": 2025,
            "fp": "Q3",
            "form": "10-Q",
            "filed": "2025-08-01",
        }
    )

    fact = _extract_latest_annual_fact(payload, "USD")

    assert fact == ("2024-09-28", 93736000000.0)


def test_extract_latest_annual_fact_empty_units_returns_none() -> None:
    """No facts for the requested unit -> ``None``."""
    assert _extract_latest_annual_fact({"units": {"USD": []}}, "USD") is None
    assert _extract_latest_annual_fact({"units": {}}, "USD") is None


def test_extract_latest_annual_fact_no_annual_facts_returns_none() -> None:
    """Only quarterly/YTD facts on record (no 10-K/FY yet) -> ``None``, not a bogus quarter."""
    payload = {
        "units": {
            "USD": [
                {"end": "2024-03-30", "val": 1.0, "fp": "Q2", "form": "10-Q", "filed": "x"},
            ]
        }
    }

    assert _extract_latest_annual_fact(payload, "USD") is None


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


def test_fetch_revenue_picks_most_recent_fact_across_all_concepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compares every fallback concept's latest annual fact; the most recent wins.

    Regression test: a discontinued tag (e.g. ``Revenues``, last used ~2018
    before ASC 606) can still have *some* annual data. Stopping at the first
    concept with any value would silently return that stale figure instead
    of the current tag's up-to-date one.
    """
    facts_by_concept = {
        "Revenues": ("2018-09-29", 265595000000.0),  # discontinued tag, stale
        "SalesRevenueNet": None,  # even more stale, no annual fact at all
        "RevenueFromContractWithCustomerExcludingAssessedTax": (
            "2025-09-27",
            416161000000.0,
        ),  # current tag
    }

    def fake_fetch(_cik: str, concept: str, _unit: str) -> tuple[str, float] | None:
        return facts_by_concept[concept]

    monkeypatch.setattr(xbrl, "_fetch_latest_annual_fact", fake_fetch)

    value = fetch_revenue("0000320193")

    assert value == 416161000000.0


def test_fetch_revenue_all_concepts_miss_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Foreign filer / no revenue reported under any known tag -> ``None``."""
    monkeypatch.setattr(xbrl, "_fetch_latest_annual_fact", lambda _cik, _concept, _unit: None)

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
