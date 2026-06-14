"""Tests for :mod:`analyze_stock_kpi.orchestrators.enhanced_kpi_screener_longshort`.

Non-trivial behaviours only (matches the aggregator file's convention).
Trivial smoke cases (empty input, all-pass single ticker) ride along in
the parametrize / integration test.

Orchestrator returns ``(longs, shorts, audit)``; conjunctive gates per
side; long ∩ short empty by construction.
"""

from __future__ import annotations

from datetime import date

import pytest

from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot
from analyze_stock_kpi.orchestrators.enhanced_kpi_screener_longshort import build_universe

_LONG_FIXTURE: dict[str, float | str | None] = {
    "market_cap": 5e9,
    "forward_pe": 18.0,
    "earnings_growth": 0.20,
    "revenue_growth": 0.15,
    "trailing_peg_ratio": 0.8,
    "return_on_equity": 0.18,
    "beta": 1.2,
    "return_on_assets": 0.12,
    "roi": 0.15,
    "current_ratio": 1.5,
    "quick_ratio": 1.2,
    "fcf_margin": 0.18,
    "profit_margins": 0.15,
    "analyst_recommendation": "buy",
    "rd_to_revenue": 0.08,
}

_SHORT_FIXTURE: dict[str, float | str | None] = {
    "market_cap": 5e9,
    "forward_pe": 45.0,
    "earnings_growth": -0.10,
    "revenue_growth": -0.05,
    "trailing_peg_ratio": 3.0,
    "return_on_equity": 0.02,
    "beta": 1.5,
    "return_on_assets": 0.01,
    "roi": 0.02,
    "current_ratio": 0.6,
    "quick_ratio": 0.4,
    "fcf_margin": -0.08,
    "profit_margins": -0.05,
    "analyst_recommendation": "sell",
}

_NEUTRAL_FIXTURE: dict[str, float | str | None] = {
    "market_cap": 5e9,
    "forward_pe": 20.0,  # passes long, fails short
    "earnings_growth": 0.05,  # fails both gates
    "revenue_growth": 0.05,
    "trailing_peg_ratio": 1.5,  # fails long (< 1), passes short (>= 1)
    "return_on_equity": 0.07,  # fails both
    "beta": 1.2,
    "return_on_assets": 0.05,
    "roi": 0.07,
    "current_ratio": 1.0,  # passes neither (not > 1, not < 1)
    "quick_ratio": 1.0,
    "fcf_margin": 0.05,  # fails both (not > 0.10, not < 0)
    "profit_margins": 0.05,
    "analyst_recommendation": "hold",
}


def _snap(symbol: str, **overrides: float | str | None) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(symbol=symbol, **overrides)


@pytest.mark.parametrize(
    ("fixture", "expected_tier", "expected_list_attr"),
    [
        (_LONG_FIXTURE, "long", "longs"),
        (_SHORT_FIXTURE, "short", "shorts"),
    ],
    ids=["long-pass-all-15", "short-pass-all-14"],
)
def test_pass_all_gates_lands_in_correct_list(
    fixture: dict[str, float | str | None],
    expected_tier: str,
    expected_list_attr: str,
) -> None:
    """All conjunctive gates met -> ticker in expected list with matching tier.

    Parametrized over both sides so an asymmetric regression on long OR short
    selection surfaces from the same test scaffold.
    """
    snap = _snap("TEST", **fixture)
    longs, shorts, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )
    result = {"longs": longs, "shorts": shorts}[expected_list_attr]
    other = {"longs": shorts, "shorts": longs}[expected_list_attr]
    assert result == ["TEST"]
    assert other == []
    assert audit[0].tier == expected_tier
    assert audit[0].eligible is True


def test_neutral_ticker_lands_in_neither() -> None:
    """Mid-range values that pass some long + some short gates -> neither side.

    The conjunctive-gate primitive must NOT classify a ticker as "long" or
    "short" unless EVERY gate on that side passes; the partial-overlap case
    is the highest-risk false positive.
    """
    snap = _snap("MID", **_NEUTRAL_FIXTURE)
    longs, shorts, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )
    assert longs == []
    assert shorts == []
    assert audit[0].tier == "neither"
    assert audit[0].eligible is True


