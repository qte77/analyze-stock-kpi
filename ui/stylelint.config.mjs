// CSS lint for the dashboard: stylelint's "recommended" set flags likely errors
// (e.g. duplicate selectors, invalid hex, unknown properties) without imposing a
// formatting style on the existing stylesheet. Runs in `npm run lint:css`, which
// `make lint_js` and the `ui` CI job call.
/** @type {import('stylelint').Config} */
export default {
  extends: ["stylelint-config-recommended"],
  ignoreFiles: ["dist/**"],
  rules: {
    // Off: it compares selectors by source order only, so it flags unrelated
    // ID-scoped elements (26 hits when adopted, e.g. `#fg-panel > summary` vs
    // `#backtest-details > summary`), none of them a real override bug.
    "no-descending-specificity": null,
  },
};
