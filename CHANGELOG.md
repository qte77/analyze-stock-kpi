# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bugfixes.
- `Security` in case of vulnerabilities.

<!-- scriv-insert-here -->

## [1.0.0] - 2026-05-17

### Removed

- `.github/dependabot.yaml` (the duplicate config that used the broken `pip` ecosystem — no-op for this uv-managed repo). The remaining `.github/dependabot.yml` now carries the `commit-message` prefix + labels that previously lived only on the deleted file. Dependabot only ever loaded one of the two configs anyway; this removes the ambiguity.

### Changed

- `llms.txt` is now **auto-generated** at `docs/llms.txt` by the `llms-txt.yaml` workflow using the [qte77/gha-llms-txt-action](https://github.com/qte77/gha-llms-txt-action) composite action (Marketplace-listed; pinned to the v0.1.0 commit SHA per the repo's full-SHA rule). The hand-curated `llms.txt` at repo root is replaced by a template at `.github/templates/llms.txt.tpl` that uses `${BLOB}` / `${PROJECT_NAME}` / `${PROJECT_DESC}` envsubst variables. The action validates that every `${BLOB}/path` reference points to an existing file, preventing stale links over time.
- **complexipy cognitive-complexity gate tightened from 15 to 10** in `make check_complexity` (and the validate CI path). The current codebase peaks at 9 (`_batch_close_prices`, `_index_subindicator_data_by_date`), so this is a no-op for existing code but prevents regressions. Brings the cognitive-complexity ceiling in line with the existing ruff mccabe `max-complexity = 10`, so both gates now enforce the same budget.
- **ruff `S` rule set (flake8-bandit) enabled** in `tool.ruff.lint.select`. Replaces the legacy Bandit `# nosec B310` markers with ruff-native `# noqa: S310` on the two `urllib.request` call sites in `src/sentiment.py` (the explicit `https://` scheme check is the defense-in-depth boundary, kept inline). The single test-side `subprocess.run` in `tests/test_build_demo_manifest.py` gets `# noqa: S603` (hardcoded local script, no external argv). `tests/**` continues to ignore `S101` (pytest `assert` convention). Future security regressions are now caught by `make lint` instead of needing a separate Bandit invocation.
- `screener_score` rewritten as a factor-weighted composite. The 9 KPIs are grouped into 4 thematic factors (Profitability, Valuation, Risk, Momentum) with per-factor input minimums (>= 2/4, >= 1/2, >= 1/2, 1/1); factors below their minimum drop from the composite and remaining factors weigh equally. The previous input-equal mean over-weighted Profitability (4 of 9 inputs = 44%); the new math gives each thematic dimension equal voice. Existing >= 5 of 9 total-input gate unchanged. Tooltips on the Score column and detail panel updated to spell out the per-factor minimums.

### Fixed

- Dashboard row-detail panel now dismisses on outside click or Escape, while
  clicks inside the panel and row-to-row detail swaps keep the panel open.

- **Dashboard `<thead>` actually sticks on vertical scroll now.** `docs/demo/style.css` `.table-wrap` previously set only `overflow-x: auto`, which per CSS spec makes the wrapper the containing block for nested `position: sticky` elements but provides no vertical scroll port — so `thead th { top: 0 }` had nowhere to stick and scrolled away with the page. Switched the wrapper to `overflow: auto` + `max-height: 75vh` so both sticky-top (thead) and sticky-left (Ticker + Name columns) anchor against the same scroll port. Delivers on the v0.6.0 "sticky `<thead>` so column headers stay visible on vertical scroll" CHANGELOG promise.

## [0.6.0] - 2026-05-15

### Added

- **Static demo dashboard on GitHub Pages** at `https://qte77.github.io/analyze-stock-kpi/` (#59) — F&G 2-year chart + sortable universe table with date selector. Vanilla HTML/JS/CSS in `docs/demo/`; Chart.js v4.5.1 via CDN; no build step. Deploys via modern `actions/upload-pages-artifact` + `actions/deploy-pages` in `.github/workflows/gh-pages.yaml`.
- **Weekly fundamentals snapshot workflow** `.github/workflows/demo-snapshot.yaml` (Sunday 06:15 UTC) commits `results/demo/qte77-watchlist/YYYY-MM-DD.json` + `index.json` manifest to the `data` branch.
- **`scripts/build_demo_manifest.py`** — stdlib-only Python that rebuilds the per-universe manifest from on-disk snapshot files.
- **Snapshot enrichments** — `trailing_peg_ratio` (alias `trailingPegRatio`), `roi` (computed from `info`: NetIncome / (BookEquity + Debt - Cash)), `rd_to_revenue` (from `Ticker.income_stmt`, EQUITY-gated), `sortino_ratio` (annualized 1y, batched via `yf.download` at universe level). Per [ADR-0004](docs/decisions/0004-price-history-composite-input.md).
- **7th composite score** `CompositeScores.screener_score` — aggregates the 9 visible main-table KPIs into a single 0-100 ranking.
- **Dashboard KPI expansion** — `docs/demo/` main table goes 8 → 13 columns (P/E (fwd) · PEG · Beta · R&D/Rev % · Op M % · ROE % · ROA % · Current · Sortino · Score added; original `P/E` and `Div %` moved to detail panel). English `title=` tooltips on every column header and detail-panel label. Default sort: descending by Score. Per-row Weight % (= 100 × score / sum) shown in `<tr>` tooltip. Mobile-graceful CSS: sticky Ticker + Name columns, horizontal scroll, full-screen detail drawer at ≤640px.

### Changed

- **`fear-greed.yaml` rewritten** to use the verified REST Git Data API commit pattern via `actions/github-script@v9`, targeting the `data` branch. Restores the cron that broke on 2026-05-11 when the `required_signatures` ruleset was activated and rejected `stefanzweifel/git-auto-commit-action@v5`'s unsigned pushes.
- **All workflow actions pinned to full-length commit SHAs** per the repo's new "Require actions to be pinned to a full-length commit SHA" rule. Migrated `validate.yaml`, `sbom.yaml`, `bump-my-version.yaml`, `links-fail-fast.yml`, `codeql.yaml`.
- Defer the v0.6.0 RS hedging epic per [ADR-0003](docs/decisions/0003-defer-rs-hedging-epic.md). Parent issue #4 and sub-issues #8 / #9 / #10 stay open with the `deferred` label; #55 (RS alternatives survey) closes as resolved by the ADR. v0.6.0 milestone repurposed to the demo dashboard above. Behavioral price analytics (pandas, time-series, regime classification) fits a sibling repo rather than this CLI.
- **Composite-score inputs** extended to include price-history-derived terms ([ADR-0004](docs/decisions/0004-price-history-composite-input.md)), amending ADR-0002's point-in-time-only scope. `fetch_universe_fundamentals` now makes one batched `yf.download` per `make run` for the whole universe.
- **`screener_score` requires ≥ 5 of 9 inputs** to return a non-`None` value (`_SCREENER_MIN_TERMS` constant in `src/composite_scores.py`). Informationally-thin tickers — mostly FX / futures / crypto / very sparse ADRs — show "—" in the Score column instead of a misleading partial score. Per-row dashboard tooltip gains the input count (`N / 9 inputs`) alongside the existing Weight % and raw Score.

### Fixed

- **Detail-panel off-by-one** — the `dl()` helper in `docs/demo/app.js` emitted a stray `<dd>` for section-header rows, shifting every following label/value pair right by one cell. The Composite Scores block now lines up correctly.

- **Dashboard UX polish**: Score-column heatmap (red→yellow→green gradient via HSL, higher = greener), fuzzy filter input over Ticker / Name / Sector with typo tolerance (Fuse.js 7.0.0, Apache-2.0, vendored at `docs/demo/vendor/`), sticky `<thead>` so column headers stay visible on vertical scroll. No telemetry — Fuse.js bundle audited and is pure client-side string matching.

### Removed

- Four trivial `defaults_to_none` tests in `tests/test_fundamentals.py` (`test_snapshot_{roi,rd_to_revenue,sortino_ratio,beta}_defaults_to_none*`). All four asserted that a `float | None = None` field defaults to `None` — which is what the type annotation literally says. Regression coverage for "field stays optional" is provided by `test_snapshot_handles_sparse_info` (the GC=F fixture constructs successfully without any of these fields).

## [0.5.1] - 2026-05-11

### Added

- `llms.txt` at the repository root — spec-compliant index per
  [llmstxt.org](https://llmstxt.org/) pointing LLM consumers at the
  authoritative README / AGENTS / architecture / ADR / source files.
  Hand-curated rather than template-generated (KISS); update inline
  when the documentation hierarchy moves.
- `.github/workflows/sbom.yaml` — Software Bill of Materials generation
  via [`qte77/gha-sbom-action@v0.1.1`](https://github.com/qte77/gha-sbom-action).
  Runs on push to `pyproject.toml` / `uv.lock`, weekly Sunday cron,
  and manual dispatch; opens an auto-PR with the SPDX SBOM and a
  markdown summary under `docs/SBOM/` whenever the dependency graph
  changes.

### Changed

- **Project renamed**: `scrape-stock-kpi` → `analyze-stock-kpi`. Reflects
  the post-Traderfox reality — the codebase no longer scrapes anything
  (yfinance is a library, CNN F&G is a documented JSON endpoint). The
  GitHub repository was renamed in the same change; GitHub auto-redirects
  the old URLs. `importlib.metadata.version("analyze-stock-kpi")` reads
  from `[project].name` in `pyproject.toml`.

### Fixed

- `FundamentalsSnapshot.dividend_yield` is now normalized at the fetch
  boundary via a new `_normalize_yfinance_info` helper called from
  `fetch_fundamentals`. Current yfinance ships `info["dividendYield"]`
  as a percentage (e.g. `0.37` for AAPL's 0.37 % yield); the helper
  divides by 100 so downstream consumers (rich table, JSON output,
  `composite_scores._YIELD_HI` bound, `_format_percent`) see one
  consistent fractional convention (#43).

## [0.5.0] - 2026-05-10

Adds composite proxy scores derived from each `FundamentalsSnapshot`.
Six 0-100 proxies — Quality, Dividend, Growth, Big Call, AAQS, HGI —
with simplified formulas using only point-in-time inputs plus
`info["beta"]`. Multi-year trend formulas (Piotroski, CAGR, FCF
coverage) are deliberately deferred per
[`docs/decisions/0002-simplified-composites.md`](docs/decisions/0002-simplified-composites.md).

### Added

- `src/composite_scores.py` — `CompositeScores(BaseModel)` plus
  `quality` / `dividend` / `growth` / `big_call` / `aaqs` / `hgi`
  score functions and a `compute_scores(snap)` entry point. Each
  score is a `float | None` in `[0, 100]`; `None` propagates from
  missing inputs except `big_call`, which reweights proportionally
  over its non-`None` Q/D/G components (#18).
- `tests/test_composite_scores.py` — 29 unit tests with hand-computed
  expectations covering saturation, midpoints, sparse-snapshot,
  negative-D/E guard, and `beta=None` paths (#18).
- `docs/decisions/0002-simplified-composites.md` — ADR documenting
  simplified formulas as the deliberate v0.5.0 design (not a
  placeholder); amends [ADR-0000](docs/decisions/0000-remove-traderfox.md)
  and [ADR-0001](docs/decisions/0001-defer-financetoolkit.md) (#18).
- `FundamentalsSnapshot.beta` — captures yfinance `info["beta"]`;
  required input for the AAQS proxy (#18).
- `FundamentalsSnapshot.composite_scores` — optional nested
  `CompositeScores`; attached post-fetch via `model_copy(update=…)`
  so JSON output schema stays additive (#18).
- `CliArgs.show_scores` (`--show-scores` flag, off by default) —
  appends Quality / Div / Growth columns to the rich summary table.
  Composites are always computed and persisted regardless of the
  flag (#18).

### Changed

- README adds a **Composite proxy scores** section + TOC entry under
  Fundamentals (#18).
- `docs/architecture.md` — composite_scores no longer marked as "not
  yet implemented"; data-flow diagram bumped to v0.5.0; financetoolkit
  reframed as not-used (per ADR-0002) (#18).
- `docs/roadmap.md` — v0.4.0 marked shipped; v0.5.0 framing aligned
  with ADR-0002 simplified composites (#18).
- `docs/UserStory.md` — current milestone updated to v0.5.0 with
  composite scores; corrects stale `results/fear_greed/` path to
  `results/cnn_fg/YYYY.json` (#18).

## [0.4.0] - 2026-05-10

Replaces the Traderfox scraper with a library-based fundamentals +
sentiment stack (yfinance + CNN F&G). See
`docs/decisions/0000-remove-traderfox.md`. Composites deferred to
v0.5.0 per `docs/decisions/0001-defer-financetoolkit.md`.

### Documentation

- README cleanup (#3): drop `[DRAFT]/[WIP]/<0.0.0>` markers, replace
  static version badge with dynamic GitHub-tag badge, fill TOC, add a
  Sentiment section, drop pre-Phase-1 "Other possible packages" + "API"
  sections.
- `src/__version__.py` now reads from package metadata via
  `importlib.metadata.version("analyze-stock-kpi")` — `pyproject.toml` is
  the single source of truth, no more triple-source drift.

### Added

- `src/sentiment.py` — `FearGreedSnapshot(BaseModel)`, `fetch_fear_greed()`,
  `parse_historical()`, and `merge_payload_into_years()` via stdlib
  `urllib.request`. CNN's WAF requires a current desktop-browser UA +
  `Accept` + `Referer: https://edition.cnn.com/` (returns 418 otherwise);
  all three are sent. Each daily entry now also carries a
  `subindicators: dict[str, SubindicatorReading]` map covering CNN's 9
  subindicator blocks (S&P momentum, breadth, VIX, etc.). Today's row
  has the precise 0-100 score per subindicator; historical rows have
  rating + raw value but no per-day score (CNN doesn't ship that). See
  [`docs/cnn-fg-api.md`](docs/cnn-fg-api.md) for the backfillable-vs-
  daily-only breakdown. `python -m src.sentiment` merges the live
  headline + ~1y of historical readings into per-year JSON files at
  `results/cnn_fg/YYYY.json` (sorted by date; today's entry is force-
  overwritten with the live headline so its `previous_*` deltas and
  per-subindicator scores survive intraday CNN updates) (#17).
- `.github/workflows/fear-greed.yaml` — daily cron at 21:30 UTC (~30 min
  after NYSE close, year-round) plus `workflow_dispatch`; commits the
  rewritten year files via `stefanzweifel/git-auto-commit-action@v5`,
  scoped to `results/cnn_fg/[0-9][0-9][0-9][0-9].json` (#17).
- `src/fundamentals.py` — `FundamentalsSnapshot(BaseModel)` plus
  `fetch_fundamentals` / `fetch_price_history` /
  `fetch_universe_fundamentals`. yfinance-backed, ~30 aliased fields,
  sparse snapshots for non-equities (FX/futures/crypto) valid by design
  (#28, closes #16, supersedes #7).
- `src/__main__.py` wires fundamentals end-to-end: fetch every resolved
  ticker, print a rich summary table (equities + ETFs), persist all
  snapshots to `results/fundamentals_<UTC>.json` (#28).
- `src/universe.py` — universe resolver with presets in
  `src/assets/universes/`, CSV/file/inline ticker sources, dedup with
  order preservation (#26, closes #20).
- `src/utils/parse_args.py` — `CliArgs(BaseSettings)` typed CLI args + env
  vars (env prefix `SSK_`, kebab-case CLI flags, `extra="forbid"`); adds
  `period` field reserved for the v0.5.0 composites PR (#26, #28).
- Governance scaffold: `docs/architecture.md`, `docs/UserStory.md`,
  `docs/roadmap.md`, `docs/decisions/0000-remove-traderfox.md` (#24);
  `docs/decisions/0001-defer-financetoolkit.md` documents the v0.4.0
  yfinance-only scope amendment.
- Complexity gates: `complexipy` cognitive ≤15 + `ruff` mccabe ≤10, both
  wired into `make validate` and CI (#24).
- Mandatory markdown + link checks: `lint_md` (in `make validate` and CI),
  `lint_links` (CI workflow `links-fail-fast.yml` runs on push/PR/weekly).
  Adopts the qte77 Agents-eval convention; `.lychee.toml` cribbed from
  sibling `llm-local-text` (#27, #28).
- Dependencies: `pydantic>=2.10`, `pydantic-settings>=2.6` (#26),
  `yfinance>=0.2.40` (#28).

### Changed

- **Renamed top-level package `app/` → `src/`.** All imports become
  `from src.X import ...`; `make run` invokes `python -m src`; the
  daily cron invokes `python -m src.sentiment`; pyright/complexipy/
  coverage targets and pyproject build config all updated accordingly.
  Mechanical: no behavior changes.
- `make run` no longer scrapes via Playwright; runs fundamentals via
  yfinance and writes `results/fundamentals_<UTC>.json` plus a rich
  summary table (#28). A CNN Fear & Greed banner now precedes the table;
  fetch failure logs a warning and continues (#17).
- `results/` is no longer gitignored — cron-committed F&G snapshots live
  under `results/cnn_fg/`. The cron's `file_pattern` is scoped narrowly
  so locally-produced fundamentals files are never accidentally swept
  into a CI commit (#17).
- Default `pytest` excludes `@pytest.mark.network` tests via
  `-m 'not network'` in addopts. Opt in with `pytest -m network`
  (#28).
- `markdownlint` style: ATX headings via `.markdownlint.json` matching
  the qte77 ecosystem convention from sibling `llm-local-text` (#27).
- Python 3.9 → 3.12 (`requires-python = ">=3.12,<3.13"`).

### Removed

- Traderfox provider end-to-end: `app/utils/handle_playwright.py`,
  `app/config/dom.json`, the Playwright dependency, traderfox dispatch
  in `__main__.py` (#25, closes #19).
- Dead config layer left over from the Traderfox era:
  `app/utils/handle_config.py`, `app/utils/handle_files.py`,
  `app/config/defaults.json`, the now-empty `app/config/` directory
  (#28).
- `Pipfile`, `.flake8`, `.cirrus.yml`, `.bumpversion.cfg`, `make.bat`
  — superseded by uv / ruff / GitHub Actions / no-release-yet (YAGNI).

### Fixed

- Runtime orphan `title=` kwarg on Playwright page calls and missing
  `mkdir -p results/` before write (#15).
- File I/O utilities no longer return `Exception` objects from
  `except` blocks; errors propagate naturally so callers see the real
  failure (later removed entirely in #28).
- Latent argument-order bug in `get_values_single_url`: `_get_result`
  was called with `headless` and `timeout` swapped (later removed via
  the Traderfox decommission in #25).
- 22 pre-existing pyright errors cleared; pyright gates `make validate`
  and CI.

### Earlier

Pre-Phase-1 setup work — kept here for traceability.

- Tooling adoption per qte77 ecosystem conventions: `uv` (replaces
  Pipfile), `ruff` (replaces black + flake8 + isort + pyupgrade),
  `pyright` (replaces mypy), `Makefile` with `validate` target,
  `AGENTS.md` + `CLAUDE.md` agent docs, `.claude/settings.json` with
  marketplace plugins, GitHub Actions `validate.yaml` workflow.
- `[tool.uv].exclude-newer` pinned for reproducible dependency
  resolution.
- `MEMORY.md` and bwrap sandbox phantom block in `.gitignore`;
  `.gitmessage` conventional-commit template tracked.
- `tests/` scaffold with smoke test; pytest + coverage config.
