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
- **Shipped after v1.4.0** (2026-09-25): #435 (`country` on snapshots, #419 step 1), #437
  (bump syncs `uv.lock`), #438 (complexipy unpinned + baseline), #441 (`make preview` via Vite,
  #415), #442 (plan 010), #443/#444 (`llms.txt`, #416), #445 (touch scroll hint, #417), #440 (SBOM).
- **What's next, in order:**
  1. #419 step 2 = **draft PR #436**. Merge it only after the Sun 2026-09-27 demo-snapshot run
     has written `country` to `data` (check `git show origin/data:results/demo/<u>/2026-09-27.json`),
     rebased and green; the Sat 2026-10-03 cron then rebuilds series B once. Verify that rebuild.
  2. #446, the backtest audit (owner request). Its findings shape plan 010's slice 3; plan 010's
     slices 0-2 don't depend on it and can go first.
  3. The UI redesign (approved), incl. #426: [plan 010](010-ui-redesign-progressive-disclosure.md).
  4. #418, the private cache, once the owner has stored the `CACHE_REPO_TOKEN` secret.
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
| Preview targets | `Makefile:130/135` |
| `llms.txt` template | `.github/templates/llms.txt.tpl` |
| Wide-table scroll container | `ui/style.css` `.table-wrap` |

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| Country-based filing lag [#419](https://github.com/qte77/analyze-stock-kpi/issues/419). Step 1 shipped: `FundamentalsSnapshot.country` (PR #435). Step 2 is **draft PR #436** (lag rule + `_METHOD_VERSION_B` bump); rebase it on `main`, then merge only **after** a demo-snapshot run has written `country` to `data` (next cron Sun 2026-09-27 06:15 UTC), or the Saturday rebuild runs without countries | agent | country lookup with suffix fallback, tested; `method_version` bumped; one rebuild verified on `data` |
| ~~Dependabot python-deps [#411](https://github.com/qte77/analyze-stock-kpi/pull/411)~~ | agent | shipped 2026-09-25, PR #431: applied 7 of 8 bumps; `complexipy` pinned to 5.5.0 (its 6.x/7.x/8.x scorer flags unchanged functions — see PR #431) |
| ~~Dependabot `setup-uv` [#412](https://github.com/qte77/analyze-stock-kpi/pull/412)~~ | agent | shipped 2026-09-25: its CI was green (the allow-list accepts the new SHA); merged, and `validate` passes on `main` |
| ~~`bump-my-version.yaml` doesn't sync the project's own version in `uv.lock`~~ | agent | shipped 2026-09-25, PR #437: a multiline `[[tool.bumpversion.files]]` entry for `uv.lock` in `pyproject.toml`; a `--dry-run` shows it bumped (confirm on the next real bump) |
| ~~Radar labels + inert row detail in Simple view [#426](https://github.com/qte77/analyze-stock-kpi/issues/426)~~ | agent | moved to plan 010, slice 5 |
| ~~UI redesign: positioning + progressive disclosure~~ | agent | moved 2026-09-25 to [plan 010](010-ui-redesign-progressive-disclosure.md) (UX review done; slices 0-7 open there) |
| ~~Unpin `complexipy`~~ | agent | shipped 2026-09-25, PR #438: `complexipy>=8.0.1`; the gate stays at 10, and the 11 functions that exceed it only because 6.x+ scores comprehensions (probe: the same comprehensions score 0 in 5.5.0, 4 in 8.0.1) are baselined in `complexipy-snapshot.json`; `make validate` green |
| ~~`make preview` serves `ui/public` [#415](https://github.com/qte77/analyze-stock-kpi/issues/415)~~ | agent | shipped 2026-09-25, PR #441: both preview targets run Vite's dev server (URL `/analyze-stock-kpi/`); `preview_local` reads local `results/` via `<base>/@fs/<repo>` (`server.fs.allow` adds only `../results`). Headless check: 4 Chart.js instances on desktop and phone |
| ~~Scroll hint on touch devices [#417](https://github.com/qte77/analyze-stock-kpi/issues/417)~~ | agent | shipped 2026-09-25: `ui/scroll_hint.js` sets `.overflow-right` while columns are hidden to the right; `style.css` masks the edge under `(pointer: coarse)`. e2e: on for phone (both views) and tablet (Detailed), off when the table fits, off at the scroll end |
| ~~`llms.txt` template up to date [#416](https://github.com/qte77/analyze-stock-kpi/issues/416)~~ | agent | shipped 2026-09-25, PR #443: the template lists ADRs 0000-0014 and every module; `tests/test_llms_txt_template.py` fails on a missing one. The `llms-txt` workflow regenerates `ui/public/llms.txt` on merge |
| Backtest audit [#446](https://github.com/qte77/analyze-stock-kpi/issues/446) (owner request 2026-09-25): re-verify prices, allocation, rebalance dates and metrics; SPY benchmark; long/short/combined separation; simplify. Verified so far: series A's irregular snapshot grid makes `monthly` trade 06-01 and 06-08 and `weekly` trade 06-08 three times; SPY is only a beta number; legs only as two annualized columns; series A metrics are `null` until 12 months | agent (rule changes → `method_version` bump) | every checklist item on #446 has a finding and a fix or an explicit keep; the UI outcome feeds plan 010 slice 3 |
| Private cache repo [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) | owner → agent | two consecutive runs show the cache growing and B's start date stable |
| US-only SEC-XBRL extension to ~2017 | owner (deferred) | only if the owner asks for a longer US series |
