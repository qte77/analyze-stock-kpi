# ADR-0008 — Promote the demo dashboard to `ui/` (EyeRest-themed)

**Status:** Proposed (2026-06-13)

**Relates to:**
[ADR-0007](0007-package-vs-infrastructure-boundary.md) — **amends** its
Scope 3, reframing the dashboard from "reference implementation, not a
product feature" to a maintained, branded product surface, and relocates
it from `docs/demo/` to a top-level `ui/`. The wheel boundary (ADR-0007
Scope 1 = `src/`) and the one-way import rule (Rule 1) are **unchanged** —
`ui/` sits outside `src/`, so it is never in the wheel by construction.
Sibling adoption: `agentic-job-offer-to-application-kit` ADR-0001
(co-proposed, same session) will mirror this schema with the same
top-level `ui/` (its #11 dashboard will fork this scaffold).

## Context

ADR-0007 placed the dashboard at `docs/demo/` (Scope 3) and framed it as
a reference implementation, not a product feature. Two things changed:

- The qte77 brand (**EyeRest** — zero-blue, warm amber) is now codified
  at `qte77/qte77/brand/DESIGN.md` and rolled into the blog. The
  dashboard should become a maintained, branded surface, not just docs.
- The dashboard's `lib/*.js` is being made DOM-free and
  data-shape-agnostic so a sibling repo
  (`agentic-job-offer-to-application-kit` #11 trends dashboard) can
  copy-and-adapt it.

Two placements were considered:

- **Top-level `ui/` (chosen).** Sibling of `src/`, served separately,
  outside the wheel **by construction** — ADR-0007 scopes the wheel to
  `src/`, so anything outside `src/` is never packaged. No build-config
  change needed, and it matches the kit's `ui/` for one portfolio-wide
  layout (`src/<pkg>/` + `ui/`).
- **`src/ui/`.** Rejected: `src/` is the Python package root, so a
  non-Python, non-shipped frontend there would be auto-included in the
  wheel (`packages = ["src"]`) unless excluded via a hatchling `exclude`
  hack — extra config for no benefit, and it diverges from the kit.

## Decision

1. **Move** `docs/demo/` → `ui/` (`index.html`, `style.css`, `app.js`,
   `table.js`, `detail_panel.js`, `lib/*.js`).

2. **`ui/` is a Scope-3 product surface, outside the wheel by
   construction.** It is a top-level sibling of `src/`; since ADR-0007
   scopes the wheel to `src/`, `ui/` is never packaged — no `pyproject`
   change required.

3. **One-way import rule unchanged** (ADR-0007 Rule 1): `ui/` MAY consume
   the `data` branch + library JSON outputs; package code (`src/`) MUST
   NOT import from `ui/` and MUST NOT read the `data` branch.

4. **Re-theme to EyeRest tokens:** zero-blue Chart.js palette + CSS vars
   sourced from `DESIGN.md` (by pointer, not copied). Reuse `lib/theme.js`
   (system/light/dark) and the `lib/chart_axes.js` injected `cssVarFn`
   seam — re-theming is one token table, not per-chart edits. Never a
   blue accent.

5. **Keep `lib/` DOM-free + data-shape-agnostic** so kit #11 is
   copy-and-adapt. Do NOT extract a shared package until a 3rd consumer
   exists (AHA).

6. Add the **"Why these universes?"** tab.

7. **Stale-copy cleanup:** `app.js` #136 reference, `empty_reason.js`
   CAD #169.

## Consequences

- **Wheel boundary untouched** — `ui/` is outside `src/`, so ADR-0007
  Scope 1 and Rule 1 hold with no build-config change. (This corrects
  the earlier assumption that the demo would move *into* `src/` and need
  a hatchling `exclude`.)
- **GitHub Pages deploy source** changes from `docs/demo/` to `ui/`. The
  Pages workflow + any cron path filters that trigger on `docs/demo/`
  changes must be updated.
- **Layout parity with the kit** — both repos become `src/<pkg>/` +
  top-level `ui/`, the shared separation schema.
- **Sequencing:** independent of the `src/` → `src/analyze_stock_kpi/`
  rename (top-level `ui/` is clean before and after it); lands BEFORE
  kit #11 (which forks this scaffold).
- **Brand dependency:** Chart.js re-theming needs the `DESIGN.md` tokens.
  The logo/avatar/`render_avatar.py` Primer-blue → EyeRest-amber recolor
  is separate visual work, NOT gated by this ADR.

## Out of scope

- The package rename `src/` → `src/analyze_stock_kpi/` (own ADR).
- Extracting a shared UI library package (AHA — wait for the 3rd consumer).

## References

- [ADR-0007](0007-package-vs-infrastructure-boundary.md) — three-scope
  model + one-way import rule (amended 2026-06-13, recorded in ADR-0007).
- `qte77/qte77/brand/DESIGN.md` — EyeRest brand tokens (by pointer).
- `agentic-job-offer-to-application-kit` issue #11 — trends dashboard
  (forks this scaffold).
