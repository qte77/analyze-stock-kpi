"""SEC XBRL cross-validation of yfinance fundamentals.

SEC's XBRL "companyconcept" API returns per-concept US-GAAP facts for
one filer:
``data.sec.gov/api/xbrl/companyconcept/CIK<10>/us-gaap/<concept>.json``.
Each response's ``units.<unit>`` array holds one entry per reporting
period; we take the most-recent fact (max by ``(end, filed)``) as the
authoritative SEC value.

Cross-validates three yfinance-derived
:class:`analyze_stock_kpi.data_sources.fundamentals.FundamentalsSnapshot`
fields — ``total_revenue``, ``net_income_to_common``, ``trailing_eps``
— against their SEC XBRL counterparts and attaches the relative delta
(``(yfinance - sec) / sec``) as ``sec_*_delta_pct`` fields. Revenue
falls back across three concept names because filers report it under
different US-GAAP tags depending on filing vintage / ASC 606 adoption.

Foreign filers (Form 20-F / IFRS) report no ``us-gaap`` concepts, so
every :func:`fetch_xbrl_concept` call 404s and all three delta fields
stay ``None`` — same "skip gracefully" behaviour as
:mod:`analyze_stock_kpi.data_sources.sec.submissions`.

Public API:

- :func:`fetch_xbrl_concept` — GET one concept's latest value.
- :func:`fetch_revenue` / :func:`fetch_net_income` / :func:`fetch_eps`
  — concept-specific convenience wrappers.
- :func:`enrich_snapshot_xbrl` — orchestrator: resolve CIK, fetch the
  three concepts, compute deltas against the snapshot's yfinance
  values, and return the enrichment dict for
  ``model_copy(update=...)``.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.sec.cik_map import resolve_cik
from analyze_stock_kpi.utils.http_ua import require_https

if TYPE_CHECKING:
    from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot

logger = logging.getLogger(__name__)

_REVENUE_CONCEPTS = (
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
)
"""Fallback chain — filers report revenue under different US-GAAP tags
depending on filing vintage / ASC 606 adoption; first hit wins."""


def fetch_xbrl_concept(cik: str, concept: str, unit: str = "USD") -> float | None:
    """GET SEC XBRL ``companyconcept`` for ``concept``; latest value by period end.

    Returns ``None`` when the filer hasn't reported ``concept`` (404 —
    not an error, e.g. a non-US-GAAP or foreign filer) or when
    ``units[unit]`` is empty. Any other HTTP error propagates.
    """
    url = settings.edgar_xbrl_url_template.format(cik=cik.zfill(10), concept=concept)
    # S310 / B310: URL is built from an HTTPS template plus a zero-padded
    # CIK and a concept name from the fixed tuples in this module; the
    # explicit scheme check below is defense-in-depth for any future
    # refactor that might let external input flow into it.
    request = urllib.request.Request(  # noqa: S310  # nosec B310
        url,
        headers={
            "User-Agent": settings.sec_user_agent,
            "Accept": settings.http_accept,
            "Referer": settings.sec_referer,
        },
    )
    require_https(request.full_url)
    try:
        with urllib.request.urlopen(  # noqa: S310  # nosec B310
            request, timeout=settings.request_timeout_sec
        ) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return _extract_latest_value(payload, unit)


def _extract_latest_value(payload: dict, unit: str) -> float | None:
    """Pick the fact with the latest ``(end, filed)`` from one units array."""
    facts = payload.get("units", {}).get(unit, [])
    if not facts:
        return None
    latest = max(facts, key=lambda fact: (fact["end"], fact.get("filed", "")))
    return float(latest["val"])


def fetch_revenue(cik: str) -> float | None:
    """Latest revenue, trying each concept in :data:`_REVENUE_CONCEPTS` in order."""
    for concept in _REVENUE_CONCEPTS:
        value = fetch_xbrl_concept(cik, concept)
        if value is not None:
            return value
    return None


def fetch_net_income(cik: str) -> float | None:
    """Latest ``NetIncomeLoss``."""
    return fetch_xbrl_concept(cik, "NetIncomeLoss")


def fetch_eps(cik: str) -> float | None:
    """Latest basic EPS — ``USD/shares`` unit, not ``USD``."""
    return fetch_xbrl_concept(cik, "EarningsPerShareBasic", unit="USD/shares")


def _delta_pct(yf_value: float | None, sec_value: float | None) -> float | None:
    """Relative delta ``(yf - sec) / sec``; ``None`` if either operand is missing or sec is 0."""
    if yf_value is None or sec_value is None or sec_value == 0:
        return None
    return (yf_value - sec_value) / sec_value


def enrich_snapshot_xbrl(snap: FundamentalsSnapshot) -> dict:
    """Return ``FundamentalsSnapshot`` XBRL cross-validation fields for ``snap``.

    Resolves ``snap.symbol`` to a CIK; if no CIK (FX, crypto, futures,
    or non-SEC equity), returns ``{}`` and does NOT call EDGAR.

    Network / HTTP errors from the XBRL fetch are logged as warnings
    and degrade to ``{}`` so one ticker's failure doesn't kill the
    whole universe run (wrap-degrade per ``docs/architecture.md``).
    """
    cik = resolve_cik(snap.symbol)
    if not cik:
        return {}
    try:
        sec_revenue = fetch_revenue(cik)
        sec_net_income = fetch_net_income(cik)
        sec_eps = fetch_eps(cik)
    except urllib.error.URLError as exc:
        logger.warning("SEC XBRL fetch failed for %s (CIK %s): %s", snap.symbol, cik, exc)
        return {}
    return {
        "sec_revenue_delta_pct": _delta_pct(snap.total_revenue, sec_revenue),
        "sec_net_income_delta_pct": _delta_pct(snap.net_income_to_common, sec_net_income),
        "sec_eps_delta_pct": _delta_pct(snap.trailing_eps, sec_eps),
    }
