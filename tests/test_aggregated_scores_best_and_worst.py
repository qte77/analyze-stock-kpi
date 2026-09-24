"""Tests for :mod:`analyze_stock_kpi.orchestrators.aggregated_scores_best_and_worst`.

Non-trivial behaviours only (matches the `make test_js` convention).
Trivial smoke cases (empty input, single ticker) are exercised
implicitly by the integration test and the ranking-boundary parametrize.

Orchestrator returns a 3-tuple ``(best, worst, audit)``; the script
wrapper writes ``best`` and ``worst`` to separate preset files
(``aggregated-scores-best.txt`` + ``aggregated-scores-worst.txt``).
"""

from __future__ import annotations

from datetime import date

import pytest

from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot
from analyze_stock_kpi.domain.composite_scores import CompositeScores
from analyze_stock_kpi.orchestrators.aggregated_scores_best_and_worst import (
    build_universe,
    ranked_snapshots,
)


def _snap(
    symbol: str,
    **composites: float | None,
) -> FundamentalsSnapshot:
    """Build a synthetic FundamentalsSnapshot with optional composite scores."""
    cs = CompositeScores(**composites) if composites else None
    return FundamentalsSnapshot(symbol=symbol, composite_scores=cs)


def test_composite_breakdown_covers_every_composite_scores_field() -> None:
    """``composite_breakdown`` keys must equal ``CompositeScores`` fields.

    Regression guard for a previously hardcoded ``_COMPOSITE_FIELDS`` tuple
    that could silently drift from ``CompositeScores`` — adding a new
    composite to the model would have been omitted from cross-universe
    ranking without a separate edit here.
    """
    snap = _snap(
        "AAPL",
        quality=80,
        dividend=20,
        growth=70,
        big_call=60,
        aaqs=75,
        hgi=65,
        screener_score=70,
    )

    _, _, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert set(audit[0].composite_breakdown) == set(CompositeScores.model_fields)


