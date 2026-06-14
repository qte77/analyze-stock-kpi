"""Composite proxy scores derived from a `FundamentalsSnapshot`.

The proxy scores are inspired by the Traderfox aggregate scores
referenced in issue #18. Formulas are intentionally simplified: each
composite uses only point-in-time fields on `FundamentalsSnapshot`
plus ``beta`` from yfinance info, with `screener_score` also reading
the price-history-derived `sortino_ratio` (see ADR-0004). Multi-year
trend formulas (Piotroski, ROIC stability, 5y CAGR, FCF coverage)
are deliberately deferred — see
``docs/decisions/0002-simplified-composites.md``.

Public API:
    - :class:`CompositeScores` — frozen pydantic model holding the
      proxy scores.
    - :func:`compute_scores` — entry point that takes a
      `FundamentalsSnapshot` and returns a fully-populated
      :class:`CompositeScores`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot


_ROE_LO, _ROE_HI = 0.0, 0.30
_ROA_LO, _ROA_HI = 0.0, 0.15
_OP_MARGIN_LO, _OP_MARGIN_HI = 0.0, 0.30
_DE_LO, _DE_HI = 0.0, 200.0
_YIELD_LO, _YIELD_HI = 0.0, 0.07
_GROWTH_LO, _GROWTH_HI = -0.20, 0.50
_BETA_LO, _BETA_HI = 0.0, 2.0

_FORWARD_PE_LO, _FORWARD_PE_HI = 5.0, 40.0
_PEG_LO, _PEG_HI = 0.0, 3.0
_RD_REV_LO, _RD_REV_HI = 0.0, 0.20
_CURRENT_LO, _CURRENT_HI = 1.0, 3.0
_SORTINO_LO, _SORTINO_HI = 0.0, 3.0
_SCREENER_MIN_TERMS = 5
_PROFIT_MIN = 2  # of 4 profitability inputs
_VALUE_MIN = 1  # of 2 valuation inputs
_RISK_MIN = 1  # of 2 risk inputs
_MOMENT_MIN = 1  # of 1 momentum input

_HGI_MARGIN_THRESHOLD = 0.10
_HGI_MARGIN_BONUS = 10.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _rescale(value: float, lo: float, hi: float) -> float:
    """Linear rescale of ``value`` clamped to ``[lo, hi]`` into ``[0, 100]``."""
    return (_clamp(value, lo, hi) - lo) / (hi - lo) * 100


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _factor_mean(*norm_values: float | None, min_inputs: int) -> float | None:
    """Mean of non-``None`` inputs; ``None`` if fewer than ``min_inputs`` present."""
    present = [v for v in norm_values if v is not None]
    return _mean(present) if len(present) >= min_inputs else None


class CompositeScores(BaseModel):
    """Seven 0-100 proxy scores derived from a single `FundamentalsSnapshot`.

    Any score is ``None`` when its required inputs were unavailable.
    ``big_call`` reweights proportionally over its non-``None`` components
    so a tech stock with no dividend still receives a robustness score.
    ``screener_score`` aggregates the visible main-table KPIs (see
    `docs/decisions/0004-price-history-composite-input.md`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    quality: float | None = None
    dividend: float | None = None
    growth: float | None = None
    big_call: float | None = None
    aaqs: float | None = None
    hgi: float | None = None
    screener_score: float | None = None


def quality(snap: FundamentalsSnapshot) -> float | None:
    """Average of normalized ROE, ROA, operating margin, inverted D/E.

    Negative D/E (negative shareholder equity) drops the leverage term;
    the score is averaged over the remaining three. Returns ``None`` when
    all four inputs are unavailable.
    """
    terms: list[float] = []
    if snap.return_on_equity is not None:
        terms.append(_rescale(snap.return_on_equity, _ROE_LO, _ROE_HI))
    if snap.return_on_assets is not None:
        terms.append(_rescale(snap.return_on_assets, _ROA_LO, _ROA_HI))
    if snap.operating_margins is not None:
        terms.append(_rescale(snap.operating_margins, _OP_MARGIN_LO, _OP_MARGIN_HI))
    if snap.debt_to_equity is not None and snap.debt_to_equity >= 0:
        terms.append(100 - _rescale(snap.debt_to_equity, _DE_LO, _DE_HI))
    return _mean(terms) if terms else None


def dividend(snap: FundamentalsSnapshot) -> float | None:
    """Yield + payout-ratio sweet spot. Tilts toward ~50% payout.

    Returns ``None`` when both yield and payout ratio are unavailable.
    """
    terms: list[float] = []
    if snap.dividend_yield is not None:
        terms.append(_rescale(snap.dividend_yield, _YIELD_LO, _YIELD_HI))
    if snap.payout_ratio is not None:
        sweet_spot = max(0.0, 1 - 2 * abs(snap.payout_ratio - 0.5))
        terms.append(sweet_spot * 100)
    return _mean(terms) if terms else None


def growth(snap: FundamentalsSnapshot) -> float | None:
    """Average of point-in-time revenue growth + earnings growth.

    Each component clamped to ``[_GROWTH_LO, _GROWTH_HI]`` and rescaled
    linearly. Returns ``None`` when both growth fields are unavailable.
    """
    terms: list[float] = []
    if snap.revenue_growth is not None:
        terms.append(_rescale(snap.revenue_growth, _GROWTH_LO, _GROWTH_HI))
    if snap.earnings_growth is not None:
        terms.append(_rescale(snap.earnings_growth, _GROWTH_LO, _GROWTH_HI))
    return _mean(terms) if terms else None


def big_call(
    quality_score: float | None,
    dividend_score: float | None,
    growth_score: float | None,
) -> float | None:
    """Weighted Quality/Dividend/Growth with proportional reweighting.

    Default weights 0.4 / 0.3 / 0.3. Missing components are dropped and
    the remaining weights renormalize. Returns ``None`` only when all
    three inputs are ``None``.
    """
    pairs: list[tuple[float, float]] = []
    if quality_score is not None:
        pairs.append((quality_score, 0.4))
    if dividend_score is not None:
        pairs.append((dividend_score, 0.3))
    if growth_score is not None:
        pairs.append((growth_score, 0.3))
    if not pairs:
        return None
    total_weight = sum(w for (_, w) in pairs)
    return sum(s * w for (s, w) in pairs) / total_weight


def aaqs(quality_score: float | None, beta: float | None) -> float | None:
    """Quality combined with low-volatility (low beta is better).

    Returns ``None`` when either input is unavailable — without beta this
    composite would degenerate to ``quality_score`` alone, which is
    already its own score.
    """
    if quality_score is None or beta is None:
        return None
    low_vol = _rescale(_BETA_HI - beta, _BETA_LO, _BETA_HI)
    return _mean([quality_score, low_vol])


def hgi(snap: FundamentalsSnapshot) -> float | None:
    """Growth-tilted approximation of Traderfox's GMG screen.

    Average of normalized revenue + earnings growth plus a fixed bonus
    when operating margin clears ``_HGI_MARGIN_THRESHOLD``. Returns
    ``None`` when both growth components are unavailable.
    """
    terms: list[float] = []
    if snap.revenue_growth is not None:
        terms.append(_rescale(snap.revenue_growth, _GROWTH_LO, _GROWTH_HI))
    if snap.earnings_growth is not None:
        terms.append(_rescale(snap.earnings_growth, _GROWTH_LO, _GROWTH_HI))
    if not terms:
        return None
    score = _mean(terms)
    if snap.operating_margins is not None and snap.operating_margins > _HGI_MARGIN_THRESHOLD:
        score = min(100.0, score + _HGI_MARGIN_BONUS)
    return score


def _normalize_term(
    value: float | None, lo: float, hi: float, *, invert: bool = False
) -> float | None:
    """Rescale ``value`` to ``[0, 100]`` clamped to ``[lo, hi]``.

    Returns ``None`` when ``value`` is ``None``. When ``invert=True``
    returns ``100 - rescaled`` so low input values produce high scores
    (used for cheapness / risk metrics where lower is better).
    """
    if value is None:
        return None
    raw = _rescale(value, lo, hi)
    return 100 - raw if invert else raw


def screener_score(snap: FundamentalsSnapshot) -> float | None:
    """Factor-weighted 0-100 composite of the 9 visible main-table KPIs.

    The 9 KPIs group into four thematic factors and the composite is
    the mean of the factor scores — so every dimension has equal voice
    when present:

    - Profitability (ROE, ROA, Op margin, R&D/Rev) — needs >= 2 of 4
    - Valuation (forward P/E, PEG) — needs >= 1 of 2
    - Risk (Beta, Current ratio) — needs >= 1 of 2
    - Momentum (Sortino) — needs 1 of 1

    Missing inputs are handled at three layers. L1 within a factor:
    factors below their input minimum drop. L2 across factors: dropped
    factors are removed and the remaining factors weigh equally
    (drop-and-renormalize). L3 global: total non-``None`` inputs across
    all 9 KPIs must reach ``_SCREENER_MIN_TERMS`` (5) or the composite
    returns ``None`` — guards informationally-thin tickers (FX /
    futures / crypto / sparse ADRs) from ranking alongside fully-
    populated equities.

    Negative ``forward_pe`` (loss-making companies) drops the term
    rather than rewarding it via the inverted cheapness rescale.
    """
    forward_pe = snap.forward_pe if snap.forward_pe is None or snap.forward_pe > 0 else None
    profitability = [
        _normalize_term(snap.return_on_equity, _ROE_LO, _ROE_HI),
        _normalize_term(snap.return_on_assets, _ROA_LO, _ROA_HI),
        _normalize_term(snap.operating_margins, _OP_MARGIN_LO, _OP_MARGIN_HI),
        _normalize_term(snap.rd_to_revenue, _RD_REV_LO, _RD_REV_HI),
    ]
    valuation = [
        _normalize_term(forward_pe, _FORWARD_PE_LO, _FORWARD_PE_HI, invert=True),
        _normalize_term(snap.trailing_peg_ratio, _PEG_LO, _PEG_HI, invert=True),
    ]
    risk = [
        _normalize_term(snap.beta, _BETA_LO, _BETA_HI, invert=True),
        _normalize_term(snap.current_ratio, _CURRENT_LO, _CURRENT_HI),
    ]
    momentum = [
        _normalize_term(snap.sortino_ratio, _SORTINO_LO, _SORTINO_HI),
    ]
    all_terms = profitability + valuation + risk + momentum
    if sum(1 for t in all_terms if t is not None) < _SCREENER_MIN_TERMS:
        return None
    factor_scores = [
        _factor_mean(*profitability, min_inputs=_PROFIT_MIN),
        _factor_mean(*valuation, min_inputs=_VALUE_MIN),
        _factor_mean(*risk, min_inputs=_RISK_MIN),
        _factor_mean(*momentum, min_inputs=_MOMENT_MIN),
    ]
    present_factors = [s for s in factor_scores if s is not None]
    return _mean(present_factors) if present_factors else None


def compute_scores(snap: FundamentalsSnapshot) -> CompositeScores:
    """Compute every composite for a single snapshot."""
    q = quality(snap)
    d = dividend(snap)
    g = growth(snap)
    return CompositeScores(
        quality=q,
        dividend=d,
        growth=g,
        big_call=big_call(q, d, g),
        aaqs=aaqs(q, snap.beta),
        hgi=hgi(snap),
        screener_score=screener_score(snap),
    )
