# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bugfixes.
- `Security` in case of vulnerabilities.

<!-- scriv-insert-here -->

## [1.2.0] - 2026-06-26

### Added

- **Enhanced KPI long/short conjunctive-gate screener — Phase 2a (#192).** `src/orchestrators/enhanced_kpi_screener_longshort.py` ships 13 of 16 issue criteria — every gate that reads an existing `FundamentalsSnapshot` field plus criterion 14 via the new `analyst_recommendation` field (alias `recommendationKey`, already in the yfinance `info` payload — no new HTTP). Paired output (`enhanced-kpi-screener-longs` + `…-shorts`); a ticker lands in `longs` iff it passes ALL 14 long-side gates, in `shorts` iff it passes ALL 13 inverted short-side gates, otherwise `neither`. Long ∩ short empty by construction. Declarative `_NUMERIC_GATES` table keeps `_evaluate` cognitive complexity at 5. PR #228. Phase 2b owes criterion 12 (FCF margin, `Ticker.cashflow` fetch), criterion 15 (tech rating, blocked on #21), ADR amendments, and threshold tuning.
- **Demo: `1y | 5y | 10y | all` time-window chips above the long-term F&G + 5s10s charts (#206).** Click filters the entries array client-side before passing to Chart.js (per the issue's option 1 — no zoom plugin, no brush slider). New URL params `?ltFgWindow=` / `?ycWindow=` (omitted at default). Existing lazy-render guard preserved: chip click while a pane is hidden flips the rendered flag back so the next tab activation picks up the new window. PR #227.
- **Demo: score-cell tooltip surfaces `mean_composite` on aggregator universes (#218).** On `aggregated-scores-best` / `…-worst`, hovering the Score cell shows the mean-of-7-composites — the metric the aggregator actually ranks on. Closes the user-confusion gap surfaced by #202 (PRSO in worst-25 with visible `screener_score` 64, mean 16.5). PR #231.

- **FCF margin enrichment for the long/short screener (#192 Phase 2b).** `src/data_sources/fundamentals.py` gains `_fetch_fcf_margin` mirroring `_fetch_rd_to_revenue`: gated on `info["quoteType"] == "EQUITY"`, reads "Free Cash Flow" from `Ticker.cashflow` and "Total Revenue" from `Ticker.income_stmt` via the shared `_find_row` helper, returns `None` on any missing data / zero revenue / network error. New `fcf_margin: float | None` field on `FundamentalsSnapshot` attached post-validate via `model_copy`. `src/orchestrators/enhanced_kpi_screener_longshort.py` adds the gate to `_NUMERIC_GATES` (long > 0.10, short < 0), bringing the conjunctive-gate screener to 15 of 16 criteria. Criterion 15 (tech rating) stays deferred behind #21. ADR-0002 amended to note the new enrichment field. Closes #192.

- **Radar-hexagon favicon for the demo dashboard (`docs/demo/favicon.svg`).** A dependency-free inline SVG echoing the composite-score radar chart, theme-aware via `prefers-color-scheme` so it stays legible on light and dark browser tabs. Linked from `index.html` as `type="image/svg+xml"`.

- Self-hosted brand typography for the demo dashboard — **Inter** (UI/prose)
  and **JetBrains Mono** (numeric table cells + `<code>`), per the qte77
  EyeRest design tokens (#295). Latin TTF subsets ship in `ui/fonts/` (SIL OFL 1.1,
  `ui/fonts/OFL.txt`) with `font-display: swap` and the prior system stack as
  fallback — no third-party font CDN request.
- Adopted the qte77 brand mark (`logo-mark.paths.dejavu.svg`) as the demo
  dashboard favicon, replacing the bespoke radar SVG (#295).

- Deep history for the demo's long-term charts: CNN Fear & Greed back to
  **2011** and the 5s10s yield-curve slope back to **2011** (committed to the
  `data` branch). New `scripts/backfill_yield_curve.py` forces a full
  `period="max"` yfinance fetch — the daily cron only deepens on a first run
  (#287).

- **`equity-spy.yaml` daily cron (#288).** Recomputes the SPY indexed-return
  series and commits changed `results/series/equity_spy/YYYY.json` to the `data`
  branch via the shared verified-commit helper. Runs 23:00 UTC, staggered 30min
  after the yield-curve cron so the data-branch writers don't race the same ref.
  Mirrors `yield-curve.yaml` (same pinned action SHAs).

- **`equity_spy` data source — SPY indexed-return series (#288).** New
  `analyze_stock_kpi.data_sources.equity_spy` fetches SPY (the SPDR S&P 500 ETF)
  via yfinance and emits a **derived rebased index** (`ret_indexed = close /
  epoch_close * 100`, epoch = first close ≥ 2011) — never the raw close and never
  the S&P 500 index level (ADR-0011). Same per-year `results/series/<kind>/`
  shape + wrap-degrade boundary as `yield_curve`. Backend only here; the
  data-branch backfill, the cron, and the merged-chart UI follow separately.

- **Governance for the #288 equity-macro overlay (ADR-0011).** Records the
  decision to source the equity line from **SPY** (an ETF security, not the S&P
  Dow Jones index) and commit only a **derived indexed-return** series — never
  raw index levels — keeping it at the same redistribution tier as the existing
  `yield_curve` slope. Adds a `docs/data-sources.md` guardrail row and a repo
  `NOTICE` recording the non-commercial/educational, derived-data posture, the
  upstream ToS, and attribution for the bundled third-party libs (Chart.js MIT,
  Fuse.js Apache-2.0). (#288)

- **Forks that enable Pages now self-host their own `data` branch.** The dashboard
  derives `DATA_BASE_URL` from the Pages origin (`<owner>.github.io/<repo>` →
  that owner/repo's `data` branch) via a new pure `ui/lib/data.js`; `?base=` still
  overrides, and the canonical qte77 deploy is unchanged. Prior art: the sibling
  `agentic-job-offer-to-application-kit` dashboard.

### Changed

- **Aggregator derives composite-field list from `CompositeScores.model_fields`.** `src/orchestrators/aggregated_scores_best_and_worst.py` previously hardcoded the 7-field tuple in two places (the model definition and the orchestrator constant); adding a new composite would have been silently omitted from cross-universe ranking. Now the tuple is `tuple(CompositeScores.model_fields)` — single source of truth, zero hidden coupling. Regression guard added in `tests/test_aggregated_scores_best_and_worst.py`.

- **Demo: `screener_score` displays as "qte77 Score" (#203).** Display-only rename across `KPI_GLOSSARY` / detail-panel / time-series chart / radar chart. Internal field name `composite_scores.screener_score` is unchanged so JSON snapshots on the `data` branch keep validating. Table column header stays `Score` for column-width parity. PR #221.
- **Demo: F&G rolling chart trimmed to a strict 12-month TTM window (#207).** `renderFearGreedChart` now applies `trimToRollingWindow(entries, 365)` before render so the rendered window is always 12 months regardless of when in the year the dashboard opens (was drifting between ~8 and ~24 months as the loader consumes this-year + last-year files). PR #222.
- **Demo: `Op M %` column hidden in simple view.** Marks the `<th>` and the cellSpec as `detail-only` so simple view keeps the 4 headline columns (Ticker / Name / Sector / Score). PR #229.
- **CI: dependabot updates grouped per ecosystem.** `groups: { python-deps / github-actions: { patterns: ["*"] } }` on the `uv` + `github-actions` ecosystems — collapses N per-dependency PRs into one grouped PR per weekly run per ecosystem. PR #219.
- **CI: `demo-snapshot.yaml` fan-out reads `docs/demo/universes.json` instead of a hardcoded JSON literal.** Adding a new universe is now a one-file change (the JSON). Empty-input dispatch re-builds every universe the dashboard knows about regardless of preset `.txt` state — emitting a zero-row snapshot for an unpopulated universe is the right rebuild behavior. PR #232.

- **Typed contracts in `src/orchestrators/_shared.py`: `AuditRowBase` + `DedupedSnapshot`.** Closes assessment gaps #2 (3 divergent `AuditRow` models) and #3 (`dedup_by_ticker` returned `dict[str, dict[str, Any]]`). `AuditRowBase` extracts the 5-field decision-trail prefix (`ticker`, `source_universes`, `snapshot_dates`, `eligible`, `excluded_reason`) shared by the aggregator + longshort `AuditRow` subclasses; federal_contractors stays distinct (different domain — per-recipient match audit). `DedupedSnapshot(BaseModel)` replaces the untyped dict return of `dedup_by_ticker`; consumers switch from `info["snapshot"]` string-key indexing to `info.snapshot` attribute access. Rule-of-three pre-application for Phase 2b's FCF orchestrator (#192) which becomes the 3rd consumer of both shapes. JSON shape change is safe: the aggregator + longshort audit JSONs are written but never read back (JS dashboard only consumes federal_contractors audit). Matches the AGENTS.md "every structured payload is a BaseModel" rule.

- **Extracted shared snapshot-loader + paired-output writer from build scripts.** `scripts/build_aggregated_scores_best_and_worst.py` and `scripts/build_enhanced_kpi_screener_longshort.py` were ~80% identical (same `SOURCE_UNIVERSES`, same `_load_snapshots`, same main-loop dict-builder, same paired-preset+audit-write pattern); CodeFactor flagged the duplicated block as its sole remaining issue on `main`. Moved to a new `scripts/_demo_snapshot_loader.py` exposing `load_snapshots` / `load_all_snapshots` / `write_paired_universe_and_audit`. Each build script collapses from ~100 LOC to ~50 LOC of orchestrator-import + thin `main()`; Phase 2b's FCF orchestrator (#192) becomes a drop-in 3rd consumer. `build_federal_contractors.py` left alone (different input shape — no snapshot loading, single preset). Leading-underscore module name signals scripts/-internal per ADR-0007.

- **`fear-greed.yaml` + `yield-curve.yaml` now route through `scripts/data-branch-commit.cjs`.** Both daily crons carried byte-identical 36-line inline `github-script` blocks (getRef → getCommit → mkBlob → createTree → createCommit → updateRef) — the same verified-commit logic that `demo-snapshot.yaml` + `universe-builder.yaml` already delegate to the CJS helper. Migrating eliminates ~52 LOC of duplicated workflow YAML, ends the convention drift between the two stale crons and the two updated ones, and **adds 422-race retry** the inline blocks lacked (8 attempts with jittered backoff). Future verified-commit fixes propagate to all 4 workflows from a single file. Surfaced by today's scripts+workflows duplication sweep.

- **README / UserStory / roadmap / architecture sync after #248.** Surface the `fcf_margin` enrichment field in README's sample-output blurb; mark Phase 2b shipped in `docs/UserStory.md` and `docs/roadmap.md` (criterion 15 / tech rating stays deferred behind #21); record the new gate count (15 long + 14 short) and the `_fetch_fcf_margin` boundary in `docs/architecture.md`. No behaviour change — pure doc drift cleanup so the long/short screener's documented state matches the merged code on `main`.

- **`docs/demo/app.js`: extract `destroyChart`, `scoreYAxis`/`themedXAxis`, and `toggleHistoryHint` to collapse repeated chart + empty-hint boilerplate.** The chart-teardown idiom (`liveCharts.delete` + `.destroy()`) is now one helper across all six chart renderers; the 0–100 score y-axis and themed x-axis configs (each repeated 3×) become builder functions; the two byte-for-byte-identical empty-hint functions (sector-donut + long-term F&G) share one `toggleHistoryHint`, while the rolling + yield-curve variants that intentionally overwrite text stay separate. Behaviour-preserving, in-file only (no new modules/tests); `node --check` + `tsc` clean. First slice of the app.js size/repetition reduction.

- **`src/data_sources/fundamentals.py`: single-source duplicated structure via `_safe_ratio`, `_extract_two_rows`, `_equity_ratio`.** CodeFactor reported "0 duplication" but missed near-identical structure where only literals differ: the None/zero-denominator ratio guard (`_compute_roi` + both EQUITY-gated fetchers), the two-row extract-with-empty/missing-row/NaN guards (`_read_rd_revenue` / `_read_fcf_revenue`, one-frame vs two-frame), and the EQUITY-gate + try/except + safe-divide fetchers (`_fetch_rd_to_revenue` / `_fetch_fcf_margin`). Behaviour-preserving — the full regression suite stays green; per-method cognitive complexity drops (both readers and both fetchers to 0) and `_read_rd_revenue` gains the direct unit coverage it previously lacked. The `fetch` thunk in `_equity_ratio` keeps the yfinance property access inside the `try` and short-circuits the EQUITY gate before any fetch.

- **`docs/demo/lib/detail_rows.js`: extract the pure detail-panel data (`KPI_GLOSSARY`, `auditDetailRows`, `externalLinkRows`) out of `app.js`.** The KPI-glossary text and the row-tuple builders for the federal-contracts audit block + external links move to a tested lib module; `app.js` imports them. Adds `tests/demo/detail_rows.test.mjs` (7 cases for the two builders; the glossary is static data, no test). The DOM rendering (`showDetail` / `renderRadar` / `renderTimeSeriesPane`) intentionally stays in `app.js` — extracting it would require exporting the shared mutable `liveCharts` Set across modules or a god-object deps argument, both worse than co-location (AHA). Behaviour-preserving.

- **`docs/demo/lib/format.js`: extract the pure value formatters + comparator (`nested`, `fmtNum`, `fmtPct`, `compareValues`) out of `app.js` into a unit-tested module.** Adds `tests/demo/format.test.mjs` covering dotted-key access (incl. missing segments / nullish root), `fmtNum` null/NaN/precision, `fmtPct` null plus its intentional no-NaN-guard behaviour, and `compareValues` nulls-last-regardless-of-direction + string/number ordering. `td()` stays in `app.js` (DOM glue). Behaviour-preserving; prerequisite for the upcoming `table.js` / `detail.js` concern splits.

- **`docs/demo/lib/window.js`: extract the pure time-window helpers (`WINDOW_DAYS`, `filterByWindow`, `findClosestScore`) out of `app.js` into a unit-tested module.** Adds `tests/demo/window.test.mjs` covering the non-trivial branches (empty input, `"all"` passthrough, unparseable-latest fallback, inclusive cutoff boundary, arbitrary iso field; closest-score nearest-match + equidistant tie-break). Also deletes the redundant `trimToRollingWindow` — it was equivalent to `filterByWindow(entries, "1y", "timestamp")` — and rewrites its sole call site in `renderFearGreedChart`. Behaviour-preserving; the window math is now testable without a DOM.

- **`docs/demo/table.js`: split the universe-table rendering concern out of `app.js`.** Moves `ALL_COLUMNS`, the DOM builders (`renderUniverseTable`, `renderRow`, `td`, `annotateEmpty`) and the pure helpers (`buildRowTitle`, `coverageCount`, `meanComposite`, `totalCompositeScore`, `emptyTableMessage`) into a new sibling module. Module state (active universe, sort key/dir, filter query, row-click handler) is now passed in via an `opts` object instead of read from `app.js` globals, so `table.js` holds no mutable app state. `app.js` keeps a thin `renderTable()` adapter, so its 7 call sites are unchanged. Adds `tests/demo/table.test.mjs` (18 cases for the pure helpers) and widens `tsconfig` `include` to top-level `*.js`. Behaviour-preserving; `app.js` drops ~225 lines.

- **`docs/demo/app.js`: prune verified-dead code.** Removes two obsolete historical comments (the removed mobile auto-simple guard; the removed simple-mode external-link behaviour in `onRowClick`), the inert `radarCanvas.className = "radar-canvas"` assignment (no matching CSS/HTML selector — Chart.js gets the canvas node by reference), and the never-passed `text` parameter of `renderRollingEmptyHint` (its sole call site always resolves to `EMPTY_HISTORY`). Each removal was cross-checked against `index.html` / `style.css` / tests to confirm zero live references. Behaviour-preserving.

- **`docs/demo/detail_panel.js`: extract the `#row-detail` side-panel lifecycle out of `app.js`.** `showDetail` / `bindDetailDismiss` (plus the private `dl` / `closeDetail` helpers) move to a new sibling DOM module that mirrors `table.js`: it owns the detail aside but takes the row's audit record and the two chart renderers (`renderRadar`, `renderTimeSeriesPane`) via a context object instead of reading `app.js` globals, so it stays free of `app.js` mutable state and chart slots. `app.js` keeps a one-line `onRowClick` adapter and drops its now-unused `detail_rows` import + `fmtPct`. Net −163 LOC in `app.js`. Behaviour-preserving (logic moved verbatim); the consumed pure builders stay covered by `tests/demo/detail_rows.test.mjs`.

- **`docs/demo/lib/fetch.js`: extract the data-branch fetch helpers out of `app.js`.** `fetchJson` (fetch + throw-on-non-2xx + parse) and `loadYearsFromBranch` (this-year + last-year concat with per-leg silent-fail and ascending sort) move to a pure, DOM-free lib module; `app.js` imports them and keeps the thin state-closing wrappers (`loadManifest`, `loadSnapshot`, `loadFearGreedYears`, …). `loadYearsFromBranch` now takes the base URL as a parameter (`loadYearsFromBranch(baseUrl, pathPrefix, sortKey)`) instead of closing over `DATA_BASE_URL`, which is what makes it pure and testable. Adds `tests/demo/fetch.test.mjs` (5 cases: 2xx parse, non-2xx throw, two-leg concat+sort, per-leg silent-fail, non-array-leg skip). Net −31 LOC in `app.js`. Behaviour-preserving.

- **`docs/demo/lib/chart_axes.js`: extract the themed Chart.js axis factories out of `app.js`.** `scoreYAxis` (0–100, stepSize 25) and `themedXAxis` (tick-capped x) move to a pure, DOM-free lib module. To keep `lib/` DOM-free they take an injected `cssVarFn(token, fallback)` instead of closing over `app.js`'s `cssVar`: `scoreYAxis(cssVar)` / `themedXAxis(cssVar)` at the four call sites (`renderTimeSeriesPane`, `renderFearGreedChart`, `renderMonthlyFearGreedChart`, `renderYieldCurveChart`). The returned objects still carry deferred color closures (Chart.js resolves them lazily on theme flip), now documented as a caller-owns-lifetime contract. Adds `tests/demo/chart_axes.test.mjs` (4 cases: static shape + deferred-injection for both factories). Net −19 LOC in `app.js`. Behaviour-preserving.

- **`docs/demo/app.js`: dedup the chart empty-hint helpers onto a single `toggleHistoryHint`.** `renderRollingEmptyHint` and `renderYieldCurveEmptyHint` were 14-line near-twins re-implementing the create/update/remove logic; both collapse to one-line delegations (matching the existing `renderDonutEmptyHint` / `renderLongTermEmptyHint` wrappers). `toggleHistoryHint` gains an optional `text` param and switches from skip-if-existing to update-if-existing — which is what preserves the "loading… → no history yet" overwrite of the static placeholders shipped in `#fg-chart-wrap` / `#yc-chart-wrap`. Verified safe for the donut + long-term callers: they have no static placeholder and only ever store `EMPTY_HISTORY`, so the update path is a no-op for them. Net −24 LOC in `app.js`. Behaviour-preserving.

- **`ui/charts.js`: extract the Chart.js rendering layer out of `app.js` (closes #268).** All chart builders (sector donut, radar, F&G rolling/monthly, yield curve, detail-panel time-series) plus the shared chart infra (`liveCharts`/`cssVar`/`destroyChart`/`bindThemeObserver`/`toggleHistoryHint`) and the long-term-tab + window-chip wiring move verbatim into a sibling module. The only app↔chart coupling is wired through a single injected context object — `initCharts(ctx)` with live getters/setters for `snapshot`/`sectorFilter`/`ltFgWindow`/`ycWindow`/`manifest`/… and `afterSectorToggle`/`afterWindowChange` callbacks — mirroring the `table.js` / `detail_panel.js` opts-object precedent. Net `app.js` −722 LOC (1278 → ~615); behaviour-preserving (147 vitest pass; headless render verified: donut click-filter, tabs, window chips, detail radar + time-series all functional, 0 console errors).

- **Import package renamed `src` → `analyze_stock_kpi` (src-layout; [ADR-0009](docs/decisions/0009-rename-package-to-analyze-stock-kpi.md), resolving the ADR-0007 refactor candidate).** The package now lives at `src/analyze_stock_kpi/` and is imported as `analyze_stock_kpi` (e.g. `from analyze_stock_kpi.domain.universe import resolve_universe`); the CLI entry is `python -m analyze_stock_kpi`. **Breaking for any code importing `src.*`** — switch to `analyze_stock_kpi.*`. The PyPI distribution name (`analyze-stock-kpi`), CLI behaviour, and public API are otherwise unchanged.

- **Dashboard re-themed to the qte77 EyeRest brand (zero-blue, warm).** The `ui/` dashboard moves from its cool-gray Apple-system palette to EyeRest's umber/parchment tones (`DESIGN.md`). Blue/teal accents → the amber accent + the brand's zero-blue data arc across rating chips, KPI heatmap, the score-cell ramp, the sector donut, and the favicon (#278); the neutral surfaces → warm parchment (light) / umber (dark) (#282). Both light + dark, system-theme default kept, WCAG AA on the brand pairs. Fully token-driven (CSS custom properties), so scheme/variant flips re-resolve every value.

- **Data-branch `results/` layout grouped by kind.** Per-year series moved to
  `results/series/{cnn_fg,yield_curve}/`; every per-universe audit JSON moved
  under `results/audit/<universe>/` (federal-contractors, aggregated-scores,
  enhanced-kpi-screener). Demo snapshots (`results/demo/`) and the universe
  audit (`results/audit/universes-*.json`) are unchanged. Config, the snapshot
  workflows, the demo loader, and docs all route through the new paths; the
  `data` branch is migrated in lockstep so the live demo never 404s. Plan:
  `docs/plans/restructure-results.md`.

- **Demo header constrained to the content-column width.** `header` now shares
  `main`'s `max-width: 1400px; margin: 0 auto`, so on wide viewports the title and
  the theme / report-issue / updated meta align with the cards instead of
  stretching edge-to-edge. No effect below 1400px.

- **Merged long-term-context chart (#288).** The "CNN F&G long-term" and "5s10s
  slope" tabs collapse into one "Long-term context" chart: the F&G monthly median
  and the 5s10s monthly mean (normalized to 0-100) share the left axis, and the
  **SPY indexed return** sits on a **logarithmic right axis**. All three reconcile
  onto one monthly grid via the new pure `ui/lib/combined.js`
  (`normalizeSlope` / `aggregateMonthly` / `buildCombinedSeries`) +
  `logRightAxis` in `ui/lib/chart_axes.js`. SPY is the derived `equity_spy` series
  on the `data` branch (ADR-0011, never raw index levels).

- **`NOTICE` expanded to the full third-party-attribution convention (matches the
  paperverse sibling).** Now opens with the project's Apache-2.0 license header
  and reproduces/points to the verbatim license texts of every bundled,
  redistributed component shipped in the built UI: Chart.js (MIT), Fuse.js
  (Apache-2.0), and the **Inter + JetBrains Mono fonts** (SIL OFL 1.1) — the
  fonts were previously omitted. Non-redistributed Python/JS dependencies are
  explicitly excluded. Also corrects a stale "MIT" reference in
  `docs/data-sources.md` (the repo is Apache-2.0).

- **qte77 watchlist expanded to 100 symbols (+27).** Added Allianz (`ALV.DE`),
  Deckers (`DECK`), Enel (`ENEL.MI`), Comfort Systems (`FIX`), Intl Container
  Terminal Services (`ICTEF`), InterDigital (`IDCC`), Louisiana-Pacific (`LPX`),
  Moody's (`MCO`), Meta (`META`), Monster Beverage (`MNST`), Monolithic Power
  (`MPWR`), NetEase (`NTES`), Qualcomm (`QCOM`), REA Group (`REA.AX`), Sezzle
  (`SEZL`), Sterling Infrastructure (`STRL`), TSMC (`TSM`), Clear Secure (`YOU`),
  SK hynix (`000660.KS`), Zhejiang NHU (`002001.SZ`), kakaku.com (`2371.T`),
  Realtek (`2379.TW`), MediaTek (`2454.TW`), Evergreen Marine (`2603.TW`), Yutong
  Bus (`600066.SS`), Organo (`6368.T`) and Advantest (`6857.T`). Each symbol was
  verified against the yfinance KPI surfaces the screener reads
  (`.info` / `.income_stmt` / `.cashflow`); inline `# Name` comments document the
  cryptic international codes. SK hynix is the lone partial — Yahoo omits a ROIC
  input so that one composite stays `None`; all other KPIs populate.

- **Theme toggle is now a single cycler button instead of the 3-button
  segmented control.** One click advances system → light → dark → system;
  the button shows the active mode as an `<icon> <word>` label so it stays
  glanceable. "System" (follow OS) remains a reachable state, and the
  `?theme=` URL + `localStorage` persistence is unchanged. A visually
  hidden `aria-live="polite"` status region announces each change to
  screen readers, since focus stays on the button after a click.

- **JS tooling + tests consolidated under `ui/` with a Vite build (ADR-0010,
  #289).** `package.json`, the eslint/prettier/vitest configs, and `tests/demo/`
  moved from the repo root into `ui/` (`ui/tests/`), so the root is Python-only.
  `ui/` is now Vite *source* → `ui/dist/` is the deployable; `gh-pages.yaml`
  builds (`npm run build`) and uploads `ui/dist` instead of raw-copying `ui/`.
  Vendored Chart.js/Fuse.js, `favicon.svg`, and `universes.json` moved to
  `ui/public/` (served verbatim under the project base path). The dashboard's
  data still loads at runtime from the `data` branch — never bundled. `Makefile`
  + `validate.yaml` JS steps now run from `ui/`; `validate` also builds the UI to
  catch breakage on PRs.

- **5s10s slope chart de-noised to a weekly mean on the wide windows.** The
  yield-curve tab now aggregates the daily 10y−5y slope to an ISO-week mean for
  the 5y / 10y / all windows (1y stays daily), mirroring the F&G long-term
  monthly view so multi-year context reads as trend rather than noise. New pure
  `ui/lib/weekly.js` (`aggregateWeekly`); client-side only — no change to the
  `data`-branch `results/series/yield_curve/` files. (#308)

- **Refreshed the "Why these charts?" copy for the merged long-term chart
  (#288).** The pane described the F&G long-term and 5s10s charts as separate
  tabs; it now describes the single combined chart — F&G monthly median + the
  normalized 5s10s on the 0–100 axis and the SPY-derived equity index on the log
  axis.

- **Dashboard adopts the qte77 EyeRest brand theming, aligned with the sibling
  paperverse + agentic-job-offer-to-application-kit dashboards.** CSS tokens are
  renamed to the brand-canonical names (`--surface` / `--text-muted` / `--primary`,
  plus a new `--primary-on`) and the light/dark cascade moves to `html[data-theme]`,
  set by a new repo-local `ui/theme.js` that mirrors `qte77.github.io/assets/theme.js`:
  one cycling `◐/○/●` button, `localStorage["qte77-theme"]`, a `themechange` event that
  recolours the charts, a dynamic `aria-label` + `#theme-status` live region,
  `prefers-reduced-motion`, and a `<head>` anti-FOUC guard. The data arc re-tones per
  theme, so rating-chip text uses `--primary-on` to keep contrast in both modes. The old
  `lib/theme.js` + its test are removed (the toggle logic now lives in `ui/theme.js`).
- **Theme toggle no longer writes `?theme=` to the URL on click** — it reads `?theme=`
  on load (deep-links still work) and persists the choice to `localStorage`.

- **README restructured to the qte77 doc-structure canon.** Hero tagline under the H1,
  then **What → How → Why → References → License**: the one-line pitch moves to a hero
  blockquote, a new **Why** section states the keyless-vs-paid-feed gap, **What** is
  trimmed to ≤7 reader-value bullets (field lists / composite formulas / preset details
  now link out to `docs/architecture.md`), and the non-canon `Sample output` /
  `Universe sources` sections fold into What/How. Orientation only; depth lives in `docs/`.

### Fixed

- **CodeFactor E241: collapse multi-space alignment in `enhanced_kpi_screener_longshort` + its test.** Three fixture dicts and a parametrize tuple table in `tests/test_enhanced_kpi_screener_longshort.py` plus the `_NUMERIC_GATES` table in `src/orchestrators/enhanced_kpi_screener_longshort.py` used column-aligned spacing after `:` / `,`. CodeFactor's pycodestyle (which ignores the repo's ruff config) flagged ~57 E241 hits, tanking the two files to F / D grades. Collapsed to single-space; no semantic change. Preferred over a new `setup.cfg [pycodestyle]` override because no sibling qte77 repo uses one and `pyproject.toml` ruff stays the single lint source of truth. Inline-comment `,  # ...` sites (PEP 8 standard) untouched — CodeFactor isn't flagging those.

- **Demo: dark-mode chart grid + axis labels visibility (#205).** Chart.js scale defaults were theme-blind (rgba(0,0,0,0.1) grid lines, near-black tick labels) — vanished against the dark panel. Add scriptable `() => cssVar()` closures for `scales[].grid.color` + `scales[].ticks.color` across `fearGreedChart`, `monthlyFearGreedChart`, `yieldCurveChart`, `timeSeriesChart`, `radarChart`. `sectorChart`'s static `--panel` slice-seam color converts to a scriptable closure too; `radarChart` + `sectorChart` register in `liveCharts` so `bindThemeObserver` re-evaluates their scriptable colors on theme flip. PR #220.
- **CI: `sam.gov` added to lychee's exclude list.** `https://sam.gov/about/terms-of-use` (referenced in `docs/data-sources.md`) returns 403 to lychee's UA, breaking the `linkChecker` job on every unrelated PR. Same pattern as the existing `sec.gov` / `aaii.com` / `naaim.org` exclusions. PR #223.
- **CI: include long/short universes in `demo-snapshot.yaml` fan-out.** PR #228 added `enhanced-kpi-screener-{longs,shorts}` to `universe-builder.yaml` and `docs/demo/universes.json` but missed `demo-snapshot.yaml` — picker showed them, selection painted "no history yet" forever because no snapshot ever landed at `results/demo/enhanced-kpi-screener-*/…`. PR #230.
- **Demo: dedupe the `"no history yet"` empty-hint string.** Extracted into one module-level `EMPTY_HISTORY` const; replaced 5 hardcoded copies + 1 near-duplicate. AHA-warranted (5 of one literal); context-specific strings (`"first cron run pending"`, `"loading manifest…"`) stay inline. PR #224.

- **`docs/demo/types.d.ts`: declare `Row.composite_scores` as nullable.** `src/data_sources/fundamentals.py:FundamentalsSnapshot.composite_scores` is `CompositeScores | None`, which serializes to `null`. The TS declaration was `composite_scores?: CompositeScores;` — optional but not nullable; type narrowing on a literal `null` value would have failed. Now `composite_scores?: CompositeScores | null;`, matching the convention every other nullable field already uses (`?: T | null`). One-line drift fix surfaced by today's contracts audit; the remaining 11 `FundamentalsSnapshot` fields absent from `Row` are intentional per the file's "subset the dashboard reads" header policy and confirmed unused in `docs/demo/`.

- Sector donut legend now reappears after browser zoom-out using ResizeObserver-based auto-hide (#152).

- **`docs/demo/tsconfig.json`: bump `moduleResolution` `node` → `bundler` (and `module` `ES2020` → `ESNext`).** The legacy `node` (node10) resolver is deprecated on the TypeScript 7.0 track and fails `make lint_js` / `make validate` with TS5107. `bundler` is the correct resolver for this browser-native ES-module demo (relative `./lib/*.js` imports with explicit extensions, no Node package semantics). Dev-tooling only; no runtime or behaviour change.

- F&G backfill is now a strict **gap-fill** — it no longer clobbers a
  CNN-direct row's `subindicators` / `previous_*` fields when a whit3rabbit row
  shares the same midnight-UTC date key. The prior `_upsert(force=False)` path
  replaced same-timestamp rows on any content difference; the test meant to
  guard this used an unrealistic intraday timestamp and so missed it (#287).

- Demo dashboard now shows the **full** long-term history. The data loader only
  fetched the last two years, so the CNN F&G long-term + 5s10s slope charts
  stopped at ~2025 even after the data branch was backfilled to 2011 (#287).
  `loadYearsFromBranch` now fetches every year from the series floor (2011)
  through the current year, so the 5y / 10y / all window chips paint the whole
  range.

- **`sp500` universe: `BRK.B` → `BRK-B`.** Yahoo / yfinance uses a hyphen for
  Berkshire Hathaway's Class B share-class symbol; the dotted `BRK.B` resolves to
  all-null KPI rows (verified `0/3` on retry-probe vs `BRK-B` `3/3`). The qte77
  watchlist already used `BRK-B`; this aligns `sp500.txt`. The other empty-data
  symbols from the same audit (`MMC`, latam `.SA` lines and their ADRs `ERJ` /
  `EBR`) are an upstream yfinance `quoteSummary` issue, not symbol errors —
  tracked in #312.

- **No more flash-of-wrong-theme on load for an explicit light/dark
  override.** An inline guard in `<body>` resolves the theme (URL >
  `localStorage` > system) and sets the body class before first paint,
  instead of waiting for the deferred `app.js` module.

## [1.1.0] - 2026-05-31

### Security

- **Bump `idna` 3.13 → 3.16 (CVE-2026-45409 ReDoS in `idna.encode()`).** `[tool.uv].exclude-newer` rolled forward 2026-05-09 → 2026-05-23 so the patched version is reachable; no other transitive bumps. Practical exposure was nil (we never pass external input through `idna.encode()`), but the patched version is trivial to ship.

### Added

- **[`CONTRIBUTING.md`](CONTRIBUTING.md) as the shared dev-workflow doc (#177).** README = humans, AGENTS = AI agents, CONTRIBUTING = both. `AGENTS.md` shrinks to agent-specific rules only.
- **`setup_lychee` accepts a `LYCHEE_URL` override** so a specific lychee version can be pinned without editing the Makefile.

- **Demo: "File feature request or bug" link with GitHub-mark octicon next to the theme picker (#180).** Opens `/issues/new` in a new tab.

- **CNN F&G historical backfill via `whit3rabbit/fear-greed-data` mirror (#164).** Operator-only one-shot (`scripts/backfill_fear_greed_whitrabbit.py`, pinned to upstream SHA `aa4f6009`) extends the dashboard's long-term context from ~13 months back to 2011-01-03. Subindicators stay `null` for backfilled rows. ADR-0005 amendment classifies whit3rabbit as Tier-0.

- **Changelog fragments via [scriv](https://github.com/nedbat/scriv) (#175).** Each PR adds one file under `changelog.d/`; `make changelog_new` / `_preview` / `_release VERSION=X.Y.Z`. `bump-my-version` no longer touches `CHANGELOG.md`.

- **5s10s US Treasury slope tab in the long-term-context panel (#165).** Daily cron (22:30 UTC) pulls yfinance `^TNX` − `^FVX` (percentage points) and commits per-year history to the `data` branch. New "Why these charts?" tab explains the timeframe choices. yfinance fetch is `wrap-degrade` per leg; both legs failing → no write.

- **Aggregated-scores-best-and-worst universe (#184).** New cross-universe meta preset that ranks every ticker across the 7 sector/region universes by mean of their 7 composite scores (`quality / dividend / growth / big_call / aaqs / hgi / screener_score`) and combines the top 25 + bottom 25. New `src/orchestrators/aggregated_scores_best_and_worst.py` (pure orchestrator, DI snapshots dict) + `scripts/build_aggregated_scores_best_and_worst.py` + Sunday `02:00 UTC` cron workflow + ADR-0005 amendment. **NOT a hedging primitive** — composite-mean blends growth/value/quality signals; the hedging-grade gate-based screener ships as Phase 2 (#192).

- **`publish-release.yaml` — opt-in GitHub Release publication (#208).** `tag-release.yaml` creates the annotated `v{version}` git tag on every bump merge but never published a Release object — the Releases page has stayed empty across every prior version. New `workflow_dispatch` workflow publishes a Release for an existing tag (defaults to the latest `v*`), extracting the matching `## [version]` block from `CHANGELOG.md` as release notes (falls back to `--generate-notes` when empty). Decoupled from `tag-release.yaml` so the auto path stays tag-only; operator opts in via `gh workflow run publish-release.yaml`.

- **Demo: per-cell empty-reason tooltips (#170).** When a rendered "—" reflects a structural gap rather than a data lag, the cell now carries a `title` explaining why (dotted underline + `cursor: help` signal the tooltip). New pure module `docs/demo/lib/empty_reason.js::explainEmpty` resolves a declarative rule table against `(sector, industry, currency, columnKey)` — initial rules cover Bank R&D, Bank current-ratio (no current/long-term split), and CAD-bank ROE/ROA (Yahoo gap narrowed to CAD pending #169 survey). Unmatched combos return `null` so no speculative copy ships. 10 new Vitest cases (TDD red → green); rule table widens additively as #168 + #169 surface concrete patterns.
- **`scripts/audit_universes.py` + `src/orchestrators/universe_audit.py` — operator-side universe-coverage audit (#168).** Walks every bundled preset under `src/assets/universes/*.txt` and probes `yfinance.Ticker(sym).info` per ticker, classifying each as `OK` / `SPARSE` / `FAIL` against a 40-populated-field threshold. Surfaces stale-US-ticker rot (the FI → FISV / RY → RY.TO / SUEZY → SZU.DE patterns from the post-#159 sweep) into a structured `results/audit/universes-<UTC>.json` report so per-ticker swap PRs become a triage-from-report flow instead of a manual cron. Boundary policy is `wrap-degrade` — one ticker's yfinance failure produces a `FAIL` entry with the exception in `note` rather than aborting the sweep. Orchestrator (logic) lives in `src/`; thin wrapper script (I/O) lives in `scripts/`, mirroring `build_federal_contractors.py`. 7 unit tests (mocked yfinance) + 1 `@pytest.mark.network` `^GSPC` smoke.
- **Demo: tabbed F&G panel · rolling history ↔ long-term monthly (median + average).** `#fear-greed-section` gains a "Rolling history" / "Long-term context" tab pair sharing the today's-score header. The long-term tab is a per-month reduction (median + average) of the existing `loadFearGreedYears()` data — no new fetch, no schema change. New pure module `docs/demo/lib/monthly.js::aggregateMonthlyFG` buckets by UTC `YYYY-MM` so boundaries stay stable across viewer timezones; empty F&G fetch renders a centered "no F&G history yet" hint instead of a blank canvas. Monthly chart is lazily constructed on first long-term tab click (matches the detail-panel time-series lazy pattern). 8 new Vitest cases (TDD red→green). Documented under "Backfillable on any cron run" in `docs/cnn-fg-api.md`.
- **Demo: click-to-filter sector donut + readable dark-mode palette + tidier universe layout.** Six topic-grouped commits on the demo dashboard:
  - **GICS color palette** — `docs/demo/lib/sector.js` gains a `sectorColor(name)` lookup (12 muted hex tones tuned for both light `#ffffff` and dark `#2c2c2e` panels; null bucket and unknown sectors map to neutral grey). The donut now passes per-slice `backgroundColor` to Chart.js; slice borders read from the live `--panel` custom property so seams blend in both themes. Legend swatches inherit the slice colors automatically — fixes the dark-mode "empty grey ring" rendering. 5 new Vitest cases (TDD red→green).
  - **Click slice / legend to filter by sector** — clicking a donut slice (or its legend entry) filters the table to that sector and pulls the slice outward via Chart.js `dataset.offset` for visual confirmation; clicking the same slice again clears the filter. A small accent-colored chip in the controls row shows the active sector with an `×` to clear. State persists via `?sector=<label>` in the URL. `lib/state.js` gains a `sector` field with parse/serialize coverage (round-trip + empty-value-to-null).
  - **Donut tooltip percentages + empty-state hint** — tooltips read `Sector: count (pct%)`; empty snapshots render a centered "no data" hint inside `#sector-donut-wrap` instead of a blank canvas.
  - **Picker replaces, no longer accumulates** — switching universes via the dropdown was previously appending to the multi-universe overlay in detailed mode, surprising users. The picker now always replaces; overlay behavior stays reachable via `?universe=a,b,c` deep-links and chip `×` removal so the existing tests + code path keep working.
  - **Controls-left / donut-right grid layout** — `#universe-controls-row` is now a 2-column grid (`1fr 280px`) that collapses to a single stacked column below 767px. The redundant `"Universe · X tickers"` H2 is removed; the picker label leads with the ticker count inline next to it. Donut height shrinks from 180 to 160px.
- **Multi-universe overlay + per-ticker time-series tab (#137).** Detailed-mode-only. Picker still selects the primary universe; in detailed mode a second selection adds the universe to the overlay rather than replacing it. Each active overlay universe shows as a `#universe-chips` chip with a `×` to remove. URL `?universe=primary,extra1,extra2` round-trips. A new `Universe` column appears in the table when ≥2 universes are active (CSS toggled via `body.overlay-active`). Detail panel gains an `Overview` / `Time series` tab pair; the time-series tab renders a Chart.js multi-line of Screener / Quality / Growth / Sortino across `manifest.dates` for the picked ticker. Pre-#136 backfill the series is short (~5 points) and shows a hint chip; post-#136 the same code consumes the 17-month grid with no migration. New pure modules `docs/demo/lib/overlay.js` (`mergeUniverseSnapshots`) + `docs/demo/lib/timeseries.js` (`buildTimeSeries`); 12 non-trivial Vitest cases.
- **Theme toggle (system / light / dark).** New 3-button segmented control in the header overrides the prior `prefers-color-scheme`-only dark mode shipped with #134. Default stays "system" (follows OS). Choice persists via `?theme=` URL query + `localStorage`. CSS refactored: dark palette driven by custom-property overrides on `body.theme-dark` (forced) OR `body.theme-system` under the media query — one variable, three triggers. New `docs/demo/lib/theme.js` with `resolveTheme` + `isThemeMode` (precedence: URL > localStorage > "system"); 8 Vitest cases.
- **Demo v2 simple/detailed toggle dashboard (#134).** New `<button id="view-toggle">` flips `body.view-simple` / `body.view-detailed`; 8 of 13 KPI columns + detail aside + CSV button hide in simple mode. Adds: A1 conditional cell coloring, A2 URL state for view/sort/filter/date, A3 CSV export, A4 external links (Yahoo / SEC EDGAR / Wikipedia), A5 empty/loading states, B1 composite radar, B3 sector donut, D1 `/` focuses filter, D2 dark-mode via `prefers-color-scheme`, D3 mobile auto-simple <768px. Pure-JS units extracted into `docs/demo/lib/{audit,coloring,csv,sector,state}.js` with Vitest harness (closes #131). ESLint/Prettier deferred per #135.
- **Dashboard universe-picker + Federal Contracts detail section (#130).** `docs/demo/index.html` gains a `<select id="universe-picker">` populated from the new `docs/demo/universes.json` manifest (8 bundled presets); `?universe=<id>` query param persists across reloads via `history.replaceState`. `docs/demo/app.js` adds `loadAudit(universe, date)` (silent-404; only fetches for `federal-contractors`) and appends a "Federal Contracts" section to `showDetail(row)` when the row's symbol joins to an `AuditRow.final_ticker`. `.github/workflows/demo-snapshot.yaml` now fans out across all 8 universes via a matrix (`fail-fast: false`); the verified-commit step retries on 422 `Reference cannot be updated` so concurrent matrix legs writing to the `data` branch don't lose snapshots to ref-update races. `workflow_dispatch` accepts an optional `universe` `type: choice` input that collapses to a single leg for ad-hoc dispatch. Vitest unit harness deferred to #131.
- **Federal-contractors universe orchestrator (Item 3b)** — `src/orchestrators/federal_contractors.{build_universe,AuditRow}` chains usaspending → EDGAR → yfinance; CLI `--refresh-universe federal-contractors`; bundled preset (`src/assets/universes/federal-contractors.txt`, 26 entries) + weekly refresh workflow + ADR-0006 amendment.
- **`src/usaspending.py` — POST top-contractors API client (Item 3a).** Wraps `api.usaspending.gov/api/v2/search/spending_by_category/recipient/` per the verified upstream contract. Public surface: frozen `RecipientRecord` pydantic model (`name`, `recipient_id`, `code` (DUNS), `uei`, `amount`, `total_outlays`, `rank`) plus `fetch_top_contractors(fy_start, fy_end, *, limit, naics_codes, award_type_codes)`. Default NAICS filter is `None` (broad "top contractors by obligated $" across sectors); `naics_codes=[...]` wraps into the contract's `{"require": [...]}` dict shape. Drops the `"MULTIPLE RECIPIENTS"` aggregate row (`recipient_id is None`) before ranking; assigns rank from post-filter list position. 100% test coverage; cycle 4 includes `@pytest.mark.network` live FY2025 round-trip. `settings.usaspending_url` + `settings.usaspending_timeout_sec = 30` added to `AppSettings`. `settings.federal_contractors_dir = Path("results/federal_contractors")` reserved for the upcoming Item 3b orchestrator. Strict R/G/R cycles throughout (one commit per phase, one push per cycle).
- **`src/config.py` — centralised runtime config via `AppSettings(BaseSettings)`.** Every URL endpoint, filesystem path, HTTP-shape constant (`Accept`, `Referer`, CNN User-Agent), and request timeout that previously lived as a module-level constant across `src/sec/`, `src/sentiment.py`, and `src/__main__.py` now resides in a single `pydantic-settings` model. The module-level `settings` singleton is what downstream callers import. Env-var override is free via the `SSK_` prefix (e.g. `SSK_REQUEST_TIMEOUT_SEC=30`). Defaults reproduce the pre-refactor literals exactly; behaviour unchanged. Domain / algorithm constants (`_TRADING_DAYS`, `_STALE_10Q_DAYS`, `_TABLE_QUOTE_TYPES`) intentionally stay co-located — they're not user-overridable runtime config.
- **`src/sec/submissions.py` — EDGAR last-filed dates per US form type (10-K / 10-Q / 8-K).** Implements ADR-0006 UC1: per-ticker enrichment using EDGAR's `data.sec.gov/submissions/CIK<10>.json` endpoint. New `LastFiledSnapshot` (frozen pydantic) carries the three optional date fields; `enrich_snapshot_sec(symbol)` resolves the CIK via `src.sec.cik_map`, fetches submissions, and returns a dict ready for `FundamentalsSnapshot.model_copy(update=...)`. Non-SEC-registered Yahoo symbols (FX, crypto, futures) bypass the EDGAR call. `FundamentalsSnapshot` gains three optional enrichment fields (`sec_last_10k_date`, `sec_last_10q_date`, `sec_last_8k_date`) attached post-fetch in `src/__main__.py`. The Rich summary table gains a `Days 10-Q` column that renders as `"{n}d"`, wrapping in `[red]…[/red]` markup when the most-recent 10-Q is older than 150 days. Strict TDD throughout the build.
- **ADR-0007 — package vs repo-infrastructure boundary.** Formalizes the three concentric scopes (package `src/` + `README.md` → ships in wheel; repo infrastructure `scripts/` + `.github/` + lint configs → CI-only; demo + dev docs `docs/demo/` + `docs/*.md` + `tests/` → reference / showcase) plus a one-way direction rule (Scope 2/3 may import Scope 1; Scope 1 must not reference Scope 2/3 paths, and the `data` branch is consumed only by the demo) and a path-write rule (`src/` writes only to user-controlled paths, never to its own install location). Drives the ADR-0006 amendment that moves usaspending logic into the package.
- **`src/sec/cik_map.py` — CIK ↔ ticker resolver via EDGAR's `company_tickers_exchange.json`.** Foundation layer for SEC EDGAR integration (ADR-0006 UC3). Frozen pydantic `CikRecord` model + `resolve_cik(ticker)` returning a 10-digit zero-padded CIK string (or `None` for non-SEC-registered Yahoo symbols like FX, crypto, futures). Module-level cache fetches the EDGAR JSON once per process. Keyless; sends browser-shape `User-Agent` from `src/utils/http_ua.py`. Strict TDD throughout the build.
- **ADR-0005 — three-tier sentiment + risk source framework.** Documents the auth-tier classification (Tier 0 keyless / Tier 1 free-key opt-in / Tier 2 paid opt-in) that gates default-on behavior, env-var requirements, and `data`-branch persistence eligibility for every current and future sentiment / risk source. Tier 0 (CNN F&G, Yahoo-Finance-proxied volatility) stays default-on; Tier 1 (Nasdaq Data Link — NAAIM, AAII; sam.gov future enrichment for the federal-contractors universe) requires env-var opt-in; Tier 2 (Bloomberg `blpapi`, GS `gs-quant`, State Street institutional) is runtime-only and never persisted publicly. Closes #22.
- **ADR-0006 — federal-contractors universe via usaspending.gov + EDGAR.** Scopes a Tier-0 (keyless) pipeline that ranks the top-100 US federal contractors by trailing-fiscal-year contract obligations (`usaspending.gov spending_by_category/recipient`), bridges legal names to Yahoo-resolvable tickers via SEC EDGAR `company_tickers_exchange.json`, and gates final entries through `yfinance.Ticker(...).fast_info`. Subsidiaries roll up to the parent ticker; a curated DoD Top-25 publicly-traded seed list is always included. Output preset `src/assets/universes/federal-contractors.txt` is refreshed weekly via a new workflow that commits an audit JSON to the `data` branch and opens a PR with the preset diff (suppressed when empty). sam.gov is documented as future Tier-1 enrichment; not in the critical path. **Amended 2026-05-21 (Library-first architecture):** core logic relocated into `src/usaspending.py` + `src/federal_contractors.py` per ADR-0007; the script becomes a thin wrapper.

### Fixed

- **Demo: 5s10s slope tab stuck on `loading…` when no history yet.** The lazy-render path overwrote the existing `.yc-empty` element instead of skipping when one was already there.
- **Demo: unified the empty-history label.** F&G rolling / F&G long-term / 5s10s slope all now read `no history yet` (was three different strings).

- **`yield-curve.yaml` cron silently skipped commit on first run.** `git status --porcelain` summarises untracked directories instead of enumerating their contents; the detect-step's awk regex then matched nothing and the workflow reported "no yield-curve history changes". `-uall` enumerates files inside untracked dirs so the first run writes to `data` branch as intended. Same `-uall` defensive fix applied to `fear-greed.yaml`.
- **Yield-curve first run now backfills 5 years of history** instead of writing only today's reading. `main()` detects an empty `results/yield_curve/` and calls the new `fetch_yield_curve_history(period="5y")`; subsequent daily runs continue to fetch just today's snapshot. Chart now paints something useful on first deploy.

- **Demo: Fear & Greed line chart readable in dark mode (and repaints instantly on theme toggle).** `renderFearGreedChart` previously baked `borderColor: "#1d1d1f"` + `backgroundColor: "rgba(29, 29, 31, 0.08)"` at construction time. In dark mode `--text` flips to `#f5f5f7` but the chart never re-read it, so the line and fill sat near-black on `#2c2c2e`. The F&G, monthly F&G, and detail-panel time-series charts now read their theme-coupled colors (`--text`, `--accent`, `--rating-*`) via Chart.js scriptable color functions resolved on each draw cycle, and a single `MutationObserver` on `document.body` triggers `chart.update("none")` on every tracked instance when the `theme-system` / `theme-light` / `theme-dark` class flips — no more waiting for hover-driven redraws.
- **Demo row click no longer silently opens Yahoo Finance via `window.open`.** Simple-mode rows are now non-actionable (detail panel stays `class="detail-only"` and hidden); detailed-mode rows open the side panel as before. External-link visits go through the panel's visible `<a href>` anchors only — no invisible JS click referrals.
- **`_persist_snapshots` JSON-serializes `date` enrichment fields** — `s.model_dump(mode="json")` so `sec_last_*_date` (now populated since PR #127 unblocked SEC) become ISO strings instead of crashing `json.dumps`. Regression for [run #26303499996](https://github.com/qte77/analyze-stock-kpi/actions/runs/26303499996).
- **SEC EDGAR `User-Agent` now identity-shape** — default `"opensource-research-client contact@example.com"` (RFC 2606 placeholder, no PII / repo fingerprint); operator overrides via `SSK_SEC_USER_AGENT` env or CI repo variable `vars.SEC_USER_AGENT` (optional — `AppSettings(env_ignore_empty=True)` ignores empty-string env so unset `vars` falls through to the in-source default). See [ADR-0006 amendment 2026-05-22 (later)](docs/decisions/0006-federal-contractors-universe.md#amendment-2026-05-22-later--sec-anti-bot-ua-shape).
- **CodeFactor `B108` quiets in `tests/test_config.py`** — `# nosec B108` matching existing pattern on lines 75/80.

### Changed

- **Demo: simple/detailed toggle moves below the filter + CSV row** and reads `Detailed view: Show all KPI columns` / `Simple view: Show essentials only` (label + muted desc with a CSS-injected `": "` separator). Mobile hide preserved.

- **Demo: dashboard layout polish.** `#universe-header` rows all share a width (filter+CSV defines the max); `Universe:` prefix dropped (label now `aria-label`); chart-wrap rules collapsed into a grouped selector.

- **Aggregator universe splits into a paired-universes set (#184 follow-up).** `aggregated-scores-best-and-worst` (combined 50-ticker preset shipped earlier today) replaced by two separate universes: `aggregated-scores-best` (top 25) + `aggregated-scores-worst` (bottom 25). One orchestrator ranking pass still produces both; the script writes two preset files; the universe-builder workflow's matrix dispatches each leg separately and each leg commits only its own preset via the existing pathspec fix. Dashboard picker shows two entries (`Aggregated scores (best 25)` + `Aggregated scores (worst 25)`); each is independently sortable, filterable, and URL-linkable. Establishes the paired-output pattern Phase 2 #192 (`enhanced-kpi-screener-longshort`) reuses with gated criteria.

- **`bump-my-version.yaml` collects changelog fragments inside the workflow (#208).** Adds a `scriv collect --version $NEW` step after the version bump so the release PR carries `pyproject.toml` + README badge + `CHANGELOG.md` in one shot. Eliminates the "remember to run `make changelog_release` first" footgun documented in `pyproject.toml:142`. No-op when `changelog.d/` is empty (patch bumps without fragments still work).

- **CI: consolidated per-universe refresh workflows.** `federal-contractors-refresh.yaml` + `aggregated-scores-best-and-worst-refresh.yaml` collapse into one matrix-driven `universe-builder.yaml`; one Sunday `02:00 UTC` cron; `workflow_dispatch` with empty `universe` input runs all in parallel, with `universe` set collapses to a single leg. Adding a future universe (e.g. Phase 2 #192) takes one option line + one matrix entry + one `case` branch instead of a 130-line copy-paste. Fixes two duplication-bugs from the parallel-workflows era: invalid JS escape (#194) and preset-PR bundling 100k lines of staged index state (#195). Consumers running `gh workflow run <name>` directly: switch to `gh workflow run universe-builder.yaml -f universe=<id>`.

- **Rename ruff rule code `TCH` → `TC` in `pyproject.toml`.** `TCH` is the deprecated alias; `TC` is the modern code for flake8-type-checking. Functionally identical under ruff 0.15; future-proof against ruff 1.0 dropping the alias. Aligns with the shared `py-harden-ruff.md` recipe doc.
- **Docs restructure (Item 6b)** — single-source-of-truth + concision. AGENTS.md "Active modules" list removed (docs/architecture.md owns it). README.md "Sample output" JSON dump trimmed (links to source). docs/architecture.md `Modules` tree refreshed for the three-tier layout; "Planned modules" section dropped (all shipped). roadmap.md marks federal-contractors + gh-pages + static dashboard as done. Stale `results/fundamentals_<UTC>.json` references repaired across 5 docs.
- **`src/` restructured into three-tier sub-packages** — `src/domain/`, `src/data_sources/` (incl. `sec/`), `src/orchestrators/`. Pure rename + import-path updates; no behaviour change.
- **CNN F&G UA centralised on `src.utils.http_ua.STABLE_USER_AGENT`** — `AppSettings.cnn_fg_user_agent` removed (it duplicated `USER_AGENTS[0]`). SEC keeps random rotation via `pick_user_agent()`; CNN pins to `STABLE_USER_AGENT` to avoid WAF profiling.
- **`USER_AGENTS` pool moved into `AppSettings.user_agents`** — `src/utils/http_ua.py` now re-exports `USER_AGENTS` + `STABLE_USER_AGENT` from settings; single source of truth, env-overridable via `SSK_USER_AGENTS`.
- **`results/` source-aligned**: top-level `fundamentals_<UTC>.json` writes moved into `results/fundamentals/<UTC>.json`. New `settings.fundamentals_dir = Path("results/fundamentals")`. `demo-snapshot.yaml` `mv` updated.
- **`docs/data-sources.md` — Redistribution guardrails section (verified 2026-05-21).** Independent ToS / license audit per source for committing derived outputs to the public `data` branch. Verdicts: usaspending.gov **CLEAR** (CC0 + DATA Act), SEC EDGAR **CLEAR** (17 USC § 105 federal-works public-domain), yfinance raw payloads **CAUTION** (Yahoo ToS §2.4(i)/§2.8 prohibits redistribution; derived ticker list + resolution boolean **CLEAR**), `fedspendingtransparency/usaspending-api` API contract files **CLEAR** (CC0; verbatim fixture copy OK), CNN F&G numeric values **LOW RISK** (revised after deeper precedent research: *Feist* rules numeric facts uncopyrightable; *Van Buren* / *hiQ* rule User-Agent spoofing is not CFAA "gate circumvention" on publicly-accessible endpoints; zero CNN takedowns on record against any of ≥10 public F&G redistributors on PyPI/Kaggle/GitHub). Standing rule that lands with this: `AuditRow` in the upcoming `src/federal_contractors.py` MUST NOT carry any `fast_info` / `info` fields — only the ticker symbol + boolean.
- **`docs/data-sources.md` usaspending.gov section re-verified against the upstream API contract (2026-05-21).** Five corrections sourced from `fedspendingtransparency/usaspending-api/.../recipient.md`: (a) per-result `code` field is **DUNS** (9-digit legacy), not UEI; `uei` is a separate field that is frequently `null` even on legitimate contractor rows. (b) The internal hash field is `recipient_id`, not `id`. (c) `total_outlays` is part of the response (nullable). (d) The first result is often a `"MULTIPLE RECIPIENTS"` aggregate row with all three identifiers null — must be filtered before ranking. (e) `filters.naics_codes` is a dict (`{"require": [...], "exclude": [...]}`), not a list. Adds a "Why POST instead of GET" note documenting the search-API design convention. Pre-implementation correction; no source code changes.
- **Boundary failure-policy table in `docs/architecture.md`.** Single source of truth for every I/O boundary (network / filesystem / parse / external-library) and its failure policy — one of `fail-loud`, `wrap-degrade`, or `wrap-continue`. Future PRs touching I/O update the row; future reviewers consult the row before approving silent error handling.
- **`src/sec/cik_map.py::_fetch_json` falls back to cache on network failure.** New `except urllib.error.URLError` arm: when a cache file exists, a logged WARNING is emitted and the cached body is returned (wrap-degrade); without a cache the error propagates as before (fail-loud cold start). Concrete impact — a transient SEC outage no longer kills the whole `python -m src` run.
- **`src/sec/submissions.py::enrich_snapshot_sec` wraps `fetch_last_filed` failures.** `URLError` (parent class of `HTTPError`) is caught, logged as a warning, and degraded to `{}` — exactly the same shape as the no-CIK bypass. One ticker's SEC fetch failure now leaves enrichment empty for that ticker only; the universe run continues.
- **ruff `TRY` rule family added.** `[tool.ruff.lint].select` adds `TRY` (tryceratops). `TRY003` (long messages outside exception classes) is globally ignored — defensive one-off raises with informative messages are fine without custom exception classes. The other TRY rules (`TRY002` no vanilla `Exception`, `TRY200`/`TRY201` `raise ... from` chains, `TRY300` `else` for happy path, `TRY301` no `raise` inside `try` when re-raising after logging) all pass clean on the existing codebase.
- **EDGAR ticker registry now disk-cached with HTTP conditional GET.** `src/sec/cik_map.py::_fetch_json` persists `company_tickers_exchange.json` to `results/edgar/` (configurable via `settings.edgar_cache_dir` / `SSK_EDGAR_CACHE_DIR=...`) and sends `If-Modified-Since` (cache file mtime → HTTP-date) on every subsequent call. On `304 Not Modified` the cached body is reused; on `200 OK` the cache is overwritten and the file mtime is re-stamped to the server's `Last-Modified` value. Steady-state network cost drops from ~13 MB per `python -m src` run to ~200 B (one 304 response). Cache directory auto-creates; missing `Last-Modified` headers tolerated; no behavior change for the in-process `_records_cache`. `results/edgar/` gitignored. Strict TDD: 7 R/G cycles + 1 `@pytest.mark.network` live-EDGAR roundtrip.
- **ruff lint rule set widened.** `[tool.ruff.lint].select` adds `B` (flake8-bugbear), `SIM` (flake8-simplify), `RUF` (ruff-specific), `PT` (pytest-style), `ANN` (flake8-annotations), `TCH` / `TC` (flake8-type-checking), `PGH` (pygrep-hooks), `D` (pydocstyle, `convention = "google"`) on top of the existing `E`, `F`, `I`, `N`, `W`, `UP`, `C90`, `S` baseline. Each entry carries an inline comment describing the rule family. Per-file ignores extended: `tests/**` adds `D` (no docstring requirement on tests; `S101` already there), `scripts/**` adds `D` + `ANN` (one-off scripts; over-annotating is noise). Two `# noqa: TC001` / `# noqa: TC003` markers stay in `src/fundamentals.py` because pydantic needs runtime access to `CompositeScores` / `date` for model field resolution. Existing code touched only to satisfy the new rules; behaviour unchanged.
- **CodeQL config inlined.** The `paths-ignore` rule (excluding vendored `docs/demo/vendor/**`) now lives in the `Initialize CodeQL` step's `config:` input in `.github/workflows/codeql.yaml`, co-located with the action invocation. The standalone `.github/codeql/codeql-config.yml` is removed. No behavioural change to CodeQL analysis — same paths excluded, same SHA-pinned action versions.

## [1.0.0] - 2026-05-17

### Removed

- `.github/dependabot.yaml` (the duplicate config that used the broken `pip` ecosystem — no-op for this uv-managed repo). The remaining `.github/dependabot.yml` now carries the `commit-message` prefix + labels that previously lived only on the deleted file. Dependabot only ever loaded one of the two configs anyway; this removes the ambiguity.

### Changed

- `llms.txt` is now **auto-generated** at `docs/llms.txt` by the `llms-txt.yaml` workflow using the [qte77/gha-llms-txt-action](https://github.com/qte77/gha-llms-txt-action) composite action (Marketplace-listed; pinned to the v0.1.0 commit SHA per the repo's full-SHA rule). The hand-curated `llms.txt` at repo root is replaced by a template at `.github/templates/llms.txt.tpl` that uses `${BLOB}` / `${PROJECT_NAME}` / `${PROJECT_DESC}` envsubst variables. The action validates that every `${BLOB}/path` reference points to an existing file, preventing stale links over time.
- **complexipy cognitive-complexity gate tightened from 15 to 10** in `make check_complexity` (and the validate CI path). The current codebase peaks at 9 (`_batch_close_prices`, `_index_subindicator_data_by_date`), so this is a no-op for existing code but prevents regressions. Brings the cognitive-complexity ceiling in line with the existing ruff mccabe `max-complexity = 10`, so both gates now enforce the same budget.
- **ruff `S` rule set (flake8-bandit) enabled** in `tool.ruff.lint.select`. Replaces the legacy Bandit `# nosec B310` markers with ruff-native `# noqa: S310` on the two `urllib.request` call sites in `src/sentiment.py` (the explicit `https://` scheme check is the defense-in-depth boundary, kept inline). The single test-side `subprocess.run` in `tests/test_build_demo_manifest.py` gets `# noqa: S603` (hardcoded local script, no external argv). `tests/**` continues to ignore `S101` (pytest `assert` convention). Future security regressions are now caught by `make lint` instead of needing a separate Bandit invocation.
- `screener_score` rewritten as a factor-weighted composite. The 9 KPIs are grouped into 4 thematic factors (Profitability, Valuation, Risk, Momentum) with per-factor input minimums (>= 2/4, >= 1/2, >= 1/2, 1/1); factors below their minimum drop from the composite and remaining factors weigh equally. The previous input-equal mean over-weighted Profitability (4 of 9 inputs = 44%); the new math gives each thematic dimension equal voice. Existing >= 5 of 9 total-input gate unchanged. Tooltips on the Score column and detail panel updated to spell out the per-factor minimums.

### Fixed

- Dashboard row-detail panel now dismisses on outside click or Escape, while
  clicks inside the panel and row-to-row detail swaps keep the panel open.

- **Dashboard `<thead>` actually sticks on vertical scroll now.** `docs/demo/style.css` `.table-wrap` previously set only `overflow-x: auto`, which per CSS spec makes the wrapper the containing block for nested `position: sticky` elements but provides no vertical scroll port — so `thead th { top: 0 }` had nowhere to stick and scrolled away with the page. Switched the wrapper to `overflow: auto` + `max-height: 75vh` so both sticky-top (thead) and sticky-left (Ticker + Name columns) anchor against the same scroll port. Delivers on the v0.6.0 "sticky `<thead>` so column headers stay visible on vertical scroll" CHANGELOG promise.

## [0.6.0] - 2026-05-15

### Added

- **Static demo dashboard on GitHub Pages** at `https://qte77.github.io/analyze-stock-kpi/` (#59) — F&G 2-year chart + sortable universe table with date selector. Vanilla HTML/JS/CSS in `docs/demo/`; Chart.js v4.5.1 via CDN; no build step. Deploys via modern `actions/upload-pages-artifact` + `actions/deploy-pages` in `.github/workflows/gh-pages.yaml`.
- **Weekly fundamentals snapshot workflow** `.github/workflows/demo-snapshot.yaml` (Sunday 06:15 UTC) commits `results/demo/qte77-watchlist/YYYY-MM-DD.json` + `index.json` manifest to the `data` branch.
- **`scripts/build_demo_manifest.py`** — stdlib-only Python that rebuilds the per-universe manifest from on-disk snapshot files.
- **Snapshot enrichments** — `trailing_peg_ratio` (alias `trailingPegRatio`), `roi` (computed from `info`: NetIncome / (BookEquity + Debt - Cash)), `rd_to_revenue` (from `Ticker.income_stmt`, EQUITY-gated), `sortino_ratio` (annualized 1y, batched via `yf.download` at universe level). Per [ADR-0004](docs/decisions/0004-price-history-composite-input.md).
- **7th composite score** `CompositeScores.screener_score` — aggregates the 9 visible main-table KPIs into a single 0-100 ranking.
- **Dashboard KPI expansion** — `docs/demo/` main table goes 8 → 13 columns (P/E (fwd) · PEG · Beta · R&D/Rev % · Op M % · ROE % · ROA % · Current · Sortino · Score added; original `P/E` and `Div %` moved to detail panel). English `title=` tooltips on every column header and detail-panel label. Default sort: descending by Score. Per-row Weight % (= 100 × score / sum) shown in `<tr>` tooltip. Mobile-graceful CSS: sticky Ticker + Name columns, horizontal scroll, full-screen detail drawer at ≤640px.

### Changed

- **`fear-greed.yaml` rewritten** to use the verified REST Git Data API commit pattern via `actions/github-script@v9`, targeting the `data` branch. Restores the cron that broke on 2026-05-11 when the `required_signatures` ruleset was activated and rejected `stefanzweifel/git-auto-commit-action@v5`'s unsigned pushes.
- **All workflow actions pinned to full-length commit SHAs** per the repo's new "Require actions to be pinned to a full-length commit SHA" rule. Migrated `validate.yaml`, `sbom.yaml`, `bump-my-version.yaml`, `links-fail-fast.yml`, `codeql.yaml`.
- Defer the v0.6.0 RS hedging epic per [ADR-0003](docs/decisions/0003-defer-rs-hedging-epic.md). Parent issue #4 and sub-issues #8 / #9 / #10 stay open with the `deferred` label; #55 (RS alternatives survey) closes as resolved by the ADR. v0.6.0 milestone repurposed to the demo dashboard above. Behavioral price analytics (pandas, time-series, regime classification) fits a sibling repo rather than this CLI.
- **Composite-score inputs** extended to include price-history-derived terms ([ADR-0004](docs/decisions/0004-price-history-composite-input.md)), amending ADR-0002's point-in-time-only scope. `fetch_universe_fundamentals` now makes one batched `yf.download` per `make run` for the whole universe.
- **`screener_score` requires ≥ 5 of 9 inputs** to return a non-`None` value (`_SCREENER_MIN_TERMS` constant in `src/composite_scores.py`). Informationally-thin tickers — mostly FX / futures / crypto / very sparse ADRs — show "—" in the Score column instead of a misleading partial score. Per-row dashboard tooltip gains the input count (`N / 9 inputs`) alongside the existing Weight % and raw Score.

### Fixed

- **Detail-panel off-by-one** — the `dl()` helper in `docs/demo/app.js` emitted a stray `<dd>` for section-header rows, shifting every following label/value pair right by one cell. The Composite Scores block now lines up correctly.

- **Dashboard UX polish**: Score-column heatmap (red→yellow→green gradient via HSL, higher = greener), fuzzy filter input over Ticker / Name / Sector with typo tolerance (Fuse.js 7.0.0, Apache-2.0, vendored at `docs/demo/vendor/`), sticky `<thead>` so column headers stay visible on vertical scroll. No telemetry — Fuse.js bundle audited and is pure client-side string matching.

### Removed

- Four trivial `defaults_to_none` tests in `tests/test_fundamentals.py` (`test_snapshot_{roi,rd_to_revenue,sortino_ratio,beta}_defaults_to_none*`). All four asserted that a `float | None = None` field defaults to `None` — which is what the type annotation literally says. Regression coverage for "field stays optional" is provided by `test_snapshot_handles_sparse_info` (the GC=F fixture constructs successfully without any of these fields).

## [0.5.1] - 2026-05-11

### Added

- `llms.txt` at the repository root — spec-compliant index per
  [llmstxt.org](https://llmstxt.org/) pointing LLM consumers at the
  authoritative README / AGENTS / architecture / ADR / source files.
  Hand-curated rather than template-generated (KISS); update inline
  when the documentation hierarchy moves.
- `.github/workflows/sbom.yaml` — Software Bill of Materials generation
  via [`qte77/gha-sbom-action@v0.1.1`](https://github.com/qte77/gha-sbom-action).
  Runs on push to `pyproject.toml` / `uv.lock`, weekly Sunday cron,
  and manual dispatch; opens an auto-PR with the SPDX SBOM and a
  markdown summary under `docs/SBOM/` whenever the dependency graph
  changes.

### Changed

- **Project renamed**: `scrape-stock-kpi` → `analyze-stock-kpi`. Reflects
  the post-Traderfox reality — the codebase no longer scrapes anything
  (yfinance is a library, CNN F&G is a documented JSON endpoint). The
  GitHub repository was renamed in the same change; GitHub auto-redirects
  the old URLs. `importlib.metadata.version("analyze-stock-kpi")` reads
  from `[project].name` in `pyproject.toml`.

### Fixed

- `FundamentalsSnapshot.dividend_yield` is now normalized at the fetch
  boundary via a new `_normalize_yfinance_info` helper called from
  `fetch_fundamentals`. Current yfinance ships `info["dividendYield"]`
  as a percentage (e.g. `0.37` for AAPL's 0.37 % yield); the helper
  divides by 100 so downstream consumers (rich table, JSON output,
  `composite_scores._YIELD_HI` bound, `_format_percent`) see one
  consistent fractional convention (#43).

## [0.5.0] - 2026-05-10

Adds composite proxy scores derived from each `FundamentalsSnapshot`.
Six 0-100 proxies — Quality, Dividend, Growth, Big Call, AAQS, HGI —
with simplified formulas using only point-in-time inputs plus
`info["beta"]`. Multi-year trend formulas (Piotroski, CAGR, FCF
coverage) are deliberately deferred per
[`docs/decisions/0002-simplified-composites.md`](docs/decisions/0002-simplified-composites.md).

### Added

- `src/composite_scores.py` — `CompositeScores(BaseModel)` plus
  `quality` / `dividend` / `growth` / `big_call` / `aaqs` / `hgi`
  score functions and a `compute_scores(snap)` entry point. Each
  score is a `float | None` in `[0, 100]`; `None` propagates from
  missing inputs except `big_call`, which reweights proportionally
  over its non-`None` Q/D/G components (#18).
- `tests/test_composite_scores.py` — 29 unit tests with hand-computed
  expectations covering saturation, midpoints, sparse-snapshot,
  negative-D/E guard, and `beta=None` paths (#18).
- `docs/decisions/0002-simplified-composites.md` — ADR documenting
  simplified formulas as the deliberate v0.5.0 design (not a
  placeholder); amends [ADR-0000](docs/decisions/0000-remove-traderfox.md)
  and [ADR-0001](docs/decisions/0001-defer-financetoolkit.md) (#18).
- `FundamentalsSnapshot.beta` — captures yfinance `info["beta"]`;
  required input for the AAQS proxy (#18).
- `FundamentalsSnapshot.composite_scores` — optional nested
  `CompositeScores`; attached post-fetch via `model_copy(update=…)`
  so JSON output schema stays additive (#18).
- `CliArgs.show_scores` (`--show-scores` flag, off by default) —
  appends Quality / Div / Growth columns to the rich summary table.
  Composites are always computed and persisted regardless of the
  flag (#18).

### Changed

- README adds a **Composite proxy scores** section + TOC entry under
  Fundamentals (#18).
- `docs/architecture.md` — composite_scores no longer marked as "not
  yet implemented"; data-flow diagram bumped to v0.5.0; financetoolkit
  reframed as not-used (per ADR-0002) (#18).
- `docs/roadmap.md` — v0.4.0 marked shipped; v0.5.0 framing aligned
  with ADR-0002 simplified composites (#18).
- `docs/UserStory.md` — current milestone updated to v0.5.0 with
  composite scores; corrects stale `results/fear_greed/` path to
  `results/cnn_fg/YYYY.json` (#18).

## [0.4.0] - 2026-05-10

Replaces the Traderfox scraper with a library-based fundamentals +
sentiment stack (yfinance + CNN F&G). See
`docs/decisions/0000-remove-traderfox.md`. Composites deferred to
v0.5.0 per `docs/decisions/0001-defer-financetoolkit.md`.

### Documentation

- README cleanup (#3): drop `[DRAFT]/[WIP]/<0.0.0>` markers, replace
  static version badge with dynamic GitHub-tag badge, fill TOC, add a
  Sentiment section, drop pre-Phase-1 "Other possible packages" + "API"
  sections.
- `src/__version__.py` now reads from package metadata via
  `importlib.metadata.version("analyze-stock-kpi")` — `pyproject.toml` is
  the single source of truth, no more triple-source drift.

### Added

- `src/sentiment.py` — `FearGreedSnapshot(BaseModel)`, `fetch_fear_greed()`,
  `parse_historical()`, and `merge_payload_into_years()` via stdlib
  `urllib.request`. CNN's WAF requires a current desktop-browser UA +
  `Accept` + `Referer: https://edition.cnn.com/` (returns 418 otherwise);
  all three are sent. Each daily entry now also carries a
  `subindicators: dict[str, SubindicatorReading]` map covering CNN's 9
  subindicator blocks (S&P momentum, breadth, VIX, etc.). Today's row
  has the precise 0-100 score per subindicator; historical rows have
  rating + raw value but no per-day score (CNN doesn't ship that). See
  [`docs/cnn-fg-api.md`](docs/cnn-fg-api.md) for the backfillable-vs-
  daily-only breakdown. `python -m src.sentiment` merges the live
  headline + ~1y of historical readings into per-year JSON files at
  `results/cnn_fg/YYYY.json` (sorted by date; today's entry is force-
  overwritten with the live headline so its `previous_*` deltas and
  per-subindicator scores survive intraday CNN updates) (#17).
- `.github/workflows/fear-greed.yaml` — daily cron at 21:30 UTC (~30 min
  after NYSE close, year-round) plus `workflow_dispatch`; commits the
  rewritten year files via `stefanzweifel/git-auto-commit-action@v5`,
  scoped to `results/cnn_fg/[0-9][0-9][0-9][0-9].json` (#17).
- `src/fundamentals.py` — `FundamentalsSnapshot(BaseModel)` plus
  `fetch_fundamentals` / `fetch_price_history` /
  `fetch_universe_fundamentals`. yfinance-backed, ~30 aliased fields,
  sparse snapshots for non-equities (FX/futures/crypto) valid by design
  (#28, closes #16, supersedes #7).
- `src/__main__.py` wires fundamentals end-to-end: fetch every resolved
  ticker, print a rich summary table (equities + ETFs), persist all
  snapshots to `results/fundamentals_<UTC>.json` (#28).
- `src/universe.py` — universe resolver with presets in
  `src/assets/universes/`, CSV/file/inline ticker sources, dedup with
  order preservation (#26, closes #20).
- `src/utils/parse_args.py` — `CliArgs(BaseSettings)` typed CLI args + env
  vars (env prefix `SSK_`, kebab-case CLI flags, `extra="forbid"`); adds
  `period` field reserved for the v0.5.0 composites PR (#26, #28).
- Governance scaffold: `docs/architecture.md`, `docs/UserStory.md`,
  `docs/roadmap.md`, `docs/decisions/0000-remove-traderfox.md` (#24);
  `docs/decisions/0001-defer-financetoolkit.md` documents the v0.4.0
  yfinance-only scope amendment.
- Complexity gates: `complexipy` cognitive ≤15 + `ruff` mccabe ≤10, both
  wired into `make validate` and CI (#24).
- Mandatory markdown + link checks: `lint_md` (in `make validate` and CI),
  `lint_links` (CI workflow `links-fail-fast.yml` runs on push/PR/weekly).
  Adopts the qte77 Agents-eval convention; `.lychee.toml` cribbed from
  sibling `llm-local-text` (#27, #28).
- Dependencies: `pydantic>=2.10`, `pydantic-settings>=2.6` (#26),
  `yfinance>=0.2.40` (#28).

### Changed

- **Renamed top-level package `app/` → `src/`.** All imports become
  `from src.X import ...`; `make run` invokes `python -m src`; the
  daily cron invokes `python -m src.sentiment`; pyright/complexipy/
  coverage targets and pyproject build config all updated accordingly.
  Mechanical: no behavior changes.
- `make run` no longer scrapes via Playwright; runs fundamentals via
  yfinance and writes `results/fundamentals_<UTC>.json` plus a rich
  summary table (#28). A CNN Fear & Greed banner now precedes the table;
  fetch failure logs a warning and continues (#17).
- `results/` is no longer gitignored — cron-committed F&G snapshots live
  under `results/cnn_fg/`. The cron's `file_pattern` is scoped narrowly
  so locally-produced fundamentals files are never accidentally swept
  into a CI commit (#17).
- Default `pytest` excludes `@pytest.mark.network` tests via
  `-m 'not network'` in addopts. Opt in with `pytest -m network`
  (#28).
- `markdownlint` style: ATX headings via `.markdownlint.json` matching
  the qte77 ecosystem convention from sibling `llm-local-text` (#27).
- Python 3.9 → 3.12 (`requires-python = ">=3.12,<3.13"`).

### Removed

- Traderfox provider end-to-end: `app/utils/handle_playwright.py`,
  `app/config/dom.json`, the Playwright dependency, traderfox dispatch
  in `__main__.py` (#25, closes #19).
- Dead config layer left over from the Traderfox era:
  `app/utils/handle_config.py`, `app/utils/handle_files.py`,
  `app/config/defaults.json`, the now-empty `app/config/` directory
  (#28).
- `Pipfile`, `.flake8`, `.cirrus.yml`, `.bumpversion.cfg`, `make.bat`
  — superseded by uv / ruff / GitHub Actions / no-release-yet (YAGNI).

### Fixed

- Runtime orphan `title=` kwarg on Playwright page calls and missing
  `mkdir -p results/` before write (#15).
- File I/O utilities no longer return `Exception` objects from
  `except` blocks; errors propagate naturally so callers see the real
  failure (later removed entirely in #28).
- Latent argument-order bug in `get_values_single_url`: `_get_result`
  was called with `headless` and `timeout` swapped (later removed via
  the Traderfox decommission in #25).
- 22 pre-existing pyright errors cleared; pyright gates `make validate`
  and CI.

### Earlier

Pre-Phase-1 setup work — kept here for traceability.

- Tooling adoption per qte77 ecosystem conventions: `uv` (replaces
  Pipfile), `ruff` (replaces black + flake8 + isort + pyupgrade),
  `pyright` (replaces mypy), `Makefile` with `validate` target,
  `AGENTS.md` + `CLAUDE.md` agent docs, `.claude/settings.json` with
  marketplace plugins, GitHub Actions `validate.yaml` workflow.
- `[tool.uv].exclude-newer` pinned for reproducible dependency
  resolution.
- `MEMORY.md` and bwrap sandbox phantom block in `.gitignore`;
  `.gitmessage` conventional-commit template tracked.
- `tests/` scaffold with smoke test; pytest + coverage config.
