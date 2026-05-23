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

## [Unreleased]

### Changed

- **Rename ruff rule code `TCH` → `TC` in `pyproject.toml`.** `TCH` is the deprecated alias; `TC` is the modern code for flake8-type-checking. Functionally identical under ruff 0.15; future-proof against ruff 1.0 dropping the alias. Aligns with the shared `py-harden-ruff.md` recipe doc.

### Security

- **Bump `idna` 3.13 → 3.16 (CVE-2026-45409 ReDoS in `idna.encode()`).** `[tool.uv].exclude-newer` rolled forward 2026-05-09 → 2026-05-23 so the patched version is reachable; no other transitive bumps. Practical exposure was nil (we never pass external input through `idna.encode()`), but the patched version is trivial to ship.

### Fixed

- **Demo row click no longer silently opens Yahoo Finance via `window.open`.** Simple-mode rows are now non-actionable (detail panel stays `class="detail-only"` and hidden); detailed-mode rows open the side panel as before. External-link visits go through the panel's visible `<a href>` anchors only — no invisible JS click referrals.
- **`_persist_snapshots` JSON-serializes `date` enrichment fields** — `s.model_dump(mode="json")` so `sec_last_*_date` (now populated since PR #127 unblocked SEC) become ISO strings instead of crashing `json.dumps`. Regression for [run #26303499996](https://github.com/qte77/analyze-stock-kpi/actions/runs/26303499996).
- **SEC EDGAR `User-Agent` now identity-shape** — default `"opensource-research-client contact@example.com"` (RFC 2606 placeholder, no PII / repo fingerprint); operator overrides via `SSK_SEC_USER_AGENT` env or CI repo variable `vars.SEC_USER_AGENT` (optional — `AppSettings(env_ignore_empty=True)` ignores empty-string env so unset `vars` falls through to the in-source default). See [ADR-0006 amendment 2026-05-22 (later)](docs/decisions/0006-federal-contractors-universe.md#amendment-2026-05-22-later--sec-anti-bot-ua-shape).
- **CodeFactor `B108` quiets in `tests/test_config.py`** — `# nosec B108` matching existing pattern on lines 75/80.

### Added

- **Multi-universe overlay + per-ticker time-series tab (#137).** Detailed-mode-only. Picker still selects the primary universe; in detailed mode a second selection adds the universe to the overlay rather than replacing it. Each active overlay universe shows as a `#universe-chips` chip with a `×` to remove. URL `?universe=primary,extra1,extra2` round-trips. A new `Universe` column appears in the table when ≥2 universes are active (CSS toggled via `body.overlay-active`). Detail panel gains an `Overview` / `Time series` tab pair; the time-series tab renders a Chart.js multi-line of Screener / Quality / Growth / Sortino across `manifest.dates` for the picked ticker. Pre-#136 backfill the series is short (~5 points) and shows a hint chip; post-#136 the same code consumes the 17-month grid with no migration. New pure modules `docs/demo/lib/overlay.js` (`mergeUniverseSnapshots`) + `docs/demo/lib/timeseries.js` (`buildTimeSeries`); 12 non-trivial Vitest cases.
- **Theme toggle (system / light / dark).** New 3-button segmented control in the header overrides the prior `prefers-color-scheme`-only dark mode shipped with #134. Default stays "system" (follows OS). Choice persists via `?theme=` URL query + `localStorage`. CSS refactored: dark palette driven by custom-property overrides on `body.theme-dark` (forced) OR `body.theme-system` under the media query — one variable, three triggers. New `docs/demo/lib/theme.js` with `resolveTheme` + `isThemeMode` (precedence: URL > localStorage > "system"); 8 Vitest cases.
- **Demo v2 simple/detailed toggle dashboard (#134).** New `<button id="view-toggle">` flips `body.view-simple` / `body.view-detailed`; 8 of 13 KPI columns + detail aside + CSV button hide in simple mode. Adds: A1 conditional cell coloring, A2 URL state for view/sort/filter/date, A3 CSV export, A4 external links (Yahoo / SEC EDGAR / Wikipedia), A5 empty/loading states, B1 composite radar, B3 sector donut, D1 `/` focuses filter, D2 dark-mode via `prefers-color-scheme`, D3 mobile auto-simple <768px. Pure-JS units extracted into `docs/demo/lib/{audit,coloring,csv,sector,state}.js` with Vitest harness (closes #131). ESLint/Prettier deferred per #135.
- **Dashboard universe-picker + Federal Contracts detail section (#130).** `docs/demo/index.html` gains a `<select id="universe-picker">` populated from the new `docs/demo/universes.json` manifest (8 bundled presets); `?universe=<id>` query param persists across reloads via `history.replaceState`. `docs/demo/app.js` adds `loadAudit(universe, date)` (silent-404; only fetches for `federal-contractors`) and appends a "Federal Contracts" section to `showDetail(row)` when the row's symbol joins to an `AuditRow.final_ticker`. `.github/workflows/demo-snapshot.yaml` now fans out across all 8 universes via a matrix (`fail-fast: false`); the verified-commit step retries on 422 `Reference cannot be updated` so concurrent matrix legs writing to the `data` branch don't lose snapshots to ref-update races. `workflow_dispatch` accepts an optional `universe` `type: choice` input that collapses to a single leg for ad-hoc dispatch. Vitest unit harness deferred to #131.
- **Federal-contractors universe orchestrator (Item 3b)** — `src/orchestrators/federal_contractors.{build_universe,AuditRow}` chains usaspending → EDGAR → yfinance; CLI `--refresh-universe federal-contractors`; bundled preset (`src/assets/universes/federal-contractors.txt`, 26 entries) + weekly refresh workflow + ADR-0006 amendment.
- **`src/usaspending.py` — POST top-contractors API client (Item 3a).** Wraps `api.usaspending.gov/api/v2/search/spending_by_category/recipient/` per the verified upstream contract. Public surface: frozen `RecipientRecord` pydantic model (`name`, `recipient_id`, `code` (DUNS), `uei`, `amount`, `total_outlays`, `rank`) plus `fetch_top_contractors(fy_start, fy_end, *, limit, naics_codes, award_type_codes)`. Default NAICS filter is `None` (broad "top contractors by obligated $" across sectors); `naics_codes=[...]` wraps into the contract's `{"require": [...]}` dict shape. Drops the `"MULTIPLE RECIPIENTS"` aggregate row (`recipient_id is None`) before ranking; assigns rank from post-filter list position. 100% test coverage; cycle 4 includes `@pytest.mark.network` live FY2025 round-trip. `settings.usaspending_url` + `settings.usaspending_timeout_sec = 30` added to `AppSettings`. `settings.federal_contractors_dir = Path("results/federal_contractors")` reserved for the upcoming Item 3b orchestrator. Strict R/G/R cycles throughout (one commit per phase, one push per cycle).
- **`src/config.py` — centralised runtime config via `AppSettings(BaseSettings)`.** Every URL endpoint, filesystem path, HTTP-shape constant (`Accept`, `Referer`, CNN User-Agent), and request timeout that previously lived as a module-level constant across `src/sec/`, `src/sentiment.py`, and `src/__main__.py` now resides in a single `pydantic-settings` model. The module-level `settings` singleton is what downstream callers import. Env-var override is free via the `SSK_` prefix (e.g. `SSK_REQUEST_TIMEOUT_SEC=30`). Defaults reproduce the pre-refactor literals exactly; behaviour unchanged. Domain / algorithm constants (`_TRADING_DAYS`, `_STALE_10Q_DAYS`, `_TABLE_QUOTE_TYPES`) intentionally stay co-located — they're not user-overridable runtime config.
- **`src/sec/submissions.py` — EDGAR last-filed dates per US form type (10-K / 10-Q / 8-K).** Implements ADR-0006 UC1: per-ticker enrichment using EDGAR's `data.sec.gov/submissions/CIK<10>.json` endpoint. New `LastFiledSnapshot` (frozen pydantic) carries the three optional date fields; `enrich_snapshot_sec(symbol)` resolves the CIK via `src.sec.cik_map`, fetches submissions, and returns a dict ready for `FundamentalsSnapshot.model_copy(update=...)`. Non-SEC-registered Yahoo symbols (FX, crypto, futures) bypass the EDGAR call. `FundamentalsSnapshot` gains three optional enrichment fields (`sec_last_10k_date`, `sec_last_10q_date`, `sec_last_8k_date`) attached post-fetch in `src/__main__.py`. The Rich summary table gains a `Days 10-Q` column that renders as `"{n}d"`, wrapping in `[red]…[/red]` markup when the most-recent 10-Q is older than 150 days. Strict TDD throughout the build.
- **ADR-0007 — package vs repo-infrastructure boundary.** Formalizes the three concentric scopes (package `src/` + `README.md` → ships in wheel; repo infrastructure `scripts/` + `.github/` + lint configs → CI-only; demo + dev docs `docs/demo/` + `docs/*.md` + `tests/` → reference / showcase) plus a one-way direction rule (Scope 2/3 may import Scope 1; Scope 1 must not reference Scope 2/3 paths, and the `data` branch is consumed only by the demo) and a path-write rule (`src/` writes only to user-controlled paths, never to its own install location). Drives the ADR-0006 amendment that moves usaspending logic into the package.
- **`src/sec/cik_map.py` — CIK ↔ ticker resolver via EDGAR's `company_tickers_exchange.json`.** Foundation layer for SEC EDGAR integration (ADR-0006 UC3). Frozen pydantic `CikRecord` model + `resolve_cik(ticker)` returning a 10-digit zero-padded CIK string (or `None` for non-SEC-registered Yahoo symbols like FX, crypto, futures). Module-level cache fetches the EDGAR JSON once per process. Keyless; sends browser-shape `User-Agent` from `src/utils/http_ua.py`. Strict TDD throughout the build.
- **ADR-0005 — three-tier sentiment + risk source framework.** Documents the auth-tier classification (Tier 0 keyless / Tier 1 free-key opt-in / Tier 2 paid opt-in) that gates default-on behavior, env-var requirements, and `data`-branch persistence eligibility for every current and future sentiment / risk source. Tier 0 (CNN F&G, Yahoo-Finance-proxied volatility) stays default-on; Tier 1 (Nasdaq Data Link — NAAIM, AAII; sam.gov future enrichment for the federal-contractors universe) requires env-var opt-in; Tier 2 (Bloomberg `blpapi`, GS `gs-quant`, State Street institutional) is runtime-only and never persisted publicly. Closes #22.
- **ADR-0006 — federal-contractors universe via usaspending.gov + EDGAR.** Scopes a Tier-0 (keyless) pipeline that ranks the top-100 US federal contractors by trailing-fiscal-year contract obligations (`usaspending.gov spending_by_category/recipient`), bridges legal names to Yahoo-resolvable tickers via SEC EDGAR `company_tickers_exchange.json`, and gates final entries through `yfinance.Ticker(...).fast_info`. Subsidiaries roll up to the parent ticker; a curated DoD Top-25 publicly-traded seed list is always included. Output preset `src/assets/universes/federal-contractors.txt` is refreshed weekly via a new workflow that commits an audit JSON to the `data` branch and opens a PR with the preset diff (suppressed when empty). sam.gov is documented as future Tier-1 enrichment; not in the critical path. **Amended 2026-05-21 (Library-first architecture):** core logic relocated into `src/usaspending.py` + `src/federal_contractors.py` per ADR-0007; the script becomes a thin wrapper.

### Changed

- **Docs restructure (Item 6b)** — single-source-of-truth + concision. AGENTS.md "Active modules" list removed (docs/architecture.md owns it). README.md "Sample output" JSON dump trimmed (links to source). docs/architecture.md `Modules` tree refreshed for the three-tier layout; "Planned modules" section dropped (all shipped). roadmap.md marks federal-contractors + gh-pages + static dashboard as done. Stale `results/fundamentals_<UTC>.json` references repaired across 5 docs.
- **`src/` restructured into three-tier sub-packages** — `src/domain/`, `src/data_sources/` (incl. `sec/`), `src/orchestrators/`. Pure rename + import-path updates; no behaviour change.
- **CNN F&G UA centralised on `src.utils.http_ua.STABLE_USER_AGENT`** — `AppSettings.cnn_fg_user_agent` removed (it duplicated `USER_AGENTS[0]`). SEC keeps random rotation via `pick_user_agent()`; CNN pins to `STABLE_USER_AGENT` to avoid WAF profiling.
- **`USER_AGENTS` pool moved into `AppSettings.user_agents`** — `src/utils/http_ua.py` now re-exports `USER_AGENTS` + `STABLE_USER_AGENT` from settings; single source of truth, env-overridable via `SSK_USER_AGENTS`.
- **`results/` source-aligned**: top-level `fundamentals_<UTC>.json` writes moved into `results/fundamentals/<UTC>.json`. New `settings.fundamentals_dir = Path("results/fundamentals")`. `demo-snapshot.yaml` `mv` updated.
- **`docs/data-sources.md` — Redistribution guardrails section (verified 2026-05-21).** Independent ToS / license audit per source for committing derived outputs to the public `data` branch. Verdicts: usaspending.gov **CLEAR** (CC0 + DATA Act), SEC EDGAR **CLEAR** (17 USC § 105 federal-works public-domain), yfinance raw payloads **CAUTION** (Yahoo ToS §2.4(i)/§2.8 prohibits redistribution; derived ticker list + resolution boolean **CLEAR**), `fedspendingtransparency/usaspending-api` API contract files **CLEAR** (CC0; verbatim fixture copy OK), CNN F&G numeric values **LOW RISK** (revised after deeper precedent research: *Feist* rules numeric facts uncopyrightable; *Van Buren* / *hiQ* rule User-Agent spoofing is not CFAA "gate circumvention" on publicly-accessible endpoints; zero CNN takedowns on record against any of ≥10 public F&G redistributors on PyPI/Kaggle/GitHub). Standing rule that lands with this: `AuditRow` in the upcoming `src/federal_contractors.py` MUST NOT carry any `fast_info` / `info` fields — only the ticker symbol + boolean.
- **`docs/data-sources.md` usaspending.gov section re-verified against the upstream API contract (2026-05-21).** Five corrections sourced from `fedspendingtransparency/usaspending-api/.../recipient.md`: (a) per-result `code` field is **DUNS** (9-digit legacy), not UEI; `uei` is a separate field that is frequently `null` even on legitimate contractor rows. (b) The internal hash field is `recipient_id`, not `id`. (c) `total_outlays` is part of the response (nullable). (d) The first result is often a `"MULTIPLE RECIPIENTS"` aggregate row with all three identifiers null — must be filtered before ranking. (e) `filters.naics_codes` is a dict (`{"require": [...], "exclude": [...]}`), not a list. Adds a "Why POST instead of GET" note documenting the search-API design convention. Pre-implementation correction; no source code changes.
- **Boundary failure-policy table in `docs/architecture.md`.** Single source of truth for every I/O boundary (network / filesystem / parse / external-library) and its failure policy — one of `fail-loud`, `wrap-degrade`, or `wrap-continue`. Future PRs touching I/O update the row; future reviewers consult the row before approving silent error handling.
- **`src/sec/cik_map.py::_fetch_json` falls back to cache on network failure.** New `except urllib.error.URLError` arm: when a cache file exists, a logged WARNING is emitted and the cached body is returned (wrap-degrade); without a cache the error propagates as before (fail-loud cold start). Concrete impact — a transient SEC outage no longer kills the whole `python -m src` run.
- **`src/sec/submissions.py::enrich_snapshot_sec` wraps `fetch_last_filed` failures.** `URLError` (parent class of `HTTPError`) is caught, logged as a warning, and degraded to `{}` — exactly the same shape as the no-CIK bypass. One ticker's SEC fetch failure now leaves enrichment empty for that ticker only; the universe run continues.
- **ruff `TRY` rule family added.** `[tool.ruff.lint].select` adds `TRY` (tryceratops). `TRY003` (long messages outside exception classes) is globally ignored — defensive one-off raises with informative messages are fine without custom exception classes. The other TRY rules (`TRY002` no vanilla `Exception`, `TRY200`/`TRY201` `raise ... from` chains, `TRY300` `else` for happy path, `TRY301` no `raise` inside `try` when re-raising after logging) all pass clean on the existing codebase.
- **EDGAR ticker registry now disk-cached with HTTP conditional GET.** `src/sec/cik_map.py::_fetch_json` persists `company_tickers_exchange.json` to `results/edgar/` (configurable via `settings.edgar_cache_dir` / `SSK_EDGAR_CACHE_DIR=...`) and sends `If-Modified-Since` (cache file mtime → HTTP-date) on every subsequent call. On `304 Not Modified` the cached body is reused; on `200 OK` the cache is overwritten and the file mtime is re-stamped to the server's `Last-Modified` value. Steady-state network cost drops from ~13 MB per `python -m src` run to ~200 B (one 304 response). Cache directory auto-creates; missing `Last-Modified` headers tolerated; no behavior change for the in-process `_records_cache`. `results/edgar/` gitignored. Strict TDD: 7 R/G cycles + 1 `@pytest.mark.network` live-EDGAR roundtrip.
- **ruff lint rule set widened.** `[tool.ruff.lint].select` adds `B` (flake8-bugbear), `SIM` (flake8-simplify), `RUF` (ruff-specific), `PT` (pytest-style), `ANN` (flake8-annotations), `TCH` / `TC` (flake8-type-checking), `PGH` (pygrep-hooks), `D` (pydocstyle, `convention = "google"`) on top of the existing `E`, `F`, `I`, `N`, `W`, `UP`, `C90`, `S` baseline. Each entry carries an inline comment describing the rule family. Per-file ignores extended: `tests/**` adds `D` (no docstring requirement on tests; `S101` already there), `scripts/**` adds `D` + `ANN` (one-off scripts; over-annotating is noise). Two `# noqa: TC001` / `# noqa: TC003` markers stay in `src/fundamentals.py` because pydantic needs runtime access to `CompositeScores` / `date` for model field resolution. Existing code touched only to satisfy the new rules; behaviour unchanged.
- **CodeQL config inlined.** The `paths-ignore` rule (excluding vendored `docs/demo/vendor/**`) now lives in the `Initialize CodeQL` step's `config:` input in `.github/workflows/codeql.yaml`, co-located with the action invocation. The standalone `.github/codeql/codeql-config.yml` is removed. No behavioural change to CodeQL analysis — same paths excluded, same SHA-pinned action versions.

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
