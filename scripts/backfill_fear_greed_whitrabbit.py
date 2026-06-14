"""One-shot backfill: whit3rabbit/fear-greed-data → results/cnn_fg/YYYY.json (#164).

Thin wrapper around :mod:`analyze_stock_kpi.data_sources.sentiment_backfill`. Pinned
to a specific upstream commit SHA for deterministic backfill —
re-running on the same SHA must produce byte-identical output.

Operator workflow::

    uv run python scripts/backfill_fear_greed_whitrabbit.py

Then commit the changed ``results/cnn_fg/<YYYY>.json`` files to the
``data`` branch via the verified Git Data API pattern
(see ``.github/workflows/fear-greed.yaml`` for the cron analogue).
After the data-branch commit, the demo dashboard's Long-Term Context
tab renders ~14 years of monthly buckets instead of the ~13 months
the CNN-direct endpoint alone covers.

See [ADR-0005](../docs/decisions/0005-sentiment-risk-sources.md) for
the Tier-0 mirror amendment and the license posture (tracked
upstream at ``whit3rabbit/fear-greed-data#2``).
"""

from __future__ import annotations

import logging
import urllib.request

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.sentiment import _write_year
from analyze_stock_kpi.data_sources.sentiment_backfill import merge_into_years, parse_csv
from analyze_stock_kpi.utils.http_ua import STABLE_USER_AGENT, require_https

PINNED_SHA = "aa4f600959a12f9266d5bff75a78a50987b7e760"
CSV_URL = (
    f"https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/{PINNED_SHA}/fear-greed.csv"
)

logger = logging.getLogger(__name__)


def _fetch_csv() -> str:
    """Fetch the pinned whit3rabbit CSV body."""
    # S310 / B310: CSV_URL is a constant HTTPS string; the require_https
    # call below is the defense-in-depth boundary. Pattern mirrors
    # src/analyze_stock_kpi/data_sources/sentiment.py::_fetch_payload.
    request = urllib.request.Request(  # noqa: S310  # nosec B310
        CSV_URL, headers={"User-Agent": STABLE_USER_AGENT}
    )
    require_https(request.full_url)
    with urllib.request.urlopen(  # noqa: S310  # nosec B310
        request, timeout=settings.request_timeout_sec
    ) as response:
        return response.read().decode("utf-8")


def main() -> None:
    """Fetch CSV, merge into per-year files, persist."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Backfilling F&G from whit3rabbit @ %s", PINNED_SHA[:12])
    by_year = merge_into_years(parse_csv(_fetch_csv()))
    for year, by_date in sorted(by_year.items()):
        path = _write_year(year, by_date)
        logger.info("Wrote %s with %d entries", path, len(by_date))


if __name__ == "__main__":
    main()
