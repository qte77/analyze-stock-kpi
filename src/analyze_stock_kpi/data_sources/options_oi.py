"""SPY option open-interest levels via yfinance (plan 011).

Derived-only on the public side: per collection day and expiry kind (``nearest``
and ``monthly``) this publishes max pain, call wall, put floor, the put/call OI
ratio, total OI and the null-OI share — never the raw chain, quotes or the spot
price. Raw chains (strike, openInterest, impliedVolatility per contract) are
written only under ``settings.backtest_prices_cache_dir / "options" / "SPY"``,
which is gitignored and saved to the private cache repo, never the ``data`` branch.

Public API:

- :func:`collect_options_oi` fetches the two expiries' chains and derives the rows.
- ``python -m analyze_stock_kpi.data_sources.options_oi`` collects for today (UTC)
  and merges the rows into ``results/series/options_oi/YYYY.json``.

Boundary policy (per ``docs/architecture.md``): yfinance reads are **wrap-degrade**
— any failure yields no rows rather than raising, so the cron skips the write.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd
import yfinance as yf
from pydantic import BaseModel, ConfigDict

from analyze_stock_kpi.config import settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_TICKER_SPY = "SPY"
_FRIDAY = 4
_THURSDAY = 3
_THIRD_FRIDAY_DAYS = range(15, 22)
_CHAIN_COLUMNS = ("strike", "openInterest", "impliedVolatility")

ExpiryKind = Literal["nearest", "monthly"]
Chain = dict[str, list[dict[str, float | None]]]
"""Raw chain for one expiry: ``{"calls": [...], "puts": [...]}`` of contract records."""


class OptionsOiRow(BaseModel):
    """One day's OI levels for one expiry kind. Level fields are None on zero OI."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    date: date
    expiry_kind: ExpiryKind
    expiry: date
    max_pain: float | None
    call_wall: float | None
    put_floor: float | None
    pc_oi_ratio: float | None
    total_oi: int
    oi_null_share: float


# ----- expiry selection -----


def _is_third_friday(day: date) -> bool:
    return day.weekday() == _FRIDAY and day.day in _THIRD_FRIDAY_DAYS


def _is_monthly(day: date, listed: set[date]) -> bool:
    """Third Friday, or the Thursday before it when that Friday is not listed (holiday)."""
    if _is_third_friday(day):
        return True
    friday = day + timedelta(days=1)
    return day.weekday() == _THURSDAY and _is_third_friday(friday) and friday not in listed


def pick_expiries(listed: list[date], today: date) -> dict[ExpiryKind, date]:
    """Pick the nearest and the monthly expiry on or after ``today`` (may coincide)."""
    upcoming = sorted(d for d in listed if d >= today)
    out: dict[ExpiryKind, date] = {}
    if upcoming:
        out["nearest"] = upcoming[0]
    listed_set = set(listed)
    monthly = next((d for d in upcoming if _is_monthly(d, listed_set)), None)
    if monthly is not None:
        out["monthly"] = monthly
    return out


# ----- level derivation -----


def _records(frame: pd.DataFrame) -> list[dict[str, float | None]]:
    """Contract records with NaN mapped to None (JSON-safe); missing columns -> None."""
    out: list[dict[str, float | None]] = []
    for _, row in frame.iterrows():
        rec: dict[str, float | None] = {}
        for col in _CHAIN_COLUMNS:
            value = row.get(col)
            rec[col] = None if value is None or pd.isna(value) else float(value)
        out.append(rec)
    return out


def _oi_by_strike(records: list[dict[str, float | None]]) -> dict[float, int]:
    """Strike -> OI, null OI counted as 0."""
    out: dict[float, int] = {}
    for rec in records:
        strike = rec["strike"]
        if strike is None:
            continue
        out[strike] = out.get(strike, 0) + int(rec["openInterest"] or 0)
    return out


def _argmax_lowest(oi: dict[float, int]) -> float | None:
    """Strike with the largest OI (ties -> lowest); None when that OI is 0."""
    if not oi:
        return None
    strike = max(sorted(oi), key=lambda k: oi[k])
    return strike if oi[strike] > 0 else None


def _max_pain(calls: dict[float, int], puts: dict[float, int]) -> float | None:
    """Strike minimising total intrinsic payout to holders (ties -> lowest)."""
    strikes = sorted(set(calls) | set(puts))
    if not strikes:
        return None

    def payout(k: float) -> float:
        return sum(o * max(0.0, k - s) for s, o in calls.items()) + sum(
            o * max(0.0, s - k) for s, o in puts.items()
        )

    return min(strikes, key=payout)


