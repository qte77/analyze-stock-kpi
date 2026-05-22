# ADR-0006 — Federal-contractors universe via usaspending.gov + EDGAR

**Status:** Accepted (2026-05-20)

**Relates to:**
[ADR-0005](0005-sentiment-risk-sources.md) (three-tier source framework
— this ADR is a concrete Tier-0 application);
[ADR-0000](0000-remove-traderfox.md) (no HTML scraping — both sources
expose documented JSON endpoints).

## Context

The repo's existing universes (`src/assets/universes/*.txt`) cover
broad equity baskets (e.g., `qte77-watchlist`) and asset-class baskets
(FX, futures, crypto). There is no curated way to construct a universe
of **publicly-traded US federal contractors** ranked by trailing
fiscal-year contract dollars — a natural screening axis for
contract-exposed equities (defense, federal IT services, healthcare
contractors).

Three constraints from earlier ADRs gate any such construction:

- [ADR-0000](0000-remove-traderfox.md) — no HTML scraping; sources must
  expose documented JSON / CSV endpoints.
- [ADR-0005](0005-sentiment-risk-sources.md) — default-on flows must be
  Tier 0 (keyless); any source that requires auth defaults to OFF.
- AGENTS.md — outputs persisted to the public `data` branch must come
  from sources whose ToS permits redistribution.

A sam.gov-driven build was the original direction but was rejected on
cost-benefit: sam.gov requires an API key (Tier 1), a ~10-business-day
entity-registration wait to unlock 1000 req/day, and 90-day key
rotation — for fields a ticker preset doesn't need (DBA names,
business-type designations, parent-UEI hierarchy).

## Decision

Adopt a three-step **Tier-0 (keyless)** pipeline:

### 1. Rank contractors via usaspending.gov

Source of truth for federal-contract obligations is
<https://api.usaspending.gov/>. The DATA Act
(`31 U.S.C. § 6101`) mandates redistribution-permitted public data;
the API has no key requirement and no published rate limit.

Endpoint:

```text
POST https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/
```

Request body filters:

| Field | Value | Purpose |
|---|---|---|
| `filters.award_type_codes` | `["A","B","C","D"]` | Contracts only (excludes grants, loans, direct payments) |
| `filters.time_period` | `[{"start_date": "<FY-start>", "end_date": "<FY-end>"}]` | One US fiscal year (Oct 1 → Sep 30) |
| `limit` | `100` | Top-100 in one page |
| `page` | `1` | Single page |

Response per recipient: `{name, code (= UEI), amount}` where `amount`
is total obligated dollars in the window. The endpoint is
pre-aggregated and ranked by `amount` descending.

### 2. Bridge legal name → ticker via SEC EDGAR

Source: <https://www.sec.gov/files/company_tickers_exchange.json> —
keyless, fully public, refreshed continuously. Maps
`{cik, ticker, title, exchange}` for every SEC-registered equity.

Bridging strategy (per `name-to-ticker` research thread):

- **Seed list always included.** The DoD's annual Top-25 Publicly
  Traded Contractors list is the bootstrap — a curated reference of
  ~25 verified `{legal_name → ticker}` pairs (LMT, RTX, NOC, GD, BA,
  LHX, HII, LDOS, BAH, SAIC, CACI, KBR, TXT, OSK, GE, HON, FLR, J,
  DELL, ACN, PLTR, MSFT, AMZN, BAESY, MMS, ICFI). Every member of
  this seed is in the output regardless of usaspending fixture
  presence.
- **Auto-match for new entries.** For each usaspending recipient not
  in the seed, propose a ticker via fuzzy match
  (`difflib.SequenceMatcher`, threshold ~0.85) of the legal name
  against EDGAR `title`. Avoid `rapidfuzz` as a new dep (stdlib
  suffices for ~100 records).
- **Subsidiary rollup happens at the ticker layer**, not the
  recipient layer. Both `LOCKHEED MARTIN CORPORATION` and
  `LOCKHEED MARTIN AERONAUTICS CO` resolve to `LMT` via EDGAR and
  collapse during ticker-level dedupe. No per-recipient parent-UEI
  lookups (would add ~100 extra HTTP calls for marginal value).
- **Confidence flag in the audit JSON.** Each candidate ticker is
  tagged with the SequenceMatcher score so low-confidence matches
  can be reviewed manually.

### 3. Verify each ticker resolves on Yahoo Finance

The CLI's runtime data source is yfinance. Every candidate ticker
must pass `yf.Ticker(t).fast_info` non-empty before being committed
to the preset. Failures (delisted, foreign-only listing without ADR,
recent symbol churn) drop from the preset and are flagged in the
audit JSON.

