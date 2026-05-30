### Added

- **[`CONTRIBUTING.md`](CONTRIBUTING.md) as single source of truth for the shared dev workflow.** Test conventions, commit + PR conventions, branch protection, GHA workflow rules, changelog-fragment workflow, and release flow now live in one document referenced by both `README.md` (humans) and `AGENTS.md` (AI agents). `AGENTS.md` shrinks to agent-specific content only — Core Rules, Decision Framework, Quality Thresholds, and a short reminders section. README's Documentation block gains a `CONTRIBUTING.md` row.
- **`setup_lychee` recipe accepts `LYCHEE_URL` override.** Defaults to the existing `latest` release URL; override at the CLI to pin a specific lychee version (e.g. when CI surfaces a regression in a newer release).
