"""Tests for :mod:`src.orchestrators.aggregated_scores_best_and_worst`.

Strict TDD per #184 AC: each behaviour C1-C9 lands as a Red commit
(failing test) followed by a Green commit (minimal impl that passes).
"""

from __future__ import annotations

from src.orchestrators.aggregated_scores_best_and_worst import build_universe


def test_c1_empty_input_returns_empty_tuples() -> None:
    """C1: empty snapshots dict + empty dates dict -> empty preset, empty audit."""
    tickers, audit = build_universe({}, {})

    assert tickers == []
    assert audit == []
