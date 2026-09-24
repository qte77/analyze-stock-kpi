// @ts-check
// Pure URL state parse/serialize + view-mode resolution for the demo
// dashboard. DOM-free; side-effect-free. Tested by
// tests/demo/state.test.mjs.

/**
 * @typedef {"1y" | "5y" | "10y" | "all"} WindowKey
 */

/**
 * @typedef {object} State
 * @property {"simple" | "detailed"} view
 * @property {string[]} universes
 * @property {string | null} sortKey
 * @property {1 | -1} sortDir
 * @property {string} filter
 * @property {string | null} date  ISO yyyy-mm-dd
 * @property {string | null} sector  GICS sector label or null when no filter
 * @property {WindowKey} ltFgWindow  Long-term F&G chart time-window
 * @property {WindowKey} ycWindow    Yield-curve chart time-window
 */

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const WINDOW_KEYS = /** @type {const} */ (["1y", "5y", "10y", "all"]);

/** @returns {WindowKey} */
function parseWindow(/** @type {string | null} */ raw) {
  return WINDOW_KEYS.includes(/** @type {WindowKey} */ (raw))
    ? /** @type {WindowKey} */ (raw)
    : "all";
}

/**
 * @param {string | null} v
 * @returns {v is "simple" | "detailed"}
 */
function isValidView(v) {
  return v === "simple" || v === "detailed";
}

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
  const params = new URLSearchParams(search.startsWith("?") ? search : `?${search}`);
  const viewRaw = params.get("view");
  const view = isValidView(viewRaw) ? viewRaw : "simple";
  const universes = (params.get("universe") ?? "")
    .split(",")
    .map((u) => u.trim())
    .filter((u) => u.length > 0 && knownUniverses.includes(u));
  const sortKey = params.get("sort") || null;
  const sortDir = params.get("sortDir") === "1" ? 1 : -1;
  const filter = params.get("filter") ?? "";
  const dateRaw = params.get("date");
  const date = dateRaw && isValidIsoDate(dateRaw) ? dateRaw : null;
  const sector = params.get("sector") || null;
  const ltFgWindow = parseWindow(params.get("ltFgWindow"));
  const ycWindow = parseWindow(params.get("ycWindow"));
  return {
    view,
    universes,
    sortKey,
    sortDir,
    filter,
    date,
    sector,
    ltFgWindow,
    ycWindow,
  };
}

/**
 * Set `key` to `value` in `params` when `shouldSet` is true, else remove any
 * stale value already there. `baseUrl` in `serializeState` is the *current*
 * `location.href` (not a blank slate), so a bare `URLSearchParams.set()` per
 * field — the previous approach — only ever added/overwrote params for
 * non-default values and never removed one that reverted to its default
 * (e.g. a filter/sector cleared back to `""`/`null`). That let a stale
 * `filter=`/`sector=`/etc. carried over from a shared or bookmarked URL
 * survive every subsequent `history.replaceState()` call.
 *
 * @param {URLSearchParams} params
 * @param {string} key
 * @param {string} value
 * @param {boolean} shouldSet
 */
function setOrDelete(params, key, value, shouldSet) {
  if (shouldSet) {
    params.set(key, value);
  } else {
    params.delete(key);
  }
}

/**
 * Build a URL string carrying only non-default state values — every
 * default-valued field is explicitly removed (via `setOrDelete`) rather
 * than merely left unset, so the search portion always exactly reflects
 * `state`, never a stale param carried over from `baseUrl`.
 *
 * @param {State} state
 * @param {string} baseUrl  Origin + path (e.g., `https://example.com/demo/`) —
 *   may itself already carry query params (typically the current `location.href`).
 * @returns {string}
 */
export function serializeState(state, baseUrl) {
  const url = new URL(baseUrl);
  const p = url.searchParams;
  setOrDelete(p, "view", state.view, state.view !== "simple");
  setOrDelete(p, "universe", state.universes.join(","), state.universes.length > 0);
  setOrDelete(p, "sort", state.sortKey ?? "", Boolean(state.sortKey));
  setOrDelete(p, "sortDir", String(state.sortDir), state.sortDir !== -1);
  setOrDelete(p, "filter", state.filter, Boolean(state.filter));
  setOrDelete(p, "date", state.date ?? "", Boolean(state.date));
  setOrDelete(p, "sector", state.sector ?? "", Boolean(state.sector));
  setOrDelete(p, "ltFgWindow", state.ltFgWindow, state.ltFgWindow !== "all");
  setOrDelete(p, "ycWindow", state.ycWindow, state.ycWindow !== "all");
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
  if (isValidView(urlValue)) return urlValue;
  if (isValidView(localStorageValue)) return localStorageValue;
  return "simple";
}
