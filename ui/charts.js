// @ts-check
/* global Chart */
// Chart rendering extracted from app.js (#268).
// All app-state is accessed through the injected `ctx` object.

import { logRightAxis, scoreYAxis, themedXAxis } from "./lib/chart_axes.js";
import { buildCombinedSeries } from "./lib/combined.js";
import { COMPOSITE_LABELS } from "./lib/detail_rows.js";
import { fetchJson } from "./lib/fetch.js";
import { fmtNum, fmtPct } from "./lib/format.js";
import {
  CADENCE_LABELS,
  CADENCE_ORDER,
  compound,
  headlineLine,
  keyFacts,
  metricsTableRows,
  rebalanceMarkers,
  sinceLabel,
  spyIndexOn,
  tradeLogRows,
} from "./lib/portfolio.js";
import { aggregateSectors, sectorColor } from "./lib/sector.js";
import { buildTimeSeries } from "./lib/timeseries.js";
import { filterByWindow, findClosestScore } from "./lib/window.js";
import { observeScrollHint } from "./scroll_hint.js";

/**
 * @typedef {{
 *   readonly snapshot: Row[],
 *   readonly activeUniverse: string,
 *   readonly dataBaseUrl: string,
 *   readonly ratingClasses: Record<string, string>,
 *   readonly manifest: {dates: string[], latest: string} | null,
 *   sectorFilter: string | null,
 *   ltFgWindow: import("./lib/state.js").WindowKey,
 *   ycWindow: import("./lib/state.js").WindowKey,
 *   afterSectorToggle(): void,
 *   afterWindowChange(): void,
 * }} ChartContext
 */

/** @type {ChartContext} */
let ctx = /** @type {any} */ (null);

/**
 * Inject the application context. Must be called before any chart function.
 * @param {ChartContext} context
 */
export function initCharts(context) {
  ctx = context;
}

// Shared Chart.js option bases. Every chart is responsive + non-aspect-locked;
// the time-series charts also share the 250ms animation. Spread first in each
// `options` block so per-chart `plugins`/`scales` extend them.
const BASE_CHART_OPTS = { responsive: true, maintainAspectRatio: false };
const BASE_ANIMATED_OPTS = { ...BASE_CHART_OPTS, animation: { duration: 250 } };

/** @type {any} */
let sectorChart = null;
/** @type {any} */
let radarChart = null;

/**
 * Minimum inline width (px) for the sector-donut-wrap before the legend
 * appears. Below this threshold the legend is hidden so sector labels
 * like "Communication Services" don't truncate. See
 * https://github.com/qte77/analyze-stock-kpi/issues/152
 */
const SECTOR_LEGEND_MIN_WIDTH = 380;

/** @type {ResizeObserver | null} */
let sectorLegendRo = null;

export function renderSectorDonut() {
  const canvas = /** @type {HTMLCanvasElement | null} */ (document.getElementById("sector-donut"));
  if (!canvas || typeof Chart === "undefined") return;
  const aggregated = aggregateSectors(ctx.snapshot);
  const labels = [...aggregated.keys()];
  const data = [...aggregated.values()];
  destroyChart(sectorChart);
  sectorChart = null;
  renderDonutEmptyHint(labels.length === 0);
  if (labels.length === 0) {
    renderSectorFilterChip();
    return;
  }
  const backgroundColor = labels.map(sectorColor);
  // Seam color follows --surface so slice borders blend cleanly with the
  // section background in both light and dark themes. Scriptable so it
  // re-resolves on theme flip via bindThemeObserver → chart.update().
  const borderColor = () => cssVar("--surface", "#e2dec8");
  // Pull the active sector's slice outward so the user has visual
  // confirmation of which slice the table is filtered by.
  const offset = labels.map((l) => (l === ctx.sectorFilter ? 12 : 0));
  sectorChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor, borderColor, borderWidth: 1, offset }],
    },
    options: {
      ...BASE_CHART_OPTS,
      plugins: {
        legend: {
          display: false, // updated below after wrap width check
          position: "bottom",
          labels: {
            boxWidth: 12,
            padding: 12,
            font: { size: 11 },
          },
        },
        tooltip: {
          callbacks: {
            label: (/** @type {any} */ ctx) => {
              const total = ctx.dataset.data.reduce(
                (/** @type {number} */ a, /** @type {number} */ b) => a + b,
                0,
              );
              const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : "0";
              return `${ctx.label}: ${ctx.parsed} (${pct}%)`;
            },
          },
        },
      },
      onClick: (/** @type {any} */ _evt, /** @type {any[]} */ elements) => {
        const el = elements?.[0];
        if (!el) return;
        const label = sectorChart?.data?.labels?.[el.index];
        if (typeof label === "string") toggleSectorFilter(label);
      },
    },
  });
  // Determine initial legend display based on the wrap's current width.
  const wrap = document.getElementById("sector-donut-wrap");
  if (wrap && sectorChart) {
    const wrapWidth = wrap.getBoundingClientRect().width;
    sectorChart.options.plugins.legend.display = wrapWidth >= SECTOR_LEGEND_MIN_WIDTH;

    // Disconnect previous observer before creating a new one (the chart
    // was just destroyed + recreated at the top of this function).
    if (sectorLegendRo) sectorLegendRo.disconnect();

    // Watch for resize events on the wrap element. When the width
    // crosses SECTOR_LEGEND_MIN_WIDTH, toggle legend visibility and
    // call chart.update() so the layout recalculates — Chart.js's own
    // onResize with "none" mode stalls the legend reflow (see #152).
    sectorLegendRo = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentBoxSize?.[0]?.inlineSize ?? entry.contentRect.width;
        const shouldShow = w >= SECTOR_LEGEND_MIN_WIDTH;
        if (sectorChart && sectorChart.options.plugins.legend.display !== shouldShow) {
          sectorChart.options.plugins.legend.display = shouldShow;
          sectorChart.update();
        }
      }
    });
    sectorLegendRo.observe(wrap);
  }
  liveCharts.add(sectorChart);
  renderSectorFilterChip();
}