def build_row(
    day: date, kind: ExpiryKind, expiry: date, chain: Chain
) -> OptionsOiRow:
    """Derive one row from a raw chain; level fields are None when total OI is 0."""
    calls, puts = chain["calls"], chain["puts"]
    contracts = calls + puts
    nulls = sum(1 for r in contracts if r["openInterest"] is None)
    null_share = nulls / len(contracts) if contracts else 0.0
    call_oi, put_oi = _oi_by_strike(calls), _oi_by_strike(puts)
    total_calls, total_puts = sum(call_oi.values()), sum(put_oi.values())
    total = total_calls + total_puts
    has_oi = total > 0
    return OptionsOiRow(
        date=day,
        expiry_kind=kind,
        expiry=expiry,
        max_pain=_max_pain(call_oi, put_oi) if has_oi else None,
        call_wall=_argmax_lowest(call_oi) if has_oi else None,
        put_floor=_argmax_lowest(put_oi) if has_oi else None,
        pc_oi_ratio=total_puts / total_calls if has_oi and total_calls else None,
        total_oi=total,
        oi_null_share=null_share,
    )


# ----- fetch (wrap-degrade) -----


def collect_options_oi(
    day: date, symbol: str = _TICKER_SPY
) -> tuple[list[OptionsOiRow], dict[str, Chain]]:
    """Fetch chains for the nearest + monthly expiry and derive the rows.

    Returns ``(rows, raw)`` where ``raw`` maps expiry ISO date -> raw chain (private
    cache payload only). Wrap-degrades to ``([], {})`` on any yfinance failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        listed = [date.fromisoformat(e) for e in ticker.options]
        picks = pick_expiries(listed, day)
        raw: dict[str, Chain] = {}
        for expiry in sorted(set(picks.values())):
            chain = ticker.option_chain(expiry.isoformat())
            raw[expiry.isoformat()] = {
                "calls": _records(chain.calls),
                "puts": _records(chain.puts),
            }
    except Exception as exc:
        logger.warning("yfinance %s option chains failed: %s", symbol, exc)
        return [], {}
    rows = [build_row(day, kind, exp, raw[exp.isoformat()]) for kind, exp in picks.items()]
    return rows, raw


def write_raw_chains(
    day: date, raw: dict[str, Chain], *, root: Path = settings.backtest_prices_cache_dir
) -> Path:
    """Write raw chains to ``<root>/options/SPY/<date>.json`` (private-cache payload)."""
    path = root / "options" / _TICKER_SPY / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2) + "\n")
    return path


# ----- per-year merge -----

RowKey = tuple[str, str]


def _year_path(year: int, *, root: Path) -> Path:
    return root / f"{year}.json"


def _load_year(year: int, *, root: Path) -> dict[RowKey, OptionsOiRow]:
    """Load a per-year file keyed by ``(date, expiry_kind)``, empty when missing."""
    path = _year_path(year, root=root)
    if not path.exists():
        return {}
    rows = (OptionsOiRow.model_validate(item) for item in json.loads(path.read_text()))
    return {(r.date.isoformat(), r.expiry_kind): r for r in rows}


def _write_year(year: int, by_key: dict[RowKey, OptionsOiRow], *, root: Path) -> Path:
    """Write a year's rows as a date-sorted JSON array."""
    root.mkdir(parents=True, exist_ok=True)
    path = _year_path(year, root=root)
    payload: list[Any] = [by_key[k].model_dump(mode="json") for k in sorted(by_key)]
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def merge_rows_into_years(
    rows: list[OptionsOiRow], *, root: Path = settings.options_oi_cache_dir
) -> dict[int, dict[RowKey, OptionsOiRow]]:
    """Merge fresh rows onto on-disk per-year files (in memory only).

    Rows are keyed by ``(date, expiry_kind)``; a same-day re-run replaces them.
    """
    by_year: dict[int, dict[RowKey, OptionsOiRow]] = {}
    for row in rows:
        if row.date.year not in by_year:
            by_year[row.date.year] = _load_year(row.date.year, root=root)
        by_year[row.date.year][(row.date.isoformat(), row.expiry_kind)] = row
    return by_year


def main() -> None:
    """Cron entrypoint: collect today's (UTC) rows, persist them and the raw chains."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    today = datetime.now(UTC).date()
    rows, raw = collect_options_oi(today)
    if not rows:
        logger.warning("options OI collection empty; nothing to write")
        return
    write_raw_chains(today, raw)
    by_year = merge_rows_into_years(rows)
    for year, by_key in sorted(by_year.items()):
        path = _write_year(year, by_key, root=settings.options_oi_cache_dir)
        logger.info("Wrote %s with %d entries", path, len(by_key))


if __name__ == "__main__":
    main()
