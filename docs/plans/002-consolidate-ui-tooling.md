# Plan — Consolidate JS tooling + tests into `ui/` (Vite build)

Issue [#289](https://github.com/qte77/analyze-stock-kpi/issues/289) · status: **mostly shipped** —
Vite build + `ui/` consolidation (steps 1–3, 5–6) shipped; step 4 (dedicated `ui.yml` CI
split, dropping JS steps from `validate.yaml`) not done — JS lint/typecheck/test still
run inside `validate.yaml` today. #289 itself is closed; the remaining step 4 work is
tracked in a fresh follow-up issue (see References).

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

1. **Done.** Add **Vite** as a dev dep; `ui/vite.config.*` → output `ui/dist/`.
2. **Done.** Move into `ui/`: `package.json` + `package-lock.json`, the eslint/prettier/vitest
   configs; and `tests/demo/` → `ui/tests/`.
3. **Done.** Repoint eslint/vitest/tsc globs (relative to `ui/`); update the `Makefile` JS
   targets to run npm from `ui/` (`--prefix ui`).
4. **Outstanding.** **Split the JS CI into a dedicated `ui.yml`** — path-filtered (`ui/**`),
   `defaults.run.working-directory: ui`, least-privilege (`permissions: contents: read`),
   running `npm ci` + lint + `format:check` + `tsc` typecheck + vitest. `validate.yaml`
   drops its JS steps → **Python-only**. (paperverse's `ui.yml` is the template; theirs
   is typecheck + test only — ours also carries eslint/prettier.) Tracked in a fresh
   follow-up issue (see References) since #289 closed without this step.
5. **Done.** `gh-pages.yaml`: `cp -r ui/. _site/` → `npm ci && npm run build` (in `ui/`) +
   `upload-pages-artifact path: ui/dist`.
6. **Done.** Data stays **runtime-fetched** from the `data` branch (Vite bundles only JS/CSS).

## Open questions

- Vendored `Chart.js` / `Fuse.js`: keep vendored + imported, or npm deps (Vite-bundled)?
- Own ADR vs amending [ADR-0007](../decisions/0007-package-vs-infrastructure-boundary.md)? Lean own ADR — it changes the build model.
- Index-page wiring under Vite (the `<script type="module">` entry + vendored `<script>` tags).

## References

- [#289](https://github.com/qte77/analyze-stock-kpi/issues/289) (closed — steps 1–3, 5–6 shipped);
  [#367](https://github.com/qte77/analyze-stock-kpi/issues/367) (fresh follow-up for step 4,
  the outstanding `ui.yml` CI split); [ADR-0007](../decisions/0007-package-vs-infrastructure-boundary.md) (scope boundary).
- `../paperverse/ui/` + `../paperverse/.github/workflows/`: `gh-pages.yaml` (build → upload `ui/dist`) and `ui.yml` (the dedicated UI CI — path-filtered, `working-directory: ui`, `npm ci` + typecheck + test).
