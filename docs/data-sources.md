# External data sources — EDGAR, usaspending.gov, sam.gov, yfinance

Research note consolidating the four external data sources scoped
for the v0.6.0+ SEC foundation + federal-contractors universe work.

- See [ADR-0005](decisions/0005-sentiment-risk-sources.md) for the
  three-tier auth framework.
- See [ADR-0006](decisions/0006-federal-contractors-universe.md) for
  the pipeline that wires the keyless sources together.
- See [ADR-0000](decisions/0000-remove-traderfox.md) for the no-HTML-
  scraping invariant — all sources below expose documented JSON.

**Last refreshed: 2026-05-20.** Endpoints and rate limits drift; treat
specific numbers as accurate-at-that-date and re-verify before relying.

## At a glance

| Source | Tier | Auth | Rate limit | Redistribute? | Used by |
|---|---|---|---|---|---|
| **EDGAR (SEC)** | 0 | none — `User-Agent` header only | ~10 req/sec self-limit | yes (public-domain federal data) | runtime: `src/analyze_stock_kpi/data_sources/sec/` |
| **usaspending.gov** | 0 | none | unpublished, generous | yes (DATA Act § 6101) | build-time: `scripts/build_federal_contractors.py` |
| **whit3rabbit/fear-greed-data** (mirror) | 0 | none | GitHub raw-content (generous) | accept-as-is (no LICENSE upstream; derivative of CNN public endpoint) | backfill: `scripts/backfill_fear_greed_whitrabbit.py` (pinned SHA) |
| **yfinance `^TNX` / `^FVX`** (US Treasury yields) | 0 | none | yfinance (rate-limit risk on bulk runs) | yes — derived percentage-point values; CBOE-derived public indices | daily cron: `src/analyze_stock_kpi/data_sources/yield_curve.py` → `.github/workflows/yield-curve.yaml` |
| **sam.gov Entity Management** | 1 | free key, 90-day rotate | 10/day → 1000/day (entity-reg) | yes — public tier only | deferred — future enrichment, not in critical path |
| **Yahoo Finance search/lookup** | n/a | none (cookie/crumb session) | ~360/hr unofficial | n/a — bridge only | build-time: bootstrap candidate resolution in the universe builder |

## How they fit together

The federal-contractors universe pipeline chains three keyless sources:

```text
usaspending.gov                  EDGAR                          yfinance
─────────────────                ─────                          ────────
spending_by_category/recipient   company_tickers_exchange.json  Ticker(t).fast_info
  (top-100 contractors by FY     (legal name → CIK + ticker     (final smoke-test
   obligated $)                   + exchange)                    that the ticker
   │                              │                              actually resolves)
   │   recipient legal names      │   CIK + canonical ticker     │
   └──────────────────────────────▶───────────────────────────────▶
                                                                  │
                                                                  ▼
                                                  src/analyze_stock_kpi/assets/universes/federal-contractors.txt
                                                  (~25-40 verified public tickers)
                                                  +
                                                  results/federal-contractors/<date>.json
                                                  (audit trail on the data branch)
```

sam.gov sits adjacent as a **future Tier-1 enrichment** layer: if a
later consumer wants DBA names, business-type designations
(SBA/veteran-owned/etc.), or parent-UEI hierarchy, sam.gov supplies
them — but the universe build does NOT require it.

EDGAR has a second role beyond the bridge: runtime per-ticker
last-filed dates (10-K / 10-Q / 8-K) land on every
`FundamentalsSnapshot` via `src/analyze_stock_kpi/data_sources/sec/submissions.py` (planned). Same
authentication, different endpoint.

## Redistribution guardrails (verified 2026-05-21)

Independent ToS / license audit run pre-Item 3 against the canonical
sources (not relying on prior summaries). Verdict per source for
committing **derived outputs** to the public `data` branch under this
repo's MIT licence:

| Source | Verdict | Why | Operational guardrail |
|---|---|---|---|
| usaspending.gov payloads | **CLEAR** | The reference implementation (`fedspendingtransparency/usaspending-api`) is CC0 1.0; DATA Act (31 USC § 6101) mandates public, machine-readable, bulk-downloadable access with no downstream restrictions | None beyond the existing rate-limit / backoff |
| SEC EDGAR data | **CLEAR** | Federal works are public-domain by statute (17 USC § 105) | Browser-shape `User-Agent` header + 9 req/sec self-limit + exponential backoff on 429/503 (already in place) |
| yfinance raw payloads | **CAUTION** | Yahoo's ToS §2.4(i)/§2.8 prohibits automated collection AND redistribution of "the Services" | **Never commit raw `fast_info` / `info` JSON.** Persist only the *resolution boolean* (`yfinance_resolves: bool`) and the public ticker symbol itself |
| yfinance-derived ticker list | **CLEAR** | A list of ticker symbols + a "this resolves" boolean is your pipeline's state, not Yahoo's copyrightable expression (Feist v. Rural Telephone) | Same as above — keep the audit row schema lean |
| `fedspendingtransparency/usaspending-api` API contract files | **CLEAR** | Repo is CC0 1.0; LOCKHEED MARTIN / MULTIPLE RECIPIENTS example JSON is in the public domain | Verbatim copy into test fixtures is permitted; no attribution required, but mention provenance in commit messages |
| CNN Fear & Greed numeric values | **LOW RISK** | (a) Copyright: facts are uncopyrightable per *Feist Publications v. Rural Telephone*, 499 U.S. 340 (1991). The integer 1-100 and label are computed facts, not original expression. (b) CFAA: User-Agent / Referer spoofing is not "gate circumvention" on a publicly-accessible endpoint per *Van Buren v. United States*, 594 U.S. 374 (2021) and *hiQ Labs v. LinkedIn*, 938 F.3d 985 (9th Cir. 2022). (c) ToS: a browsewrap contract claim is theoretically possible but unenforced — zero DMCA / C&D against ≥10 public CNN F&G redistributors on PyPI / Kaggle / GitHub. (d) No US sui-generis database right | Already in place: cache numeric-only history to `data` branch; never store raw HTML; daily cron only; graceful degradation on 418 |

### Standing rules these verdicts impose

- The `AuditRow` schema in `src/federal_contractors.py` must NOT include
  any fields sourced from `yfinance.Ticker(...).fast_info` or `info`
  beyond a boolean "resolved" gate. Market cap, exchange, sector,
  price — all NO. Ticker symbol + boolean = the only Yahoo-derived
  fields that may persist publicly.
- Test fixtures sourced from the CC0 usaspending-api contract docs
  should reference the upstream commit / URL in the commit message or
  fixture header so provenance is auditable.
- If any future data source's ToS is ambiguous, default to **CAUTION**
  — persist derived state only, not raw payloads.

References for the audit:

- [CC0 LICENSE on `fedspendingtransparency/usaspending-api`](https://github.com/fedspendingtransparency/usaspending-api/blob/master/LICENSE)
- [Yahoo Terms of Service (`legal.yahoo.com`)](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
- [17 USC § 105 (federal-work public-domain rule)](https://www.govinfo.gov/content/pkg/USCODE-2022-title17/html/USCODE-2022-title17-chap1-sec105.htm)
- [DATA Act / 31 USC § 6101](https://www.law.cornell.edu/uscode/text/31/6101)
- [*Feist Publications v. Rural Telephone Service*, 499 U.S. 340 (1991)](https://www.law.cornell.edu/supremecourt/text/499/340) — facts not copyrightable
- [*Van Buren v. United States*, 594 U.S. 374 (2021)](https://www.supremecourt.gov/opinions/20pdf/19-783_k53l.pdf) — CFAA "gates-up-or-down" test
- [*hiQ Labs v. LinkedIn*, 938 F.3d 985 (9th Cir. 2022)](https://cdn.ca9.uscourts.gov/datastore/opinions/2022/04/18/17-16783.pdf) — publicly-accessible data is not CFAA-protected by header checks
- [GitHub DMCA archive search](https://github.com/github/dmca) — zero CNN F&G takedowns on record (2026-05-21 audit)

---

## EDGAR (SEC)

### Access model

All `data.sec.gov` and `www.sec.gov/files/` endpoints are **keyless**
and explicitly public-domain. Every automated request must carry:

```text
User-Agent: <App> <contact-email>
```

Without it the API returns HTTP 403. SEC documents a **10 req/sec**
hard ceiling per IP; community practice is to self-limit to 9 req/sec.
No OAuth, no registration, no redistribution restrictions.

The project sends a browser-shape UA from `src/analyze_stock_kpi/utils/http_ua.py` (refreshed
quarterly from <https://useragents.me/>) rather than the
identify-as-the-project format that SEC's docs suggest. Both are
acceptable to SEC's rate-limiter; the browser-shape blends the egress
profile with regular visitor traffic, matching the existing
`src/sentiment.py` pattern for CNN.

### Endpoints we use (or plan to)

| Endpoint | Returns | Project use |
|---|---|---|
| `https://www.sec.gov/files/company_tickers_exchange.json` | All SEC-registered equities: `{cik, name, ticker, exchange}` (~10k entries, ~1 MB) | **CIK ↔ ticker bridge** (`src/sec/cik_map.py`, shipped Item 1) |
| `https://data.sec.gov/submissions/CIK<10-digit>.json` | Filing history per company: parallel `form[]` + `filingDate[]` arrays | **Last-filed dates** (`src/sec/submissions.py`, planned Item 2) |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK<10>.json` | Every XBRL-tagged fact ever filed by one company | UC2 XBRL cross-val ([#101](https://github.com/qte77/analyze-stock-kpi/issues/101)) |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK<10>/us-gaap/<Concept>.json` | One concept's time-series for one company | UC2 XBRL cross-val ([#101](https://github.com/qte77/analyze-stock-kpi/issues/101)) |
| `https://data.sec.gov/api/xbrl/frames/us-gaap/<Concept>/USD/CY<YYYY>Q<N>I.json` | Cross-sectional: one value per registrant for a quarter | Potential future universe-wide widget |
| `https://efts.sec.gov/LATEST/search-index?q=...&forms=...` | EDGAR full-text search (structured JSON, in-scope under ADR-0000) | Not currently used |
| `https://www.sec.gov/Archives/edgar/data/<CIK>/<accession-nondash>/<doc>.xml` | Raw filing documents (Form 4 XML, 13F-HR `infotable.xml`, 8-K header) | UC4 ([#102](https://github.com/qte77/analyze-stock-kpi/issues/102)), UC5 ([#103](https://github.com/qte77/analyze-stock-kpi/issues/103)) |

The `cgi-bin/browse-edgar` HTML endpoint is **out of scope** per
ADR-0000 — all use cases reachable via it are better served by the
JSON APIs above.

### Top-5 use cases for this project

Ranked by ROI (highest first):

1. **CIK ↔ ticker resolution layer** (S, shipped) — `src/sec/cik_map.py`.
   Prerequisite for every other EDGAR call.
2. **Last-filed staleness flags** (S, planned) —
   `sec_last_10k_date / sec_last_10q_date / sec_last_8k_date` on
   `FundamentalsSnapshot`. Universe-wide trust signal; a US issuer
   that hasn't filed a 10-Q in >150 days is either delisted, in
   restatement, or a foreign filer.
3. **XBRL cross-validation of yfinance numbers** (M,
   [#101](https://github.com/qte77/analyze-stock-kpi/issues/101)) —
   compare yfinance `totalRevenue` against SEC-filed `Revenues`,
   flag deltas. Catches yfinance bugs.
4. **Form 4 insider buying/selling momentum** (M-L,
   [#102](https://github.com/qte77/analyze-stock-kpi/issues/102)) —
   trailing-90-day net shares as a signal column.
5. **8-K material-events recency + item-code flags** (M,
   [#103](https://github.com/qte77/analyze-stock-kpi/issues/103)) —
   `4.01` auditor change, `5.02` officer departure, `2.05`
   impairment in last 30 days = yellow flag.

Descoped: 13F institutional ownership (CUSIP licensing); restatement
detection (low frequency); S-1 pre-IPO (no Yahoo ticker yet);
universe-wide XBRL frames (concept-drift complexity dominates).

### Gotchas

1. **CIK lookup failures for non-equity Yahoo symbols.**
   `company_tickers_exchange.json` covers SEC-registered equities
   only. ETFs partial coverage; FX / commodity futures / crypto /
   indices return no CIK. Caller must handle `None`.
2. **XBRL concept name drift.** The `us-gaap` taxonomy evolved
   post-ASC 606 (2017) — `SalesRevenueNet` → `RevenueFromContract
   WithCustomerExcludingAssessedTax`. No canonical alias map; try a
   prioritized list and take first non-null. Foreign filers (Form
   20-F) use `ifrs-full` namespace with different concept names.
3. **Rate limiting under cron on shared egress IPs.** GitHub Actions
   runners pool IPs; multiple parallel workflows can collectively
   breach the 10 req/sec ceiling. Implement exponential backoff on
   429/503 and respect any `Retry-After` header.

### References

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC Accessing EDGAR Data (User-Agent policy)](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [EDGAR Full Text Search FAQ](https://www.sec.gov/edgar/search/efts-faq.html)
- [data.sec.gov landing](https://data.sec.gov/)

---

## usaspending.gov

### Access model

**Fully keyless.** A REST JSON API mandated by the DATA Act
(31 U.S.C. § 6101), operated by Treasury's Bureau of the Fiscal
Service. No headers required; the API server is MIT-licensed on
GitHub. Practical request volume is "generous for individual
researchers"; no formal SLA published.

**Tier 0.** Outputs can land on a public `data` branch — the data is
explicitly public-domain (works of the federal government are not
copyrightable per US law).

### Endpoint we use

The pipeline uses one pre-aggregated category endpoint:

```bash
POST https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/
Content-Type: application/json

{
  "filters": {
    "award_type_codes": ["A", "B", "C", "D"],
    "time_period": [
      {"start_date": "2024-10-01", "end_date": "2025-09-30"}
    ]
  },
  "limit": 100,
  "page": 1
}
```

`award_type_codes=[A,B,C,D]` is "all contract types" (excludes
grants, loans, direct payments). `time_period` is one US fiscal year
(Oct 1 → Sep 30). Returns recipients **pre-ranked descending by
total obligated dollars** in the filtered window.

### Representative response

Verified against the
[upstream API contract](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_category/recipient.md)
on 2026-05-21:

```json
{
  "category": "recipient",
  "spending_level": "transactions",
  "limit": 100,
  "page_metadata": {
    "page": 1, "hasNext": true, "hasPrevious": false,
    "next": 2, "previous": null
  },
  "results": [
    {
      "amount": 46069068318.25,
      "recipient_id": null,
      "name": "MULTIPLE RECIPIENTS",
      "code": null,
      "uei": null,
      "total_outlays": null
    },
    {
      "amount": 17388378311.33,
      "recipient_id": "005a8812-bab5-2780-533b-b62c33271882-C",
      "name": "LOCKHEED MARTIN CORPORATION",
      "code": "008016958",
      "uei": null,
      "total_outlays": null
    }
  ],
  "messages": []
}
```

Per-result fields:

- `name` — recipient legal entity name (as registered with SAM).
- `recipient_id` — usaspending internal hash with `-P` / `-C` / `-R`
  suffix (parent / child / recipient). `null` for the `"MULTIPLE
  RECIPIENTS"` aggregate row (see Gotchas). Useful as the key for
  `/api/v2/recipient/<id>/` profile lookups, but the bridging thread
  settled on **ticker-level dedupe** instead (cheaper).
- `code` — **DUNS** (9-digit, D&B-legacy). Often present even though
  DUNS was deprecated April 2022; usaspending exposes the historical
  identifier for continuity. `null` for non-DUNS-registered entities
  and aggregate rows.
- `uei` — modern 12-char SAM identifier. `null` on aggregate rows and
  on older records that pre-date the UEI migration; do NOT assume it
  is populated.
- `amount` — total obligated dollars in the filtered window.
- `total_outlays` — outlays (cash actually disbursed) in the same
  window. Frequently `null` — usaspending populates outlays only
  under certain `spending_level` modes.

**No `rank` field in the response** — rank is derived from
`results[]` array position (the API pre-sorts descending by
`amount`).

### Filtering knobs

- `filters.naics_codes` — **dict, not list:**
  `{"require": ["33", "5417"], "exclude": [...]}`. Both keys optional.
  Values are 2-to-6-digit NAICS code prefixes (longer = narrower).
  Populated **only on contract awards** — grants and loans return
  null NAICS, so filtering by NAICS while also including grant
  award-type codes makes sector composition meaningless.
- `filters.awarding_agency_codes` / `filters.funding_agency_codes` —
  agency-specific universes.
- `filters.recipient_id` (with `-P` suffix) — scope to a single
  parent entity's awards.

### Why POST instead of GET

The filter payload carries nested objects (`naics_codes` is a dict,
`time_period` is an array of date-range objects, `agencies` is an
array of `{type, tier, name}` triples). Cramming that into URL query
strings would be fragile and hit URL-length limits. usaspending uses
POST for everything under `/api/v2/search/*`
(`spending_by_category/`, `spending_over_time/`,
`spending_by_award/`); GET is reserved for resource-id lookups like
`/api/v2/recipient/<id>/`. Convention is shared with Elasticsearch /
OpenSearch search APIs.

### Stability and ToS

- **API at v2** since ~2017; v1 deprecated. No formal semver
  promise. Field-level deprecations are announced via in-response
  `messages` array warnings + GitHub wiki entries in
  `fedspendingtransparency/usaspending-api`.
- **The `recipient_duns` sub-endpoint is phased out** in favor of
  the modern `/recipient/` path (already migrated; treat DUNS as
  legacy).
- **DATA Act § 6101 mandates public access; Treasury's open-data
  policy explicitly allows redistribution, adaptation, and
  commercial use.** A derived ticker preset committed to a public
  git branch raises no ToS concerns.

### Gotchas

1. **`"MULTIPLE RECIPIENTS"` aggregate row.** The first result is
   frequently the synthetic bucket of awards that couldn't be tied
   to a single recipient (cross-contract pools, masked-recipient
   awards). All three identifiers (`recipient_id`, `code`, `uei`)
   are `null` and `amount` is the sum across the bucket. **Filter
   out** any row with `recipient_id is None` before ranking.
2. **`uei` is unreliably populated.** Per the contract, `uei` may
   be `null` on legitimate contractor rows too — usaspending only
   populates the modern identifier where SAM registration carried
   it. Use `recipient_id` as the dedupe key; treat `uei` and `code`
   (DUNS) as opportunistic metadata.
3. **10,000-record deep-pagination wall** applies to the raw
   `spending_by_award` endpoint (award-level rows), **not** to the
   pre-aggregated `spending_by_category` endpoint we use. Top-500
   recipients via 5 paged calls is well within bounds.
4. **NAICS is contracts-only.** Filtering by `naics_codes` while
   also including grant award-type codes returns grants with null
   NAICS — sector composition becomes meaningless. Always restrict
   to `["A","B","C","D"]` if filtering on NAICS.
5. **No ticker or stock-exchange field.** The recipient → ticker
   bridge happens downstream via EDGAR (see "yfinance + name-to-
   ticker bridging" below). Subsidiaries appear as separate
   recipients (`LOCKHEED MARTIN AERONAUTICS CO` vs `LOCKHEED
   MARTIN CORPORATION`); dedupe at the ticker layer rather than
   chasing parent UEIs.

### References

- [usaspending.gov API root](https://api.usaspending.gov/)
- [spending_by_category contract spec](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_category.md)
- [Basic API Training PDF](https://www.usaspending.gov/data/Basic-API-Training.pdf)
- DATA Act (31 U.S.C. § 6101)

---

## sam.gov Entity Management API

**Not in the critical path.** Documented here as future Tier-1
enrichment work; the federal-contractors universe build does NOT
depend on sam.gov.

### Why deferred

The path of least resistance for ticker-list construction is
`usaspending → EDGAR → yfinance` — all keyless. sam.gov requires:

- A free API key obtained via a sam.gov account
  (`sam.gov/profile/details` → "Request Public API Key"). Instant,
  but rate-limited to **10 req/day** until entity-registration is
  completed.
- **Entity registration** (free, ~10 business days approval,
  annual renewal) to unlock the **1000 req/day** tier — the only
  usable threshold for any real automation.
- **Key rotation every 90 days** — pipeline must monitor expiry
  and alert ~15 days out.

For a ticker preset, none of sam.gov's extra fields (DBA names,
business-type codes, parent-UEI hierarchy, registration status) are
needed. Adding sam.gov inflates the setup-friction for contributors
without adding product value.

### What sam.gov adds when adopted

| Field | Use |
|---|---|
| `legalBusinessName` | Already available from usaspending |
| `dbaName` | Alternate trade names — useful for dashboard display |
| `cageCode` | DoD-specific contractor identifier |
| `entityStructureCode/Desc` | "Corporate Entity Not Tax Exempt" etc. |
| `businessTypes.businessTypeList[]` | Socioeconomic flags (SBA, veteran-owned, women-owned, HUBZone) |
| `goodsAndServices.naicsCodeList[]` | Richer NAICS list (all sectors the entity serves, not just primary) |
| `entityHierarchyInformation.immediateParentEntity` / `highestOwnerEntity` | Parent-UEI / ultimate-owner chain |
| `registrationStatus`, `registrationExpirationDate` | Active vs. inactive — could filter universe to active-only |

### Endpoints (when we eventually adopt)

```bash
# Single UEI lookup
GET https://api.sam.gov/entity-information/v3/entities
  ?api_key=$SAM_API_KEY
  &ueiSAM=JH9ZARNKWKC7
  &includeSections=entityRegistration,coreData

# CAGE code lookup
GET .../entities?cageCode=0TXG0&...

# Legal-name search (begins-with / wildcard — NOT fuzzy edit-distance)
GET .../entities?legalBusinessName=LOCKHEED MARTIN*&...
```

### Bulk extract alternative

```text
https://api.sam.gov/data-services/v1/extracts
  ?fileName=SAM_PUBLIC_MONTHLY_YYYYMMDD.ZIP
```

Monthly full extract (1st Sunday) + daily delta files (Tue-Sat).
**More complete and one day more current** than the Entity API
(which lags by one day). For one-time universe bootstrap this would
be the cheaper path than 100 per-UEI calls.

### What sam.gov CANNOT identify

**Whether an entity is publicly traded.** There is no business-type
code for "stock-exchange listed". Closest proxies (`entityStructureCode
= "2L"` Corporate Not Tax Exempt; `profitStructureCode = "2X"` For
Profit) are necessary-but-not-sufficient. **Stock-exchange membership
must be resolved externally** — which is what EDGAR
`company_tickers_exchange.json` + yfinance `fast_info` do in our
pipeline.

### Gotchas

1. **Key rotation every 90 days, no warning grace.** Returns 403 on
   expired key. Build expiry monitoring into any pipeline that adopts.
2. **Legal name ≠ ticker / trade name.** Plan for a separate
   reconciliation step (EDGAR or curated list).
3. **1000/day quota resets at midnight UTC with no burst.** For a
   universe enrichment run covering 200 tickers, that's 20% of the
   daily quota — cache responses aggressively (entity registrations
   are valid for a year and rarely change).
4. **D&B legacy fields.** Older records carry DUNS numbers that are
   D&B-copyrighted. UEI (post-April-2022) is clean. Avoid storing
   any `dunsNumber` field on the public `data` branch.

### References

- [SAM.gov Entity Management API | GSA Open Technology](https://open.gsa.gov/api/entity-api/)
- [SAM.gov Entity/Exclusions Extracts API](https://open.gsa.gov/api/sam-entity-extracts-api/)
- [SAM.gov Terms of Use](https://sam.gov/about/terms-of-use)
- [SAM Functional Data Dictionary (PDF)](https://open.gsa.gov/api/entity-api/v1/SAM%20Functional%20Data%20Dictionary_June%2023_v2.pdf)

---

## Yahoo Finance + name-to-ticker bridging

### yfinance ≥1.3.0 built-ins

**`yf.Search(query)`** — `v0.2.51+` (Dec 2024). Hits Yahoo's general
search endpoint. Returns `.quotes` list of dicts (`symbol`, `shortname`,
`longname`, `typeDisp`, `exchange`). Hard-capped at 5 quote results
per query in the underlying endpoint.

**`yf.Lookup(query)`** — `v0.2.56+` (April 2025). Uses Yahoo's
dedicated ticker-lookup endpoint mirroring `finance.yahoo.com/lookup/`.
Returns `.stock`, `.etf`, etc., with `.get_stock(count=100)` for
pagination. **More reliable** than `Search` for name-to-ticker
bridging (built specifically when `Search` was found to cap).

Both keyless; both inherit yfinance's cookie/crumb session handling.
No new dependencies — yfinance is already a runtime dep.

### Yahoo's raw `query2` search endpoint

```text
https://query2.finance.yahoo.com/v1/finance/search
  ?q=<query>&quotesCount=5&newsCount=0
```

Reverse-engineered, no SLA. Requires `User-Agent` + Yahoo's
cookie/crumb pair (yfinance handles automatically). Observed ceiling
~360 req/hour; tighter throttling reported through 2024-2025 (HTTP
429 after ~950 calls per session). yfinance wraps these as
`YFRateLimitError`. **Acceptable for one-time bootstrap (~30 calls);
not for nightly bulk resolution.**

### SEC EDGAR `company_tickers_exchange.json` as the bridge

This is **the cheapest, most reliable name-to-ticker mapping** for
SEC-registered equities. Single keyless GET of ~1 MB JSON. Schema:

```json
{
  "fields": ["cik", "name", "ticker", "exchange"],
  "data": [
    [320193, "Apple Inc.", "AAPL", "Nasdaq"],
    [789019, "MICROSOFT CORP", "MSFT", "Nasdaq"],
    [936468, "LOCKHEED MARTIN CORP", "LMT", "NYSE"],
    ...
  ]
}
```

Used in the federal-contractors universe build as the **primary
name-match candidate generator**. usaspending recipient legal names
are matched against the EDGAR `name` field via
`difflib.SequenceMatcher` (stdlib — no new deps; threshold ~0.85).

**Failure modes — known and accepted:**

- **Subsidiaries** are the dominant mismatch class. SAM/usaspending
  register the contracting entity (`RAYTHEON MISSILES & DEFENSE`,
  `BOOZ ALLEN HAMILTON INC`) while EDGAR holds the publicly-listed
  parent (`RTX CORP`, `BOOZ ALLEN HAMILTON HOLDING CORP`). The
  subsidiary may have no EDGAR entry, or a separate CIK with no
  exchange listing.
- **Recent name changes.** RTX was Raytheon Technologies through
  2023. EDGAR reflects current names; SAM lags.
- **Private companies** — Anduril, Peraton, Bechtel, Deloitte arms,
  and most large defense subsidiaries don't file with the SEC and
  thus have no EDGAR entry.
- **OTC / ADR ambiguity** — foreign primes (BAE Systems → `BAESY`,
  Leonardo SpA → `FINMY`, Rolls-Royce → `RYCEY`) are on OTC; their
  `typeDisp` is `"EQUITY"` but exchange field is `"OTC"`. They
  resolve fine via yfinance; just be aware.

### The curated DoD Top-25 seed list

To handle the failure modes above, the federal-contractors build
**always seeds** the preset with the DoD's annual "Top-25 Publicly
Traded Contractors" list, verified by name:

| SAM-style legal name | Ticker | Exchange |
|---|---|---|
| LOCKHEED MARTIN CORPORATION | `LMT` | NYSE |
| RTX CORPORATION | `RTX` | NYSE |
| NORTHROP GRUMMAN CORPORATION | `NOC` | NYSE |
| GENERAL DYNAMICS CORPORATION | `GD` | NYSE |
| THE BOEING COMPANY | `BA` | NYSE |
| L3HARRIS TECHNOLOGIES INC | `LHX` | NYSE |
| HUNTINGTON INGALLS INDUSTRIES INC | `HII` | NYSE |
| LEIDOS INC | `LDOS` | NYSE |
| BOOZ ALLEN HAMILTON INC (parent: HOLDING CORP) | `BAH` | NYSE |
| SCIENCE APPLICATIONS INTERNATIONAL CORPORATION | `SAIC` | NYSE |
| CACI INTERNATIONAL INC | `CACI` | NYSE |
| KBR INC | `KBR` | NYSE |
| TEXTRON INC | `TXT` | NYSE |
| OSHKOSH DEFENSE LLC (parent: OSHKOSH CORP) | `OSK` | NYSE |
| GENERAL ELECTRIC COMPANY | `GE` | NYSE |
| HONEYWELL INTERNATIONAL INC | `HON` | NASDAQ |
| FLUOR CORPORATION | `FLR` | NYSE |
| JACOBS SOLUTIONS INC | `J` | NYSE |
| DELL TECHNOLOGIES INC | `DELL` | NYSE |
| ACCENTURE FEDERAL SERVICES LLC (parent: ACCENTURE PLC) | `ACN` | NYSE |
| PALANTIR TECHNOLOGIES INC | `PLTR` | NASDAQ |
| MICROSOFT CORPORATION | `MSFT` | NASDAQ |
| AMAZON WEB SERVICES INC (parent: AMAZON.COM INC) | `AMZN` | NASDAQ |
| BAE SYSTEMS (US holdings; parent OTC ADR) | `BAESY` | OTC |
| MAXIMUS FEDERAL SERVICES INC (parent: MAXIMUS INC) | `MMS` | NYSE |
| ICF INCORPORATED LLC (parent: ICF INTERNATIONAL INC) | `ICFI` | NASDAQ |

Source: DoD's "Top 25 Publicly Traded Prime Contractors" published
annually by SOCO. The list is the **defensive bootstrap** — every
member is in the final preset regardless of usaspending API health
on any given week.

### Publicly-traded fraction of top-100 federal contractors

Roughly **30-35 % of the top-100** by DoD obligation dollars are
publicly traded — the rest are private LLCs (Bechtel, Peraton,
Anduril, Deloitte arms), defense subsidiaries without independent
listing, healthcare distributors, energy suppliers, etc.

For our top-100 input, **expect ~25-40 verified tickers in the final
preset** after EDGAR matching + yfinance smoke-test. The narrow
defense-prime tail dominates dollar volume but not headcount.

### Smoke-test gate

Every candidate ticker passes through:

```python
import yfinance as yf
info = yf.Ticker(t).fast_info
if not info:           # empty / unresolvable → drop
    ...
```

`fast_info` is yfinance's cheap path (no full `info` dict fetch).
Used as a final gate to filter out delisted tickers, recently-changed
symbols, and OTC tickers that yfinance can't resolve.

### References

- [yfinance `Search` reference](https://ranaroussi.github.io/yfinance/reference/yfinance.search.html)
- [yfinance `Lookup` reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html)
- [yfinance CHANGELOG](https://github.com/ranaroussi/yfinance/blob/main/CHANGELOG.rst)
- [Top 100 Defense Contractors 2024 — Defense Security Monitor](https://dsm.forecastinternational.com/2025/11/12/top-100-defense-contractors-2024/)
- [DoD Top 25 Publicly Traded Contractors PDF](https://ederfinancial.org/files/galleries/DoD_Lists_2024_Top_25.pdf)
- [Yahoo Finance rate-limiting — yfinance issue #2422](https://github.com/ranaroussi/yfinance/issues/2422)

---

## Refresh cadence summary

| Source | Cadence | Owner |
|---|---|---|
| EDGAR `company_tickers_exchange.json` | Per-run, in-process cache (one fetch per `make run`) | `src/analyze_stock_kpi/data_sources/sec/cik_map.py` |
| EDGAR submissions / XBRL / Form-4 / 8-K | Per-ticker per-run | Per-feature SEC module |
| usaspending `spending_by_category/recipient` | **Weekly** Sunday 04:00 UTC, 2h before `demo-snapshot.yaml` | `.github/workflows/federal-contractors-refresh.yaml` (per ADR-0006 + thread refinement 2026-05-20) |
| sam.gov Entity API | n/a — not in critical path | Deferred |
| Yahoo Finance `fast_info` smoke-test | Build-time only (universe refresh) | `scripts/build_federal_contractors.py` |

The `federal-contractors-refresh` workflow's preset-file PR to `main`
is **suppressed when the ticker diff is empty** (most weeks at top-100
scale); the audit JSON still commits to the `data` branch every week
for retrospective trail.