/**
 * Toggle the active sector filter. Clicking the same sector clears it;
 * clicking a new sector replaces it. Re-renders donut + table + chip
 * and persists the change in the URL.
 *
 * @param {string | null} label
 */
function toggleSectorFilter(label) {
  if (!label) return;
  ctx.sectorFilter = ctx.sectorFilter === label ? null : label;
  renderSectorDonut();
  ctx.afterSectorToggle();
}

/** Shared by every chart-section empty hint (sector donut, F&G rolling,
 *  long-term F&G, yield curve, universe-size badge). Per-section, context-
 *  specific strings stay inline at their site (e.g. table-empty's "first
 *  cron run pending"). */
export const EMPTY_HISTORY = "no history yet";

/**
 * Create-or-update a centered hint inside a wrap element, or remove it when
 * hidden. Update-if-existing: when shown and a hint is already present (e.g. the
 * static "loading…" placeholder shipped in #fg-chart-wrap / #yc-chart-wrap),
 * its text is overwritten rather than left stale. Shared by all four chart
 * empty states; `text` defaults to EMPTY_HISTORY — the sector-donut + long-term
 * callers always use it and have no static placeholder, so the overwrite is a
 * no-op for them.
 *
 * @param {string} wrapId
 * @param {string} hintClass
 * @param {boolean} show
 * @param {string} [text]
 */
function toggleHistoryHint(wrapId, hintClass, show, text = EMPTY_HISTORY) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  let hint = wrap.querySelector(`.${hintClass}`);
  if (show) {
    if (!hint) {
      hint = document.createElement("div");
      hint.className = hintClass;
      wrap.append(hint);
    }
    hint.textContent = text;
  } else if (hint) {
    hint.remove();
  }
}

/**
 * Toggle the sector-donut "no data" hint (#sector-donut-wrap). Idempotent.
 * @param {boolean} show
 */
function renderDonutEmptyHint(show) {
  toggleHistoryHint("sector-donut-wrap", "sector-donut-empty", show);
}

function renderSectorFilterChip() {
  const chipEl = document.getElementById("sector-filter-chip");
  if (!chipEl) return;
  chipEl.replaceChildren();
  if (!ctx.sectorFilter) {
    chipEl.hidden = true;
    return;
  }
  chipEl.hidden = false;
  chipEl.className = "universe-chip sector-chip";
  const label = document.createElement("span");
  label.textContent = `Sector: ${ctx.sectorFilter}`;
  const x = document.createElement("button");
  x.type = "button";
  x.textContent = "×";
  x.setAttribute("aria-label", `Clear sector filter (${ctx.sectorFilter})`);
  x.addEventListener("click", () => toggleSectorFilter(ctx.sectorFilter));
  chipEl.append(label, x);
}

