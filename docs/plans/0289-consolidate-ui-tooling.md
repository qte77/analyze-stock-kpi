# Plan 0289 — Consolidate JS tooling + tests into `ui/` (Vite build)

Issue [#289](https://github.com/qte77/analyze-stock-kpi/issues/289) · status: proposed · likely **graduates to an ADR** (build-tooling decision).

## Context

Dashboard JS tooling is split: root holds `package.json` / lockfile /
`eslint.config.mjs` / `.prettierrc.json` / `.prettierignore` / `vitest.config.mjs`;
the runtime is in `ui/`; tests are in root `tests/demo/`. Goal: co-locate everything
under `ui/` so the root is Python-only. Blocker: `gh-pages.yaml` does
`cp -r ui/. _site/` (raw copy), so tooling placed in `ui/` would ship to Pages.

## Approach (precedent: `../paperverse/ui/`)

paperverse keeps `package.json` + configs + `src/` + `tests/` in `ui/` and avoids
deploy pollution with a **Vite build**: `vite build` emits `ui/dist/`, and `gh-pages`
uploads `ui/dist` (not raw `ui/`). Adopt the same shape here.

## Steps

1. Add **Vite** as a dev dep; `ui/vite.config.*` → output `ui/dist/`.
2. Move into `ui/`: `package.json` + `package-lock.json`, the eslint/prettier/vitest
   configs; and `tests/demo/` → `ui/tests/`.
3. Repoint eslint/vitest/tsc globs (relative to `ui/`); update the `Makefile` JS
   targets + `validate.yaml` to run npm from `ui/` (`--prefix ui` / `working-directory: ui`).
4. `gh-pages.yaml`: `cp -r ui/. _site/` → `npm ci && npm run build` (in `ui/`) +
   `upload-pages-artifact path: ui/dist`.
5. Data stays **runtime-fetched** from the `data` branch (Vite bundles only JS/CSS).

## Open questions

- Vendored `Chart.js` / `Fuse.js`: keep vendored + imported, or npm deps (Vite-bundled)?
- Own ADR vs amending [ADR-0007](../decisions/0007-package-vs-infrastructure-boundary.md)? Lean own ADR — it changes the build model.
- Index-page wiring under Vite (the `<script type="module">` entry + vendored `<script>` tags).

## References

- [#289](https://github.com/qte77/analyze-stock-kpi/issues/289); [ADR-0007](../decisions/0007-package-vs-infrastructure-boundary.md) (scope boundary).
- `../paperverse/ui/` + `../paperverse/.github/workflows/gh-pages.yaml` (build → upload `ui/dist`).
