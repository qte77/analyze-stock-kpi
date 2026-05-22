# User Story

## What this is

A no-API-keys CLI that produces a per-asset KPI dossier (fundamentals + sentiment + composite scores) for any tradable Yahoo symbol — stocks, ETFs, FX pairs, commodity futures, crypto, indices.

## Who it is for

Solo investors building their own auditable, rule-based screening pipeline. Anyone who wants Traderfox-style aggregate scores without paying Traderfox, with formulas they can read and modify.

## Core user stories

- **As an investor**, I want to point the tool at a list of tickers (or a curated universe preset) and get one JSON snapshot per asset so I can sort/filter on KPIs in any downstream tool.
- **As an investor**, I want quality / dividend / growth / robustness / screener composite scores derived from documented public formulas (Piotroski, ROIC stability, dividend coverage, CAGR) so I can audit and tune the weighting myself.
- **As an investor**, I want a daily CNN Fear & Greed sentiment snapshot committed to the repo so I have a long-running market-mood timeseries without paying for one.
- **As a maintainer**, I want every structured payload validated by pydantic and every module within strict cyclomatic + cognitive complexity budgets so the codebase stays readable and the failure modes are loud.

## Non-goals (explicit)

- Replicate Traderfox's exact proprietary numerical scores (won't match byte-for-byte; composite proxies are documented approximations of the same signals)
- Long/short hedging strategy execution (deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md) — issues #4 / #8 / #9 / #10 stay open with the `deferred` label; behavioral price analytics fits a sibling repo)
- Paid-data integrations (CDS spreads, Bloomberg, Refinitiv) — out of scope
- Automated trade execution — analysis only

## v0.6.0 done means (in progress)

- A read-only static dashboard at `https://qte77.github.io/analyze-stock-kpi/` shows the current CNN Fear & Greed score with a 2-year history chart plus a sortable table of the latest `qte77-watchlist` fundamentals snapshot (74 tickers, weekly cadence).
- A weekly GitHub Actions cron (`demo-snapshot.yml`) writes `results/demo/qte77-watchlist/YYYY-MM-DD.json` snapshots and a manifest to the `data` branch via verified REST Git Data API commits. The dashboard fetches them cross-origin from `raw.githubusercontent.com`.
- `fear-greed.yaml` rewritten to the same verified-commit pattern, fixing the cron blocked by the repo's `required_signatures` ruleset.
- Inherits everything from v0.5.1 below.

## v0.5.1 done means

- yfinance `info["dividendYield"]` is normalized at the fetch boundary so the rich table, JSON output and composite formulas all see one fractional convention (#43).
- Inherits everything from v0.5.0 below.

## v0.5.0 done means

- `make run UNIVERSE=<preset>` (or `TICKERS=...`, `TICKERS_FILE=...`) writes a single `results/fundamentals/<UTC>.json` containing one `FundamentalsSnapshot` per resolved ticker, with a nested `composite_scores` object (seven 0-100 proxies). Sparse fields for non-equities are valid.
- Stdout shows a rich summary table for equities + ETFs; pass `SHOW_SCORES=1` to append Quality / Div / Growth columns.
- CNN F&G snapshot lands daily in `results/cnn_fg/YYYY.json` via cron (v0.4.0 #17).
- `make validate` passes lint + types + complexity + lint_md + tests. CI green on push and PR (validate + links-fail-fast workflows).

## v1.0.0 vision (post v0.5.0)

`make run UNIVERSE=<preset>` produces, per asset in `results/<DATE>_<universe>/<ticker>/`:

- `fundamentals.json` — Tier 1: extends `FundamentalsSnapshot` with PEG, dividend-aristocrat flag, and any richer trend/historical fields the simplified composites currently approximate
- `composites.json` — Tier 3: quality / dividend / growth / big_call / aaqs / hgi proxy scores (v0.5.0 #18, simplified per [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md))
- `sentiment.json` — CNN F&G snapshot (v0.4.0 #17, runs independently on cron)

The per-asset directory layout is a future schema change from v0.5.0's single-file output; not yet implemented.