### Operational mechanics

- **Preset file:** `src/assets/universes/federal-contractors.txt` —
  bare ticker list, one per line, sorted ASCII-ascending for
  deterministic diffs. Overwrite-on-rebuild.
- **Audit JSON:** `results/federal-contractors/<YYYY-MM-DD>.json` on
  the `data` branch — full trail of (recipient name, UEI, obligated
  $, candidate ticker, confidence score, smoke-test status). Useful
  for retrospective review of why a ticker entered or left the
  preset.
- **Refresh workflow:** `.github/workflows/federal-contractors-refresh.yaml`
  — monthly cron (`0 8 1 * *`), `workflow_dispatch` for ad-hoc.
  Audit JSON commits to the `data` branch via the verified REST
  Git Data API pattern (Blob → Tree → Commit → Ref via
  `actions/github-script`). The preset file change targets `main`
  via a bot-opened PR titled
  `chore(universe): refresh federal-contractors preset <YYYY-MM>` —
  the bot **never** direct-pushes to `main` (blocked by
  `required_signatures` + `pull_request` rules).

## Consequences

- **No new runtime dependencies.** Both endpoints are stdlib-fetchable
  (`urllib`); `difflib.SequenceMatcher` is stdlib; pydantic and
  yfinance are already pinned in `pyproject.toml`.
- **New modules and files** introduced incrementally across separate
  PRs under strict TDD per the v0.6.0+ plan: a `src/sec/` package
  containing `cik_map.py` (CIK ↔ ticker resolver — UC3 in the plan's
  EDGAR use-case ranking) and `submissions.py` (last-filed flags),
  plus `scripts/build_federal_contractors.py` (the builder), the new
  refresh workflow YAML, and the seeded preset file.
- **Expected universe size.** Top-100 usaspending recipients →
  ~25-40 Yahoo-resolvable tickers after EDGAR + yfinance filtering
  (the DoD list confirms roughly 30-35 % of top-100 federal
  contractors are publicly traded; balance is private LLCs, large
  defense subsidiaries without independent listing, foreign primes
  without US ADRs, healthcare distributors, etc.).
- **Refresh churn is expected low.** At top-100 scale the ranking is
  stable month-over-month; the monthly cron should usually produce
  empty preset diffs. The audit JSON still grows monotonically as a
  historical trail.
- **sam.gov is documented as a future Tier-1 enrichment** in
  ADR-0005 but is not in this pipeline's critical path. If a future
  consumer needs DBA / business-type / parent-UEI fields, sam.gov
  enrichment can be bolted on under a separate workflow keyed by
  `SAM_API_KEY`.

## Out of scope

- **sam.gov enrichment.** Documented as Tier-1 future work; not
  built here.
- **Sector-narrowed preset variants** (`defense-only`,
  `federal-it-only`). Possible follow-ups — same pipeline with
  `filters.naics_codes` (e.g., `["33"]` for manufacturing /
  defense). Not in the first cut.
- **Sub-award data.** usaspending exposes sub-awards via a
  separate endpoint with different ranking dynamics. Out of scope
  unless a concrete consumer asks for it.
- **Trailing-12-month vs fiscal-year ranking.** The first cut uses
  the last completed FY (Oct 1 → Sep 30). Trailing-12-month is
  trivially supported via `filters.time_period` but adds no value
  for a monthly-refreshed preset.

## Amendment (2026-05-21) — Library-first architecture

Original ADR scoped the usaspending logic to
`scripts/build_federal_contractors.py` (Scope 2 in
[ADR-0007](0007-package-vs-infrastructure-boundary.md)'s
terminology). After ADR-0007 formalized the package /
repo-infrastructure / demo boundary, the work was reorganized so
that the canonical implementation lives **inside the package**:

- `src/usaspending.py` — `RecipientRecord(BaseModel)` and
  `fetch_top_contractors(...)` library API.
- `src/federal_contractors.py` — `AuditRow(BaseModel)`,
  `CURATED_TICKERS` (DoD Top-25 seed), and the
  `build_universe(...) -> tuple[list[str], list[AuditRow]]`
  orchestrator.
- `python -m src --refresh-universe federal-contractors` exposes
  the orchestrator via the CLI; writes the preset + audit to the
  XDG cache directory by default (`--output` / `--audit-output`
  override).

`scripts/build_federal_contractors.py` is retained as a **thin
wrapper** that calls `build_universe(...)` and persists the
outputs to repo-specific paths
(`src/assets/universes/federal-contractors.txt` in editable mode,
`results/federal-contractors/<date>.json` for the `data` branch).
It exists so the refresh workflow has a stable invocation point;
downstream consumers of the wheel call the library API directly.