export function renderRadar(
  /** @type {HTMLCanvasElement} */ canvas,
  /** @type {CompositeScores} */ scores,
) {
  if (typeof Chart === "undefined") return;
  // #426: the same labels as the panel's "Composite scores" list below.
  const axes = COMPOSITE_LABELS;
  destroyChart(radarChart);
  radarChart = new Chart(canvas, {
    type: "radar",
    data: {
      labels: Object.values(axes),
      datasets: [
        {
          label: "score",
          data: Object.keys(axes).map(
            (a) => /** @type {Record<string, number | null | undefined>} */ (scores)[a] ?? 0,
          ),
          borderColor: () => cssVar("--primary", "#7a6010"),
          backgroundColor: () => `${cssVar("--primary", "#7a6010")}26`,
        },
      ],
    },
    options: {
      ...BASE_CHART_OPTS,
      scales: {
        r: {
          min: 0,
          max: 100,
          // #426: the tick numbers crowded the top axis label on a phone; the
          // exact values are listed under "Composite scores" below the chart.
          ticks: { stepSize: 25, display: false },
          grid: { color: () => cssVar("--border", "#c8c4b0") },
          angleLines: { color: () => cssVar("--border", "#c8c4b0") },
          pointLabels: { color: () => cssVar("--text", "#2c2818") },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
  liveCharts.add(radarChart);
}

/** @type {any} */
let timeSeriesChart = null;

/** @type {Set<any>} */
const liveCharts = new Set();

/**
 * @param {string} token  CSS custom property name (with leading `--`).
 * @param {string} fallback  Hex used if the token is unset.
 * @returns {string}  Resolved hex/rgb string (no alpha).
 */
function cssVar(token, fallback) {
  return getComputedStyle(document.body).getPropertyValue(token).trim() || fallback;
}

/**
 * Tear down a Chart.js instance: deregister from `liveCharts` + destroy.
 * No-ops on null. Callers keep their own `slot = null` and `liveCharts.add`
 * at their current sites — the add timing matters (e.g. the sector-donut
 * ResizeObserver/legend setup must run before its add).
 * @param {any} chart
 */
function destroyChart(chart) {
  if (!chart) return;
  liveCharts.delete(chart);
  chart.destroy();
}

/**
 * Lazy-load the time-series chart for one ticker. Pre-#136 backfill,
 * the dashboard has at most ~5 historic dates per universe so the
 * series is short; a hint chip is rendered when ≤3 points are available
 * to set expectations. Post-#136 the same code consumes a 17-point grid
 * with no migration.
 *
 * @param {HTMLElement} pane
 * @param {Row} row
 */
export async function renderTimeSeriesPane(pane, row) {
  if (!row.symbol) {
    pane.append(emptyHint("no ticker — nothing to plot"));
    return;
  }
  if (!ctx.manifest) {
    pane.append(emptyHint("loading manifest…"));
    return;
  }
  const dates = [...ctx.manifest.dates].sort();
  pane.append(emptyHint(`loading ${dates.length} snapshots…`));
  const results = await Promise.allSettled(
    dates.map((d) => fetchJson(`${ctx.dataBaseUrl}/results/demo/${ctx.activeUniverse}/${d}.json`)),
  );
  /** @type {Array<{date: string, rows: Row[] | null}>} */
  const snapshotsByDate = dates.map((d, i) => ({
    date: d,
    rows: results[i].status === "fulfilled" ? /** @type {Row[]} */ (results[i].value) : null,
  }));
  const series = buildTimeSeries(snapshotsByDate, row.symbol);
  pane.replaceChildren();
  if (series.dates.length < 3) {
    pane.append(
      emptyHint(
        `only ${series.dates.length} historic point(s) — full history populates after backfill (#136)`,
      ),
    );
  }
  const wrap = document.createElement("div");
  wrap.className = "timeseries-wrap";
  const canvas = document.createElement("canvas");
  wrap.append(canvas);
  pane.append(wrap);
  if (typeof Chart === "undefined") return;
  destroyChart(timeSeriesChart);
  timeSeriesChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: series.dates,
      datasets: [
        {
          label: "qte77 Score",
          data: series.score,
          borderColor: () => cssVar("--primary", "#7a6010"),
        },
        {
          label: "Quality",
          data: series.quality,
          borderColor: () => cssVar("--chart-quality", "#587818"),
        },
        {
          label: "Growth",
          data: series.growth,
          borderColor: () => cssVar("--chart-growth", "#787010"),
        },
        {
          label: "Sortino",
          data: series.sortino,
          borderColor: () => cssVar("--chart-sortino", "#983828"),
          yAxisID: "y1",
        },
      ],
    },
    options: {
      ...BASE_CHART_OPTS,
      scales: {
        y: {
          ...scoreYAxis(cssVar),
          title: {
            display: true,
            text: "Composite (0–100)",
            color: () => cssVar("--text", "#2c2818"),
          },
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: () => cssVar("--text", "#2c2818") },
          title: { display: true, text: "Sortino", color: () => cssVar("--text", "#2c2818") },
        },
      },
    },
  });
  liveCharts.add(timeSeriesChart);
}

/**
 * @param {string} text
 * @returns {HTMLDivElement}
 */
function emptyHint(text) {
  const el = document.createElement("div");
  el.className = "timeseries-hint";
  el.textContent = text;
  return el;
}

export function renderFearGreedHeader(
  /** @type {Array<{timestamp: string, score: number, rating?: string}>} */ entries,
) {
  const header = document.getElementById("fg-header");
  const scoreEl = document.getElementById("fg-score");
  const chipEl = /** @type {HTMLElement | null} */ (document.getElementById("fg-rating"));
  const deltasEl = document.getElementById("fg-deltas");
  if (!header || !scoreEl || !chipEl || !deltasEl) return;
  if (!entries.length) {
    header.hidden = true;
    return;
  }
  header.hidden = false;
  const last = entries[entries.length - 1];
  scoreEl.textContent = fmtNum(last.score, 0);
  const rating = (last.rating ?? "").toLowerCase();
  chipEl.textContent = last.rating ?? "—";
  chipEl.className = `chip ${/** @type {Record<string, string>} */ (ctx.ratingClasses)[rating] ?? ""}`;
  const latestMs = new Date(last.timestamp).getTime();
  const deltas = [
    ["yesterday", 1],
    ["last week", 7],
    ["last month", 30],
    ["last year", 365],
  ]
    .map(
      ([label, d]) =>
        `${label} ${fmtNum(findClosestScore(entries, latestMs, /** @type {number} */ (d)), 0)}`,
    )
    .join(" · ");
  deltasEl.textContent = `(${deltas})`;
}

/** @type {any} */
let fearGreedChart = null;
/** @type {any} */
let combinedChart = null;

function renderRollingEmptyHint(/** @type {boolean} */ show) {
  toggleHistoryHint("fg-chart-wrap", "fg-empty", show);
}

export function renderFearGreedChart(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
) {
  const canvasEl = /** @type {HTMLCanvasElement | null} */ (document.getElementById("fg-chart"));
  if (!canvasEl) return;
  destroyChart(fearGreedChart);
  fearGreedChart = null;
  // Strict trailing 12-month window — the loader concatenates this-year +
  // last-year files, so trim from the latest entry's date.
  const windowed = filterByWindow(entries, "1y", "timestamp");
  renderRollingEmptyHint(windowed.length === 0);
  if (!windowed.length || typeof Chart === "undefined") return;
  fearGreedChart = new Chart(canvasEl, {
    type: "line",
    data: {
      labels: windowed.map((e) => e.timestamp.slice(0, 10)),
      datasets: [
        {
          data: windowed.map((e) => e.score),
          borderColor: () => cssVar("--text", "#2c2818"),
          backgroundColor: () => `${cssVar("--text", "#2c2818")}14`,
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.15,
        },
      ],
    },
    options: {
      ...BASE_ANIMATED_OPTS,
      plugins: { legend: { display: false } },
      scales: { y: scoreYAxis(cssVar), x: themedXAxis(cssVar) },
    },
  });
  liveCharts.add(fearGreedChart);
}

function renderCombinedEmptyHint(/** @type {boolean} */ show) {
  toggleHistoryHint("lt-combined-wrap", "lt-combined-empty", show);
}

/**
 * Render the merged long-term-context chart (#288): CNN F&G monthly median and
 * the 5s10s monthly mean (normalized to 0-100) share the left score axis, while
 * SPY's indexed return sits on a logarithmic right axis. All three are
 * reconciled onto one monthly grid by buildCombinedSeries; renderActiveCombined
 * trims the window upstream.
 *
 * @param {Array<{timestamp: string, score: number}>} fgEntries
 * @param {Array<{date: string, slope_5s10s: number | null}>} ycEntries
 * @param {Array<{date: string, ret_indexed: number}>} spyEntries
 */
function renderCombinedLongTerm(fgEntries, ycEntries, spyEntries) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("lt-combined-chart")
  );
  if (!canvas) return;
  destroyChart(combinedChart);
  combinedChart = null;
  const series = buildCombinedSeries(fgEntries, ycEntries, spyEntries, { slopeLo: -2, slopeHi: 3 });
  renderCombinedEmptyHint(series.labels.length === 0);
  if (series.labels.length === 0 || typeof Chart === "undefined") return;
  combinedChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: series.labels,
      datasets: [
        {
          label: "CNN F&G (median)",
          data: series.fgMedian,
          yAxisID: "y",
          borderColor: () => cssVar("--text", "#2c2818"),
          backgroundColor: () => `${cssVar("--text", "#2c2818")}14`,
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.2,
          spanGaps: true,
        },
        {
          label: "5s10s slope (norm.)",
          data: series.slopeNorm,
          yAxisID: "y",
          borderColor: () => cssVar("--primary", "#7a6010"),
          backgroundColor: () => `${cssVar("--primary", "#7a6010")}14`,
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.2,
          borderDash: [4, 3],
          spanGaps: true,
        },
        {
          label: "SPY (indexed)",
          data: series.spyIndexed,
          yAxisID: "spy",
          borderColor: () => cssVar("--text-muted", "#686040"),
          backgroundColor: () => `${cssVar("--text-muted", "#686040")}14`,
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.2,
          spanGaps: true,
        },
      ],
    },
    options: {
      ...BASE_ANIMATED_OPTS,
      plugins: { legend: { display: true, position: "bottom" } },
      scales: { y: scoreYAxis(cssVar), spy: logRightAxis(cssVar), x: themedXAxis(cssVar) },
    },
  });
  liveCharts.add(combinedChart);
}

