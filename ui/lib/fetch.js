// @ts-check
// HTTP fetch helpers for the demo dashboard's data-branch loads. Pure;
// DOM-free; side-effect-free apart from the network call. `fetchJson` is the
// thin fetch+throw+parse wrapper every loader builds on; `loadYearsFromBranch`
// fetches the this-year + last-year per-year JSON files for a results prefix and
// concatenates them, silently dropping a leg that fails so a brand-new data
// branch still paints what's available. The app.js closures (loadManifest,
// loadSnapshot, loadFearGreedYears, …) compose these with the active universe +
// base URL. Tested by tests/demo/fetch.test.mjs.

/**
 * Fetch JSON from `url`, throwing on a non-2xx response. `cache: "no-cache"`
 * forces revalidation so the dashboard never paints a stale snapshot.
 *
 * @param {string} url
 * @returns {Promise<any>}
 */
export async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  return res.json();
}

/**
 * Fetch every per-year JSON file from `floorYear` through the current UTC year
 * off the data branch and concat. Fetched in parallel; silent-fail per leg so
 * years with no file yet (a 404 before the series started, or this year before
 * the first cron run) are simply skipped — the chart still paints what exists.
 * Sorts ascending by the named string field. The default floor (2011) is the
 * CNN F&G / 5s10s inception; pass an explicit `floorYear` for a shallower series.
 *
 * @param {string} baseUrl     data-branch base URL (no trailing slash)
 * @param {string} pathPrefix  e.g. "results/cnn_fg" / "results/yield_curve"
 * @param {string} sortKey     e.g. "timestamp" / "date"
 * @param {number} [floorYear] first year to try (inclusive); default 2011
 * @returns {Promise<Array<any>>}
 */
export async function loadYearsFromBranch(baseUrl, pathPrefix, sortKey, floorYear = 2011) {
  const thisYear = new Date().getUTCFullYear();
  const years = Array.from({ length: thisYear - floorYear + 1 }, (_, i) => floorYear + i);
  const results = await Promise.allSettled(
    years.map((y) => fetchJson(`${baseUrl}/${pathPrefix}/${y}.json`)),
  );
  /** @type {Array<any>} */
  const merged = [];
  for (const r of results) {
    if (r.status === "fulfilled" && Array.isArray(r.value)) {
      merged.push(...r.value);
    }
  }
  return merged.sort((a, b) => a[sortKey].localeCompare(b[sortKey]));
}
