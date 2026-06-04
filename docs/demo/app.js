// @ts-check
/* global Chart, Fuse */
// Demo dashboard glue (#59, #134).
//
// Imports pure-JS units from ./lib/* (DOM-free, unit-tested); this file
// stays as the DOM glue. Switched to an ES module entry so the lib/
// imports resolve at runtime; vendor scripts (Chart.js, Fuse.js) still
// attach via the classic <script> tag.

import { buildAuditMap, formatObligated, loadAudit } from "./lib/audit.js";
import { cellClass } from "./lib/coloring.js";
import { exportCsv } from "./lib/csv.js";
import { explainEmpty } from "./lib/empty_reason.js";
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

const KPI_GLOSSARY = {
  forward_pe: "Forward P/E = price / next-12mo EPS estimate. Lower = cheaper.",
  trailing_pe: "Trailing P/E = price / past-12mo EPS. Lower = cheaper.",
  trail_fwd_pe:
    "Trailing P/E divided by Forward P/E. >1 = EPS growth expected; <1 = EPS contraction expected.",
  trailing_peg_ratio:
    "Trailing PEG = P/E adjusted for historical earnings growth. Lower better; <1 is the classic Peter Lynch threshold.",
  beta: "5y market sensitivity. <1 = less volatile than market.",
  rd_to_revenue:
    "R&D expense / total revenue (latest annual income statement). EQUITY-only.",
  operating_margins:
    "Operating income / revenue. Pre-tax, pre-interest — comparable across countries.",
  gross_margins: "(Revenue - COGS) / revenue. Pricing power / cost discipline.",
  profit_margins:
    "Net margin = net income / revenue. Bottom-line efficiency after tax + interest.",
  return_on_equity:
    "ROE = net income / equity. Profitability per equity dollar; sensitive to leverage.",
  return_on_assets:
    "ROA = net income / total assets. Leverage-neutral profitability per asset dollar.",
  roi:
    "Simplified ROIC = NetIncome / (BookEquity + TotalDebt - TotalCash). Screener-style; not company-filed ROIC.",
  current_ratio:
    "Current assets / current liabilities. Short-term liquidity (>1 = assets cover liabilities).",
  quick_ratio:
    "(Current assets - inventory) / current liabilities. Stricter liquidity than Current.",
  debt_to_equity: "Total debt / equity. Leverage (higher = more leveraged).",
  sortino_ratio:
    "Annualized Sortino over 1y (rf=0). Higher = better upside vs downside skew.",
  screener_score:
    "Mean of 4 thematic factor scores: Profitability (>=2/4 inputs); Valuation (>=1/2); Risk (>=1/2); Momentum (1/1). Higher = better.",
  quality:
    "Mean of normalized ROE, ROA, operating margin, and inverted D/E. Higher = stronger fundamentals.",
  dividend:
    "Dividend yield + payout-ratio sweet spot (peaks near ~50% payout). Higher = healthier dividend profile.",
  growth:
    "Mean of normalized revenue + earnings growth. Higher = stronger top-line and bottom-line growth.",
  big_call:
    "Weighted Quality (40%) + Dividend (30%) + Growth (30%); reweights proportionally when a component is missing.",
  aaqs: "Quality combined with low-volatility (low beta is better).",
  hgi: "Growth-tilted score with a fixed bonus when operating margin clears ~10%.",
};

async function fetchJson(/** @type {string} */ url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  return res.json();
}

const loadManifest = () =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/index.json`);

const loadSnapshot = (/** @type {string} */ date) =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/${date}.json`);

const loadUniverses = () => fetchJson("universes.json");

/**
 * Fetch this-year + last-year per-year JSON files from the data branch
 * and concat. Silent-fail per leg so a brand-new repo (no
 * `results/<prefix>/<thisYear>.json` yet on the data branch) still
 * paints what's available. Sorts ascending by the named string field.
 *
 * @param {string} pathPrefix  e.g. "results/cnn_fg" / "results/yield_curve"
 * @param {string} sortKey     e.g. "timestamp" / "date"
 * @returns {Promise<Array<any>>}
 */
