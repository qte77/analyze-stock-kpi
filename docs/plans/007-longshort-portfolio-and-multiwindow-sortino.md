# 007 — Long/short model portfolio + multi-window Sortino

Issues: none yet — owner request 2026-09-21/22.

## Context

The owner wants two separate features:

1. **Multi-window Sortino:** the per-ticker Sortino (today 1y only) also at
   10y/20y/30y.
2. **Hypothetical long/short model portfolio:** long `aggregated-scores-best`, short
   `aggregated-scores-worst`, weighted by a portfoliovisualizer-style Min Variance
   optimizer and tracked forward with real prices on the dashboard.

KISS pass agreed with the owner 2026-09-22:

- scipy is the only new dependency (optional).
- One weekly cron marks both the weekly- and monthly-rebalanced portfolios.
- No UI tabs.
- Two parallel worktree PRs.
- No stored NAV: weekly returns only, compounded in the UI; no cost model
  (owner, 2026-09-23).
- Raw prices go to a local gitignored cache (never committed).

## Status / how to run this plan (read first)

- **PR B (long/short model portfolio) is implemented and open for review** —
  ADR-0012 committed (scipy-only shrinkage, no transaction costs, gitignored price
  cache, weekly returns not a stored NAV), `domain/portfolio_optimizer.py` +
  `orchestrators/longshort_portfolio.py` + `.github/workflows/portfolio.yaml` +
  the `#portfolio-section` UI shipped with tests, `make validate` green. See the
  remaining-work table below for its PR number. **Nothing merged yet.**
- **Owner gate — PRs #392/#393** (candidate refresh; CodeFactor green; blocked only
  by unsigned bot commits; the classifier denied `--admin`): the owner runs
  `gh pr merge 392 --squash --admin`, then rebases #393 and merges it the same way.
  Do this before PR B's first real run, so the pool is fresh.
- **Run:** two `Agent` calls in ONE message, each `isolation: "worktree"`, based on
  `main`. The prompt for each is its section below (A or B), self-contained.
- **Loop per PR:** RED test → implement → `make validate` → changelog fragment →
  strike your own row below → push with `env -u GH_TOKEN -u GITHUB_TOKEN` → PR.
  Merge is owner-gated.
- **Phase C (after merge):** the owner dispatches `portfolio.yaml` once; the agent
  verifies the data-branch files and runs the polyfetch e2e on Pages.
- **Watch-outs:**
  - Raw closes never reach git or the `data` branch.
  - `gh` needs `env -u GH_TOKEN -u GITHUB_TOKEN`.
  - The sandbox denies `ls/cat/grep`, so use `git ls-files` / `git grep`.
  - Pin every `uses:` to the SHAs already in `equity-spy.yaml` (strict allow-list).
  - `validate.yaml:30` must install the new extra, or pyright fails on the scipy
    import.

## Decisions

