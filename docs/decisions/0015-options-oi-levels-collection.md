# ADR-0015 — Collect SPY options open-interest levels daily; collection only

**Status:** Accepted 2026-11-22 (owner approved the licensing verdict, incl. the unverified points) · **Relates to:**
[ADR-0011](0011-equity-macro-overlay-via-spy-indexed-returns.md) (SPY derived-only precedent),
[ADR-0013](0013-point-in-time-backtest.md) (the backtest that must support any later use) ·
**Plan:** [011](../plans/011-options-oi-levels.md), issue [#563](https://github.com/qte77/analyze-stock-kpi/issues/563)

## Context

Yahoo (via yfinance) lists SPY option chains with per-strike open interest (OI), but only for the
current day. There is no free OI history, so the data exists only from the day collection starts.
Large OI strikes are a hypothesis for price "gravity" near expiry. The hypothesis is untested here.

## Decision

1. **Collect only.** Every weekday, derive OI levels for SPY and store them. They stay out of the qte77
   Score and the dashboard until the point-in-time backtest (ADR-0013) supports them.
2. **Two expiries per day.** `nearest` = the first listed expiry on or after the collection date.
   `monthly` = the first listed expiry on or after the collection date that is the third Friday of its
   month; a listed Thursday counts as monthly only when the third Friday after it is not listed (the
   market-holiday case, as on 2025-04-17 before Good Friday). If both are the same expiry, both rows are still written.
3. **Six fields per row:** `max_pain`, `call_wall`, `put_floor`, `pc_oi_ratio`, `total_oi`,
   `oi_null_share`. Definitions and tie rules are in plan 011 (Approach). Null OI counts as 0. Rows also
   carry `date`, `expiry_kind` and `expiry`, and are keyed by `(date, expiry_kind)`.
4. **Row date = collection date (UTC).** What day the OI itself reflects (prior close or intraday) is
   **to confirm in plan 011 row 3**; until then the row date does not claim an as-of date for the OI.
   (Checked: see the 2026-11-23 amendment below.)
5. **Cut: dealer gamma exposure (GEX) and its sign.** GEX rests on an assumption about which side
   dealers hold, and the null-OI share (about 14 % in the nearest expiry on 2026-11-22) makes it noisy.
   It can come back as its own decision if the levels prove useful.
6. **Where data goes.** The public `data` branch gets only the derived rows
   (`results/series/options_oi/YYYY.json`). Raw chains (Yahoo payloads) go only to the gitignored
   `results/prices/options/SPY/<date>.json` and, when `CACHE_REPO_TOKEN` exists, to the private cache
   repo. They are never committed publicly.

## Licensing verdict

**CLEAR (derived-only), same tier as the SPY row**, with the open points below. Strike prices are
contract terms. The other fields are aggregates computed by this pipeline, not quotes. Raw chains stay
private, matching the CAUTION handling of Yahoo payloads in
[`data-sources.md`](../data-sources.md) (Redistribution guardrails).

Checked 2026-11-22 (fetched pages treated as data):

- **OPRA** ([opraplan.com](https://www.opraplan.com/)): verified. Open interest is listed among the
  "other types of information" OPRA disseminates; redistributing OPRA data needs a Vendor Agreement
  with OPRA; the page does not address derived data. It states that the OPRA Plan and other documents
  control if they conflict. **Unverified:** the OPRA Plan / Vendor Agreement text itself, so whether
  aggregates computed from OI count as redistribution is not confirmed at source.
- **OCC** (source of the OI figures): **unverified.** `theocc.com` pages returned HTTP 403 to the
  fetch tool, so OCC's own terms were not read.
- **Yahoo** ([Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), sections
  2(d)(ix), 2(d)(x), 2(e), 2(h); the last ~27k characters of the page were not read): verified. They
  restrict automated collection, building aggregated data sources, commercial reuse and redistribution
  of the Services. This is the same restriction the repo already accepts for every derived yfinance
  series (SPY, yield curve) by publishing only derived facts, never raw payloads. The residual risk is
  therefore the same as for those series, not new. It is a risk posture, not a legal opinion.

Merging this ADR accepts that verdict, including the unverified points. If OCC or OPRA terms are
later found to forbid publishing derived OI aggregates, stop the workflow and revisit this ADR.

## Consequences

- Rows start accumulating on the `data` branch from the first scheduled run; a hypothesis test needs
  about 6 months of rows (plan 011 row 5).
- Public data stays small and derived. Raw chains are discarded with the runner if no private cache
  token exists.
- Market holidays are not special-cased: the row repeats the prior OI.

## Alternatives considered

- **Include GEX:** rejected for now (decision 5).
- **Publish raw chains:** rejected. They are Yahoo payloads (CAUTION).
- **Wait for the backtest before collecting:** rejected. There is no OI history, so waiting only loses
  data.
- **QQQ and other symbols:** deferred; a later one-line config change if wanted.

## Amendment (2026-11-23) — OI timing (decision 4, plan 011 row 3)

On Mon 2026-11-23 the scheduled run (13:16 UTC) and a manual run (20:34 UTC) stored identical
per-expiry call and put OI for both expiries (2026-11-23: 289,769 / 280,515; 2026-12-18: 1,394,084 /
2,463,801). So Yahoo's OI does not move during the session and the 13:07 UTC weekday schedule stays.
The monthly total did change between a reading on Sun 2026-11-22 18:58 UTC (3,771,784) and the Monday
run (3,857,885), so the update happens overnight. A row's OI is therefore the latest overnight
publication, most likely the previous trading session's close. That as-of day is an inference from
one day of observations, not confirmed against OCC's publication schedule.