async function loadYearsFromBranch(pathPrefix, sortKey) {
  const thisYear = new Date().getUTCFullYear();
  const results = await Promise.allSettled([
    fetchJson(`${DATA_BASE_URL}/${pathPrefix}/${thisYear - 1}.json`),
    fetchJson(`${DATA_BASE_URL}/${pathPrefix}/${thisYear}.json`),
  ]);
  /** @type {Array<any>} */
  const merged = [];
  for (const r of results) {
    if (r.status === "fulfilled" && Array.isArray(r.value)) {
      merged.push(...r.value);
    }
  }
  return merged.sort((a, b) => a[sortKey].localeCompare(b[sortKey]));
}

/** @type {() => Promise<Array<{timestamp: string, score: number, rating?: string}>>} */
const loadFearGreedYears = () =>
  loadYearsFromBranch("results/cnn_fg", "timestamp");

/** @type {() => Promise<Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>>} */
const loadYieldCurveYears = () =>
  loadYearsFromBranch("results/yield_curve", "date");

function nested(/** @type {Row} */ obj, /** @type {string} */ key) {
  return key
    .split(".")
    .reduce(
      (/** @type {any} */ o, /** @type {string} */ k) => (o == null ? null : o[k]),
      obj,
    );
}

const fmtNum = (/** @type {unknown} */ v, /** @type {number} */ d = 1) =>
  v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d);

const fmtPct = (/** @type {unknown} */ v) =>
  v == null ? "—" : (Number(v) * 100).toFixed(2);

function compareValues(
  /** @type {unknown} */ a,
  /** @type {unknown} */ b,
  /** @type {1 | -1} */ dir,
) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "string" && typeof b === "string") return dir * a.localeCompare(b);
  return dir * (Number(a) - Number(b));
}

/**
 * @param {string} text
 * @param {string} [cls]
 * @returns {HTMLTableCellElement}
 */
function td(text, cls) {
  const el = document.createElement("td");
  el.textContent = text;
  if (cls) el.className = cls;
  return el;
}

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
    },
    window.location.href,
  );
  window.history.replaceState({}, "", url);
}

// Mobile auto-simple guard removed — detailed view is now allowed on
// narrow viewports. The table-wrap's overflow: auto handles horizontal
// scroll for the 13-column detail layout rather than hiding it.

// ───────────────────────── Rendering ───────────────────────────

const ALL_COLUMNS = /** @type {const} */ ([
  "symbol",
  "long_name",
  "sector",
  "forward_pe",
  "trailing_peg_ratio",
  "beta",
  "rd_to_revenue",
  "operating_margins",
  "return_on_equity",
  "return_on_assets",
  "current_ratio",
  "sortino_ratio",
  "composite_scores.screener_score",
]);

/**
 * Annotate a `—`-rendering cell with the structural reason (#170) when
 * one applies. Extracted from `renderTable()` to keep that function's
 * cognitive complexity inside the CodeFactor gate.
 *
 * @param {HTMLElement} cell
 * @param {Row} row
 * @param {string} col
 */
function annotateEmpty(cell, row, col) {
  const reason = explainEmpty(row, col);
  if (!reason) return;
  cell.title = reason;
  cell.setAttribute("data-empty-reason", "1");
}

const COVERAGE_KEYS = /** @type {const} */ ([
  "forward_pe",
  "trailing_peg_ratio",
  "beta",
  "rd_to_revenue",
  "operating_margins",
  "return_on_equity",
  "return_on_assets",
  "current_ratio",
  "sortino_ratio",
]);

/**
 * Count how many of the 9 KPI inputs the row has populated.
 * `forward_pe <= 0` is treated as missing (negative/zero P/E is a
 * sentinel, not a real reading).
 *
 * `row` is typed `any` to match the existing renderTable pipeline,
 * which propagates `any[]` from filteredSnapshot's `fuseIndex.search`
 * branch — keeps the indexed lookup against COVERAGE_KEYS cheap.
 *
 * @param {any} row
 * @returns {number}
 */
