# Agent Instructions for analyze-stock-kpi

Behavioral rules for AI agents working on this library-based stock KPI CLI.
For technical details and run instructions, see [README.md](README.md). For
module map and data flow, see [docs/architecture.md](docs/architecture.md).

## Core Rules

- Follow KISS, DRY, YAGNI, AHA — simplest solution that works, no speculative
  features, no premature abstractions
- **Never assume missing context** — ask if uncertain about requirements
- **Never hallucinate libraries** — only use packages verified in `pyproject.toml`
- **Always confirm file paths exist** before referencing in code or tests
- **Never delete existing code** unless explicitly instructed
- **Touch only task-related code** — bug fixes don't need surrounding cleanup
- **Strict pydantic** — every structured payload is a `BaseModel`; CLI/env via
  `BaseSettings(cli_parse_args=True)`. No `TypedDict`, no `dataclass`.

## Architecture

Module map, data flow, boundary-failure policy, and planned/shipped
modules all live in [docs/architecture.md](docs/architecture.md) —
single source of truth. AGENTS.md only carries behaviour rules.

## Decision Framework

**Priority order:** User instructions → AGENTS.md → README.md → existing code patterns

**Information sources:**

- Requirements: task description (primary)
- Run/lint/test commands: `make help`
- Project version: `src/__version__.py`
- Library API shapes (yfinance, pydantic, etc.): `context7` MCP, not training data

**Anti-scope-creep:** Implement only what is explicitly requested. Prefer
landing small working slices over comprehensive rewrites within a single PR.

## Quality Thresholds

Subjective gut-check before starting any task. If below threshold: gather
more context or ask the user.

- **Context** 8/10 — understand requirements, codebase patterns, target API
- **Clarity** 7/10 — clear implementation path and expected outcomes
- **Alignment** 8/10 — follows project patterns, respects KISS/DRY/YAGNI/AHA
- **Success** 7/10 — confident in completing task correctly

## Agent Quick Reference

**Pre-task:**

- Read AGENTS.md → README.md → relevant `docs/` files
- Confirm quality thresholds met
- Check `make help` for available recipes

**During task:**

- Use `make` commands; document any deviation
- For new feature code: **topic-grouped commits with tests + implementation
  co-committed**. Strict TDD (Red → Green → Refactor with one commit per
  phase) is opt-in per feature
- Tag network-dependent tests with `@pytest.mark.network` (excluded from
  default `make test` via `-m 'not network'`; opt in with `pytest -m network`)
- **GHA workflows**: pin every `uses:` to a full-length commit SHA
- **Bot commits to `main` are blocked** by the branch ruleset; workflows
  that need to write data target the `data` branch via verified commits.
  See [`docs/architecture.md`](docs/architecture.md) for the pattern

**Post-task:**

- Run `make validate` — must pass (lint + types + complexity + lint_md + tests)
- Update `CHANGELOG.md` `[Unreleased]` section for non-trivial changes
- Bump `src/__version__.py` only at the end of a feature branch (semver)
