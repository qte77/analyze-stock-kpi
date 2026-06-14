# ADR-0007 — Package vs repo-infrastructure boundary

**Status:** Accepted (2026-05-21)

**Relates to:**
[ADR-0005](0005-sentiment-risk-sources.md) (three-tier source
framework — the tier-vs-scope axis is orthogonal: tier governs
auth/persistence, this ADR governs distribution scope);
[ADR-0006](0006-federal-contractors-universe.md) (amended in-place
to relocate usaspending logic from `scripts/` into `src/`).

**Amended by:** [ADR-0008](0008-ui-promotion-to-ui.md) — promotes the
demo to a top-level `ui/` (Scope-3 reframe + stale Scope-1 paths
corrected; see the 2026-06-13 amendment below);
[ADR-0009](0009-rename-package-to-analyze-stock-kpi.md) — implements the
flagged "rename `src/` → `analyze_stock_kpi/`" refactor candidate (the
Scope-1 package path becomes `src/analyze_stock_kpi/`).

## Context

The repo's tree had grown to conflate three distinct concerns under
one root:

- Code that ships in the `analyze-stock-kpi` wheel and is importable
  by downstream consumers
- This repo's CI / build / refresh infrastructure
- A demonstration dashboard hosted on GitHub Pages, with its own
  data layout on a separate `data` branch

As the federal-contractors universe work landed (PR #107: CIK
resolver in `src/sec/`; PR #108: research note; upcoming Items 2-4
adding usaspending and dashboard matrix work), the question of
"does this belong in `src/`?" was getting answered ad hoc per file.
The risk: silent drift where demo-specific or CI-specific code
seeps into `src/`, bloating the wheel and coupling the package to
this repo's deployment specifics.

A downstream user who runs `pip install analyze-stock-kpi` should
get the CLI + library + bundled presets — nothing else. They should
not need `make`, GitHub Actions, Chart.js, or this repo's `data`
branch.

## Decision

The repository tree splits into **three concentric scopes**, with
one direction rule and one path-write rule.

### Scope 1 — Package (`src/` + `README.md`)

Ships in the wheel. Hatchling's
`[tool.hatch.build.targets.wheel].packages = ["src"]` auto-includes
every `src/` file (Python source + non-Python assets such as the
`.txt` presets under `src/assets/universes/`). `README.md` is
included as project metadata via `[project].readme`.

Examples: `src/fundamentals.py`, `src/sentiment.py`,
`src/composite_scores.py`, `src/universe.py`, `src/sec/cik_map.py`,
`src/utils/http_ua.py`, `src/assets/universes/*.txt`, future
`src/usaspending.py` and `src/federal_contractors.py`.

### Scope 2 — Repo infrastructure (`scripts/`, `.github/`, `Makefile`, lint configs)

CI/CD tooling specific to this repo. Refreshes the package's bundled
artifacts (e.g., presets), runs validation, deploys the demo. Does
not ship in the wheel.

Examples: `scripts/build_demo_manifest.py`,
`scripts/build_federal_contractors.py` (future thin wrapper),
`.github/workflows/*.yaml`, `.lychee.toml`, `.markdownlint.json`,
`Makefile`.

### Scope 3 — Demo + dev docs (`docs/demo/`, `docs/*.md`, `tests/`)

Demonstrates package usage, documents design decisions, exercises
package behavior. Reference and validation material only — not part
of the public API. Tests are in the sdist but not the wheel.

Examples: `docs/demo/{index.html,app.js,style.css}`,
`docs/architecture.md`, `docs/decisions/*.md`, `docs/cnn-fg-api.md`,
`docs/data-sources.md`, `tests/**`.

### Rule 1 — Direction (one-way only)

- **Scope 2 / 3 MAY import from Scope 1.** Repo infrastructure may
  call library APIs (`from src.federal_contractors import
  build_universe`). Tests do the same.
- **Scope 1 MUST NOT reference Scope 2 / 3 paths or artifacts.**
  Package code must not assume `scripts/` exists, must not read
  files from `.github/`, must not consume the `data` branch.
- **The `data` branch is consumed only by `docs/demo/*`** (which
  fetches cross-origin from `raw.githubusercontent.com`). Package
  code never reads or writes the `data` branch.

