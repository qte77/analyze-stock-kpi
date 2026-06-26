# analyze-stock-kpi

> Library-based stock KPI CLI: per-ticker fundamentals via yfinance plus a daily CNN Fear & Greed sentiment snapshot — no API keys, no scraping.

[![version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/qte77/analyze-stock-kpi/blob/main/CHANGELOG.md)
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
- 11 bundled **universes** — watchlists, regional lists, screener long/short, aggregated
  best/worst — driven by an inline list, a file, or a preset.
- A 13-column **rich CLI table** (P/E, PEG, Beta, ROE/ROA, Current, Sortino, Score, …)
  with an optional composite-score breakdown.
- A static **[live dashboard](https://qte77.github.io/analyze-stock-kpi/)** (deployed to
  GitHub Pages): tabbed F&G panel + sortable universe table + row-click KPI detail.
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
```

CLI args double as env vars with the `SSK_` prefix (e.g. `SSK_TICKERS=AAPL,MSFT`).
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
