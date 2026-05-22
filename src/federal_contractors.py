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

from src.sec.cik_map import _load_records

if TYPE_CHECKING:
    from src.usaspending import RecipientRecord


def _resolve_candidates(recipients: list[RecipientRecord]) -> list[str]:
    """Cycle-6 RED scaffold — returns empty list."""
    _ = recipients
    return []


def _match_to_edgar(
    recipient_name: str,
    threshold: float = 0.85,
) -> tuple[str | None, float | None]:
    """Fuzzy-match a recipient name against EDGAR titles."""
    target = recipient_name.upper().strip()
    best_ticker: str | None = None
    best_score = 0.0
    for record in _load_records().values():
        score = SequenceMatcher(None, target, record.title.upper().strip()).ratio()
        if score > best_score:
            best_score = score
            best_ticker = record.ticker
    if best_score >= threshold:
        return (best_ticker, best_score)
    return (None, None)
