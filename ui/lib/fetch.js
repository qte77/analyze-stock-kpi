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
 * Fetch this-year + last-year per-year JSON files from the data branch and
 * concat. Silent-fail per leg so a brand-new repo (no
 * `<baseUrl>/<pathPrefix>/<thisYear>.json` yet on the data branch) still paints
 * what's available. Sorts ascending by the named string field.
 *
 * @param {string} baseUrl     data-branch base URL (no trailing slash)
 * @param {string} pathPrefix  e.g. "results/cnn_fg" / "results/yield_curve"
 * @param {string} sortKey     e.g. "timestamp" / "date"
 * @returns {Promise<Array<any>>}
 */
export async function loadYearsFromBranch(baseUrl, pathPrefix, sortKey) {
  const thisYear = new Date().getUTCFullYear();
  const results = await Promise.allSettled([
    fetchJson(`${baseUrl}/${pathPrefix}/${thisYear - 1}.json`),
    fetchJson(`${baseUrl}/${pathPrefix}/${thisYear}.json`),
  ]);
  /** @type {Array<any>} */
  const merged = [];
  for (const r of results) {
    if (r.status === "fulfilled" && Array.isArray(r.value)) {
      merged.push(...r.value);
    }
  }
  return merged.sort((a, b) => a[sortKey].localeCompare(b[sortKey]));
}
