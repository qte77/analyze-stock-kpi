// @ts-check
/* global Chart */
// Chart rendering extracted from app.js (#268).
// All app-state is accessed through the injected `ctx` object.

import { scoreYAxis, themedXAxis } from "./lib/chart_axes.js";
import { fetchJson } from "./lib/fetch.js";
import { fmtNum } from "./lib/format.js";
import { aggregateMonthlyFG } from "./lib/monthly.js";
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
  // Seam color follows --panel so slice borders blend cleanly with the
  // section background in both light and dark themes. Scriptable so it
  // re-resolves on theme flip via bindThemeObserver → chart.update().
  const borderColor = () => cssVar("--panel", "#e2dec8");
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
          borderColor: () => cssVar("--accent", "#7a6010"),
          backgroundColor: () => `${cssVar("--accent", "#7a6010")}26`,
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
          borderColor: () => cssVar("--accent", "#7a6010"),
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
let monthlyFearGreedChart = null;

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

function renderLongTermEmptyHint(/** @type {boolean} */ show) {
  toggleHistoryHint("lt-fg-chart-wrap", "lt-fg-empty", show);
}

function renderMonthlyFearGreedChart(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (document.getElementById("lt-fg-chart"));
  if (!canvas) return;
  const monthly = aggregateMonthlyFG(entries);
  destroyChart(monthlyFearGreedChart);
  monthlyFearGreedChart = null;
  renderLongTermEmptyHint(monthly.months.length === 0);
  if (monthly.months.length === 0 || typeof Chart === "undefined") return;
  monthlyFearGreedChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: monthly.months,
      datasets: [
        {
          label: "Median",
          data: monthly.median,
          borderColor: () => cssVar("--text", "#2c2818"),
          backgroundColor: () => `${cssVar("--text", "#2c2818")}14`,
          fill: false,
          pointRadius: 2,
          borderWidth: 1.5,
          tension: 0.2,
        },
        {
          label: "Average",
          data: monthly.avg,
          borderColor: () => cssVar("--accent", "#7a6010"),
          backgroundColor: () => `${cssVar("--accent", "#7a6010")}14`,
          fill: false,
          pointRadius: 2,
          borderWidth: 1.5,
          tension: 0.2,
          borderDash: [4, 3],
        },
      ],
    },
    options: {
      ...BASE_ANIMATED_OPTS,
      plugins: { legend: { display: true, position: "bottom" } },
      scales: { y: scoreYAxis(cssVar), x: themedXAxis(cssVar) },
    },
  });
  liveCharts.add(monthlyFearGreedChart);
}

/**
 * Wires the three-tab Long-term-context tab group:
 *   - Rolling history (F&G live + ~1y)
 *   - Long-term context (monthly F&G aggregate)
 *   - Yield curve (5s10s slope)
 *
 * Both the monthly chart and the yield-curve chart are lazily
 * constructed on first click — matches the detail-panel time-series
 * lazy pattern so initial paint stays cheap. The raw entry arrays are
 * captured at module level (`rawFgEntries` / `rawYcEntries`) so the
 * window-chip handlers can re-filter and re-render without re-fetching.
 *
 * @param {Array<{timestamp: string, score: number}>} fgEntries
 * @param {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} ycEntries
 */
