# Implementation Plans

Working implementation plans — the **how**, sitting between the issue(s)
(the *what* / *why*) and the code.

- **One file per plan** (a coherent unit of work), named `NNN-slug.md` — a
  zero-padded creation-order number plus a descriptive slug. A plan is
  **not keyed to an issue number** — it may span several issues, or none
  (exploratory / pre-issue design), so the filename can't encode that
  relationship; the number is purely creation order. (Numbered prefix added
  retroactively 2026-09-21 — the first 5 plans were originally bare slugs;
  new plans get the next number. This repo keeps `NNN` rather than the
  workspace-wide `YYYY-MM-DD-NNNN` form — decided 2026-11-22 in
  [#294](https://github.com/qte77/analyze-stock-kpi/issues/294).)
- **Record the related issue(s) in the plan's header line** —
  `Issue [#NNN]`, `Issues [#a] + [#b]`, or `none — exploratory`. That line
  (and the References section), not the filename, is the issue link.
- Structure: **Context · Approach · Steps · Open questions · References**.
- A plan is a living draft. It may **graduate to an ADR**
  ([`../decisions/`](../decisions/)) once a load-bearing decision in it is locked,
  and is **deleted once its work ships**. Links to a deleted plan (roadmap, other
  plans) become a permalink to the last commit that had it; numbers are never reused.

Substantial work gets a plan; a thin change (a one-file tweak, a process
tracker) stays issue-only — no plan file.

Plans 001–008 and 010 shipped or closed and were deleted on 2026-11-22; read them at
[`815d93b`](https://github.com/qte77/analyze-stock-kpi/tree/815d93b8df3b4f7f5965a50ab24dac5f4d573593/docs/plans).

| Plan | Status | Issue(s) |
|---|---|---|
| [Backtest carry-over](009-backtest-carry-over.md) | open: [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) | [#415](https://github.com/qte77/analyze-stock-kpi/issues/415) · [#416](https://github.com/qte77/analyze-stock-kpi/issues/416) · [#417](https://github.com/qte77/analyze-stock-kpi/issues/417) · [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) · [#419](https://github.com/qte77/analyze-stock-kpi/issues/419) |
| [Options open-interest levels: daily collection](011-options-oi-levels.md) | proposed | none yet — owner request 2026-11-22 |
