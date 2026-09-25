# 009 — Backtest carry-over after plan 008

Issues [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) ·
[#419](https://github.com/qte77/analyze-stock-kpi/issues/419) ·
[#415](https://github.com/qte77/analyze-stock-kpi/issues/415) ·
[#416](https://github.com/qte77/analyze-stock-kpi/issues/416) ·
[#417](https://github.com/qte77/analyze-stock-kpi/issues/417). This plan takes over the open rows of
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
- **What's next, in order:**
  1. #419, the country-based filing lag (agent). It changes series B's inputs, so it needs a
     `method_version` bump and one rebuild. Do it before series B accumulates much new history.
  2. #415 and #417, small UI/build fixes (agent).
  3. #416, the `llms.txt` template (agent).
  4. #418, the private cache, once the owner has created the repo and token.
- **Loop:** a new branch per topic → RED test → `make validate` → changelog fragment → strike the row
  here → PR → admin squash-merge on green (`gh pr update-branch` first if the PR is BEHIND; never
  change rulesets) → delete the remote and local branches.
- **Watch-outs:**
  - A change to the ranking inputs rewrites frozen history only through a `method_version` bump,
    once and deliberately.
  - Never commit raw Yahoo prices or statements.
  - `make preview` doesn't render charts until #415 is fixed; use `npm run dev`.
- **Owner gates:** #418 (create a private repo + a fine-grained PAT secret). The US-only SEC-XBRL
  extension is deferred until the owner asks for it.

## Source map

| What | Where |
|---|---|
| Filing lag (D18) | `src/analyze_stock_kpi/orchestrators/longshort_backtest.py`: `_filing_lag_days` and the known-issuer list |
| `country` per ticker | **not stored today** (verified 2026-09-25: absent from the `data` snapshots). yfinance `Ticker.info["country"]` has it. Add it as a `FundamentalsSnapshot` field (`src/analyze_stock_kpi/data_sources/fundamentals.py`), or read it in the backtest's `fetch_frames` |
| Rebuild switch | `_METHOD_VERSION_B` in `longshort_backtest.py` |
| Statement cache layout | `results/prices/statements/<TICKER>/<fetch-date>.json` (gitignored; earliest fetch wins) |
| Cron | `.github/workflows/portfolio.yaml`; commit helper `scripts/data-branch-commit.cjs` |
| Preview targets | `Makefile:130/135` |
| `llms.txt` template | `.github/templates/llms.txt.tpl` |
| Wide-table scroll container | `ui/style.css` `.table-wrap` |

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| Country-based filing lag [#419](https://github.com/qte77/analyze-stock-kpi/issues/419) | agent | country lookup with suffix fallback, tested; `method_version` bumped; one rebuild verified on `data` |
| `make preview` serves `ui/public` [#415](https://github.com/qte77/analyze-stock-kpi/issues/415) | agent | charts render under `make preview` |
| Scroll hint on touch devices [#417](https://github.com/qte77/analyze-stock-kpi/issues/417) | agent | a hint shows only on overflow; checked in the e2e on a tablet and a phone |
| `llms.txt` template up to date [#416](https://github.com/qte77/analyze-stock-kpi/issues/416) | agent | every ADR and module listed, or generated from the tree |
| Private cache repo [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) | owner → agent | two consecutive runs show the cache growing and B's start date stable |
| US-only SEC-XBRL extension to ~2017 | owner (deferred) | only if the owner asks for a longer US series |
