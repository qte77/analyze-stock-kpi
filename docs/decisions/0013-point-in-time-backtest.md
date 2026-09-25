# ADR-0013 — Point-in-time backfilled best/worst 25 + backtested long/short 25/25

**Status:** Accepted (2026-09-23) · **Amended in part by [ADR-0014](0014-current-candidates-use-live-score.md)**
(D2's reduced score is no longer the dashboard's "current candidates" source — narrowed to the historical
backfill + backtested returns simulation only) · **Supersedes in part** [ADR-0012](0012-longshort-model-portfolio.md)
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

## Amendment (2026-09-24) — series A, freeze, filing lag (D15-D19, plan 008 PR E)

PR C's first run ([#404](https://github.com/qte77/analyze-stock-kpi/pull/404)) exposed two gaps
in the original decision: the backfill (now "series B") is a *reconstruction*, not a record of
what a real viewer actually saw; and D13's "full deterministic recompute" silently rewrites
history on every run, which is unsafe once yfinance's restated figures or a bug fix can change a
past value. It also shipped a start-trim bug: `simulate` marks every day in the full
union-of-price-history calendar (back to 1962 for some tickers) rather than the book's own
inception, so every published metric was diluted by ~15.7k padding days (published ann. vol
4.96%, hit rate 2.8%, vs. ~21.2% ann. vol over the real 907-day window).

1. **Two series, never spliced (D15):** series B (this ADR's original decision, D1-D14) stays the
   *reconstructed* backfill, explicitly labelled an approximation. A new **series A** is the
   *genuine* record — the actual best/worst 25 a real dashboard viewer would have seen, computed
   with the actual live qte77 Score, on the actual dates it was computed. The two are never drawn
   as one continuous line or spliced end to end.
2. **Series A (D16):** each rank date is a genuine `data`-branch snapshot date — a date every D1
   base universe has a `results/demo/<universe>/<date>.json` file (from 2026-05-31, when the 7th
   base universe's demo cron came online). Ranked with the **full live qte77 Score** (all 9
   `screener_score` inputs, no fields forced to `None`) by reusing
   `aggregated_scores_best_and_worst.build_universe` **unchanged** — the same dedup + 14-day
   staleness gate the live dashboard lists use. Trade date is the first trading day strictly after
   the rank date (conservative: snapshots fetch ~06:15 UTC, after Asian closes). The book holds
   across a snapshot gap (e.g. 2026-07-12 -> 2026-09-21); disclosed, not hidden. No null benchmark
   or fidelity check for series A until it has >= 12 monthly rebalances — both stay `null` in the
   interim per the frozen contract.
3. **Freeze, append-only, both series (D17):** once a date's list or a day's return row is
   written, it is never recomputed — a run only appends new dates, and the summary/metrics are
   recomputed from the rows actually on disk (never from an ephemeral in-memory recompute, since
   restated fundamentals can make an old date's fresh value differ from its frozen one). A
   `method_version` bump is the only explicit way to force a one-time full rebuild. This
   supersedes D13's "full deterministic recompute every run."
4. **Non-US filing lag (D18):** series B's usability lag becomes ticker-aware — 90 days for a US
   ticker (no exchange suffix) as before, 120 days for any non-US ticker (a `.XX` suffix, e.g.
   `.DE`/`.SA`/`.T`/`.KS`), since 20-F and foreign filers publish later. Ships with a single
   `method_version` bump (D17's one explicit rebuild), combined with the start-trim fix below.
5. **Sortino stays in both series (D19):** it is part of the qte77 Score (ADR-0004) and is
   reconstructable from closes up to the rank date alone in both series, so nothing about it
   changes.
6. **Start-trim fix:** `simulate`'s raw daily rows are now trimmed to each cadence's own first
   trade date (`_trim_to_first_trade`) before they are persisted or fed to `metrics` — the
   pre-inception zero-return padding no longer reaches either series' output. The pre-start year
   files already committed to the `data` branch (1962-2022, all-zero) are deleted as part of the
   `method_version` bump, via a minimal `sha: null` tree-entry extension to
   `scripts/data-branch-commit.cjs` (Git's Trees API already supports path deletion this way — no
   new dependency).

### Frozen data contract addendum

Series A adds a parallel set of paths, same shapes as series B's:
`results/series/backtest_genuine/<cadence>/YYYY.json`, `results/backtest_genuine/lists/YYYY.json`,
`results/backtest_genuine/summary.json` (where `null`/`fidelity` may be `null`). Series B's paths
are unchanged, so PR D's UI keeps working unmodified. See plan
[008](../plans/008-pit-longshort-backtest.md) §"Frozen data contract" for the exact shapes.
