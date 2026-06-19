// @ts-check
// Theme-mode resolver for the demo dashboard. Three modes:
//   - "system"  → follow `prefers-color-scheme` (CSS media query)
//   - "light"   → force light palette regardless of OS
//   - "dark"    → force dark palette regardless of OS
//
// Pure module — no DOM, no side effects. The corresponding CSS lives in
// ui/style.css under `body.theme-light` / `body.theme-dark`
// blocks plus a `@media (prefers-color-scheme: dark)` rule that applies
// the dark palette when `body.theme-system` is active.
// Tested by tests/theme.test.mjs.

/** @typedef {"system" | "light" | "dark"} ThemeMode */

/**
 * Type guard for ThemeMode strings. Case-sensitive (the URL parser
 * normalises to lowercase before passing in, so callers shouldn't
 * see mixed-case anyway).
 *
 * @param {unknown} value
 * @returns {value is ThemeMode}
 */
export function isThemeMode(value) {
  return value === "system" || value === "light" || value === "dark";
}

/**
 * Resolve the active theme from a URL value plus a localStorage
 * fallback. Precedence: URL > localStorage > "system" default.
 * Invalid URL values fall through to localStorage (then default).
 *
 * @param {string | null} urlValue
 * @param {string | null} localStorageValue
 * @returns {ThemeMode}
 */
export function resolveTheme(urlValue, localStorageValue) {
  if (isThemeMode(urlValue)) return urlValue;
  if (isThemeMode(localStorageValue)) return localStorageValue;
  return "system";
}

/** Cycle order for the single-button toggle. @type {readonly ThemeMode[]} */
export const THEME_CYCLE = ["system", "light", "dark"];

/**
 * Next mode in the system → light → dark → system cycle, for the
 * single-button toggle. `mode` is always a valid ThemeMode (it is the
 * resolved `activeTheme`), so the wrap-around (dark → system) is the
 * only edge worth guarding.
 *
 * @param {ThemeMode} mode
 * @returns {ThemeMode}
 */
export function nextTheme(mode) {
  const i = THEME_CYCLE.indexOf(mode);
  return THEME_CYCLE[(i + 1) % THEME_CYCLE.length];
}
