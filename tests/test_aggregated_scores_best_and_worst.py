"""Tests for :mod:`src.orchestrators.aggregated_scores_best_and_worst`.

Non-trivial behaviours only (matches the `make test_js` convention).
Trivial smoke cases (empty input, single ticker) are exercised
implicitly by the integration test and the ranking-boundary parametrize.
"""

from __future__ import annotations

from datetime import date

import pytest
from src.data_sources.fundamentals import FundamentalsSnapshot
from src.domain.composite_scores import CompositeScores
from src.orchestrators.aggregated_scores_best_and_worst import build_universe


def _snap(
    symbol: str, **composites: float | None,
) -> FundamentalsSnapshot:
    """Build a synthetic FundamentalsSnapshot with optional composite scores."""
    cs = CompositeScores(**composites) if composites else None
    return FundamentalsSnapshot(symbol=symbol, composite_scores=cs)


def test_ineligible_lt_min_composites_excluded() -> None:
    """< min_composites populated -> excluded, reason 'insufficient_composites'.

    Mirrors the L3 gate in `composite_scores.screener_score` so non-equities
    (FX / futures / sparse ADRs) don't rank alongside fully-populated equities.
    """
    snap = _snap("BTC-USD", quality=50, dividend=10, growth=20, big_call=30)

    tickers, audit = build_universe(
        {"crypto": [snap]},
        {"crypto": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert tickers == []
    assert len(audit) == 1
    row = audit[0]
    assert row.eligible is False
    assert row.excluded_reason == "insufficient_composites"
    assert row.populated_composites == 4
    assert row.rank is None
    assert row.mean_composite is None


def test_stale_snapshot_excluded() -> None:
    """Snapshot older than max_stale_days -> excluded, reason 'stale'.

    Guards against ranking on a universe whose cron is paused or broken.
    """
    snap = _snap(
        "AAPL", quality=80, dividend=20, growth=70, big_call=60,
        aaqs=75, hgi=65, screener_score=70,
    )

    tickers, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-11"},  # 20 days before as_of (default max=14)
        as_of=date(2026, 5, 31),
    )

    assert tickers == []
    assert audit[0].eligible is False
    assert audit[0].excluded_reason == "stale"
    assert audit[0].rank is None


def test_dedup_ticker_across_universes_first_seen_wins() -> None:
    """Ticker in multiple universes -> first-seen snapshot wins; all sources recorded.

    Dedup matters because the same ticker can appear in qte77-watchlist AND sp500;
    we shouldn't double-rank and shouldn't lose the cross-universe membership signal.
    """
    snap_sp500 = _snap(
        "AAPL", quality=80, dividend=20, growth=70, big_call=60,
        aaqs=75, hgi=65, screener_score=70,
    )
    snap_watchlist = _snap(
        "AAPL", quality=50, dividend=10, growth=40, big_call=30,
        aaqs=45, hgi=35, screener_score=40,
    )

    tickers, audit = build_universe(
        {"sp500": [snap_sp500], "qte77-watchlist": [snap_watchlist]},
        {"sp500": "2026-05-31", "qte77-watchlist": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert tickers == ["AAPL"]
    assert len(audit) == 1
    row = audit[0]
    assert row.source_universes == ["sp500", "qte77-watchlist"]
    assert row.snapshot_dates == {
        "sp500": "2026-05-31",
        "qte77-watchlist": "2026-05-31",
    }
    # First-seen snapshot's values (sp500) used for the mean, not watchlist's.
    assert row.mean_composite == sum([80, 20, 70, 60, 75, 65, 70]) / 7


@pytest.mark.parametrize(
    ("n", "expected_top", "expected_bottom", "expected_unranked"),
    [
        (60, 25, 25, 10),  # > 2*top_n: top 25 + bottom 25, 10 middle excluded
        (50, 25, 25, 0),   # exactly 2*top_n: all selected, no middle
        (30, 25, 5, 0),    # < 2*top_n but > top_n: top fills first, partial bottom
        (20, 20, 0, 0),    # < top_n: all top, no bottom (no room)
    ],
)
def test_ranking_boundaries(
    n: int,
    expected_top: int,
    expected_bottom: int,
    expected_unranked: int,
) -> None:
    """Top/bottom selection handles the four count regimes around 2*top_n.

    Distinct means (descending) so sort order is unambiguous. Boundary
    behaviour matters: an off-by-one here would silently drop tickers from
    the universe preset or over-select past the intended count.
    """
    snapshots = [
        _snap(
            f"T{i:03d}",
            quality=float(100 - i),
            dividend=50.0,
            growth=50.0,
            big_call=50.0,
            aaqs=50.0,
            hgi=50.0,
            screener_score=50.0,
        )
        for i in range(n)
    ]

    tickers, audit = build_universe(
        {"sp500": snapshots},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
        top_n=25,
    )

    assert len(tickers) == expected_top + expected_bottom
    top_ranked = [row for row in audit if row.rank is not None and row.rank > 0]
    bottom_ranked = [row for row in audit if row.rank is not None and row.rank < 0]
    unranked_eligible = [
        row for row in audit if row.eligible and row.rank is None
    ]
    assert len(top_ranked) == expected_top
    assert len(bottom_ranked) == expected_bottom
    assert len(unranked_eligible) == expected_unranked


def test_ties_sort_ascii_ascending_by_ticker() -> None:
    """All eligible tied on mean -> stable secondary sort by ticker ASCII ascending.

    Without a deterministic tiebreak the preset diff would flap week-over-week
    on identical inputs and the auto/refresh PR-on-diff cron would noise out.
    """
    snaps = [
        _snap(
            t, quality=50.0, dividend=50.0, growth=50.0, big_call=50.0,
            aaqs=50.0, hgi=50.0, screener_score=50.0,
        )
        for t in ["MSFT", "AAPL", "GOOG"]
    ]

    tickers, audit = build_universe(
        {"sp500": snaps},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
        top_n=2,
    )

    # All 3 tied. Ascending tiebreak: AAPL, GOOG, MSFT.
    # top_n=2 -> top=2, bottom=min(2, 3-2)=1.
    # Ranks: AAPL=1, GOOG=2, MSFT=-1. All 3 selected.
    assert tickers == ["AAPL", "GOOG", "MSFT"]
    ranks = {row.ticker: row.rank for row in audit}
    assert ranks["AAPL"] == 1
    assert ranks["GOOG"] == 2
    assert ranks["MSFT"] == -1


def test_integration_multiple_universes_mixed_eligibility() -> None:
    """3 universes, mixed eligible/ineligible -> correct preset + audit."""
    sp500 = [
        _snap(
            "AAPL", quality=90, dividend=30, growth=80, big_call=70,
            aaqs=85, hgi=75, screener_score=80,
        ),
        _snap(
            "MSFT", quality=85, dividend=25, growth=75, big_call=65,
            aaqs=80, hgi=70, screener_score=75,
        ),
        _snap(
            "XOM", quality=40, dividend=60, growth=20, big_call=30,
            aaqs=35, hgi=25, screener_score=30,
        ),
    ]
    eurostoxx = [
        _snap(
            "ASML", quality=82, dividend=22, growth=72, big_call=62,
            aaqs=77, hgi=67, screener_score=72,
        ),
    ]
    crypto = [_snap("BTC", quality=50, dividend=10)]  # 2/7 -> ineligible

    tickers, audit = build_universe(
        {"sp500": sp500, "eurostoxx": eurostoxx, "crypto": crypto},
        {
            "sp500": "2026-05-31",
            "eurostoxx": "2026-05-31",
            "crypto": "2026-05-31",
        },
        as_of=date(2026, 5, 31),
        top_n=2,
    )

    # Means desc: AAPL ≈ 72.86, MSFT ≈ 67.86, ASML ≈ 64.86, XOM ≈ 34.29
    # top_n=2: top = [AAPL(1), MSFT(2)]; bottom = [XOM(-1), ASML(-2)]
    assert sorted(tickers) == ["AAPL", "ASML", "MSFT", "XOM"]
    ranks = {row.ticker: row.rank for row in audit}
    assert ranks["AAPL"] == 1
    assert ranks["MSFT"] == 2
    assert ranks["XOM"] == -1
    assert ranks["ASML"] == -2
    assert ranks["BTC"] is None
    btc_row = next(r for r in audit if r.ticker == "BTC")
    assert btc_row.excluded_reason == "insufficient_composites"
