# 011 — Options open-interest levels: daily collection

Issue: none yet (owner request 2026-11-22; opened when the owner approves this plan).

## Status (read first)

- **State:** proposed. Nothing is built yet. The owner approves this plan, then the agent starts at
  row 1 of the [remaining-work table](#remaining-work).
- **Why now:** there is no free history of option open interest (OI). Levels can only be measured
  from the day collection starts, so collection comes first and every use of the data comes later.
- **Scope:** collection only. The levels are a **hypothesis** about price "gravity" near large OI
  strikes, not a signal. They stay out of the qte77 Score and the dashboard until the point-in-time
  backtest ([ADR-0013](../decisions/0013-point-in-time-backtest.md)) supports them.
- **Owner gates:** approve this plan; approve the ADR's licensing verdict; the #418 deploy key, which
  is needed only to keep the raw chains (row 4). Everything else is agent work.
- **Loop per row:** branch → tests first → `make validate` → PR → checks green → squash-merge →
  strike the row in the same PR.

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

One module, one daily workflow, one public series. KISS: SPY only; QQQ is a later one-line
config change if wanted.

**Per collection day, for each of two expiries** (`nearest`, `monthly` = the first third-Friday
expiry on or after today):

| Field | Definition |
|---|---|
| `max_pain` | strike minimising total intrinsic value owed to holders of all calls + puts at that expiry |
| `call_wall` | strike with the largest call OI |
| `put_floor` | strike with the largest put OI |
| `pc_oi_ratio` | total put OI / total call OI |
| `total_oi` | total call + put OI |
| `oi_null_share` | share of contracts with null OI (data-quality flag; null OI counts as 0) |

**Cut** (recommended 2026-11-22 after an independent review; confirmed when the owner approves this
plan): dealer gamma exposure (GEX) and its sign — it rests on an assumption about dealer positioning,
and the null OI share makes it noisy. No UI, no score work.

**Where data goes** (licensing; see [`data-sources.md`](../data-sources.md) guardrails):

- Public `data` branch: only the derived rows above, in `results/series/options_oi/YYYY.json`,
  one row per `(date, expiry_kind)`. No quotes, no prices, no spot level, no raw chain.
- Raw chains (Yahoo payloads, CAUTION): only in the private cache repo from #418, under
  `results/prices/options/SPY/<date>.json`, and only once that cache is live.

## Source map

| What | Where |
|---|---|
| Pattern to copy (fetch → per-year JSON, wrap-degrade) | `src/analyze_stock_kpi/data_sources/equity_spy.py` (`_fetch_history_closes`, `_load_year`, `_write_year`, `merge_payload_into_years`, `main`) |
| Settings (cache dirs) | `src/analyze_stock_kpi/config.py` (`equity_spy_cache_dir`, `backtest_prices_cache_dir`) |
| Daily workflow to copy | `.github/workflows/equity-spy.yaml`; verified data-branch commit via `scripts/data-branch-commit.cjs` |
| Private cache wiring (#418) | `.github/workflows/portfolio.yaml` (`CACHE_REPO_SSH_KEY` restore/save steps) |
| Licensing rules | `docs/data-sources.md` §Redistribution guardrails; [ADR-0011](../decisions/0011-equity-macro-overlay-via-spy-indexed-returns.md) |
| Future hypothesis test | `src/analyze_stock_kpi/orchestrators/longshort_backtest.py`, [ADR-0013](../decisions/0013-point-in-time-backtest.md) |
| New module (to create) | `src/analyze_stock_kpi/data_sources/options_oi.py`, `tests/test_options_oi.py` |

## Remaining work

| # | Item | Gate | Done when |
|---|---|---|---|
| 1 | ADR-0015 (collection-only OI levels, the two expiries, the GEX cut) + an OI guardrail row in `docs/data-sources.md` | owner (approves the licensing verdict in the PR) | ADR merged |
| 2 | `options_oi.py`: pydantic models, expiry selection, the six fields, per-year merge; tests first for max pain, walls, ratio, null handling, monthly-expiry pick, same-day re-run idempotence | agent | `make validate` passes; module runs locally and writes one row per expiry kind |
| 3 | Check when Yahoo's OI updates each day (fetch at two times one day apart, compare) and set the cron after it | agent | cron time chosen from two observed fetches, noted in the workflow header |
| 4 | `options-oi.yaml`: daily cron on weekdays, derived rows → `data` branch; raw chain → private cache when `CACHE_REPO_SSH_KEY` exists (dormant until then) | agent (raw-chain half: owner, #418) | two consecutive scheduled runs add rows on `data` |
| 5 | Hypothesis test: distance from `max_pain` / walls vs return to expiry, with the point-in-time backtest | data (≥ 6 months of rows) | a written result; only if it holds does a dashboard line or score input get its own plan |

## Open questions (defaults applied unless the owner overrides)

- **Licensing verdict for the derived rows** — default: CLEAR (derived-only), like the put/call ratio:
  strikes are contract terms and the other fields are aggregates, not quotes. Not yet checked against
  the OCC/OPRA terms; the ADR in row 1 records that check or marks it unverified.
- **Symbols** — default: SPY only.
- **Weekend/holiday runs** — default: skip non-trading days (no new OI).

## References

- yfinance `Ticker.option_chain` (verified live 2026-11-22, see Context).
- Issue [#418](https://github.com/qte77/analyze-stock-kpi/issues/418) — private cache repo.