/**
 * Wires the Long-term-context tab group:
 *   - Rolling history (F&G live + ~1y)
 *   - Long-term context (merged: F&G monthly + normalized 5s10s + SPY indexed)
 *
 * The merged chart is lazily constructed on first click — matches the
 * detail-panel time-series lazy pattern so initial paint stays cheap. The raw
 * entry arrays are captured at module level (`rawFgEntries` / `rawYcEntries` /
 * `rawSpyEntries`) so the window-chip handler can re-filter and re-render
 * without re-fetching.
 *
 * @param {Array<{timestamp: string, score: number}>} fgEntries
 * @param {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} ycEntries
 * @param {Array<{date: string, ret_indexed: number}>} spyEntries
 */
export function bindLongTermTabs(fgEntries, ycEntries, spyEntries) {
  rawFgEntries = fgEntries;
  rawYcEntries = ycEntries;
  rawSpyEntries = spyEntries;
  /** @type {Array<[string, string]>} */
  const tabs = [
    ["fg-tab-rolling", "fg-chart-wrap"],
    ["fg-tab-longterm", "lt-combined-wrap"],
  ];
  /** @type {Array<[HTMLElement, HTMLElement]>} */
  const resolved = [];
  for (const [tabId, paneId] of tabs) {
    const t = document.getElementById(tabId);
    const p = document.getElementById(paneId);
    if (!t || !p) return;
    resolved.push([t, p]);
  }
  for (const [tab, pane] of resolved) {
    tab.addEventListener("click", () => {
      for (const [t, p] of resolved) {
        const selected = t === tab;
        t.setAttribute("aria-selected", selected ? "true" : "false");
        t.tabIndex = selected ? 0 : -1; // roving tabindex (plan 010 slice 7)
        p.hidden = !selected;
      }
      if (pane.id === "lt-combined-wrap" && !combinedRendered) {
        renderActiveCombined();
        combinedRendered = true;
      }
    });
  }
}

/** Raw chart entries cached at module scope by `bindLongTermTabs` so chip
 *  handlers can re-render with a different window without re-fetching.
 *  @type {Array<{timestamp: string, score: number}>} */
let rawFgEntries = [];
/** @type {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} */
let rawYcEntries = [];
/** @type {Array<{date: string, ret_indexed: number}>} */
let rawSpyEntries = [];
let combinedRendered = false;

function renderActiveCombined() {
  const w = ctx.ltFgWindow;
  renderCombinedLongTerm(
    filterByWindow(rawFgEntries, w, "timestamp"),
    filterByWindow(rawYcEntries, w, "date"),
    filterByWindow(rawSpyEntries, w, "date"),
  );
}

/**
 * Wire the `.window-chips` chip rows above the long-term F&G + yield-curve
 * charts. Click toggles `aria-pressed`, updates the active window var,
 * re-renders the chart if its pane is currently visible (otherwise the
 * next tab activation picks up the new window), and persists state via URL.
 */
export function bindWindowChips() {
  const wrap = document.getElementById("lt-combined-wrap");
  const row = wrap?.querySelector(".window-chips");
  if (!wrap || !row) return;
  syncChipAriaPressed(row, ctx.ltFgWindow);
  row.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const next = /** @type {import("./lib/state.js").WindowKey} */ (target.dataset.window);
    if (!next) return;
    ctx.ltFgWindow = next;
    if (wrap.hidden) combinedRendered = false;
    else renderActiveCombined();
    syncChipAriaPressed(row, next);
    ctx.afterWindowChange();
  });
}

function syncChipAriaPressed(
  /** @type {Element} */ row,
  /** @type {import("./lib/state.js").WindowKey} */ active,
) {
  for (const btn of row.querySelectorAll("button[data-window]")) {
    btn.setAttribute("aria-pressed", btn.getAttribute("data-window") === active ? "true" : "false");
  }
}

/**
 * Surface today's slope + raw legs above the chart so the chart's role
 * stays "trajectory" while the header carries the current-day reading.
 * @param {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} entries
 */
export function renderYieldCurveHeader(entries) {
  const header = document.getElementById("yc-header");
  const slope = document.getElementById("yc-current-slope");
  const legs = document.getElementById("yc-current-legs");
  if (!header || !slope || !legs) return;
  const latest = entries.length ? entries[entries.length - 1] : null;
  if (!latest || latest.slope_5s10s == null) {
    header.hidden = true;
    return;
  }
  header.hidden = false;
  const bps = (latest.slope_5s10s * 100).toFixed(0);
  slope.textContent = `${latest.slope_5s10s >= 0 ? "+" : ""}${bps} bps`;
  const tnx = latest.tnx_yield != null ? `${latest.tnx_yield.toFixed(2)} %` : "—";
  const fvx = latest.fvx_yield != null ? `${latest.fvx_yield.toFixed(2)} %` : "—";
  legs.textContent = `10y ${tnx} − 5y ${fvx} · ${latest.date}`;
}

