"""Tests for :mod:`src.composite_scores`.

Each assertion uses a hand-computable expected value. Inputs are chosen
so every term saturates at exactly 0 or 100, or rescales to a clean
midpoint. No ``pytest.approx`` — fixtures vendor exact values.
"""

from __future__ import annotations

from src.data_sources.fundamentals import FundamentalsSnapshot
from src.domain.composite_scores import (
    CompositeScores,
    aaqs,
    big_call,
    compute_scores,
    dividend,
    growth,
    hgi,
    quality,
    screener_score,
)


def _snap(**kwargs: object) -> FundamentalsSnapshot:
    """Build a synthetic snapshot with only the fields under test."""
    return FundamentalsSnapshot(symbol="X", **kwargs)  # type: ignore[arg-type]


def test_quality_saturates_to_100() -> None:
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        debt_to_equity=0.0,
    )
    assert quality(snap) == 100.0


def test_quality_clamps_at_zero() -> None:
    snap = _snap(
        return_on_equity=-0.10,
        return_on_assets=-0.05,
        operating_margins=-0.10,
        debt_to_equity=300.0,
    )
    assert quality(snap) == 0.0


def test_quality_midpoint() -> None:
    snap = _snap(
        return_on_equity=0.15,
        return_on_assets=0.075,
        operating_margins=0.15,
        debt_to_equity=100.0,
    )
    assert quality(snap) == 50.0


def test_quality_drops_negative_de_term() -> None:
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        debt_to_equity=-50.0,
    )
    assert quality(snap) == 100.0


def test_quality_returns_none_when_all_inputs_missing() -> None:
    assert quality(_snap()) is None


def test_dividend_saturates() -> None:
    snap = _snap(dividend_yield=0.07, payout_ratio=0.5)
    assert dividend(snap) == 100.0


def test_dividend_zero_yield_zero_payout() -> None:
    snap = _snap(dividend_yield=0.0, payout_ratio=0.0)
    assert dividend(snap) == 0.0


def test_dividend_yield_only_when_payout_missing() -> None:
    snap = _snap(dividend_yield=0.07)
    assert dividend(snap) == 100.0


def test_dividend_returns_none_when_both_missing() -> None:
    assert dividend(_snap()) is None


def test_growth_saturates() -> None:
    snap = _snap(revenue_growth=0.50, earnings_growth=0.50)
    assert growth(snap) == 100.0


def test_growth_clamps_at_zero() -> None:
    snap = _snap(revenue_growth=-0.20, earnings_growth=-0.20)
    assert growth(snap) == 0.0


def test_growth_midpoint() -> None:
    snap = _snap(revenue_growth=0.15, earnings_growth=0.15)
    assert growth(snap) == 50.0


def test_growth_returns_none_when_both_missing() -> None:
    assert growth(_snap()) is None


def test_big_call_full_weights() -> None:
    assert big_call(80.0, 60.0, 70.0) == 0.4 * 80 + 0.3 * 60 + 0.3 * 70


def test_big_call_renormalizes_when_dividend_missing() -> None:
    assert big_call(80.0, None, 80.0) == 80.0


def test_big_call_single_component() -> None:
    assert big_call(75.0, None, None) == 75.0


def test_big_call_returns_none_when_all_missing() -> None:
    assert big_call(None, None, None) is None


def test_aaqs_saturates_when_beta_zero() -> None:
    assert aaqs(80.0, 0.0) == 90.0


def test_aaqs_zero_low_vol_term_when_beta_at_max() -> None:
    assert aaqs(80.0, 2.0) == 40.0


def test_aaqs_returns_none_when_beta_missing() -> None:
    assert aaqs(80.0, None) is None


def test_aaqs_returns_none_when_quality_missing() -> None:
    assert aaqs(None, 1.0) is None


def test_hgi_saturates_with_margin_bonus() -> None:
    snap = _snap(
        revenue_growth=0.50, earnings_growth=0.50, operating_margins=0.30
    )
    assert hgi(snap) == 100.0


def test_hgi_no_bonus_below_margin_threshold() -> None:
    snap = _snap(
        revenue_growth=0.15, earnings_growth=0.15, operating_margins=0.05
    )
    assert hgi(snap) == 50.0


def test_hgi_bonus_above_margin_threshold() -> None:
    snap = _snap(
        revenue_growth=0.15, earnings_growth=0.15, operating_margins=0.15
    )
    assert hgi(snap) == 60.0


def test_hgi_returns_none_when_growth_missing() -> None:
    assert hgi(_snap(operating_margins=0.30)) is None


def test_screener_score_saturates_to_100() -> None:
    """All 9 visible inputs at their best bound -> 100."""
    snap = _snap(
        forward_pe=5.0,
        trailing_peg_ratio=0.0,
        beta=0.0,
        rd_to_revenue=0.20,
        operating_margins=0.30,
        return_on_equity=0.30,
        return_on_assets=0.15,
        current_ratio=3.0,
        sortino_ratio=3.0,
    )
    assert screener_score(snap) == 100.0


def test_screener_score_clamps_at_zero() -> None:
    """All 9 inputs at their worst bound -> 0."""
    snap = _snap(
        forward_pe=40.0,
        trailing_peg_ratio=3.0,
        beta=2.0,
        rd_to_revenue=0.0,
        operating_margins=0.0,
        return_on_equity=0.0,
        return_on_assets=0.0,
        current_ratio=1.0,
        sortino_ratio=0.0,
    )
    assert screener_score(snap) == 0.0


