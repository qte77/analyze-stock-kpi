// ESLint flat config (ESLint 9+). Run from ui/ — lints the dashboard JS and
// its Vitest units. The dashboard ships zero runtime deps; Chart.js + Fuse.js
// are vendored under public/vendor/ (ignored) and arrive as script-tag globals.
// Prettier owns formatting — eslint-config-prettier (last) disables stylistic
// rules. JSDoc type-checking stays with tsc (the `typecheck` script), not ESLint.
import js from "@eslint/js";
import globals from "globals";
import prettier from "eslint-config-prettier";

export default [
  { ignores: ["public/**", "dist/**", "node_modules/**"] },
  js.configs.recommended,
  {
    // Browser dashboard modules. Chart.js + Fuse.js arrive as script-tag
    // globals, declared inline via `/* global Chart, Fuse */` in app.js.
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
    },
  },
  {
    // Vitest units + Node-run config files (vite/vitest/eslint config) run
    // under Node, importing the DOM-free lib/ modules.
    files: ["tests/**/*.mjs", "*.config.js", "*.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.node },
    },
  },
  prettier,
];
