# Architecture

High-level sketch of modules + data flow. See [`UserStory.md`](UserStory.md) for *what* this builds; this doc covers *how*.

## Principles

- **Modular**: one responsibility per module, narrow public API, no cross-module reach-around
- **OOP-minimal**: prefer functions; classes only for `pydantic.BaseModel` data containers; no inheritance hierarchies
- **Boundary-validated**: every external payload (CLI args, HTTP responses, library returns) parsed into a pydantic model — invalid data fails loudly at the edge
- **Complexity-budgeted**: ruff `C901` cyclomatic ≤ 10; complexipy cognitive ≤ 15; both gate `make validate`

## Failure policy at I/O boundaries

Every external boundary carries one of three failure policies. Logged via `logger.exception` / `logger.warning(..., exc_info=True)` for the wrap-* policies; never silent.

- **fail-loud** — raise immediately; failure is a programmer / infrastructure / config problem that silent degradation would hide
- **wrap-degrade** — catch a specific exception class, log a `WARNING`, return a degraded result (`None` / sparse snapshot / cached body); caller continues
- **wrap-continue** — same as wrap-degrade but inside a loop; per-item failures don't abort the batch

| Boundary | File / function | Policy | Notes |
|---|---|---|---|
| SEC ticker registry fetch | `sec.cik_map._fetch_json` | wrap-degrade if cache exists, else fail-loud | network blip + cache present → reuse cache; corrupt cache → invalidate + refetch |
| SEC submissions per CIK | `sec.submissions.fetch_last_filed` | wrap-degrade — drop `sec_last_*` fields | called per-ticker by `enrich_snapshot_sec`; one ticker's SEC failure leaves enrichment as `{}`, snapshot survives |
| CNN F&G fetch | `sentiment._fetch_payload` | wrap-degrade — banner skipped | caller `__main__.main` wraps; rest of run continues |
| yfinance `Ticker.info` | `fundamentals.fetch_fundamentals` | wrap-continue — sparse snapshot | per-ticker `try/except` in `fetch_universe_fundamentals` |
| yfinance batch `download` | `fundamentals._batch_close_prices` | wrap-degrade — `sortino_ratio=None` for all | network / shape error → returns `None`; per-ticker Sortino stays unset |
| yfinance `Ticker.info` (audit) | `universe_audit.classify_ticker` | wrap-degrade — `FAIL` entry | exception → `AuditEntry(classification="FAIL", note=str(exc))`; one ticker can't abort the audit sweep |
| whit3rabbit CSV fetch (backfill) | `scripts/backfill_fear_greed_whitrabbit._fetch_csv` | fail-loud | operator-only one-shot; CSV unavailability is a configuration error (wrong SHA, network down), not a degradable state — abort + retry rather than write partial data |
| yfinance `Ticker.history` (yield curve) | `yield_curve._fetch_close` | wrap-degrade — `None` per leg | per-leg `try/except`; both legs failing → `fetch_yield_curve_snapshot` returns `None` and the cron skips today's write rather than persisting an empty row |
| Filesystem write (snapshots) | `__main__._persist_snapshots` | fail-loud | disk full / permission denied → abort |
| Filesystem write (CNN cache) | `sentiment._write_year` | fail-loud | same rationale |
| Filesystem read (universe preset) | `universe.resolve_universe` (preset mode) | wrap-degrade — empty preset returns `[]` | orchestrator-driven case (#192 Phase 2a): the longshort presets start as 0-byte placeholders; the conjunctive gate can also yield zero candidates legitimately. Missing-file path still fail-loud — config error |
| Filesystem read (inline `tickers` / `tickers_file`) | `universe.resolve_universe` | fail-loud — empty raises `UniverseError` | operator-typed input; an empty result is almost certainly a typo / wrong path, not a designed state |
| Filesystem read (EDGAR cache) | `sec.cik_map._fetch_json` (cached read) | fail-loud | corrupt JSON shouldn't happen on a CDN-served read; if it does, user removes `results/edgar/` to recover |
| Pydantic `model_validate` | every call | fail-loud | upstream schema break or programmer error — never wrap |

## Modules

```text
src/
├── __main__.py                       entrypoint: resolve universe -> per-ticker fetch -> rich table + results/fundamentals/<UTC>.json; `--refresh-universe NAME` branches to an orchestrator
├── __version__.py                    package version constant
├── config.py                         AppSettings(BaseSettings) — every URL/path/timeout/HTTP-shape constant; env-overridable via SSK_*
├── domain/
│   ├── universe.py                   resolve_universe(args) -> list[ticker]; presets in src/analyze_stock_kpi/assets/universes/*.txt
│   └── composite_scores.py           quality/dividend/growth/big_call/aaqs/hgi/screener 0-100 proxies; `compute_scores(snap) -> CompositeScores`
├── data_sources/
│   ├── fundamentals.py               fetch_fundamentals / fetch_price_history / fetch_universe_fundamentals — yfinance
│   ├── sentiment.py                  fetch_fear_greed() -> FearGreedSnapshot; `python -m analyze_stock_kpi.data_sources.sentiment` merges into per-year files results/series/cnn_fg/YYYY.json
│   ├── sentiment_backfill.py         parse_csv / merge_into_years — whit3rabbit/fear-greed-data CSV → per-year F&G files; one-shot gap-fill backfill (#164)
│   ├── yield_curve.py                fetch_yield_curve_snapshot / fetch_yield_curve_history — yfinance ^TNX/^FVX 5s10s slope → per-year results/series/yield_curve/YYYY.json (daily cron #165; one-shot deep backfill to 2011 via scripts/backfill_yield_curve.py, #287)
│   ├── usaspending.py                fetch_top_contractors(...) -> list[RecipientRecord] — usaspending.gov POST client
│   └── sec/
│       ├── cik_map.py                resolve_cik / lookup_record — EDGAR company_tickers_exchange.json with HTTP conditional GET + disk cache
│       └── submissions.py            fetch_last_filed / enrich_snapshot_sec — EDGAR submissions API
├── orchestrators/
│   ├── aggregated_scores_best_and_worst.py  build_universe(snapshots_by_universe, snapshot_dates_by_universe, *, top_n=25, ...) -> tuple[list[str], list[str], list[AuditRow]]; cross-universe composite-mean ranking, returns (best, worst, audit) — paired presets `aggregated-scores-best` + `aggregated-scores-worst` (#184; NOT a hedging primitive, see ADR-0005 amendment)
│   ├── enhanced_kpi_screener_longshort.py   build_universe(snapshots_by_universe, snapshot_dates_by_universe, *, min_criteria=10, ...) -> tuple[list[str], list[str], list[AuditRow]]; 15 long-side + 14 short-side conjunctive gates (a ticker lands in `longs` iff it passes ALL long gates, in `shorts` iff it passes ALL inverted short gates, otherwise neither). Phases 2a + 2b of #192; criterion 15 (tech rating) still deferred behind #21. Paired presets `enhanced-kpi-screener-longs` + `enhanced-kpi-screener-shorts`. Long ∩ short empty by construction. Declarative `_NUMERIC_GATES` table keeps `_evaluate` cognitive complexity at 5
│   ├── federal_contractors.py        build_universe(*, fy=None, top_n=100) -> tuple[list[str], list[AuditRow]]; chains usaspending → EDGAR → yfinance
│   └── universe_audit.py             classify_ticker / audit_universes -> UniverseAuditReport; operator triage for stale-US-ticker rot (#168)
├── assets/
│   └── universes/                    preset *.txt ticker lists (one per universe name)
└── utils/
    ├── http_ua.py                    USER_AGENTS pool (re-exported from settings), STABLE_USER_AGENT, pick_user_agent(), require_https()
    └── parse_args.py                 CliArgs(BaseSettings) — pydantic-settings CLI + env (env_prefix="SSK_")
```

## Data flow (v1.1.0 current)

```text
CLI args  ──► CliArgs(BaseSettings)
                  │
                  ▼
            sentiment.fetch_fear_greed()  ──► rich banner (best-effort; failure logs and continues)
                  │
                  ▼
            universe.resolve_universe()
                  │  list[ticker]
                  ▼
        fundamentals.fetch_universe_fundamentals()
                  │  list[FundamentalsSnapshot]   (sequential, tqdm, per-ticker errors logged + skipped)
                  ▼
   rich table (equities + ETFs only)  +  json.dumps -> results/fundamentals/<UTC>.json
```

A separate daily GitHub Actions cron (`.github/workflows/fear-greed.yaml`) runs `python -m analyze_stock_kpi.data_sources.sentiment`, which loads each affected per-year history file (`results/series/cnn_fg/YYYY.json` — a date-sorted JSON array), upserts the live headline (force, since CNN updates intraday) plus any historical points CNN now exposes that are missing or stale on disk, and rewrites only the year files that changed. The workflow checks out the `data` branch (not `main`) so accumulated history is present before `sentiment.py` merges, then commits the changed year files via the REST Git Data API (Blob → Tree → Commit → Ref) invoked from `actions/github-script@v9`. Commits created via this API path with the workflow's `GITHUB_TOKEN` are signed by GitHub's web-flow PGP key and marked `verified: true` — required by the repo's `required_signatures` ruleset on `main`. The `data` branch lives outside the ruleset's `~DEFAULT_BRANCH` scope, so direct pushes to it succeed.

A second cron (`.github/workflows/demo-snapshot.yaml`, Sunday 06:15 UTC) runs `make run UNIVERSE=qte77-watchlist`, renames the timestamped output to `results/demo/qte77-watchlist/YYYY-MM-DD.json`, rebuilds the manifest via `scripts/build_demo_manifest.py`, and commits both files to the `data` branch through the same verified-commit mechanism.

A third workflow (`.github/workflows/gh-pages.yaml`) deploys the static dashboard at `ui/{index.html, app.js, style.css}` to GitHub Pages via `actions/upload-pages-artifact` + `actions/deploy-pages` whenever those files change. The dashboard fetches data files at runtime cross-origin from `raw.githubusercontent.com/qte77/analyze-stock-kpi/data/results/…`; this decouples data-update cadence from page deploys.

v1.1.0 attaches a `CompositeScores` object to every `FundamentalsSnapshot` after fetch via `model_copy(update={"composite_scores": compute_scores(snap)})`. The rich summary table appends Quality / Div / Growth columns only when `--show-scores` is passed; persistence carries the composites unconditionally.

## Public types (`pydantic.BaseModel`)

| Type | Module | Role |
|---|---|---|
| `CliArgs(BaseSettings)` | `utils/parse_args.py` | CLI + env input — `cli_parse_args=True`, `extra="forbid"` |
| `FundamentalsSnapshot` | `fundamentals.py` | Per-ticker fundamentals — ~35 aliased fields including the post-fetch enrichments `roi`, `rd_to_revenue`, `fcf_margin` (#192 Phase 2b; `Ticker.cashflow` + `Ticker.income_stmt`, EQUITY-gated), `sortino_ratio` (see [ADR-0004](decisions/0004-price-history-composite-input.md)) and the analyst-rating bucket `analyst_recommendation` (#192 Phase 2a; alias `recommendationKey`, already in the yfinance `info` payload — no extra HTTP); sparse for non-equities |
| `FearGreedSnapshot` | `sentiment.py` | CNN F&G headline (score, rating, timestamp, prev close/1w/1m/1y) + optional `subindicators` map of 9 named `SubindicatorReading` entries (score, rating, raw_value); see [`cnn-fg-api.md`](cnn-fg-api.md) for what's backfillable vs daily-only |
| `CompositeScores` | `composite_scores.py` | Quality/dividend/growth/big_call/aaqs/hgi/screener 0-100 proxies derived from `FundamentalsSnapshot`; simplified formulas per [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md) amended by [`decisions/0004-price-history-composite-input.md`](decisions/0004-price-history-composite-input.md) |

## External boundaries

- **`yfinance`** — fundamentals (`Ticker.info`) + price history (`Ticker.history`); rate-limit risk; live tests tagged `@pytest.mark.network` (excluded from default `make test`, opt in via `pytest -m network`). `_normalize_yfinance_info` in `src/analyze_stock_kpi/data_sources/fundamentals.py` divides the current percentage-shaped `info["dividendYield"]` by 100 at the fetch boundary so the rest of the codebase sees fractional yields. `fetch_universe_fundamentals` adds a batched `yf.download(tickers, period="1y")` once per run for Sortino — see [ADR-0004](decisions/0004-price-history-composite-input.md). `_fetch_rd_to_revenue` reads `Ticker.income_stmt` per EQUITY ticker for the R&D / Revenue ratio. `_fetch_fcf_margin` reads `Ticker.cashflow` + `Ticker.income_stmt` per EQUITY ticker for the Free-Cash-Flow margin (criterion 12 of #192).
- **SEC EDGAR JSON endpoints** — `www.sec.gov/files/company_tickers_exchange.json` (CIK / ticker registry) and `data.sec.gov/submissions/CIK<10>.json` (per-company filing index); SEC prefers *identity-shape* `User-Agent`. `_fetch_json` / `fetch_last_filed` send `settings.sec_user_agent` — identity-shape default (RFC 2606 placeholder, opposite of CNN below); operator overrides via `SSK_SEC_USER_AGENT` env (CI: `vars.SEC_USER_AGENT`). Stdlib `urllib.request`, no extra deps. Disk cache at `settings.edgar_cache_dir` lets `_http_error_cache_fallback` survive 403/304 once primed; first cold-cache CI call can still 403 if the placeholder default is rejected. Rationale in [ADR-0006 amendment 2026-05-22 (later)](decisions/0006-federal-contractors-universe.md).
- **CNN F&G JSON endpoint** — `production.dataviz.cnn.io/index/fearandgreed/graphdata`; requires browser-shape headers (UA + `Accept` + `Referer`; returns 418 otherwise); stdlib `urllib.request`, no extra deps. Observed schema in [`cnn-fg-api.md`](cnn-fg-api.md). Classified as Tier 0 (keyless, default-on, public-`data`-branch-persistable) per [ADR-0005](decisions/0005-sentiment-risk-sources.md)'s three-tier framework — additional sentiment / risk sources must declare their tier under the same rubric.
- **GitHub Actions cron** — `.github/workflows/fear-greed.yaml` (daily 21:30 UTC) commits per-year history files `results/series/cnn_fg/YYYY.json`; `.github/workflows/demo-snapshot.yaml` (Sunday 06:15 UTC) commits per-week universe snapshots under `results/demo/<UNIVERSE>/`. Both target the `data` branch via verified REST Git Data API commits from `actions/github-script@v9`.
- **`financetoolkit`** — *not used; v1.1.0 composites use simplified formulas with point-in-time `FundamentalsSnapshot` inputs only. See [`decisions/0001-defer-financetoolkit.md`](decisions/0001-defer-financetoolkit.md) and [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md).*

## What's not here

- Traderfox provider, Playwright, DOM scraping (removed; see [`decisions/0000-remove-traderfox.md`](decisions/0000-remove-traderfox.md))
- Long/short hedging strategy (Mansfield RS, regime split, ranking) — deferred per [ADR-0003](decisions/0003-defer-rs-hedging-epic.md)
- Paid-data integrations (CDS, Bloomberg, FMP) — explicitly out of scope per [`UserStory.md`](UserStory.md)

## Distribution scope

The repo tree splits into three concentric scopes per
[ADR-0007](decisions/0007-package-vs-infrastructure-boundary.md):
**package** (`src/` + `README.md`, ships in the wheel),
**repo infrastructure** (`scripts/`, `.github/`, `Makefile`, lint
configs — CI-only), and **demo + dev docs** (`ui/`,
`docs/*.md`, `tests/` — reference / showcase only). One-way
direction rule: infrastructure and demo MAY import from package;
package MUST NOT reference scripts or workflow artifacts, and the
`data` branch is consumed only by the demo dashboard.
