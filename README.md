# analyze-stock-kpi

[![version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://github.com/qte77/analyze-stock-kpi/blob/main/CHANGELOG.md)
[![validate](https://github.com/qte77/analyze-stock-kpi/actions/workflows/validate.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/validate.yaml)
[![Links (Fail Fast)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/links-fail-fast.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/links-fail-fast.yaml)
[![CodeFactor](https://www.codefactor.io/repository/github/qte77/analyze-stock-kpi/badge)](https://www.codefactor.io/repository/github/qte77/analyze-stock-kpi)
[![CodeQL](https://github.com/qte77/analyze-stock-kpi/actions/workflows/codeql.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/codeql.yaml)
[![SBOM](https://github.com/qte77/analyze-stock-kpi/actions/workflows/sbom.yaml/badge.svg)](https://github.com/qte77/analyze-stock-kpi/actions/workflows/sbom.yaml)
[![gh-pages](https://github.com/qte77/analyze-stock-kpi/actions/workflows/gh-pages.yaml/badge.svg)](https://qte77.github.io/analyze-stock-kpi/)

Library-based stock KPI CLI: per-ticker fundamentals via yfinance plus a
daily CNN Fear & Greed sentiment snapshot. No API keys, no scraping.

**Live demo**: [qte77.github.io/analyze-stock-kpi/](https://qte77.github.io/analyze-stock-kpi/) — weekly `qte77-watchlist` snapshot plus a tabbed F&G panel (rolling history ↔ long-term monthly median + average).

<details>
<summary>Dashboard screenshot · click to expand</summary>

![analyze-stock-kpi dashboard — CNN F&G banner with 2-year history, qte77-watchlist universe table with 13 KPI columns, factor-weighted Score heatmap](assets/images/analyze-stock-kpi-screenshot.png)

</details>

## Quickstart

```bash
make setup_dev                              # uv sync (default groups: dev + test)
make run UNIVERSE=qte77-watchlist           # fetch fundamentals -> results/fundamentals/<UTC>.json
make run TICKERS=AAPL,MSFT                  # ad-hoc ticker list
make run TICKERS=AAPL SHOW_SCORES=1         # also append composite-score columns
make help                                   # list available recipes
make validate                               # lint + types + complexity + md + tests
```

CLI args double as env vars with the `SSK_` prefix
(e.g. `SSK_TICKERS=AAPL,MSFT`).

## What it produces

* **Fundamentals** — `results/fundamentals/<UTC>.json`: one
  `FundamentalsSnapshot` per resolved ticker (~34 yfinance fields,
  including the computed `roi`, `rd_to_revenue`, `sortino_ratio`
  enrichments) plus seven 0-100 composite proxy scores (Quality /
  Dividend / Growth / Big Call / AAQS / HGI / Screener). Sparse
  fields for non-equities (FX, futures, crypto) are valid by design.
* **Sentiment** — `results/cnn_fg/YYYY.json`: per-year date-sorted
  array of CNN Fear & Greed snapshots (headline + 9 subindicators).
  Updated daily by a GitHub Actions cron at 21:30 UTC.

## Sample output

`make run TICKERS=AAPL` prints a CNN Fear & Greed banner, then a
13-column rich summary table:

> Ticker · Name · Sector · P/E (fwd) · PEG · Beta · R&D/Rev % ·
> Op M % · ROE % · ROA % · Current · Sortino · Score

With `--show-scores`, three legacy composite columns (Quality · Div ·
Growth) are appended. The [live demo dashboard][demo] renders the same
column set with row-click → KPI detail panel + sortable headers — see
the screenshot near the top of this README.

[demo]: https://qte77.github.io/analyze-stock-kpi/

The persisted JSON `results/fundamentals/<UTC>.json` carries one
`FundamentalsSnapshot` per ticker with a nested `composite_scores`
block. Field list lives in
[`src/data_sources/fundamentals.py`](src/data_sources/fundamentals.py);
composite formulas in
[`src/domain/composite_scores.py`](src/domain/composite_scores.py).

## Universe sources

In priority order:

| Source | Example |
|---|---|
| Inline list | `TICKERS=AAPL,MSFT` |
| File (one symbol per line) | `TICKERS_FILE=path/to/list.txt` |
| Preset | `UNIVERSE=qte77-watchlist` (see [`src/assets/universes/`](src/assets/universes) for all available presets) |

## Documentation

* [`docs/architecture.md`](docs/architecture.md) — module map + data flow
* [`docs/UserStory.md`](docs/UserStory.md) — product intent + non-goals
* [`docs/roadmap.md`](docs/roadmap.md) — milestones + tracked issues
* [`docs/demo/`](docs/demo) — static dashboard sources (deployed to GitHub Pages); preview locally with `make preview` (serves on `:8000`, data fetched cross-origin from the `data` branch)
* [`docs/decisions/`](docs/decisions) — [MADR](https://adr.github.io/madr/) ADRs (Traderfox removal,
  `financetoolkit` deferral, simplified composites, RS hedging deferral)
* [`docs/cnn-fg-api.md`](docs/cnn-fg-api.md) — CNN F&G endpoint schema
* [`CHANGELOG.md`](CHANGELOG.md) — release history + known issues
* [`CONTRIBUTING.md`](CONTRIBUTING.md) — shared dev workflow (tests, commits, GHA, changelog fragments, release flow)
* [`AGENTS.md`](AGENTS.md) — AI-agent-specific behavioural rules

## License

[Apache 2.0](LICENSE)
