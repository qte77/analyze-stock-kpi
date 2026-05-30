# Contributing to analyze-stock-kpi

Shared technical workflow for human contributors and AI agents.
[README.md](README.md) covers project overview + live demo;
[AGENTS.md](AGENTS.md) carries AI-agent-only behavioural rules;
this document is the single source of truth for **how** to make
changes that pass CI and land cleanly on `main`.

## Quickstart

```bash
make setup_dev    # uv sync (default groups: dev + test)
make help         # canonical command list — every recipe with one-liner
make validate     # CI gate (lint + types + complexity + lint_md + lint_js + test_cov + test_js)
```

Every command in this document is discoverable via `make help`. If
this file disagrees with `make help`, `make help` wins.

## Test conventions

- **Mock external I/O.** yfinance / CNN / SEC EDGAR are mocked via
  `unittest.mock.patch` + `SimpleNamespace` fixtures
  (see `tests/test_fundamentals.py` for the canonical pattern).
- **Network tests are opt-in.** Tag live external calls with
  `@pytest.mark.network`; they are excluded from `make test` by
  default and opt-in via `pytest -m network`. Aim for **one** smoke
  per data source so integration drift is still caught.
- **JS units only.** `docs/demo/lib/*.js` are pure (DOM-free) and
  unit-tested via vitest (`tests/demo/*.test.mjs`); the DOM-coupled
  glue in `docs/demo/app.js` is verified by hand with `make preview`.

## Commit + PR conventions

- **[Conventional Commits](https://www.conventionalcommits.org/)**
  for every commit message and PR title:
  `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `ci`.
- **Topic-grouped commits.** One logical concern per commit; tests
  and implementation co-committed unless using strict TDD
  (red → green → optional refactor, one commit per phase).
- **Touch only task-related code.** Bug fixes don't carry surrounding
  cleanup; refactors are their own PR.
- **PRs are squash-merged** (signed via GitHub web-flow). Each PR's
  topic commits collapse into a single tidy commit on `main`.

## Branch protection + GHA workflows

- **Bot commits to `main` are blocked** by the branch ruleset.
  Workflows that need to write data target the **`data` branch** via
  the verified REST Git Data API pattern
  (Blob → Tree → Commit → Ref). See `docs/architecture.md` for the
  cron workflow shape that makes commits show as `verified: true`.
- **Pin every `uses:` to a full-length commit SHA** in any new or
  edited workflow (e.g. `actions/checkout@de0fac2e...`).

## Changelog fragments

`CHANGELOG.md` is owned by [scriv](https://github.com/nedbat/scriv).
Each PR adds **one fragment** under `changelog.d/`; no PR ever
hand-edits `CHANGELOG.md`. This eliminates the parallel-PR conflict
that used to hit every cross-cutting change.

```bash
make changelog_new        # creates + stages changelog.d/<topic>.md
                          # edit it: ### Added | ### Fixed | ### Security + one bullet
make changelog_preview    # preview the assembled next-release entry (scriv print)
```

A fragment file looks like:

```markdown
### Added

- One-sentence description of the change (#PR-number). Optional second
  sentence with motivation or non-obvious context.
```

Only the three categories currently in use are configured (`Added`,
`Fixed`, `Security`); extending to `Changed` / `Deprecated` /
`Removed` is two characters in `pyproject.toml` when needed.

## Release flow

1. **Collect fragments.**
   `make changelog_release VERSION=X.Y.Z` — runs `scriv collect`,
   prepends `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md`,
   deletes consumed fragments.
2. **Bump version + tag.**
   `uv run bump-my-version bump [major|minor|patch]` — updates
   `pyproject.toml` version, README badge, creates the bump commit
   and `v{X.Y.Z}` git tag.
3. **Push tags.** `git push --tags`.

`bump-my-version` no longer touches `CHANGELOG.md` (scriv owns it).

## Documentation pointers

- **[`docs/architecture.md`](docs/architecture.md)** — module map,
  data flow, boundary failure policy, cron workflow patterns
- **[`docs/decisions/`](docs/decisions/)** — ADRs (Traderfox removal,
  composite-score formulas, federal-contractors universe, package
  vs. repo-infrastructure boundary, etc.)
- **[`AGENTS.md`](AGENTS.md)** — AI agent behavioural rules
  (KISS / DRY / YAGNI / AHA, decision framework, quality thresholds)
- **[`README.md`](README.md)** — project overview, live demo, sample
  output, universe presets
