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
- **JS units only.** `ui/lib/*.js` are pure (DOM-free) and
  unit-tested via vitest (`ui/tests/*.test.mjs`); the DOM-coupled
  glue in `ui/app.js` is verified by hand with `make preview`.

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

Semi-automated: bump is a manual dispatch, tag + publish are automatic /
on-demand `workflow_call` callers to `qte77/.github`'s reusable workflows.

1. **Bump** — trigger `bump-my-version.yaml` via `workflow_dispatch` (choose
   `major`/`minor`/`patch`). It bumps `pyproject.toml` + the README version
   badge, collects `changelog.d/` fragments via `scriv`, and opens a release
   PR — review and merge it like any other PR.
2. **Tag** — merging that PR to `main` (a `pyproject.toml` version change)
   triggers `tag-release.yaml`, which calls `qte77/.github`'s reusable
   `tag-release.yml` to create the annotated `v{X.Y.Z}` tag automatically.
   Idempotent — aborts rather than overwrites if the tag already exists.
3. **Publish (optional)** — trigger `publish-release.yaml` via
   `workflow_dispatch` to call the reusable `publish-release.yml`, which
   creates a GitHub Release from the tag using the `CHANGELOG.md`
   `## [X.Y.Z]` block. Also idempotent — aborts if a Release already exists.

Neither tag nor publish ever deletes a tag/Release on failure — release
immutability means a deleted tag name is unusable forever (`qte77/.github#23`).
`bump-my-version.yaml` stays a local, repo-owned workflow rather than a
`qte77/.github` reusable call by design — see `qte77/qte77#126` ("no
reusable-bump"; human-merge-triggers-tag is the intended flow estate-wide).

## Documentation pointers

- **[`docs/architecture.md`](docs/architecture.md)** — module map,
  data flow, boundary failure policy, cron workflow patterns
- **[`docs/decisions/`](docs/decisions/)** — ADRs (Traderfox removal,
  composite-score formulas, federal-contractors universe, package
  vs. repo-infrastructure boundary, etc.)
- **[`docs/plans/`](docs/plans/)** — working implementation plans for
  substantial issues (the *how* between issue and code); its README
  gives the slug-naming + structure convention and when to write one
- **[`AGENTS.md`](AGENTS.md)** — AI agent behavioural rules
  (KISS / DRY / YAGNI / AHA, decision framework, quality thresholds)
- **[`README.md`](README.md)** — project overview, live demo, sample
  output, universe presets
