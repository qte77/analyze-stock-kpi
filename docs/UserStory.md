# User Story

## What this is

A no-API-keys CLI that produces a per-asset KPI dossier (fundamentals + sentiment + composite scores) for any tradable Yahoo symbol — stocks, ETFs, FX pairs, commodity futures, crypto, indices.

## Who it is for

Solo investors building their own auditable, rule-based screening pipeline. Anyone who wants Traderfox-style aggregate scores without paying Traderfox, with formulas they can read and modify.

## Core user stories

- **As an investor**, I want to point the tool at a list of tickers (or a curated universe preset) and get one JSON snapshot per asset so I can sort/filter on KPIs in any downstream tool.
- **As an investor**, I want quality / dividend / growth / robustness / screener composite scores derived from documented public formulas (Piotroski, ROIC stability, dividend coverage, CAGR) so I can audit and tune the weighting myself.
- **As an investor**, I want a daily CNN Fear & Greed sentiment snapshot committed to the repo so I have a long-running market-mood timeseries without paying for one.
- **As a maintainer**, I want every structured payload validated by pydantic and every module within strict cyclomatic + cognitive complexity budgets so the codebase stays readable and the failure modes are loud.

## Non-goals (explicit)

- Replicate Traderfox's exact proprietary numerical scores (won't match byte-for-byte; composite proxies are documented approximations of the same signals)
- Long/short hedging strategy execution (deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md) — issues #4 / #8 / #9 / #10 stay open with the `deferred` label; behavioral price analytics fits a sibling repo)
- Paid-data integrations (CDS spreads, Bloomberg, Refinitiv) — out of scope
- Automated trade execution — analysis only

## v0.6.0 done means

- A read-only static dashboard at `https://qte77.github.io/analyze-stock-kpi/` shows the current CNN Fear & Greed score with a 2-year history chart plus a sortable table of the latest `qte77-watchlist` fundamentals snapshot (74 tickers, weekly cadence). Dashboard UX polish: Score heatmap, Fuse.js filter, sticky table head, mobile layout.
- A weekly GitHub Actions cron (`demo-snapshot.yaml`) writes `results/demo/qte77-watchlist/YYYY-MM-DD.json` snapshots and a manifest to the `data` branch via verified REST Git Data API commits. The dashboard fetches them cross-origin from `raw.githubusercontent.com`.
- `fear-greed.yaml` rewritten to the same verified-commit pattern, fixing the cron blocked by the repo's `required_signatures` ruleset.
- Chart.js vendored locally (drops jsdelivr.net CDN dependency).
- Inherits everything from v0.5.1 below.

## v0.5.1 done means

