# ADR-0012 — Hypothetical long/short model portfolio over the aggregated best/worst lists

**Status:** Accepted (2026-09-22) · **Supersedes** [ADR-0003](0003-defer-rs-hedging-epic.md)
(for the portfolio-tracking scope only — ADR-0003's RS-signal survey stays the
reference for any future relative-strength work) · **Amends**
[ADR-0005](0005-sentiment-risk-sources.md) §"NOT a hedging primitive"

**Relates to:** [ADR-0004](0004-price-history-composite-input.md) (price history
is already a runtime input), [ADR-0011](0011-equity-macro-overlay-via-spy-indexed-returns.md)
(derived-only persistence precedent), [`docs/data-sources.md`](../data-sources.md)
§"Redistribution guardrails", plan
[007](../plans/007-longshort-portfolio-and-multiwindow-sortino.md).

## Context

ADR-0003 deferred long/short hedging analytics to a sibling repo because the repo
was then a point-in-time fundamentals CLI without pandas or price history, and there
was no product reason to widen its scope. Both premises have since changed:

- pandas and daily price history are already runtime inputs (ADR-0004 Sortino,
  ADR-0011 SPY series).
- The owner now wants a concrete product feature: track a **hypothetical long/short
  sample portfolio** — long the `aggregated-scores-best` list, short the
  `aggregated-scores-worst` list — with real prices, weighted by a
  portfoliovisualizer.com-style optimizer (Min Variance first; Max Sharpe, Min CVaR,
  Min Drawdown later). The owner chose to build it in this repo rather than a sibling.

ADR-0005 says the best/worst lists are "a meta-screening starting point, not a
long-candidate set". That remains true of the *lists*; this ADR uses them only as a
**candidate pool**. The optimizer, not the list order, sets the positions.

## Decision

1. **Scope:** a forward-only, hypothetical, dollar-neutral long/short model
   portfolio. **No backtest** is published. The first point is the inception date,
   so there is no look-ahead or survivorship bias to explain.
2. **Pool vs weights are decoupled.** The candidate pool (best list → long leg,
   worst list → short leg) is frozen for 90 days. Weights are re-optimized on each
   cadence. Two portfolios are tracked in parallel: **weekly** and **monthly**
   rebalance.
3. **Optimizer v1 = joint Min Variance** over the combined vector `x = [w_long, −w_short]`,
   each leg summing to 1 (gross 200 %, net 0), per-name cap `max(0.10, 1/n)`,
   `scipy.optimize.minimize(method="SLSQP")`. Covariance is the sample covariance of
   daily returns over the trailing ~3 years (756 trading days), **shrunk toward its
   own diagonal with a fixed intensity `δ = 0.3`** — `(1 − δ)·S + δ·diag(S)`, plain
   numpy, a documented constant rather than an estimated one (no scikit-learn /
   Ledoit-Wolf: scipy is the only new dependency, per the owner's 2026-09-22 KISS
   pass) — then annualized ×252. The legs are optimized **jointly**, so cross-leg
   correlation hedges the spread. Optimizing each leg alone would ignore that
   correlation and leave net beta uncontrolled. Sample-mean Max Sharpe is **not**
   used: it maximizes estimation error. Future Max Sharpe uses composite-rank-derived
   expected returns instead.
4. **Persistence is derived-only** (per ADR-0011 and the data-sources guardrails):
   the public `data` branch gets **weekly returns and target weights only — never a
   stored NAV series** (owner, 2026-09-23). Each cron run appends one
   `{date, ret_long, ret_short, ret_ls}` row per cadence; the dashboard compounds
   those returns client-side into a 100-based index line. **Raw prices are never
   committed.** They are held in memory and, when run locally, written to a
   gitignored cache (`results/prices/`, same posture as `results/edgar/`).
5. **The only new dependency is `scipy`** (optional): `[project.optional-dependencies]
   portfolio = ["scipy>=1.14"]`. The core CLI's install is unchanged. The shrinkage
   estimator (decision 3) is plain numpy, already transitive via pandas/yfinance —
   no scikit-learn dependency.
6. **No transaction-cost model.** Returns are gross, in local currency; costs, FX,
   financing and borrow are not modelled — stated in the dashboard's disclaimer
   alongside "not investment advice" and the inception date.
7. **Weekly returns use last week's *target* weights** (an implicit weekly
   reset-to-target, since no intra-month drift is tracked between rebalances). This
   approximation is noted once in the UI caveat.
8. **Presentation:** the dashboard labels it a *hypothetical model portfolio*, shows
   "not investment advice", and states decisions 6 and 7 plus the inception date.

## Consequences

- New module (`domain/portfolio_optimizer.py` and `orchestrators/longshort_portfolio.py`),
  cron workflow, and dashboard section. The optional `portfolio` extra adds `scipy`
  only for CI and portfolio runs.
- ADR-0003's "no pandas / sibling repo" stance no longer applies to this scope;
  its RS survey remains valid reference material.
- The compounded index is a model result, not a track record. With no backtest, the
  chart starts flat and gains meaning over months. That is accepted, because it is
  honest.
- No stored NAV means the chart's history depends entirely on the on-disk return
  series staying intact; a lost or truncated series file cannot be recomputed
  without the (never-committed) raw prices from that week. Accepted — the same
  posture as every other derived-only series in this repo (e.g. `equity_spy`).

## Alternatives considered

- **Sibling repo (ADR-0003's future home):** rejected by the owner. The data,
  presets and dashboard already live here.
- **Per-leg Max Sharpe, then combine:** rejected. It ignores cross-leg covariance,
  leaves net beta uncontrolled, and sample means maximize error.
- **Ledoit-Wolf shrinkage (scikit-learn):** rejected in the owner's 2026-09-22 KISS
  pass in favor of a fixed-intensity diagonal shrinkage in plain numpy — scipy stays
  the only new dependency, and a documented constant is easier to reason about than
  an estimated shrinkage target for a v1 optimizer.
- **A flat per-rebalance transaction-cost charge:** considered, then dropped
  (owner, 2026-09-23) — the model is already gross-of-costs and unhedged for
  FX/financing/borrow, so a partial cost model would suggest more precision than
  the rest of the model supports.
- **Backtest from 3–5 years of history:** rejected. The pool comes from today's
  scores, so a backtest would be survivorship- and look-ahead-biased by
  construction.
- **PortfolioVisualizer API:** none exists (verified 2026-09-21). The
  optimization is computed locally.
