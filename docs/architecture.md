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
| Filesystem write (snapshots) | `__main__._persist_snapshots` | fail-loud | disk full / permission denied → abort |
| Filesystem write (CNN cache) | `sentiment._write_year` | fail-loud | same rationale |
| Filesystem read (universe preset) | `universe._read_symbol_file` | fail-loud | config error — missing preset means the user passed a wrong name |
| Filesystem read (EDGAR cache) | `sec.cik_map._fetch_json` (cached read) | fail-loud | corrupt JSON shouldn't happen on a CDN-served read; if it does, user removes `results/edgar/` to recover |
| Pydantic `model_validate` | every call | fail-loud | upstream schema break or programmer error — never wrap |

## Modules

```text
src/
├── __main__.py                       entrypoint: resolve universe -> per-ticker fetch -> rich table + results/fundamentals/<UTC>.json; `--refresh-universe NAME` branches to an orchestrator
├── __version__.py                    package version constant
├── config.py                         AppSettings(BaseSettings) — every URL/path/timeout/HTTP-shape constant; env-overridable via SSK_*
├── domain/
│   ├── universe.py                   resolve_universe(args) -> list[ticker]; presets in src/assets/universes/*.txt
│   └── composite_scores.py           quality/dividend/growth/big_call/aaqs/hgi/screener 0-100 proxies; `compute_scores(snap) -> CompositeScores`
├── data_sources/
│   ├── fundamentals.py               fetch_fundamentals / fetch_price_history / fetch_universe_fundamentals — yfinance
│   ├── sentiment.py                  fetch_fear_greed() -> FearGreedSnapshot; `python -m src.data_sources.sentiment` merges into per-year files results/cnn_fg/YYYY.json
│   ├── usaspending.py                fetch_top_contractors(...) -> list[RecipientRecord] — usaspending.gov POST client
│   └── sec/
│       ├── cik_map.py                resolve_cik / lookup_record — EDGAR company_tickers_exchange.json with HTTP conditional GET + disk cache
│       └── submissions.py            fetch_last_filed / enrich_snapshot_sec — EDGAR submissions API
├── orchestrators/
│   └── federal_contractors.py        build_universe(*, fy=None, top_n=100) -> tuple[list[str], list[AuditRow]]; chains usaspending → EDGAR → yfinance
├── assets/
│   └── universes/                    preset *.txt ticker lists (one per universe name)
└── utils/
    ├── http_ua.py                    USER_AGENTS pool (re-exported from settings), STABLE_USER_AGENT, pick_user_agent(), require_https()
    └── parse_args.py                 CliArgs(BaseSettings) — pydantic-settings CLI + env (env_prefix="SSK_")
```

## Data flow (v0.5.0 current)

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

A separate daily GitHub Actions cron (`.github/workflows/fear-greed.yaml`) runs `python -m src.sentiment`, which loads each affected per-year history file (`results/cnn_fg/YYYY.json` — a date-sorted JSON array), upserts the live headline (force, since CNN updates intraday) plus any historical points CNN now exposes that are missing or stale on disk, and rewrites only the year files that changed. The workflow checks out the `data` branch (not `main`) so accumulated history is present before `sentiment.py` merges, then commits the changed year files via the REST Git Data API (Blob → Tree → Commit → Ref) invoked from `actions/github-script@v9`. Commits created via this API path with the workflow's `GITHUB_TOKEN` are signed by GitHub's web-flow PGP key and marked `verified: true` — required by the repo's `required_signatures` ruleset on `main`. The `data` branch lives outside the ruleset's `~DEFAULT_BRANCH` scope, so direct pushes to it succeed.

A second cron (`.github/workflows/demo-snapshot.yaml`, Sunday 06:15 UTC) runs `make run UNIVERSE=qte77-watchlist`, renames the timestamped output to `results/demo/qte77-watchlist/YYYY-MM-DD.json`, rebuilds the manifest via `scripts/build_demo_manifest.py`, and commits both files to the `data` branch through the same verified-commit mechanism.

A third workflow (`.github/workflows/gh-pages.yaml`) deploys the static dashboard at `docs/demo/{index.html, app.js, style.css}` to GitHub Pages via `actions/upload-pages-artifact` + `actions/deploy-pages` whenever those files change. The dashboard fetches data files at runtime cross-origin from `raw.githubusercontent.com/qte77/analyze-stock-kpi/data/results/…`; this decouples data-update cadence from page deploys.

v0.5.0 attaches a `CompositeScores` object to every `FundamentalsSnapshot` after fetch via `model_copy(update={"composite_scores": compute_scores(snap)})`. The rich summary table appends Quality / Div / Growth columns only when `--show-scores` is passed; persistence carries the composites unconditionally.

## Public types (`pydantic.BaseModel`)