export function bindLongTermTabs(fgEntries, ycEntries) {
  rawFgEntries = fgEntries;
  rawYcEntries = ycEntries;
  /** @type {Array<[string, string]>} */
  const tabs = [
    ["fg-tab-rolling", "fg-chart-wrap"],
    ["fg-tab-monthly", "lt-fg-chart-wrap"],
    ["fg-tab-yield-curve", "yc-chart-wrap"],
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
      if (pane.id === "lt-fg-chart-wrap" && !ltFgRendered) {
        renderActiveLtFg();
        ltFgRendered = true;
      }
      if (pane.id === "yc-chart-wrap" && !ycRendered) {
        renderActiveYc();
        ycRendered = true;
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
let ltFgRendered = false;
let ycRendered = false;

function renderActiveLtFg() {
  renderMonthlyFearGreedChart(filterByWindow(rawFgEntries, ctx.ltFgWindow, "timestamp"));
}

function renderActiveYc() {
  renderYieldCurveChart(filterByWindow(rawYcEntries, ctx.ycWindow, "date"));
}

/**
 * Wire the `.window-chips` chip rows above the long-term F&G + yield-curve
 * charts. Click toggles `aria-pressed`, updates the active window var,
 * re-renders the chart if its pane is currently visible (otherwise the
 * next tab activation picks up the new window), and persists state via URL.
 */
export function bindWindowChips() {
  /** @type {Array<[string, "ltFg" | "yc"]>} */
  const groups = [
    ["lt-fg-chart-wrap", "ltFg"],
    ["yc-chart-wrap", "yc"],
  ];
  for (const [wrapId, kind] of groups) {
    const wrap = document.getElementById(wrapId);
    const row = wrap?.querySelector(".window-chips");
    if (!wrap || !row) continue;
    syncChipAriaPressed(row, kind === "ltFg" ? ctx.ltFgWindow : ctx.ycWindow);
    row.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const next = /** @type {import("./lib/state.js").WindowKey} */ (target.dataset.window);
      if (!next) return;
      if (kind === "ltFg") {
        ctx.ltFgWindow = next;
        if (wrap.hidden) ltFgRendered = false;
        else renderActiveLtFg();
      } else {
        ctx.ycWindow = next;
        if (wrap.hidden) ycRendered = false;
        else renderActiveYc();
      }
      syncChipAriaPressed(row, next);
      ctx.afterWindowChange();
    });
  }
}

function syncChipAriaPressed(
  /** @type {Element} */ row,
  /** @type {import("./lib/state.js").WindowKey} */ active,
) {
  for (const btn of row.querySelectorAll("button[data-window]")) {
    btn.setAttribute("aria-pressed", btn.getAttribute("data-window") === active ? "true" : "false");
  }
}

/** @type {any} */
let yieldCurveChart = null;

/**
 * Toggle the yield-curve "no history yet" hint (#yc-chart-wrap). Overwrites the
 * static "loading…" placeholder via toggleHistoryHint's update-if-existing path.
 * @param {boolean} show
 */
function renderYieldCurveEmptyHint(show) {
  toggleHistoryHint("yc-chart-wrap", "yc-empty", show);
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
 * Render the slope line over all loaded history. Theme-aware via the
 * same scriptable cssVar() colour pattern as renderFearGreedChart.
 *
 * @param {Array<{date: string, slope_5s10s: number | null}>} entries
 */
function renderYieldCurveChart(entries) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (document.getElementById("yc-chart"));
  if (!canvas) return;
  destroyChart(yieldCurveChart);
  yieldCurveChart = null;
  const points = entries.filter((e) => e.slope_5s10s != null);
  renderYieldCurveEmptyHint(points.length === 0);
  if (points.length === 0 || typeof Chart === "undefined") return;
  yieldCurveChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: points.map((p) => p.date),
      datasets: [
        {
          label: "5s10s slope (10y − 5y, % pts)",
          data: points.map((p) => p.slope_5s10s),
          borderColor: () => cssVar("--accent", "#7a6010"),
          backgroundColor: () => `${cssVar("--accent", "#7a6010")}14`,
          fill: false,
          pointRadius: 1,
          borderWidth: 1.5,
          tension: 0.2,
        },
      ],
    },
    options: {
      ...BASE_ANIMATED_OPTS,
      plugins: { legend: { display: false } },
      scales: {
        // Highlight the zero line — inversions sit below.
        y: {
          grid: { color: () => `${cssVar("--border", "#c8c4b0")}` },
          ticks: { color: () => cssVar("--text", "#2c2818") },
        },
        x: themedXAxis(cssVar),
      },
    },
  });
  liveCharts.add(yieldCurveChart);
}

/**
 * Watches body class flips (theme-system / theme-light / theme-dark) and
 * pings every live Chart.js instance so its scriptable color closures
 * re-resolve `--text` / `--accent` / etc. against the new palette. Without
 * this, the F&G + monthly-F&G lines stay near-invisible after a dark-mode
 * toggle until the next hover triggers a redraw.
 */
export function bindThemeObserver() {
  const obs = new MutationObserver(() => {
    for (const chart of liveCharts) chart.update("none");
  });
  obs.observe(document.body, { attributes: true, attributeFilter: ["class"] });
}
