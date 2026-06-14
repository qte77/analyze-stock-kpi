# ${PROJECT_NAME}

> ${PROJECT_DESC}

## Documentation

- [README](${BLOB}/README.md)
- [AGENTS](${BLOB}/AGENTS.md)
- [Architecture](${BLOB}/docs/architecture.md)
- [User story](${BLOB}/docs/UserStory.md)
- [Roadmap](${BLOB}/docs/roadmap.md)
- [Changelog](${BLOB}/CHANGELOG.md)

## Decisions (ADRs)

- [ADR-0000: Remove Traderfox](${BLOB}/docs/decisions/0000-remove-traderfox.md)
- [ADR-0001: Defer financetoolkit](${BLOB}/docs/decisions/0001-defer-financetoolkit.md)
- [ADR-0002: Simplified composites](${BLOB}/docs/decisions/0002-simplified-composites.md)
- [ADR-0003: Defer RS hedging epic](${BLOB}/docs/decisions/0003-defer-rs-hedging-epic.md)
- [ADR-0004: Price-history composite input](${BLOB}/docs/decisions/0004-price-history-composite-input.md)
- [ADR-0005: Three-tier sentiment + risk sources](${BLOB}/docs/decisions/0005-sentiment-risk-sources.md)
- [ADR-0006: Federal-contractors universe](${BLOB}/docs/decisions/0006-federal-contractors-universe.md)
- [ADR-0007: Package vs infrastructure boundary](${BLOB}/docs/decisions/0007-package-vs-infrastructure-boundary.md)
- [ADR-0008: Promote demo to top-level ui/](${BLOB}/docs/decisions/0008-ui-promotion-to-ui.md)
- [ADR-0009: Rename package to analyze_stock_kpi](${BLOB}/docs/decisions/0009-rename-package-to-analyze-stock-kpi.md)

## Source

- [src/analyze_stock_kpi/__main__.py](${BLOB}/src/analyze_stock_kpi/__main__.py)
- [src/analyze_stock_kpi/config.py](${BLOB}/src/analyze_stock_kpi/config.py)
- [src/analyze_stock_kpi/domain/composite_scores.py](${BLOB}/src/analyze_stock_kpi/domain/composite_scores.py)
- [src/analyze_stock_kpi/domain/universe.py](${BLOB}/src/analyze_stock_kpi/domain/universe.py)
- [src/analyze_stock_kpi/data_sources/fundamentals.py](${BLOB}/src/analyze_stock_kpi/data_sources/fundamentals.py)
- [src/analyze_stock_kpi/data_sources/sentiment.py](${BLOB}/src/analyze_stock_kpi/data_sources/sentiment.py)
- [src/analyze_stock_kpi/data_sources/usaspending.py](${BLOB}/src/analyze_stock_kpi/data_sources/usaspending.py)
- [src/analyze_stock_kpi/data_sources/sec/cik_map.py](${BLOB}/src/analyze_stock_kpi/data_sources/sec/cik_map.py)
- [src/analyze_stock_kpi/data_sources/sec/submissions.py](${BLOB}/src/analyze_stock_kpi/data_sources/sec/submissions.py)
- [src/analyze_stock_kpi/orchestrators/federal_contractors.py](${BLOB}/src/analyze_stock_kpi/orchestrators/federal_contractors.py)
- [src/analyze_stock_kpi/utils/http_ua.py](${BLOB}/src/analyze_stock_kpi/utils/http_ua.py)
- [src/analyze_stock_kpi/utils/parse_args.py](${BLOB}/src/analyze_stock_kpi/utils/parse_args.py)

## Reference

- [pyproject.toml](${BLOB}/pyproject.toml)
- [Makefile](${BLOB}/Makefile)
- [docs/cnn-fg-api.md](${BLOB}/docs/cnn-fg-api.md)
- [scripts/build_demo_manifest.py](${BLOB}/scripts/build_demo_manifest.py)

## Optional

- [tests/conftest.py](${BLOB}/tests/conftest.py)
