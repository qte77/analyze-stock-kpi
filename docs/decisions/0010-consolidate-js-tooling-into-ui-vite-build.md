# ADR-0010 — Consolidate JS tooling into `ui/` with a Vite build

**Status:** Accepted (2026-06-19)

**Relates to:**
[ADR-0007](0007-package-vs-infrastructure-boundary.md) — the JS lint/test
tooling is repo-infrastructure (Scope 2); the dashboard runtime is the Scope-3
product surface. Consolidating the tooling under `ui/` and shipping only a
built `ui/dist/` keeps the deployed surface clean and the wheel boundary
(Scope 1 = `src/`) untouched.
[ADR-0008](0008-ui-promotion-to-ui.md) — promoted the dashboard to top-level
`ui/` and set the GitHub Pages deploy source to `ui/`. This ADR refines *how*
`ui/` deploys: from a raw copy to a build artifact.

## Context

After ADR-0008 the dashboard lives in `ui/`, but its JS tooling is split across
the repo root:

- **Root:** `package.json`, `package-lock.json`, `eslint.config.mjs`,
  `.prettierrc.json`, `.prettierignore`, `vitest.config.mjs`.
- **Runtime:** `ui/` — static `index.html` + `*.js` + `lib/*.js`, with Chart.js
  and Fuse.js **vendored** under `ui/vendor/` (zero shipped JS deps, no bundler).
- **Tests:** `tests/demo/*.test.mjs` at the root.

Two problems:

1. The root mixes Python packaging metadata with JS tooling metadata, which is
   confusing for contributors ("is this a Python repo or a JS repo?").
2. The natural fix — move the JS tooling and tests *into* `ui/` — is blocked by
   the deploy step. `gh-pages.yaml` assembles the site with a **raw copy**
   (`cp -r ui/. _site/`), so anything placed in `ui/` (tooling configs,
   `tests/`, `node_modules/`) would ship to GitHub Pages.

The sibling repo **paperverse** (`../paperverse/ui/`) already solves this with a
build step: `ui/` is *source* (`package.json` + `vite.config.ts` + `src/` +
`tests/`), `vite build` emits `ui/dist/`, and the Pages workflow uploads
`ui/dist/`. Tooling, tests, and `node_modules` never deploy.

This trades the dashboard's current **deliberate no-build simplicity** (static
files + vendored libs, zero bundler — a property valued since ADR-0008) for a
build pipeline. That tradeoff is the decision this ADR exists to make.

## Decision

> **Accepted** 2026-06-19 by owner sign-off (PR #316). The migration lands as a
> follow-up PR; this record captures the decision and its rationale.

Adopt **Vite** as a dev-only build tool so `ui/` becomes self-contained source
that compiles to a deployable `ui/dist/`:

1. **`ui/` = source, `ui/dist/` = deployable.** Add Vite as a dev dependency and
   a minimal `ui/vite.config.*` (mirroring paperverse).
2. **Move into `ui/`:** `package.json`, `package-lock.json`, `eslint.config.mjs`,
   `.prettierrc.json`, `.prettierignore`, `vitest.config.mjs`; and
   `tests/demo/` → `ui/tests/`.
3. **Repoint tooling** (globs now relative to `ui/`): the `Makefile` JS targets
   (`lint_js`, `test_js`) and `validate.yaml` JS steps run npm from `ui/`
   (`working-directory: ui`).
4. **`gh-pages.yaml`:** replace `cp -r ui/. _site/` with `npm ci && npm run build`
   in `ui/` and `upload-pages-artifact path: ui/dist`. The `ui/**` push path
   filter stays.
5. **Data stays runtime-fetched** from the `data` branch (unlike paperverse,
   which bundles data at build). Vite bundles only JS/CSS; the dashboard keeps
   fetching `results/series/*` and `results/demo/*` from
   `raw.githubusercontent.com` at runtime. ADR-0007 Rule 1 (one-way: `ui/` reads
   the data branch; `src/` never does) is unchanged.
6. **Vendored libs (sub-decision):** migrate the vendored `Chart.js` / `Fuse.js`
   to npm dev-deps (Vite-bundled) for a clean dependency graph, **or** keep them
   vendored and `import` them. Default to migrating; not load-bearing for this
   ADR.

## Consequences

- **Decluttered, Python-only root**; JS metadata + tests live with the JS, and
  the layout matches the paperverse sibling convention.
- **Deploy is now a build, not a copy.** `gh-pages` runs `npm ci && vite build`;
  tooling/tests/`node_modules` never reach Pages. A broken build fails the
  deploy loudly (vs. a raw copy that can ship anything).
- **Contributor friction:** running the dashboard locally gains an `npm ci &&
  npm run build` (or `vite dev`) step; it is no longer "open `index.html`".
- **Loss of the no-build property** (ADR-0008): the dashboard is no longer pure
  static files. This is the core tradeoff — accepted only if the decluttered,
  sibling-consistent layout is judged worth a bundler.
- **Path churn:** every moved-file reference (Makefile, `validate.yaml`,
  `gh-pages.yaml`, ADRs, README, navigable links) must be repointed. Historical
  ADR `[](path)` links break `lint/links` (lychee) if missed.

## Alternatives considered

- **Status quo (rejected — it is the problem):** leave tooling at the root. Root
  clutter and the Python/JS metadata mix remain.
- **Move tooling into `ui/` with no build (rejected):** the raw `cp -r ui/.
  _site/` would ship tooling configs, `tests/`, and `node_modules/` to Pages.
  Mitigating with copy-excludes is fragile and re-introduces per-path special
  cases; a build is the clean boundary.
- **Vite build (chosen-proposed):** matches paperverse; `ui/dist` is the single
  deployable artifact.

## References

- [ADR-0007](0007-package-vs-infrastructure-boundary.md) — scope boundaries.
- [ADR-0008](0008-ui-promotion-to-ui.md) — dashboard promoted to `ui/`; Pages
  source = `ui/`.
- `../paperverse/ui/` + its `gh-pages.yaml` — build → upload `ui/dist` precedent.
- Issue #289 — the consolidation request this ADR decides.
