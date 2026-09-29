### Changed

- CI: the dashboard's JS checks (typecheck, ESLint, Prettier, Vitest, Vite build) run in their
  own `ui` workflow, only when `ui/` changes. `validate` is now Python-only (#367).
