// @ts-check
// Universe-table rendering for the demo dashboard. DOM-coupled glue split
// out of app.js (#…) to shrink the entry file; the pure row helpers
// (buildRowTitle, coverageCount, totalCompositeScore, emptyTableMessage)
// are exported for unit testing. Module-level state (active universe,
// sort, filter, row-click handler) is passed in by the caller rather than
// read from globals, so this file stays free of app.js mutable state.
// Tested by tests/demo/table.test.mjs.

import { cellClass } from "./lib/coloring.js";
import { explainEmpty } from "./lib/empty_reason.js";
import { compareValues, fmtNum, fmtPct, nested } from "./lib/format.js";

const SCORE_KEY = "composite_scores.screener_score";

export const ALL_COLUMNS = /** @type {const} */ ([
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

/**
 * Annotate a `—`-rendering cell with the structural reason (#170) when
 * one applies.
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

/**
 * The "qte77 Score" a row displays and is ranked by, everywhere in the
 * dashboard — `composite_scores.screener_score`. Aggregator universes
 * (`aggregated-scores-best` / `-worst`) used to rank by the mean of all 7
 * composites while this column kept showing `screener_score`, so a
 * ticker's displayed score could disagree with the metric that actually
 * placed it in best-25/worst-25. The aggregator now ranks by
 * `screener_score` too (see `aggregated_scores_best_and_worst.py`), so
 * one value is correct on every universe.
 *
 * @param {any} row
 * @returns {number | null}
 */
export function effectiveScore(row) {
  return nested(row, SCORE_KEY);
}

/**
 * Count how many of the 9 KPI inputs the row has populated.
 * `forward_pe <= 0` is treated as missing (negative/zero P/E is a
 * sentinel, not a real reading).
 *
 * @param {any} row
 * @returns {number}
 */
export function coverageCount(row) {
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
export function buildRowTitle(score, totalScore, coverage) {
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
 * @param {string} activeUniverse
 * @param {(row: any) => void} onRowClick
 * @returns {HTMLTableRowElement}
 */
function renderRow(row, totalScore, activeUniverse, onRowClick) {
  const tr = document.createElement("tr");
  const score = effectiveScore(row);
  tr.title = buildRowTitle(score, totalScore, coverageCount(row));
  const scoreCell = td(fmtNum(score, 0), "num score-cell");
  if (score != null) {
    const s = Math.max(0, Math.min(100, Number(score)));
    scoreCell.style.backgroundColor =
      s <= 50
        ? `color-mix(in oklab, var(--score-lo), var(--score-mid) ${s * 2}%)`
        : `color-mix(in oklab, var(--score-mid), var(--score-hi) ${(s - 50) * 2}%)`;
  }
  const universeCell = td(/** @type {any} */ (row)._universe ?? activeUniverse);
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
    ["operating_margins", td(fmtPct(row.operating_margins), "num"), false],
    ["return_on_equity", td(fmtPct(row.return_on_equity), "num"), false],
    ["return_on_assets", td(fmtPct(row.return_on_assets), "num"), false],
    ["current_ratio", td(fmtNum(row.current_ratio, 2), "num"), false],
    ["sortino_ratio", td(fmtNum(row.sortino_ratio, 2), "num"), false],
    [SCORE_KEY, scoreCell, true],
  ];
  for (const [col, cell, inSimple] of cellSpecs) {
    const value = col === SCORE_KEY ? score : row[col];
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
 * Reduce all visible rows' qte77 Scores (see {@link effectiveScore}) to a
 * single normalisation denominator for the `buildRowTitle` weight
 * calculation.
 *
 * @param {any[]} rows
 * @returns {number}
 */
export function totalCompositeScore(rows) {
  return rows.reduce((acc, row) => {
    const s = effectiveScore(row);
    return acc + (s == null ? 0 : Number(s));
  }, 0);
}

/**
 * Empty-state message for the table body. Orchestrator-driven universes
 * (aggregator / longshort) can legitimately produce zero rows when the
 * ranking / conjunctive-gate returns an empty set — distinguish that
 * from a static universe whose cron hasn't run yet so the message reads
 * as a design outcome rather than an infrastructure bug.
 *
 * @param {string} filterQuery
 * @param {string} activeUniverse
 * @returns {string}
 */
export function emptyTableMessage(filterQuery, activeUniverse) {
  if (filterQuery) return `no matches for "${filterQuery}"`;
  if (activeUniverse.startsWith("enhanced-kpi-screener-")) {
    return "0 candidates — the conjunctive 14-criteria gate matched no tickers in this snapshot.";
  }
  if (activeUniverse.startsWith("aggregated-scores-")) {
    return "0 eligible tickers — the aggregator's freshness gate excluded every candidate this run, or none had a qte77 Score.";
  }
  return "no rows in this universe yet — first cron run pending";
}

/**
 * Render the universe table into `#universe-table tbody` from a
 * pre-filtered row list. The caller owns filtering (fuzzy search + sector)
 * and passes the sort + universe + click context via `opts`.
 *
 * @param {any[]} rows  pre-filtered visible rows
 * @param {{
 *   sortKey: string,
 *   sortDir: 1 | -1,
 *   activeUniverse: string,
 *   filterQuery: string,
 *   onRowClick: (row: any) => void,
 * }} opts
 */
export function renderUniverseTable(rows, opts) {
  const tbody = document.querySelector("#universe-table tbody");
  if (!tbody) return;
  tbody.replaceChildren();
  if (rows.length === 0) {
    const tr = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = ALL_COLUMNS.length;
    cell.className = "empty-state";
    cell.textContent = emptyTableMessage(opts.filterQuery, opts.activeUniverse);
    tr.appendChild(cell);
    tbody.appendChild(tr);
    return;
  }
  const sortValue = (/** @type {any} */ row) => nested(row, opts.sortKey);
  const sorted = [...rows].sort((a, b) => compareValues(sortValue(a), sortValue(b), opts.sortDir));
  const totalScore = totalCompositeScore(rows);
  for (const row of sorted) {
    tbody.appendChild(renderRow(row, totalScore, opts.activeUniverse, opts.onRowClick));
  }
}
