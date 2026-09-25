# Implementation Plans

Working implementation plans — the **how**, sitting between the issue(s)
(the *what* / *why*) and the code.

- **One file per plan** (a coherent unit of work), named `NNN-slug.md` — a
  zero-padded creation-order number plus a descriptive slug. A plan is
  **not keyed to an issue number** — it may span several issues, or none
  (exploratory / pre-issue design), so the filename can't encode that
  relationship; the number is purely creation order. (Numbered prefix added
  retroactively 2026-09-21 — the first 5 plans were originally bare slugs;
  new plans get the next number.)
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
| [Backfill F&G + 5s10s history](001-backfill-history.md) | [#287](https://github.com/qte77/analyze-stock-kpi/issues/287) |
| [Consolidate UI tooling into ui/](002-consolidate-ui-tooling.md) | [#289](https://github.com/qte77/analyze-stock-kpi/issues/289) |
| [Merge long-term charts + SP500](003-merge-longterm-charts.md) | [#288](https://github.com/qte77/analyze-stock-kpi/issues/288) |
| [XBRL cross-validation](004-xbrl-crossval.md) (shipped) | [#101](https://github.com/qte77/analyze-stock-kpi/issues/101) |
| [Restructure data-branch results/ layout](005-restructure-results.md) | none — pre-issue design |
| [Agent-ready backlog: llms.txt, XBRL, release workflows](006-agent-ready-backlog.md) | [#361](https://github.com/qte77/analyze-stock-kpi/issues/361) + [#101](https://github.com/qte77/analyze-stock-kpi/issues/101) + [#340](https://github.com/qte77/analyze-stock-kpi/issues/340) |
| [Long/short model portfolio + multi-window Sortino](007-longshort-portfolio-and-multiwindow-sortino.md) (closed; superseded by 008) | none — owner request 2026-09-21/22 |
| [Point-in-time backfill + backtested L/S 25/25](008-pit-longshort-backtest.md) (closed; carry-over in 009) | [#401](https://github.com/qte77/analyze-stock-kpi/issues/401) |
| [Backtest carry-over](009-backtest-carry-over.md) | [#415](https://github.com/qte77/analyze-stock-kpi/issues/415) · [#416](https://github.com/qte77/analyze-stock-kpi/issues/416) · [#417](https://github.com/qte77/analyze-stock-kpi/issues/417) · [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) · [#419](https://github.com/qte77/analyze-stock-kpi/issues/419) |
| [UI redesign: positioning + progressive disclosure](010-ui-redesign-progressive-disclosure.md) | [#426](https://github.com/qte77/analyze-stock-kpi/issues/426) · owner request 2026-09-25 |