| Type | Module | Role |
|---|---|---|
| `CliArgs(BaseSettings)` | `utils/parse_args.py` | CLI + env input — `cli_parse_args=True`, `extra="forbid"` |
| `FundamentalsSnapshot` | `fundamentals.py` | Per-ticker fundamentals — ~34 aliased fields including the post-fetch enrichments `roi`, `rd_to_revenue`, `sortino_ratio` (see [ADR-0004](decisions/0004-price-history-composite-input.md)); sparse for non-equities |
| `FearGreedSnapshot` | `sentiment.py` | CNN F&G headline (score, rating, timestamp, prev close/1w/1m/1y) + optional `subindicators` map of 9 named `SubindicatorReading` entries (score, rating, raw_value); see [`cnn-fg-api.md`](cnn-fg-api.md) for what's backfillable vs daily-only |
| `CompositeScores` | `composite_scores.py` | Quality/dividend/growth/big_call/aaqs/hgi/screener 0-100 proxies derived from `FundamentalsSnapshot`; simplified formulas per [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md) amended by [`decisions/0004-price-history-composite-input.md`](decisions/0004-price-history-composite-input.md) |

## External boundaries

- **`yfinance`** — fundamentals (`Ticker.info`) + price history (`Ticker.history`); rate-limit risk; live tests tagged `@pytest.mark.network` (excluded from default `make test`, opt in via `pytest -m network`). `_normalize_yfinance_info` in `src/data_sources/fundamentals.py` divides the current percentage-shaped `info["dividendYield"]` by 100 at the fetch boundary so the rest of the codebase sees fractional yields. `fetch_universe_fundamentals` adds a batched `yf.download(tickers, period="1y")` once per run for Sortino — see [ADR-0004](decisions/0004-price-history-composite-input.md). `_fetch_rd_to_revenue` reads `Ticker.income_stmt` per EQUITY ticker for the R&D / Revenue ratio.
- **SEC EDGAR JSON endpoints** — `www.sec.gov/files/company_tickers_exchange.json` (CIK / ticker registry) and `data.sec.gov/submissions/CIK<10>.json` (per-company filing index); require *identity-shape* `User-Agent` (operator-supplied; **not** browser-shape — opposite of CNN below). UA sourced from `settings.sec_user_agent` (`SSK_SEC_USER_AGENT` env, no in-source default); `_fetch_json` / `fetch_last_filed` fail loud if unset. Stdlib `urllib.request`, no extra deps. Disk cache at `settings.edgar_cache_dir` carries warm runs; first-call rejection cannot fall back. Root-cause analysis in [ADR-0006 amendment 2026-05-22 (later)](decisions/0006-federal-contractors-universe.md).
- **CNN F&G JSON endpoint** — `production.dataviz.cnn.io/index/fearandgreed/graphdata`; requires browser-shape headers (UA + `Accept` + `Referer`; returns 418 otherwise); stdlib `urllib.request`, no extra deps. Observed schema in [`cnn-fg-api.md`](cnn-fg-api.md). Classified as Tier 0 (keyless, default-on, public-`data`-branch-persistable) per [ADR-0005](decisions/0005-sentiment-risk-sources.md)'s three-tier framework — additional sentiment / risk sources must declare their tier under the same rubric.
- **GitHub Actions cron** — `.github/workflows/fear-greed.yaml` (daily 21:30 UTC) commits per-year history files `results/cnn_fg/YYYY.json`; `.github/workflows/demo-snapshot.yaml` (Sunday 06:15 UTC) commits per-week universe snapshots under `results/demo/<UNIVERSE>/`. Both target the `data` branch via verified REST Git Data API commits from `actions/github-script@v9`.
- **`financetoolkit`** — *not used; v0.5.0 composites use simplified formulas with point-in-time `FundamentalsSnapshot` inputs only. See [`decisions/0001-defer-financetoolkit.md`](decisions/0001-defer-financetoolkit.md) and [`decisions/0002-simplified-composites.md`](decisions/0002-simplified-composites.md).*

## What's not here

- Traderfox provider, Playwright, DOM scraping (removed; see [`decisions/0000-remove-traderfox.md`](decisions/0000-remove-traderfox.md))
- Long/short hedging strategy (Mansfield RS, regime split, ranking) — deferred per roadmap §0.5+
- Paid-data integrations (CDS, Bloomberg, FMP) — explicitly out of scope per [`UserStory.md`](UserStory.md)

## Distribution scope

The repo tree splits into three concentric scopes per
[ADR-0007](decisions/0007-package-vs-infrastructure-boundary.md):
**package** (`src/` + `README.md`, ships in the wheel),
**repo infrastructure** (`scripts/`, `.github/`, `Makefile`, lint
configs — CI-only), and **demo + dev docs** (`docs/demo/`,
`docs/*.md`, `tests/` — reference / showcase only). One-way
direction rule: infrastructure and demo MAY import from package;
package MUST NOT reference scripts or workflow artifacts, and the
`data` branch is consumed only by the demo dashboard.
