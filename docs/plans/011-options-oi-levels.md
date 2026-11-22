# 011 — Options open-interest levels: daily collection

Issue: none yet. The orchestrator opens one when the owner approves this plan, then puts its
number here.

## Status and how to work this plan (read first)

- **State (2026-11-22):** proposed in PR #562. Nothing is built. Merging #562 approves the plan.
- **Goal:** collect SPY option open interest (OI) levels every weekday from now on. There is no free
  OI history, so the data only exists from the day collection starts. Collection comes first; any
  use of the data comes later (row 5).
- **Scope:** collection only. The levels are a **hypothesis** about price "gravity" near large OI
  strikes, not a signal. They stay out of the qte77 Score and the dashboard until the point-in-time
  backtest ([ADR-0013](../decisions/0013-point-in-time-backtest.md)) supports them.
- **What to do next, in order:** follow [Parallel execution](#parallel-execution-subagents-in-worktrees).
  Wave 1 runs rows 1, 2 and 3 at the same time. Wave 2 runs row 4. Row 5 waits for data.
- **Your role in a fresh session:** you are the orchestrator. You open the issue, start the
  subagents, check their PRs, merge, and do row 3 yourself. Subagents write code and open PRs.
  They never merge.
- **Owner gates (one sitting):** approve this plan (merge #562); approve the licensing verdict in
  the row 1 PR. The `CACHE_REPO_TOKEN` secret from plan 009 / #418, needed only to keep the raw
  chains (row 4), exists since 2026-11-22. Everything else proceeds on the defaults in
  [Open questions](#open-questions-defaults-applied-unless-the-owner-overrides).
- **Loop per row:** branch → tests first → `make validate` → changelog fragment
  (`make changelog_new`) → strike the row in this file → PR → checks green → squash-merge → delete
  the branch.
- **Watch-outs:**
  - A fresh worktree has no `.venv` and no `ui/node_modules`. Run `make setup_dev` and
    `make setup_npm_tools` before `make validate`, or `lint_js` fails with "eslint: not found".
  - `make validate` can rewrite `complexipy-snapshot.json`. Restore it before committing unless
    your new code caused the change.
  - Never commit raw Yahoo payloads, quotes or the SPY spot price. Only the derived rows in the
    [Approach](#approach) table go public.
  - Do **not** gitignore `results/series/options_oi/`. The workflow finds changed files with
    `git status`, which skips ignored files. The equity_spy series works the same way.
  - Use only actions that are already pinned in `equity-spy.yaml`. The repo's Actions allow-list
    requires SHA pins, and adding a new action needs the owner.

## Context

- Verified 2026-11-22 with yfinance 1.8.0 (`uv run`): `yf.Ticker("SPY").option_chain(expiry)`
  returns `calls` and `puts` frames with `strike`, `openInterest` and `impliedVolatility`; SPY listed
  30 expiries (2026-11-23 to 2029-01-19). In the nearest expiry about 14 % of `openInterest` values
  were null (calls 24/172, puts 24/158).
- SPY has daily expiries, so the nearest expiry and the standard monthly expiry (third Friday) give
  different levels; both are collected.
- The `data` branch already holds CNN's put/call ratio (`series/cnn_fg`, `put_call_options.raw_value`,
  daily since 2025-05-12), a market-wide volume ratio to compare the OI ratio against.

## Approach

One module, one weekday workflow, one public series. KISS: SPY only; QQQ is a later one-line config
change if wanted.

**Per collection day, for each of two expiries:**

- `nearest` = the first listed expiry on or after the collection date.
- `monthly` = the first listed expiry on or after the collection date that is the third Friday of its
  month. If that Friday is a market holiday, the listed expiry is the Thursday before it (this
  happened on 2025-04-17, Good Friday). So treat a listed Thursday in the third-Friday week as
  monthly.
- If both are the same expiry, still write both rows.

| Field | Definition |
|---|---|
| `max_pain` | strike `K` minimising `Σcalls OI·max(0, K − strike) + Σputs OI·max(0, strike − K)` over all listed strikes; ties → lowest strike |
| `call_wall` | strike with the largest call OI; ties → lowest strike |
| `put_floor` | strike with the largest put OI; ties → lowest strike |
| `pc_oi_ratio` | total put OI / total call OI; `None` when call OI is 0 |
| `total_oi` | total call + put OI (int) |
| `oi_null_share` | share of contracts with null OI. Null OI counts as 0 everywhere else |

If total OI is 0, the four level fields are `None`, and the row is still written so the gap is
visible. Each row also carries `date` (the collection date, UTC), `expiry_kind` and `expiry`. Rows
are keyed by `(date, expiry_kind)`, so a re-run on the same day replaces that day's rows.

**Cut** (recommended 2026-11-22 after an independent review; confirmed when the owner approves this
plan): dealer gamma exposure (GEX) and its sign. GEX rests on an assumption about dealer
positioning, and the null OI share makes it noisy. No UI, no score work.

**Where data goes** (licensing; see the [`data-sources.md`](../data-sources.md) guardrails):

- Public `data` branch: only the derived rows above, in `results/series/options_oi/YYYY.json` (a
  date-sorted JSON array, same shape as `equity_spy`).
- Raw chains (Yahoo payloads, CAUTION) are written locally to the gitignored
  `results/prices/options/SPY/<date>.json`. The workflow saves them to the private cache repo
  `qte77/__analyze-stock-kpi-cache` only when `CACHE_REPO_TOKEN` exists. Otherwise they are
  discarded with the runner.

## Source map

| What | Where |
|---|---|
| Module to copy (fetch → per-year JSON, wrap-degrade) | `src/analyze_stock_kpi/data_sources/equity_spy.py`: frozen model `:50`, `_fetch_history_closes` `:82` (try/except → empty), `_year_path`/`_load_year`/`_write_year` `:122-142`, `merge_payload_into_years` `:144`, `main` `:162` |
| Settings | `src/analyze_stock_kpi/config.py`: `AppSettings` `:21`; add `options_oi_cache_dir: Path = Path("results/series/options_oi")` next to `equity_spy_cache_dir` `:49`; raw chains go under `backtest_prices_cache_dir` `:62` (`results/prices`, gitignored at `.gitignore:117`) |
| Tests to copy | `tests/test_equity_spy.py`: DataFrame helper for mocked yfinance `:82`, wrap-degrade test `:90`, merge/replace tests `:147-166`, live test marked `@pytest.mark.network` `:168` (excluded from `make test`) |
| yfinance API | `Ticker.options` (tuple of `YYYY-MM-DD` strings), `Ticker.option_chain(expiry).calls/.puts`; `pyproject.toml:14` pins `yfinance>=1.4.1`. Check shapes with the context7 MCP, not memory |
| Workflow to copy | `.github/workflows/equity-spy.yaml`: cron `:22`, permissions/concurrency `:25-30`, data-branch fetch `:45-51`, uv setup `:53-62`, change detection `:67-82`, verified commit via `scripts/data-branch-commit.cjs` (`run()` `:48`) `:84-101` |
| Private cache wiring | `.github/workflows/portfolio.yaml` restore/save steps reading `CACHE_REPO_TOKEN` (PR #560; on `main` once merged). The cache repo is `qte77/__analyze-stock-kpi-cache` |
| Other data-branch crons (avoid their slots) | `fear-greed.yaml:25` 21:30 daily · `yield-curve.yaml:22` 22:30 daily · `equity-spy.yaml:22` 23:00 daily · `portfolio.yaml:31` Sat 12:00 · `demo-snapshot.yaml:44` Sun 06:15 (all UTC) |
| Licensing rules | `docs/data-sources.md` guardrail table `:66` (header) with the SPY "CLEAR (derived-only)" row `:74` to model the OI row on; section heading `:59` lists when rows were added; [ADR-0011](../decisions/0011-equity-macro-overlay-via-spy-indexed-returns.md) |
| ADR format + index | next number is **0015** (last: `docs/decisions/0014-current-candidates-use-live-score.md`); index table in `docs/decisions/README.md` `:20-22` |
| Docs to update | `docs/architecture.md` `data_sources/` tree `:50-56` (row 2 adds `options_oi.py`); `docs/data-sources.md` "Refresh cadence summary" table `:620` (row 4 adds the cron) |
| Changelog | one fragment per PR via `make changelog_new` (`Makefile:163`) into `changelog.d/`; never edit `CHANGELOG.md` |
| Future hypothesis test | `src/analyze_stock_kpi/orchestrators/longshort_backtest.py`, [ADR-0013](../decisions/0013-point-in-time-backtest.md) |
| New files | `src/analyze_stock_kpi/data_sources/options_oi.py`, `tests/test_options_oi.py`, `.github/workflows/options-oi.yaml`, `docs/decisions/0015-options-oi-levels-collection.md` |

## Remaining work

| # | Item | Gate | Done when |
|---|---|---|---|
| 1 | ADR-0015 (collection-only OI levels, the two expiries, the GEX cut, the licensing verdict) + an OI row in the `data-sources.md` guardrail table + ADR index row | owner (approves the licensing verdict in the PR) | ADR merged |
| ~~2~~ | ~~`options_oi.py`: pydantic row model, expiry selection, the six fields, per-year merge, raw-chain write to `results/prices/options/SPY/<date>.json`, `main()` entrypoint; tests first for max pain, walls, ratio, null and zero-OI handling, monthly pick incl. the holiday Thursday, same-day re-run replace, wrap-degrade~~ shipped in PR #564 | agent | `make validate` passes; `uv run python -m analyze_stock_kpi.data_sources.options_oi` writes two rows locally |
| 3 | Find when Yahoo's OI changes during the day, then pick the cron time | agent (orchestrator) | the observed times and the chosen cron are written in the row 4 workflow header |
| 4 | `options-oi.yaml`: weekday cron, derived rows → `data` branch; raw chains → private cache when `CACHE_REPO_TOKEN` exists (it does since 2026-11-22; keep the check so the job still runs without it); refresh-cadence row | agent | two consecutive scheduled runs add rows on `data` and raw chains in the cache repo |
| 5 | Hypothesis test: distance from `max_pain` / walls vs return to expiry, with the point-in-time backtest | data (≥ 6 months of rows, so not before mid-2027) | a written result; only if it holds does a dashboard line or score input get its own plan |

## Parallel execution (subagents in worktrees)

Every subagent runs in its own git worktree (Agent tool, `isolation: "worktree"`) on its own
branch. It edits **only** the files listed for it, plus its own changelog fragment and its own row
strike in this file. It never merges. It returns the PR number and the `make validate` result. The
orchestrator merges.

| Wave | Row | Who | Branch | Files it owns | Starts after |
|---|---|---|---|---|---|
| 1 | 3 | orchestrator, inline | none | none: a throwaway script outside the repo | plan approved. Start it first, because it needs wall-clock time |
| 1 | 1 | subagent `adr` | `docs/adr-0015-options-oi` | `docs/decisions/0015-options-oi-levels-collection.md` (new), `docs/decisions/README.md`, `docs/data-sources.md` guardrail section only | plan approved |
| 1 | 2 | subagent `module` | `feat/options-oi-module` | `src/analyze_stock_kpi/data_sources/options_oi.py` (new), `tests/test_options_oi.py` (new), `tests/fixtures/options_oi/` (new, if needed), `src/analyze_stock_kpi/config.py`, `docs/architecture.md` | plan approved |
| 2 | 4 | subagent `workflow` | `ci/options-oi-workflow` | `.github/workflows/options-oi.yaml` (new), `docs/data-sources.md` refresh-cadence table only | rows 1 and 2 merged, row 3 observed |

- **Row 3 method:** fetch the `monthly` expiry's `total_oi` for SPY at about 13:00 UTC and 21:00 UTC
  on one weekday, and at 13:00 UTC the next weekday. If the value changes only overnight, use a
  weekday cron at 13:00 UTC (before the US open, and no other data-branch writer runs then).
  Otherwise pick the first slot after the observed change. This is a default to confirm, not a
  verified fact about Yahoo or OCC timing.
- **Merge order:** rows 1 and 2 in either order, then row 4. Rows in the remaining-work table sit
  on adjacent lines, so the second wave-1 PR gets a small conflict in this file after the first
  merges. Rebase it and keep both strikes.
- **Brief each subagent with:** this file's path, its row number, the files it owns, and the
  watch-outs in [Status](#status-and-how-to-work-this-plan-read-first). Don't restate the plan.

## Open questions (defaults applied unless the owner overrides)

- **Licensing verdict for the derived rows:** default is CLEAR (derived-only), like the put/call
  ratio. Strikes are contract terms and the other fields are aggregates, not quotes. Not yet checked
  against the OCC/OPRA terms; the row 1 ADR records that check or marks it unverified.
- **Symbols:** default is SPY only.
- **Weekend/holiday runs:** default is a weekday-only cron. Market holidays are not special-cased:
  the row repeats the prior OI, and row 5 joins on trading days.

## References

- yfinance `Ticker.option_chain` (verified live 2026-11-22, see Context).
- Issue [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) and
  [plan 009](009-backtest-carry-over.md): the private cache repo and its `CACHE_REPO_TOKEN` secret.
