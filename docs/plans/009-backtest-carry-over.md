# 009 — Backtest carry-over after plan 008

Issues [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) ·
[#419](https://github.com/qte77/analyze-stock-kpi/issues/419) ·
[#415](https://github.com/qte77/analyze-stock-kpi/issues/415) ·
[#416](https://github.com/qte77/analyze-stock-kpi/issues/416) ·
[#417](https://github.com/qte77/analyze-stock-kpi/issues/417) ·
[#426](https://github.com/qte77/analyze-stock-kpi/issues/426). This plan takes over the open rows of
[plan 008](008-pit-longshort-backtest.md), which is closed.

## Status and handoff (read first)

- **Shipped in 008** (all merged by 2026-09-25):
  - #402/#407: the plan;
  - #403/#410: the dashboard;
  - #404/#414: the engine, series A, freeze, filing lag, yearly cadence, rebalance log and the
    foresight-audit fixes;
  - #409: the close-download retry.

  `portfolio.yaml` rebuilt series B once (`method_version` 2) and wrote series A. The weekly cron
  (Sat 12:00 UTC) now only appends.
- **Released: v1.4.0** (2026-09-25, tag on `5fb3539`, the SBOM refreshed in #425). #401 is closed.
  Verified after the release:
  - the qte77 Score matches across all 83 tickers that appear on more than one list (2026-09-25
    snapshots);
  - the live e2e passed on desktop, iPad and iPhone, both orientations, light and dark;
  - the URL-filter fix is confirmed live.
- **Released: v1.5.0** (2026-09-29, tag on `f6425bf`, bump PR #463 synced `uv.lock` by itself,
  confirming #437; SBOM refreshed in #464). Contents: the country filing lag (#436), the
  rebalance-schedule fix (#452), plan 010 slices 0–3, the retired screener lists (#460), the
  CI split (#455) and the fail-fast Makefile (#457).
- **Shipped after v1.4.0** (2026-09-25): #435 (`country` on snapshots, #419 step 1), #437
  (bump syncs `uv.lock`), #438 (complexipy unpinned + baseline), #441 (`make preview` via Vite,
  #415), #442 (plan 010), #443/#444 (`llms.txt`, #416), #445 (touch scroll hint, #417), #440 (SBOM).
- **Rebuilds verified** (2026-09-29): a manually dispatched `portfolio` run (36616450294,
  23.5 min, data commit `7b3c947`) logged both one-time rebuilds (B → 3, A → 2). Checks passed:
  - both summaries are at the new versions with the new caveats, and B's `start` is unchanged
    (2023-05-05);
  - no duplicate or backwards trade dates in any trade log of either series, and every trade is
    after its rank date;
  - series A's weekly cadence is one rebalance per ISO week (05-31 … 07-12, 09-27);
  - file counts on `data` are unchanged.

  Effect on B's monthly net: 8.52 % → 7.97 % a year, t-stat 0.92 → 0.88, null percentile
  97.7 → 98.1.
- **What's next, in order:**
  1. The UI redesign (approved), incl. #426 and #446's presentation items:
     [plan 010](010-ui-redesign-progressive-disclosure.md).
  2. #418, the private cache, once the owner has stored the `CACHE_REPO_TOKEN` secret.
- **Offloading to the cloud (optional):** `claude --cloud` needs an interactive TTY, so it fails
  from an agent's Bash. Use a one-time routine instead (`/schedule` → `RemoteTrigger`, environment
  "Default"). Good candidates are #416, #415 and #417, which need no Yahoo/SEC network and no
  polyfetch. **Blocked** until the owner connects GitHub to their Claude account
  (<https://claude.ai/connect-github> or `/web-setup`). Keep merges and releases local.
- **Loop:** a new branch per topic → RED test → `make validate` → changelog fragment → strike the row
  here → PR → admin squash-merge on green (`gh pr update-branch` first if the PR is BEHIND; never
  change rulesets) → delete the remote and local branches.
- **Watch-outs:**
  - A change to the ranking inputs rewrites frozen history only through a `method_version` bump,
    once and deliberately.
  - Never commit raw Yahoo prices or statements.
  - `make preview` serves `http://localhost:8000/analyze-stock-kpi/` (Vite, #415). In a
    Patchright `page.evaluate`, pass `isolated_context=False` to see page globals like `Chart`.
- **Owner gates:**
  - #418: the private repo `qte77/analyze-stock-kpi-cache` exists (2026-09-25). Still needed: a fine-grained PAT scoped to it, stored as the `CACHE_REPO_TOKEN` secret (steps on #418).
  - Connect GitHub to the Claude account, only if you want cloud offloading.
  - The US-only SEC-XBRL extension is deferred until the owner asks for it.

## UI redesign

Moved to [plan 010](010-ui-redesign-progressive-disclosure.md) (2026-09-25), with the
wireframe, the UX review, the defaults and the slices.

## Source map

| What | Where |
|---|---|
| Filing lag (D18) | `src/analyze_stock_kpi/orchestrators/longshort_backtest.py`: `_filing_lag_days` and the known-issuer list |
| `country` per ticker | `FundamentalsSnapshot.country` (`src/analyze_stock_kpi/data_sources/fundamentals.py`), from yfinance `info["country"]`; in `data` snapshots from the first demo-snapshot run after it merged. The backtest reads snapshots via `_load_snapshot_list` in `longshort_backtest.py` |
| Rebuild switch | `_METHOD_VERSION_B` in `longshort_backtest.py` |
| Statement cache layout | `results/prices/statements/<TICKER>/<fetch-date>.json` (gitignored; earliest fetch wins) |
| Cron | `.github/workflows/portfolio.yaml`; commit helper `scripts/data-branch-commit.cjs` |
| Preview targets | `Makefile` `preview` / `preview_local` (Vite dev server, #441) |
| `llms.txt` template | `.github/templates/llms.txt.tpl` |
| Wide-table scroll container | `ui/style.css` `.table-wrap` |

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| ~~Country-based filing lag [#419](https://github.com/qte77/analyze-stock-kpi/issues/419)~~ | data | shipped: PRs #435, #436. Rebuild verified 2026-09-29 (run 36616450294, data commit `7b3c947`; see "Rebuilds verified") |
| ~~Dependabot python-deps [#411](https://github.com/qte77/analyze-stock-kpi/pull/411)~~ | agent | shipped 2026-09-25, PR #431: applied 7 of 8 bumps; `complexipy` pinned to 5.5.0 (its 6.x/7.x/8.x scorer flags unchanged functions — see PR #431) |
| ~~Dependabot `setup-uv` [#412](https://github.com/qte77/analyze-stock-kpi/pull/412)~~ | agent | shipped 2026-09-25: its CI was green (the allow-list accepts the new SHA); merged, and `validate` passes on `main` |
| ~~`bump-my-version.yaml` doesn't sync the project's own version in `uv.lock`~~ | agent | shipped 2026-09-25, PR #437: a multiline `[[tool.bumpversion.files]]` entry for `uv.lock` in `pyproject.toml`; a `--dry-run` shows it bumped (confirm on the next real bump) |
| ~~Radar labels + inert row detail in Simple view [#426](https://github.com/qte77/analyze-stock-kpi/issues/426)~~ | agent | moved to plan 010, slice 5 |
| ~~UI redesign: positioning + progressive disclosure~~ | agent | moved 2026-09-25 to [plan 010](010-ui-redesign-progressive-disclosure.md) (UX review done; slices 0-7 open there) |
| ~~Unpin `complexipy`~~ | agent | shipped 2026-09-25, PR #438: `complexipy>=8.0.1`; the gate stays at 10, and the 11 functions that exceed it only because 6.x+ scores comprehensions (probe: the same comprehensions score 0 in 5.5.0, 4 in 8.0.1) are baselined in `complexipy-snapshot.json`; `make validate` green |
| ~~`make preview` serves `ui/public` [#415](https://github.com/qte77/analyze-stock-kpi/issues/415)~~ | agent | shipped 2026-09-25, PR #441: both preview targets run Vite's dev server (URL `/analyze-stock-kpi/`); `preview_local` reads local `results/` via `<base>/@fs/<repo>` (`server.fs.allow` adds only `../results`). Headless check: 4 Chart.js instances on desktop and phone |
| ~~Scroll hint on touch devices [#417](https://github.com/qte77/analyze-stock-kpi/issues/417)~~ | agent | shipped 2026-09-25: `ui/scroll_hint.js` sets `.overflow-right` while columns are hidden to the right; `style.css` masks the edge under `(pointer: coarse)`. e2e: on for phone (both views) and tablet (Detailed), off when the table fits, off at the scroll end |
| ~~`llms.txt` template up to date [#416](https://github.com/qte77/analyze-stock-kpi/issues/416)~~ | agent | shipped 2026-09-25, PR #443: the template lists ADRs 0000-0014 and every module; `tests/test_llms_txt_template.py` fails on a missing one. The `llms-txt` workflow regenerates `ui/public/llms.txt` on merge |
| ~~Backtest audit [#446](https://github.com/qte77/analyze-stock-kpi/issues/446): verification + rebalance-schedule fix~~ | agent | shipped 2026-09-28 (fix/backtest-rebalance-schedule): findings on #446 (metrics, allocation and prices verified; three schedule bugs fixed; series A `method_version` 2 with a new rebuild switch; total-return caveat). The presentation items (SPY line, leg sign, which metrics, empty state) moved to plan 010 slice 3 |
| ~~Screener long/short lists decision [#413](https://github.com/qte77/analyze-stock-kpi/issues/413)~~ | owner → agent | shipped 2026-09-29, PR #460: retired (shorts empty on every snapshot date, longs 0–3); ADR-0014 amendment |
| Private cache repo [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) | owner → agent | two consecutive runs show the cache growing and B's start date stable |
| LatAm (Brazil) universe [#312](https://github.com/qte77/analyze-stock-kpi/issues/312): its revisit trigger fired (yfinance 1.4.1 → 1.7.0 in `uv.lock`) | agent | re-probe the blocked symbols on 1.7.0; either ship the universe or record on #312 that it's still blocked (with the probe output) |
| Lint MD startup_failure [#391](https://github.com/qte77/analyze-stock-kpi/issues/391): fails before any job starts on every run (57/57 since 09-25); blocks nothing | agent | root cause found and fixed, or the workflow replaced by the local `lint_md` + `lint_links` targets in `validate`/`ui` jobs |
| Plan convention write-up [#294](https://github.com/qte77/analyze-stock-kpi/issues/294): about 80 % already practised (plans record issue headers, roadmap links plans, CONTRIBUTING references `docs/plans/`) | owner → agent | owner says yes/no; if yes, `docs/plans/README.md` states the convention and the issue closes |
| US-only SEC-XBRL extension to ~2017 | owner (deferred) | only if the owner asks for a longer US series |
