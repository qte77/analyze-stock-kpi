// @ts-check
/* global Chart, Fuse */
// Demo dashboard glue (#59, #134).
//
// Imports pure-JS units from ./lib/* (DOM-free, unit-tested); this file
// stays as the DOM glue. Switched to an ES module entry so the lib/
// imports resolve at runtime; vendor scripts (Chart.js, Fuse.js) still
// attach via the classic <script> tag.

import { buildAuditMap, loadAudit } from "./lib/audit.js";
import { exportCsv } from "./lib/csv.js";
import { fetchJson, loadYearsFromBranch } from "./lib/fetch.js";
import { fmtNum, nested } from "./lib/format.js";
import { aggregateMonthlyFG } from "./lib/monthly.js";
import { mergeUniverseSnapshots } from "./lib/overlay.js";
import { aggregateSectors, sectorColor } from "./lib/sector.js";
import {
  parseState,
  resolveViewMode,
  serializeState,
} from "./lib/state.js";
import { resolveTheme } from "./lib/theme.js";
import { buildTimeSeries } from "./lib/timeseries.js";
import { filterByWindow, findClosestScore } from "./lib/window.js";
import { bindDetailDismiss, showDetail } from "./detail_panel.js";
import { ALL_COLUMNS, renderUniverseTable } from "./table.js";

const DATA_BASE_URL = (
  new URLSearchParams(window.location.search).get("base") ??
  "https://raw.githubusercontent.com/qte77/analyze-stock-kpi/data"
).replace(/\/$/, "");

const VIEW_MODE_STORAGE_KEY = "demo-view-mode";
const THEME_STORAGE_KEY = "demo-theme";

const FALLBACK_UNIVERSE_IDS = [
  "qte77-watchlist",
  "sp500",
  "eurostoxx",
  "federal-contractors",
  "japan",
  "south-america",
  "south-korea",
  "aggregated-scores-best",
  "aggregated-scores-worst",
];

/** @type {string[]} */
let knownUniverseIds = [...FALLBACK_UNIVERSE_IDS];

let activeUniverse = "qte77-watchlist";

/**
 * Extra universes overlaid on top of `activeUniverse` (detailed mode
 * only). When non-empty, the table merges all snapshots and shows a
 * "Universe" column. Manipulated via the picker change handler (add)
 * and chip × buttons (remove). Persists via `?universe=primary,extra1,…`.
 * @type {string[]}
 */
let extraUniverses = [];

/** @type {Map<string, AuditRow> | null} */
let auditByTicker = null;

/** @type {"simple" | "detailed"} */
let viewMode = "simple";

const RATING_CLASSES = {
  "extreme fear": "rating-extreme-fear",
  "fear": "rating-fear",
  "neutral": "rating-neutral",
  "greed": "rating-greed",
  "extreme greed": "rating-extreme-greed",
};

/** @type {{snapshot: Row[], sortKey: string, sortDir: 1 | -1}} */
const state = {
  snapshot: [],
  sortKey: "composite_scores.screener_score",
  sortDir: -1,
};

/** @type {any} */
let fuseIndex = null;
let filterQuery = "";

/** Optional sector filter set by clicking a donut slice or legend
 *  entry. Combined with `filterQuery` in filteredSnapshot() — fuzzy
 *  text search first, then sector post-filter. Persisted via ?sector=…
 * @type {string | null} */
let sectorFilter = null;

/** @type {string | null} */
let currentDate = null;

/** Active time-window for the long-term F&G + yield-curve charts. Persisted
 *  via ?ltFgWindow= / ?ycWindow=; "all" is the default and is omitted from
 *  the URL. Filter is applied client-side over already-loaded entries —
 *  windows greater than the available data span gracefully render as "all".
 *  @type {import("./lib/state.js").WindowKey} */
let activeLtFgWindow = "all";
/** @type {import("./lib/state.js").WindowKey} */
let activeYcWindow = "all";

