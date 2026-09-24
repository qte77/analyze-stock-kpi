# ADR-0013 — Point-in-time backfilled best/worst 25 + backtested long/short 25/25

**Status:** Accepted (2026-09-23) · **Supersedes in part** [ADR-0012](0012-longshort-model-portfolio.md)
(its "no backtest", Min-Variance-weighting, weekly/monthly-tracker and "no costs" decisions — see
"Supersession" below) · **Relates to:** [ADR-0004](0004-price-history-composite-input.md)
(price-history-derived composite inputs), [ADR-0011](0011-equity-macro-overlay-via-spy-indexed-returns.md)
(derived-only persistence precedent), [`docs/data-sources.md`](../data-sources.md) §"Redistribution
guardrails", plan [008](../plans/008-pit-longshort-backtest.md).

## Context

ADR-0012 shipped a forward-only, hypothetical Min-Variance long/short model portfolio over the
`aggregated-scores-best`/`-worst` pool. It explicitly rejected a backtest: "the pool comes from
today's scores, so a backtest would be survivorship- and look-ahead-biased by construction." That
premise held only because the *live* qte77 Score reads forward-looking-at-fetch-time fields
(`forward_pe`, `trailing_peg_ratio`, current `beta`) that cannot be reconstructed for a past date.
`portfolio.yaml` never actually ran (no data to migrate).

The owner now wants two things a Min-Variance forward tracker can't give: (1) a **backfilled**
best/worst 25 over past dates, ranked by the KPIs as they actually were on each date, and (2) a
**backtested** theoretical long/short book so the strategy's historical behaviour is visible, not
just its forward crawl. Removing the forward-looking score inputs (point-in-time fundamentals,
D2/D3) removes the specific look-ahead ADR-0012 objected to — survivorship and today's-universe
biases remain and are disclosed, not eliminated.

## Decision

1. **Scope (D1):** all base universes (every `PRESET_DIR/*.txt` except the derived
   `aggregated-scores-*`, `enhanced-kpi-screener-*` and `crypto-*` presets) = today's members,
   ~320 tickers. Survivorship bias and the `sp500` preset's "today's top-100-by-cap" size
   look-ahead are disclosed caveats, not eliminated.
2. **One reduced score for both the backfill and the cron (D2):** `score_bt = screener_score(snap_bt)`,
   where `snap_bt` is a `FundamentalsSnapshot` holding only the point-in-time-reconstructable
   inputs — `return_on_equity`, `return_on_assets`, `operating_margins`, `rd_to_revenue`,
   `current_ratio`, `sortino_ratio`. `forward_pe`, `trailing_peg_ratio` and `beta` are always
   `None`, so Valuation always drops and Risk degrades to the current ratio alone. The live
   `screener_score` function is reused unchanged — no seam, because the input set never changes.
   The live qte77 Score shown elsewhere on the dashboard is untouched.
3. **Point-in-time fundamentals (D3):** yfinance annual `income_stmt` + `balance_sheet` (~4-5 FY).
   A column is usable at date D iff `period_end + 90 days <= D` — yfinance exposes no filing
   dates, so this is a documented approximation of the real filing lag. Latest-restated (not
   as-originally-reported) values are a disclosed caveat.
4. **Sortino at D (D4)** = the existing `_compute_sortino` on the ticker's closes over `(D-1y, D]`.
5. **Book (D5):** 25 long / 25 short, equal-weight 1/25 each (gross 200%, net 0). Rank at the
   close of rank date t, trade at the close of the next trading day — no same-close look-ahead.
   Weights drift between rebalances. Local-currency returns (no FX modelled). A union trading
   calendar treats a non-trading day as a 0% return for that ticker; a name that stops trading
   after entry is held at its last known close.
6. **Rank grid = weekly (D6):** the last trading day of each ISO week. The backfill starts at the
   first grid date with >= 200 eligible tickers (`score_bt` not `None` and >= 1y of closes) —
   computed, not asserted; verified via a full local run to land at 2023-03-31, driven by
   yfinance's ~4-5 FY statement window rather than by price-history depth.
7. **Five cadences, all on the weekly grid (D7):** monthly (**primary**), quarterly-after-filings
   (first grid date on/after Feb 15 / May 15 / Aug 15 / Nov 15), monthly-with-buffer (a holding
   stays while its rank is within 40 of its own end, refilled from the top ranks), weekly, and
   buy-and-hold (rank once at inception). Presented as one table with the primary highlighted,
   never a sortable leaderboard — the point is to show one recommended default, not invite
   cadence-shopping.
