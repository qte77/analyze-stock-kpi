// @ts-check
// Pure helpers for the point-in-time backtested long/short 25/25 dashboard
// section (ADR-0013, plan 008). `compound` turns one cadence's daily return
// rows (`results/series/backtest/<cadence>/YYYY.json`) into a 100-based
// index line client-side — no stored NAV (D5/D8). `metricsTableRows` and
// `keyFacts` project `results/backtest/summary.json` into the shapes the
// metrics table and key-facts line render. DOM rendering lives in
// ui/charts.js.

/**
 * @typedef {object} BacktestReturnRow
 * @property {string} date
 * @property {number} [ret_long]
 * @property {number} [ret_short]
 * @property {number} [ret_ls_gross]
 * @property {number} [ret_ls_net]
 * @property {number} [turnover]
 */

/**
 * Compound a date-sorted return series into a 100-based index line.
 * `index[0] = 100 * (1 + row[0][field])`; each subsequent point multiplies
 * the running level by `(1 + row[i][field])`. Rows with a non-numeric
 * `field` value are skipped — the running level carries forward unchanged
 * — rather than aborting the whole line.
 *
 * @param {BacktestReturnRow[]} rows  ascending by date.
 * @param {"ret_long" | "ret_short" | "ret_ls_gross" | "ret_ls_net"} [field]
 * @returns {{dates: string[], index: number[]}}
 */
export function compound(rows, field = "ret_ls_net") {
  const dates = [];
  const index = [];
  let level = 100;
  for (const row of rows) {
    const ret = row[field];
    if (typeof ret === "number" && Number.isFinite(ret)) {
      level *= 1 + ret;
    }
    dates.push(row.date);
    index.push(level);
  }
  return { dates, index };
}

/**
 * Cadence display order (D7). `monthly` is the primary cadence in practice,
 * but "primary" is always read from `summary.primary` rather than assumed
 * here, so the table/chart follow the data rather than a hardcoded key.
 */
export const CADENCE_ORDER = [
  "monthly",
  "quarterly_filings",
  "monthly_buffer",
  "weekly",
  "buy_hold",
];

/** @type {Record<string, string>} */
export const CADENCE_LABELS = {
  monthly: "Monthly",
  quarterly_filings: "Quarterly (after filings)",
  monthly_buffer: "Monthly + buffer",
  weekly: "Weekly",
  buy_hold: "Buy & hold",
};

/**
 * @typedef {object} CadenceMetrics
 * @property {number} ann_return
 * @property {number} ann_vol
 * @property {number} max_drawdown
 * @property {number} ann_turnover
 * @property {number} long_ann_return
 * @property {number} short_ann_return
 * @property {number} beta
 * @property {number} hit_rate
 * @property {number} mean_monthly_return
 * @property {[number, number]} ci90
 * @property {number} t_stat
 */

/**
 * @typedef {object} BacktestSummary
 * @property {string} method_version
 * @property {string} as_of
 * @property {string} start
 * @property {string[]} universes
 * @property {string[]} score_inputs
 * @property {number} cost_bps
 * @property {string} primary
 * @property {Record<string, {gross: CadenceMetrics, net: CadenceMetrics, rebalances: number}>} cadences
 * @property {{n: number, percentile: number, median_net_ann: number}} null
 * @property {{per_date: Array<{date: string, rho: number, n: number}>, median_rho: number}} fidelity
 * @property {string[]} caveats
 */

/**
 * Build metrics-table rows for one gross/net mode, in the fixed cadence
 * display order (D7), with the primary cadence flagged from `summary.primary`
 * (never hardcoded). A cadence absent from `summary.cadences`, or missing the
 * requested mode, is skipped — defensive against a partial run/fixture.
 *
 * @param {BacktestSummary | null | undefined} summary
 * @param {"gross" | "net"} mode
 * @returns {Array<{key: string, label: string, primary: boolean, rebalances: number} & CadenceMetrics>}
 */
export function metricsTableRows(summary, mode) {
  if (!summary?.cadences) return [];
  const rows = [];
  for (const key of CADENCE_ORDER) {
    const cadence = summary.cadences[key];
    const metrics = cadence?.[mode];
    if (!cadence || !metrics) continue;
    rows.push({
      key,
      label: CADENCE_LABELS[key] ?? key,
      primary: key === summary.primary,
      rebalances: cadence.rebalances,
      ...metrics,
    });
  }
  return rows;
}

/**
 * Extract the dashboard's "key facts" line values: the backfill start date,
 * the primary cadence's realized beta to SPY (net), the null-benchmark
 * percentile, and the fidelity median Spearman rho. Any missing piece
 * resolves to `null` so the caller renders "—" rather than throwing on a
 * partial summary.
 *
 * @param {BacktestSummary | null | undefined} summary
 * @returns {{start: string | null, beta: number | null, nullPercentile: number | null, fidelityRho: number | null}}
 */
export function keyFacts(summary) {
  const primaryKey = summary?.primary;
  const primaryNet = primaryKey ? summary?.cadences?.[primaryKey]?.net : undefined;
  return {
    start: summary?.start ?? null,
    beta: primaryNet?.beta ?? null,
    nullPercentile: summary?.null?.percentile ?? null,
    fidelityRho: summary?.fidelity?.median_rho ?? null,
  };
}