function rebuildFuseIndex() {
  fuseIndex =
    typeof Fuse !== "undefined" && state.snapshot.length
      ? new Fuse(state.snapshot, {
          keys: ["symbol", "long_name", "sector"],
          threshold: 0.3,
        })
      : null;
}

function filteredSnapshot() {
  let rows =
    !filterQuery || fuseIndex == null
      ? state.snapshot
      : fuseIndex.search(filterQuery).map((/** @type {{item: Row}} */ r) => r.item);
  if (sectorFilter) {
    rows = rows.filter((/** @type {Row} */ r) => (r.sector ?? "—") === sectorFilter);
  }
  return rows;
}

const loadManifest = () =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/index.json`);

const loadSnapshot = (/** @type {string} */ date) =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/${date}.json`);

const loadUniverses = () => fetchJson("universes.json");

/** @type {() => Promise<Array<{timestamp: string, score: number, rating?: string}>>} */
const loadFearGreedYears = () =>
  loadYearsFromBranch(DATA_BASE_URL, "results/cnn_fg", "timestamp");

/** @type {() => Promise<Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>>} */
const loadYieldCurveYears = () =>
  loadYearsFromBranch(DATA_BASE_URL, "results/yield_curve", "date");

// ───────────────────────── View-mode + URL state ───────────────────────────

function applyViewMode() {
  const body = document.body;
  body.classList.toggle("view-simple", viewMode === "simple");
  body.classList.toggle("view-detailed", viewMode === "detailed");
  const btn = document.getElementById("view-toggle");
  if (btn) {
    // Visible label is the destination view name; the muted desc
    // below it spells out what that view shows. Clicking flips to it.
    const label = btn.querySelector(".view-toggle-label");
    const desc = btn.querySelector(".view-toggle-desc");
    if (label && desc) {
      label.textContent = viewMode === "simple" ? "Detailed view" : "Simple view";
      desc.textContent = viewMode === "simple"
        ? "Show all KPI columns"
        : "Show essentials only";
    }
  }
}

/** @type {"system" | "light" | "dark"} */
let activeTheme = "system";

/**
 * Apply the active theme to `<body>` and sync the segmented toggle's
 * aria-pressed state. The three theme-* classes are mutually exclusive
 * (only one is set at any time); CSS picks the right palette via
 * `body.theme-dark` (forced) or `body.theme-system` + media query.
 */
function applyTheme() {
  const body = document.body;
  body.classList.toggle("theme-system", activeTheme === "system");
  body.classList.toggle("theme-light", activeTheme === "light");
  body.classList.toggle("theme-dark", activeTheme === "dark");
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  for (const btn of toggle.querySelectorAll("button[data-theme]")) {
    if (!(btn instanceof HTMLButtonElement)) continue;
    btn.setAttribute(
      "aria-pressed",
      btn.dataset.theme === activeTheme ? "true" : "false",
    );
  }
}

function persistStateFromCurrent() {
  const universes = activeUniverse
    ? [activeUniverse, ...extraUniverses]
    : [];
  const url = serializeState(
    {
      view: viewMode,
      universes,
      sortKey: state.sortKey,
      sortDir: state.sortDir,
      filter: filterQuery,
      date: currentDate,
      sector: sectorFilter,
      ltFgWindow: activeLtFgWindow,
      ycWindow: activeYcWindow,
    },
    window.location.href,
  );
  window.history.replaceState({}, "", url);
}

// ───────────────────────── Rendering ───────────────────────────

/**
 * Re-render the universe table from current module state. Thin adapter
 * over `renderUniverseTable()` in table.js: pre-filters via
 * `filteredSnapshot()` and passes the sort + universe + click context.
 */
function renderTable() {
  renderUniverseTable(filteredSnapshot(), {
    sortKey: state.sortKey,
    sortDir: state.sortDir,
    activeUniverse,
    filterQuery,
    onRowClick,
  });
}

function onRowClick(/** @type {Row} */ row) {
  showDetail(row, { auditByTicker, renderRadar, renderTimeSeriesPane });
}

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


