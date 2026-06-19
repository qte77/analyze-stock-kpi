# ADR-0011 — Equity-macro overlay via SPY indexed returns

**Status:** Accepted (2026-06-19)

**Relates to:**
[ADR-0005](0005-sentiment-risk-sources.md) — the three-tier source framework
(`^GSPC`/`SPY` reach via the same keyless Yahoo v8 chart endpoint as the existing
`^TNX`/`^FVX` legs, Tier 0).
[`docs/data-sources.md`](../data-sources.md) §"Redistribution guardrails" — the
standing rule this decision applies: **persist derived state only, never raw
price payloads.**

## Context

Issue #288 wants an equity-market line on the merged long-term-context chart for
macro context (alongside CNN F&G and the 5s10s slope). The obvious series — the
**S&P 500 index level (`^GSPC`)** — cannot be committed to the public `data`
branch:

- **S&P Dow Jones Indices** prohibits reproducing the S&P 500 index "in any
  form" without a licence, and actively enforces it. This is a *second*
  restriction layer on top of Yahoo's ToS, and a `^GSPC` level series is exactly
  the index reproduction they prohibit.
- Pulling the same level from FRED's `SP500` series does not help — it carries
  the identical S&P DJI copyright notice ("reproduction … prohibited").
- The repo's own guardrail (`docs/data-sources.md`) already says: when a source's
  ToS is ambiguous, **default to CAUTION — persist derived state only, not raw
  payloads.** A raw price level fails that test.

Rounding or approximating the index level was considered and rejected: a rounded
S&P 500 value is still the index "in any form" — it buys no legal protection and
degrades the data.

## Decision

Source the equity-macro line from **SPY** (the SPDR S&P 500 ETF, a State Street
*security*), not the S&P DJI index, and commit only a **derived indexed-return**
series:

1. **Instrument: `SPY`.** SPY's market price is a fact about a traded security on
   NYSE Arca — it is **not** the S&P DJI index level, so the index-IP layer does
   not attach. The only remaining layer is Yahoo's ToS, identical to the existing
   `yield_curve` (`^TNX`/`^FVX`) series and mitigated the same way (derived-only;
   *Feist* — facts are uncopyrightable).
2. **Stored value: `ret_indexed` only.** `results/series/equity_spy/YYYY.json`
   rows are `{ date, ret_indexed }` where `ret_indexed = close / close_epoch *
   100` (rebased to 100 at the series epoch). The **raw `close` is never
   committed.** This is the same derived-state posture as the `yield_curve` slope.
3. **UI labelling:** the line is **"SPY (indexed)" / "US equity (SPY)"** — never
   the "S&P 500®" trademark, and no SPDR/State Street branding.

## Consequences

- A new Tier-0 `equity_spy` series joins `cnn_fg` and `yield_curve` on the `data`
  branch, at the **same** redistribution risk tier (derived value, no index IP).
- `docs/data-sources.md` gains an `equity_spy` guardrail row; a repo-root
  `NOTICE` records the non-commercial/educational, derived-data posture and the
  upstream ToS URLs.
- The chart shows relative equity trajectory (indexed), not absolute index
  points — sufficient for macro context on a log axis, and the honest
  representation of what we may publish.
- Yahoo's ToS still applies to *fetching* (as for every series); unchanged.

## Alternatives considered

- **Raw `^GSPC` levels (rejected):** dual-layer prohibition (Yahoo ToS + S&P DJI
  IP); conflicts with the repo's derived-only rule.
- **`^GSPC` derived/indexed (rejected):** removes the raw-level issue but a
  reversible transform of the *index itself* is still arguably "the index in any
  form" — S&P DJI's IP ambiguity remains. SPY removes that layer at the source.
- **Drop the overlay (rejected):** #288 explicitly wants equity context.
- **Round/approximate the index (rejected):** no legal protection; worse data.

## References

- [`docs/data-sources.md`](../data-sources.md) — redistribution guardrails.
- S&P Dow Jones Indices disclaimers — index reproduction prohibited.
- Issue [#288](https://github.com/qte77/analyze-stock-kpi/issues/288) — merged
  long-term chart + equity overlay.