function coverageCount(row) {
  let n = 0;
  for (const k of COVERAGE_KEYS) {
    const v = row[k];
    if (v == null) continue;
    if (k === "forward_pe" && v <= 0) continue;
    n += 1;
  }
  return n;
}

/**
 * Hover tooltip for a row: weight % within the visible universe,
 * raw score, and input coverage. Weight + Score are omitted when
 * the row has no composite score.
 *
 * @param {number | null} score
 * @param {number} totalScore
 * @param {number} coverage
 * @returns {string}
 */
function buildRowTitle(score, totalScore, coverage) {
  const parts = [];
  if (score != null && totalScore > 0) {
    const weightPct = ((100 * Number(score)) / totalScore).toFixed(1);
    parts.push(`Weight ${weightPct} %`);
    parts.push(`Score ${Number(score).toFixed(0)}`);
  }
  parts.push(`${coverage}/9 inputs`);
  return parts.join(" · ");
}

/**
 * Build the per-row `<tr>` — score cell heatmap, hover title, the 14
 * cellSpecs entries, KPI coloring, and empty-reason annotation.
 *
 * @param {any} row
 * @param {number} totalScore
 * @returns {HTMLTableRowElement}
 */
function renderRow(row, totalScore) {
  const tr = document.createElement("tr");
  const score = nested(row, "composite_scores.screener_score");
  tr.title = buildRowTitle(score, totalScore, coverageCount(row));
  const scoreCell = td(fmtNum(score, 0), "num score-cell");
  if (score != null) {
    scoreCell.style.backgroundColor = `hsl(${Number(score) * 1.2}, 60%, 75%)`;
  }
  const universeCell = td(
    /** @type {any} */ (row)._universe ?? activeUniverse,
  );
  universeCell.classList.add("universe-col");
  /** @type {Array<[string, HTMLElement, boolean]>} */
  const cellSpecs = [
    ["symbol", td(row.symbol ?? "—"), true],
    ["_universe", universeCell, true],
    ["long_name", td(row.long_name ?? "—"), true],
    ["sector", td(row.sector ?? "—"), true],
    ["forward_pe", td(fmtNum(row.forward_pe, 2), "num"), false],
    ["trailing_peg_ratio", td(fmtNum(row.trailing_peg_ratio, 2), "num"), false],
    ["beta", td(fmtNum(row.beta, 2), "num"), false],
    ["rd_to_revenue", td(fmtPct(row.rd_to_revenue), "num"), false],
    ["operating_margins", td(fmtPct(row.operating_margins), "num"), true],
    ["return_on_equity", td(fmtPct(row.return_on_equity), "num"), false],
    ["return_on_assets", td(fmtPct(row.return_on_assets), "num"), false],
    ["current_ratio", td(fmtNum(row.current_ratio, 2), "num"), false],
    ["sortino_ratio", td(fmtNum(row.sortino_ratio, 2), "num"), false],
    ["composite_scores.screener_score", scoreCell, true],
  ];
  for (const [col, cell, inSimple] of cellSpecs) {
    const value = col === "composite_scores.screener_score" ? score : row[col];
    const klass = cellClass(col, value);
    if (klass) cell.classList.add(klass);
    if (!inSimple) cell.classList.add("detail-only");
    if (value == null) annotateEmpty(cell, row, col);
    tr.appendChild(cell);
  }
  tr.addEventListener("click", () => onRowClick(row));
  return tr;
}

/**
 * Reduce all visible rows' composite scores to a single normalisation
 * denominator for the `buildRowTitle` weight calculation.
 *
 * @param {any[]} rows
 * @returns {number}
 */
function totalCompositeScore(rows) {
  return rows.reduce((acc, row) => {
    const s = nested(row, "composite_scores.screener_score");
    return acc + (s == null ? 0 : Number(s));
  }, 0);
}

