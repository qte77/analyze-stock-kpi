# Core Principles

**MANDATORY for ALL tasks.** These principles override all other guidance when
conflicts arise. Every decision optimizes for user value, clarity, and usability.

## Code Quality

- **KISS (Keep It Simple, Stupid)** — simplest solution that works.
- **DRY (Don't Repeat Yourself)** — single source of truth; reference, don't duplicate.
- **AHA (Avoid Hasty Abstractions)** — three similar lines beats a premature abstraction; extract only when the pattern is stable.
- **YAGNI (You Aren't Gonna Need It)** — build for the requested behavior, not for imagined future ones.

## Execution

- **Reuse and extend** — use existing patterns and dependencies; extend rather than rebuild.
- **Consistency and coherence** — validate changes against established conventions; spot inconsistencies before they compound.
- **Concise and focused** — minimal code/text for the task; touch only task-related code.
- **Root-cause and first-principles** — solve root problems, not symptoms; understand the "why" before patching.

## Decision

- **Rigor and sufficiency** — research enough to decide with confidence, then move.
- **High-impact quick wins** — prioritize must-do tasks; ship fast, iterate.

## Communication

- **Clarity** — name things for what they are; state decisions and reasons plainly; prefer concrete examples over abstract framing.
- **Actionable and concrete** — specific deliverables, measurable outcomes.

## Before Starting Any Task

- [ ] Does this serve user value?
- [ ] Is this the simplest approach?
- [ ] Am I duplicating existing work?
- [ ] Do I actually need this?
- [ ] Am I touching only relevant code?
- [ ] What's the root cause I'm solving?
- [ ] Is this clear to a reader who lacks my context?

## Post-Task Review

Before finishing, ask yourself:

- **Did we forget anything?** — check requirements thoroughly
- **High-ROI enhancements?** — suggest opportunities (don't implement)
- **Something to delete?** — remove obsolete/unnecessary code

**IMPORTANT**: Do NOT alter files based on this review. Only output
suggestions to the user.

## When in Doubt

**STOP. Ask the user.**

Don't assume, don't over-engineer, don't add complexity.
