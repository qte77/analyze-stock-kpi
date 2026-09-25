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
- **What's next, in order:**
  1. #419, the country-based filing lag (agent). It changes series B's inputs, so it needs a
     `method_version` bump and one rebuild. Do it before series B accumulates much new history.
     `country` is **not** stored today; capture it from yfinance `info` first (see the source map).
  2. #411 (Dependabot, 8 Python updates): **CI fails**, and it changes only `uv.lock`. Find which
     bump breaks lint/types/tests on a branch, fix or pin it, then merge on green.
  3. #415, #417, #426: small UI/build fixes (agent; run the polyfetch e2e for #417/#426).
  4. #416, the `llms.txt` template (agent).
  5. #418, the private cache, once the owner has created the repo and token.
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
  - `make preview` doesn't render charts until #415 is fixed; use `npm run dev`.
- **Owner gates:**
  - #418: create a private repo + a fine-grained PAT secret.
  - Connect GitHub to the Claude account, only if you want cloud offloading.
  - Approve or adjust the UI redesign proposal (§UI redesign proposal) before any UI rework starts.
  - The US-only SEC-XBRL extension is deferred until the owner asks for it.

## UI redesign proposal (owner feedback 2026-09-25: "overwhelming and convoluted")

The page stacks three products at equal weight: market sentiment, a research backtest and a stock
screener. The proposal is to make the ranking the product and reveal everything else in three
layers. It is a proposal only, awaiting the owner's go-ahead (see the table row). It changes layout
and emphasis only: the data, URL parameters (`ui/lib/state.js`) and EyeRest theme stay as they are.

**Positioning line:** "qte77 ranks ~320 stocks by one quality score, shows today's best and worst
25, and tracks how that ranking would have performed."

Layer 1, what everyone sees (the list and chart values are illustrative):

```text
+--------------------------------------------------------------------------+
| qte77 · stock quality ranking               [Fear 32 v]  [theme]  [?]    |
| <positioning line>                                                       |
+--------------------------------------------------------------------------+
|  TODAY'S PICKS (date)                                                    |
|  +------------------------------+  +------------------------------+      |
|  | BEST 25          qte77 Score |  | WORST 25         qte77 Score |      |
|  | ticker  name              86 |  | ticker  name              11 |      |
|  | ... [show all 25 v]          |  | ... [show all 25 v]          |      |
|  +------------------------------+  +------------------------------+      |
|  DOES IT WORK?                                                           |
|  +--------------------------------------------------------------------+  |
|  |  one chart: the headline backtest line (100-based)                 |  |
|  +--------------------------------------------------------------------+  |
|  "Long best 25 / short worst 25: +8 % a year after costs since 2023.     |
|   Not statistically significant. Hypothetical, not investment advice."   |
|  [How it's tested >]                    [Browse all stocks >]            |
+--------------------------------------------------------------------------+
| Methodology · Data sources · GitHub · Report an issue                    |
+--------------------------------------------------------------------------+
```

Layer 2, one click away:

- **Fear & Greed chip** → a dropdown with the score, deltas, and the 30d / long-term / 5s10s tabs.
- **How it's tested** → the metrics table (gross/net), other cadences on demand, the rebalance log,
  caveats and series B.
- **Browse all stocks** → the universe table in Simple view (5–6 columns), with picker, date, filter,
  CSV and the sector donut collapsed. A row click opens the side panel in Simple view too (#426).

Layer 3, reference: a Methodology drawer or page holding "What the qte77 Score measures", "Why these
universes", "Why these charts", the backtest rules, the look-ahead audit, all caveats and ADR links.

| Current element | New home |
|---|---|
| F&G section (3 tabs, big charts) | header chip + dropdown (layer 2) |
| "Why these charts?" / "Why these universes?" | Methodology (layer 3) |
| Backtest series A/B blocks, tables, key facts | one chart + one line (layer 1), details in layer 2 |
| Series B, rebalance log, caveats | "How it's tested", collapsed |
| "Current candidates" + "Latest best/worst 25" | merged into Today's picks (layer 1) |
| Universe table, picker, donut, CSV | "Browse all stocks" (layer 2) |

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
| ~~Dependabot python-deps [#411](https://github.com/qte77/analyze-stock-kpi/pull/411)~~ | agent | shipped 2026-09-25, PR #431: applied 7 of 8 bumps; `complexipy` pinned to 5.5.0 (its 6.x/7.x/8.x scorer flags unchanged functions — see PR #431) |
| ~~Dependabot `setup-uv` [#412](https://github.com/qte77/analyze-stock-kpi/pull/412)~~ | agent | shipped 2026-09-25: its CI was green (the allow-list accepts the new SHA); merged, and `validate` passes on `main` |
| `bump-my-version.yaml` doesn't sync the project's own version in `uv.lock` (v1.4.0 shipped with 1.3.0 there; fixed by hand in #427) | agent | the next bump leaves `uv.lock`'s `analyze-stock-kpi` version equal to `pyproject.toml` |
| Radar labels + inert row detail in Simple view [#426](https://github.com/qte77/analyze-stock-kpi/issues/426) | agent | both addressed or decided; checked in the phone e2e |
| UI redesign: positioning + progressive disclosure (see §UI redesign proposal) | owner (approve direction) → agent | the owner approves or adjusts the wireframe; then a plan 010 with a UX review (a `frontend-design` skill or usability-audit subagent) and the polyfetch e2e on phone and desktop as the done-when |
| `make preview` serves `ui/public` [#415](https://github.com/qte77/analyze-stock-kpi/issues/415) | agent | charts render under `make preview` |
| Scroll hint on touch devices [#417](https://github.com/qte77/analyze-stock-kpi/issues/417) | agent | a hint shows only on overflow; checked in the e2e on a tablet and a phone |
| `llms.txt` template up to date [#416](https://github.com/qte77/analyze-stock-kpi/issues/416) | agent | every ADR and module listed, or generated from the tree |
| Private cache repo [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) | owner → agent | two consecutive runs show the cache growing and B's start date stable |
| US-only SEC-XBRL extension to ~2017 | owner (deferred) | only if the owner asks for a longer US series |
