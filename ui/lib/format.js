// @ts-check
// Pure value formatters + a null-aware comparator + dotted-key accessor for
// the demo dashboard's table/detail rendering. DOM-free; side-effect-free.
// The DOM cells that consume these (e.g. `td()`) live in ui/app.js.
// Tested by tests/demo/format.test.mjs.

/**
 * Walk a dotted key path (e.g. "composite_scores.screener_score") into a
 * nested object, returning null if any segment is missing.
 * @param {any} obj
 * @param {string} key
 * @returns {any}
 */
export function nested(obj, key) {
  return key.split(".").reduce((o, k) => (o == null ? null : o[k]), obj);
}

/**
 * Format a number to `d` decimals, or "—" for null / NaN / non-numeric.
 * @param {unknown} v
 * @param {number} [d]
 * @returns {string}
 */
export function fmtNum(v, d = 1) {
  return v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d);
}

/**
 * Format a fraction as a 2-decimal percentage value (×100), or "—" for null.
 * NOTE: intentionally no NaN guard — historical behaviour yields "NaN" for
 * NaN/non-numeric input (callers append a literal " %").
 * @param {unknown} v
 * @returns {string}
 */
export function fmtPct(v) {
  return v == null ? "—" : (Number(v) * 100).toFixed(2);
}

/**
 * Null-aware comparator: nulls always sort last (regardless of `dir`);
 * strings compare via localeCompare, numbers numerically. `dir` is 1 (asc)
 * or -1 (desc).
 * @param {unknown} a
 * @param {unknown} b
 * @param {1 | -1} dir
 * @returns {number}
 */
export function compareValues(a, b, dir) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "string" && typeof b === "string") return dir * a.localeCompare(b);
  return dir * (Number(a) - Number(b));
}
