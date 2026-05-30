"""5s10s US Treasury yield curve via yfinance ^TNX / ^FVX (#165).

Public API:

- :func:`fetch_yield_curve_snapshot` returns the latest
  :class:`YieldCurveSnapshot` (10y minus 5y, percentage points).
- ``python -m src.data_sources.yield_curve`` fetches the latest
  reading and merges it into per-year files at
  ``results/yield_curve/YYYY.json``.

Boundary policy (per ``docs/architecture.md``): yfinance reads are
**wrap-degrade**. A network failure on either leg returns ``None``
for that leg; if both fail the snapshot itself is ``None`` (cron skips
today's write rather than aborting). Slope is computed only when
both legs are present.

Unit shape: ``^TNX`` and ``^FVX`` ship as **percentage points**
(e.g. ``4.453`` = 4.453 % yield). The slope inherits the same unit, so
a positive value means a normal curve (10y > 5y) and a negative value
means inversion. Confirmed via live probe 2026-05-30.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import yfinance as yf
from pydantic import BaseModel, ConfigDict, computed_field
from src.config import settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_TICKER_TNX = "^TNX"
"""yfinance symbol for the CBOE 10-Year Treasury Yield Index."""

_TICKER_FVX = "^FVX"
"""yfinance symbol for the CBOE 5-Year Treasury Yield Index."""


class YieldCurveSnapshot(BaseModel):
    """One day's 5s10s yield curve reading.

    Yields stored as percentage points (matches yfinance raw output).
    ``slope_5s10s`` is a computed field — ``None`` when either leg
    is missing.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    date: date
    tnx_yield: float | None = None
    fvx_yield: float | None = None

    @computed_field
    @property
    def slope_5s10s(self) -> float | None:
        """TNX - FVX in percentage points. ``None`` when a leg is missing."""
        if self.tnx_yield is None or self.fvx_yield is None:
            return None
        return self.tnx_yield - self.fvx_yield


def _fetch_close(symbol: str) -> float | None:
    """Probe a single yield ticker's most-recent ``Close``.

    Wraps yfinance per the wrap-degrade boundary policy: any failure
    or empty response returns ``None`` rather than raising so the
    caller can still surface a partial snapshot.
    """
    try:
        history = yf.Ticker(symbol).history(period="1d")
    except Exception as exc:
        logger.warning("yfinance %s history failed: %s", symbol, exc)
        return None
    if history.empty:
        return None
    return float(history["Close"].iloc[-1])


def fetch_yield_curve_snapshot() -> YieldCurveSnapshot | None:
    """Fetch the latest ``^TNX`` and ``^FVX`` closes and build a snapshot.

    Returns ``None`` only when **both** legs fail (network down, both
    symbols delisted) — a partial reading still yields a snapshot with
    one ``None`` leg and ``slope_5s10s=None`` so the operator can spot
    the gap.
    """
    try:
        tnx = _fetch_close(_TICKER_TNX)
        fvx = _fetch_close(_TICKER_FVX)
    except Exception as exc:
        logger.warning("yield_curve fetch outer wrap: %s", exc)
        return None
    if tnx is None and fvx is None:
        return None
    return YieldCurveSnapshot(
        date=datetime.now(UTC).date(), tnx_yield=tnx, fvx_yield=fvx
    )


def _year_path(year: int, *, root: Path) -> Path:
    return root / f"{year}.json"


def _load_year(year: int, *, root: Path) -> dict[str, YieldCurveSnapshot]:
    """Load a per-year file as a date-keyed dict, empty when missing."""
    path = _year_path(year, root=root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {item["date"][:10]: YieldCurveSnapshot.model_validate(item) for item in raw}


def _write_year(
    year: int, by_date: dict[str, YieldCurveSnapshot], *, root: Path
) -> Path:
    """Write a year's snapshots as a date-sorted JSON array.

    ``exclude_none=True`` keeps each row tight — a row with one leg
    missing omits that field entirely. The computed ``slope_5s10s``
    serialises like a regular field, so reading back is one-shot via
    ``model_validate``.
    """
    root.mkdir(parents=True, exist_ok=True)
    path = _year_path(year, root=root)
    payload = [
        by_date[k].model_dump(mode="json", exclude_none=True) for k in sorted(by_date)
    ]
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def merge_payload_into_years(
    snapshots: list[YieldCurveSnapshot],
    *,
    root: Path = settings.yield_curve_cache_dir,
) -> dict[int, dict[str, YieldCurveSnapshot]]:
    """Merge fresh snapshots onto on-disk per-year files (in memory only).

    Each snapshot routes to its UTC year. Same-date entries are
    replaced — the cron re-fetches every day, and the most-recent
    payload is the authoritative one (yfinance has no intraday
    refresh for these closing-price indices).
    """
    by_year: dict[int, dict[str, YieldCurveSnapshot]] = {}
    for snap in snapshots:
        year = snap.date.year
        if year not in by_year:
            by_year[year] = _load_year(year, root=root)
        by_year[year][snap.date.isoformat()] = snap
    return by_year


def main() -> None:
    """Cron entrypoint: fetch the latest snapshot, merge, persist."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    snap = fetch_yield_curve_snapshot()
    if snap is None:
        logger.warning("yield-curve fetch returned no snapshot; skipping write")
        return
    by_year = merge_payload_into_years([snap])
    for year, by_date in by_year.items():
        path = _write_year(year, by_date, root=settings.yield_curve_cache_dir)
        logger.info("Wrote %s with %d entries", path, len(by_date))


if __name__ == "__main__":
    main()
