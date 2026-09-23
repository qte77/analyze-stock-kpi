// @ts-check
// Pure helpers for the hypothetical long/short model portfolio section
// (ADR-0012). No stored NAV (D11): the weekly-return rows persisted on the
// data branch are compounded client-side into a 100-based index line. DOM
// rendering lives in ui/charts.js.

/**
 * @typedef {object} PortfolioReturnRow
 * @property {string} date
 * @property {number} [ret_long]
 * @property {number} [ret_short]
 * @property {number} [ret_ls]
 */

/**
 * Compound a date-sorted return series into a 100-based index line.
 * `index[0] = 100 * (1 + row[0][field])`; each subsequent point multiplies
 * the running level by `(1 + row[i][field])`. Rows with a non-numeric
 * `field` value are skipped — the running level carries forward unchanged
 * — rather than aborting the whole line.
 *
 * @param {PortfolioReturnRow[]} rows  ascending by date.
 * @param {"ret_long" | "ret_short" | "ret_ls"} [field]
 * @returns {{dates: string[], index: number[]}}
 */
export function compound(rows, field = "ret_ls") {
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
 * @typedef {object} HoldingWeight
 * @property {string} ticker
 * @property {number} weight
 */

/**
 * @typedef {object} PortfolioStateShape
 * @property {HoldingWeight[]} long
 * @property {HoldingWeight[]} short
 */

/**
 * @typedef {object} HoldingRow
 * @property {string} ticker
 * @property {"long" | "short"} side
 * @property {number} weight
 */

/**
 * Flatten a weekly-state's long + short target weights into holdings-table
 * rows, long leg first, each leg sorted descending by weight so the
 * largest positions lead.
 *
 * @param {PortfolioStateShape | null | undefined} state
 * @returns {HoldingRow[]}
 */
export function holdingsRows(state) {
  if (!state) return [];
  /** @param {HoldingWeight[]} list @param {"long" | "short"} side */
  const bySide = (list, side) =>
    [...list]
      .sort((a, b) => b.weight - a.weight)
      .map((h) => ({ ticker: h.ticker, side, weight: h.weight }));
  return [...bySide(state.long ?? [], "long"), ...bySide(state.short ?? [], "short")];
}
