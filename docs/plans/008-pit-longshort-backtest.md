# 008 — Point-in-time backfilled best/worst 25 + backtested equal-weight L/S book

Issue [#401](https://github.com/qte77/analyze-stock-kpi/issues/401) (tracking) — owner request
2026-09-23. This plan closes arc [007](007-longshort-portfolio-and-multiwindow-sortino.md): its open rows
migrated here (see the table).

## Handoff (read this first, then act; don't re-explore)

**Where things stand (2026-09-23):**

- `main` includes #392–#400: arc 007 shipped, the qte77 Score is unified, and the lists are re-ranked by
  it.
- `portfolio.yaml` (#395's forward Min-Variance tracker) was **never dispatched**. There is no data to
  migrate; this plan rewires it.
- Every design decision below is owner-approved or marked *default*. Do not re-litigate; the owner
  overrides at merge time.

**Your loop:**

1. **W0 — done** (this plan landed on `main` with plan 007 closed, tracking issue #401 open, and a #294
   comment). Next is step 2.
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

## Frozen data contract (`data` branch, derived only)

- `results/series/backtest/<cadence>/YYYY.json`, with cadence ∈ {`monthly`, `quarterly_filings`,
  `monthly_buffer`, `weekly`, `buy_hold`}: a daily, date-sorted array of
  `{"date","ret_long","ret_short","ret_ls_gross","ret_ls_net","turnover"}`. `ret_short` is the short
  basket's price return, and `ret_ls = ret_long − ret_short`. Loadable via
  `loadYearsFromBranch(base, "results/series/backtest/monthly", "date", <startYear>)`.
- `results/backtest/lists/YYYY.json`: one entry per weekly rank date,
  `{"date","eligible":n,"best":[{"ticker","score"}×25],"worst":[…×25]}`. This is **the backfilled
  best/worst 25**, with `score` = `score_bt` rounded to 0.1.
- `results/backtest/summary.json`:
  - `method_version`, `as_of`, `start`, `universes[]`, `score_inputs[]`, `cost_bps`, `primary`;
  - `cadences{name:{gross:{…D9}, net:{…D9}, rebalances:n}}`;
  - `null{n, percentile, median_net_ann}`;
  - `fidelity{per_date:[{date, rho, n}], median_rho}`;
  - `caveats[]` (strings the UI renders verbatim).

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

## Parallelism

| PR | Files |
|---|---|
| C | `src/**`, `tests/**` (Python), `pyproject.toml`, `uv.lock`, `Makefile`, `.github/workflows/{portfolio,validate}.yaml`, `docs/**`, `README.md`, own changelog |
| D | `ui/**` only, own changelog |

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| ~~W0 land this plan + close plan 007 + open tracking issue + #294 comment~~ | agent → admin-merge on green | shipped — issue #401, plan on `main` |
| PR C core engine + cron + removals + docs | agent → admin-merge on green | per PR C done-when |
| Dispatch `portfolio.yaml` + verify data files + Pages e2e (migrated from 007) | agent (after C+D) | the three artifact kinds on `data`; the section renders on Pages without console errors |
| PR D dashboard section | agent → admin-merge on green | per PR D done-when |
| Issue: `make preview` doesn't serve `ui/public/` | agent | issue filed |
| Issue: `llms.txt` template missing ADR-0010..0013 + newer modules | agent | issue filed |
| US-only SEC-XBRL extension to ~2017 (filed dates) | owner (deferred) | only if the owner wants a longer US series |

## Verification

1. `make validate` on both branches.
2. A local `uv run python -m analyze_stock_kpi.orchestrators.longshort_backtest`, then check:
   - the start date and eligible counts per year;
   - the monthly net index is sane (no ±100 % single-day jumps);
   - realized beta, null percentile and fidelity ρ are present;
   - `git status` shows only ignored cache files.
3. `npm run dev` + polyfetch against the local output.
4. After merge + dispatch: the data-branch commit touches only the contract paths; Pages renders.
