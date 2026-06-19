### Changed

- **JS tooling + tests consolidated under `ui/` with a Vite build (ADR-0010,
  #289).** `package.json`, the eslint/prettier/vitest configs, and `tests/demo/`
  moved from the repo root into `ui/` (`ui/tests/`), so the root is Python-only.
  `ui/` is now Vite *source* → `ui/dist/` is the deployable; `gh-pages.yaml`
  builds (`npm run build`) and uploads `ui/dist` instead of raw-copying `ui/`.
  Vendored Chart.js/Fuse.js, `favicon.svg`, and `universes.json` moved to
  `ui/public/` (served verbatim under the project base path). The dashboard's
  data still loads at runtime from the `data` branch — never bundled. `Makefile`
  + `validate.yaml` JS steps now run from `ui/`; `validate` also builds the UI to
  catch breakage on PRs.
