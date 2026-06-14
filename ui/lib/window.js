// @ts-check
// Time-window helpers for the demo dashboard's long-term charts. Pure;
// DOM-free; side-effect-free. `filterByWindow` trims an ascending-by-date
// series to a trailing window keyed by WindowKey; `findClosestScore` picks
// the entry nearest a target offset. The Chart.js render that consumes
// these lives in ui/app.js. Tested by tests/demo/window.test.mjs.

/** @typedef {import("./state.js").WindowKey} WindowKey */

/** @type {Record<WindowKey, number>} */
export const WINDOW_DAYS = { "1y": 365, "5y": 1826, "10y": 3653, "all": Infinity };

/**
 * Filter ascending-by-`isoField` entries to a trailing window measured
 * from the latest entry. Returns the input unchanged for "all" or when the
 * latest timestamp can't be parsed.
 *
 * @template {Record<string, unknown>} T
 * @param {Array<T>} entries
 * @param {WindowKey} windowKey
 * @param {string} isoField  property on each entry carrying the ISO date
 * @returns {Array<T>}
 */
export function filterByWindow(entries, windowKey, isoField) {
  if (entries.length === 0) return entries;
  const days = WINDOW_DAYS[windowKey];
  if (!Number.isFinite(days)) return entries;
  const latestIso = /** @type {string} */ (entries[entries.length - 1][isoField]);
  const latestMs = Date.parse(latestIso);
  if (Number.isNaN(latestMs)) return entries;
  const cutoff = latestMs - days * 86400000;
  return entries.filter(
    (e) => Date.parse(/** @type {string} */ (e[isoField])) >= cutoff,
  );
}

/**
 * Find the score of the entry whose timestamp is closest to `daysAgo`
 * before `latestMs`. Ties keep the earlier-listed entry (strict `<`).
 * Returns undefined for an empty list.
 *
 * @param {Array<{timestamp: string, score: number}>} entries
 * @param {number} latestMs  epoch ms of the latest entry
 * @param {number} daysAgo
 * @returns {number | undefined}
 */
export function findClosestScore(entries, latestMs, daysAgo) {
  const target = latestMs - daysAgo * 86400000;
  /** @type {{timestamp: string, score: number} | null} */
  let best = null;
  let bestDiff = Number.POSITIVE_INFINITY;
  for (const e of entries) {
    const diff = Math.abs(new Date(e.timestamp).getTime() - target);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = e;
    }
  }
  return best?.score;
}
