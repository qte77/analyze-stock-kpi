# ADR-0002 — Simplified composite proxy scores

**Status:** Accepted (2026-05-10) — amended 2026-06-06 (#192 Phase 2b: `fcf_margin` enrichment added to `FundamentalsSnapshot` to serve the long/short screener's criterion 12; the seven simplified composites themselves are unchanged)

**Amends:** [ADR-0000](0000-remove-traderfox.md) §Decision (composite proxies);
[ADR-0001](0001-defer-financetoolkit.md) §Accepted risks

**Drives:** [#18](https://github.com/qte77/analyze-stock-kpi/issues/18)

**Amended by:** [ADR-0004](0004-price-history-composite-input.md) (composite inputs extended to include price-history-derived `sortino_ratio`)

## Context

ADR-0000 specified that the v0.4.0 → v0.5.0 stack would replace
Traderfox's eight aggregate scores with documented composite formulas
in `composite_scores.py`. Issue #18 enumerates six target composites
and the textbook formulas behind them: Piotroski F-Score for Quality,
5-year ROIC stability, 5-year dividend CAGR, FCF / dividends coverage,
3-year and 5-year revenue/EPS CAGR, the GMG (Geberer / Mansfield /
Gartman) screen for HGI, and 52-week beta for AAQS.

`FundamentalsSnapshot` (shipped in v0.4.0 / PR #28) carries only
**point-in-time** fields from `yf.Ticker(t).info`: ROE, ROA, margins,
debt/equity, current/quick ratio, 1-year revenue and earnings growth,
dividend yield, payout ratio, EPS, book value, 52-week high/low. It
carries **no** financial-statement series, no dividend history, no
free cash flow, no per-period balance sheet. ADR-0001 defers
`financetoolkit` until a real need surfaces, leaving the textbook
formulas without their inputs.

## Decision

Implement all six composites in `src/composite_scores.py` using only
the point-in-time inputs already available, plus the cheap addition of
`info["beta"]`. Drop the trend / multi-year terms from each formula
and document the resulting simplifications in the module docstring and
function docstrings. Score every composite on `[0, 100]`. Return
`None` from any composite whose required inputs are unavailable.

This is **not a placeholder**. Simplified composites are the design.
A future PR may add `financetoolkit` and richer formulas if a real
use case demands them, but no such follow-up is committed by this ADR.

## Simplifications adopted

| Composite | Formula in #18 | Shipped formula |
|---|---|---|
| Quality | Piotroski F-Score + ROIC stability + margin stability | Mean of normalized ROE, ROA, operating margin, inverted D/E (negative-D/E term dropped) |
| Dividend | Yield + payout + 5y dividend CAGR + FCF coverage | Mean of normalized yield + payout-ratio sweet spot at ~0.5 |
| Growth | Revenue CAGR (3y/5y) + EPS CAGR + forward growth | Mean of normalized 1-year revenue growth + earnings growth (point-in-time proxies for CAGR) |
| Big Call | Weighted Quality + Dividend + Growth | Same. Reweights proportionally over non-`None` components |
| AAQS | Quality + low-volatility (52w beta) + ROIC consistency | Mean of `quality_score` + normalized low-beta term (yfinance ships 5-year monthly beta, not 52-week) |
| HGI | Revenue CAGR + GMG screen | Mean of normalized 1y growth components + fixed bonus when operating margin clears 10 % |

## Consequences

**Won:**

- Composites ship in v0.5.0 with no new dependencies — yfinance covers
  every input.
- Formulas are short, auditable, and tunable via named module-level
  domain bounds (`_ROE_HI`, `_GROWTH_HI`, etc.) rather than hidden
  magic numbers.
- Sparse-snapshot policy is uniform: each composite returns `None`
  when its inputs are missing, matching the existing `_format_*` "-"
  rendering pattern in `__main__.py`.

**Lost:**

- Quality is no longer Piotroski. A company with strong point-in-time
  ratios but poor multi-year trend (degrading ROA, leverage rising,
  share count diluting) scores higher than Piotroski would award.
- Dividend doesn't reward dividend growers — a flat-yield mature
  payer and a 10-year dividend grower score identically given the
  same point-in-time yield + payout.
- Growth is a 1-year proxy, more volatile than 3y/5y CAGR and noisier
  for cyclicals.
- AAQS uses 5-year monthly beta (yfinance default), not 52-week; the
  numerical surface differs from the issue text but the signal is the
  same direction.
- HGI bonus is fixed (10 points when op margin > 10 %), not the full
  rev + EPS + margin all-rising trend that the GMG screen describes.

**Accepted risks:**

- Composite numbers are not Traderfox numbers — explicitly out of
  scope per #18 and ADR-0000.
- Beta is missing for many non-US equities, low-history ETFs, and all
  non-equity quote types. AAQS returns `None` in those cases.
- Negative D/E (negative shareholder equity, common at distressed
  financials) drops the leverage term in Quality rather than producing
  a misleading bonus.

## Alternatives considered

- **Pull `financetoolkit` now per ADR-0001's escape hatch.** Rejected:
  ADR-0001's reasoning is unchanged. FT's `enforce_source="YahooFinance"`
  double-fetches statements yfinance has already returned, and the
  transitive cost (plotly etc.) is non-trivial. KISS / YAGNI.
- **Vendor a few formulas (Piotroski, CAGR helpers) into our codebase
  using `yf.Ticker.financials` / `.cashflow` / `.dividends`.** Rejected
  for v0.5.0 scope: those endpoints add per-ticker network calls and
  per-formula error surface. Worth revisiting only if user-facing
  output proves insufficient.
- **Defer composites entirely until FT lands.** Rejected: ships no
  value; ADR-0000 marked composites as a v0.5.0 deliverable.
- **Implement simplified composites and document them as deliberate.**
  Accepted (this ADR).

## References

- [#18](https://github.com/qte77/analyze-stock-kpi/issues/18) — composite
  proxy scores
- [`src/analyze_stock_kpi/domain/composite_scores.py`](../../src/analyze_stock_kpi/domain/composite_scores.py) — module
  docstring + per-function formulas
- [ADR-0000](0000-remove-traderfox.md) — original library-stack
  decision; "out of scope: replicating Traderfox values"
- [ADR-0001](0001-defer-financetoolkit.md) — `financetoolkit`
  escape-hatch reasoning, still applicable