def test_ineligible_missing_screener_score_excluded() -> None:
    """No `screener_score` -> excluded, reason 'no_screener_score'.

    Ranking is by `screener_score` (the same "qte77 Score" the dashboard
    shows on every universe); a snapshot without it -- e.g. an
    informationally-thin non-equity (FX / futures / sparse ADR) that fails
    `composite_scores.screener_score`'s own L3 gate -- can't be ranked.
    """
    snap = _snap("BTC-USD", quality=50, dividend=10, growth=20, big_call=30)

    best, worst, audit = build_universe(
        {"crypto": [snap]},
        {"crypto": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert best == []
    assert worst == []
    assert len(audit) == 1
    row = audit[0]
    assert row.eligible is False
    assert row.excluded_reason == "no_screener_score"
    assert row.populated_composites == 4
    assert row.rank is None
    assert row.screener_score is None


def test_stale_snapshot_excluded() -> None:
    """Snapshot older than max_stale_days -> excluded, reason 'stale'.

    Guards against ranking on a universe whose cron is paused or broken.
    """
    snap = _snap(
        "AAPL",
        quality=80,
        dividend=20,
        growth=70,
        big_call=60,
        aaqs=75,
        hgi=65,
        screener_score=70,
    )

    best, worst, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-11"},  # 20 days before as_of (default max=14)
        as_of=date(2026, 5, 31),
    )

    assert best == []
    assert worst == []
    assert audit[0].eligible is False
    assert audit[0].excluded_reason == "stale"
    assert audit[0].rank is None


def test_dedup_ticker_across_universes_first_seen_wins() -> None:
    """Ticker in multiple universes -> first-seen snapshot wins; all sources recorded.

    Dedup matters because the same ticker can appear in qte77-watchlist AND sp500;
    we shouldn't double-rank and shouldn't lose the cross-universe membership signal.
    """
    snap_sp500 = _snap(
        "AAPL",
        quality=80,
        dividend=20,
        growth=70,
        big_call=60,
        aaqs=75,
        hgi=65,
        screener_score=70,
    )
    snap_watchlist = _snap(
        "AAPL",
        quality=50,
        dividend=10,
        growth=40,
        big_call=30,
        aaqs=45,
        hgi=35,
        screener_score=40,
    )

    best, worst, audit = build_universe(
        {"sp500": [snap_sp500], "qte77-watchlist": [snap_watchlist]},
        {"sp500": "2026-05-31", "qte77-watchlist": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    # Single eligible ticker -> goes to best (rank=1), worst is empty.
    assert best == ["AAPL"]
    assert worst == []
    assert len(audit) == 1
    row = audit[0]
    assert row.source_universes == ["sp500", "qte77-watchlist"]
    assert row.snapshot_dates == {
        "sp500": "2026-05-31",
        "qte77-watchlist": "2026-05-31",
    }
    # First-seen snapshot's screener_score (sp500) used for ranking, not watchlist's.
    assert row.screener_score == 70


@pytest.mark.parametrize(
    ("n", "expected_best", "expected_worst", "expected_unranked"),
    [
        (60, 25, 25, 10),  # > 2*top_n: best 25 + worst 25, 10 middle excluded
        (50, 25, 25, 0),  # exactly 2*top_n: all selected, no middle
        (30, 25, 5, 0),  # < 2*top_n but > top_n: best fills first, partial worst
        (20, 20, 0, 0),  # < top_n: all best, no worst (no room)
    ],
)
def test_ranking_boundaries(
    n: int,
    expected_best: int,
    expected_worst: int,
    expected_unranked: int,
) -> None:
    """Best/worst selection handles the four count regimes around 2*top_n.

    Distinct screener_scores (descending) so sort order is unambiguous.
    Boundary behaviour matters: an off-by-one here would silently drop
    tickers from a preset or over-select past the intended count.
    """
    snapshots = [
        _snap(
            f"T{i:03d}",
            quality=50.0,
            dividend=50.0,
            growth=50.0,
            big_call=50.0,
            aaqs=50.0,
            hgi=50.0,
            screener_score=float(100 - i),
        )
        for i in range(n)
    ]

    best, worst, audit = build_universe(
        {"sp500": snapshots},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
        top_n=25,
    )

    assert len(best) == expected_best
    assert len(worst) == expected_worst
    assert set(best).isdisjoint(set(worst))
    top_ranked = [row for row in audit if row.rank is not None and row.rank > 0]
    bottom_ranked = [row for row in audit if row.rank is not None and row.rank < 0]
    unranked_eligible = [row for row in audit if row.eligible and row.rank is None]
    assert len(top_ranked) == expected_best
    assert len(bottom_ranked) == expected_worst
    assert len(unranked_eligible) == expected_unranked


def test_ties_sort_ascii_ascending_by_ticker() -> None:
    """All eligible tied on mean -> stable secondary sort by ticker ASCII ascending.

    Without a deterministic tiebreak the preset diff would flap week-over-week
    on identical inputs and the auto/refresh PR-on-diff cron would noise out.
    """
    snaps = [
        _snap(
            t,
            quality=50.0,
            dividend=50.0,
            growth=50.0,
            big_call=50.0,
            aaqs=50.0,
            hgi=50.0,
            screener_score=50.0,
        )
        for t in ["MSFT", "AAPL", "GOOG"]
    ]

    best, worst, audit = build_universe(
        {"sp500": snaps},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
        top_n=2,
    )

    # All 3 tied. Ascending tiebreak: AAPL, GOOG, MSFT.
    # top_n=2 -> best=[AAPL,GOOG] (ranks 1,2); worst=[MSFT] (rank -1).
    assert best == ["AAPL", "GOOG"]
    assert worst == ["MSFT"]
    ranks = {row.ticker: row.rank for row in audit}
    assert ranks["AAPL"] == 1
    assert ranks["GOOG"] == 2
    assert ranks["MSFT"] == -1


def test_ranks_by_screener_score_not_mean_of_composites() -> None:
    """Regression guard: ranking uses `screener_score`, not the mean of all 7.

    A ticker with a high mean-of-7 but a comparatively low `screener_score`
    must NOT outrank a ticker with the opposite shape -- otherwise the
    aggregator's best/worst placement disagrees with the "qte77 Score" the
    dashboard displays for the same ticker on every other universe (the
    dashboard-consistency bug this aggregator is being fixed for).
    """
    high_mean_low_screener = _snap(
        "HIGH_MEAN",
        quality=95,
        dividend=95,
        growth=95,
        big_call=95,
        aaqs=95,
        hgi=95,
        screener_score=40,
    )
    low_mean_high_screener = _snap(
        "LOW_MEAN",
        quality=10,
        dividend=10,
        growth=10,
        big_call=10,
        aaqs=10,
        hgi=10,
        screener_score=90,
    )

    best, worst, audit = build_universe(
        {"sp500": [high_mean_low_screener, low_mean_high_screener]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
        top_n=1,
    )

    assert best == ["LOW_MEAN"]
    assert worst == ["HIGH_MEAN"]
    ranks = {row.ticker: row.screener_score for row in audit}
    assert ranks["LOW_MEAN"] == 90
    assert ranks["HIGH_MEAN"] == 40


def test_integration_multiple_universes_mixed_eligibility() -> None:
    """3 universes, mixed eligible/ineligible -> correct best+worst pair + audit."""
    sp500 = [
        _snap(
            "AAPL",
            quality=90,
            dividend=30,
            growth=80,
            big_call=70,
            aaqs=85,
            hgi=75,
            screener_score=80,
        ),
        _snap(
            "MSFT",
            quality=85,
            dividend=25,
            growth=75,
            big_call=65,
            aaqs=80,
            hgi=70,
            screener_score=75,
        ),
        _snap(
            "XOM",
            quality=40,
            dividend=60,
            growth=20,
            big_call=30,
            aaqs=35,
            hgi=25,
            screener_score=30,
        ),
    ]
    eurostoxx = [
        _snap(
            "ASML",
            quality=82,
            dividend=22,
            growth=72,
            big_call=62,
            aaqs=77,
            hgi=67,
            screener_score=72,
        ),
    ]
    crypto = [_snap("BTC", quality=50, dividend=10)]  # 2/7 -> ineligible

    best, worst, audit = build_universe(
        {"sp500": sp500, "eurostoxx": eurostoxx, "crypto": crypto},
        {
            "sp500": "2026-05-31",
            "eurostoxx": "2026-05-31",
            "crypto": "2026-05-31",
        },
        as_of=date(2026, 5, 31),
        top_n=2,
    )

    # screener_score desc: AAPL 80, MSFT 75, ASML 72, XOM 30
    # top_n=2: best = [AAPL(1), MSFT(2)]; worst = [XOM(-1), ASML(-2)]
    assert best == ["AAPL", "MSFT"]
    assert worst == ["ASML", "XOM"]
    assert set(best).isdisjoint(set(worst))
    ranks = {row.ticker: row.rank for row in audit}
    assert ranks["AAPL"] == 1
    assert ranks["MSFT"] == 2
    assert ranks["XOM"] == -1
    assert ranks["ASML"] == -2
    assert ranks["BTC"] is None
    btc_row = next(r for r in audit if r.ticker == "BTC")
    assert btc_row.excluded_reason == "no_screener_score"


def test_ranked_snapshots_returns_identical_records_used_for_ranking() -> None:
    """``ranked_snapshots`` returns the exact objects ``build_universe`` ranked.

    Owner requirement: the aggregated best/worst lists must carry the
    identical per-ticker qte77 Score (``screener_score``) and KPI record as
    the source-universe snapshot they were ranked from -- never a second,
    independent fetch. The build script uses this accessor to emit the
    demo-display JSON, so it must hand back the SAME objects, not
    recomputed ones.
    """
    best_snap = _snap(
        "AAPL", quality=90, dividend=30, growth=80, big_call=70, aaqs=85, hgi=75, screener_score=80
    )
    worst_snap = _snap(
        "XOM", quality=40, dividend=60, growth=20, big_call=30, aaqs=35, hgi=25, screener_score=30
    )
    snapshots_by_universe = {"sp500": [best_snap, worst_snap]}
    snapshot_dates = {"sp500": "2026-05-31"}

    best, worst, _ = build_universe(
        snapshots_by_universe, snapshot_dates, as_of=date(2026, 5, 31), top_n=1
    )
    resolved = ranked_snapshots(snapshots_by_universe, snapshot_dates, best + worst)

    assert best == ["AAPL"]
    assert worst == ["XOM"]
    assert resolved == [best_snap, worst_snap]


def test_best_min_score_gte_worst_max_score() -> None:
    """Owner acceptance criterion: best-list minimum score >= worst-list maximum.

    Guards the aggregated display invariant end to end -- a re-fetch that
    reintroduced divergent data could let a worst-list ticker outscore a
    best-list one (the BAYN.DE/YOU regression this fix addresses).
    """
    snapshots = [
        _snap(
            f"T{i:03d}",
            quality=50.0,
            dividend=50.0,
            growth=50.0,
            big_call=50.0,
            aaqs=50.0,
            hgi=50.0,
            screener_score=float(100 - i),
        )
        for i in range(50)
    ]

    best, worst, audit = build_universe(
        {"sp500": snapshots}, {"sp500": "2026-05-31"}, as_of=date(2026, 5, 31), top_n=25
    )

    scores = {row.ticker: row.screener_score for row in audit}
    assert min(scores[t] for t in best) >= max(scores[t] for t in worst)
