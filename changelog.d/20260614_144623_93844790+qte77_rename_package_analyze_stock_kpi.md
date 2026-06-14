### Changed

- **Import package renamed `src` → `analyze_stock_kpi` (src-layout; [ADR-0009](docs/decisions/0009-rename-package-to-analyze-stock-kpi.md), resolving the ADR-0007 refactor candidate).** The package now lives at `src/analyze_stock_kpi/` and is imported as `analyze_stock_kpi` (e.g. `from analyze_stock_kpi.domain.universe import resolve_universe`); the CLI entry is `python -m analyze_stock_kpi`. **Breaking for any code importing `src.*`** — switch to `analyze_stock_kpi.*`. The PyPI distribution name (`analyze-stock-kpi`), CLI behaviour, and public API are otherwise unchanged.
