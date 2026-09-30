# analyze-stock-kpi

> Library-based stock KPI CLI: per-ticker fundamentals via yfinance plus a daily CNN Fear & Greed sentiment snapshot — no API keys, no scraping.

[![version](https://img.shields.io/badge/version-1.6.0-blue.svg)](https://github.com/qte77/analyze-stock-kpi/blob/main/CHANGELOG.md)
[![validate](https://github.com/qte77/analyze-stock-kpi/actions/workflows/validate.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/validate.yaml)
[![Lint MD and Links](https://github.com/qte77/analyze-stock-kpi/actions/workflows/lint-md-links.yml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/lint-md-links.yml)
[![CodeFactor](https://www.codefactor.io/repository/github/qte77/analyze-stock-kpi/badge)](https://www.codefactor.io/repository/github/qte77/analyze-stock-kpi)
[![CodeQL](https://github.com/qte77/analyze-stock-kpi/actions/workflows/codeql.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/codeql.yaml)
[![SBOM](https://github.com/qte77/analyze-stock-kpi/actions/workflows/sbom.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/sbom.yaml)
[![gh-pages](https://github.com/qte77/analyze-stock-kpi/actions/workflows/gh-pages.yaml/badge.svg)](https://qte77.github.io/analyze-stock-kpi/)

## What

- Per-ticker **fundamentals** from yfinance — ~35 fields plus computed enrichments and
  seven 0–100 composite "qte77 Score" proxies — persisted to `results/fundamentals/<UTC>.json`.
- A daily **CNN Fear & Greed** sentiment snapshot (headline + subindicators) at
  `results/series/cnn_fg/YYYY.json`, refreshed by a GitHub Actions cron.
- 9 bundled **universes** — watchlists, regional lists, aggregated best/worst — driven by an
  inline list, a file, or a preset.
- A 13-column **rich CLI table** (P/E, PEG, Beta, ROE/ROA, Current, Sortino, Score, …)
  with an optional composite-score breakdown.
- A static **[live dashboard](https://qte77.github.io/analyze-stock-kpi/)** (deployed to
  GitHub Pages). It opens on **Today's picks**, the best and worst 25 stocks by qte77 Score,
  under a collapsible **Market mood** bar (CNN F&G, long-term context, 5s10s). Below it, a
  hypothetical, point-in-time backtested long/short **25/25 book**: a chart with SPY's total
  return as a reference line and one plain sentence on how it has done. Everything else is
  behind **How it's tested**: the metrics, the rebalance log (when, why, and which names
  changed), the caveats, and a second, **reconstructed backfill** series since 2023 (an
  approximation, never mixed with the headline series of genuine decisions since 2026-05-31).
  Both are equal-weight, shown gross and net of a 10 bp turnover cost, across six rebalance
  cadences (see [ADR-0013](docs/decisions/0013-point-in-time-backtest.md)). A sortable table
  of every universe with row-click KPI detail sits behind "Browse all stocks" (a quick search,
  `/`, opens it filtered), followed by a Methodology section.
- **No API keys, no scraping** — keyless public sources only.

<details>
<summary>Dashboard screenshot · click to expand</summary>

![analyze-stock-kpi dashboard — CNN F&G banner with 2-year history, qte77-watchlist universe table with 13 KPI columns, factor-weighted Score heatmap](assets/images/analyze-stock-kpi-screenshot.png)

</details>

## How

```bash
make setup_dev                              # uv sync (dev + test groups)
make run UNIVERSE=qte77-watchlist           # fundamentals -> results/fundamentals/<UTC>.json
make run TICKERS=AAPL,MSFT                  # ad-hoc tickers (SHOW_SCORES=1 appends score columns)
make help                                   # list available recipes
make validate                               # lint + types + complexity + md + tests
make preview                                # dashboard at http://localhost:8000/analyze-stock-kpi/ (PORT=8000)
```

CLI args double as env vars with the `SSK_` prefix (e.g. `SSK_TICKERS=AAPL,MSFT`).
Per-ticker Sortino is reported at fixed 1y/3y/5y/10y/20y/30y windows plus an
optional operator-chosen frame via `--sortino-from YYYY-MM-DD [--sortino-to
YYYY-MM-DD]` (`--sortino-to` defaults to each ticker's latest close), e.g.:

```bash
uv run python -m analyze_stock_kpi --tickers AAPL --sortino-from 2015-01-01 --sortino-to 2020-12-31
```

The dashboard keeps its state in the URL, so views can be shared. A parameter is omitted
while it has its default value, and clearing a filter in the UI removes it from the URL:

| Parameter | Values | Default |
|---|---|---|
| `universe` | comma-separated universe ids, e.g. `sp500` | the first universe |
| `date` | snapshot date `YYYY-MM-DD` | latest |
| `sort` / `sortDir` | a column key, e.g. `composite_scores.screener_score` / `1` = ascending | Score, descending |
| `filter` | ticker/name text filter | none |
| `sector` | sector name (from the donut) | none |
| `view` | `simple` or `detailed` | `simple` |
| `ltFgWindow` / `ycWindow` | `1y`, `5y`, `10y`, `all` (a non-default value opens the Market mood panel on its long-term tab) | `all` |
| `theme` | `light`, `dark`, `system` | the last choice (stored in the browser), else `system` |
| `base` | data origin URL, e.g. a fork's `raw.githubusercontent.com/<owner>/<repo>/data` | this deployment's own `data` branch |

A non-default table parameter (`universe`, `date`, `sort`/`sortDir`, `filter`, `sector`,
`view`) opens the collapsed "Browse all stocks" section on load, so a shared table view is
visible straight away. The Methodology topics have stable anchors for linking: `#methodology`,
`#why-charts`, `#why-universes`, `#backtest-rules` and `#decisions`. On the page, `/` focuses
the quick search, and the arrow keys (plus Home/End) move between tabs.

See [`docs/architecture.md`](docs/architecture.md) for the module map, the persisted
`FundamentalsSnapshot` fields, the composite-score formulas, and the universe presets.

## Why

Fundamentals-plus-sentiment dashboards usually sit behind a paid data terminal or a
fragile scraping layer. analyze-stock-kpi fills the gap between a raw `yfinance` REPL and
a paid feed: a reproducible, **keyless** CLI + dashboard over public sources, versioned to
a `data` branch so the demo and the numbers stay auditable. See
[`docs/UserStory.md`](docs/UserStory.md) for product intent and non-goals.

## References

- [`docs/architecture.md`](docs/architecture.md) — module map + data flow
- [`docs/UserStory.md`](docs/UserStory.md) — product intent + non-goals
- [`docs/roadmap.md`](docs/roadmap.md) — milestones + tracked issues
- [`ui/`](ui) — static dashboard sources (deployed to GitHub Pages); preview with `make preview`
- [`docs/decisions/`](docs/decisions) — [MADR](https://adr.github.io/madr/) ADRs
- [`docs/cnn-fg-api.md`](docs/cnn-fg-api.md) — CNN F&G endpoint schema
- [`CHANGELOG.md`](CHANGELOG.md) — release history + known issues
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev workflow (tests, commits, GHA, changelog, release)
- [`AGENTS.md`](AGENTS.md) — AI-agent-specific behavioural rules

## License

[Apache 2.0](LICENSE)
