// @ts-check
// Themed Chart.js axis configs for the demo dashboard's composite line charts.
// Pure; DOM-free. Each function returns a plain options object whose tick/grid
// colors are DEFERRED closures: Chart.js calls them lazily on every
// render/update, so a theme flip re-resolves the palette (see bindThemeObserver
// in app.js). The colors come from an injected `cssVarFn(token, fallback)` — the
// caller (app.js) owns it and its lifetime; this module never touches the DOM.
// Tested by tests/demo/chart_axes.test.mjs.

/** @typedef {(token: string, fallback: string) => string} CssVarFn */

/**
 * Themed 0–100 score y-axis (stepSize 25) shared by the composite line charts.
 * The returned object holds deferred `cssVarFn` closures (evaluated lazily by
 * Chart.js) — pass a stable cssVarFn that stays valid for the chart's lifetime.
 *
 * @param {CssVarFn} cssVarFn
 */
export function scoreYAxis(cssVarFn) {
  return {
    min: 0,
    max: 100,
    ticks: { stepSize: 25, color: () => cssVarFn("--text", "#2c2818") },
    grid: { color: () => cssVarFn("--border", "#c8c4b0") },
  };
}

/**
 * Themed x-axis with a tick cap, shared by the time-series line charts. Same
 * deferred-closure caveat as scoreYAxis.
 *
 * @param {CssVarFn} cssVarFn
 * @param {number} [maxTicks]
 */
export function themedXAxis(cssVarFn, maxTicks = 14) {
  return {
    ticks: { maxTicksLimit: maxTicks, color: () => cssVarFn("--text", "#2c2818") },
    grid: { color: () => cssVarFn("--border", "#c8c4b0") },
  };
}
