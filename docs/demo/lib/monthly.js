// @ts-check
// Monthly aggregation of CNN Fear & Greed daily entries for the
// long-term-context section of the demo dashboard. Pure — takes the
// same `{timestamp, score}[]` list already fetched by `loadFearGreedYears`
// in app.js and returns parallel arrays of YYYY-MM bucket / median / avg
// / count, sorted ascending. The Chart.js render lives in app.js.
//
// UTC bucketing: `timestamp` is treated as ISO-8601 and reduced to its
// UTC `YYYY-MM` prefix. A 23:59 UTC entry on the last of a month stays
// in that month regardless of the viewer's local timezone — matches the
// CNN payload's own UTC framing and keeps the dashboard's display stable
// across timezones.

/**
 * @typedef {object} FGEntry
 * @property {string} timestamp  ISO-8601; entries with unparseable timestamps are skipped.
 * @property {number} score      0-100.
 */

/**
 * @typedef {object} MonthlyFG
 * @property {string[]} months   YYYY-MM, ascending.
 * @property {number[]} median   Per-month median of `score`.
 * @property {number[]} avg      Per-month mean of `score`.
 * @property {number[]} count    Per-month entry count.
 */

/**
 * @param {number[]} sorted  Ascending.
 * @returns {number}
 */
function median(sorted) {
  const n = sorted.length;
  const mid = Math.floor(n / 2);
  return n % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * @param {FGEntry[]} entries
 * @returns {MonthlyFG}
 */
export function aggregateMonthlyFG(entries) {
  /** @type {Map<string, number[]>} */
  const buckets = new Map();
  for (const { timestamp, score } of entries) {
    const d = new Date(timestamp);
    if (Number.isNaN(d.getTime())) continue;
    const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    const bucket = buckets.get(key);
    if (bucket) bucket.push(score);
    else buckets.set(key, [score]);
  }
  const months = [...buckets.keys()].sort();
  /** @type {MonthlyFG} */
  const out = { months, median: [], avg: [], count: [] };
  for (const m of months) {
    const scores = /** @type {number[]} */ (buckets.get(m)).slice().sort((a, b) => a - b);
    out.median.push(median(scores));
    out.avg.push(scores.reduce((s, v) => s + v, 0) / scores.length);
    out.count.push(scores.length);
  }
  return out;
}
