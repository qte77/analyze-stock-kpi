"""Tests for :mod:`analyze_stock_kpi.domain.portfolio_optimizer` (ADR-0012).

Non-trivial cases only: the diagonal-shrinkage transform, the joint
dollar-neutral Min Variance solve (leg-sum + bound constraints, and that a
near-perfect long/short hedge pair gets upweighted relative to equal-weight),
and the ex-ante-vol helper. No network, no I/O.
"""

from __future__ import annotations

import numpy as np
import pytest

from analyze_stock_kpi.domain.portfolio_optimizer import (
    OptimizationError,
    ex_ante_vol,
    min_variance_longshort,
    shrunk_covariance,
)

# ----- shrunk_covariance -----


def test_shrunk_covariance_preserves_diagonal_and_shrinks_offdiagonal() -> None:
    """Variances (diagonal) are untouched; covariances shrink by (1 - delta)."""
    rng = np.random.default_rng(7)
    returns = rng.normal(size=(300, 3))
    sample = np.cov(returns, rowvar=False)

    shrunk = shrunk_covariance(returns, delta=0.3)

    assert shrunk.shape == (3, 3)
    np.testing.assert_allclose(np.diag(shrunk), np.diag(sample) * 252, rtol=1e-9)
    off_i, off_j = 0, 1
    np.testing.assert_allclose(
        shrunk[off_i, off_j], sample[off_i, off_j] * 0.7 * 252, rtol=1e-9
    )


def test_shrunk_covariance_default_delta_matches_adr_0012() -> None:
    """The documented ADR-0012 D4 constant (0.3) is the default, not just an option."""
    rng = np.random.default_rng(11)
    returns = rng.normal(size=(100, 2))

    default = shrunk_covariance(returns)
    explicit = shrunk_covariance(returns, delta=0.3)

    np.testing.assert_allclose(default, explicit)


def test_shrunk_covariance_handles_single_asset() -> None:
    """`np.cov` returns a 0-d scalar for a single column; must not crash."""
    returns = np.array([[0.01], [-0.02], [0.03], [0.0]])
    shrunk = shrunk_covariance(returns)
    assert shrunk.shape == (1, 1)
    assert shrunk[0, 0] > 0


# ----- min_variance_longshort -----


def _identity_with_hedge_pair(n_long: int, n_short: int, corr: float = 0.95) -> np.ndarray:
    """Unit-variance covariance where long[0] and short[0] are near-perfectly
    correlated (a clean hedge pair) and every other asset is independent.
    """
    n = n_long + n_short
    cov = np.eye(n)
    cov[0, n_long] = corr
    cov[n_long, 0] = corr
    return cov


def test_each_leg_sums_to_one_and_respects_bounds() -> None:
    n_long, n_short = 12, 12
    cov = _identity_with_hedge_pair(n_long, n_short)

    w_long, w_short = min_variance_longshort(cov, n_long, n_short)

    assert w_long.shape == (n_long,)
    assert w_short.shape == (n_short,)
    assert np.sum(w_long) == pytest.approx(1.0, abs=1e-6)
    assert np.sum(w_short) == pytest.approx(1.0, abs=1e-6)
    cap = max(0.10, 1 / n_long)
    assert np.all(w_long >= -1e-9)
    assert np.all(w_long <= cap + 1e-6)
    assert np.all(w_short >= -1e-9)
    assert np.all(w_short <= cap + 1e-6)


def test_hedge_pair_gets_upweighted_and_lowers_ex_ante_vol() -> None:
    """A long/short pair that near-perfectly cancels risk should be pushed
    toward its per-name cap, and the resulting ex-ante vol should beat
    equal-weight (ADR-0012 D4's rationale for joint, not per-leg, optimization).
    """
    n_long, n_short = 12, 12
    cov = _identity_with_hedge_pair(n_long, n_short)

    w_long, w_short = min_variance_longshort(cov, n_long, n_short)

    assert w_long[0] > np.mean(w_long[1:])
    assert w_short[0] > np.mean(w_short[1:])

    x_opt = np.concatenate([w_long, -w_short])
    equal_long = np.full(n_long, 1 / n_long)
    equal_short = np.full(n_short, 1 / n_short)
    x_equal = np.concatenate([equal_long, -equal_short])

    assert ex_ante_vol(cov, x_opt) < ex_ante_vol(cov, x_equal)


def test_shape_mismatch_raises_value_error() -> None:
    with pytest.raises(ValueError, match="cov shape"):
        min_variance_longshort(np.eye(3), n_long=2, n_short=2)


def test_infeasible_problem_raises_optimization_error() -> None:
    """A NaN-poisoned covariance can't be optimized — surfaces as a clear
    `OptimizationError` rather than a silent bad result."""
    cov = np.full((4, 4), np.nan)
    with pytest.raises(OptimizationError):
        min_variance_longshort(cov, n_long=2, n_short=2)


# ----- ex_ante_vol -----


def test_ex_ante_vol_of_zero_weights_is_zero() -> None:
    cov = np.eye(4)
    assert ex_ante_vol(cov, np.zeros(4)) == pytest.approx(0.0)


def test_ex_ante_vol_matches_hand_computation() -> None:
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    x = np.array([0.5, -0.5])
    expected = float(np.sqrt(x @ cov @ x))
    assert ex_ante_vol(cov, x) == pytest.approx(expected)