def test_screener_score_midpoint() -> None:
    """All 9 inputs at the midpoint of their range -> 50."""
    snap = _snap(
        forward_pe=22.5,
        trailing_peg_ratio=1.5,
        beta=1.0,
        rd_to_revenue=0.10,
        operating_margins=0.15,
        return_on_equity=0.15,
        return_on_assets=0.075,
        current_ratio=2.0,
        sortino_ratio=1.5,
    )
    assert screener_score(snap) == 50.0


def test_screener_score_returns_none_when_all_missing() -> None:
    """No visible inputs -> None (consistent with the existing composites)."""
    assert screener_score(_snap()) is None


def test_screener_score_partial_inputs_renormalized() -> None:
    """Partial-but-above-threshold inputs at HI -> mean of present terms.

    Exactly 5 inputs at their HI bound (meets ``_SCREENER_MIN_TERMS``)
    -> ``_mean([100] * 5) == 100``. Below the threshold the score
    would return ``None`` instead — that path is covered by
    ``test_screener_score_below_threshold_returns_none``.
    """
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        current_ratio=3.0,
        sortino_ratio=3.0,
    )
    assert screener_score(snap) == 100.0


def test_screener_score_below_threshold_returns_none() -> None:
    """Four inputs at their HI bound -> ``None``.

    Without the ``_SCREENER_MIN_TERMS`` threshold, mean-of-present-terms
    would yield ``_mean([100, 100, 100, 100]) == 100`` — a high score
    derived from only 4 of the 9 KPIs is misleading. The threshold
    guards informationally-thin tickers (mostly FX / futures / crypto
    / very sparse ADRs) from being ranked alongside fully-populated
    equities.
    """
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        current_ratio=3.0,
    )
    assert screener_score(snap) is None


def test_screener_score_drops_negative_forward_pe() -> None:
    """Loss-making company: ``forward_pe < 0`` drops the term.

    Five non-PE inputs all at midpoint (-> 50 each) plus a negative
    ``forward_pe`` that should be silently dropped (not saturated to
    100 via the inverted cheapness rescale). Mean of present terms =
    50; that the dropped negative-PE term doesn't pull the mean up
    is the load-bearing behaviour.
    """
    snap = _snap(
        forward_pe=-10.0,
        return_on_equity=0.15,
        return_on_assets=0.075,
        operating_margins=0.15,
        current_ratio=2.0,
        sortino_ratio=1.5,
    )
    assert screener_score(snap) == 50.0


def test_screener_score_profit_drops_when_only_one_input_present() -> None:
    """L1 within-factor: a sub-floor Profitability factor drops out.

    Profitability has 1 of 4 inputs present (ROE), below its ``>= 2``
    floor — the whole factor drops. Valuation / Risk / Momentum each
    saturate to 100. Five total inputs (>= the global 5/9 gate) ->
    composite = mean of the three present factor scores = 100.

    Old input-equal math: ``(0 + 100 + 100 + 100 + 100) / 5 == 80``.
    The new factor-weighted math returns 100 here; this test is the
    load-bearing distinguisher between the two compositions.
    """
    snap = _snap(
        return_on_equity=0.0,
        trailing_peg_ratio=0.0,
        beta=0.0,
        current_ratio=3.0,
        sortino_ratio=3.0,
    )
    assert screener_score(snap) == 100.0


def test_screener_score_factor_renormalizes_when_factor_missing() -> None:
    """L2 across factors: absent factors are dropped, not penalized.

    Profitability saturates to 100 (4 of 4 inputs at HI). Valuation
    saturates to 0 (forward_pe at the bad bound, 1 of 2 inputs meets
    the >= 1 floor). Risk and Momentum have zero inputs each -> both
    factors drop. Five total inputs meet the global >= 5/9 gate.

    Old input-equal math: ``(0 + 100 + 100 + 100 + 100) / 5 == 80``.
    New math averages only the two present factor scores:
    ``(100 + 0) / 2 == 50``.
    """
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        rd_to_revenue=0.20,
        forward_pe=40.0,
    )
    assert screener_score(snap) == 50.0


def test_compute_scores_full_snapshot() -> None:
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        debt_to_equity=0.0,
        dividend_yield=0.07,
        payout_ratio=0.5,
        revenue_growth=0.50,
        earnings_growth=0.50,
        beta=0.0,
        forward_pe=5.0,
        trailing_peg_ratio=0.0,
        rd_to_revenue=0.20,
        current_ratio=3.0,
        sortino_ratio=3.0,
    )
    scores = compute_scores(snap)
    assert scores.quality == 100.0
    assert scores.dividend == 100.0
    assert scores.growth == 100.0
    assert scores.big_call == 100.0
    assert scores.aaqs == 100.0
    assert scores.hgi == 100.0
    assert scores.screener_score == 100.0


def test_compute_scores_sparse_returns_all_none() -> None:
    scores = compute_scores(_snap())
    assert scores == CompositeScores()


def test_compute_scores_no_dividend_still_yields_big_call() -> None:
    snap = _snap(
        return_on_equity=0.30,
        return_on_assets=0.15,
        operating_margins=0.30,
        debt_to_equity=0.0,
        revenue_growth=0.50,
        earnings_growth=0.50,
    )
    scores = compute_scores(snap)
    assert scores.dividend is None
    assert scores.big_call == 100.0


def test_composite_scores_model_is_frozen() -> None:
    scores = CompositeScores(quality=80.0)
    try:
        scores.quality = 50.0  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("CompositeScores should be frozen")
