"""One-shot backfill: full yfinance ^TNX/^FVX history → results/yield_curve/YYYY.json (#287).

Thin wrapper around :mod:`analyze_stock_kpi.data_sources.yield_curve`. The daily
cron (``yield-curve.yaml``) only fetches deep history on a *first* run
(``period="5y"``); every subsequent run appends a single day. This script forces
a full ``period="max"`` fetch so the 5s10s slope chart's 10y / all windows have
data well beyond the 5-year cron horizon — "as far back as the upstream source
allows" (#287).

Re-running merges onto the on-disk per-year files (``merge_payload_into_years``
loads them first), so it is idempotent against the same yfinance horizon and
never clobbers existing rows.

Operator workflow::

    uv run python scripts/backfill_yield_curve.py

Then commit the changed ``results/yield_curve/<YYYY>.json`` files to the
``data`` branch (the daily ``yield-curve.yaml`` cron keeps them current after).
Override ``SSK_YIELD_CURVE_CACHE_DIR`` to write somewhere other than the default
``results/yield_curve``.
"""

from __future__ import annotations

import logging

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.yield_curve import (
    _write_year,
    fetch_yield_curve_history,
    merge_payload_into_years,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Fetch full ^TNX/^FVX history, merge into per-year files, persist."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Backfilling 5s10s yield-curve history (period=max)")
    snaps = fetch_yield_curve_history(period="max")
    if not snaps:
        logger.warning("yield-curve history fetch empty; nothing to write")
        return
    by_year = merge_payload_into_years(snaps)
    for year, by_date in sorted(by_year.items()):
        path = _write_year(year, by_date, root=settings.yield_curve_cache_dir)
        logger.info("Wrote %s with %d entries", path, len(by_date))


if __name__ == "__main__":
    main()
