// @ts-check
/* global Chart */
// Chart rendering extracted from app.js (#268).
// All app-state is accessed through the injected `ctx` object.

import { logRightAxis, scoreYAxis, themedXAxis } from "./lib/chart_axes.js";
import { buildCombinedSeries } from "./lib/combined.js";
import { fetchJson } from "./lib/fetch.js";
import { fmtNum, fmtPct } from "./lib/format.js";
import {
  CADENCE_LABELS,
  CADENCE_ORDER,
  compound,
  keyFacts,
  metricsTableRows,
} from "./lib/portfolio.js";
import { aggregateSectors, sectorColor } from "./lib/sector.js";
import { buildTimeSeries } from "./lib/timeseries.js";
import { filterByWindow, findClosestScore } from "./lib/window.js";

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
  const axes = ["quality", "dividend", "growth", "big_call", "aaqs", "hgi", "screener_score"];
  destroyChart(radarChart);
  radarChart = new Chart(canvas, {
    type: "radar",
    data: {
      labels: axes.map((a) => a.replace("screener_score", "qte77 Score")),
      datasets: [
        {
          label: "score",
          data: axes.map(
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
          ticks: {
            stepSize: 25,
            color: () => cssVar("--text", "#2c2818"),
            backdropColor: "transparent",
          },
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
 *   - Why these charts?
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
    ["fg-tab-why", "why-wrap"],
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

/** @type {any} */
let backtestChart = null;

const BACKTEST_EMPTY = "Backtest runs Saturdays";

function renderBacktestChartEmptyHint(/** @type {boolean} */ show) {
  toggleHistoryHint("backtest-chart-wrap", "backtest-chart-empty", show, BACKTEST_EMPTY);
}

/** Thin "foil" cadence line colors (everything but the primary, which uses
 *  --primary for both its net/gross lines) — the zero-blue EyeRest data arc. */
const FOIL_COLORS = ["--data-alt", "--data-caution", "--data-negative", "--text-muted"];

/**
 * Render the backtested long/short 25/25 index chart (ADR-0013): the primary
 * cadence's net index (bold) + gross index (dashed), plus the other four
 * cadences' net index as thin foil lines — all 100-based, compounded
 * client-side via `compound()` (D5/D8 — no stored NAV). A 404 before the
 * first Saturday cron run (every cadence's rows empty) shows the empty hint
 * and never throws — the caller passes `{}`/`[]` for a failed/missing fetch.
 *
 * @param {Record<string, import("./lib/portfolio.js").BacktestReturnRow[]>} seriesByCadence
 * @param {string | null | undefined} primary
 */
export function renderBacktestChart(seriesByCadence, primary) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("backtest-chart")
  );
  if (!canvas) return;
  destroyChart(backtestChart);
  backtestChart = null;
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
  renderBacktestChartEmptyHint(!hasData);
  if (!hasData || typeof Chart === "undefined") return;
  const labels = [primaryNet, ...foils].reduce(
    (longest, series) => (series.dates.length > longest.length ? series.dates : longest),
    /** @type {string[]} */ ([]),
  );
  backtestChart = new Chart(canvas, {
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
  liveCharts.add(backtestChart);
}

/** @type {import("./lib/portfolio.js").BacktestSummary | null} */
let backtestSummaryCache = null;
/** @type {"gross" | "net"} */
let backtestMode = "net";

function renderBacktestMetricsTable() {
  const tbody = document.querySelector("#backtest-metrics-table tbody");
  if (!tbody) return;
  tbody.replaceChildren();
  for (const row of metricsTableRows(backtestSummaryCache, backtestMode)) {
    const tr = document.createElement("tr");
    if (row.primary) tr.className = "backtest-primary-row";
    const cells = [
      row.label,
      `${fmtPct(row.ann_return)} %`,
      `${fmtPct(row.ann_vol)} %`,
      `${fmtPct(row.max_drawdown)} %`,
      `${fmtPct(row.ann_turnover)} %`,
      `${fmtPct(row.long_ann_return)} %`,
      `${fmtPct(row.short_ann_return)} %`,
      fmtNum(row.beta, 2),
      `${fmtPct(row.hit_rate)} %`,
      `${fmtPct(row.mean_monthly_return)} % [${fmtPct(row.ci90?.[0])}, ${fmtPct(row.ci90?.[1])}]`,
      fmtNum(row.t_stat, 2),
      row.rebalances != null ? String(row.rebalances) : "—",
    ];
    cells.forEach((text, i) => {
      const td = document.createElement("td");
      if (i > 0) td.className = "num";
      td.textContent = text;
      tr.append(td);
    });
    tbody.append(tr);
  }
}

function renderBacktestKeyFacts() {
  const el = document.getElementById("backtest-key-facts");
  if (!el) return;
  const facts = keyFacts(backtestSummaryCache);
  el.textContent = facts.start
    ? `Start ${facts.start} · Realized beta to SPY ${fmtNum(facts.beta, 2)} · ` +
      `Null percentile ${fmtNum(facts.nullPercentile, 0)}th · Fidelity median ρ ${fmtNum(facts.fidelityRho, 2)}`
    : "";
}

function renderBacktestCaveats() {
  const el = document.getElementById("backtest-caveats");
  if (!el) return;
  el.replaceChildren();
  for (const caveat of backtestSummaryCache?.caveats ?? []) {
    const li = document.createElement("li");
    li.textContent = caveat;
    el.append(li);
  }
}

/**
 * Render the backtest summary block: the metrics table (D9, one gross/net
 * mode at a time — default net), the key-facts line, and the caveats
 * (rendered verbatim from `summary.caveats`). A missing/404 `summary`
 * (before the first Saturday cron run) renders an empty table + blank
 * key-facts line and never throws.
 *
 * @param {import("./lib/portfolio.js").BacktestSummary | null} summary
 */
export function renderBacktestSummary(summary) {
  backtestSummaryCache = summary;
  renderBacktestMetricsTable();
  renderBacktestKeyFacts();
  renderBacktestCaveats();
}

let backtestModeToggleBound = false;

/** Wire the metrics table's gross/net switch once; idempotent. Re-renders
 *  just the metrics table (not the whole section) on click. */
export function bindBacktestModeToggle() {
  if (backtestModeToggleBound) return;
  const row = document.getElementById("backtest-mode-toggle");
  if (!row) return;
  backtestModeToggleBound = true;
  row.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const mode = target.dataset.mode;
    if (mode !== "gross" && mode !== "net") return;
    backtestMode = mode;
    for (const btn of row.querySelectorAll("button[data-mode]")) {
      btn.setAttribute("aria-pressed", btn.getAttribute("data-mode") === mode ? "true" : "false");
    }
    renderBacktestMetricsTable();
  });
}

/**
 * @param {string} title
 * @param {Array<{ticker: string, score: number}>} rows
 * @returns {HTMLDivElement}
 */
function buildRankList(title, rows) {
  const wrap = document.createElement("div");
  wrap.className = "backtest-rank-list";
  const h = document.createElement("h3");
  h.textContent = title;
  wrap.append(h);
  const ol = document.createElement("ol");
  for (const row of rows) {
    const li = document.createElement("li");
    const ticker = document.createElement("span");
    ticker.textContent = row.ticker;
    const score = document.createElement("span");
    score.className = "num";
    score.textContent = fmtNum(row.score, 1);
    li.append(ticker, score);
    ol.append(li);
  }
  wrap.append(ol);
  return wrap;
}

/**
 * Render the latest best/worst 25 collapsible from the most recent
 * `results/backtest/lists/YYYY.json` entry. A missing/empty `entry` (before
 * the first Saturday cron run) renders the empty hint and never throws.
 *
 * @param {{date: string, eligible: number, best: Array<{ticker: string, score: number}>, worst: Array<{ticker: string, score: number}>} | null} entry
 */
export function renderBacktestLists(entry) {
  const summaryEl = document.querySelector("#backtest-lists summary");
  const body = document.getElementById("backtest-lists-body");
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