| # | Decision |
|---|---|
| D1 | Sortino: new per-ticker fields `sortino_3y`, `sortino_5y`, `sortino_10y`, `sortino_20y`, `sortino_30y`, plus an optional custom time frame via CLI `--sortino-from YYYY-MM-DD [--sortino-to YYYY-MM-DD]` → `sortino_custom` (+ `sortino_custom_from`/`_to`), CLI-only (the dashboard doesn't show it). `sortino_ratio` (1y) keeps its name and composite role (ADR-0004). The new fields are informational only. |
| D2 | A window's value is `None` unless the first valid close is ≤ `as_of − window + 30 days`. |
| D3 | Sortino display: JSON + detail-panel rows. The table keeps the single 1y column. |
| D4 | Optimizer: joint **Min Variance**, dollar-neutral: `x = [w_L, −w_S]`, each leg sums to 1, bounds `[0, max(0.10, 1/n)]`, `scipy.optimize.minimize(method="SLSQP")`. Covariance = daily returns over 756 trading days, shrunk toward its diagonal with a fixed δ = 0.3 (`(1−δ)·S + δ·diag(S)`, numpy, documented constant), annualized ×252. |
| D5 | One weekly cron (`30 23 * * 5`, Fri after close, 30 min after equity-spy). The **weekly** portfolio rebalances every run; the **monthly** one on the first run of each calendar month. |
| D6 | Pool: long = `aggregated-scores-best.txt`, short = `aggregated-scores-worst.txt`, frozen 90 days in state. Tickers with <90 % return coverage over the lookback are excluded with a reason. |
| D7 | Gross returns: no transaction costs. Local-currency returns; costs, FX, financing and borrow are not modelled (stated in the UI). |
| D8 | Raw closes are written to a gitignored `results/prices/closes_<date>.csv` (the `results/edgar/` precedent), never committed. The cron's commit filter excludes them. |
| D9 | `[project.optional-dependencies] portfolio = ["scipy>=1.14"]`. `validate.yaml:30` → `uv sync --all-extras --group dev --group test`; `Makefile` `setup_dev` → `uv sync --all-extras`; `portfolio.yaml` → `uv sync --extra portfolio`. |
| D10 | UI: "Hypothetical model portfolio" section: one chart (weekly L/S NAV + monthly L/S NAV), one holdings table (weekly portfolio's current targets), a disclaimer ("Not investment advice" + D7 + inception date). No tabs. |
| D11 | Forward-only, no backtest. **No stored NAV:** the cron stores weekly returns only, and the UI compounds them into the chart line (100 at the first stored week). |
| D12 | Weekly returns use last week's **target** weights, so there is an implicit weekly reset to target (no intra-month drift). This approximation is noted once in the UI caveat. |

## Frozen data contract (`data` branch)

- `results/series/portfolio_weekly/YYYY.json`, `results/series/portfolio_monthly/YYYY.json`:
  a date-sorted array of `{"date","ret_long","ret_short","ret_ls"}`, one row per
  weekly run, covering the week ending on `date`. Loadable via
  `loadYearsFromBranch(base, "results/series/portfolio_weekly", "date")`.
- `results/portfolio/{weekly,monthly}/state.json`: `cadence, objective("min_variance"),
  inception, as_of, last_rebalance, pool_as_of, lookback_days,
  long[{ticker,weight}], short[{ticker,weight}], pool{long[],short[]},
  excluded[{ticker,reason}], ex_ante_vol_annual`.

Weekly run math (the only math; no NAV state). `prev` = the date of the previous
run (`state.as_of`); `r_i = P_i,today / P_i,prev − 1`.

- `ret_long = Σ w_i·r_i` and `ret_short = Σ v_j·r_j`, using the state's current
  target weights.
- `ret_ls = ret_long − ret_short`.
- Append the row, then rebalance if due (weekly: always; monthly: first run of the
  month) and save the new weights and `as_of = today`.
- The first run only optimizes and saves the state; it writes no return row.
- UI: `index = 100·cumprod(1 + ret)` for each of the three lines.

## Source map

| What | Where |
|---|---|
| Sortino math (reuse unchanged) | `src/analyze_stock_kpi/data_sources/fundamentals.py:203-238` `_compute_sortino`, `_TRADING_DAYS`, `_MIN_SORTINO_DATAPOINTS` |
| Batched closes (`period="1y"` hardcoded) | `fundamentals.py:368-397` `_batch_close_prices`, `:383` |
| Attach to snapshot / field | `fundamentals.py:400-424` `fetch_universe_fundamentals`; `sortino_ratio` `:128`; docstring `:14-16` |
| Composite (don't touch) | `src/analyze_stock_kpi/domain/composite_scores.py:42,222,252` |
| UI Sortino | `ui/detail_panel.js:205`; `ui/lib/detail_rows.js:33` (`KPI_GLOSSARY`); `detail_panel.js` does not use `coloring.js` |
| Derived-series template | `src/analyze_stock_kpi/data_sources/equity_spy.py` (BaseModel row, `_year_path`/`_load_year`/`_write_year`/`merge_payload_into_years` `:122-159`, `main()`) |
| Cron + data-branch commit template | `.github/workflows/equity-spy.yaml` (+ `scripts/data-branch-commit.cjs`) |
| Preset loader | `src/analyze_stock_kpi/domain/universe.py:68` `_read_symbol_file`, `PRESET_DIR` `:23` |
| Config / gitignore precedent | `src/analyze_stock_kpi/config.py:31,47-49`; `.gitignore` `results/edgar/` |
| Deps / CI install | `pyproject.toml:9-28`; `.github/workflows/validate.yaml:30`; `Makefile:36-37` |
| UI loaders | `ui/lib/fetch.js:18` `fetchJson`, `:38` `loadYearsFromBranch`; usage `ui/app.js:144-152` |
| UI chart template | `ui/charts.js` `renderCombinedLongTerm` (~503-564), `liveCharts`/`bindThemeObserver` (~697-701) |
| UI markup | `ui/index.html:66` `#fear-greed-section`, `:145` `#universe-section` |
| UI tests | `ui/tests/*.test.mjs` (vitest) |
| Local preview | `make preview` (`python -m http.server` on `ui/`, Makefile:130), `preview_local` :135 |
| Docs | `docs/data-sources.md` §Redistribution guardrails (SPY row precedent); `docs/architecture.md` module tree ~:55-60, failure table ~:20-35; `docs/decisions/README.md`; `docs/plans/README.md` |

## PR A — multi-window Sortino (worktree agent)

**Scope extended by the owner** (mid-run) beyond the original 10y/20y/30y set: also
`sortino_3y`/`sortino_5y`, plus an optional custom time frame via new CLI flags
`--sortino-from YYYY-MM-DD [--sortino-to YYYY-MM-DD]` → `sortino_custom` (+
`sortino_custom_from`/`_to`). The custom window is CLI-only — no dashboard row.

- `fundamentals.py`:
  - `_batch_close_prices` → `period="max"` (`yf.download` has no "30y").
  - New `_windowed_sortinos(close) -> dict[str, float | None]`: `dropna()`; `as_of`
    = the last index; slice each window with `DateOffset(years=y)`; apply the D2
    coverage check to the 3/5/10/20/30y windows only (1y behaviour is unchanged);
    then `_compute_sortino`.
  - `fetch_universe_fundamentals` does `model_copy(update=_windowed_sortinos(...))`.
  - Add five fields after `:128` and update the docstrings.
  - New `CliArgs.sortino_from` / `sortino_to` (optional, `--sortino-from`/`--sortino-to`)
    → a `sortino_custom` field (+ its own `_from`/`_to` echo) computed the same way,
    CLI-only.
- Tests, RED first:
  - A synthetic 12y series sets 1y/3y/5y and 10y; 20y and 30y are None.
  - The 1y result equals `_compute_sortino` on the last-year slice (guards the
    composite input).
  - Leading NaNs (the multi-ticker shape) are handled.
  - `--sortino-from`/`--sortino-to` produces `sortino_custom` over the requested window.
- UI: `detail_panel.js:205` becomes rows "Sortino 1y/3y/5y/10y/20y/30y (rf=0)";
  add glossary keys to `detail_rows.js`. `sortino_custom` is CLI-only, not shown.
- `docs/architecture.md` fundamentals line; changelog `### Added`.
- **Done-when:**
  - `make validate` is green.
  - A local run on a small preset shows the four fields: AAPL's 30y is set, and a
    recent IPO's 10y+ is None.

## PR B — long/short model portfolio (worktree agent)

- Docs:
  - Commit ADR-0012 from the draft on `docs/007-longshort-portfolio-plan`, edited to
    D4/D7/D8/D9/D11/D12 (scipy only, no costs, gitignored cache, weekly returns not
    NAV).
  - Add a status line on ADR-0003 ("Superseded by ADR-0012 for portfolio scope") and
    on ADR-0005 ("Amended by ADR-0012").
  - Add index rows to `docs/decisions/README.md` and `docs/plans/README.md`, and add
    this plan as `docs/plans/007-…md`.
- Deps: add the D9 extra and run `uv lock`; update `validate.yaml:30` and
  `Makefile` `setup_dev`.
- `src/analyze_stock_kpi/domain/portfolio_optimizer.py` (pure numpy + scipy):
  - `shrunk_covariance(returns) -> np.ndarray` (D4).
  - `min_variance_longshort(cov, n_long, n_short) -> (w_long, w_short)`. It starts
    equal-weight and raises a clear error if `not res.success`.
  - `ex_ante_vol(cov, x)`.
- `src/analyze_stock_kpi/orchestrators/longshort_portfolio.py`:
  - pydantic `WeeklyReturn` and `PortfolioState` per the contract.
  - `load_pool()` via `_read_symbol_file`.
  - `fetch_closes(tickers)`: batched `yf.download(period="5y", auto_adjust=True)`.
    It wrap-degrades to empty (skip the mark) and writes the D8 CSV. Its own helper,
    not `_batch_close_prices`, which PR A is editing; dedupe later is a table row.
  - `is_rebalance_due`.
  - Pure `step(state | None, closes, today, cadence) -> (state, WeeklyReturn | None)`.
  - Per-year persistence mirroring `equity_spy.py:122-159`.
  - `main()` runs both cadences; the entrypoint is
    `python -m analyze_stock_kpi.orchestrators.longshort_portfolio`.
  - Import the optimizer lazily inside `step`.
- Config paths: `results/series`, `results/portfolio`, `results/prices`. Add
  `results/prices/` to `.gitignore`.
- Tests, RED first, no network:
  - Optimizer: each leg sums to 1 and bounds hold. On a built covariance where long
    A ≈ short B, the pair gets the higher weights and the ex-ante vol is below
    equal-weight.
  - `step`: the first run writes a state and no row; known price moves give the exact
    `ret_long`/`ret_short`/`ret_ls`; monthly is not due mid-month (weights unchanged);
    the pool refreshes only after 90 days; excluded tickers carry a reason.
  - Persistence round-trip; a same-date re-run replaces the row rather than
    duplicating it.
- `.github/workflows/portfolio.yaml`, a copy of `equity-spy.yaml`:
  - Cron per D5.
  - Check out `results/series/portfolio_{weekly,monthly}` and `results/portfolio`
    from `data`.
  - `uv sync --extra portfolio`.
  - Commit filter
    `^results/(series/portfolio_(weekly|monthly)/[0-9]{4}\.json|portfolio/(weekly|monthly)/state\.json)$`.
- UI:
  - `ui/lib/portfolio.js` (pure): `compound(rows)` (100·cumprod per line) and
    `holdingsRows`, tested in `ui/tests/portfolio.test.mjs`.
  - `#portfolio-section` in `ui/index.html` between `:66` and `:145`.
  - `renderPortfolioChart` in `ui/charts.js`, joining `liveCharts`.
  - `ui/app.js` loads both series + the weekly state. On 404 it shows "Tracking
    starts after the first run" and never throws.
- `docs/data-sources.md` guardrail row; `docs/architecture.md` module lines + a
  wrap-degrade failure row; changelog `### Added`.
- **Done-when:**
  - `make validate` is green.
  - A local run writes both series + states, and `results/prices/` shows as ignored
    in `git status`.
  - The polyfetch e2e passes on `make preview`: desktop + mobile, theme toggle,
    screenshots in both orientations, no console errors, clean empty state.

## Remaining work (the ONLY list of open items)

| Item | Gate | Done-when |
|---|---|---|
| Merge #392, then rebase + merge #393 | owner | presets on main refreshed |
| PR A multi-window Sortino (PR #394) | agent → owner merge | per PR A done-when |
| First `portfolio.yaml` dispatch + Pages e2e | owner → agent | data files on `data`; the section renders on Pages with no console errors |
| PR B long/short model portfolio — see the PR opened from `feat/longshort-portfolio` | agent → owner merge | per PR B done-when (shipped, pending owner merge) |
| Dedupe `fetch_closes` vs `_batch_close_prices` | agent (after A+B) | one shared batched-close helper |

Further objectives (Max Sharpe with composite-rank μ, Min CVaR, Min Drawdown) are
**deferred** until the owner asks. `state.objective` leaves room for them.

## Verification

1. `make validate` on each branch (ruff, pyright with the extra, complexity,
   markdownlint, JS lint, pytest-cov, vitest).
2. `uv sync --all-extras && uv run python -m analyze_stock_kpi.orchestrators.longshort_portfolio`.
   Check that each leg's weights sum to 1, that no raw price appears in the
   committed paths, and that `results/prices/` is ignored.
3. `make preview` + polyfetch click-through, screenshots and the console gate.
4. After merge + dispatch, check that the data-branch commit contains only the
   filtered paths and that Pages shows the section.
