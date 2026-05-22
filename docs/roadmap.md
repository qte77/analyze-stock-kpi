# Roadmap

Issues link to [GitHub Issues](https://github.com/qte77/analyze-stock-kpi/issues). See [`UserStory.md`](UserStory.md) for product intent and [`architecture.md`](architecture.md) for module structure.

## 0.3.0 — Tooling foundation [x]

Adopt qte77 ecosystem conventions (uv, ruff, pyright, Makefile, AGENTS.md, validate.yaml CI), Apache-2.0 license, working `make run`, runtime fixes.

**Shipped:** PR #2 (uv+ruff+pyright stack), #11 (plugins), #12 (orphan cleanup), #13 (pyright gate), #14 (Apache-2.0 + badges + `make run`), #15 (runtime fixes).

## 0.4.0 — Library-based KPI architecture [x]

Replace the Traderfox Playwright scraper with library-based fundamentals, asset-universe abstraction, and CNN F&G sentiment.

**Shipped:**

- [x] Governance scaffold + complexity gates wired into CI — PR #24
- [x] Decommission Traderfox scraper — issue [#19](https://github.com/qte77/analyze-stock-kpi/issues/19), PR #25
- [x] Universe layer (stocks/ETFs/FX/commodities/crypto/indices via Yahoo symbology) — issue [#20](https://github.com/qte77/analyze-stock-kpi/issues/20), PR #26
- [x] Mandatory markdownlint + lychee link checking (qte77 convention) — PRs #27 + #28
- [x] Fundamentals via yfinance — `FundamentalsSnapshot` with identity / valuation / profitability / financial health / growth / dividends / per-share / 52-week range fields. `financetoolkit` deferred per [ADR-0001](decisions/0001-defer-financetoolkit.md) — issue [#16](https://github.com/qte77/analyze-stock-kpi/issues/16), PR #28
- [x] CNN Fear & Greed sentiment + scheduled workflow — issue [#17](https://github.com/qte77/analyze-stock-kpi/issues/17), PRs #30-#37
- [x] README rewrite reflecting new architecture — issue [#3](https://github.com/qte77/analyze-stock-kpi/issues/3), PR #40

## 0.5.0 — Composite proxy scores [x]

Reproduce Traderfox-style aggregate signals as transparent, formula-documented composites built on v0.4.0's fundamentals. Simplified formulas use only point-in-time `FundamentalsSnapshot` inputs plus `info["beta"]`; multi-year trend formulas (Piotroski, CAGR, FCF coverage) are deliberately deferred per [ADR-0002](decisions/0002-simplified-composites.md).

**Shipped:**

- [x] `CompositeScores(BaseModel)` with quality / dividend / growth / big_call / aaqs / hgi proxies; each formula documented in docstrings — issue [#18](https://github.com/qte77/analyze-stock-kpi/issues/18), PR #42

## 0.5.1 — Data-quality follow-ups [x]

Patch release covering issues surfaced by the v0.5.0 composites work.

**Shipped:**

- [x] Normalize `dividend_yield` at the fetch boundary so the table render, JSON output, and composite formulas all see one convention — issue [#43](https://github.com/qte77/analyze-stock-kpi/issues/43), PR #51

## 0.6.0 — Demo dashboard on GitHub Pages [x]

The original v0.6.0 RS hedging scope was deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md); the milestone was repurposed for a read-only static dashboard that visualizes the repo's two existing committed datasets (CNN F&G + weekly fundamentals snapshots).

**Goals:**

- [x] Weekly fundamentals snapshot workflow (`demo-snapshot.yml`) committing to `results/demo/qte77-watchlist/YYYY-MM-DD.json` on a separate `data` branch via verified REST Git Data API commits — PR #60 + follow-up #61
- [x] Rewrite `fear-greed.yaml` to the same verified-commit pattern, fixing the cron broken by the `required_signatures` ruleset — PR #60 + #61
- [x] GitHub Pages deploy (`gh-pages.yaml`) using modern `actions/upload-pages-artifact` + `actions/deploy-pages` of `docs/demo/*` — issue [#59](https://github.com/qte77/analyze-stock-kpi/issues/59)
- [x] Static dashboard (`docs/demo/{index.html,app.js,style.css}`) — F&G 2-year chart + universe table with date selector, fetching cross-origin from `raw.githubusercontent.com/.../data/results/...`
- [x] **Dashboard KPI expansion** — 13-column main table (P/E (fwd) / PEG / Beta / R&D/Rev % / Op M % / ROE / ROA / Current / Sortino / Score), English tooltips, mobile-graceful CSS, off-by-one fix in composite-scores detail panel. New snapshot fields (`trailing_peg_ratio`, `roi`, `rd_to_revenue`, `sortino_ratio`) and 7th composite (`screener_score`) per [ADR-0004](decisions/0004-price-history-composite-input.md).

## Deferred

- [ ] RS hedging epic — parent [#4](https://github.com/qte77/analyze-stock-kpi/issues/4); sub-issues [#8](https://github.com/qte77/analyze-stock-kpi/issues/8) (Mansfield RS), [#9](https://github.com/qte77/analyze-stock-kpi/issues/9) (regime-split returns), [#10](https://github.com/qte77/analyze-stock-kpi/issues/10) (long/short ranking + CLI). Deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md); behavioral price analytics fits a sibling repo (e.g. `qte77/regime-hedging`) consuming `results/fundamentals/<UTC>.json`.

## Open research (no milestone)

- [ ] TradingView screener evaluation — issue [#21](https://github.com/qte77/analyze-stock-kpi/issues/21)
- [x] Alternative risk-sentiment sources (UBS, AAII, NAAIM, etc.) — issue [#22](https://github.com/qte77/analyze-stock-kpi/issues/22), resolved by [ADR-0005](decisions/0005-sentiment-risk-sources.md) (three-tier source framework)
- [ ] pandas alternatives (Polars, DuckDB, Dask, Modin, etc.) — issue [#23](https://github.com/qte77/analyze-stock-kpi/issues/23)
- [ ] Volatility-indices chart (Tier 0 application of ADR-0005) — issue [#100](https://github.com/qte77/analyze-stock-kpi/issues/100)
- [x] Federal-contractors universe (Tier 0 pipeline: usaspending.gov + EDGAR + yfinance) — shipped via PRs #107 (CIK resolver), #110 (last-filed flags), #123 (Item 3a usaspending client), #125 (Item 3b orchestrator + CLI + workflow). Library-first reorg documented in [ADR-0006 amendment](decisions/0006-federal-contractors-universe.md).
- [ ] Deferred EDGAR product use cases — XBRL cross-validation [#101](https://github.com/qte77/analyze-stock-kpi/issues/101), Form 4 insider momentum [#102](https://github.com/qte77/analyze-stock-kpi/issues/102), 8-K material events [#103](https://github.com/qte77/analyze-stock-kpi/issues/103)

## Out of scope

- CDS spreads (paid data only)
- Paid-API integrations (Tiingo, FMP premium, Alpha Vantage premium, Bloomberg)
- Trade execution (analysis only)
- Published artifacts on PyPI (CNN F&G remains an HTTP fetch from a non-public-API endpoint)
