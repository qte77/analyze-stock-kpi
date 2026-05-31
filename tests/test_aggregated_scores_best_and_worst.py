"""Tests for :mod:`src.orchestrators.aggregated_scores_best_and_worst`.

Strict TDD per #184 AC: each behaviour C1-C9 lands as a Red commit
(failing test) followed by a Green commit (minimal impl that passes).
"""

from __future__ import annotations

from datetime import date

from src.data_sources.fundamentals import FundamentalsSnapshot
from src.domain.composite_scores import CompositeScores
from src.orchestrators.aggregated_scores_best_and_worst import build_universe


def _snap(
    symbol: str, **composites: float | None,
) -> FundamentalsSnapshot:
    """Build a synthetic FundamentalsSnapshot with optional composite scores."""
    cs = CompositeScores(**composites) if composites else None
    return FundamentalsSnapshot(symbol=symbol, composite_scores=cs)


def test_c1_empty_input_returns_empty_tuples() -> None:
    """C1: empty snapshots dict + empty dates dict -> empty preset, empty audit."""
    tickers, audit = build_universe({}, {})

    assert tickers == []
    assert audit == []


def test_c2_single_eligible_ticker_ranked_first() -> None:
    """C2: one fully-populated snapshot -> preset = [ticker], rank = 1."""
    snap = _snap(
        "AAPL", quality=80, dividend=20, growth=70, big_call=60,
        aaqs=75, hgi=65, screener_score=70,
    )

    tickers, audit = build_universe(
        {"sp500": [snap]},
        {"sp500": "2026-05-31"},
        as_of=date(2026, 5, 31),
    )

    assert tickers == ["AAPL"]
    assert len(audit) == 1
    row = audit[0]
    assert row.ticker == "AAPL"
    assert row.source_universes == ["sp500"]
    assert row.snapshot_dates == {"sp500": "2026-05-31"}
    assert row.eligible is True
    assert row.populated_composites == 7
    assert row.rank == 1
    assert row.mean_composite == sum([80, 20, 70, 60, 75, 65, 70]) / 7


def test_c3_ineligible_lt_min_composites_excluded() -> None:
    """C3: < 5 populated composites -> excluded, reason 'insufficient_composites'."""
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