/**
 * Two series, never spliced (D15): Series A ("a", genuine decisions, the
 * section headline) and Series B ("b", the reconstructed backfill, a
 * collapsible below it) share this contract shape and DOM structure, so
 * every render function below is parameterized by `kind` — DOM ids are
 * derived as `backtest-${kind}-*` — rather than duplicated per series. Each
 * series keeps its own Chart.js instance, summary cache, and gross/net mode,
 * keyed by `kind`; the two are never drawn on one axis.
 * @typedef {"a" | "b"} BacktestKind
 */

/** @type {Record<BacktestKind, any>} */
const backtestChart = { a: null, b: null };

const BACKTEST_EMPTY = "Backtest runs Saturdays";

/** @param {BacktestKind} kind */
function renderBacktestChartEmptyHint(kind, /** @type {boolean} */ show) {
  toggleHistoryHint(`backtest-${kind}-chart-wrap`, "backtest-chart-empty", show, BACKTEST_EMPTY);
}

/** Thin "foil" cadence line colors (everything but the primary, which uses
 *  --primary for both its net/gross lines) — the zero-blue EyeRest data arc.
 *  Five entries for D7's five non-primary cadences (D20 added `yearly`). */
const FOIL_COLORS = [
  "--data-alt",
  "--data-caution",
  "--data-negative",
  "--text-muted",
  "--data-positive",
];

/**
 * Render one series' backtested long/short 25/25 index chart (ADR-0013,
 * D15): the primary cadence's net index (bold) + gross index (dashed), plus
 * the other four cadences' net index as thin foil lines — all 100-based,
 * compounded client-side via `compound()` (D5/D8 — no stored NAV). A 404
 * before the first cron run for this series (every cadence's rows empty)
 * shows the empty hint and never throws — the caller passes `{}`/`[]` for a
 * failed/missing fetch; this is the same path whether the series has simply
 * never run yet or is a series whose paths don't exist at all (e.g. Series A
 * before PR E ships) — no special-casing. `tradeDates` (D21, the primary
 * cadence's rebalance log trade dates) draws a marker point on each
 * rebalance day, aligned to the chart's own label axis rather than the
 * primary series' own dates — a foil cadence can have a longer history, in
 * which case the x-axis (`labels`) is longer than `primaryNet.dates`.
 *
 * `spyEntries` (plan 010 slice 3, #446) adds SPY's total return rebased to 100
 * on the chart's first date as a thin reference line (`spyIndexOn`); it is a
 * long-only index, not a benchmark the market-neutral book is expected to track.
 *
 * @param {BacktestKind} kind
 * @param {Record<string, import("./lib/portfolio.js").BacktestReturnRow[]>} seriesByCadence
 * @param {string | null | undefined} primary
 * @param {string[]} [tradeDates]
 * @param {Array<{date: string, ret_indexed: number}>} [spyEntries]
 */
export function renderBacktestChart(
  kind,
  seriesByCadence,
  primary,
  tradeDates = [],
  spyEntries = [],
) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById(`backtest-${kind}-chart`)
  );
  if (!canvas) return;
  destroyChart(backtestChart[kind]);
  backtestChart[kind] = null;
  const primaryLabel = (primary && CADENCE_LABELS[primary]) || "Primary";
  const primaryRows = (primary && seriesByCadence[primary]) || [];
  const primaryNet = compound(primaryRows, "ret_ls_net");
  const primaryGross = compound(primaryRows, "ret_ls_gross");
  const foils = CADENCE_ORDER.filter((key) => key !== primary).map((key, i) => ({
    key,
    label: CADENCE_LABELS[key] ?? key,
    color: FOIL_COLORS[i % FOIL_COLORS.length],
    ...compound(seriesByCadence[key] ?? [], "ret_ls_net"),
  }));
  const hasData = primaryNet.dates.length > 0 || foils.some((f) => f.dates.length > 0);
  renderBacktestChartEmptyHint(kind, !hasData);
  if (!hasData || typeof Chart === "undefined") return;
  const labels = [primaryNet, ...foils].reduce(
    (longest, series) => (series.dates.length > longest.length ? series.dates : longest),
    /** @type {string[]} */ ([]),
  );
  const primaryNetByDate = new Map(primaryNet.dates.map((d, i) => [d, primaryNet.index[i]]));
  const markers = rebalanceMarkers(
    labels,
    labels.map((d) => primaryNetByDate.get(d) ?? null),
    tradeDates,
  );
  backtestChart[kind] = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: `${primaryLabel} (net)`,
          data: primaryNet.index,
          borderColor: () => cssVar("--primary", "#7a6010"),
          backgroundColor: () => `${cssVar("--primary", "#7a6010")}14`,
          fill: false,
          pointRadius: 0,
          borderWidth: 2.5,
          tension: 0.1,
        },
        {
          label: `${primaryLabel} (gross)`,
          data: primaryGross.index,
          borderColor: () => cssVar("--primary", "#7a6010"),
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
          borderDash: [4, 3],
          tension: 0.1,
        },
        ...foils.map((f) => ({
          label: `${f.label} (net)`,
          data: f.index,
          borderColor: () => cssVar(f.color, "#686040"),
          fill: false,
          pointRadius: 0,
          borderWidth: 1,
          tension: 0.1,
        })),
        ...(spyEntries.length > 0
          ? [
              {
                label: "SPY (total return)",
                data: spyIndexOn(labels, spyEntries),
                borderColor: () => cssVar("--text", "#2c2818"),
                fill: false,
                pointRadius: 0,
                borderWidth: 1,
                borderDash: [2, 3],
                tension: 0.1,
                spanGaps: true,
              },
            ]
          : []),
        {
          // D21: rebalance-day markers for the primary cadence — a sparse
          // point-only dataset (no connecting line), drawn on top.
          label: "Rebalance",
          data: markers,
          showLine: false,
          pointStyle: "triangle",
          pointRadius: 5,
          pointBackgroundColor: () => cssVar("--data-caution", "#787010"),
          pointBorderColor: () => cssVar("--data-caution", "#787010"),
          order: 0,
        },
      ],
    },
    options: {
      ...BASE_ANIMATED_OPTS,
      plugins: { legend: { display: true, position: "bottom" } },
      scales: {
        y: { ticks: { color: () => cssVar("--text", "#2c2818") } },
        x: themedXAxis(cssVar),
      },
    },
  });
  liveCharts.add(backtestChart[kind]);
}

