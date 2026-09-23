"""Joint dollar-neutral Min Variance optimizer (ADR-0012 D4).

For the long/short model portfolio. Pure numpy + scipy — no pandas, no I/O.
``scipy`` is an optional runtime dependency
(``[project.optional-dependencies] portfolio``); this module is the only
place that imports it, and callers import this module lazily so the core
CLI's install stays scipy-free.

Public API:

- :func:`shrunk_covariance` — sample covariance of daily returns, shrunk
  toward its diagonal (fixed intensity), annualized.
- :func:`min_variance_longshort` — joint Min Variance over the combined
  long + short vector, each leg summing to 1 (gross 200 %, net 0).
- :func:`ex_ante_vol` — annualized ex-ante volatility of a signed weight
  vector under a given covariance matrix.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

_SHRINKAGE_DELTA = 0.3
"""Diagonal shrinkage intensity (ADR-0012 D4) — fixed, not estimated. Higher
values pull the sample covariance's off-diagonal (correlation) terms harder
toward zero while leaving the diagonal (per-asset variance) unchanged."""

_TRADING_DAYS = 252
"""Trading-day annualization factor, matching `fundamentals._TRADING_DAYS`."""

_MIN_LEG_CAP = 0.10
"""Per-name weight cap floor (ADR-0012 D4): `max(0.10, 1/n)`."""


class OptimizationError(RuntimeError):
    """Raised when the SLSQP solve does not converge."""


def shrunk_covariance(returns: np.ndarray, *, delta: float = _SHRINKAGE_DELTA) -> np.ndarray:
    """Annualized covariance of daily returns, shrunk toward its diagonal.

    Args:
        returns: ``(T, N)`` array of daily simple returns, one column per
            asset (``T`` trading days, ``N`` assets).
        delta: Diagonal shrinkage intensity in ``[0, 1]``. ``new = (1 -
            delta) * S + delta * diag(S)`` — variances are unchanged;
            covariances (off-diagonal) shrink toward zero by ``(1 -
            delta)``. ADR-0012 D4 fixes this at 0.3.

    Returns:
        ``(N, N)`` annualized (x252) shrunk covariance matrix.
    """
    sample = np.atleast_2d(np.cov(returns, rowvar=False))
    diag_only = np.diag(np.diag(sample))
    shrunk = (1 - delta) * sample + delta * diag_only
    return shrunk * _TRADING_DAYS


def _leg_cap(n: int) -> float:
    return max(_MIN_LEG_CAP, 1.0 / n)


def min_variance_longshort(
    cov: np.ndarray, n_long: int, n_short: int
) -> tuple[np.ndarray, np.ndarray]:
    """Joint dollar-neutral Min Variance over long + short legs (ADR-0012 D4).

    Optimizes the combined signed vector ``x_full = [w_long, -w_short]`` so
    cross-leg correlation can hedge the spread — optimizing each leg alone
    would ignore that correlation and leave net beta uncontrolled.

    Args:
        cov: ``(n_long + n_short, n_long + n_short)`` annualized covariance,
            long assets first, then short assets (matching `shrunk_covariance`).
        n_long: Number of long candidates.
        n_short: Number of short candidates.

    Returns:
        ``(w_long, w_short)`` — each a 1-D array of nonnegative weights
        summing to 1, bounded by ``[0, max(0.10, 1/n)]`` per name.

    Raises:
        ValueError: if `cov`'s shape doesn't match `n_long + n_short`.
        OptimizationError: if the SLSQP solve does not converge.
    """
    n = n_long + n_short
    if cov.shape != (n, n):
        raise ValueError(f"cov shape {cov.shape} != ({n}, {n})")
    sign = np.concatenate([np.ones(n_long), -np.ones(n_short)])

    def objective(x: np.ndarray) -> float:
        full = x * sign
        return float(full @ cov @ full)

    constraints = [
        {"type": "eq", "fun": lambda x: np.sum(x[:n_long]) - 1.0},
        {"type": "eq", "fun": lambda x: np.sum(x[n_long:]) - 1.0},
    ]
    bounds = [(0.0, _leg_cap(n_long))] * n_long + [(0.0, _leg_cap(n_short))] * n_short
    x0 = np.concatenate([np.full(n_long, 1.0 / n_long), np.full(n_short, 1.0 / n_short)])

    res = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not res.success:
        raise OptimizationError(f"min-variance optimization failed: {res.message}")
    return res.x[:n_long], res.x[n_long:]


def ex_ante_vol(cov: np.ndarray, x: np.ndarray) -> float:
    """Annualized ex-ante volatility of a signed weight vector under `cov`.

    Args:
        cov: Annualized covariance matrix (see `shrunk_covariance`).
        x: Signed combined weight vector, e.g. ``concatenate([w_long,
            -w_short])`` — the caller applies the leg sign.

    Returns:
        ``sqrt(x @ cov @ x)``.
    """
    return float(np.sqrt(x @ cov @ x))
