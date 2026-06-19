// @ts-check
// Weekly aggregation of a daily numeric time-series for the long-term-
// context section of the demo dashboard. Pure — mirrors ui/lib/monthly.js
// but buckets to ISO weeks and aggregates an arbitrary numeric field, so
// the 5s10s yield-curve slope (and any similar daily series) can be
// de-noised on the wide windows the same way the CNN F&G long-term view
// aggregates daily headline scores to months. The Chart.js render lives in
// ui/charts.js.
//
// UTC / ISO-8601 week bucketing: each entry's date is reduced to its ISO
// week (Thursday-anchored, ISO-8601). Weeks are keyed `YYYY-Www` where
// `YYYY` is the ISO *week-year* — which differs from the calendar year at
// the Dec/Jan boundary (e.g. 2021-01-01 → 2020-W53). Zero-padded week
// numbers make the keys sort chronologically as plain strings. UTC framing
// keeps the buckets stable across the viewer's timezone, matching monthly.js.

/**
 * @typedef {object} WeeklyAgg
 * @property {string[]} weeks  ISO `YYYY-Www`, ascending.
 * @property {number[]} mean   Per-week mean of the aggregated value.
 * @property {number[]} count  Per-week entry count.
 */

/**
 * ISO-8601 week key (`YYYY-Www`) for a date, computed in UTC.
 * @param {Date} d
 * @returns {string}
 */
function isoWeekKey(d) {
  // The Thursday of the entry's week fixes both the ISO week-year and number.
  const thursday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dayNum = (thursday.getUTCDay() + 6) % 7; // Mon=0 … Sun=6
  thursday.setUTCDate(thursday.getUTCDate() - dayNum + 3);
  const isoYear = thursday.getUTCFullYear();
  // Week 1 is the week containing the first Thursday of the ISO year.
  const firstThursday = new Date(Date.UTC(isoYear, 0, 4));
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);
  const week = 1 + Math.round((thursday.getTime() - firstThursday.getTime()) / (7 * 86400000));
  return `${isoYear}-W${String(week).padStart(2, "0")}`;
}

/**
 * Bucket daily `entries` into ISO weeks and return parallel arrays of week
 * key / mean / count, sorted ascending by week. Entries whose date is
 * unparseable or whose aggregated value is non-numeric are skipped. Input
 * order does not matter.
 *
 * @template {Record<string, unknown>} T
 * @param {T[]} entries
 * @param {{ dateKey?: string, valueKey?: string }} [opts]
 * @returns {WeeklyAgg}
 */
export function aggregateWeekly(entries, opts = {}) {
  const dateKey = opts.dateKey ?? "date";
  const valueKey = opts.valueKey ?? "slope_5s10s";
  /** @type {Map<string, number[]>} */
  const buckets = new Map();
  for (const entry of entries) {
    const value = entry[valueKey];
    if (typeof value !== "number" || Number.isNaN(value)) continue;
    const d = new Date(/** @type {string} */ (entry[dateKey]));
    if (Number.isNaN(d.getTime())) continue;
    const key = isoWeekKey(d);
    const bucket = buckets.get(key);
    if (bucket) bucket.push(value);
    else buckets.set(key, [value]);
  }
  const weeks = [...buckets.keys()].sort();
  /** @type {WeeklyAgg} */
  const out = { weeks, mean: [], count: [] };
  for (const w of weeks) {
    const values = /** @type {number[]} */ (buckets.get(w));
    out.mean.push(values.reduce((s, v) => s + v, 0) / values.length);
    out.count.push(values.length);
  }
  return out;
}
