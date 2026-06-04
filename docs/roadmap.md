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

## 1.0.0 — Release engineering + headline weighting [x]

**Shipped:**

- [x] Factor-weighted `screener_score` replaces the unweighted composite aggregate — issue [#84](https://github.com/qte77/analyze-stock-kpi/issues/84)
- [x] `tag-release` workflow, README screenshot, copyright + docstring polish — issue [#90](https://github.com/qte77/analyze-stock-kpi/issues/90)
- [x] Auto-generated `llms.txt` via `qte77/gha-llms-txt-action` — issue [#80](https://github.com/qte77/analyze-stock-kpi/issues/80)
- [x] Dashboard polish — detail-panel dismiss (#89), sticky-header fix, lint-gate tightening

## Post-1.0 polish [in progress on `main`]

Shipped on `main`; rolls into the next semver tag. See the `[Unreleased]` block in [`CHANGELOG.md`](../CHANGELOG.md) + the `changelog.d/` fragments for the canonical inventory.

**Shipped:**

- [x] **Universe coverage audit** — `scripts/audit_universes.py` + `src/orchestrators/universe_audit.py` classify every bundled-preset ticker against current Yahoo data (OK / SPARSE / FAIL) — issue [#168](https://github.com/qte77/analyze-stock-kpi/issues/168), PR #174
- [x] **F&G historical backfill** — `scripts/backfill_fear_greed_whitrabbit.py` + `src/data_sources/sentiment_backfill.py` extend the dashboard's long-term context from ~13 months to ~14 years via the [`whit3rabbit/fear-greed-data`](https://github.com/whit3rabbit/fear-greed-data) mirror; ADR-0005 amendment classifies as Tier-0 — issue [#164](https://github.com/qte77/analyze-stock-kpi/issues/164), PR #178
- [x] **Per-cell empty-reason tooltips** — `docs/demo/lib/empty_reason.js` explains structural gaps (bank R&D, bank current-ratio, CAD-bank ROE/ROA) so "—" cells answer "why" — issue [#170](https://github.com/qte77/analyze-stock-kpi/issues/170), PR #173
- [x] **Long-term context tab** + monthly F&G aggregation (median + average), click-to-filter sector donut, theme toggle, multi-universe overlay — issue [#159](https://github.com/qte77/analyze-stock-kpi/issues/159) and follow-ups
- [x] **5s10s yield curve slope panel** — `src/data_sources/yield_curve.py` + `.github/workflows/yield-curve.yaml` (daily cron, 22:30 UTC, Tier-0 yfinance `^TNX` / `^FVX`) + new "5s10s slope" tab in the long-term-context panel. Issue [#165](https://github.com/qte77/analyze-stock-kpi/issues/165).
- [x] **Changelog tooling** — `scriv` fragments replace direct `[Unreleased]` edits; eliminates the parallel-PR conflict pattern — PR #175
- [x] **Doc architecture split** — `CONTRIBUTING.md` carries shared dev workflow (humans + AI); `AGENTS.md` shrinks to AI-agent-specific behavioural rules — PR #177
- [x] **DRY refactor: shared per-year loader** — `loadFearGreedYears` + `loadYieldCurveYears` collapsed into `loadYearsFromBranch(pathPrefix, sortKey)` in `docs/demo/app.js`; future Tier-0 per-year sources plug in as one-line wrappers — issue [#181](https://github.com/qte77/analyze-stock-kpi/issues/181), PR #189
- [x] **lychee install fix** — Makefile `setup_lychee` recipe extracts the binary from the lycheeverse wrapper-dir tarball; drops `sudo` per qte77 convention; factors install path into `LYCHEE_BIN` — issue [#149](https://github.com/qte77/analyze-stock-kpi/issues/149), PR #188 (co-authored by @onurege3467)
- [x] **Universe pruning: drop crypto-top10** — preset removed from `src/assets/universes/`, `FALLBACK_UNIVERSE_IDS`, `universes.json`, demo-snapshot matrix; freed the cross-universe aggregator's source set from a non-equity preset that would have been ineligible anyway — issue [#190](https://github.com/qte77/analyze-stock-kpi/issues/190), PR #191
- [x] **Aggregated-scores best + worst universe pair (Phase 1 of long/short screener)** — new `src/orchestrators/aggregated_scores_best_and_worst.py` + weekly cron + PR-on-diff workflow; cross-universe meta preset emitted as **two paired universes** (`aggregated-scores-best` + `aggregated-scores-worst`, 25 tickers each, ranked by composite-mean); explicit "NOT a hedging primitive" framing in ADR-0005 amendment. Establishes the paired-output pattern Phase 2 #192 will reuse for gated longs/shorts — issue [#184](https://github.com/qte77/analyze-stock-kpi/issues/184)
- [x] **Universe-builder workflow consolidation** — `federal-contractors-refresh.yaml` + `aggregated-scores-best-and-worst-refresh.yaml` collapse into one matrix-driven `universe-builder.yaml`; adding a future universe (e.g. Phase 2 #192) becomes a ~7-line config addition instead of a 130-line copy-paste. Fixes two duplication-bugs from the parallel-workflows era: invalid JS escape (#194) and preset-PR bundling 100k lines of index state (#195).
- [x] **Enhanced KPI long/short screener — Phase 2a** — `src/orchestrators/enhanced_kpi_screener_longshort.py` ships 13 of the issue's 16 conjunctive-gate criteria (every gate that reads an existing `FundamentalsSnapshot` field plus criterion 14 via the new `analyst_recommendation` model field — no new HTTP). Paired output (`enhanced-kpi-screener-longs.txt` + `…-shorts.txt`); long ∩ short empty by construction. Wired into `universe-builder.yaml`, `demo-snapshot.yaml`, and `docs/demo/universes.json`. Deferred to Phase 2b: criterion 12 (FCF margin, needs `Ticker.cashflow`) and criterion 15 (tech rating, blocked on #21). PR #228, partial closure of issue [#192](https://github.com/qte77/analyze-stock-kpi/issues/192).
- [x] **Dashboard polish batch** — dark-mode chart grid + axis label contrast fix (#205 → PR #220), screener_score label renamed to "qte77 Score" across detail panel / radar / time-series (#203 → PR #221), strict 12-month TTM trim on the F&G rolling chart (#207 → PR #222), `1y | 5y | 10y | all` time-window chips on the long-term F&G + 5s10s charts (#206 → PR #227), Op M % hidden in simple view (PR #229), score-cell tooltip surfaces `mean_composite` on aggregator universes (closes #218 → PR #231).
- [x] **CI hygiene** — dependabot grouping per ecosystem (PR #219), `sam.gov` added to lychee's exclude list to silence pre-existing 403-to-bots flake repo-wide (PR #223), `demo-snapshot.yaml` matrix fan-out now reads `docs/demo/universes.json` as the source of truth instead of a hardcoded JSON literal (PR #232), `"no history yet"` empty-hint string deduped into one constant (PR #224).

**Open / queued (research + medium-effort):**

- [ ] **Enhanced KPI long/short screener — Phase 2b** — remaining criteria from #192: criterion 12 (FCF margin, needs a new `Ticker.cashflow` fetch + offline fixture + `@pytest.mark.network` live test), criterion 15 (tech rating, blocked on TradingView decision #21), ADR-0002 + ADR-0005 amendments, strict per-criterion red/green TDD pairs (issue's acceptance criterion), and gate-threshold tuning (Phase 2a's 13-gate conjunction returned 0 candidates each side on a 7-universe source set — thresholds are honest but operationally too strict).
- [ ] **Surface "Why these universes?" dashboard tab** — analog of the F&G "Why these charts?" pane; explains best/worst (mean-of-7 ranking) vs longshort (conjunctive-gate filter) so the empty-state for unpopulated universes reads as a design outcome, not a bug.

## Deferred

- [ ] RS hedging epic — parent [#4](https://github.com/qte77/analyze-stock-kpi/issues/4); sub-issues [#8](https://github.com/qte77/analyze-stock-kpi/issues/8) (Mansfield RS), [#9](https://github.com/qte77/analyze-stock-kpi/issues/9) (regime-split returns), [#10](https://github.com/qte77/analyze-stock-kpi/issues/10) (long/short ranking + CLI). Deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md); behavioral price analytics fits a sibling repo (e.g. `qte77/regime-hedging`) consuming `results/fundamentals/<UTC>.json`.

## Open research (no milestone)

- [ ] TradingView screener evaluation — issue [#21](https://github.com/qte77/analyze-stock-kpi/issues/21)
- [x] Alternative risk-sentiment sources (UBS, AAII, NAAIM, etc.) — issue [#22](https://github.com/qte77/analyze-stock-kpi/issues/22), resolved by [ADR-0005](decisions/0005-sentiment-risk-sources.md) (three-tier source framework)
- [ ] pandas alternatives (Polars, DuckDB, Dask, Modin, etc.) — issue [#23](https://github.com/qte77/analyze-stock-kpi/issues/23)
- [ ] Volatility indices overlay (^VIX / ^VIX9D) — issue [#187](https://github.com/qte77/analyze-stock-kpi/issues/187), deferred pending Part 1 of #100 (F&G subindicator panels, also deferred per session re-evaluation)
- [ ] F&G 9-subindicator panels (narrowed) — issue [#100](https://github.com/qte77/analyze-stock-kpi/issues/100), deferred (9-sparkline grid more visual load than action signal)
- [x] Federal-contractors universe (Tier 0 pipeline: usaspending.gov + EDGAR + yfinance) — shipped via PRs #107 (CIK resolver), #110 (last-filed flags), #123 (Item 3a usaspending client), #125 (Item 3b orchestrator + CLI + workflow). Library-first reorg documented in [ADR-0006 amendment](decisions/0006-federal-contractors-universe.md).
- [ ] Deferred EDGAR product use cases — XBRL cross-validation [#101](https://github.com/qte77/analyze-stock-kpi/issues/101), Form 4 insider momentum [#102](https://github.com/qte77/analyze-stock-kpi/issues/102), 8-K material events [#103](https://github.com/qte77/analyze-stock-kpi/issues/103)

## Out of scope

- CDS spreads (paid data only)
- Paid-API integrations (Tiingo, FMP premium, Alpha Vantage premium, Bloomberg)
- Trade execution (analysis only)
- Published artifacts on PyPI (CNN F&G remains an HTTP fetch from a non-public-API endpoint)
