// @ts-check
// Pure data layer for the merged long-term-context chart (#288). Reconciles the
// CNN F&G (monthly median), the 5s10s slope (monthly mean, normalized to 0-100),
// and the SPY indexed return (monthly last, plotted on a log axis) onto one
// monthly grid so a single Chart.js chart can show all three. DOM-free; the
// render lives in ui/charts.js. Tested by ui/tests/combined.test.mjs.

import { aggregateMonthlyFG } from "./monthly.js";

/**
 * Linearly map a 5s10s slope (percentage points) onto 0-100, clamped to the
 * band [lo, hi] so it can share the F&G 0-100 score axis.
 * @param {number} value
 * @param {number} lo
 * @param {number} hi
 * @returns {number}
 */
export function normalizeSlope(value, lo, hi) {
  const pct = ((value - lo) / (hi - lo)) * 100;
  return Math.max(0, Math.min(100, pct));
}

/**
 * @typedef {object} MonthlyAgg
 * @property {string[]} months  YYYY-MM, ascending.
 * @property {number[]} values  One value per month (mean or last).
 */

/**
 * Bucket daily entries into UTC months and reduce each month to one value.
 * Entries with a non-numeric value or unparseable date are skipped.
 * @param {Array<Record<string, unknown>>} entries
 * @param {{ dateKey: string, valueKey: string, reduce: "mean" | "last" }} opts
 * @returns {MonthlyAgg}
 */
export function aggregateMonthly(entries, opts) {
  const { dateKey, valueKey, reduce } = opts;
  /** @type {Map<string, { sum: number, n: number, lastMs: number, last: number }>} */
  const buckets = new Map();
  for (const entry of entries) {
    const value = entry[valueKey];
    if (typeof value !== "number" || Number.isNaN(value)) continue;
    const ms = new Date(/** @type {string} */ (entry[dateKey])).getTime();
    if (Number.isNaN(ms)) continue;
    const d = new Date(ms);
    const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    const b = buckets.get(key);
    if (b) {
      b.sum += value;
      b.n += 1;
      if (ms >= b.lastMs) {
        b.lastMs = ms;
        b.last = value;
      }
    } else {
      buckets.set(key, { sum: value, n: 1, lastMs: ms, last: value });
    }
  }
  const months = [...buckets.keys()].sort();
  const values = months.map((m) => {
    const b = /** @type {{ sum: number, n: number, last: number }} */ (buckets.get(m));
    return reduce === "last" ? b.last : b.sum / b.n;
  });
  return { months, values };
}

/**
 * @typedef {object} CombinedSeries
 * @property {string[]} labels                 Union of months, ascending.
 * @property {Array<number|null>} fgMedian     F&G monthly median (0-100).
 * @property {Array<number|null>} slopeNorm    5s10s monthly mean, normalized 0-100.
 * @property {Array<number|null>} spyIndexed   SPY monthly-last indexed return.
 */

/**
 * Reconcile the three long-term series onto one monthly grid (the union of
 * their months), each aligned with `null` in the months it doesn't cover.
 * @param {Array<{timestamp: string, score: number}>} fgEntries
 * @param {Array<{date: string, slope_5s10s: number|null}>} ycEntries
 * @param {Array<{date: string, ret_indexed: number}>} spyEntries
 * @param {{ slopeLo: number, slopeHi: number }} opts
 * @returns {CombinedSeries}
 */
export function buildCombinedSeries(fgEntries, ycEntries, spyEntries, opts) {
  const fg = aggregateMonthlyFG(fgEntries);
  const fgMap = new Map(fg.months.map((m, i) => [m, fg.median[i]]));
  const yc = aggregateMonthly(/** @type {Array<Record<string, unknown>>} */ (ycEntries), {
    dateKey: "date",
    valueKey: "slope_5s10s",
    reduce: "mean",
  });
  const ycMap = new Map(yc.months.map((m, i) => [m, yc.values[i]]));
  const spy = aggregateMonthly(/** @type {Array<Record<string, unknown>>} */ (spyEntries), {
    dateKey: "date",
    valueKey: "ret_indexed",
    reduce: "last",
  });
  const spyMap = new Map(spy.months.map((m, i) => [m, spy.values[i]]));

  const labels = [...new Set([...fgMap.keys(), ...ycMap.keys(), ...spyMap.keys()])].sort();
  /** @param {Map<string, number>} map @returns {Array<number|null>} */
  const align = (map) =>
    labels.map((m) => (map.has(m) ? /** @type {number} */ (map.get(m)) : null));
  return {
    labels,
    fgMedian: align(fgMap),
    slopeNorm: labels.map((m) =>
      ycMap.has(m)
        ? normalizeSlope(/** @type {number} */ (ycMap.get(m)), opts.slopeLo, opts.slopeHi)
        : null,
    ),
    spyIndexed: align(spyMap),
  };
}
