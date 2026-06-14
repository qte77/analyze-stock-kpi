"""Whit3rabbit CSV → FearGreedSnapshot backfill orchestration (#164).

Parses the [whit3rabbit/fear-greed-data](https://github.com/whit3rabbit/fear-greed-data)
mirror CSV (pinned via commit SHA in :mod:`scripts.backfill_fear_greed_whitrabbit`)
and merges its rows onto the same per-year ``results/cnn_fg/YYYY.json``
files :mod:`analyze_stock_kpi.data_sources.sentiment` writes, via the same
:func:`_upsert` semantics. Backfill is always ``force=False`` — a
higher-fidelity CNN-direct entry (intraday timestamp + subindicators)
always wins; backfill only fills genuine gaps.

Out of scope (per #164):

- Subindicator backfill — whit3rabbit only ships the headline score +
  rating; subindicator fields stay ``None`` for backfilled rows.
- Continuous re-sync — backfill is one-shot. The daily
  ``fear-greed.yaml`` cron remains authoritative for new dates.

ADR-0005 classifies whit3rabbit as a Tier-0 mirror — see the
2026-XX-XX amendment for the license posture (no upstream LICENSE
file as of the pinned SHA; tracked upstream at
``whit3rabbit/fear-greed-data#2``).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.sentiment import (
    FearGreedSnapshot,
    _load_year,
    _upsert,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def parse_row(row: dict[str, str]) -> FearGreedSnapshot | None:
    """Convert one whit3rabbit CSV row to a :class:`FearGreedSnapshot`.

    Returns ``None`` for blank / malformed rows (parser skips them
    silently). Pre-2021 archive ships integer scores; CNN-era ships
    floats — ``float()`` parses both.
    """
    date_str = (row.get("Date") or "").strip()
    score_str = (row.get("Fear Greed") or "").strip()
    rating = (row.get("Rating") or "").strip()
    if not (date_str and score_str and rating):
        return None
    try:
        score = float(score_str)
        moment = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
    except ValueError:
        return None
    return FearGreedSnapshot(score=score, rating=rating, timestamp=moment)


def parse_csv(text: str) -> Iterator[FearGreedSnapshot]:
    """Stream-parse the full whit3rabbit CSV body into snapshots.

    Silently skips blank rows and rows that fail :func:`parse_row`'s
    validation — operator inspects the eventual write count to confirm
    coverage.
    """
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        snap = parse_row(row)
        if snap is not None:
            yield snap


def merge_into_years(
    snapshots: Iterable[FearGreedSnapshot],
    *,
    root: Path = settings.cnn_fg_cache_dir,
) -> dict[int, dict[str, FearGreedSnapshot]]:
    """Merge backfill snapshots onto on-disk per-year files (in-memory only).

    Each snapshot routes to its UTC year. ``_upsert`` with
    ``force=False`` ensures backfill never overwrites a higher-fidelity
    CNN-direct entry that already exists for the same date (newer
    timestamp wins).

    Caller persists each year via
    :func:`analyze_stock_kpi.data_sources.sentiment._write_year`.
    """
    by_year: dict[int, dict[str, FearGreedSnapshot]] = {}
    for snap in snapshots:
        year = snap.timestamp.astimezone(UTC).year
        if year not in by_year:
            by_year[year] = _load_year(year, root=root)
        _upsert(by_year[year], snap, force=False)
    return by_year