- yfinance `info["dividendYield"]` is normalized at the fetch boundary so the rich table, JSON output and composite formulas all see one fractional convention (#43).
- Inherits everything from v0.5.0 below.

## v0.5.0 done means

- `make run UNIVERSE=<preset>` (or `TICKERS=...`, `TICKERS_FILE=...`) writes a single `results/fundamentals/<UTC>.json` containing one `FundamentalsSnapshot` per resolved ticker, with a nested `composite_scores` object (seven 0-100 proxies). Sparse fields for non-equities are valid.
- Stdout shows a rich summary table for equities + ETFs; pass `SHOW_SCORES=1` to append Quality / Div / Growth columns.
- CNN F&G snapshot lands daily in `results/cnn_fg/YYYY.json` via cron (v0.4.0 #17).
- `make validate` passes lint + types + complexity + lint_md + tests. CI green on push and PR (validate + links-fail-fast workflows).

## v1.0.0 done means

- Factor-weighted `screener_score` (#84) — replaces the prior unweighted composite aggregate so the headline score reflects KPI weights from `composite_scores.py`.
- Release engineering: `tag-release` workflow, README screenshot, copyright + composite_scores docstring polish (#90, pre-1.0 cleanup).
- Auto-generated `llms.txt` via `qte77/gha-llms-txt-action` (#80).
- Dashboard: detail-panel dismiss fix (#89), sticky-header fix, lint-gate tightening.
- Inherits everything from v0.6.0 above.

## Post-1.0 (shipped on `main`, not yet tagged)

A polish + observability batch widening the dashboard's signal density and the operator-side toolkit. Inherits everything from v1.0.0; new themes:

- **Federal-contractors universe** — `usaspending.gov` POST client (#123), `src/orchestrators/federal_contractors.py` chains usaspending → EDGAR → yfinance, weekly refresh workflow opens PRs against `main` only when the top-100 ranking diffs. ADR-0006 ([decisions/0006-federal-contractors-universe.md](decisions/0006-federal-contractors-universe.md)).
- **SEC EDGAR enrichment** — `src/data_sources/sec/cik_map.py` (CIK ↔ ticker resolver with conditional-GET cache) + `submissions.py` (per-ticker last 10-K / 10-Q / 8-K dates appended to every `FundamentalsSnapshot`).
- **Dashboard expansion** — view-mode toggle (simple / detailed, #134), URL-state persistence, conditional cell coloring, CSV export, external links, theme toggle (system / light / dark), multi-universe overlay (#137), tabbed F&G panel with long-term monthly aggregate (#159), click-to-filter sector donut, per-cell empty-reason tooltips (#170).
- **Operator tooling** — universe coverage audit (`scripts/audit_universes.py`, #168) classifies every bundled-preset ticker as OK / SPARSE / FAIL against current Yahoo data; one-shot historical F&G backfill via the `whit3rabbit/fear-greed-data` mirror (#164) extends the dashboard's long-term context from ~13 months to ~14 years.
- **Risk-curve view** — 5s10s US Treasury slope tab in the dashboard's long-term-context panel (#165) tracks `^TNX − ^FVX` (10y minus 5y yield in percentage points). Positive = normal curve; negative = inversion. Daily cron (`yield-curve.yaml`, 22:30 UTC) writes `results/yield_curve/YYYY.json` to the `data` branch via the same verified-commit pattern as `fear-greed.yaml`.
- **Doc + workflow architecture** — package vs repo-infrastructure boundary formalized in [ADR-0007](decisions/0007-package-vs-infrastructure-boundary.md); `CONTRIBUTING.md` carries the shared technical workflow (test conventions, commits, GHA SHA-pinning, scriv changelog fragments, release flow); `AGENTS.md` shrunk to AI-agent-specific rules only; `CHANGELOG.md` now owned by [scriv](https://github.com/nedbat/scriv) — each PR drops a fragment under `changelog.d/`, no parallel-PR conflicts on `[Unreleased]`.
- **Cross-universe aggregation** — `src/orchestrators/aggregated_scores_best_and_worst.py` ranks every ticker across the 7 sector/region universes by mean of the 7 composite scores; emits as a **paired-universes set** (`aggregated-scores-best` + `aggregated-scores-worst`, 25 tickers each). Phase 1 of a long/short-screener pair; the dashboard's score-cell now exposes the `mean_composite` value as a tooltip on aggregator universes (closes #218) so users can see why a ticker placed in best/worst even when its visible `screener_score` looks counterintuitive. ADR-0005 amendment classifies as Tier-0 pure-aggregation.
- **Enhanced KPI long/short conjunctive-gate screener — Phase 2a + 2b** (#192). `src/orchestrators/enhanced_kpi_screener_longshort.py` ships 15 of the 16 issue criteria — Phase 2a delivered 13 gates from existing `FundamentalsSnapshot` fields plus the `analyst_recommendation` bucket; Phase 2b added criterion 12 (FCF margin via `Ticker.cashflow` / `Ticker.income_stmt`, attached as the `fcf_margin` enrichment). Paired output (`enhanced-kpi-screener-longs.txt` + `…-shorts.txt`); a ticker lands in `longs` iff it passes **every** long-side gate, in `shorts` iff it passes **every** inverted short-side gate, otherwise neither. No top-N truncation — counts vary, can be 0 each side. Criterion 15 (tech rating) stays deferred behind the #21 TradingView decision.

## Future: per-asset directory layout (not currently scheduled)

A future schema change would shift `make run UNIVERSE=<preset>` from the current single-file output (`results/fundamentals/<UTC>.json`) to a per-asset directory at `results/<DATE>_<universe>/<ticker>/`:

- `fundamentals.json` — Tier 1: extends `FundamentalsSnapshot` with PEG, dividend-aristocrat flag, and any richer trend/historical fields the simplified composites currently approximate
- `composites.json` — Tier 3: quality / dividend / growth / big_call / aaqs / hgi proxy scores (v0.5.0 #18, simplified per [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md))
- `sentiment.json` — CNN F&G snapshot (v0.4.0 #17, runs independently on cron)

Not on the current roadmap — no consumer requires it. Re-open as a v2.0.0 candidate if downstream tooling needs the per-asset shape.