function renderSectorDonut() {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("sector-donut")
  );
  if (!canvas || typeof Chart === "undefined") return;
  const aggregated = aggregateSectors(state.snapshot);
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
  const borderColor = () => cssVar("--panel", "#ffffff");
  // Pull the active sector's slice outward so the user has visual
  // confirmation of which slice the table is filtered by.
  const offset = labels.map((l) => (l === sectorFilter ? 12 : 0));
  sectorChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor, borderColor, borderWidth: 1, offset }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
              const pct =
                total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : "0";
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
        const w =
          entry.contentBoxSize?.[0]?.inlineSize ??
          entry.contentRect.width;
        const shouldShow = w >= SECTOR_LEGEND_MIN_WIDTH;
        if (
          sectorChart &&
          sectorChart.options.plugins.legend.display !== shouldShow
        ) {
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
  sectorFilter = sectorFilter === label ? null : label;
  renderSectorDonut();
  renderTable();
  persistStateFromCurrent();
}

/** Shared by every chart-section empty hint (sector donut, F&G rolling,
 *  long-term F&G, yield curve, universe-size badge). Per-section, context-
 *  specific strings stay inline at their site (e.g. table-empty's "first
 *  cron run pending"). */
const EMPTY_HISTORY = "no history yet";

/**
 * Toggle a centered "no history yet" hint inside a wrap element: create it
 * once when shown, remove it when hidden. Skip-if-existing — never
 * overwrites a present hint's text. Shared by the sector-donut and
 * long-term-F&G empty states (the rolling + yield-curve variants
 * intentionally overwrite, so they stay separate).
 *
 * @param {string} wrapId
 * @param {string} hintClass
 * @param {boolean} show
 */
function toggleHistoryHint(wrapId, hintClass, show) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  const existing = wrap.querySelector(`.${hintClass}`);
  if (show && !existing) {
    const hint = document.createElement("div");
    hint.className = hintClass;
    hint.textContent = EMPTY_HISTORY;
    wrap.append(hint);
  } else if (!show && existing) {
    existing.remove();
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
  if (!sectorFilter) {
    chipEl.hidden = true;
    return;
  }
  chipEl.hidden = false;
  chipEl.className = "universe-chip sector-chip";
  const label = document.createElement("span");
  label.textContent = `Sector: ${sectorFilter}`;
  const x = document.createElement("button");
  x.type = "button";
  x.textContent = "×";
  x.setAttribute("aria-label", `Clear sector filter (${sectorFilter})`);
  x.addEventListener("click", () => toggleSectorFilter(sectorFilter));
  chipEl.append(label, x);
}

function renderRadar(
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
            (a) =>
              /** @type {Record<string, number | null | undefined>} */ (scores)[a] ?? 0,
          ),
          borderColor: () => cssVar("--accent", "#0066cc"),
          backgroundColor: () => `${cssVar("--accent", "#0066cc")}26`,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 25,
            color: () => cssVar("--text", "#1d1d1f"),
            backdropColor: "transparent",
          },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
          angleLines: { color: () => cssVar("--border", "#d2d2d7") },
          pointLabels: { color: () => cssVar("--text", "#1d1d1f") },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
  liveCharts.add(radarChart);
}

/** @type {any} */
let timeSeriesChart = null;

