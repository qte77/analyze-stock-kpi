"""SPY equity-macro indexed-return series via yfinance (#288).

Derived-only (ADR-0011): this publishes SPY's price as a REBASED INDEX
(``ret_indexed = close / epoch_close * 100``) — never the raw close and never
the S&P 500 index level. SPY is a State Street ETF *security*, so S&P Dow Jones
Indices' index IP does not attach; only Yahoo's ToS applies, mitigated the same
way as the yield_curve slope (derived state, not raw payload).

Public API:

- :func:`index_returns` rebases a ``date -> close`` map to an indexed series
  (earliest close = 100).
- :func:`fetch_equity_spy_history` fetches SPY closes from ``_START`` onward and
  indexes them.
- ``python -m analyze_stock_kpi.data_sources.equity_spy`` recomputes the full
  indexed history and merges it into ``results/series/equity_spy/YYYY.json``.

Boundary policy (per ``docs/architecture.md``): yfinance reads are
**wrap-degrade** — a network failure returns an empty series rather than
raising, so the daily cron skips today's write instead of aborting.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd
import yfinance as yf
from pydantic import BaseModel, ConfigDict

from analyze_stock_kpi.config import settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_TICKER_SPY = "SPY"
"""yfinance symbol for the SPDR S&P 500 ETF (a State Street security)."""

_START = date(2011, 1, 1)
"""Series start. SPY history reaches 1993, but the series aligns to ~2011 so the
merged long-term chart's windows line up with the cnn_fg / yield_curve series.
The rebase epoch is the first SPY close on or after this date."""


class EquitySpySnapshot(BaseModel):
    """One day's SPY reading as a rebased index (earliest in series = 100).

    Derived-only: carries ``ret_indexed``, never the raw close.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    date: date
    ret_indexed: float


def index_returns(closes: dict[date, float]) -> list[EquitySpySnapshot]:
    """Rebase a ``date -> close`` map to an indexed series (earliest = 100).

    ``ret_indexed = close / epoch_close * 100`` where ``epoch_close`` is the
    close on the earliest date. Snapshots come back ascending by date. An empty
    map — or a non-positive epoch close, which can't form a ratio — returns an
    empty list.
    """
    if not closes:
        return []
    epoch_close = closes[min(closes)]
    if epoch_close <= 0:
        logger.warning("equity_spy epoch close %.4f is non-positive; skipping", epoch_close)
        return []
    return [
        EquitySpySnapshot(date=d, ret_indexed=closes[d] / epoch_close * 100.0)
        for d in sorted(closes)
    ]


def _fetch_history_closes(symbol: str, period: str) -> dict[date, float]:
    """Date-indexed ``Close`` map for ``symbol`` over ``period``.

    Wrap-degrades to ``{}`` on any failure. Mirrors the yield_curve fetch helper
    (NaN-drop + Timestamp guard); now that there are two consumers a shared
    yfinance-history util could absorb both — deferred (AHA) to keep this PR
    focused.
    """
    try:
        history = yf.Ticker(symbol).history(period=period)
    except Exception as exc:
        logger.warning("yfinance %s history(%s) failed: %s", symbol, period, exc)
        return {}
    if history.empty:
        return {}
    out: dict[date, float] = {}
    for ts, row in history.iterrows():
        if not isinstance(ts, pd.Timestamp):
            continue
        close = row.get("Close")
        if close is None:
            continue
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        # pandas turns None / NA into NaN in numeric columns — drop those rows.
        if value != value:
            continue
        out[ts.date()] = value
    return out


def fetch_equity_spy_history(period: str = "max") -> list[EquitySpySnapshot]:
    """Fetch SPY closes from ``_START`` onward and rebase to an indexed series."""
    closes = _fetch_history_closes(_TICKER_SPY, period)
    windowed = {d: c for d, c in closes.items() if d >= _START}
    return index_returns(windowed)


def _year_path(year: int, *, root: Path) -> Path:
    return root / f"{year}.json"


def _load_year(year: int, *, root: Path) -> dict[str, EquitySpySnapshot]:
    """Load a per-year file as a date-keyed dict, empty when missing."""
    path = _year_path(year, root=root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {item["date"][:10]: EquitySpySnapshot.model_validate(item) for item in raw}


def _write_year(year: int, by_date: dict[str, EquitySpySnapshot], *, root: Path) -> Path:
    """Write a year's snapshots as a date-sorted JSON array."""
    root.mkdir(parents=True, exist_ok=True)
    path = _year_path(year, root=root)
    payload = [by_date[k].model_dump(mode="json") for k in sorted(by_date)]
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def merge_payload_into_years(
    snapshots: list[EquitySpySnapshot],
    *,
    root: Path = settings.equity_spy_cache_dir,
) -> dict[int, dict[str, EquitySpySnapshot]]:
    """Merge fresh snapshots onto on-disk per-year files (in memory only).

    Each snapshot routes to its UTC year; same-date entries are replaced.
    """
    by_year: dict[int, dict[str, EquitySpySnapshot]] = {}
    for snap in snapshots:
        year = snap.date.year
        if year not in by_year:
            by_year[year] = _load_year(year, root=root)
        by_year[year][snap.date.isoformat()] = snap
    return by_year


def main() -> None:
    """Cron entrypoint: recompute the full indexed history and persist.

    The rebase epoch (first SPY close >= ``_START``) is stable, so re-running is
    idempotent for prior years — only the current year gains today's row. No
    first-run branch is needed (unlike yield_curve): the full series is always
    recomputed from one ``period="max"`` fetch.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    snaps = fetch_equity_spy_history(period="max")
    if not snaps:
        logger.warning("equity-spy history fetch empty; nothing to write")
        return
    by_year = merge_payload_into_years(snaps)
    for year, by_date in sorted(by_year.items()):
        path = _write_year(year, by_date, root=settings.equity_spy_cache_dir)
        logger.info("Wrote %s with %d entries", path, len(by_date))


if __name__ == "__main__":
    main()
