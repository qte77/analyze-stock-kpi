# Plan — Restructure data-branch `results/` layout (group by kind)

Issue `none — pre-issue design` (adjacent: [#288](https://github.com/qte77/analyze-stock-kpi/issues/288), [#289](https://github.com/qte77/analyze-stock-kpi/issues/289)) · status: **shipped** (PR #305, 2026-06-18; data branch migrated) — one tail deferred (see below).

## Context

The `results/` tree on the `data` branch grew flat and convoluted — each
source carried its own `audit/` subdir, and series sat beside demo
snapshots. This regroups results into three kinds — **series**, **demo**,
**audit** — for a legible tree and to give incoming work
([#288](https://github.com/qte77/analyze-stock-kpi/issues/288) adds
`series/yield_curve/sp500/`) a clean home.

The live demo (gh-pages) reads these paths at **runtime**, so this is a
coordinated outward-facing migration: data must exist at the new paths
*before* the reading code ships, and old paths are deleted *after* the
redeploy is verified — otherwise the demo 404s. Groundwork shipped in
[#300](https://github.com/qte77/analyze-stock-kpi/pull/300): every
`results/…` path on the Python side derives from `AppSettings` regular
`Path` fields (kept regular, **not** `computed_field` — that breaks
`model_copy(update={dir: tmp_path})` in the config/main tests).

### Target layout

```text
results/
  series/cnn_fg/YYYY.json
  series/yield_curve/YYYY.json          (sp500/ arrives with #288)
  demo/<universe>/{index,latest,<date>}.json      ← unchanged
  audit/universes-<date>.json                      ← already here
  audit/federal_contractors/<date>.json
  audit/aggregated_scores_best_and_worst/<date>.json
  audit/enhanced_kpi_screener_longshort/<date>.json
```

## Approach

One **code PR** plus a **3-phase data move** that keeps the demo
404-free. Strict TDD on the three affected *modules* (config defaults,
`_run_refresh_universe`, the `ui/lib/audit.js` URL); no tests for thin
scripts, workflow YAML, or DOM-glue path strings.

## Steps

1. **Code PR** —
   - `config.py`: `cnn_fg_cache_dir` / `yield_curve_cache_dir` →
     `results/series/…`.
   - Federal-contractors audit (two writers — `__main__._run_refresh_universe`
     and `scripts/build_federal_contractors.py`) → `audit_dir/federal_contractors/`
     (preset path stays on `federal_contractors_dir`).
   - `scripts/_demo_snapshot_loader.py`: paired-universe audit →
     `audit_dir/<universe>/`.
   - Workflows: `fear-greed.yaml` / `yield-curve.yaml` series paths
     (incl. the `awk` regexes); `universe-builder.yaml` three `audit_dir=`
     outputs → `results/audit/<universe>`.
   - UI: `ui/app.js` series prefixes; `ui/lib/audit.js` →
     `results/audit/federal_contractors/`.
   - Docs/comments swept to the new paths (`architecture.md`, `README.md`,
     `UserStory.md`, ADR-0005, this plan set, module docstrings,
     `.gitignore`).
2. **Data move (sequenced)** — on a `git worktree` of `data`:
   1. **Copy** (not move) old → new paths so both coexist; push to `data`.
   2. **Merge** the code PR → gh-pages redeploys reading new paths; crons
      now write new paths.
   3. **Verify** the live demo on new paths (long-term F&G + 5s10s slope
      charts; federal-contractors audit overlay; no 404s), then **delete**
      the old paths from `data`.

## Deferred / open questions / out of scope

- **Deferred — rename `results/demo/` → `results/snapshots/`**: de-"demo" the
  production snapshot dir. Fold into [#289](https://github.com/qte77/analyze-stock-kpi/issues/289)
  (consolidate-ui-tooling), which already reworks the demo/UI layer — rename the
  path *and* the subsystem (`demo-snapshot.yaml`, `demo_dir`, docs) together, not
  as a standalone migration. `universes/` was rejected: ambiguous vs
  `universes.json` / `audit/universes-*.json`, and `audit/` is also per-universe.
- **Naming mismatch** — universe id `federal-contractors` (hyphen) vs path
  `federal_contractors` (underscore) is pre-existing; normalizing would
  balloon the data move → out of scope.
- **`series/yield_curve/sp500/`** — arrives with
  [#288](https://github.com/qte77/analyze-stock-kpi/issues/288), not here.
- Aggregated/enhanced audits are write-only (only the federal-contractors
  audit is read by the UI), so moving them carries no 404 risk.

## References

- PRs [#287](https://github.com/qte77/analyze-stock-kpi/pull/287),
  [#297](https://github.com/qte77/analyze-stock-kpi/pull/297),
  [#300](https://github.com/qte77/analyze-stock-kpi/pull/300),
  [#303](https://github.com/qte77/analyze-stock-kpi/pull/303),
  [#304](https://github.com/qte77/analyze-stock-kpi/pull/304).
- Adjacent plans: [merge-longterm-charts](merge-longterm-charts.md) (#288),
  [consolidate-ui-tooling](consolidate-ui-tooling.md) (#289).
