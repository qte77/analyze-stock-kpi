"""Federal-contractors universe orchestrator.

Chains :mod:`src.usaspending` → :mod:`src.sec.cik_map` → yfinance
smoke-test to produce a list of publicly-traded contractor tickers
plus a per-candidate :class:`AuditRow` trail. See
``docs/data-sources.md`` (Redistribution guardrails section) for the
ToS rule that bars persisting any ``fast_info`` / ``info`` payload —
the audit row carries only ticker symbol + resolution boolean.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

import yfinance as yf
from src.sec.cik_map import _load_records

if TYPE_CHECKING:
    from src.usaspending import RecipientRecord


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


def _ensure_seed(tickers: list[str]) -> list[str]:
    """Cycle-8 RED scaffold — returns input unchanged (no seed added)."""
    return list(tickers)


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