/** @type {Record<BacktestKind, import("./lib/portfolio.js").BacktestSummary | null>} */
const backtestSummaryCache = { a: null, b: null };
/** @type {Record<BacktestKind, "gross" | "net">} */
const backtestMode = { a: "net", b: "net" };

/** @typedef {ReturnType<typeof metricsTableRows>[number]} MetricsRow */
/** @typedef {[string, (row: MetricsRow) => string]} MetricsColumn */

/** @type {(v: number | null | undefined) => string} */
const pctCell = (v) => `${fmtPct(v)} %`;

/** Plan 010 slice 3 (#446): the metrics a reader needs to judge the book. */
/** @type {MetricsColumn[]} */
const HEADLINE_METRICS = [
  ["Ann. return", (r) => pctCell(r.ann_return)],
  ["Ann. vol", (r) => pctCell(r.ann_vol)],
  ["Max drawdown", (r) => pctCell(r.max_drawdown)],
  ["Beta (SPY)", (r) => fmtNum(r.beta, 2)],
  [
    "Mean monthly (90% CI)",
    (r) => `${fmtPct(r.mean_monthly_return)} % [${fmtPct(r.ci90?.[0])}, ${fmtPct(r.ci90?.[1])}]`,
  ],
  ["Rebalances", (r) => (r.rebalances != null ? String(r.rebalances) : "—")],
];

/** ...and the rest, behind "More metrics". */
/** @type {MetricsColumn[]} */
const DETAIL_METRICS = [
  ["Ann. turnover", (r) => pctCell(r.ann_turnover)],
  ["Long leg", (r) => pctCell(r.long_ann_return)],
  ["Short leg", (r) => pctCell(r.short_ann_return)],
  ["Hit rate", (r) => pctCell(r.hit_rate)],
  ["t-stat", (r) => fmtNum(r.t_stat, 2)],
];

/**
 * Fill one metrics table: a header from `columns`, one row per cadence, or a
 * single explanatory row when no cadence has annualized metrics yet (D9: fewer
 * than 12 months of returns) instead of a grid of dashes.
 *
 * @param {HTMLTableElement} table
 * @param {MetricsColumn[]} columns
 * @param {MetricsRow[]} rows
 * @param {string | null | undefined} start
 */
function fillMetricsTable(table, columns, rows, start) {
  const head = document.createElement("tr");
  for (const [i, title] of ["Cadence", ...columns.map(([t]) => t)].entries()) {
    const th = document.createElement("th");
    if (i > 0) th.className = "num";
    th.textContent = title;
    head.append(th);
  }
  const thead = document.createElement("thead");
  thead.append(head);
  const tbody = document.createElement("tbody");
  const pending = rows.length > 0 && rows.every((r) => r.ann_return == null);
  if (pending) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length + 1;
    td.className = "backtest-metrics-pending";
    td.textContent =
      `Annualized metrics need 12 months of returns${start ? ` (started ${start})` : ""}; ` +
      "until then the chart and the line above show the return so far.";
    tr.append(td);
    tbody.append(tr);
  } else {
    for (const row of rows) {
      const tr = document.createElement("tr");
      if (row.primary) tr.className = "backtest-primary-row";
      for (const [i, text] of [row.label, ...columns.map(([, cell]) => cell(row))].entries()) {
        const td = document.createElement("td");
        if (i > 0) td.className = "num";
        td.textContent = text;
        tr.append(td);
      }
      tbody.append(tr);
    }
  }
  table.replaceChildren(thead, tbody);
}

/** @param {BacktestKind} kind */
function renderBacktestMetricsTable(kind) {
  const summary = backtestSummaryCache[kind];
  const rows = metricsTableRows(summary, backtestMode[kind]);
  for (const [suffix, columns] of /** @type {Array<[string, MetricsColumn[]]>} */ ([
    ["metrics-table", HEADLINE_METRICS],
    ["metrics-detail-table", DETAIL_METRICS],
  ])) {
    const table = document.getElementById(`backtest-${kind}-${suffix}`);
    if (table instanceof HTMLTableElement) fillMetricsTable(table, columns, rows, summary?.start);
  }
}

/** @param {BacktestKind} kind */
function renderBacktestKeyFacts(kind) {
  const el = document.getElementById(`backtest-${kind}-key-facts`);
  if (!el) return;
  const facts = keyFacts(backtestSummaryCache[kind]);
  el.textContent = facts.start
    ? `Start ${facts.start} · Realized beta to SPY ${fmtNum(facts.beta, 2)} · ` +
      `Null percentile ${fmtNum(facts.nullPercentile, 0)}th · Fidelity median ρ ${fmtNum(facts.fidelityRho, 2)}`
    : "";
}

/** @param {BacktestKind} kind */
function renderBacktestCaveats(kind) {
  const el = document.getElementById(`backtest-${kind}-caveats`);
  if (!el) return;
  el.replaceChildren();
  for (const caveat of backtestSummaryCache[kind]?.caveats ?? []) {
    const li = document.createElement("li");
    li.textContent = caveat;
    el.append(li);
  }
}

const BACKTEST_HEADLINE_BASE = { a: "Genuine decisions", b: "Reconstructed backfill" };

