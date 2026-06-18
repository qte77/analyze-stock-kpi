# Plan — Merge long-term charts + SP500 overlay

Issue [#288](https://github.com/qte77/analyze-stock-kpi/issues/288) · status: proposed · depends on [backfill-history](backfill-history.md) (**shipped** — F&G + 5s10s now reach 2011 on the `data` branch, #287 / PR #297).

## Context

The long-term tab group has two separate charts — monthly CNN F&G (`#lt-fg-chart`)
and the 5s10s slope (`#yc-chart`). Merge them into one Chart.js chart and overlay
**S&P 500 price on a log axis** for macro context. With #287 shipped, F&G and 5s10s
both have ~15y of history; S&P 500 price is **entirely absent** and must be added —
it mirrors the `^TNX`/`^FVX` yield-curve data path 1:1 (incl. the new
`scripts/backfill_yield_curve.py` one-off + the data-branch cron pattern).

## Approach

Two halves: (A) a new S&P 500 price series on the `data` branch, (B) one combined
Chart.js chart replacing the two long-term panes.

### A. S&P 500 price data (mirror the yield-curve path exactly)

- `src/analyze_stock_kpi/data_sources/sp500_price.py` — `Sp500Snapshot(date, close)`
  (frozen pydantic), `fetch_sp500_snapshot()` / `fetch_sp500_history(period)` via
  `yf.Ticker("^GSPC").history(...)`, `merge_payload_into_years`, `_write_year`,
  `main()` cron entrypoint — structurally identical to `yield_curve.py`
  (wrap-degrade boundary; per-year `results/sp500/YYYY.json` arrays sorted by `date`).
- `AppSettings.sp500_cache_dir: Path = Path("results/sp500")` in `config.py`.
- `scripts/backfill_sp500.py` — thin wrapper, sibling to `scripts/backfill_yield_curve.py`
  (`fetch_sp500_history(period="max")` → merge → write).
- `.github/workflows/sp500.yaml` — daily cron mirroring `yield-curve.yaml` (same pinned
  action SHAs, `data`-branch verified commit via `scripts/data-branch-commit.cjs`).
- One-off backfill to `data` (floor **2011** to align with F&G/5s10s), via the same
  worktree + `SSK_SP500_CACHE_DIR` local-run pattern used for #287.

### B. Combined chart

- New `renderLongTermCombined(fgEntries, ycEntries, sp500Entries)` in `ui/charts.js`,
  replacing `renderMonthlyFearGreedChart` + `renderYieldCurveChart`.
- `ui/app.js`: add `loadSp500Years = () => loadYearsFromBranch(DATA_BASE_URL, "results/sp500", "date")`
  to the `Promise.all` (line ~605); `loadYearsFromBranch`/`fetch.js` need **no change**.
- `ui/index.html`: collapse the `fg-tab-monthly` + `fg-tab-yield-curve` tabs/panes into one
  `fg-tab-combined` → `#combined-chart-wrap` (one canvas, one shared `.window-chips` row —
  both panes already use `1y/5y/10y/all`, plus the `#yc-header` current-slope readout).
  **Keep** the rolling ~1y F&G tab (`fg-tab-rolling`) and the "Why these charts?" tab
  (update its `<dl>`).
- Reuse `bindWindowChips` + the `bindThemeObserver` MutationObserver path (charts register
  in `liveCharts`; theme flip → `chart.update("none")` re-reads `cssVar` closures).

### Axes (recommended resolution)

- **F&G** → left, 0–100 — reuse `scoreYAxis(cssVar)` unchanged.
- **S&P 500** → right, **logarithmic** — new `logPriceYAxis(cssVar)` helper in
  `ui/lib/chart_axes.js` (`type:"logarithmic", position:"right", grid.drawOnChartArea:false`).
- **5s10s slope** → its **own** right axis — new `slopeYAxis(cssVar)` (unclamped %pts,
  zero-line highlight). **Do not normalize 5s10s onto 0–100** — a ±%pts series squashed
  into 0–100 misleads. Three y-axes is dense on the current 220px panel → give
  `#combined-chart-wrap` more height (~300–320px).

## Steps

1. Add the S&P 500 data source + config + backfill script (A) — TDD the pure model/merge
   (mirror `tests/test_yield_curve.py`); the script is a simple wrapper (no test).
2. Add `sp500.yaml` cron; one-off backfill `results/sp500/` to `data` (floor 2011).
3. Add `logPriceYAxis` + `slopeYAxis` to `ui/lib/chart_axes.js` + unit tests in
   `chart_axes.test.mjs` (pure functions — the project tests these; chart glue stays untested).
4. `renderLongTermCombined` in `charts.js`; retire the two old render fns + their panes;
   add the combined tab/pane in `index.html`; wire `loadSp500Years`.
5. If the combined chart unifies the two window states into one, update `ui/lib/state.js`
   (`parseState`/`serializeState`) + `state.test.mjs` for the single window param.
6. Update the "Why these charts?" `<dl>` + a changelog fragment.

## Open questions (for implementation time)

- 3 y-axes vs a series-toggle (legend click) to cut density on the small panel?
- F&G in the combined view: keep **monthly** aggregation (`aggregateMonthlyFG`) or plot raw
  daily to align point-for-point with slope + SP500? (Recommend: keep monthly for F&G to
  preserve the regime read; slope + SP500 daily.)
- Fold the rolling ~1y F&G tab in too, or keep it standalone? (Recommend: keep standalone —
  different horizon/purpose.)

## References

- [#288](https://github.com/qte77/analyze-stock-kpi/issues/288); depends on
  [backfill-history](backfill-history.md) (**shipped**, #287).
- `ui/charts.js` (`renderMonthlyFearGreedChart` ~491, `renderYieldCurveChart` ~696,
  `bindLongTermTabs` ~555, `bindThemeObserver` ~746); `ui/lib/fetch.js`
  (`loadYearsFromBranch`); `ui/lib/chart_axes.js` (`scoreYAxis`, `themedXAxis`);
  `ui/index.html` (`#fg-tabs`, the long-term panes).
- S&P 500 series mirrors `src/analyze_stock_kpi/data_sources/yield_curve.py` +
  `scripts/backfill_yield_curve.py` + `.github/workflows/yield-curve.yaml`.
