# Agent Instructions for analyze-stock-kpi

Behavioural rules for AI agents working on this library-based stock
KPI CLI. **Shared dev workflow lives in [CONTRIBUTING.md](CONTRIBUTING.md)**
(test conventions, commit + PR conventions, branch protection, GHA
workflow rules, changelog fragments, release flow); this document
carries only what's agent-specific. For project overview see
[README.md](README.md); for module map + data flow see
[docs/architecture.md](docs/architecture.md).

## Core Rules

- Follow KISS, DRY, YAGNI, AHA — simplest solution that works, no
  speculative features, no premature abstractions
- **Never assume missing context** — ask if uncertain about requirements
- **Never hallucinate libraries** — only use packages verified in
  `pyproject.toml`
- **Always confirm file paths exist** before referencing in code or tests
- **Never delete existing code** unless explicitly instructed
- **Touch only task-related code** — bug fixes don't need surrounding
  cleanup
- **Strict pydantic** — every structured payload is a `BaseModel`; CLI
  / env via `BaseSettings(cli_parse_args=True)`. No `TypedDict`, no
  `dataclass`.

## Decision Framework

**Priority order:** User instructions → AGENTS.md → CONTRIBUTING.md →
README.md → existing code patterns

**Information sources:**

- Requirements: task description (primary)
- Run / lint / test commands: `make help`
- Project version: `src/__version__.py`
- Library API shapes (yfinance, pydantic, etc.): `context7` MCP, not
  training data

**Anti-scope-creep:** Implement only what is explicitly requested.
Prefer landing small working slices over comprehensive rewrites within
a single PR.

## Quality Thresholds

Subjective gut-check before starting any task. If below threshold:
gather more context or ask the user.

- **Context** 8/10 — understand requirements, codebase patterns, target API
- **Clarity** 7/10 — clear implementation path and expected outcomes
- **Alignment** 8/10 — follows project patterns, respects KISS / DRY /
  YAGNI / AHA
- **Success** 7/10 — confident in completing task correctly

## Agent-specific reminders

- **Pre-task:** read AGENTS.md → CONTRIBUTING.md → README.md →
  relevant `docs/` files; confirm quality thresholds; check
  `make help` for available recipes.
- **Verify before claiming done.** `make validate` must pass locally
  (or document why a step couldn't run — e.g. sandbox restrictions);
  CI is authoritative.
- **Strict TDD is opt-in per feature.** Default is topic-grouped
  commits with tests + implementation co-committed. When using strict
  TDD, one commit per phase (red → green → optional refactor).