/**
 * Update Series A's section `<h2>` / Series B's collapsible `<summary>`
 * label with its start date once known (D16/D18), via `sinceLabel` — never a
 * dangling "since null" before the first successful summary load.
 * @param {BacktestKind} kind
 * @param {import("./lib/portfolio.js").BacktestSummary | null} summary
 */
function renderBacktestHeadline(kind, summary) {
  const el = document.getElementById(
    kind === "a" ? "backtest-a-headline" : "backtest-b-summary-label",
  );
  if (!el) return;
  const label = sinceLabel(BACKTEST_HEADLINE_BASE[kind], summary?.start);
  el.textContent = kind === "b" ? `${label} (approximation)` : label;
}

/**
 * Render one series' backtest summary block: the section headline/label
 * (with its start date once known), the metrics table (D9, one gross/net
 * mode at a time — default net), the key-facts line, and the caveats
 * (rendered verbatim from `summary.caveats`). A missing/404 `summary`
 * (before this series' first cron run) renders an empty table + blank
 * key-facts line and never throws.
 *
 * Also fills the one-sentence summary under the chart (`headlineLine`, plan
 * 010 slice 3) from `primaryRows`, the primary cadence's daily rows.
 *
 * @param {BacktestKind} kind
 * @param {import("./lib/portfolio.js").BacktestSummary | null} summary
 * @param {import("./lib/portfolio.js").BacktestReturnRow[]} [primaryRows]
 */
export function renderBacktestSummary(kind, summary, primaryRows = []) {
  backtestSummaryCache[kind] = summary;
  renderBacktestHeadline(kind, summary);
  const oneLine = document.getElementById(`backtest-${kind}-oneline`);
  if (oneLine) oneLine.textContent = headlineLine(summary, primaryRows);
  renderBacktestMetricsTable(kind);
  renderBacktestKeyFacts(kind);
  renderBacktestCaveats(kind);
}

/** @type {Record<BacktestKind, boolean>} */
const backtestModeToggleBound = { a: false, b: false };

/** Wire one series' metrics-table gross/net switch once; idempotent.
 *  Re-renders just that series' metrics table (not the whole section) on
 *  click.
 *  @param {BacktestKind} kind */
export function bindBacktestModeToggle(kind) {
  if (backtestModeToggleBound[kind]) return;
  const row = document.getElementById(`backtest-${kind}-mode-toggle`);
  if (!row) return;
  backtestModeToggleBound[kind] = true;
  row.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const mode = target.dataset.mode;
    if (mode !== "gross" && mode !== "net") return;
    backtestMode[kind] = mode;
    for (const btn of row.querySelectorAll("button[data-mode]")) {
      btn.setAttribute("aria-pressed", btn.getAttribute("data-mode") === mode ? "true" : "false");
    }
    renderBacktestMetricsTable(kind);
  });
}

/** @typedef {{ticker: string, score: number, name?: string}} RankRow */

/**
 * @param {RankRow[]} rows
 * @param {number} [start] 1-based number of the first row (an `<ol start>`)
 * @returns {HTMLOListElement}
 */
function buildRankOl(rows, start = 1) {
  const ol = document.createElement("ol");
  ol.start = start;
  for (const row of rows) {
    const li = document.createElement("li");
    const ticker = document.createElement("span");
    ticker.textContent = row.ticker;
    li.append(ticker);
    if (row.name) {
      const name = document.createElement("span");
      name.className = "rank-name";
      name.textContent = row.name;
      li.append(name);
    }
    const score = document.createElement("span");
    score.className = "num";
    score.textContent = fmtNum(row.score, 1);
    li.append(score);
    ol.append(li);
  }
  return ol;
}

/**
 * @param {string} title
 * @param {RankRow[]} rows
 * @returns {HTMLDivElement}
 */
function buildRankList(title, rows) {
  const wrap = document.createElement("div");
  wrap.className = "backtest-rank-list";
  const h = document.createElement("h3");
  h.textContent = title;
  wrap.append(h, buildRankOl(rows));
  return wrap;
}

/** Plan 010 slice 2: rows shown per list before "Show all 25" (default, owner may override). */
const PICKS_VISIBLE = 10;

/**
 * @param {string} title
 * @param {RankRow[]} rows
 * @returns {HTMLDivElement}
 */
function buildPicksList(title, rows) {
  const wrap = document.createElement("div");
  wrap.className = "backtest-rank-list picks-list";
  const h = document.createElement("h3");
  h.textContent = title;
  wrap.append(h, buildRankOl(rows.slice(0, PICKS_VISIBLE)));
  if (rows.length > PICKS_VISIBLE) {
    const more = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `Show all ${rows.length}`;
    more.append(summary, buildRankOl(rows.slice(PICKS_VISIBLE), PICKS_VISIBLE + 1));
    wrap.append(more);
  }
  return wrap;
}

/**
 * Plan 010 slice 2: "Today's picks", the live aggregated best/worst 25
 * (`app.js`'s `loadCurrentAggregatedCandidates`, ADR-0014: the identical qte77
 * Score as their source universe). Best comes first in the DOM, so it stacks
 * above Worst on narrow screens (D3). A missing `entry` shows the empty hint.
 *
 * @param {{date: string, eligible: number, best: RankRow[], worst: RankRow[]} | null} entry
 */
export function renderTodaysPicks(entry) {
  const heading = document.getElementById("picks-heading");
  const body = document.getElementById("picks-body");
  if (!body) return;
  body.replaceChildren();
  if (!entry) {
    const hint = document.createElement("p");
    hint.className = "backtest-lists-empty";
    hint.textContent = BACKTEST_EMPTY;
    body.append(hint);
    return;
  }
  if (heading) heading.textContent = `Today's picks · ${entry.date}`;
  body.append(
    buildPicksList("Best 25 · qte77 Score", entry.best ?? []),
    buildPicksList("Worst 25 · qte77 Score", entry.worst ?? []),
  );
}

