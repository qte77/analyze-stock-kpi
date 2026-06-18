"""Tests for :mod:`analyze_stock_kpi.data_sources.sentiment_backfill`.

Non-trivial cases only: parse boundaries (CNN-era float vs pre-2021 int
scores, blank rows, malformed dates, missing fields), multi-year UTC
grouping, and the load-bearing posture — backfill never overwrites a
higher-fidelity CNN-direct entry already on disk (#164).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from analyze_stock_kpi.data_sources.sentiment import (
    FearGreedSnapshot,
    SubindicatorReading,
    _write_year,
)
from analyze_stock_kpi.data_sources.sentiment_backfill import (
    merge_into_years,
    parse_csv,
    parse_row,
)

if TYPE_CHECKING:
    from pathlib import Path


# ----- parse_row -----


def test_parse_row_cnn_era_float_score() -> None:
    snap = parse_row({"Date": "2025-03-15", "Fear Greed": "42.5", "Rating": "neutral"})
    assert snap is not None
    assert snap.score == 42.5
    assert snap.rating == "neutral"
    # Per scope: whit3rabbit doesn't ship subindicators; they stay None
    # for pre-2025 (and all backfilled) rows. CNN-direct cron fills
    # post-2025 subindicators on a separate code path.
    assert snap.subindicators is None
    assert snap.timestamp.tzinfo == UTC


def test_parse_row_pre_2021_int_score() -> None:
    """Pre-2021 archive ships integer scores; CNN-era floats. Both parse."""
    snap = parse_row({"Date": "2015-08-24", "Fear Greed": "6", "Rating": "extreme fear"})
    assert snap is not None
    assert snap.score == 6.0


def test_parse_row_blank_returns_none() -> None:
    assert parse_row({"Date": "", "Fear Greed": "", "Rating": ""}) is None


def test_parse_row_malformed_date_returns_none() -> None:
    assert parse_row({"Date": "not-a-date", "Fear Greed": "50", "Rating": "neutral"}) is None


def test_parse_row_missing_rating_returns_none() -> None:
    assert parse_row({"Date": "2025-03-15", "Fear Greed": "42.5"}) is None


# ----- parse_csv -----


def test_parse_csv_skips_blanks_and_yields_valid_rows() -> None:
    text = "Date,Fear Greed,Rating\n2011-01-03,45,greed\n,,\n2026-05-29,33.2,fear\n"
    snaps = list(parse_csv(text))
    assert [s.score for s in snaps] == [45.0, 33.2]


# ----- merge_into_years -----


def test_merge_into_years_groups_by_utc_year(tmp_path: Path) -> None:
    snaps = [
        FearGreedSnapshot(score=20.0, rating="fear", timestamp=datetime(2011, 1, 3, tzinfo=UTC)),
        FearGreedSnapshot(
            score=50.0, rating="neutral", timestamp=datetime(2026, 5, 29, tzinfo=UTC)
        ),
    ]
    by_year = merge_into_years(snaps, root=tmp_path)
    assert set(by_year.keys()) == {2011, 2026}
    assert "2011-01-03" in by_year[2011]
    assert "2026-05-29" in by_year[2026]


def test_merge_into_years_does_not_overwrite_cnn_direct_entry(tmp_path: Path) -> None:
    """Backfill must never clobber a higher-fidelity CNN-direct row.

    Real CNN *historical* rows are stored at **midnight UTC** (the data-point
    date boundary) — the same key a whit3rabbit row produces, not an intraday
    timestamp. So the guard cannot rely on a newer timestamp: backfill is a
    strict gap-fill and keeps whatever is already on disk for that date, even
    when the timestamps tie and the backfill row looks "different" (it lacks
    subindicators). A same-midnight backfill row must NOT replace it.
    """
    existing = FearGreedSnapshot(
        score=42.0,
        rating="neutral",
        timestamp=datetime(2026, 5, 29, tzinfo=UTC),
        subindicators={
            "market_momentum_sp500": SubindicatorReading(rating="greed", raw_value=5800.0),
        },
    )
    _write_year(2026, {"2026-05-29": existing}, root=tmp_path)
    backfill = FearGreedSnapshot(
        score=99.0,
        rating="extreme greed",
        timestamp=datetime(2026, 5, 29, tzinfo=UTC),
    )

    by_year = merge_into_years([backfill], root=tmp_path)

    kept = by_year[2026]["2026-05-29"]
    assert kept.score == 42.0
    assert kept.subindicators is not None


def test_merge_into_years_fills_gap_when_no_existing_entry(tmp_path: Path) -> None:
    snap = FearGreedSnapshot(
        score=12.0, rating="extreme fear", timestamp=datetime(2015, 8, 24, tzinfo=UTC)
    )

    by_year = merge_into_years([snap], root=tmp_path)

    assert by_year[2015]["2015-08-24"].score == 12.0