function renderTable() {
  const tbody = document.querySelector("#universe-table tbody");
  if (!tbody) return;
  tbody.replaceChildren();
  const visible = filteredSnapshot();
  if (visible.length === 0) {
    const tr = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = ALL_COLUMNS.length;
    cell.className = "empty-state";
    cell.textContent = filterQuery
      ? `no matches for "${filterQuery}"`
      : "no rows in this universe yet — first cron run pending";
    tr.appendChild(cell);
    tbody.appendChild(tr);
    return;
  }
  const sorted = [...visible].sort((a, b) =>
    compareValues(nested(a, state.sortKey), nested(b, state.sortKey), state.sortDir),
  );
  const totalScore = totalCompositeScore(visible);
  for (const row of sorted) {
    tbody.appendChild(renderRow(row, totalScore));
  }
}

function onRowClick(/** @type {Row} */ row) {
  // Both view modes open the side detail panel; the previous
  // "simple-mode opens Yahoo externally" behaviour was jarring (users
  // didn't want to leave the app). Yahoo + SEC EDGAR + Wikipedia links
  // remain accessible inside the panel's `.detail-links` nav.
  showDetail(row);
}

function dl(
  /** @type {Array<[string, string, boolean?, string?]>} */ pairs,
) {
  const frag = document.createDocumentFragment();
  for (const [label, value, sectionHeader, tooltip] of pairs) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    if (sectionHeader) {
      dt.className = "section";
      frag.append(dt);
      continue;
    }
    if (tooltip) {
      dt.title = tooltip;
      dt.tabIndex = 0;
    }
    const dd = document.createElement("dd");
    dd.textContent = value;
    frag.append(dt, dd);
  }
  return frag;
}

/** @type {any} */
let sectorChart = null;
/** @type {any} */
let radarChart = null;


function renderSectorDonut() {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("sector-donut")
  );
  if (!canvas || typeof Chart === "undefined") return;
  const aggregated = aggregateSectors(state.snapshot);
  const labels = [...aggregated.keys()];
  const data = [...aggregated.values()];
  if (sectorChart) {
    liveCharts.delete(sectorChart);
    sectorChart.destroy();
    sectorChart = null;
  }
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
        // Legend permanently disabled — slice colors + hover tooltip
        // (`Sector: count (pct%)`) are enough to identify segments.
        // See https://github.com/qte77/analyze-stock-kpi/issues/152 —
        // the attempted onResize auto-hide regressed on zoom-out and
        // the right-side position required widening the wrap past the
        // user's preferred donut size.
        legend: { display: false },
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

/**
 * Toggle a centered "no data" hint inside #sector-donut-wrap. Called
 * whenever the donut is about to render an empty dataset (e.g. before
 * the first snapshot loads or for a universe whose data branch is
 * missing). Idempotent — safe to call repeatedly with the same flag.
 *
 * @param {boolean} show
 */
