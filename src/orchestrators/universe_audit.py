"""Universe audit orchestrator (#168).

Walks bundled-preset universes (``src/assets/universes/*.txt``) and
classifies each ticker against ``yfinance.Ticker(sym).info`` field
density. Emits a structured :class:`UniverseAuditReport` for an
operator to triage — surfaces stale-US-ticker rot (FI→FISV, RY→RY.TO,
SUEZY→SZU.DE patterns from the post-#159 sweep) without writing any
authoritative data.

Tier: this is repo-infrastructure tooling (ADR-0007 Scope 2) — output
lands under ``results/audit/`` via :mod:`scripts.audit_universes`, not
the public ``data`` branch. The orchestrator itself is I/O-free; only
the script writes.

Boundary policy: ``classify_ticker``'s yfinance call is **wrap-degrade**
— network failure or unexpected yfinance exception produces a ``FAIL``
entry with the exception message in ``note``, never raises.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yfinance as yf
from pydantic import BaseModel, ConfigDict
from src.domain.universe import PRESET_DIR

Classification = Literal["OK", "SPARSE", "FAIL"]

OK_THRESHOLD = 40
"""Populated-field count at or above which a ticker classifies as ``OK``.
40 sits comfortably above the ~12-field bands yfinance emits for
delisted / migrated tickers and well below the 80+ a healthy equity
returns. Tweak if false-positive ``SPARSE`` rate climbs."""


class AuditEntry(BaseModel):
    """One ticker's classification result."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    symbol: str
    classification: Classification
    fields_populated: int | None = None
    note: str | None = None


class UniverseAuditReport(BaseModel):
    """Per-universe entry lists + a UTC stamp for traceability."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    generated_at: datetime
    entries_by_universe: dict[str, list[AuditEntry]]


def classify_ticker(symbol: str) -> AuditEntry:
    """Probe ``yfinance.Ticker(symbol).info`` once and classify."""
    try:
        info = yf.Ticker(symbol).info
    except Exception as exc:  # noqa: BLE001 — wrap-degrade boundary
        return AuditEntry(
            symbol=symbol, classification="FAIL", note=str(exc) or repr(exc)
        )

    if not info:
        return AuditEntry(symbol=symbol, classification="FAIL", fields_populated=0)

    populated = sum(1 for v in info.values() if v is not None and v != "")
    classification: Classification = "OK" if populated >= OK_THRESHOLD else "SPARSE"
    return AuditEntry(
        symbol=symbol, classification=classification, fields_populated=populated
    )


def audit_universes(
    universe_ids: Iterable[str] | None = None,
) -> UniverseAuditReport:
    """Classify every ticker in every requested universe.

    ``universe_ids=None`` walks every bundled preset under
    :data:`src.domain.universe.PRESET_DIR`. Each id resolves to
    ``<PRESET_DIR>/<id>.txt`` and is parsed with the same comment-and-
    blank-line rules as :mod:`src.domain.universe`.
    """
    ids = list(universe_ids) if universe_ids is not None else _bundled_universe_ids()
    entries_by_universe: dict[str, list[AuditEntry]] = {}
    for universe_id in ids:
        tickers = _read_universe(universe_id)
        entries_by_universe[universe_id] = [classify_ticker(t) for t in tickers]
    return UniverseAuditReport(
        generated_at=datetime.now(UTC),
        entries_by_universe=entries_by_universe,
    )


def _bundled_universe_ids() -> list[str]:
    return sorted(p.stem for p in PRESET_DIR.glob("*.txt"))


def _read_universe(universe_id: str) -> list[str]:
    path = Path(PRESET_DIR) / f"{universe_id}.txt"
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    cleaned: list[str] = []
    for line in raw_lines:
        token = line.split("#", 1)[0].strip()
        if token:
            cleaned.append(token)
    return cleaned
