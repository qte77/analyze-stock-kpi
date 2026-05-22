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


def _normalise_name(name: str) -> str:
    """Upper-case + strip + collapse common legal-entity suffixes."""
    normalised = name.upper().strip()
    for long, short in _SUFFIX_NORMALISATIONS:
        if normalised.endswith(long):
            normalised = normalised[: -len(long)] + short
            break
    return normalised


def _smoke_test_yfinance(tickers: list[str]) -> list[str]:
    """Cycle-7 RED scaffold — returns empty list."""
    _ = tickers
    return []


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
