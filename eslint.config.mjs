// ESLint flat config (ESLint 9+). Lints the ui/ dashboard JS and its
// Vitest units. The dashboard ships zero runtime deps; Chart.js + Fuse.js are
// vendored under ui/vendor/ (excluded). Prettier owns formatting —
// eslint-config-prettier (last) disables stylistic rules to avoid conflicts.
// JSDoc type-checking stays with tsc (the "Lint JS" step), not ESLint.
import js from "@eslint/js";
import globals from "globals";
import prettier from "eslint-config-prettier";

export default [
  { ignores: ["ui/vendor/**", "node_modules/**", ".venv/**"] },
  js.configs.recommended,
  {
    // Browser dashboard modules. Chart.js + Fuse.js arrive as script-tag
    // globals, declared inline via `/* global Chart, Fuse */` in app.js.
    files: ["ui/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
    },
  },
  {
    // Vitest units run under Node, importing the DOM-free lib/ modules.
    files: ["tests/demo/**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.node },
    },
  },
  {
    // Root build/test config files run under Node (vitest.config.mjs,
    // eslint.config.mjs) — they use `process`, imports, etc.
    files: ["*.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.node },
    },
  },
  prettier,
];