8. **Costs (D8):** 10 bp x one-way turnover (½ Σ|w_new − w_drifted| over both legs), charged on the
   trade day. Both gross and net are published so the cost's impact is visible, not hidden.
9. **Metrics per cadence, gross + net (D9):** annualized return, vol, max drawdown, annualized
   one-way turnover, long/short leg annualized returns, realized beta to SPY, monthly hit rate,
   mean monthly return with a 90% CI and t-stat. Nothing is annualized from under 12 months of
   monthly returns.
10. **Null benchmark (D10, default):** 1,000 seeded random 25/25 books drawn from the same eligible
    set on the primary cadence's rank dates; the strategy's net-return percentile within that
    distribution is published, so a reader can judge whether the ranking itself adds value beyond
    "any 25/25 long/short book in this universe."
11. **Fidelity (D11, default):** on every genuine `data`-branch demo snapshot date, the Spearman
    rho between `score_bt` and the live `screener_score` (median across dates published) — a
    sanity check that the point-in-time reduction still tracks the live composite reasonably well.
12. **Drop Min-Variance + scipy (D12):** `domain/portfolio_optimizer.py`,
    `orchestrators/longshort_portfolio.py`, their tests, and the `portfolio` optional extra are
    deleted. `scipy` is no longer a dependency anywhere in the repo — Spearman correlation (D11)
    verified to work via pandas without it.
13. **Cron (D13, default):** `portfolio.yaml` now runs
    `python -m analyze_stock_kpi.orchestrators.longshort_backtest` Saturdays 12:00 UTC (no other
    data-branch writer runs then), doing a full deterministic recompute every run (stateless,
    idempotent) rather than advancing incremental state.
14. **This ADR (D14)** supersedes ADR-0012's "no backtest", Min-Variance-weighting,
    weekly/monthly-tracker and "no costs" decisions.

## Frozen data contract

See plan [008](../plans/008-pit-longshort-backtest.md) §"Frozen data contract" for the exact JSON
shapes: `results/series/backtest/<cadence>/YYYY.json` (daily gross/net rows), `results/backtest/lists/YYYY.json`
(the backfilled best/worst 25 per weekly rank date), `results/backtest/summary.json` (metrics,
null benchmark, fidelity, caveats).

## Consequences

- New module `orchestrators/longshort_backtest.py` replaces
  `domain/portfolio_optimizer.py` + `orchestrators/longshort_portfolio.py`; the dashboard's
  `#portfolio-section` is replaced by a backtest section (PR D).
- `scipy` and the `portfolio` extra are gone; `setup_dev`/CI installs are back to the plain
  default-group `uv sync`.
- The backfill is a genuinely historical view (best/worst 25 *as they were*, not just *as they are
  today, applied retroactively*) — a materially different and more defensible artifact than
  ADR-0012's forward-only tracker.
- Survivorship bias and the `sp500` size look-ahead remain; they are disclosed in
  `summary.caveats` rather than eliminated, since eliminating them (true historical index
  constituents) is out of scope for a yfinance-only pipeline.
- Statement fetches only reach back ~4-5 FY per yfinance call; the point-in-time backfill's start
  date is bounded by that window, not by price-history depth (verified via a full local run:
  2023-03-31). A local statement cache under the
  gitignored `results/prices/statements/<ticker>/<fetch-date>.json` accumulates one immutable
  snapshot per fetch date, merged first-fetch-wins per period — a future PR may sync this
  directory to a private repo so the effective statement history outgrows the live ~4-5 FY window
  without ever committing raw Yahoo data to `data`.

## Alternatives considered

- **Keep the Min-Variance forward tracker, add a separate backtest module:** rejected — two
  scoring formulas (live-multi-input vs. point-in-time-only) for the same "qte77 Score" concept
  would confuse the dashboard's single-Score narrative established by #398. One reduced score
  (D2), reused everywhere the backtest needs a score, is simpler and honest about what a backtest
  can and can't reconstruct.
- **True historical index constituents (eliminate survivorship bias):** rejected for this
  iteration — no free, keyless source of historical S&P 500 / regional-index membership exists in
  the current pipeline; disclosed as a caveat instead of blocking on new data-source work.
- **Filing-date-aware usability (US SEC-XBRL `filed` dates) instead of the +90-day heuristic:**
  deferred — would extend the true-not-restated start date to ~2017 for US tickers only; tracked
  as a follow-up in plan 008's remaining-work table, not blocking this ADR.
- **Keep scipy for a hybrid weighting scheme:** rejected — equal-weight 1/25 (D5) is simpler,
  transparent, and doesn't reintroduce ADR-0012's covariance-estimation-error concerns for a
  *backtested* book where the weighting scheme itself becomes part of what's being tested.
