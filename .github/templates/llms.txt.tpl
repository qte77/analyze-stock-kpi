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

## Source

- [src/__main__.py](${BLOB}/src/__main__.py)
- [src/config.py](${BLOB}/src/config.py)
- [src/domain/composite_scores.py](${BLOB}/src/domain/composite_scores.py)
- [src/domain/universe.py](${BLOB}/src/domain/universe.py)
- [src/data_sources/fundamentals.py](${BLOB}/src/data_sources/fundamentals.py)
- [src/data_sources/sentiment.py](${BLOB}/src/data_sources/sentiment.py)
- [src/data_sources/usaspending.py](${BLOB}/src/data_sources/usaspending.py)
- [src/data_sources/sec/cik_map.py](${BLOB}/src/data_sources/sec/cik_map.py)
- [src/data_sources/sec/submissions.py](${BLOB}/src/data_sources/sec/submissions.py)
- [src/orchestrators/federal_contractors.py](${BLOB}/src/orchestrators/federal_contractors.py)
- [src/utils/http_ua.py](${BLOB}/src/utils/http_ua.py)
- [src/utils/parse_args.py](${BLOB}/src/utils/parse_args.py)

## Reference

- [pyproject.toml](${BLOB}/pyproject.toml)
- [Makefile](${BLOB}/Makefile)
- [docs/cnn-fg-api.md](${BLOB}/docs/cnn-fg-api.md)
- [scripts/build_demo_manifest.py](${BLOB}/scripts/build_demo_manifest.py)

## Optional

- [tests/conftest.py](${BLOB}/tests/conftest.py)