`src/universe.py` is extended to check
`~/.cache/analyze-stock-kpi/universes/<name>.txt` before falling
back to the bundled preset. Downstream users can refresh and have
their cache override the wheel's bundled list without rewriting
the package.

The weekly refresh workflow (`federal-contractors-refresh.yaml`)
opens a preset-update PR against `main` **only when the diff is
non-empty** (top-100 federal-contractor ranking is stable
week-over-week; empty diffs would spam the PR list).

## Amendment (2026-05-22) — Library-first architecture

Original ADR scoped usaspending logic to
`scripts/build_federal_contractors.py`. After ADR-0007 formalised the
package-vs-infrastructure boundary, the work was reorganised so that
downstream consumers of the wheel get a first-class library API:

- `src.data_sources.usaspending.fetch_top_contractors(...)` —
  POST API client (no orchestration).
- `src.orchestrators.federal_contractors.build_universe(...) ->
  tuple[list[str], list[AuditRow]]` — end-to-end orchestrator.
- `src.utils.parse_args.CliArgs.refresh_universe` plus a branch in
  `src.__main__.main()` expose the orchestrator as `python -m src
  --refresh-universe federal-contractors`.

`scripts/build_federal_contractors.py` becomes a thin wrapper that
the GHA refresh workflow invokes; the heavy lifting lives in the
package.

## Amendment (2026-05-22 later) — SEC anti-bot UA shape

The first live run of `federal-contractors-refresh`
([Actions run #26300253536](https://github.com/qte77/analyze-stock-kpi/actions/runs/26300253536))
returned `HTTP 403 Forbidden` from
`https://www.sec.gov/files/company_tickers_exchange.json`. The original
implementation rotated browser-shape `User-Agent` strings via
`src/utils/http_ua.pick_user_agent`; SEC's anti-bot now rejects that
shape outright.

**Findings from existing Python SEC clients** (consulted because SEC's
own access-policy page also returns 403 to crawlers, blocking direct
re-verification):

- `sec-edgar/sec-edgar` (README): users supply
  `user_agent="Your Name (your.name@example.com)"` when constructing a
  filings object. The library has no default and no built-in browser
  pool.
- `dgunning/edgartools` (`edgar/httprequests.py`): sets only
  `headers["User-Agent"] = identity` where `identity` is resolved from
  one of (caller param, `identity_callable()`, `EDGAR_IDENTITY` env).
  No `Referer`, no explicit `Accept` — only the identity-shape UA.
  Requests without `identity` raise before any HTTP call.

**Convergent pattern.** Both libraries (i) require an operator-supplied
identifier, (ii) send neither browser UA nor a repo-identifying string,
(iii) treat the UA as the operator's responsibility, never a library
default.

**Decision.** Adopt the same pattern in this repo:

- `AppSettings.sec_user_agent: str | None = None` — no default in
  source (no PII, no repo fingerprint).
- `SSK_SEC_USER_AGENT` env var supplies the operator's contact at
  runtime; in CI via a repository secret (`SEC_USER_AGENT`) injected
  into `federal-contractors-refresh.yaml` env.
- `src/data_sources/sec/{cik_map._fetch_json, submissions.fetch_last_filed}`
  raise `RuntimeError` with a clear message if `sec_user_agent` is
  unset — fail-loud, no silent browser-UA fallback.
- `Referer` and `Accept` headers retained at their current values;
  empirical evidence (edgartools omits both) suggests they are not
  load-bearing, but removing them is YAGNI for this fix.

**Verification limit.** SEC's published policy at
`https://www.sec.gov/os/accessing-edgar-data` is itself 403-blocked to
automated fetchers, so the exact current minimum accepted UA string
cannot be confirmed against the source-of-truth document. The
conclusion above is the convergent practice of the two most-maintained
Python SEC clients as of 2026-05-22, plus the empirical observation
that this workflow's first ever attempt with a browser UA was rejected.

## References

- usaspending.gov API: <https://api.usaspending.gov/>
- usaspending spending_by_category contract:
  <https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_category.md>
- DATA Act (31 U.S.C. § 6101) — federal-data redistribution mandate.
- SEC EDGAR Developer Resources:
  <https://www.sec.gov/about/developer-resources>
- SEC EDGAR `company_tickers_exchange.json`:
  <https://www.sec.gov/files/company_tickers_exchange.json>
- DoD Top-25 Publicly Traded Contractors — annual SOCO publication.
- yfinance v1.3.0 `Lookup` / `Search` (used at bootstrap time only):
  <https://ranaroussi.github.io/yfinance/reference/yfinance.search.html>
