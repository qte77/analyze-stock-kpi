// @ts-check
// Pure helpers for the point-in-time backtested long/short 25/25 dashboard
// section (ADR-0013, plan 008). Shared by both series (D15): Series A
// (genuine decisions, the headline) and Series B (the reconstructed
// backfill, a collapsible below it) have the same contract shape, so every
// helper here is parameterized by the caller's data rather than duplicated
// per series — only the path prefix (ui/app.js) and DOM id prefix
// (ui/charts.js) differ. `compound` turns one cadence's daily return rows
// (`results/series/backtest[_genuine]/<cadence>/YYYY.json`) into a 100-based
// index line client-side — no stored NAV (D5/D8). `metricsTableRows` and
// `keyFacts` project a `results/backtest[_genuine]/summary.json` into the
// shapes the metrics table and key-facts line render. `sinceLabel` composes
// each series' headline once its start date is known. `tradeLogRows` and
// `rebalanceMarkers` project a `results/backtest[_genuine]/trades/<cadence>/
// YYYY.json` rebalance log (D21) into the log table's rows and the chart's
// sparse marker overlay. DOM rendering lives in ui/charts.js.

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
  "yearly",
  "buy_hold",
];

/** @type {Record<string, string>} */
export const CADENCE_LABELS = {
  monthly: "Monthly",
  quarterly_filings: "Quarterly (after filings)",
  monthly_buffer: "Monthly + buffer",
  weekly: "Weekly",
  yearly: "Yearly",
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
 * @property {{n: number, percentile: number, median_net_ann: number} | null} null
 * @property {{per_date: Array<{date: string, rho: number, n: number}>, median_rho: number} | null} fidelity
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

/**
 * Plan 010 slice 3 (#446): SPY as a reference line on a backtest chart.
 * Aligns `results/series/equity_spy` entries (`ret_indexed`, a total-return
 * index) to the chart's `dates`: each date takes the latest SPY value on or
 * before it (carried over days SPY didn't trade, e.g. a non-US holiday),
 * rebased to 100 on the first covered date; `null` before SPY data starts.
 *
 * @param {string[]} dates  ascending.
 * @param {Array<{date: string, ret_indexed: number}>} spyEntries  ascending.
 * @returns {Array<number | null>}
 */
export function spyIndexOn(dates, spyEntries) {
  const out = [];
  let i = -1;
  let base = null;
  for (const d of dates) {
    while (i + 1 < spyEntries.length && spyEntries[i + 1].date <= d) i += 1;
    const level = i >= 0 ? spyEntries[i].ret_indexed : null;
    if (level === null) {
      out.push(null);
      continue;
    }
    base ??= level;
    out.push((level / base) * 100);
  }
  return out;
}

/** @param {number} v a fraction, e.g. 0.071 → "+7.1 %" */
const signedPct = (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} %`;

/** Two-sided 90 % normal critical value, as the backend's D9 CI uses. */
const T_90 = 1.645;

/**
 * Plan 010 slice 3 (#446): layer 1's one sentence under a series' chart.
 * Uses the primary cadence's annualized net return and says plainly whether
 * it is statistically significant; before 12 months of returns (metrics
 * `null`, D9) it gives the cumulative net return since the start instead of
 * dashes. Empty when there is no summary or data yet.
 *
 * @param {BacktestSummary | null | undefined} summary
 * @param {BacktestReturnRow[]} primaryRows  the primary cadence's daily rows.
 * @returns {string}
 */
export function headlineLine(summary, primaryRows) {
  const cadence = summary?.primary ? summary.cadences?.[summary.primary] : undefined;
  if (!summary?.start || !cadence) return "";
  const lead = "Long best 25 / short worst 25:";
  const tail = `since ${summary.start}, ${cadence.rebalances} rebalances`;
  const disclaimer = "Hypothetical, not investment advice.";
  const { ann_return: ann, t_stat: t } = cadence.net ?? {};
  if (typeof ann === "number") {
    const sig =
      typeof t === "number" && Math.abs(t) >= T_90
        ? "statistically significant at 90 %"
        : "not statistically significant";
    return `${lead} ${signedPct(ann)} a year after costs ${tail}; ${sig}. ${disclaimer}`;
  }
  const { index } = compound(primaryRows, "ret_ls_net");
  if (index.length === 0) return "";
  const cumulative = index[index.length - 1] / 100 - 1;
  return (
    `${lead} ${signedPct(cumulative)} after costs ${tail}; ` +
    `too short to annualize (needs 12 months of returns). ${disclaimer}`
  );
}

/**
 * Compose a two-series section heading/label with its start date once known
 * (D16/D18: Series A's genuine-snapshot start, Series B's post-start-trim
 * start), else the plain `base` text — never a dangling "since null"/"since
 * —" before the first successful summary load. Shared by Series A's section
 * headline and Series B's collapsible `<summary>` label.
 *
 * @param {string} base
 * @param {string | null | undefined} start
 * @returns {string}
 */
export function sinceLabel(base, start) {
  return start ? `${base} since ${start}` : base;
}

/**
 * @typedef {object} RankedTicker
 * @property {string} ticker
 * @property {number | null} rank
 * @property {number | null} score
 */

/**
 * @typedef {object} LegChange
 * @property {RankedTicker[]} entered
 * @property {RankedTicker[]} exited
 */

/**
 * @typedef {"initial" | "scheduled_weekly" | "scheduled_monthly" | "quarterly_after_filings" | "scheduled_yearly" | "buffer_exit" | "buy_hold_initial"} RebalanceReason
 */

/**
 * @typedef {object} TradeLogEntry
 * @property {string} rank_date
 * @property {string} trade_date
 * @property {RebalanceReason} reason
 * @property {LegChange} long
 * @property {LegChange} short
 * @property {number} turnover
 */

/** D21 rebalance reasons, human-readable. A reason absent from this map
 *  falls back to its raw value in `tradeLogRows` rather than throwing — the
 *  enum may grow ahead of this file. */
export const REBALANCE_REASON_LABELS = {
  initial: "Initial",
  scheduled_weekly: "Scheduled (weekly)",
  scheduled_monthly: "Scheduled (monthly)",
  quarterly_after_filings: "Quarterly (after filings)",
  scheduled_yearly: "Scheduled (yearly)",
  buffer_exit: "Buffer exit",
  buy_hold_initial: "Buy & hold (initial)",
};

/**
 * Sort one series' rebalance log (D21) newest-first and attach each entry's
 * human-readable reason label, for the "Rebalance log" collapsible table.
 *
 * @param {TradeLogEntry[] | null | undefined} trades
 * @returns {Array<TradeLogEntry & {reasonLabel: string}>}
 */
export function tradeLogRows(trades) {
  return [...(trades ?? [])]
    .sort((a, b) => b.trade_date.localeCompare(a.trade_date))
    .map((t) => ({ ...t, reasonLabel: REBALANCE_REASON_LABELS[t.reason] ?? t.reason }));
}

/**
 * Build a sparse marker overlay aligned to a chart's x-axis `dates`/
 * `indexValues` (the primary cadence's compounded index, D21's "mark the
 * rebalance trade dates on the chart"): `indexValues[i]` at each date that
 * is a rebalance trade date, else `null` — so a Chart.js dataset with
 * `showLine:false` draws a point only on rebalance days, without a second
 * lookup/rescale pass over the trade log at render time.
 *
 * @param {string[]} dates
 * @param {Array<number | null | undefined>} indexValues
 * @param {string[]} tradeDates
 * @returns {Array<number | null>}
 */
export function rebalanceMarkers(dates, indexValues, tradeDates) {
  const tradeDateSet = new Set(tradeDates);
  return dates.map((d, i) => {
    const v = indexValues[i];
    return tradeDateSet.has(d) && typeof v === "number" ? v : null;
  });
}
