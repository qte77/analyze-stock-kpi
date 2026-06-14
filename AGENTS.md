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

**Experimental** (adopted 2026-06-14) — re-evaluate by **2026-06-21**; tracked in
[#283](https://github.com/qte77/analyze-stock-kpi/issues/283). Replaces the prior
1–10 scale.

Before starting any task, gut-check four dimensions on a **`1 / 0 / -1`** scale —
the assessment exists only to pick the next action, so it has three states, not ten.

- **Context** — requirements, codebase patterns, and target API understood
- **Clarity** — implementation path and expected outcome are clear
- **Alignment** — follows project patterns + KISS / DRY / YAGNI / AHA
- **Success** — confident the task can be completed correctly

Rate each:

- **`1`** sufficient — can act now; no material unknowns
- **`0`** borderline — a real gap, or an assumption being guessed at
- **`-1`** insufficient — largely guessing; cannot responsibly start

Then act on the assessment:

- **Any `-1` → STOP and ask the user.**
- **`0` on Context or Alignment → resolve before proceeding** (research it, or ask)
  — wrong understanding or a wrong-pattern fit cascades into rework.
- **`0` on Clarity or Success → may proceed**, but state the assumption and
  checkpoint early — these correct cheaply as you go.
- **All `1` → proceed.**

Judge per-dimension; **don't sum** — a single `-1` on Context or Alignment dominates
and a total would mask it.

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