def test_insufficient_criteria_excluded() -> None:
    """< min_criteria populated -> excluded, reason 'insufficient_criteria'.

    Mirrors the aggregator's L3 gate so sparse non-equity snapshots can't
    backdoor onto either side via a coincidentally-passing handful of gates.
    """
    snap = _snap(
        "SPARSE",
        market_cap=5e9,
        forward_pe=18.0,
        earnings_growth=0.20,  # 3 populated -> < 10 minimum
    )
    longs, shorts, audit = build_universe(
        {"crypto": [snap]},
        {"crypto": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )
    assert longs == []
    assert shorts == []
    assert audit[0].eligible is False
    assert audit[0].excluded_reason == "insufficient_criteria"
    assert audit[0].populated_criteria == 3
    assert audit[0].tier == "neither"


def test_stale_snapshot_excluded() -> None:
    """Snapshot older than max_stale_days -> excluded, reason 'stale'.

    Same freshness guard the aggregator runs (PR #199) — prevents ranking
    on a universe whose cron is paused.
    """
    snap = _snap("AAPL", **_LONG_FIXTURE)
    longs, shorts, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-11"},  # 20 days before as_of, default max=14
        as_of=date(2026, 5, 31),
    )
    assert longs == []
    assert shorts == []
    assert audit[0].eligible is False
    assert audit[0].excluded_reason == "stale"


def test_dedup_ticker_across_universes_first_seen_wins() -> None:
    """Ticker in 2+ universes -> first-seen snapshot wins; all sources recorded.

    Same dedup semantics the aggregator uses; the long-side classification
    must not flip based on the iteration order of the source-universes dict
    (Python dicts are insertion-ordered, so first-inserted wins).
    """
    snap_sp500 = _snap("AAPL", **_LONG_FIXTURE)
    snap_watchlist = _snap("AAPL", **_SHORT_FIXTURE)

    longs, shorts, audit = build_universe(
        {"sp500": [snap_sp500], "qte77-watchlist": [snap_watchlist]},
        {"sp500": "2026-05-31", "qte77-watchlist": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert longs == ["AAPL"]
    assert shorts == []
    row = audit[0]
    assert row.source_universes == ["sp500", "qte77-watchlist"]
    assert row.snapshot_dates == {
        "sp500": "2026-05-31",
        "qte77-watchlist": "2026-05-31",
    }


def test_longs_shorts_disjoint_at_scale() -> None:
    """Disjoint by construction: no ticker can land in both lists.

    A 50-ticker spread of long + short + neutral fixtures forces the
    selection code to reject any 'both sides pass' candidate (impossible
    given inverted gates, but worth pinning so a future widening of a gate
    threshold doesn't silently break disjointness).
    """
    snaps = []
    for i in range(20):
        snaps.append(_snap(f"L{i:02d}", **_LONG_FIXTURE))
    for i in range(20):
        snaps.append(_snap(f"S{i:02d}", **_SHORT_FIXTURE))
    for i in range(10):
        snaps.append(_snap(f"N{i:02d}", **_NEUTRAL_FIXTURE))

    longs, shorts, _ = build_universe(
        {"sp500": snaps},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert len(longs) == 20
    assert len(shorts) == 20
    assert set(longs).isdisjoint(set(shorts))
    assert longs == sorted(longs)
    assert shorts == sorted(shorts)


@pytest.mark.parametrize(
    ("rec_key", "long_pass", "short_pass"),
    [
        ("buy", True, False),
        ("strong_buy", True, False),
        ("sell", False, True),
        ("strong_sell", False, True),
        ("hold", False, False),
        (None, False, False),
    ],
)
def test_criterion_14_recommendation_key_mapping(
    rec_key: str | None,
    long_pass: bool,
    short_pass: bool,
) -> None:
    """`recommendationKey` -> gate pass/fail per Yahoo's bucket vocabulary.

    Asserts on the audit's per-criterion breakdown rather than the final
    tier so the test isolates the criterion-14 mapping from the other 14
    gates' values (different base fixtures would flip the whole tier).
    """
    fixture = dict(_LONG_FIXTURE)
    if rec_key is None:
        fixture.pop("analyst_recommendation")
    else:
        fixture["analyst_recommendation"] = rec_key
    snap = _snap("T", **fixture)
    _, _, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )
    assert audit[0].long_breakdown["analyst_recommendation"] is long_pass
    assert audit[0].short_breakdown["analyst_recommendation"] is short_pass
