// @ts-check
// Per-cell empty-tooltip rule table (#170). When a rendered cell
// resolves to null/undefined the table still shows "—"; this module
// answers `why is this empty?` for cases where the answer is
// structural (sector / instrument shape) rather than a data gap.
//
// Tested by tests/demo/empty_reason.test.mjs. New rules land
// additively as #168 / #169 surface them — keep the table flat and
// declarative so each entry can be reviewed in isolation.

/**
 * @typedef {object} EmptyContext
 * @property {string | null} [sector]
 * @property {string | null} [industry]
 * @property {string | null} [currency]
 */

/**
 * @typedef {object} Rule
 * @property {(ctx: EmptyContext) => boolean} match
 * @property {ReadonlySet<string>} columns
 * @property {string} reason
 */

const isBank = (/** @type {EmptyContext} */ ctx) =>
  ctx.sector === "Financial Services" &&
  typeof ctx.industry === "string" &&
  ctx.industry.startsWith("Banks");

/** @type {ReadonlyArray<Rule>} */
const RULES = [
  {
    match: (ctx) => ctx.sector === "Financial Services",
    columns: new Set(["rd_to_revenue"]),
    reason: "Banks don't report R&D",
  },
  {
    match: (ctx) => ctx.sector === "Financial Services",
    columns: new Set(["current_ratio"]),
    reason: "Banks have no current/long-term split",
  },
  {
    // Narrow to CAD pending #169 research; widen to all non-US banks
    // additively once Yahoo coverage is surveyed.
    match: (ctx) => isBank(ctx) && ctx.currency === "CAD",
    columns: new Set(["return_on_equity", "return_on_assets"]),
    reason: "Yahoo doesn't ship this field for non-US banks",
  },
];

/**
 * Resolve the tooltip string for one (row, columnKey) pair. Returns
 * `null` when no rule applies — the cell stays a bare "—" with no
 * tooltip.
 *
 * @param {EmptyContext} row
 * @param {string} columnKey
 * @returns {string | null}
 */
export function explainEmpty(row, columnKey) {
  for (const rule of RULES) {
    if (rule.columns.has(columnKey) && rule.match(row)) return rule.reason;
  }
  return null;
}
