---
title: Agent Learning Documentation
description: Non-obvious patterns that prevent repeated mistakes across sprints
---

## Template

- **Context**: When/where this applies
- **Problem**: What issue this solves
- **Solution**: Implementation approach
- **Example**: Working code
- **References**: Related files

## Learned Patterns

### e2e against `make preview`: run it only on settled `ui/` files

- **Context**: `scripts/e2e_ui.py` against the Vite dev server (`make preview`).
- **Problem**: Vite hot-reloads on every change under `ui/`. Editing a `ui/` file while the
  e2e runs navigates the page mid-check ("Execution context was destroyed … navigation",
  locator timeouts). The first viewport of the first run after an edit also often logs
  `request failed` for an unchanged module (`lib/monthly.js`, `vendor/chart.umd.min.js`).
  Seen four times on 2026-09-30 (plan 010 slices 4–7); every rerun on unchanged code passed.
- **Solution**: make all `ui/` edits (incl. Prettier) and `make validate` first, then start
  the e2e and touch nothing under `ui/` until it ends (`docs/` and `changelog.d/` are safe).
  A lone first-viewport `request failed` right after edits is not a verdict: rerun once on
  unchanged code; a failure that repeats is real.
- **References**: `scripts/e2e_ui.py`, `ui/vite.config.js`, CONTRIBUTING's e2e section.
