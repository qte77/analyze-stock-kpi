# Architecture Decision Records

Format: [MADR](https://adr.github.io/madr/) — filenames `NNNN-kebab.md`,
numbers assigned sequentially and never reused.

| # | Title | Status |
|---|---|---|
| [0000](0000-remove-traderfox.md) | Remove Traderfox scraper, adopt library-based KPIs | Accepted 2026-05-09 |
| [0001](0001-defer-financetoolkit.md) | Defer `financetoolkit` to v0.5.0 | Accepted 2026-05-10 |
| [0002](0002-simplified-composites.md) | Simplified composite proxy scores | Accepted 2026-05-10 |
| [0003](0003-defer-rs-hedging-epic.md) | Defer the v0.6.0 RS hedging epic | Accepted 2026-05-11 |
| [0004](0004-price-history-composite-input.md) | Allow price-history-derived inputs in composite scores | Accepted 2026-05-14 |
| [0005](0005-sentiment-risk-sources.md) | Three-tier sentiment + risk source framework | Accepted 2026-05-20 |
| [0006](0006-federal-contractors-universe.md) | Federal-contractors universe via usaspending.gov + EDGAR | Accepted 2026-05-20 |
| [0007](0007-package-vs-infrastructure-boundary.md) | Package vs repo-infrastructure boundary | Accepted 2026-05-21 |
| [0008](0008-ui-promotion-to-ui.md) | Promote demo dashboard to top-level `ui/` | Accepted 2026-06-13 |
| [0009](0009-rename-package-to-analyze-stock-kpi.md) | Rename import package `src` → `analyze_stock_kpi` | Accepted 2026-06-14 |
| [0010](0010-consolidate-js-tooling-into-ui-vite-build.md) | Consolidate JS tooling into `ui/` with a Vite build | Accepted 2026-06-19 |
| [0011](0011-equity-macro-overlay-via-spy-indexed-returns.md) | Equity-macro overlay via SPY indexed returns | Accepted 2026-06-19 |

New ADR: copy the most recent file, increment the number, fill in
**Status / Context / Decision / Consequences**. Supersedes / amendments
go in the **Status** line of both ADRs.
