// @ts-check
/* global Fuse */
// Demo dashboard glue (#59, #134).
//
// Imports pure-JS units from ./lib/* (DOM-free, unit-tested); this file
// stays as the DOM glue. Switched to an ES module entry so the lib/
// imports resolve at runtime; vendor scripts (Chart.js, Fuse.js) still
// attach via the classic <script> tag.

import { buildAuditMap, loadAudit } from "./lib/audit.js";
import { exportCsv } from "./lib/csv.js";
import { fetchJson, loadYearsFromBranch } from "./lib/fetch.js";
import { nested } from "./lib/format.js";
import { mergeUniverseSnapshots } from "./lib/overlay.js";
import { parseState, resolveViewMode, serializeState } from "./lib/state.js";
import { resolveTheme, nextTheme } from "./lib/theme.js";
import { bindDetailDismiss, showDetail } from "./detail_panel.js";
import { ALL_COLUMNS, renderUniverseTable } from "./table.js";
import {
  initCharts,
  renderSectorDonut,
  renderRadar,
  renderTimeSeriesPane,
  renderFearGreedHeader,
  renderFearGreedChart,
  renderYieldCurveHeader,
  bindLongTermTabs,
  bindWindowChips,
  bindThemeObserver,
  EMPTY_HISTORY,
} from "./charts.js";

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
  fear: "rating-fear",
  neutral: "rating-neutral",
  greed: "rating-greed",
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

/** @type {{dates: string[], latest: string} | null} */
let manifestCache = null;

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

const loadManifest = () => fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/index.json`);

const snapshotUrl = (/** @type {string} */ universe, /** @type {string} */ date) =>
  `${DATA_BASE_URL}/results/demo/${universe}/${date}.json`;

const loadSnapshot = (/** @type {string} */ date) => fetchJson(snapshotUrl(activeUniverse, date));

const loadUniverses = () => fetchJson("universes.json");

/** @type {() => Promise<Array<{timestamp: string, score: number, rating?: string}>>} */
const loadFearGreedYears = () =>
  loadYearsFromBranch(DATA_BASE_URL, "results/series/cnn_fg", "timestamp");

/** @type {() => Promise<Array<{date: string, tnx_yield: number | null, fvx_yield: number | null, slope_5s10s: number | null}>>} */
const loadYieldCurveYears = () =>
  loadYearsFromBranch(DATA_BASE_URL, "results/series/yield_curve", "date");

/** @type {() => Promise<Array<{date: string, ret_indexed: number}>>} */
const loadEquitySpyYears = () =>
  loadYearsFromBranch(DATA_BASE_URL, "results/series/equity_spy", "date");

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
      desc.textContent = viewMode === "simple" ? "Show all KPI columns" : "Show essentials only";
    }
  }
}

/** @type {"system" | "light" | "dark"} */
let activeTheme = "system";

/** Icon + word shown on the cycler button per mode. */
const THEME_LABELS = {
  system: { icon: "⏿", word: "System" },
  light: { icon: "☀", word: "Light" },
  dark: { icon: "🌙", word: "Dark" },
};

/**
 * Apply the active theme to `<body>` and sync the cycler button's label
 * + accessible name. The three theme-* classes are mutually exclusive
 * (only one is set at any time); CSS picks the right palette via
 * `body.theme-dark` (forced) or `body.theme-system` + media query.
 * Idempotent — safe to call on load without announcing (the
 * `#theme-status` live region is written only on user-driven changes).
 */
function applyTheme() {
  const body = document.body;
  body.classList.toggle("theme-system", activeTheme === "system");
  body.classList.toggle("theme-light", activeTheme === "light");
  body.classList.toggle("theme-dark", activeTheme === "dark");
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const { icon, word } = THEME_LABELS[activeTheme];
  btn.textContent = `${icon} ${word}`;
  btn.setAttribute("aria-label", `Theme: ${word} (activate to change)`);
  btn.title = `Theme: ${word}`;
}

function persistStateFromCurrent() {
  const universes = activeUniverse ? [activeUniverse, ...extraUniverses] : [];
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
      rows.map((/** @type {Row} */ r) => Object.fromEntries(headers.map((h) => [h, nested(r, h)]))),
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
async function fetchUniverseSnapshot(/** @type {string} */ universe, /** @type {string} */ date) {
  try {
    return /** @type {Row[]} */ (await fetchJson(snapshotUrl(universe, date)));
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
  state.snapshot = extraUniverses.length === 0 ? primary : mergeUniverseSnapshots(byUniverse);
  document.body.classList.toggle("overlay-active", extraUniverses.length >= 1);

  const auditMap = await loadAudit(activeUniverse, manifest.latest, DATA_BASE_URL, fetchJson);
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
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    activeTheme = nextTheme(activeTheme);
    applyTheme();
    // Announce the new mode for screen readers (the "aria-glance"):
    // focus stays on the button, so the changed label alone wouldn't
    // be re-read — the polite live region carries the update.
    const status = document.getElementById("theme-status");
    if (status) status.textContent = `Theme set to ${THEME_LABELS[activeTheme].word}`;
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
    // Independent reads — fetch the snapshot + its audit concurrently.
    const [snapshot, auditMap] = await Promise.all([
      loadSnapshot(newDate),
      loadAudit(activeUniverse, newDate, DATA_BASE_URL, fetchJson),
    ]);
    state.snapshot = snapshot;
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

const chartCtx = {
  get snapshot() {
    return state.snapshot;
  },
  get activeUniverse() {
    return activeUniverse;
  },
  dataBaseUrl: DATA_BASE_URL,
  ratingClasses: RATING_CLASSES,
  get manifest() {
    return manifestCache;
  },
  get sectorFilter() {
    return sectorFilter;
  },
  set sectorFilter(v) {
    sectorFilter = v;
  },
  get ltFgWindow() {
    return activeLtFgWindow;
  },
  set ltFgWindow(v) {
    activeLtFgWindow = v;
  },
  get ycWindow() {
    return activeYcWindow;
  },
  set ycWindow(v) {
    activeYcWindow = v;
  },
  afterSectorToggle() {
    renderTable();
    persistStateFromCurrent();
  },
  afterWindowChange() {
    persistStateFromCurrent();
  },
};

async function init() {
  initCharts(chartCtx);
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
      : (universes[0]?.id ?? "qte77-watchlist");
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

  const [fgEntries, ycEntries, spyEntries] = await Promise.all([
    loadFearGreedYears(),
    loadYieldCurveYears(),
    loadEquitySpyYears(),
  ]);
  renderFearGreedHeader(fgEntries);
  renderFearGreedChart(fgEntries);
  renderYieldCurveHeader(ycEntries);
  bindLongTermTabs(fgEntries, ycEntries, spyEntries);
  bindWindowChips();
  bindThemeObserver();
}

document.addEventListener("DOMContentLoaded", init);
