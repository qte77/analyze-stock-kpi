// @ts-check
// A1 conditional cell coloring — KPI-aware threshold map + class
// resolver. Used by renderTable() in app.js to attach `kpi-good` /
// `kpi-neutral` / `kpi-bad` classes to numeric cells alongside the
// existing Score-column HSL heatmap.
// Tested by tests/demo/coloring.test.mjs.

/**
 * @typedef {object} Threshold
 * @property {boolean} lowerBetter
 *   `true` when smaller values are healthier (P/E, beta, debt).
 * @property {number} good
 *   Boundary into the "good" band. For lowerBetter the band is
 *   `[-Inf, good)`; otherwise `[good, +Inf)`. Inclusive on the
 *   lower-better-bad side / upper-good side.
 * @property {number} bad
 *   Boundary into the "bad" band. For lowerBetter the band is
 *   `[bad, +Inf)`; otherwise `[-Inf, bad)`.
 */

/** @type {Record<string, Threshold>} */
const THRESHOLDS = {
  forward_pe: { lowerBetter: true, good: 20, bad: 30 },
  trailing_peg_ratio: { lowerBetter: true, good: 1, bad: 2 },
  beta: { lowerBetter: true, good: 1, bad: 1.5 },
  rd_to_revenue: { lowerBetter: false, good: 0.08, bad: 0.03 },
  operating_margins: { lowerBetter: false, good: 0.2, bad: 0.1 },
  return_on_equity: { lowerBetter: false, good: 0.15, bad: 0.05 },
  return_on_assets: { lowerBetter: false, good: 0.08, bad: 0.03 },
  current_ratio: { lowerBetter: false, good: 1.5, bad: 1 },
  sortino_ratio: { lowerBetter: false, good: 1, bad: 0.5 },
  "composite_scores.screener_score": { lowerBetter: false, good: 70, bad: 30 },
};

/**
 * Resolve the CSS class for one (column, value) pair. Returns `null`
 * when there is no threshold for the column or the value isn't a
 * finite number.
 *
 * @param {string} col
 * @param {unknown} value
 * @returns {"kpi-good" | "kpi-neutral" | "kpi-bad" | null}
 */
export function cellClass(col, value) {
  if (value == null) return null;
  const t = THRESHOLDS[col];
  if (!t) return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  if (t.lowerBetter) {
    if (n < t.good) return "kpi-good";
    if (n < t.bad) return "kpi-neutral";
    return "kpi-bad";
  }
  if (n >= t.good) return "kpi-good";
  if (n >= t.bad) return "kpi-neutral";
  return "kpi-bad";
}
