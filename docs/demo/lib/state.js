// @ts-check
// Pure URL state parse/serialize + view-mode resolution for the demo
// dashboard. DOM-free; side-effect-free. Tested by
// tests/demo/state.test.mjs.

/**
 * @typedef {object} State
 * @property {"simple" | "detailed"} view
 * @property {string[]} universes
 * @property {string | null} sortKey
 * @property {1 | -1} sortDir
 * @property {string} filter
 * @property {string | null} date  ISO yyyy-mm-dd
 */

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * @param {string} value
 * @returns {boolean}
 */
function isValidIsoDate(value) {
  const m = value.match(DATE_RE);
  if (!m) return false;
  const mo = Number(m[2]);
  const d = Number(m[3]);
  return mo >= 1 && mo <= 12 && d >= 1 && d <= 31;
}

/**
 * Parse a URL search string into a normalised dashboard state. Unknown
 * or malformed values fall through to defaults; the function never throws.
 *
 * @param {string} search  URL search substring (with or without leading `?`)
 * @param {string[]} knownUniverses  Whitelist that universe IDs must match
 * @returns {State}
 */
export function parseState(search, knownUniverses) {
  const params = new URLSearchParams(
    search.startsWith("?") ? search : `?${search}`,
  );
  const viewRaw = params.get("view");
  const view = viewRaw === "simple" || viewRaw === "detailed" ? viewRaw : "simple";
  const universes = (params.get("universe") ?? "")
    .split(",")
    .map((u) => u.trim())
    .filter((u) => u.length > 0 && knownUniverses.includes(u));
  const sortKey = params.get("sort") || null;
  const sortDir = params.get("sortDir") === "1" ? 1 : -1;
  const filter = params.get("filter") ?? "";
  const dateRaw = params.get("date");
  const date = dateRaw && isValidIsoDate(dateRaw) ? dateRaw : null;
  return { view, universes, sortKey, sortDir, filter, date };
}

/**
 * Build a URL string carrying only non-default state values, so the
 * search portion stays empty when nothing diverges from the defaults.
 *
 * @param {State} state
 * @param {string} baseUrl  Origin + path (e.g., `https://example.com/demo/`)
 * @returns {string}
 */
export function serializeState(state, baseUrl) {
  const url = new URL(baseUrl);
  if (state.view !== "simple") url.searchParams.set("view", state.view);
  if (state.universes.length > 0) {
    url.searchParams.set("universe", state.universes.join(","));
  }
  if (state.sortKey) url.searchParams.set("sort", state.sortKey);
  if (state.sortDir !== -1) {
    url.searchParams.set("sortDir", String(state.sortDir));
  }
  if (state.filter) url.searchParams.set("filter", state.filter);
  if (state.date) url.searchParams.set("date", state.date);
  return url.toString();
}

/**
 * Resolve the active view-mode from a URL value plus a localStorage
 * fallback. Precedence: URL > localStorage > "simple". Invalid URL
 * values fall through to localStorage (then default).
 *
 * @param {string | null} urlValue
 * @param {string | null} localStorageValue
 * @returns {"simple" | "detailed"}
 */
export function resolveViewMode(urlValue, localStorageValue) {
  if (urlValue === "simple" || urlValue === "detailed") return urlValue;
  if (localStorageValue === "simple" || localStorageValue === "detailed") {
    return localStorageValue;
  }
  return "simple";
}