function renderDonutEmptyHint(show) {
  const wrap = document.getElementById("sector-donut-wrap");
  if (!wrap) return;
  const existing = wrap.querySelector(".sector-donut-empty");
  if (show && !existing) {
    const hint = document.createElement("div");
    hint.className = "sector-donut-empty";
    hint.textContent = "no history yet";
    wrap.append(hint);
  } else if (!show && existing) {
    existing.remove();
  }
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
  if (radarChart) {
    liveCharts.delete(radarChart);
    radarChart.destroy();
  }
  radarChart = new Chart(canvas, {
    type: "radar",
    data: {
      labels: axes.map((a) => a.replace("screener_score", "screener")),
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

function closeDetail() {
  const aside = document.getElementById("row-detail");
  if (aside) aside.hidden = true;
}

function bindDetailDismiss() {
  const aside = document.getElementById("row-detail");
  if (!aside) return;
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (aside.hidden || !(target instanceof Node)) return;
    if (aside.contains(target)) return;
    const targetElement = target instanceof Element ? target : target.parentElement;
    if (targetElement?.closest("#universe-table tbody tr")) return;
    aside.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !aside.hidden) aside.hidden = true;
  });
}

/**
 * @param {AuditRow | null} audit
 * @returns {Array<[string, string, boolean?, string?]>}
 */
function auditDetailRows(audit) {
  if (!audit) return [];
  return [
    ["Federal Contracts", "", true],
    ["Obligated $", formatObligated(audit.obligated_usd)],
    ["UEI", audit.uei ?? "—"],
    [
      "EDGAR match",
      audit.edgar_match_score == null
        ? "—"
        : `${(Number(audit.edgar_match_score) * 100).toFixed(0)} %`,
      false,
      "SequenceMatcher score of the audit's recipient name against EDGAR's issuer title. Higher = more confident.",
    ],
    ["Recipient name", audit.recipient_name ?? "—"],
  ];
}

/**
 * @param {Row} row
 * @returns {Array<[string, string]>}
 */
function externalLinkRows(row) {
  if (!row.symbol) return [];
  const sym = encodeURIComponent(row.symbol);
  return [
    ["Yahoo", `https://finance.yahoo.com/quote/${sym}`],
    ["SEC EDGAR", `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${sym}`],
    [
      "Wikipedia",
      `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(
        row.long_name ?? row.symbol,
      )}`,
    ],
  ];
}

function showDetail(/** @type {Row} */ row) {
  const cs = row.composite_scores ?? {};
  const mcap = row.market_cap ? `$${(row.market_cap / 1e9).toFixed(2)} B` : "—";
  const audit = row.symbol ? auditByTicker?.get(row.symbol) ?? null : null;

  const aside = document.getElementById("row-detail");
  if (!aside) return;
  aside.replaceChildren();

  const closeBtn = document.createElement("button");
  closeBtn.id = "close-detail";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", closeDetail);
  aside.append(closeBtn);

  const h3 = document.createElement("h3");
  h3.textContent = `${row.symbol ?? "—"} · ${row.long_name ?? ""}`;
  aside.append(h3);

  const tabs = document.createElement("div");
  tabs.className = "detail-tabs";
  const overviewTab = document.createElement("button");
  overviewTab.type = "button";
  overviewTab.textContent = "Overview";
  overviewTab.setAttribute("aria-selected", "true");
  const seriesTab = document.createElement("button");
  seriesTab.type = "button";
  seriesTab.textContent = "Time series";
  seriesTab.setAttribute("aria-selected", "false");
  tabs.append(overviewTab, seriesTab);
  aside.append(tabs);

  const overviewPane = document.createElement("div");
  const seriesPane = document.createElement("div");
  seriesPane.hidden = true;
  aside.append(overviewPane, seriesPane);

  overviewTab.addEventListener("click", () => {
    overviewTab.setAttribute("aria-selected", "true");
    seriesTab.setAttribute("aria-selected", "false");
    overviewPane.hidden = false;
    seriesPane.hidden = true;
  });
  seriesTab.addEventListener("click", () => {
    overviewTab.setAttribute("aria-selected", "false");
    seriesTab.setAttribute("aria-selected", "true");
    overviewPane.hidden = true;
    seriesPane.hidden = false;
    if (seriesPane.childElementCount === 0) {
      void renderTimeSeriesPane(seriesPane, row);
    }
  });

  const radarWrap = document.createElement("div");
  radarWrap.className = "radar-wrap";
  const radarCanvas = document.createElement("canvas");
  radarCanvas.className = "radar-canvas";
  radarWrap.append(radarCanvas);
  overviewPane.append(radarWrap);

  const linkSection = document.createElement("nav");
  linkSection.className = "detail-links";
  for (const [label, href] of externalLinkRows(row)) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    a.target = "_blank";
    a.rel = "noopener";
    linkSection.append(a);
  }
  overviewPane.append(linkSection);

  const trail = row.trailing_pe;
  const fwd = row.forward_pe;
  const trailFwd =
    trail != null && fwd != null && fwd !== 0 ? (trail / fwd).toFixed(2) : "—";

  const list = document.createElement("dl");
  list.append(
    dl([
      ["Sector", row.sector ?? "—"],
      ["Industry", row.industry ?? "—"],
      ["Exchange", `${row.exchange ?? "—"} (${row.currency ?? "—"})`],
      ["Market cap", mcap],
      ["Trail / Fwd P/E", `${fmtNum(row.trailing_pe, 2)} / ${fmtNum(row.forward_pe, 2)}`, false, KPI_GLOSSARY.trailing_pe],
      ["Trail/Fwd P/E ratio", trailFwd, false, KPI_GLOSSARY.trail_fwd_pe],
      ["P/B / P/S TTM", `${fmtNum(row.price_to_book, 2)} / ${fmtNum(row.price_to_sales_ttm, 2)}`],
      ["Gross margin %", fmtPct(row.gross_margins), false, KPI_GLOSSARY.gross_margins],
      ["Net margin %", fmtPct(row.profit_margins), false, KPI_GLOSSARY.profit_margins],
      ["ROE / ROA", `${fmtPct(row.return_on_equity)} % / ${fmtPct(row.return_on_assets)} %`, false, KPI_GLOSSARY.return_on_equity],
      ["ROI", fmtPct(row.roi), false, KPI_GLOSSARY.roi],
      ["R&D / Revenue %", fmtPct(row.rd_to_revenue), false, KPI_GLOSSARY.rd_to_revenue],
      ["Op margin %", fmtPct(row.operating_margins), false, KPI_GLOSSARY.operating_margins],
      ["D/E", fmtNum(row.debt_to_equity, 2), false, KPI_GLOSSARY.debt_to_equity],
      ["Current ratio", fmtNum(row.current_ratio, 2), false, KPI_GLOSSARY.current_ratio],
      ["Quick ratio", fmtNum(row.quick_ratio, 2), false, KPI_GLOSSARY.quick_ratio],
      ["Revenue growth", `${fmtPct(row.revenue_growth)} %`],
      ["Earnings growth", `${fmtPct(row.earnings_growth)} %`],
      ["Div yield / Payout", `${fmtPct(row.dividend_yield)} % / ${fmtPct(row.payout_ratio)} %`],
      ["52w high / low", `$${fmtNum(row.fifty_two_week_high, 2)} / $${fmtNum(row.fifty_two_week_low, 2)}`],
      ["Beta", fmtNum(row.beta, 2), false, KPI_GLOSSARY.beta],
      ["PEG (trailing)", fmtNum(row.trailing_peg_ratio, 2), false, KPI_GLOSSARY.trailing_peg_ratio],
      ["Sortino (1y, rf=0)", fmtNum(row.sortino_ratio, 2), false, KPI_GLOSSARY.sortino_ratio],
      ["Composite scores", "", true],
      ["Quality", fmtNum(cs.quality, 0), false, KPI_GLOSSARY.quality],
      ["Dividend", fmtNum(cs.dividend, 0), false, KPI_GLOSSARY.dividend],
      ["Growth", fmtNum(cs.growth, 0), false, KPI_GLOSSARY.growth],
      ["Big Call", fmtNum(cs.big_call, 0), false, KPI_GLOSSARY.big_call],
      ["AAQS", fmtNum(cs.aaqs, 0), false, KPI_GLOSSARY.aaqs],
      ["HGI", fmtNum(cs.hgi, 0), false, KPI_GLOSSARY.hgi],
      ["Screener", fmtNum(cs.screener_score, 0), false, KPI_GLOSSARY.screener_score],
      ...auditDetailRows(audit),
    ]),
  );
  overviewPane.append(list);
  aside.hidden = false;
  renderRadar(radarCanvas, cs);
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
  if (timeSeriesChart) {
    liveCharts.delete(timeSeriesChart);
    timeSeriesChart.destroy();
  }
  timeSeriesChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: series.dates,
      datasets: [
        { label: "Screener", data: series.score, borderColor: () => cssVar("--accent", "#0066cc") },
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
          min: 0,
          max: 100,
          ticks: { stepSize: 25, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
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

function findClosestScore(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
  /** @type {number} */ latestMs,
  /** @type {number} */ daysAgo,
) {
  const target = latestMs - daysAgo * 86400000;
  /** @type {{timestamp: string, score: number} | null} */
  let best = null;
  let bestDiff = Number.POSITIVE_INFINITY;
  for (const e of entries) {
    const diff = Math.abs(new Date(e.timestamp).getTime() - target);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = e;
    }
  }
  return best?.score;
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

function renderRollingEmptyHint(
  /** @type {boolean} */ show,
  /** @type {string} */ text = "no history yet",
) {
  const wrap = document.getElementById("fg-chart-wrap");
  if (!wrap) return;
  let hint = wrap.querySelector(".fg-empty");
  if (show) {
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "fg-empty";
      wrap.append(hint);
    }
    hint.textContent = text;
  } else if (hint) {
    hint.remove();
  }
}

function renderFearGreedChart(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
) {
  const ctx = /** @type {HTMLCanvasElement | null} */ (document.getElementById("fg-chart"));
  if (!ctx) return;
  if (fearGreedChart) {
    liveCharts.delete(fearGreedChart);
    fearGreedChart.destroy();
    fearGreedChart = null;
  }
  renderRollingEmptyHint(entries.length === 0);
  if (!entries.length || typeof Chart === "undefined") return;
  fearGreedChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: entries.map((e) => e.timestamp.slice(0, 10)),
      datasets: [
        {
          data: entries.map((e) => e.score),
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
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { stepSize: 25, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
        },
        x: {
          ticks: { maxTicksLimit: 14, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
        },
      },
    },
  });
  liveCharts.add(fearGreedChart);
}

function renderLongTermEmptyHint(/** @type {boolean} */ show) {
  const wrap = document.getElementById("lt-fg-chart-wrap");
  if (!wrap) return;
  const existing = wrap.querySelector(".lt-fg-empty");
  if (show && !existing) {
    const hint = document.createElement("div");
    hint.className = "lt-fg-empty";
    hint.textContent = "no history yet";
    wrap.append(hint);
  } else if (!show && existing) {
    existing.remove();
  }
}

function renderMonthlyFearGreedChart(
  /** @type {Array<{timestamp: string, score: number}>} */ entries,
) {
  const canvas = /** @type {HTMLCanvasElement | null} */ (
    document.getElementById("lt-fg-chart")
  );
  if (!canvas) return;
  const monthly = aggregateMonthlyFG(entries);
  if (monthlyFearGreedChart) {
    liveCharts.delete(monthlyFearGreedChart);
    monthlyFearGreedChart.destroy();
    monthlyFearGreedChart = null;
  }
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
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { stepSize: 25, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
        },
        x: {
          ticks: { maxTicksLimit: 14, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
        },
      },
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
 * lazy pattern so initial paint stays cheap.
 *
 * @param {Array<{timestamp: string, score: number}>} fgEntries
 * @param {Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>} ycEntries
 */
function bindLongTermTabs(fgEntries, ycEntries) {
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
  let monthlyRendered = false;
  let yieldCurveRendered = false;
  for (const [tab, pane] of resolved) {
    tab.addEventListener("click", () => {
      for (const [t, p] of resolved) {
        const selected = t === tab;
        t.setAttribute("aria-selected", selected ? "true" : "false");
        p.hidden = !selected;
      }
      if (pane.id === "lt-fg-chart-wrap" && !monthlyRendered) {
        renderMonthlyFearGreedChart(fgEntries);
        monthlyRendered = true;
      }
      if (pane.id === "yc-chart-wrap" && !yieldCurveRendered) {
        renderYieldCurveChart(ycEntries);
        yieldCurveRendered = true;
      }
    });
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
      existing.textContent = "no history yet";
    } else {
      const hint = document.createElement("div");
      hint.className = "yc-empty";
      hint.textContent = "no history yet";
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
  if (yieldCurveChart) {
    liveCharts.delete(yieldCurveChart);
    yieldCurveChart.destroy();
    yieldCurveChart = null;
  }
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
        x: {
          ticks: { maxTicksLimit: 14, color: () => cssVar("--text", "#1d1d1f") },
          grid: { color: () => cssVar("--border", "#d2d2d7") },
        },
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
    sizeEl.textContent = "· no history yet";
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
  bindThemeObserver();
}

document.addEventListener("DOMContentLoaded", init);
