### Fixed

- **`docs/demo/tsconfig.json`: bump `moduleResolution` `node` → `bundler` (and `module` `ES2020` → `ESNext`).** The legacy `node` (node10) resolver is deprecated on the TypeScript 7.0 track and fails `make lint_js` / `make validate` with TS5107. `bundler` is the correct resolver for this browser-native ES-module demo (relative `./lib/*.js` imports with explicit extensions, no Node package semantics). Dev-tooling only; no runtime or behaviour change.
