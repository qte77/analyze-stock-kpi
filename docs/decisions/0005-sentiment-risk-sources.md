# ADR-0005 — Three-tier sentiment + risk source framework

**Status:** Accepted (2026-05-20)

**Closes:** [#22](https://github.com/qte77/analyze-stock-kpi/issues/22)
sentiment-sources research — resolved by this ADR.

**Relates to:**
[#100](https://github.com/qte77/analyze-stock-kpi/issues/100)
volatility-indices chart (concrete Tier-0 implementation).

## Context

The repo currently surfaces one sentiment indicator (CNN Fear & Greed)
via `src/sentiment.py`, with daily snapshots persisted to the `data`
branch under `results/cnn_fg/YYYY.json` by
`.github/workflows/fear-greed.yaml`.
[#22](https://github.com/qte77/analyze-stock-kpi/issues/22) opened a
survey of alternative risk-sentiment sources (UBS, Citi, Goldman, State
Street, NAAIM, AAII, Bloomberg, etc.) and asked which to add next.

Working through the survey surfaced a sharper question: **the right
axis isn't "which source", it's "which authentication tier"**. Sources
fall cleanly into three buckets based on what credentials they require,
and that bucket dictates where their output can live (public `data`
branch vs. runtime-only) and whether they can be on by default.

The project's invariants from earlier ADRs are load-bearing here:

- [ADR-0000](0000-remove-traderfox.md) — no HTML scraping. Sources must
  expose documented, structured (JSON / CSV / XML) endpoints.
- The CLI must work out of the box for any cloner of the repo, with no
  environment-variable setup, no API-key registration, and no paid
  subscriptions. Anything beyond that must be opt-in.

## Decision

Adopt a three-tier framework for all current and future sentiment +
risk data sources. Tier defines the auth requirement, the default
state, and the persistence policy.

### Tier 0 — keyless free, default-on

- **Auth:** none (anonymous public endpoint, possibly with a
  documented `User-Agent` policy as for SEC EDGAR).
- **Default:** ON. Runs in every `make run` and every cron-driven
  history workflow.
- **Persistence:** outputs land on the public `data` branch.
- **In scope:**
  - **CNN Fear & Greed** — `src/sentiment.py` already implements this.
    Endpoint:
    `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`.
  - **Yahoo-Finance-proxied volatility indices** (the set from
    [#100](https://github.com/qte77/analyze-stock-kpi/issues/100):
    `^VIX`, `^VVIX`, `^VIX9D`, `^VIX3M`, `^VIX6M`, `^SKEW`, `^OVX`,
    `^MOVE`, `^NKVI.OS`, `^INDIAVIX`). Endpoint:
    `https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>`.

### Tier 1 — free key, opt-in via env var

- **Auth:** free API key (no payment, but registration required),
  surfaced via a single environment variable per source.
- **Default:** OFF. Activates only when the env var is set.
- **Persistence:** outputs may land on the public `data` branch if
  the source's ToS permits redistribution; otherwise runtime-only.
- **In scope (designed, deferred):**
  - **NAAIM Exposure Index** — published by NAAIM
    (<https://www.naaim.org/programs/naaim-exposure-index/>),
    typically consumed via Nasdaq Data Link
    (<https://data.nasdaq.com/>). Requires
    `NASDAQ_DATA_LINK_API_KEY`. Implementation deferred until there
    is a concrete consumer (chart, composite, alert) requesting the
    series.
  - **AAII Sentiment Survey** — published by AAII
    (<https://www.aaii.com/sentimentsurvey>), available via Nasdaq
    Data Link. Same key.
  - **sam.gov Entity Management API** — as future enrichment for the
    federal-contractors universe (a separate ADR will define the
    universe build itself). Requires `SAM_API_KEY` and a one-time
    free entity-registration step on sam.gov (~10 business days
    approval) to unlock the usable 1000 req/day tier. Keys rotate
    every 90 days; a Tier-1 workflow that consumes sam.gov must
    monitor key expiry. Not in critical path — the universe can be
    built keyless from usaspending.gov + SEC EDGAR; sam.gov adds
    DBA names, business-type designations, and parent-UEI hierarchy
    when those become useful.

### Tier 2 — paid subscription, opt-in

- **Auth:** paid vendor subscription plus vendor SDK or institutional
  API credentials.
- **Default:** OFF. Activates only when the relevant SDK is installed
  and credentials are configured.
- **Persistence:** **never** the public `data` branch. Vendor ToS
  bans redistribution; outputs are runtime-only or persist to a
  private store the operator controls.
- **In scope (designed, deferred):**
  - **UBS / Citi proprietary indicators** — via Bloomberg `blpapi`
    (<https://www.bloomberg.com/professional/support/api-library/>).
  - **Goldman Sachs Marquee indicators** — via `gs-quant`
    (<https://developer.gs.com/p/docs/services/gs-quant>).
  - **State Street institutional sentiment** — via State Street's
    institutional API.

### Gating rule

Any source requiring ANY form of authentication lives in Tier 1 or
higher and defaults to OFF. Tier 0 is reserved exclusively for
sources with documented, unauthenticated public endpoints (the
`User-Agent` requirement on SEC EDGAR is not "authentication" — it is
identification, and no credential is exchanged).

## Consequences

- **Default behavior stays keyless.** Cloning the repo and running
  `make run` continues to work with no env vars, with no risk of
  partial-failure modes from missing credentials.
- **`data` branch contains only Tier 0 outputs.** This is enforceable
  by convention (workflow files only write Tier 0 data) and by
  policy (Tier 2 outputs are forbidden from any public surface).
- **Per-tier opt-in is uniform.** Tier 1 sources activate via env-var
  presence; Tier 2 sources activate via the corresponding optional
  dependency being installed (e.g., `blpapi`, `gs-quant`) plus its
  own credentials.
- **Adding a new source requires choosing its tier first.** The tier
  determines persistence, default state, and CI workflow eligibility.
- **Out of scope** for this ADR — explicitly not in any tier:
  - **UBS GREBI** — annual PDF only, no programmatic path.
  - **UBS FX Risk Indicator** — licensed via S&P DJI, no public
    endpoint.
  - **BofA Bull & Bear Indicator** — no programmatic access.
  - **African ex-JSE and LatAm ex-Brazil markets** — no public
    infrastructure for sentiment / volatility series.

## Amendment (2026-05-30) — whit3rabbit/fear-greed-data Tier-0 mirror

`src/sentiment.py` reads the live CNN endpoint, which only exposes
~1 year of headline history. To cover the demo dashboard's Long-Term
Context tab (#159) back to CNN's 2011-01-03 inception, this amendment
classifies the community mirror
[whit3rabbit/fear-greed-data](https://github.com/whit3rabbit/fear-greed-data)
as a **Tier-0 backfill source**, pinned to commit SHA
`aa4f600959a12f9266d5bff75a78a50987b7e760` (2026-05-29) for
deterministic re-runs.

The mirror satisfies the Tier-0 criteria:

- **Auth:** none — public CSV at a deterministic raw-content URL
  (`https://raw.githubusercontent.com/.../fear-greed.csv`).
- **Default:** off (one-shot backfill, not a cron). The daily
  `fear-greed.yaml` workflow remains the only Tier-0 source running
  by default; whit3rabbit is invoked manually via
  `scripts/backfill_fear_greed_whitrabbit.py`.
- **Persistence:** outputs land on the `data` branch — same
  `results/cnn_fg/YYYY.json` files the CNN-direct path writes,
  merged via the existing `_upsert` semantics with `force=False`
  so a higher-fidelity CNN-direct row always wins on shared dates.

### License posture

The upstream repo has **no `LICENSE` file** as of the pinned SHA
(tracked at [`whit3rabbit/fear-greed-data#2`](https://github.com/whit3rabbit/fear-greed-data/issues/2)).
The CSV is derivative of CNN's public Fear & Greed endpoint, which
this project already consumes keyless under fair-use. We accept the
mirror as-is on that derivative-public-data basis; if upstream lands
an explicit license, this amendment will be revised to cite it.

### Scope limits

- **Subindicator backfill is out of scope.** Whit3rabbit only ships
  the headline score + rating. The 10 subindicator blocks
  (`market_momentum_*`, `stock_price_*`, `put_call_options`, etc.)
  stay `None` for backfilled rows. The dashboard's monthly aggregate
  reduces headline scores only, so this is visually equivalent;
  detail-panel views may render "—" for pre-2025 subindicator cells.
- **No continuous re-sync.** This is a one-shot backfill. The daily
  CNN-direct cron remains authoritative for ongoing dates.

## References

- CNN Fear & Greed JSON endpoint:
  `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`
- Yahoo Finance v8 chart endpoint:
  `https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX`
- Nasdaq Data Link API docs:
  <https://docs.data.nasdaq.com/docs/getting-started>
- NAAIM Exposure Index (publisher page):
  <https://www.naaim.org/programs/naaim-exposure-index/>
- AAII Sentiment Survey (publisher page):
  <https://www.aaii.com/sentimentsurvey>
- Bloomberg API library:
  <https://www.bloomberg.com/professional/support/api-library/>
- GS Marquee (`gs-quant`):
  <https://developer.gs.com/p/docs/services/gs-quant>
- sam.gov Entity Management API:
  <https://open.gsa.gov/api/entity-api/>
- Nikkei 225 VI profile:
  <https://indexes.nikkei.co.jp/en/nkave/index/profile?idx=nk225vi>
- CBOE indices catalogue:
  <https://www.cboe.com/us/indices/>
- Related: [ADR-0000](0000-remove-traderfox.md) — no HTML scraping
  policy (informs Tier 0's "documented endpoint" requirement).

## Amendment (2026-05-31) — aggregated-scores best + worst Tier-0 aggregator

[#184](https://github.com/qte77/analyze-stock-kpi/issues/184) ships a
cross-universe meta preset, emitted as **two paired universes**
(`aggregated-scores-best` and `aggregated-scores-worst`, 25 tickers
each) from a single composite-mean ranking pass across the 7
sector/region universes. This amendment classifies the aggregator as
a **Tier-0 pure-aggregation source**.

The paired-output shape (one orchestrator pass → two preset files →
two picker entries) is the canonical pattern for **cross-universe
long/short candidate sets** in this repo. Phase 2
[`enhanced-kpi-screener-longshort`](https://github.com/qte77/analyze-stock-kpi/issues/192)
reuses the pattern with gated criteria (`-longs` + `-shorts`) instead
of composite-mean ranking.

- **Auth:** none. The aggregator consumes Tier-0 demo snapshots already
  on the `data` branch (`results/demo/<u>/<latest>.json`), via the same
  `git checkout origin/data --` pattern `demo-snapshot.yaml` uses. No
  new external boundary, no new HTTP, no new rate-limit surface.
- **Default:** weekly cron on (`Sunday 02:00 UTC`, staggers before
  federal-contractors at `04:00` and demo-snapshot at `06:15`).
- **Persistence:** preset `.txt` lives in `src/assets/universes/` on
  `main` (auto PR-on-diff); per-ticker audit JSON lives on the `data`
  branch under `results/aggregated_scores_best_and_worst/audit/`.

### NOT a hedging primitive

Composite-mean ranking blends growth / value / quality signals. The
top-25 by mean is a **meta-screening starting point** ("what should I
look at first?"), not a long-candidate set. The hedging-grade
counterpart — a 16-criteria conjunctive multi-KPI gate set — ships as
[`enhanced-kpi-screener-longshort`](https://github.com/qte77/analyze-stock-kpi/issues/192)
in Phase 2 and produces fundamentally-grounded long + short presets.

Documenting the limitation here prevents downstream consumers from
misusing the aggregator output for hedging-pair construction.

### Sector bias caveat

Composite scoring uses **absolute thresholds** per [ADR-0002](0002-simplified-composites.md)
(e.g., ROE 0% -> 30% mapped to 0 -> 100). Cross-sector aggregation
inherits this — banks structurally cluster lower than tech on
quality / margin metrics. The bias attenuates in practice because our
7 universes are sector-mixed, not sector-pure. If the first weekly
cron's top-25 / bottom-25 output shows persistent sector skew, the
trigger is an ADR-0002 amendment introducing percentile-rank-within-
universe scoring; until then, ship absolute thresholds + observe.
