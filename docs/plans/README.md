# Implementation Plans

Working implementation plans — the **how**, sitting between the issue(s)
(the *what* / *why*) and the code.

- **One file per plan** (a coherent unit of work), named by a descriptive
  slug: `slug.md`. A plan is **not keyed to an issue number** — it may span
  several issues, or none (exploratory / pre-issue design), so the filename
  can't encode that relationship.
- **Record the related issue(s) in the plan's header line** —
  `Issue [#NNN]`, `Issues [#a] + [#b]`, or `none — exploratory`. That line
  (and the References section), not the filename, is the issue link.
- Structure: **Context · Approach · Steps · Open questions · References**.
- A plan is a living draft. It may **graduate to an ADR**
  ([`../decisions/`](../decisions/)) once a load-bearing decision in it is locked,
  or be deleted once the work ships.

Substantial work gets a plan; a thin change (a one-file tweak, a process
tracker) stays issue-only — no plan file.

| Plan | Issue(s) |
|---|---|
| [XBRL cross-validation](xbrl-crossval.md) | [#101](https://github.com/qte77/analyze-stock-kpi/issues/101) |
| [Backfill F&G + 5s10s history](backfill-history.md) | [#287](https://github.com/qte77/analyze-stock-kpi/issues/287) |
| [Merge long-term charts + SP500](merge-longterm-charts.md) | [#288](https://github.com/qte77/analyze-stock-kpi/issues/288) |
| [Consolidate UI tooling into ui/](consolidate-ui-tooling.md) | [#289](https://github.com/qte77/analyze-stock-kpi/issues/289) |
