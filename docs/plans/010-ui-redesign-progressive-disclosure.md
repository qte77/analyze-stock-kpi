# 010 — UI redesign: positioning + progressive disclosure

Issues [#426](https://github.com/qte77/analyze-stock-kpi/issues/426) (absorbed as slice 5) · owner
feedback 2026-09-25 ("overwhelming and convoluted"), redesign approved by the owner 2026-09-25. Takes
over the redesign row of [plan 009](009-backtest-carry-over.md).

## Status and handoff (read first)

- **Shipped:** nothing yet. This plan, the UX review (2026-09-25) and the source map below.
- **Next, in order:** the remaining-work table, top to bottom. Slice 0 (the e2e script) comes first
  because every later slice uses it as its done-when.
- **Loop:** a new branch per slice → RED test where a pure `ui/lib/*` module changes (rendering and
  wiring are covered by the e2e) → `make validate` → the e2e on phone and desktop against
  `make preview` → changelog fragment → strike the row here → PR → admin squash-merge on green →
  delete the branches. After a merge, run the same e2e against the Pages deploy.
- **Owner gates:** none. The defaults below apply unless the owner overrides them.
- **Watch-outs:**
  - Layout and emphasis only. The data, the URL parameters (`ui/lib/state.js`) and the EyeRest
    zero-blue theme stay as they are. Every existing deep link must keep working (default D1).
  - Series A and B are **never spliced**, including in any headline (default D5).
  - `make preview` serves `http://localhost:8000/analyze-stock-kpi/` (Vite). In a Patchright
    `page.evaluate`, pass `isolated_context=False` to see page globals such as `Chart`.
  - The year-file 404s in the console (probes before a series' start) are expected; the e2e
    must ignore those and fail on any other console error.

## Context

The page stacks three products at equal weight: market sentiment, a research backtest and a stock
screener. The UX review (2026-09-25, desktop 1440×900 and phone 390×844 on the live site) found:

1. The Fear & Greed score is the visual hero (`#fg-score` at 3rem, `ui/style.css:162-166`) and the
   first block on both viewports, not the ranking.
2. The default universe is the personal watchlist (`ui/app.js:60`,
   `let activeUniverse = "qte77-watchlist"`), not the cross-universe ranking.
3. `#backtest-section` (`ui/index.html:147-279`) renders fully expanded: chart, 12-column metrics
   table, key facts, caveats and a ~200-word disclaimer, then series B repeats the pattern.
4. The metrics table shows "– %" placeholders. Confirmed 2026-09-25: by design, not timing. Every
   metric is `null` below 12 months of returns (`_MIN_MONTHS_FOR_METRICS`), and series A
   started 2026-05-31, so its table stays empty until about June 2027 (#446).
5. A row click does nothing in the default Simple view: `#row-detail` is `.detail-only`, and
   `body.view-simple .detail-only { display: none !important }` (`ui/style.css:658`), while
   `viewMode = "simple"` is the default (`ui/app.js:75`). This is #426.
6. The row-detail panel is 24 flat `<dt>/<dd>` rows (`ui/detail_panel.js:163-214`).
7. The `<h1>` has no positioning line (`ui/index.html:34-38`).
8. The ARIA tabs (`#fg-tabs`; the panel's Overview/Time-series tabs) handle `click` only, with no
   arrow-key navigation (`ui/charts.js:610-622`, `ui/detail_panel.js:107-139`).
9. The header already wraps onto several lines on a 390 px phone.

## Approach

Make the ranking the product and reveal everything else in three layers.

**Positioning line** (verify the ticker count against `ui/public/universes.json` when it ships):
"qte77 ranks ~320 stocks by one quality score, shows today's best and worst 25, and tracks how
that ranking would have performed."

Layer 1, what everyone sees (the list and chart values are illustrative):

```text
+--------------------------------------------------------------------------+
| qte77 · stock quality ranking               [Fear 32 v]  [theme]  [?]    |
| <positioning line>                                                       |
+--------------------------------------------------------------------------+
|  TODAY'S PICKS (date)                        [search ticker ______ ]     |
|  +------------------------------+  +------------------------------+      |
|  | BEST 25          qte77 Score |  | WORST 25         qte77 Score |      |
|  | ticker  name              86 |  | ticker  name              11 |      |
|  | ... [show all 25 v]          |  | ... [show all 25 v]          |      |
|  +------------------------------+  +------------------------------+      |
|  DOES IT WORK?                                                           |
|  +--------------------------------------------------------------------+  |
|  |  one chart: series A's headline line (100-based)                   |  |
|  +--------------------------------------------------------------------+  |
|  "Long best 25 / short worst 25, live decisions since 2026-05-31:        |
|   <net return>. Too short to be significant. Hypothetical, not advice."  |
|  [How it's tested >]  [Longer approximate history since 2023 >]          |
|  [Browse all stocks >]                                                   |
+--------------------------------------------------------------------------+
| Methodology · Data sources · GitHub · Report an issue                    |
+--------------------------------------------------------------------------+
```

Layer 2, one click away:

- **Fear & Greed chip** → the score, deltas, and the 30d / long-term / 5s10s tabs.
- **How it's tested** → series A's metrics table (gross/net), other cadences on demand, the
  rebalance log and caveats; series B in its own labelled block, never on A's axis.
- **Browse all stocks** → the universe table in Simple view, with picker, date, filter, CSV and the
  sector donut. A row click opens the side panel in Simple view too (#426).

Layer 3, reference: a Methodology section holding "What the qte77 Score measures", "Why these
universes", "Why these charts", the backtest rules, the look-ahead audit, all caveats and ADR
links.

| Current element | New home |
|---|---|
| F&G section (3 tabs, big charts) | header chip + panel (layer 2) |
| "Why these charts?" / "Why these universes?" | Methodology (layer 3) |
| Series A blocks, tables, key facts | one chart + one line (layer 1), details in "How it's tested" |
| Series B, rebalance log, caveats | "How it's tested", collapsed, B in its own block |
| "Current candidates" + "Latest best/worst 25" | merged into Today's picks (layer 1) |
| Universe table, picker, donut, CSV | "Browse all stocks" (layer 2); quick search stays in layer 1 |

### Defaults (decide-by-default; the owner can override any)

- **D1 — deep links open their section.** A non-default URL parameter opens the section it
  belongs to: `filter`/`sort`/`sortDir`/`sector`/`date`/`view`/`universe` → "Browse all stocks";
  `ltFgWindow`/`ycWindow` → the F&G panel on its long-term tab. Reuse `state.js`'s existing
  default-detection (`setOrDelete`, `ui/lib/state.js:105-111`).
- **D2 — quick search in layer 1.** One search box next to Today's picks, reusing the Fuse.js
  filter (`#universe-filter`). Submitting opens "Browse all stocks" pre-filtered.
- **D3 — phone order.** Below 640 px, BEST stacks above WORST.
- **D4 — F&G chip on phone.** It opens a full-width panel that pushes content down (not a popover).
  Below ~480 px the chip moves out of the header row into the Today's picks area.
- **D5 — the headline is series A only.** Series B appears only in "How it's tested", behind its own
  clearly labelled link, never spliced into A's number or axis.
- **D6 — native disclosure.** Every layer-2/3 reveal is a `<details>/<summary>` (already used at
  `#backtest-a-lists`, `#universe-help`). No new custom JS toggles.
- **D7 — the row-detail panel gets 4 groups** (Profitability / Valuation / Risk / Momentum, the
  buckets the Score tooltip already names at `ui/index.html:363`) and shows in Simple view.
- **D8 — default universe.** First load with no `?universe=` shows Today's picks from
  `aggregated-scores-best`/`-worst`. "Browse all stocks" keeps `qte77-watchlist` as its default
  picker value. An explicit `?universe=` is unchanged.

## Source map

All paths under `ui/`. The page is built in `init()` (`app.js:682-788`).

| Section | `index.html` | Filled by | CSS (`style.css`) |
|---|---|---|---|
| Header (h1, `#theme-toggle`, `#report-issue`, `#updated`) | 34-63 | `theme.js:8-56`; `#updated` in `loadActiveUniverse` `app.js:491` | — |
| F&G `#fear-greed-section` (header 67-73, tabs 74-101, rolling 102-105, long-term 106-129, `#why-wrap` 130-144) | 66-145 | `charts.js`: `renderFearGreedHeader` 419, `renderFearGreedChart` 461, `renderCombinedLongTerm` 513, `bindLongTermTabs` 592, `bindWindowChips` 650, `renderYieldCurveHeader` 682; loaders `app.js:148-156` | `#fg-header` 154, `#fg-score` 162, `.chip` 175-190, `#why-wrap` 204, `.chart-canvas` 229, `.why-list` 238-258, `#yc-header` 260-275, `.detail-tabs` 912-935, `.window-chips` 953-977 |
| Backtest `#backtest-section` (A 148-211: lists `<details>` 187-190, trades 191-194, caveats 195, disclaimer 196-211; B `<details>` 213-278) | 147-279 | `charts.js`: `renderBacktestChart` 752, metrics table 848, key facts 880, `renderBacktestCaveats` 891, headline 911, `renderBacktestSummary` 931, `bindBacktestModeToggle` 946, `buildRankList` 969, `renderBacktestLists` 1004, `buildTradeRow` 1071, `renderBacktestTrades` 1099; `app.js`: loaders 195-307, `toRankRows` 216, `loadCurrentAggregatedCandidates` 243, `loadBacktestLists` 269; wiring 764-786 | `#backtest-a-headline` 1027, `#backtest-b-*` 1032-1122, `.key-facts` 1076, `.backtest-trades-table` 1124-1160, `#backtest-b-collapsible` 1162-1182, `.backtest-rank-list` 1195-1216, `.caveats-list` 1224, `.backtest-disclaimer` 1235 |
| Universe `#universe-section` (help `<details>` 284-296, controls 282-345, `#view-toggle` 322-332, chips 336, table 346-368, `#row-detail` 369) | 281-370 | `app.js`: `applyViewMode` 311, `persistStateFromCurrent` 328, `renderTable` 354, `bindTableSort` 368, `bindCsvExport` 404, `loadActiveUniverse` 433, `renderUniverseChips` 495, `bindViewToggle` 529, `populateUniversePicker` 546, `bindUniversePicker` 566, `hydrateUrlState` 579, `bindDateSelector` 597, `bindFilterInput` 615, `applyDateFromUrl` 634; `table.js`: Simple columns `inSimple` 153-168, `renderUniverseTable` 232; `charts.js`: `renderSectorDonut` 72, `toggleSectorFilter` 169, `renderSectorFilterChip` 220; `detail_panel.js`: `showDetail` 83, tabs 107-139, KPI rows 163-216 | `#universe-controls-row` 292-330, `#universe-header` 334, `.chips-row` 355, `#universe-filter` 368/377, `#universe-picker` 384, table 398-485, `#row-detail` 487-550, `#export-csv` 644, `.detail-only` 658, `#sector-donut-wrap` 662, `.universe-chip` 859-907, `#universe-help` 979-1020 |
| Footer | 373-378 | static | — |

- **URL parameters** (`lib/state.js`: parse 61-88, serialize 124-137): `view` 63, `universe` 65
  (comma list; first is primary), `sort`/`sortDir` 69-70, `filter` 71, `date` 72, `sector` 74,
  `ltFgWindow`/`ycWindow` 75-76. `theme` is outside `state.js` (`index.html:13` anti-flash guard,
  `theme.js:19`).
- **View mode:** `body.view-simple` initially (`index.html:33`); resolved URL → localStorage →
  `"simple"` (`state.js:148`, `app.js:690-691`). Simple columns: Ticker, Universe (overlays
  only), Name, Sector, Score; Detailed adds P/E (fwd), PEG, Beta, R&D/Rev %, Op M %, ROE %, ROA %,
  Current, Sortino.
- **Tests:** `make test_js` → vitest unit tests in `ui/tests/*.test.mjs` (pure `ui/lib/*` modules).
  There is no committed e2e yet (slice 0). The manual procedure is in
  [plan 008](008-pit-longshort-backtest.md) (polyfetch + Patchright Chromium from
  `../polyfetch-scrape`).
- **Dev server:** `make preview` (Vite dev, `ui/vite.config.js`, base `/analyze-stock-kpi/`).

## Remaining work (the ONLY list of open items)

| Slice | Gate | Done-when |
|---|---|---|
| 0. Committed e2e script `scripts/e2e_ui.py` (runs with `uv run --project ../polyfetch-scrape`; phone 390×844 touch + desktop 1440×900, portrait and landscape; screenshots; fails on console errors other than the known year-file 404s and on failed requests; `--url` for local or Pages) | agent | passes on today's page locally and on Pages; documented in CONTRIBUTING |
| 1. Positioning line + F&G collapsed into a header chip and panel (D4, D6) | agent | e2e: no F&G score above Today's picks on either viewport; the chip opens and closes with click and Enter/Space; `?ltFgWindow=5y` opens it (D1) |
| 2. Today's picks as the landing view: merged Best/Worst 25 from `aggregated-scores-best`/`-worst`, quick search (D2, D3, D8) | agent | e2e: a first load with no parameters shows Best/Worst 25 first; BEST above WORST on phone; `?universe=`/`?date=` links behave as before |
| 3. Backtest behind "How it's tested"; layer 1 keeps series A's chart and one line (D5); a designed empty state for series A's metrics before 12 months. Do it after the #446 audit, whose findings (SPY benchmark, leg separation, which cadences and metrics stay) define this slice's content | agent | e2e: the metrics table and disclaimer are hidden until expanded; B never shares A's axis or headline; no "– %" wall on first render |
| 4. "Browse all stocks": the universe table, picker, donut and CSV collapsed (D1, D6) | agent | e2e: collapsed by default; `?filter=`/`?sort=`/`?sector=` open it on load |
| 5. #426: row detail works in Simple view, KPI rows in 4 groups, radar labels decided (D7) | agent | e2e: a row click in Simple view opens the panel on both viewports with 4 groups |
| 6. Methodology section (layer 3): "Why these charts?", "Why these universes?", backtest rules, caveats, ADR links | agent | links from layers 1/2 resolve; a text diff shows no content was lost |
| 7. Arrow-key navigation for the ARIA tabs (`#fg-tabs`, the panel tabs) | agent | e2e: ArrowLeft/ArrowRight/Home/End move focus and selection |

## Open questions

None blocking. D1–D8 are the defaults; the owner overrides them in review.

## References

- UX review 2026-09-25 (usability-audit subagent; screenshots were not committed).
- [ADR-0013](../decisions/0013-point-in-time-backtest.md) (series A/B, never spliced),
  [ADR-0014](../decisions/0014-current-candidates-use-live-score.md) (today's candidates come
  from the aggregated lists).
- qte77 brand: EyeRest `DESIGN.md` in `qte77/qte77/brand/`.
