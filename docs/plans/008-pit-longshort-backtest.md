# 008 — Point-in-time backfilled best/worst 25 + backtested equal-weight L/S book

Issue [#401](https://github.com/qte77/analyze-stock-kpi/issues/401) (tracking) — owner request
2026-09-23. This plan closes arc [007](007-longshort-portfolio-and-multiwindow-sortino.md): its open rows
migrated here (see the table).

> **Arc closed 2026-09-25.** Everything in the table is shipped or migrated, and the open rows
> continue in [plan 009](009-backtest-carry-over.md). The rest of this file is the historical record.

## Handoff (read this first, then act; don't re-explore)

**Where things stand (2026-09-23):**

- `main` includes #392–#400: arc 007 shipped, the qte77 Score is unified, and the lists are re-ranked by
  it.
- `portfolio.yaml` (#395's forward Min-Variance tracker) was **never dispatched**. There is no data to
  migrate; this plan rewires it.
- Every design decision below is owner-approved or marked *default*. Do not re-litigate; the owner
  overrides at merge time.

**Your loop:**

1. **W0, C (#404) and D (#403) — done.** `portfolio.yaml` was first dispatched on 2026-09-24. **Current
   step:** PR E + PR F in parallel (D15–D19; owner 2026-09-24), with the same spawn/verify/merge loop as
   step 2 below, using the E/F branch names in their sections.
2. **Parallel (one message, two `Agent` calls, each `isolation: "worktree"`, base `main`):**
   - **PR C** — branch `feat/pit-backtest-core`. Prompt: "Implement §PR C of
     `docs/plans/008-pit-longshort-backtest.md` exactly, following §Decisions, §Frozen data contract and
     §Source map. Touch only the §Parallelism files for C. Strike only your own table row. Don't merge;
     report the PR URL + validate/e2e results."
   - **PR D** — branch `feat/pit-backtest-ui`. The same prompt with §PR D. It builds against the frozen
     contract with a local, uncommitted fixture and does not wait for C.
   - Add the repo gotchas to both prompts: the sandbox denies `ls/cat/grep`, so use `git ls-files` /
     `git grep`; push/`gh` via `env -u GH_TOKEN -u GITHUB_TOKEN`; never `--no-gpg-sign`/`--no-verify`;
     commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`; PR bodies end with
     `Generated with Claude <noreply@anthropic.com>`.
3. **On each agent report, verify it yourself before merging:**
   - Diff the PR against the plan.
   - Check CI green.
   - Confirm no raw prices or statement values appear in committed paths.
4. **Merge (standing owner rule):** once CI is green, `gh pr merge <n> --squash --admin --delete-branch`.
   If the PR is BEHIND, `gh pr update-branch <n>` and wait for `gh pr checks <n> --watch` first.
   **Never modify rulesets.**
5. **Clean up after each merge:**
   - `git worktree remove <path>`, `git branch -D <branch>`.
   - Confirm the remote branch is deleted.
   - `git pull --ff-only` on `main`.
6. **Phase C:** run the table's dispatch row, then file the two issue rows, then close the arc.

**Owner gates:** none left. Merges are pre-authorized on green CI. Deferred: the US-only SEC-XBRL
extension.

## Context

Arc 007 shipped a forward-only, Min-Variance long/short tracker (#395). Its cron never ran, so there is no
data to migrate. The owner now wants:

1. **Backfill** the aggregated best/worst 25 over past dates, ranked by the qte77 Score as computed from
   **the KPIs as they actually were on each date** (point-in-time; no look-ahead).
2. **A backtested theoretical book:** long best 25 / short worst 25, **equal weight 1/25**, marked **daily
   from closing prices**, extended forward by the cron under identical rules.

Inputs:

- A feasibility research agent (live-verified yfinance/SEC behaviour).
- An adversarial Fable review.
- Owner decisions 2026-09-23 (below).

## Git workflow (every branch: W0, C, D, and any follow-up)

- **A new branch per topic** (names in the Handoff). Commits are grouped **by topic** within the branch,
  Conventional Commits (`feat`/`fix`/`test`/`docs`/`chore`/`ci`), e.g. PR C =
  `docs:` ADR-0013 → `feat:` engine → `ci:` cron → `chore:` removals.
- **Push and squash-merge only once ALL CI checks AND the local test items pass**:
  - `make validate`;
  - the plan's done-when;
  - the e2e below, for UI PRs.
- Never merge on red or pending.
- **Delete stale branches after each merge, both remote AND local**: `--delete-branch` on merge,
  `git branch -D`, `git worktree remove` for agent worktrees, and
  `git ls-remote --heads origin <branch>` to confirm the remote branch is gone.

## UI e2e (PR D locally; Phase C remotely against Pages)

Use **polyfetch + its patchright Chromium** (sibling `../polyfetch-scrape`, see its `USING.md`).

- **Locally:** `npm run dev` in `ui/`, with the fixture.
- **Remotely:** `https://qte77.github.io/analyze-stock-kpi/`, after dispatch.

Every run must:

- **Vary viewport + device emulation:** at least desktop 1440×900, tablet, and a phone
  (e.g. iPhone 13).
- **Cover both orientations:** horizontal and vertical.
- **Click the interactive elements and verify both behaviour and appearance:**
  - the gross/net switch;
  - the latest-lists toggle;
  - the theme toggle;
  - the universe picker dropdown + date selector (a regression check on the table);
  - a table row (opens the detail panel, e.g. its Sortino rows).
- **Capture screenshots per state; videos opt-in** (record at least one run per orientation). Store them
  outside the repo, and list their paths in the report.
- **Use devtools:**
  - capture console errors and failed network requests;
  - **fail on app console errors**;
  - the only allowed 404s are the documented pre-first-run backtest files (local/empty state only; none
    remotely after dispatch).

## Docs, config surface & issues audit (checked 2026-09-23; this is where each item is done)

| Doc / surface | Update? | Owner PR | What |
|---|---|---|---|
| `changelog.d/` | **Yes** | C, D | 1.3.0 is the last release, so #395's fragment (`changelog.d/20260923_081923_…_longshort_portfolio.md`) is unreleased. **Rewrite that fragment** to describe the backtest instead of adding Added + Removed noise. D adds one `### Changed` fragment for the dashboard section. Never hand-edit `CHANGELOG.md`. |
| `README.md` | **Yes** | C | Remove the `portfolio` optional-extra note (added by #397). Replace the model-portfolio bullet with the backtest (hypothetical, point-in-time, equal-weight 25/25, gross/net). |
| CLI switches | No new ones | — | The backtest is a module entrypoint (`python -m analyze_stock_kpi.orchestrators.longshort_backtest`), documented in `architecture.md` like `sentiment.py` (`docs/architecture.md:52`). `--sortino-from/--sortino-to` are already in README:48-52. |
| Env vars | No new docs needed | C | New `config.py` path fields are `SSK_`-overridable automatically. Precedent: only the generic line (README:46, `architecture.md:45`); no per-var table exists except `SSK_SEC_USER_AGENT`. Remove the four `portfolio_*` fields (`config.py:50-56`). |
| URLs | No new external URLs | C | yfinance only. The new **data-branch paths** (§Frozen contract) go into `architecture.md` + `data-sources.md`. The Pages URL is unchanged. |
| `docs/architecture.md` | **Yes** | C | Module tree: drop `portfolio_optimizer.py`/`longshort_portfolio.py`, add `longshort_backtest.py`. Failure table: yfinance statements/prices wrap-degrade → the run skips its commit. The cron paragraph covers the Sat 12:00 full recompute. |
| `docs/data-sources.md` | **Yes** | C | Replace #395's portfolio guardrail row: publish returns/scores/ranks/metrics only, never raw prices **or statement line items**, cached locally in gitignored `results/prices/`. |
| ADRs | **Yes** | C | New ADR-0013 (D14); ADR-0012 status "Superseded in part by ADR-0013"; `docs/decisions/README.md` row. |
| `docs/roadmap.md` | **Yes** | C | Mark the #395 entry "superseded by the point-in-time backtest (plan 008)" and add an `[x]` line on ship. Don't rewrite history. |
| `docs/UserStory.md` | **Yes** | C | #397's #395 bullet → the backtest story (backfilled best/worst 25 + L/S book). |
| `docs/plans/` | **Yes** | W0 | Add 008; close 007 (strike its shipped rows, migrate its open rows here); `docs/plans/README.md` row. |
| Dashboard explainers | **Yes** | D | `ui/index.html` "Why these charts?" (#397's model-portfolio text) → backtest. "Why these universes?": the aggregated lists are **no longer** the portfolio's pool (the backtest ranks all base universes with `score_bt` itself); fix that sentence. |
| `llms.txt` | Issue only | Phase C | The template is hand-maintained and missing ADR-0010..0013 → file an issue. |

**Issues** (live `gh issue list`, 2026-09-23; open: #391, #379, #368, #367, #328, #312, #294):

- **Open (W0):** a tracking issue "feat: point-in-time backfilled best/worst 25 + backtested L/S book
  (plan 008)". PRs C/D reference it; Phase C closes it with a summary. Record its number in this plan's
  header.
- **Update (W0):** comment on **#294** (the plan-convention discussion). The workspace rule now says
  `YYYY-MM-DD-NNNN-slug.md`, while the repo keeps `NNN-slug.md` (used for 008); the owner decides there.
- **Note (no action):** **#368** (rename `results/demo/` → `results/snapshots/`). D11's fidelity check
  reads `results/demo/`; whoever does #368 must repoint it.
- **Open (Phase C):** the two issue rows in the table.
- **Close:** none now. The old hedging epic #4/#8/#9/#10 is already closed (verified).

## Per-PR loop and watch-outs

- **Loop per PR (agents):** RED tests → implement → `make validate` (the exact CI gate) → changelog
  fragment → strike own row → push → PR. Don't merge.
- **Watch-outs:**
  - Never commit raw Yahoo payloads (prices or statement line items). Publish only returns, scores,
    ranks, weights and metrics.
  - The sandbox denies `ls/cat/grep`; use `git ls-files` / `git grep`.
  - Pin `uses:` to SHAs already in the repo.
  - `make preview` doesn't serve `ui/public/`; use `npm run dev` for e2e.

## Decisions (owner 2026-09-23 unless marked *default*)

| # | Decision |
|---|---|
| D1 | **Scope:** all base universes (every `PRESET_DIR/*.txt` except the derived `aggregated-scores-*`, `enhanced-kpi-screener-*` and `crypto-*`) = today's members, ~320 tickers. Start ≈ 2021–22 (computed, D6). Survivorship + "sp500 = today's top-100 by cap" size look-ahead disclosed. |
| D2 | **One reduced score, used for backfill AND the cron:** `score_bt = screener_score(snap_bt)`, where `snap_bt` is a `FundamentalsSnapshot` holding only the point-in-time-reconstructable inputs: `return_on_equity`, `return_on_assets`, `operating_margins`, `rd_to_revenue`, `current_ratio`, `sortino_ratio`. `forward_pe`, `trailing_peg_ratio` and `beta` are **always None**, so Valuation always drops and Risk = current ratio. The live score function is reused unchanged (DRY), with no seam because the input set never changes. The live qte77 Score (dashboard lists) is untouched. |
| D3 | **Point-in-time fundamentals:** yfinance annual `income_stmt` + `balance_sheet` (~4–5 FY, all regions, live-verified). A column is usable at date D iff `period_end + 90 days ≤ D` (no filing dates in yfinance). Ratios: ROE = Net Income / Stockholders Equity; ROA = Net Income / Total Assets; op margin = Operating Income / Total Revenue; R&D/rev; current = Current Assets / Current Liabilities. Row lookup reuses `_find_row` (`fundamentals.py:368`). Latest-restated values are a disclosed caveat. |
| D4 | **Sortino at D** = `_compute_sortino` (`fundamentals.py:207`) on the ticker's closes over (D−1y, D], after `dropna()`. |
| D5 | **Book:** 25 long / 25 short, 1/25 each (gross 200 %, net 0). **Rank at the close of rank date t, trade at the close of the next trading day.** Weights drift between rebalances. Local-currency returns (no FX). Union trading calendar: a non-trading day = 0 return for that ticker. A missing price after entry = held at the last close (caveat). |
| D6 | **Rank grid = weekly (last trading day of each ISO week).** Start = first grid date with ≥ 200 eligible tickers (`score_bt` not None + ≥ 1y of closes). |
| D7 | **Cadences (Fable set), all on the weekly grid:** **monthly = PRIMARY** (first grid date of each month); quarterly-after-filings (first grid date on/after Feb 15, May 15, Aug 15, Nov 15); monthly-with-buffer (keep a holding while its rank ≤ 40 from its end, refill from the top ranks); weekly; buy-and-hold (rank once at start). Presented as one table with the primary highlighted, never a sortable leaderboard. |
| D8 | **Costs:** 10 bp × one-way turnover (½ Σ\|w_new − w_drifted\| over both legs) charged on the trade day. Publish **gross and net**. |
| D9 | **Metrics per cadence (gross + net):** annualized return, vol, max drawdown, annualized one-way turnover, long vs short leg annualized returns, realized beta to SPY (daily L/S on SPY returns; SPY closes in memory via `equity_spy._fetch_history_closes`, `equity_spy.py:82`), monthly hit rate, mean monthly return with 90 % CI and t-stat. Nothing is annualized from < 12 months. |
| D10 | **Null benchmark** *(default)*: 1,000 random 25/25 books drawn from the same eligible set on the primary cadence's rank dates (seeded, deterministic); report the strategy's net-return percentile. |
| D11 | **Fidelity** *(default)*: on each genuine data-branch snapshot date (`results/demo/<u>/<date>.json`, 2026-05-22…07-12, 09-21/22), Spearman ρ between the tickers' `score_bt` and the live `screener_score`; report per date + the median. Verify pandas' spearman needs no scipy. |
| D12 | **Drop Min-Variance + scipy:** delete `domain/portfolio_optimizer.py`, `orchestrators/longshort_portfolio.py`, their tests, the `portfolio` optional extra (`pyproject.toml:17-22`), and the config fields `config.py:50-56` (replace them with backtest paths). Revert `validate.yaml:30` → `uv sync --group dev --group test` and `Makefile:37` → `uv sync`. Keep `.gitignore` `results/prices/` (the local price/statement cache). |
| D13 | **Cron** *(default)*: `portfolio.yaml` runs `python -m analyze_stock_kpi.orchestrators.longshort_backtest`. It does a **full deterministic recompute** each run (stateless, idempotent), cron `0 12 * * 6` (Sat 12:00 UTC; no other data-branch writer then). Reuse `_batch_close_prices` (`fundamentals.py:495`) for prices; this resolves the 007 dedupe row. |
| D14 | **ADR-0013** supersedes ADR-0012's "no backtest", Min-Variance, weekly/monthly-tracker and "no costs" decisions (point-in-time KPIs remove the look-ahead that justified "no backtest"). ADR-0012's status line gets "Superseded in part by ADR-0013". |
| D15 | **Two series, never spliced** (owner 2026-09-24). **Series A = headline:** genuine decisions. Series B = the reconstructed backfill (D1–D14, the as-built #404), labelled an approximation. |
| D16 | **Series A (genuine decisions):** each rank date = a genuine `data`-branch snapshot date (`results/demo/<base-universe>/<date>.json`, from 2026-05-31). Rank with the **full live qte77 Score** (all 9 inputs, as stored in the snapshot) by reusing `aggregated_scores_best_and_worst.build_universe(..., as_of=d)` unchanged (DRY; the same dedup + 14-day staleness gate as the live lists), giving the top/bottom 25. Trade at the close of the first trading day **strictly after** d, which is conservative, since snapshots are fetched ~06:15 UTC, after Asian closes. The same book rules (D5), costs (D8), metrics (D9) and cadences (D7) apply, on the snapshot grid instead of the weekly grid. Across a snapshot gap (e.g. 07-12 → 09-21) the book is held; this is disclosed. No null/fidelity for A until it has ≥ 12 monthly rebalances (the D9 rule). |
| D17 | **Freeze, append-only, both series** (owner 2026-09-24). Once a date's list or a day's return row is written, it is never recomputed. Each run only appends lists for new rank dates and rows for new days; the summary/metrics are recomputed from the frozen rows. A **`method_version` bump** is the only way to rebuild history. It is explicit, is logged in the summary's `caveats`, and is used exactly once for D18. This supersedes D13's "full deterministic recompute". |
| D18 | **Filing lag (series B):** 90 days for US tickers (no exchange suffix), **120 days for non-US** (any `.XX` suffix, e.g. `.DE`, `.SA`, `.T`, `.KS`), because 20-F and foreign filers publish later. It ships with a `method_version` bump, so B's history is rebuilt once and then frozen. |
| D19 | **Sortino stays** in both series' score. It is part of the qte77 Score (ADR-0004), and it's reconstructable from closes up to d only. |
| D20 | **Yearly cadence** (owner 2026-09-24): a sixth cadence, `yearly` = the first grid/genuine-date of each calendar year, added to both series (cadence order: monthly [primary], quarterly_filings, monthly_buffer, weekly, yearly, buy_hold). Caveat: it rebalances once a year, so its metrics stay `null` far longer than the other cadences' (D9's 12-month floor still applies). |
| D21 | **Rebalance log** (owner 2026-09-24): a new per-cadence, per-series contract (`results/backtest{,_genuine}/trades/<cadence>/YYYY.json`) recording WHEN each rebalance happened, WHY (`reason`), and WHICH tickers entered/exited each leg with their rank + score at the rank date. `reason` ∈ {`initial`, `scheduled_weekly`, `scheduled_monthly`, `quarterly_after_filings`, `scheduled_yearly`, `buffer_exit`, `buy_hold_initial`}; `buffer_exit` only fires for `monthly_buffer` when this rebalance actually dropped a held name for exceeding rank 40, else it falls back to `scheduled_monthly`. `rank` follows `aggregated_scores_best_and_worst.AuditRow`'s signed convention (`+1` best, `-1` worst); series A's EXITED entries are always `rank:null, score:null` (D16: `build_universe` exposes no full ranked pool to look an exited name's current rank up in) — series B always populates both, since it tracks the full pool. Frozen append-only like everything else (D17). |
| D22 | **Foresight audit** (owner 2026-09-24): every date-taking lookup already took `as_of` explicitly (D3/D4). Adds one explicitly-named guard function per data type — `_closes_as_of` (price) alongside the existing `_usable_column` (statement lag) — so an auditor has exactly two functions to check for a look-ahead leak, plus a regression test that poisons every statement period and closing price dated strictly after rank date t and asserts t's ranked list is byte-identical to an unpoisoned run. |

## Frozen data contract (`data` branch, derived only)

- `results/series/backtest/<cadence>/YYYY.json`, with cadence ∈ {`monthly`, `quarterly_filings`,
  `monthly_buffer`, `weekly`, `yearly`, `buy_hold`} (D20 adds `yearly`): a daily, date-sorted array of
  `{"date","ret_long","ret_short","ret_ls_gross","ret_ls_net","turnover"}`. `ret_short` is the short
  basket's price return, and `ret_ls = ret_long − ret_short`. Loadable via
  `loadYearsFromBranch(base, "results/series/backtest/monthly", "date", <startYear>)`.
- `results/backtest/lists/YYYY.json`: one entry per weekly rank date,
  `{"date","eligible":n,"best":[{"ticker","score"}×25],"worst":[…×25]}`. This is **the backfilled
  best/worst 25**, with `score` = `score_bt` rounded to 0.1.
- `results/backtest/trades/<cadence>/YYYY.json` (D21): one entry per rebalance for that cadence,
  date-sorted by `rank_date`:
  `{"rank_date","trade_date","reason","long":{"entered":[{"ticker","rank","score"}],"exited":[…]},"short":{…},"turnover"}`.
  `turnover` here is the static target-to-target one-way turnover (informational; ignores the
  intraperiod drift the daily series' cost-bearing turnover factors in).
- `results/backtest/summary.json`:
  - `method_version`, `as_of`, `start`, `universes[]`, `score_inputs[]`, `cost_bps`, `primary`;
  - `cadences{name:{gross:{…D9}, net:{…D9}, rebalances:n}}`;
  - `null{n, percentile, median_net_ann}`;
  - `fidelity{per_date:[{date, rho, n}], median_rho}`;
  - `caveats[]` (strings the UI renders verbatim).
- **Series A (D16), a parallel set with the same shapes:** `results/series/backtest_genuine/<cadence>/YYYY.json`,
  `results/backtest_genuine/lists/YYYY.json` (one entry per genuine snapshot date; `score` = the live
  qte77 Score), `results/backtest_genuine/trades/<cadence>/YYYY.json` (D21; exited entries' `rank`/`score`
  are always `null`) and `results/backtest_genuine/summary.json`. The same model, except `null` and
  `fidelity` may be `null` (D16). Series B keeps the paths above unchanged, so #403's UI keeps working.

## Source map

| What | Where |
|---|---|
| Score to reuse | `src/analyze_stock_kpi/domain/composite_scores.py:212-264` `screener_score`; bounds `:30-47` |
| Statement row lookup | `fundamentals.py:368-383` `_find_row`; existing latest-column readers `:386-472` (`_extract_two_rows`, `_read_rd_revenue`, `_read_fcf_revenue`) are templates, but the backtest needs **all columns** |
| Sortino | `fundamentals.py:207` `_compute_sortino`; `:276-307` `_windowed_sortinos` |
| Batched prices | `fundamentals.py:495-528` `_batch_close_prices(period="max")` |
| SPY closes (in memory) | `data_sources/equity_spy.py:82-112` `_fetch_history_closes` |
| Presets | `domain/universe.py:23` `PRESET_DIR`, `:68` `_read_symbol_file`; enumeration pattern `orchestrators/universe_audit.py:101` |
| Per-year persistence template | `data_sources/equity_spy.py:122-159` |
| Code to delete (#395) | `domain/portfolio_optimizer.py`, `orchestrators/longshort_portfolio.py`, `tests/test_portfolio_optimizer.py`, `tests/test_longshort_portfolio.py` |
| Cron to rewire | `.github/workflows/portfolio.yaml` (cron `:26`, sync `:69`, commit filter ~`:83`) |
| UI to replace (#395) | `ui/app.js:27-28, 157-172, 590-604`; `ui/index.html:145-167` (`#portfolio-section`), explainer `:141-142`; `ui/charts.js:10, 696-809`; `ui/lib/portfolio.js` (`compound` `:26` is reusable, `holdingsRows` `:68` is not); `ui/style.css` portfolio block; `ui/tests/portfolio.test.mjs` |
| Genuine snapshots (fidelity) | `origin/data:results/demo/<universe>/<date>.json` |
| Docs | `docs/decisions/0012-…md:3` status; `docs/decisions/README.md`; `docs/plans/README.md`; `docs/plans/007-…md` (close + migrate); `docs/architecture.md`; `docs/data-sources.md` guardrail row; `README.md` (remove the `portfolio` extra note) |

## PR C — core engine + cron + removals + docs (worktree agent)

- New `src/analyze_stock_kpi/orchestrators/longshort_backtest.py` (pydantic models for the contract). Its
  pure functions are individually testable:
  - `pit_fundamentals(frames, as_of) -> dict` (D3)
  - `score_at(fund, closes, as_of) -> float | None` (D2/D4)
  - `rank_dates(calendar)` (D6)
  - `rebalance_dates(cadence, grid)` (D7)
  - `select(ranks, cadence, prev_holdings)` (the buffer rule)
  - `simulate(weights_by_trade_date, returns) -> daily rows` (D5/D8)
  - `metrics(rows, spy)` (D9)
  - `null_percentile(...)` (D10)
  - `fidelity(...)` (D11)
- The I/O layer: `fetch_frames(ticker)` (yfinance statements, gitignored cache in `results/prices/`),
  `main()`.
- Delete/revert per D12, then do every docs row owned by **C** in §Docs audit (ADR-0013, ADR-0012
  status, README, architecture, data-sources, roadmap, UserStory, rewrite #395's changelog fragment).
- **Tests (RED first, no network):**
  - a period-end+90 d boundary (a column is not usable on day 89, usable on day 90);
  - `score_at` equals `screener_score` on a hand-built snapshot with valuation/beta None;
  - rank-at-t / trade-at-t+1 (no same-close look-ahead);
  - equal weights + drift math on a 3-ticker toy;
  - the cost = 10 bp × one-way turnover;
  - the buffer keeps rank 30 and drops rank 41;
  - the quarterly-after-filings date rule;
  - the start-date rule (≥ 200 eligible; use a small threshold param in tests);
  - a seeded null that is deterministic;
  - metrics on a known series;
  - persistence round-trip + same-run idempotence.
- **Done-when:**
  - `make validate` is green.
  - A local full run writes all three artifact kinds with start ≈ 2021–22.
  - No raw price/statement value appears in the committed paths.
  - The monthly net index and the fidelity median ρ are reported in the PR body.

## PR D — dashboard section (worktree agent)

- Replace `#portfolio-section` with "Backtested long/short 25/25 (hypothetical)":
  - **Chart:** primary monthly **net** index (bold) + gross (dashed) + four foils (thin). 100-based,
    compounded client-side with `compound()` (generalise the field param).
  - **One metrics table:** cadences as rows, primary highlighted, gross/net toggle via a simple switch,
    not sortable.
  - **Key facts line:** start date, realized beta, null percentile, fidelity median ρ.
  - **Latest best/worst 25:** from the last `lists` entry, collapsible.
  - **Caveats:** rendered from `summary.caveats`.
- Remove the #395 weekly/monthly loaders, `holdingsRows` and `renderPortfolioHoldings`.
- Update the two explainers per the **D** rows in §Docs audit, and add one changelog fragment.
- An empty state until the first run ("Backtest runs Saturdays").
- The pure helpers go in `ui/lib/portfolio.js` with vitest.
- Follow the EyeRest theme (no blue).
- **polyfetch e2e locally, per §UI e2e:** the empty state and a populated state (a local uncommitted
  fixture).
- **Done-when:** `make validate` green + local §UI e2e passes (screenshots + ≥ 1 video per orientation,
  no app console errors).

## PR E — series A + freeze + lag (worktree agent, branch `feat/pit-backtest-genuine`)

- `src/analyze_stock_kpi/orchestrators/longshort_backtest.py` (#404):
  - Add series A per D16. Reuse `build_universe` from `orchestrators/aggregated_scores_best_and_worst.py`, plus the existing `simulate`, `metrics` and `rebalance_dates`, generalized from the weekly grid to any date grid.
  - Add the D17 append-only persistence for both series: load the existing years, skip dates ≤ the last stored date, write only new entries, and recompute the summary from the stored rows.
  - Add the D18 suffix-based lag, and bump `method_version`.
  - **Fix the start-trim bug (found 2026-09-24 in #404's first run):** the B return series starts at
    **1962-01-02**, the union-calendar start, instead of `summary.start`, which is 2023-03-31.
    - The published year files hold ~15.7k pre-start zero-return days.
    - Every metric is diluted by them: the published ann. vol is 4.96 % and the hit rate 2.8 %. Over the
      real 907-day window the figures are ann. vol ≈ 21.2 %, ann. return ≈ 14.3 %, total +61.8 % and
      max DD −23.4 %.
    - The fix: emit rows only from the first trade date, compute metrics over that window only, and
      **delete the pre-start year files on `data`**. Verify that `scripts/data-branch-commit.cjs` can
      delete paths, or extend it.
    - Also investigate the 2026-03-18 short-basket move of −13.3 % in one day (a bad price or split?)
      and filter bad ticks if confirmed.
    - **Verdict (found 2026-09-24):** neither — `ICTEF`'s yfinance auto-adjusted closes are negative
      across roughly half its post-2023 history (not a split artefact; a split can never produce a
      negative price). The ticker is dropped entirely (any non-positive close excludes it) rather than
      patched point-by-point, since patching alone still manufactures a giant `ffill`-gap "return."
  - **Owner scope additions (2026-09-24, D20–D22):**
    - D20: a sixth `yearly` cadence for both series.
    - D21: a per-cadence, per-series rebalance log (`results/backtest{,_genuine}/trades/<cadence>/YYYY.json`)
      — WHEN/WHY/WHAT for every rebalance, frozen append-only like everything else.
    - D22: an explicit `_closes_as_of` foresight guard (paired with the existing `_usable_column`
      statement-lag guard) plus a poison-data regression test, for a separate falsify-then-verify
      look-ahead audit.
- `.github/workflows/portfolio.yaml`:
  - also check out `results/series/backtest_genuine/` and `results/backtest_genuine/` from `data`;
  - extend the commit regex to the A paths and to the D21 `trades/` paths.
- Docs:
  - ADR-0013 amendment (dated) for D15–D19;
  - the `architecture.md` + `data-sources.md` paths;
  - the changelog fragment (`### Changed`);
  - this plan's D20–D22 decision rows + contract lines (this PR owns `docs/**`).
- **Tests (RED first, no network):**
  - A ranks via `build_universe` on a hand-built 2-universe snapshot set;
  - the trade date is strictly after the snapshot date;
  - holdings persist across a snapshot gap;
  - an append-only re-run with no new dates leaves every file byte-identical;
  - a run with 1 new date appends exactly its rows and keeps earlier rows unchanged;
  - a `method_version` bump rebuilds once;
  - the lag is 90 days for `AAPL` and 120 days for `SAP.DE`, at the boundary day;
  - D20: `yearly` picks the first grid date of each calendar year;
  - D21: entered/exited diffing, the `reason` enum's branches (incl. `buffer_exit` only when
    flagged), per-cadence log construction for both series, and its append-only freeze;
  - D22: poisoning every statement period and closing price dated strictly after rank date t leaves
    t's ranked list byte-identical.
- **Done-when:**
  - `make validate` is green;
  - a local run writes both A and B artifacts;
  - A's start date is 2026-05-31 or later;
  - the PR body reports A's monthly net index and rebalance count.

## PR F — dashboard: A headline, B secondary (worktree agent, branch `feat/pit-backtest-ui-genuine`)

- `ui/**` only:
  - The section headline becomes **Series A** ("Genuine decisions since 2026-05-31"): its chart, metrics table, key facts and latest best/worst 25.
  - **Series B** moves into a collapsible "Reconstructed backfill since 2023 (approximation)" block, with its fidelity ρ and null percentile, and a caveat saying it is **not** the live qte77 Score (6 of 9 inputs).
  - Neither series is ever drawn on the same axis as a continuation of the other.
  - A's empty state must be clean if the A paths 404.
- Reuse the `ui/lib/portfolio.js` helpers, parameterized by path prefix.
- vitest for the helpers.
- The full §UI e2e locally (a fixture for A under `/tmp`, outside the repo).
- A changelog fragment.

## Parallelism

| PR | Files |
|---|---|
| C | `src/**`, `tests/**` (Python), `pyproject.toml`, `uv.lock`, `Makefile`, `.github/workflows/{portfolio,validate}.yaml`, `docs/**`, `README.md`, own changelog |
| D | `ui/**` only, own changelog |
| E | `src/**`, Python `tests/**`, `.github/workflows/portfolio.yaml`, `docs/**` (except this plan's other rows), own changelog |
| F | `ui/**` only, own changelog, plus its own row here |

## Foresight audit 2026-09-24 (independent falsify-then-verify review of PR E)

A separate audit agent probed the point-in-time engine for look-ahead. Its own poison test — corrupt
every statement period and closing price dated after rank date t, assert t's ranked list is
unchanged — **passed**: strict look-ahead is refuted. It also found 8 real, narrower defects the
`method_version` rebuild would otherwise have frozen into published history. Fixed in PR E, each
with its own RED test: a NaN input silently scoring 100 (#1, also patched at the shared
`composite_scores` boundary); an unfiltered interior NaN gap distorting Sortino (#2); a >50%
single-day return glitch beyond the already-excluded `ICTEF` (#3); today's intraday-partial rank
date not being excluded from the freeze (#5); a `KeyError` crash risk + an asymmetric zero-check in
the null benchmark's price lookups (#6, partial — see below); the documented ≥1y-of-closes
eligibility threshold not actually being enforced (#7); and the D18 non-US filing lag missing
several no-suffix foreign issuers (#8). The coordinator then fixed the rest in the same PR
(2026-09-25):

- **#4 fills:** a rebalance trades on the first day every name in the old and new books has its own
  close (`_trade_date`).
- **The remainder of #6:** the null benchmark's random books use the same rule and each earns its
  own period; it was off by one, so the first period was always 0.
- **Annualization:** all metrics annualize by calendar span instead of 252 rows.
- **Freeze guard:** return rows dated on or after the run day (a possibly intraday mark) are never
  frozen.

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| ~~W0 land this plan + close plan 007 + open tracking issue + #294 comment~~ | agent → admin-merge on green | shipped — issue #401, plan on `main` |
| ~~PR C core engine + cron + removals + docs~~ | agent → admin-merge on green | shipped — [#404](https://github.com/qte77/analyze-stock-kpi/pull/404) merged 2026-09-24 |
| ~~PR E series A + freeze + lag (D15–D19) + B start-trim fix + yearly cadence + rebalance log + foresight audit (D20–D22)~~ | agent → admin-merge on green | shipped — [#414](https://github.com/qte77/analyze-stock-kpi/pull/414) |
| ~~PR D dashboard section~~ | agent → admin-merge on green | shipped — [#403](https://github.com/qte77/analyze-stock-kpi/pull/403) merged 2026-09-23 |
| ~~Dispatch `portfolio.yaml` + verify data files + Pages e2e (migrated from 007)~~ | agent (after E+F) | shipped 2026-09-25: run 36133238483 rebuilt B (`method_version` 2; pre-2023 year files deleted) and wrote A. The live e2e (desktop/iPad/iPhone × both orientations × light/dark) passed with the displayed numbers matching `summary.json` and the URL fix confirmed. One mismatch (UBER) came from snapshots written before #408/#409 and is being regenerated by a `demo-snapshot` re-run (36143694243) |
| ~~PR F dashboard A headline + B secondary~~ | agent → admin-merge on green | shipped — [#410](https://github.com/qte77/analyze-stock-kpi/pull/410) (also: URL state-clear fix, D20 yearly cadence, D21 rebalance log) |
| ~~Own-close fills (audit finding #4 + the matching null-benchmark #6 remainder)~~ | agent | shipped in the PR E row's PR (2026-09-25) |
| ~~Private repo cache for `results/prices/`~~ | owner → agent | migrated to [plan 009](009-backtest-carry-over.md) · [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) |
| ~~Issue: `make preview` doesn't serve `ui/public/`~~ | agent | filed [#415](https://github.com/qte77/analyze-stock-kpi/issues/415) |
| ~~Issue: `llms.txt` template missing ADR-0010..0013 + newer modules~~ | agent | filed [#416](https://github.com/qte77/analyze-stock-kpi/issues/416) |
| ~~US-only SEC-XBRL extension to ~2017~~ | owner (deferred) | migrated to [plan 009](009-backtest-carry-over.md) |
| ~~D18 lag: country-based classification~~ | agent | migrated to [plan 009](009-backtest-carry-over.md) · [#419](https://github.com/qte77/analyze-stock-kpi/issues/419) |

## Verification

1. `make validate` on both branches.
2. A local `uv run python -m analyze_stock_kpi.orchestrators.longshort_backtest`, then check:
   - the start date and eligible counts per year;
   - the monthly net index is sane (no ±100 % single-day jumps);
   - realized beta, null percentile and fidelity ρ are present;
   - `git status` shows only ignored cache files.
3. `npm run dev` + polyfetch against the local output.
4. After merge + dispatch: the data-branch commit touches only the contract paths; Pages renders.
