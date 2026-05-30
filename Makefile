.SILENT:
.ONESHELL:
.PHONY: \
	setup_uv setup_dev setup_lychee setup_npm_tools \
	lint autofix check_types check_complexity lint_md lint_js lint_links \
	test test_cov test_js retest validate \
	run preview preview_local \
	changelog_new changelog_preview changelog_release \
	clean help
.DEFAULT_GOAL := help

VERBOSE ?=
ifndef VERBOSE
  RUFF_QUIET := --quiet
  PYTEST_QUIET := -q --tb=short --no-header
  PYRIGHT_QUIET := > /dev/null
endif


# MARK: SETUP


setup_uv:  ## Install uv (if missing)
	if command -v uv > /dev/null 2>&1; then
		echo "uv already installed: $$(uv --version)"
	else
		curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | sh
		echo "NOTE: restart your shell or run 'source $$HOME/.local/bin/env'"
	fi

setup_dev: setup_uv  ## uv sync (default groups: dev + test)
	uv sync

setup_lychee:  ## Install lychee link checker (Rust binary; sudo)
	curl -sL https://github.com/lycheeverse/lychee/releases/latest/download/lychee-x86_64-unknown-linux-gnu.tar.gz | sudo tar xz -C /usr/local/bin lychee
	echo "lychee version: $$(lychee --version)"

setup_npm_tools:  ## Install npm-based dev tools (markdownlint-cli, typescript)
	npm install -gs markdownlint-cli typescript
	echo "markdownlint version: $$(markdownlint --version)"
	echo "typescript version: $$(tsc --version)"


# MARK: QUALITY


lint:  ## ruff check
	echo "--- lint"
	uv run ruff check $(RUFF_QUIET) .

autofix:  ## ruff format + ruff check --fix
	uv run ruff format $(RUFF_QUIET) . && uv run ruff check --fix $(RUFF_QUIET) .

check_types:  ## pyright type check
	echo "--- check_types"
	uv run pyright src $(PYRIGHT_QUIET)

check_complexity:  ## complexipy cognitive complexity gate (max 10)
	echo "--- check_complexity"
	uv run complexipy src --max-complexity-allowed 10

lint_md:  ## markdownlint *.md (uses .markdownlint.json)
	echo "--- lint_md"
	markdownlint --config .markdownlint.json '**/*.md' \
	  --ignore '.venv/**' --ignore 'results/**' --ignore 'node_modules/**' \
	  --ignore 'changelog.d/**'

lint_js:  ## node syntax check + tsc JSDoc type check on docs/demo/
	echo "--- lint_js"
	node --check docs/demo/app.js
	tsc --noEmit --project docs/demo

lint_links:  ## lychee broken-link checker (network — slow; mandatory in CI)
	echo "--- lint_links"
	lychee --config .lychee.toml .

test:  ## pytest
	echo "--- test"
	uv run pytest $(PYTEST_QUIET)

test_cov:  ## pytest with coverage (--cov-fail-under=0; raise once tests exist)
	echo "--- test_cov"
	uv run pytest --cov=src --cov-fail-under=0 $(PYTEST_QUIET)

test_js:  ## vitest run on tests/demo/ (closes #131; non-trivial units only)
	echo "--- test_js"
	npx --yes vitest run tests/demo --passWithNoTests

retest:  ## rerun last failed tests only
	uv run pytest --lf -x

validate:  ## CI gate: lint + check_types + check_complexity + lint_md + lint_js + test_cov + test_js
	set -e
	$(MAKE) -s lint
	$(MAKE) -s check_types
	$(MAKE) -s check_complexity
	$(MAKE) -s lint_md
	$(MAKE) -s lint_js
	$(MAKE) -s test_cov
	$(MAKE) -s test_js


# MARK: RUN


run:  ## run fundamentals (UNIVERSE=qte77-watchlist | TICKERS=AAPL,MSFT | TICKERS_FILE=path | PERIOD=5y | SHOW_SCORES=1)
	uv run python -m src \
	  $(if $(UNIVERSE),--universe $(UNIVERSE)) \
	  $(if $(TICKERS),--tickers $(TICKERS)) \
	  $(if $(TICKERS_FILE),--tickers-file $(TICKERS_FILE)) \
	  $(if $(PERIOD),--period $(PERIOD)) \
	  $(if $(SHOW_SCORES),--show-scores)

preview:  ## serve docs/demo/ locally on PORT=8000 (data fetched cross-origin from data branch)
	echo "--- preview"
	echo "Dashboard: http://localhost:$${PORT:-8000}/  (Ctrl+C to stop)"
	uv run python -m http.server $${PORT:-8000} --directory docs/demo

preview_local:  ## like preview but serves the latest `make run` output (UNIVERSE=qte77-watchlist by default)
	echo "--- preview_local"
	U=$${UNIVERSE:-qte77-watchlist}; \
	LATEST=$$(ls -t results/fundamentals_*.json 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
	  echo "No results/fundamentals_*.json found. Run 'make run' first."; exit 1; \
	fi; \
	mkdir -p "results/demo/$$U"; \
	cp "$$LATEST" "results/demo/$$U/$$(date -u +%Y-%m-%d).json"; \
	uv run python scripts/build_demo_manifest.py "results/demo/$$U"
	echo ""
	echo "  Open in browser:  http://localhost:$${PORT:-8000}/docs/demo/?base=.."
	echo "  (the http.server URL printed below is the repo root — do NOT use it)"
	echo ""
	uv run python -m http.server $${PORT:-8000} --directory .


# MARK: CHANGELOG


changelog_new:  ## create + stage a new changelog fragment under changelog.d/
	uv run scriv create --add

changelog_preview:  ## preview the assembled release entry without consuming fragments
	uv run scriv print

changelog_release:  ## collect fragments into CHANGELOG.md (VERSION=X.Y.Z required); run before bump-my-version
	test -n "$(VERSION)" || (echo "VERSION required, e.g. make changelog_release VERSION=0.6.0"; exit 2)
	uv run scriv collect --version $(VERSION)


# MARK: CLEAN


clean:  ## remove caches
	rm -rf .pytest_cache .ruff_cache .pyright_cache .coverage htmlcov
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete


# MARK: HELP


help:  ## show available recipes grouped by section
	echo "Usage: make [recipe] [VERBOSE=1]"
	echo ""
	awk '/^# MARK:/ { \
		section = substr($$0, index($$0, ":")+2); \
		printf "\n\033[1m%s\033[0m\n", section \
	} \
	/^[a-zA-Z0-9_-]+:.*?##/ { \
		helpMessage = match($$0, /## (.*)/); \
		if (helpMessage) { \
			recipe = $$1; \
			sub(/:/, "", recipe); \
			printf "  \033[36m%-14s\033[0m %s\n", recipe, substr($$0, RSTART + 3, RLENGTH) \
		} \
	}' $(MAKEFILE_LIST)