/** @type {{dates: string[], latest: string} | null} */
let manifestCache = null;

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
async function renderTimeSeriesPane(pane, row) {
  if (!row.symbol) {
    pane.append(emptyHint("no ticker — nothing to plot"));
    return;
  }
  if (!manifestCache) {
    pane.append(emptyHint("loading manifest…"));
    return;
  }
  const dates = [...manifestCache.dates].sort();
  pane.append(emptyHint(`loading ${dates.length} snapshots…`));
  const results = await Promise.allSettled(
    dates.map((d) =>
      fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/${d}.json`),
    ),
  );
  /** @type {Array<{date: string, rows: Row[] | null}>} */
  const snapshotsByDate = dates.map((d, i) => ({
    date: d,
    rows:
      results[i].status === "fulfilled"
        ? /** @type {Row[]} */ (results[i].value)
        : null,
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
        { label: "qte77 Score", data: series.score, borderColor: () => cssVar("--accent", "#0066cc") },
        { label: "Quality", data: series.quality, borderColor: () => cssVar("--rating-greed", "#27ae60") },
        { label: "Growth", data: series.growth, borderColor: () => cssVar("--rating-fear", "#e67e22") },
        { label: "Sortino", data: series.sortino, borderColor: () => cssVar("--rating-extreme-fear", "#c0392b"), yAxisID: "y1" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          ...scoreYAxis(),
          title: { display: true, text: "Composite (0–100)", color: () => cssVar("--text", "#1d1d1f") },
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: () => cssVar("--text", "#1d1d1f") },
          title: { display: true, text: "Sortino", color: () => cssVar("--text", "#1d1d1f") },
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

function renderFearGreedHeader(
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
  chipEl.className = `chip ${
    /** @type {Record<string, string>} */ (RATING_CLASSES)[rating] ?? ""
  }`;
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

/** @type {Set<any>} */
const liveCharts = new Set();

/**
 * @param {string} token  CSS custom property name (with leading `--`).
 * @param {string} fallback  Hex used if the token is unset.
 * @returns {string}  Resolved hex/rgb string (no alpha).
 */
function cssVar(token, fallback) {
  return (
    getComputedStyle(document.body).getPropertyValue(token).trim() || fallback
  );
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

/** Themed 0–100 score y-axis (stepSize 25) shared by the composite line
 *  charts. The cssVar closures re-resolve on theme flip via bindThemeObserver. */
function scoreYAxis() {
  return {
    min: 0,
    max: 100,
    ticks: { stepSize: 25, color: () => cssVar("--text", "#1d1d1f") },
    grid: { color: () => cssVar("--border", "#d2d2d7") },
  };
}

/** Themed x-axis with a tick cap, shared by the time-series line charts.
 *  @param {number} [maxTicks] */
function themedXAxis(maxTicks = 14) {
  return {
    ticks: { maxTicksLimit: maxTicks, color: () => cssVar("--text", "#1d1d1f") },
    grid: { color: () => cssVar("--border", "#d2d2d7") },
  };
}

function renderRollingEmptyHint(/** @type {boolean} */ show) {
  const wrap = document.getElementById("fg-chart-wrap");
  if (!wrap) return;
  let hint = wrap.querySelector(".fg-empty");
  if (show) {
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "fg-empty";
      wrap.append(hint);
    }
    hint.textContent = EMPTY_HISTORY;
  } else if (hint) {
    hint.remove();
  }
}

function renderFearGreedChart(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
) {
  const ctx = /** @type {HTMLCanvasElement | null} */ (document.getElementById("fg-chart"));
  if (!ctx) return;
  destroyChart(fearGreedChart);
  fearGreedChart = null;
  // Strict trailing 12-month window — the loader concatenates this-year +
  // last-year files, so trim from the latest entry's date.
  const windowed = filterByWindow(entries, "1y", "timestamp");
  renderRollingEmptyHint(windowed.length === 0);
  if (!windowed.length || typeof Chart === "undefined") return;
  fearGreedChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: windowed.map((e) => e.timestamp.slice(0, 10)),
      datasets: [
        {
          data: windowed.map((e) => e.score),
          borderColor: () => cssVar("--text", "#1d1d1f"),
          backgroundColor: () => `${cssVar("--text", "#1d1d1f")}14`,
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: { legend: { display: false } },
      scales: { y: scoreYAxis(), x: themedXAxis() },
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
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("lt-fg-chart")
  );
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
          borderColor: () => cssVar("--text", "#1d1d1f"),
          backgroundColor: () => `${cssVar("--text", "#1d1d1f")}14`,
          fill: false,
          pointRadius: 2,
          borderWidth: 1.5,
          tension: 0.2,
        },
        {
          label: "Average",
          data: monthly.avg,
          borderColor: () => cssVar("--accent", "#0066cc"),
          backgroundColor: () => `${cssVar("--accent", "#0066cc")}14`,
          fill: false,
          pointRadius: 2,
          borderWidth: 1.5,
          tension: 0.2,
          borderDash: [4, 3],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: { legend: { display: true, position: "bottom" } },
      scales: { y: scoreYAxis(), x: themedXAxis() },
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
function bindLongTermTabs(fgEntries, ycEntries) {
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
  renderMonthlyFearGreedChart(
    filterByWindow(rawFgEntries, activeLtFgWindow, "timestamp"),
  );
}

function renderActiveYc() {
  renderYieldCurveChart(filterByWindow(rawYcEntries, activeYcWindow, "date"));
}

/**
 * Wire the `.window-chips` chip rows above the long-term F&G + yield-curve
 * charts. Click toggles `aria-pressed`, updates the active window var,
 * re-renders the chart if its pane is currently visible (otherwise the
 * next tab activation picks up the new window), and persists state via URL.
 */
function bindWindowChips() {
  /** @type {Array<[string, "ltFg" | "yc"]>} */
  const groups = [
    ["lt-fg-chart-wrap", "ltFg"],
    ["yc-chart-wrap", "yc"],
  ];
  for (const [wrapId, kind] of groups) {
    const wrap = document.getElementById(wrapId);
    const row = wrap?.querySelector(".window-chips");
    if (!wrap || !row) continue;
    syncChipAriaPressed(row, kind === "ltFg" ? activeLtFgWindow : activeYcWindow);
    row.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const next = /** @type {import("./lib/state.js").WindowKey} */ (
        target.dataset.window
      );
      if (!next) return;
      if (kind === "ltFg") {
        activeLtFgWindow = next;
        if (wrap.hidden) ltFgRendered = false;
        else renderActiveLtFg();
      } else {
        activeYcWindow = next;
        if (wrap.hidden) ycRendered = false;
        else renderActiveYc();
      }
      syncChipAriaPressed(row, next);
      persistStateFromCurrent();
    });
  }
}

function syncChipAriaPressed(
  /** @type {Element} */ row,
  /** @type {import("./lib/state.js").WindowKey} */ active,
) {
  for (const btn of row.querySelectorAll("button[data-window]")) {
    btn.setAttribute(
      "aria-pressed",
      btn.getAttribute("data-window") === active ? "true" : "false",
    );
  }
}

/** @type {any} */
let yieldCurveChart = null;

/**
 * Toggle a "no history yet" hint inside #yc-chart-wrap. When the
 * static "loading…" placeholder is still in the DOM (lazy-render
 * path: data fetched but tab not yet clicked → empty result on
 * click), overwrite its text instead of double-appending.
 *
 * @param {boolean} show
 */
function renderYieldCurveEmptyHint(show) {
  const wrap = document.getElementById("yc-chart-wrap");
  if (!wrap) return;
  const existing = wrap.querySelector(".yc-empty");
  if (show) {
    if (existing) {
      existing.textContent = EMPTY_HISTORY;
    } else {
      const hint = document.createElement("div");
      hint.className = "yc-empty";
      hint.textContent = EMPTY_HISTORY;
      wrap.append(hint);
    }
  } else if (existing) {
    existing.remove();
  }
}

/**
 * Surface today's slope + raw legs above the chart so the chart's role
 * stays "trajectory" while the header carries the current-day reading.
 * @param {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} entries
 */
function renderYieldCurveHeader(entries) {
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
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("yc-chart")
  );
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
          borderColor: () => cssVar("--accent", "#0066cc"),
          backgroundColor: () => `${cssVar("--accent", "#0066cc")}14`,
          fill: false,
          pointRadius: 1,
          borderWidth: 1.5,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: { legend: { display: false } },
      scales: {
        // Highlight the zero line — inversions sit below.
        y: {
          grid: { color: () => `${cssVar("--border", "#d2d2d7")}` },
          ticks: { color: () => cssVar("--text", "#1d1d1f") },
        },
        x: themedXAxis(),
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
function bindThemeObserver() {
  const obs = new MutationObserver(() => {
    for (const chart of liveCharts) chart.update("none");
  });
  obs.observe(document.body, { attributes: true, attributeFilter: ["class"] });
}

function bindTableSort() {
  document.querySelectorAll("#universe-table thead th").forEach((th) => {
    if (!(th instanceof HTMLElement)) return;
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (!key) return;
      if (state.sortKey === key) {
        state.sortDir = /** @type {1 | -1} */ (state.sortDir * -1);
      } else {
        state.sortKey = key;
        state.sortDir = 1;
      }
      document.querySelectorAll("#universe-table thead th").forEach((t) => {
        t.classList.remove("sort-asc", "sort-desc");
      });
      th.classList.add(state.sortDir > 0 ? "sort-asc" : "sort-desc");
      renderTable();
      persistStateFromCurrent();
    });
  });
}

function bindKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const inEditable =
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement;
    if (event.key === "/" && !inEditable) {
      event.preventDefault();
      document.getElementById("universe-filter")?.focus();
    }
  });
}

function bindCsvExport() {
  const btn = document.getElementById("export-csv");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const rows = filteredSnapshot();
    const headers = [...ALL_COLUMNS];
    const csv = exportCsv(
      rows.map((/** @type {Row} */ r) =>
        Object.fromEntries(headers.map((h) => [h, nested(r, h)])),
      ),
      headers,
    );
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeUniverse}-${currentDate ?? "latest"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

/** Fetch one universe's snapshot at a given date; null on any failure. */
async function fetchUniverseSnapshot(
  /** @type {string} */ universe,
  /** @type {string} */ date,
) {
  try {
    return /** @type {Row[]} */ (
      await fetchJson(`${DATA_BASE_URL}/results/demo/${universe}/${date}.json`)
    );
  } catch {
    return null;
  }
}

async function loadActiveUniverse() {
  const dateSelector = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("date-selector")
  );
  const sizeEl = document.getElementById("universe-size");
  if (!dateSelector || !sizeEl) return;
  let manifest;
  try {
    manifest = await loadManifest();
  } catch {
    state.snapshot = [];
    auditByTicker = null;
    rebuildFuseIndex();
    dateSelector.replaceChildren();
    sizeEl.textContent = `· ${EMPTY_HISTORY}`;
    renderTable();
    renderSectorDonut();
    renderUniverseChips();
    return;
  }
  dateSelector.replaceChildren();
  for (const date of [...manifest.dates].reverse()) {
    const opt = document.createElement("option");
    opt.value = date;
    opt.textContent = date;
    dateSelector.appendChild(opt);
  }
  dateSelector.value = manifest.latest;
  currentDate = manifest.latest;
  manifestCache = { dates: manifest.dates, latest: manifest.latest };

  // Primary snapshot (await directly so a failure still surfaces in the
  // "no data" branch above). Extras fan out in parallel via allSettled.
  const primary = await loadSnapshot(manifest.latest);
  /** @type {Record<string, Row[] | null>} */
  const byUniverse = { [activeUniverse]: primary };
  if (extraUniverses.length > 0) {
    const results = await Promise.allSettled(
      extraUniverses.map((u) => fetchUniverseSnapshot(u, manifest.latest)),
    );
    extraUniverses.forEach((u, i) => {
      const r = results[i];
      byUniverse[u] = r.status === "fulfilled" ? r.value : null;
    });
  }
  state.snapshot =
    extraUniverses.length === 0
      ? primary
      : mergeUniverseSnapshots(byUniverse);
  document.body.classList.toggle("overlay-active", extraUniverses.length >= 1);

  const auditMap = await loadAudit(
    activeUniverse,
    manifest.latest,
    DATA_BASE_URL,
    fetchJson,
  );
  auditByTicker = auditMap ?? buildAuditMap([]);
  rebuildFuseIndex();
  sizeEl.textContent =
    extraUniverses.length === 0
      ? `· ${state.snapshot.length} tickers`
      : `· ${state.snapshot.length} tickers · ${1 + extraUniverses.length} universes`;
  renderTable();
  renderSectorDonut();
  renderUniverseChips();
  const updatedEl = document.getElementById("updated");
  if (updatedEl) updatedEl.textContent = `updated ${manifest.updated_at}`;
}

function renderUniverseChips() {
  const chipsEl = document.getElementById("universe-chips");
  if (!chipsEl) return;
  chipsEl.replaceChildren();
  if (extraUniverses.length === 0) return;
  // Primary chip — no remove button (it's the active picker selection).
  chipsEl.append(makeChip(activeUniverse, false));
  for (const u of extraUniverses) chipsEl.append(makeChip(u, true));
}

/**
 * @param {string} universe
 * @param {boolean} removable
 * @returns {HTMLSpanElement}
 */
function makeChip(universe, removable) {
  const chip = document.createElement("span");
  chip.className = "universe-chip";
  chip.append(document.createTextNode(universe));
  if (removable) {
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.setAttribute("aria-label", `Remove ${universe} from overlay`);
    x.addEventListener("click", async () => {
      extraUniverses = extraUniverses.filter((u) => u !== universe);
      persistStateFromCurrent();
      await loadActiveUniverse();
    });
    chip.append(x);
  }
  return chip;
}

function setupTheme() {
  // Theme: URL `?theme=` beats localStorage beats the "system" default.
  const themeUrl = new URLSearchParams(window.location.search).get("theme");
  const lsTheme = window.localStorage?.getItem(THEME_STORAGE_KEY) ?? null;
  activeTheme = resolveTheme(themeUrl, lsTheme);
  applyTheme();
  document.getElementById("theme-toggle")?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const next = target.dataset.theme;
    if (next !== "system" && next !== "light" && next !== "dark") return;
    activeTheme = next;
    applyTheme();
    window.localStorage?.setItem(THEME_STORAGE_KEY, activeTheme);
    const url = new URL(window.location.href);
    if (activeTheme === "system") url.searchParams.delete("theme");
    else url.searchParams.set("theme", activeTheme);
    window.history.replaceState({}, "", url);
  });
}

function bindViewToggle() {
  document.getElementById("view-toggle")?.addEventListener("click", () => {
    viewMode = viewMode === "simple" ? "detailed" : "simple";
    applyViewMode();
    window.localStorage?.setItem(VIEW_MODE_STORAGE_KEY, viewMode);
    persistStateFromCurrent();
    renderTable();
  });
}

/**
 * Fetch the universes manifest and populate the picker. Falls back to
 * FALLBACK_UNIVERSE_IDS if the manifest is unreachable.
 *
 * @param {HTMLSelectElement} picker
 * @returns {Promise<{id: string, label: string}[]>}
 */
async function populateUniversePicker(picker) {
  /** @type {{universes: {id: string, label: string}[]}} */
  let payload;
  try {
    payload = await loadUniverses();
  } catch {
    payload = { universes: FALLBACK_UNIVERSE_IDS.map((id) => ({ id, label: id })) };
  }
  const universes = payload.universes ?? [];
  knownUniverseIds = universes.map((u) => u.id);
  for (const u of universes) {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = u.label;
    picker.appendChild(opt);
  }
  return universes;
}

/** @param {HTMLSelectElement} picker */
function bindUniversePicker(picker) {
  picker.addEventListener("change", async () => {
    // Picker always replaces. Overlay (multi-universe merge) is still
    // available via `?universe=primary,extra1,…` deep-links and via
    // the chip × removal — only the change handler no longer appends.
    activeUniverse = picker.value;
    extraUniverses = [];
    persistStateFromCurrent();
    await loadActiveUniverse();
  });
}

/** @param {ReturnType<typeof parseState>} parsed */
function hydrateUrlState(parsed) {
  if (parsed.sortKey) {
    state.sortKey = parsed.sortKey;
    state.sortDir = parsed.sortDir;
  }
  if (parsed.filter) {
    filterQuery = parsed.filter;
    const filterInput = /** @type {HTMLInputElement | null} */ (
      document.getElementById("universe-filter")
    );
    if (filterInput) filterInput.value = parsed.filter;
  }
  if (parsed.sector) sectorFilter = parsed.sector;
  activeLtFgWindow = parsed.ltFgWindow;
  activeYcWindow = parsed.ycWindow;
}

/** @param {HTMLSelectElement} dateSelector */
function bindDateSelector(dateSelector) {
  dateSelector.addEventListener("change", async () => {
    const newDate = dateSelector.value;
    state.snapshot = await loadSnapshot(newDate);
    const auditMap = await loadAudit(
      activeUniverse,
      newDate,
      DATA_BASE_URL,
      fetchJson,
    );
    auditByTicker = auditMap ?? buildAuditMap([]);
    currentDate = newDate;
    rebuildFuseIndex();
    renderTable();
    renderSectorDonut();
    persistStateFromCurrent();
  });
}

function bindFilterInput() {
  document.getElementById("universe-filter")?.addEventListener("input", (e) => {
    const target = e.target;
    if (target instanceof HTMLInputElement) {
      filterQuery = target.value.trim();
      renderTable();
      persistStateFromCurrent();
    }
  });
}

/**
 * Apply ?date=… from the URL after the date selector has been populated
 * by loadActiveUniverse(); silently no-ops if the requested date isn't
 * among the available options.
 *
 * @param {string | null} requested
 * @param {HTMLSelectElement | null} dateSelector
 */
function applyDateFromUrl(requested, dateSelector) {
  if (!requested || !dateSelector) return;
  const options = Array.from(dateSelector.options).map((o) => o.value);
  if (options.includes(requested)) {
    dateSelector.value = requested;
    dateSelector.dispatchEvent(new Event("change"));
  }
}

async function init() {
  bindDetailDismiss();
  bindTableSort();
  bindKeyboardShortcuts();
  bindCsvExport();

  const parsed = parseState(window.location.search, knownUniverseIds);
  const lsView = window.localStorage?.getItem(VIEW_MODE_STORAGE_KEY) ?? null;
  viewMode = resolveViewMode(parsed.view, lsView);
  applyViewMode();

  setupTheme();
  bindViewToggle();

  const picker = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("universe-picker")
  );
  if (!picker) return;
  const universes = await populateUniversePicker(picker);
  const requested = parsed.universes[0];
  activeUniverse =
    requested && knownUniverseIds.includes(requested)
      ? requested
      : universes[0]?.id ?? "qte77-watchlist";
  // Extras are universes 2..N from the URL, filtered against the
  // whitelist and de-duplicated against the primary.
  extraUniverses = parsed.universes
    .slice(1)
    .filter((u) => u !== activeUniverse && knownUniverseIds.includes(u));
  picker.value = activeUniverse;
  bindUniversePicker(picker);

  hydrateUrlState(parsed);

  const dateSelector = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("date-selector")
  );
  if (dateSelector) bindDateSelector(dateSelector);
  bindFilterInput();

  await loadActiveUniverse();
  applyDateFromUrl(parsed.date, dateSelector);

  const [fgEntries, ycEntries] = await Promise.all([
    loadFearGreedYears(),
    loadYieldCurveYears(),
  ]);
  renderFearGreedHeader(fgEntries);
  renderFearGreedChart(fgEntries);
  renderYieldCurveHeader(ycEntries);
  bindLongTermTabs(fgEntries, ycEntries);
  bindWindowChips();
  bindThemeObserver();
}

document.addEventListener("DOMContentLoaded", init);
