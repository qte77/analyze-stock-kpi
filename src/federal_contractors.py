"""Federal-contractors universe orchestrator.

Chains :mod:`src.usaspending` → :mod:`src.sec.cik_map` → yfinance
smoke-test to produce a list of publicly-traded contractor tickers
plus a per-candidate :class:`AuditRow` trail. See
``docs/data-sources.md`` (Redistribution guardrails section) for the
ToS rule that bars persisting any ``fast_info`` / ``info`` payload —
the audit row carries only ticker symbol + resolution boolean.
"""

from __future__ import annotations

from src.sec.cik_map import _load_records


def _match_to_edgar(
    recipient_name: str,
    threshold: float = 0.85,
) -> tuple[str | None, float | None]:
    """Fuzzy-match a recipient name against EDGAR titles."""
    _ = _load_records()  # cycle-5 RED scaffold: not wired yet
    _ = recipient_name, threshold
    return (None, None)