/**
 * Render one series' best/worst 25 collapsible. Only series B ("b") uses it
 * now: the historical "Latest best/worst 25" from the most recent
 * `results/backtest/lists/YYYY.json` entry (score_bt, #403/#404). Series A's
 * live lists moved to "Today's picks" (`renderTodaysPicks`, plan 010 slice 2).
 * A missing/empty `entry` renders the empty hint and never throws.
 *
 * @param {BacktestKind} kind
 * @param {{date: string, eligible: number, best: Array<{ticker: string, score: number}>, worst: Array<{ticker: string, score: number}>} | null} entry
 */
export function renderBacktestLists(kind, entry) {
  const summaryEl = document.querySelector(`#backtest-${kind}-lists summary`);
  const body = document.getElementById(`backtest-${kind}-lists-body`);
  if (!body) return;
  body.replaceChildren();
  if (!entry) {
    if (summaryEl) summaryEl.textContent = "Latest best/worst 25";
    const hint = document.createElement("p");
    hint.className = "backtest-lists-empty";
    hint.textContent = BACKTEST_EMPTY;
    body.append(hint);
    return;
  }
  if (summaryEl) {
    summaryEl.textContent = `Latest best/worst 25 (${entry.date} · ${entry.eligible} eligible)`;
  }
  body.append(
    buildRankList("Best 25", entry.best ?? []),
    buildRankList("Worst 25", entry.worst ?? []),
  );
}

/**
 * @param {import("./lib/portfolio.js").RankedTicker} ticker
 * @param {"entered" | "exited"} direction
 * @returns {HTMLSpanElement}
 */
function buildTradeChip(ticker, direction) {
  const span = document.createElement("span");
  span.className = `trade-chip trade-${direction}`;
  span.textContent = `${direction === "entered" ? "+" : "−"}${ticker.ticker}`;
  const details = [];
  if (ticker.rank != null) details.push(`rank ${ticker.rank}`);
  if (ticker.score != null) details.push(`score ${fmtNum(ticker.score, 1)}`);
  if (details.length > 0) span.title = details.join(", ");
  return span;
}

/**
 * One leg's (long or short) entered + exited chips for a rebalance-log row.
 * `rank`/`score` are nullable per ticker (Series A's `exited` legs always
 * are — `build_universe` has no full-pool lookup to resolve a name that
 * dropped out of the top/bottom 25, a disclosed limitation, not a bug).
 *
 * @param {import("./lib/portfolio.js").LegChange} leg
 * @returns {HTMLDivElement}
 */
function buildTradeLegCell(leg) {
  const wrap = document.createElement("div");
  wrap.className = "trade-leg-cell";
  const entered = leg?.entered ?? [];
  const exited = leg?.exited ?? [];
  for (const t of entered) wrap.append(buildTradeChip(t, "entered"));
  for (const t of exited) wrap.append(buildTradeChip(t, "exited"));
  if (entered.length === 0 && exited.length === 0) {
    const span = document.createElement("span");
    span.className = "trade-leg-empty";
    span.textContent = "—";
    wrap.append(span);
  }
  return wrap;
}

/**
 * @param {import("./lib/portfolio.js").TradeLogEntry & {reasonLabel: string}} row
 * @returns {HTMLTableRowElement}
 */
function buildTradeRow(row) {
  const tr = document.createElement("tr");
  const dateTd = document.createElement("td");
  dateTd.textContent = row.trade_date;
  const reasonTd = document.createElement("td");
  reasonTd.textContent = row.reasonLabel;
  const longTd = document.createElement("td");
  longTd.append(buildTradeLegCell(row.long));
  const shortTd = document.createElement("td");
  shortTd.append(buildTradeLegCell(row.short));
  const turnoverTd = document.createElement("td");
  turnoverTd.className = "num";
  turnoverTd.textContent = `${fmtPct(row.turnover)} %`;
  tr.append(dateTd, reasonTd, longTd, shortTd, turnoverTd);
  return tr;
}

/**
 * Render one series' "Rebalance log" collapsible (D21): newest-first, one
 * row per rebalance with its trade date, human reason label, and long/short
 * entered + exited tickers (color-coded, no blue) plus turnover. A
 * missing/404 `trades` array (the `trades/` paths don't exist yet, or this
 * series/cadence hasn't rebalanced) renders the empty hint and never throws
 * — same path as the lists/summary/chart empty states, no special-casing.
 *
 * @param {BacktestKind} kind
 * @param {import("./lib/portfolio.js").TradeLogEntry[] | null | undefined} trades
 */
export function renderBacktestTrades(kind, trades) {
  const summaryEl = document.querySelector(`#backtest-${kind}-trades summary`);
  const body = document.getElementById(`backtest-${kind}-trades-body`);
  if (!body) return;
  body.replaceChildren();
  const rows = tradeLogRows(trades);
  if (rows.length === 0) {
    if (summaryEl) summaryEl.textContent = "Rebalance log";
    const hint = document.createElement("p");
    hint.className = "backtest-lists-empty";
    hint.textContent = BACKTEST_EMPTY;
    body.append(hint);
    return;
  }
  if (summaryEl) summaryEl.textContent = `Rebalance log (${rows.length})`;
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "backtest-trades-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["Trade date", "Reason", "Long", "Short", "Turnover"]) {
    const th = document.createElement("th");
    if (label === "Turnover") th.className = "num";
    th.textContent = label;
    headRow.append(th);
  }
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  for (const row of rows) tbody.append(buildTradeRow(row));
  table.append(thead, tbody);
  wrap.append(table);
  body.append(wrap);
  observeScrollHint(wrap);
}

/**
 * Re-render every live Chart.js instance when the theme flips, so each
 * scriptable color closure re-resolves `--text` / `--primary` / etc. against
 * the new palette. The repo-local theme.js cycler dispatches a `themechange`
 * event on the document after applying `html[data-theme]`; without this, the
 * F&G lines stay near-invisible after a toggle until the next hover redraws.
 */
export function bindThemeObserver() {
  document.addEventListener("themechange", () => {
    for (const chart of liveCharts) chart.update("none");
  });
}
