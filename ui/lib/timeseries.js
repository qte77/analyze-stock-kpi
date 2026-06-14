// @ts-check
// Per-ticker time-series builder for the detail-panel time-series tab
// (C3 of #137). Pure — takes a list of dated snapshots + a ticker,
// returns parallel arrays of dates + 4 KPI series. The DOM-side
// Chart.js multi-line render lives in app.js. Tested by
// tests/demo/timeseries.test.mjs.
//
// Pre-#136 backfill the input list has a single entry (today's snapshot)
// so the series is a single point per axis. Once the monthly grid lands
// the same code consumes a 17-point series with no migration.

/**
 * @typedef {object} DatedSnapshot
 * @property {string} date  ISO yyyy-mm-dd; entries with empty `date` are skipped.
 * @property {Row[] | null | undefined} rows
 */

/**
 * @typedef {object} TimeSeries
 * @property {string[]} dates
 * @property {Array<number | null>} score
 * @property {Array<number | null>} quality
 * @property {Array<number | null>} growth
 * @property {Array<number | null>} sortino
 */

/**
 * @param {unknown} value
 * @returns {number | null}
 */
function num(value) {
  return value == null ? null : Number(value);
}

/**
 * @param {DatedSnapshot[]} snapshotsByDate
 * @param {string} symbol  Case-sensitive match against `row.symbol`.
 * @returns {TimeSeries}
 */
export function buildTimeSeries(snapshotsByDate, symbol) {
  /** @type {TimeSeries} */
  const series = { dates: [], score: [], quality: [], growth: [], sortino: [] };
  for (const { date, rows } of snapshotsByDate) {
    if (!date) continue;
    const row = Array.isArray(rows) ? rows.find((r) => r.symbol === symbol) : undefined;
    const cs = row?.composite_scores ?? {};
    series.dates.push(date);
    series.score.push(num(cs.screener_score));
    series.quality.push(num(cs.quality));
    series.growth.push(num(cs.growth));
    series.sortino.push(num(row?.sortino_ratio));
  }
  return series;
}
