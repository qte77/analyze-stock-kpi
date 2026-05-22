"""Federal-contractors universe orchestrator.

Chains :mod:`src.usaspending` → :mod:`src.sec.cik_map` → yfinance
smoke-test to produce a list of publicly-traded contractor tickers
plus a per-candidate :class:`AuditRow` trail. See
``docs/data-sources.md`` (Redistribution guardrails section) for the
ToS rule that bars persisting any ``fast_info`` / ``info`` payload —
the audit row carries only ticker symbol + resolution boolean.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

import yfinance as yf
from pydantic import BaseModel, ConfigDict
from src.sec.cik_map import _load_records
from src.usaspending import RecipientRecord, fetch_top_contractors

if TYPE_CHECKING:
    pass


class AuditRow(BaseModel):
    """Decision-trail entry per usaspending recipient processed in build_universe."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rank: int
    recipient_name: str
    uei: str | None = None
    obligated_usd: float
    candidate_ticker: str | None = None
    edgar_match_score: float | None = None
    yfinance_resolves: bool = False
    final_ticker: str | None = None
    note: str | None = None


# SAM / usaspending names use long-form legal suffixes ("CORPORATION",
# "INCORPORATED"); EDGAR titles use the short forms ("Corp", "Inc").
# Normalising both sides before fuzzy match lifts borderline pairs above
# the 0.85 SequenceMatcher threshold without inviting noise matches.
_SUFFIX_NORMALISATIONS: tuple[tuple[str, str], ...] = (
    (" LIMITED LIABILITY COMPANY", " LLC"),
    (" CORPORATION", " CORP"),
    (" INCORPORATED", " INC"),
    (" COMPANY", " CO"),
    (" LIMITED", " LTD"),
)


# DoD Top-25 Publicly-Traded Prime Contractors + ICF (verified
# 2026-05-20 against docs/data-sources.md lines 440-478). Hand-curated
# seed — always included in the federal-contractors universe so a
# transient usaspending API gap (a missing contractor this week) does
# not silently drop the obvious primes from the preset.
CURATED_TICKERS: tuple[tuple[str, str], ...] = (
    ("LOCKHEED MARTIN CORPORATION", "LMT"),
    ("RTX CORPORATION", "RTX"),
    ("NORTHROP GRUMMAN CORPORATION", "NOC"),
    ("GENERAL DYNAMICS CORPORATION", "GD"),
    ("THE BOEING COMPANY", "BA"),
    ("L3HARRIS TECHNOLOGIES INC", "LHX"),
    ("HUNTINGTON INGALLS INDUSTRIES INC", "HII"),
    ("LEIDOS INC", "LDOS"),
    ("BOOZ ALLEN HAMILTON INC", "BAH"),
    ("SCIENCE APPLICATIONS INTERNATIONAL CORPORATION", "SAIC"),
    ("CACI INTERNATIONAL INC", "CACI"),
    ("KBR INC", "KBR"),
    ("TEXTRON INC", "TXT"),
    ("OSHKOSH DEFENSE LLC", "OSK"),
    ("GENERAL ELECTRIC COMPANY", "GE"),
    ("HONEYWELL INTERNATIONAL INC", "HON"),
    ("FLUOR CORPORATION", "FLR"),
    ("JACOBS SOLUTIONS INC", "J"),
    ("DELL TECHNOLOGIES INC", "DELL"),
    ("ACCENTURE FEDERAL SERVICES LLC", "ACN"),
    ("PALANTIR TECHNOLOGIES INC", "PLTR"),
    ("MICROSOFT CORPORATION", "MSFT"),
    ("AMAZON WEB SERVICES INC", "AMZN"),
    ("BAE SYSTEMS", "BAESY"),
    ("MAXIMUS FEDERAL SERVICES INC", "MMS"),
    ("ICF INCORPORATED LLC", "ICFI"),
)


def _last_completed_fy_window(today: date | None = None) -> tuple[date, date]:
    """Return (start, end) of the most recently completed US federal FY.

    US FY runs Oct 1 -> Sep 30 (named by the year it ends, so FY2025
    = Oct 1 2024 -> Sep 30 2025). On any day in Q4 of the calendar
    year (Oct-Dec), the current FY ends in the following calendar
    year; in Q1-Q3 (Jan-Sep), the current FY ends in the current
    calendar year. Last-completed = current minus one.
    """
    today = today or datetime.now(UTC).date()
    current_fy_end_year = today.year + 1 if today.month >= 10 else today.year
    completed_fy_end_year = current_fy_end_year - 1
    return (
        date(completed_fy_end_year - 1, 10, 1),
        date(completed_fy_end_year, 9, 30),
    )


def _ensure_seed(tickers: list[str]) -> list[str]:
    """Append CURATED tickers not already in ``tickers``; preserve input order."""
    seen = set(tickers)
    result = list(tickers)
    for _, ticker in CURATED_TICKERS:
        if ticker not in seen:
            result.append(ticker)
            seen.add(ticker)
    return result


def _normalise_name(name: str) -> str:
    """Upper-case + strip + collapse common legal-entity suffixes."""
    normalised = name.upper().strip()
    for long, short in _SUFFIX_NORMALISATIONS:
        if normalised.endswith(long):
            normalised = normalised[: -len(long)] + short
            break
    return normalised


def _smoke_test_yfinance(tickers: list[str]) -> list[str]:
    """Drop tickers whose yfinance ``fast_info`` is empty/falsy."""
    return [t for t in tickers if yf.Ticker(t).fast_info]


def _resolve_candidates(recipients: list[RecipientRecord]) -> list[str]:
    """Map recipients to EDGAR tickers, dedupe to one entry per ticker."""
    seen: set[str] = set()
    tickers: list[str] = []
    for recipient in recipients:
        ticker, _score = _match_to_edgar(recipient.name)
        if ticker is None or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def _match_to_edgar(
    recipient_name: str,
    threshold: float = 0.85,
) -> tuple[str | None, float | None]:
    """Fuzzy-match a recipient name against EDGAR titles."""
    target = _normalise_name(recipient_name)
    best_ticker: str | None = None
    best_score = 0.0
    for record in _load_records().values():
        score = SequenceMatcher(None, target, _normalise_name(record.title)).ratio()
        if score > best_score:
            best_score = score
            best_ticker = record.ticker
    if best_score >= threshold:
        return (best_ticker, best_score)
    return (None, None)


def build_universe(
    *,
    fy: int | None = None,
    top_n: int = 100,
) -> tuple[list[str], list[AuditRow]]:
    """Cycle-12 RED scaffold — returns empty tuple."""
    _ = fy, top_n
    return ([], [])