### Rule 2 — Path-write

- Package code (Scope 1) writes only to **user-controlled paths** —
  CLI flags like `--output`, the working directory, or the XDG
  cache directory (`~/.cache/analyze-stock-kpi/`, honoring
  `XDG_CACHE_HOME`).
- Package code MUST NOT write to its own install location. In
  wheel-installed mode, `src/` lives under `site-packages/` and is
  read-only. Refreshing bundled assets is a repo-CI concern, not a
  runtime one.

### Adding new external data sources

Follow the established pattern (validated by the SEC +
usaspending split):

- Per-source module inside `src/` — single file (`src/<source>.py`)
  or subpackage (`src/<source>/`) if multiple endpoints are
  envisioned.
- Optional thin wrapper in `scripts/<source>_refresh.py` only if a
  periodic refresh workflow is needed.
- `src/<source>` exposes the library API; `scripts/<source>_refresh.py`
  calls it and persists to repo-specific paths.

## Consequences

- **Downstream `pip install` users** get the CLI + library API +
  bundled presets. No `make`, no Actions runner, no Chart.js
  vendored bundle, no `data` branch access required.
- **The dashboard** (`docs/demo/*`) is reframed as a downstream
  consumer of `src/` outputs + this repo's `data` branch — neither
  shipped with the wheel nor part of the package's public API.
  Treat it as a reference implementation, not a product feature.
- **Test suite stays in `tests/`** (Scope 3). Tests in the sdist;
  not in the wheel (hatchling default). Downstream packagers
  building from sdist can run them; pip users don't ship them.
- **Refactor candidates flagged for future ADRs** (NOT decided here):
  - Rename `src/` → `analyze_stock_kpi/` so consumers can write
    `import analyze_stock_kpi.X` instead of `import src.X`. Blocked
    by ~30 import sites in production code + tests; warrants its
    own ADR + PR.
  - `src/data_sources/` namespace consolidation if a third external
    source lands (currently SEC and usaspending sit at `src/sec/`
    and `src/usaspending.py` — the rule-of-three is not yet hit).

## Amendment (2026-06-13) — UI promotion to top-level `ui/` (ADR-0008)

[ADR-0008](0008-ui-promotion-to-ui.md) promotes the demo dashboard from
`docs/demo/` to a top-level `ui/` and re-themes it to the EyeRest brand.
Two clarifications to this ADR's text follow; the **one-way import rule
(Rule 1) is unchanged** and still governs `ui/`.

- **Scope 3 reframe.** The Consequences line "Treat it as a reference
  implementation, not a product feature" is superseded: the dashboard is
  now a **maintained, EyeRest-branded product surface** at a top-level
  **`ui/`** (relocated from `docs/demo/`). It is still **not shipped in
  the wheel** — `ui/` sits outside `src/`, so the wheel boundary (Scope 1
  = `src/`) is unchanged — and is still a downstream consumer of `src/`
  outputs + the `data` branch governed by Rule 1.

- **Stale Scope-1 example paths corrected.** The `data_sources/` and
  `domain/` sub-namespaces (introduced after this ADR was drafted, and
  by ADR-0006's library-first amendments) are now reflected. The Scope-1
  examples should read: `src/data_sources/fundamentals.py`,
  `src/data_sources/sentiment.py`, `src/domain/composite_scores.py`,
  `src/domain/universe.py`, `src/data_sources/sec/cik_map.py`,
  `src/data_sources/usaspending.py`,
  `src/orchestrators/federal_contractors.py`, `src/utils/http_ua.py`,
  `src/assets/universes/*.txt`. (The "refactor candidates" note's
  `src/sec/` + `src/usaspending.py` likewise now sit under
  `src/data_sources/`.)

## References

- pyproject.toml `[tool.hatch.build.targets.wheel].packages = ["src"]`
  defines the wheel scope.
- pyproject.toml `[project].readme = "README.md"` includes README in
  metadata.
- The CNN F&G integration in `src/data_sources/sentiment.py` is the
  precedent for "library API + own `__main__` entry point" — the
  `python -m src.data_sources.sentiment` invocation is repo-CI's cron
  hook, but the module's library API is accessible to any downstream
  caller.
