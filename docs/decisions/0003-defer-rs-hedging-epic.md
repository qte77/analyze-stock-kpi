# ADR-0003 — Defer the v0.6.0 RS hedging epic

**Status:** Accepted (2026-05-11). **Superseded by [ADR-0012](0012-longshort-model-portfolio.md)
for the portfolio-tracking scope** (2026-09-22) — the RS-signal survey below stays the
reference for any future relative-strength work.

**Defers (without abandoning):**
[#4](https://github.com/qte77/analyze-stock-kpi/issues/4) RS hedging
parent epic;
[#8](https://github.com/qte77/analyze-stock-kpi/issues/8) Mansfield RS;
[#9](https://github.com/qte77/analyze-stock-kpi/issues/9) regime-split
returns; [#10](https://github.com/qte77/analyze-stock-kpi/issues/10)
long/short ranking + CLI.

**Closes:** [#55](https://github.com/qte77/analyze-stock-kpi/issues/55)
RS alternatives survey — resolved by this ADR.

## Context

[#4](https://github.com/qte77/analyze-stock-kpi/issues/4) scheduled a
relative-strength / regime-conditional hedging analysis pipeline for
v0.6.0, decomposed into Mansfield Relative Strength
([#8](https://github.com/qte77/analyze-stock-kpi/issues/8)),
regime-split returns
([#9](https://github.com/qte77/analyze-stock-kpi/issues/9)), and
long/short ranking + CLI wiring
([#10](https://github.com/qte77/analyze-stock-kpi/issues/10)).

[#55](https://github.com/qte77/analyze-stock-kpi/issues/55) opened a
survey of alternative RS formulations (Wilder's RSI-RS, Dorsey RS,
IBD-style rank, ratio-of-MAs, beta-adjusted excess return, information
ratio). Working through the survey surfaced a sharper question: **does
the hedging epic fit the project at all?**

The project's tagline (AGENTS.md, README.md) is a "single-purpose CLI
fetching fundamentals via yfinance" — point-in-time KPIs from
`yf.Ticker(t).info`. The hedging epic introduces a **different data
axis**:

- Historical price series fetching per ticker plus the benchmark (SPY).
- pandas as a direct runtime dependency.
- Regime classification (50-day SMA slope on the benchmark).
- Per-asset conditional summary statistics (mean log-return over up- and
  down-tagged subsets).
- A separate output file with an interpretation surface (`up_return`,
  `down_return`, `score`) that does not read at a glance like the
  existing per-asset KPI snapshot.

That stack is behavioral price analytics, not stock KPIs. It can be
built — the design space is well-mapped (see the survey below) — but it
belongs in a sibling tool that consumes this repo's
`results/fundamentals_<UTC>.json` rather than living inside the
single-purpose KPI CLI.

## Decision

Defer the entire v0.6.0 RS hedging epic. No `src/relative_strength.py`,
no `src/regime_hedging.py`, no pandas dependency, no `--with-rs` /
`--with-regime` CLI flag in v0.6.0. The four sub-issues stay **open**
with the `deferred` label so the work surfaces in future planning but
does not block any near-term release;
[#55](https://github.com/qte77/analyze-stock-kpi/issues/55) closes
because the survey is complete and its outcome is captured here.

The v0.6.0 milestone is **left open for repurposing** around a
deliverable better aligned with the project's stock-KPI tagline (richer
fundamentals, additional composites from existing inputs, sector
tagging, UX polish — decided fresh).

## RS / hedging-signal survey (rationale captured for future work)

| Candidate | Verdict |
|---|---|
| **Mansfield RS** (`((stock / index) / SMA(stock/index, n) - 1) * 100`) | Deferred. Simplest of the benchmark-relative family, point-in-time, easy to vectorize. Informational only — would not feed the long/short ranking score (`down_return − up_return`). |
| **Wilder's RSI-RS** | Different signal family — pure-momentum oscillator on close changes, no benchmark reference. Would not answer [#4](https://github.com/qte77/analyze-stock-kpi/issues/4)'s question and is in the survey only to disambiguate the name. |
| **Dorsey RS** (log-ratio smoothed via Wilder) | Bounded log-ratio interpretation is nicer than Mansfield but adds Wilder smoothing complexity for no hedging-signal benefit; same metadata-only role. |
| **IBD-style RS Rank** (cross-sectional percentile, 1-99) | Structurally different — requires universe stability and cross-sectional compute on every snapshot. Worth a separate epic if user demand surfaces. |
| **Ratio-of-MAs** (`SMA(stock,n) / SMA(index,n)`) | Simpler than Mansfield but laggier; same metadata-only role. |
| **Beta-adjusted excess return** (`r_stock − β · r_index`) | Requires rolling-β regression; β estimation is itself regime-dependent, making it noisy on the lookbacks the epic targeted (63 / 126 / 252 trading days). |
| **Information ratio** (`(r_stock − r_index) / TE`) | Tracking-error estimation is noisy on short windows; same metadata-only role. |
| **Regime-conditional returns** (50-day SMA-slope tagging → per-asset `(up_return, down_return)`, `score = down_return − up_return`) | The load-bearing primitive that would have answered [#4](https://github.com/qte77/analyze-stock-kpi/issues/4) directly without any of the RS formulas above. Deferred together with the rest of the epic. |

## Consequences

**Won:**

- v0.6.0 milestone reopens for a deliverable better aligned with the
  project's stock-KPI tagline.
- No pandas direct dep, no time-series fetch path, no per-asset
  price-history surface area added to a project whose value
  proposition is point-in-time fundamentals.
- The survey work in
  [#55](https://github.com/qte77/analyze-stock-kpi/issues/55) is
  preserved as a rationale document so a future epic does not
  re-litigate it.

**Lost:**

- No long/short hedging analytics in any near-term release. Users who
  want defensive / weak-rallier identification need to build it
  elsewhere.
- The `results/relative_strength_<UTC>.json` schema and `--with-rs` UX
  never ship in this repo — any future revival will redesign them
  fresh, possibly under a different home.

**Accepted risks:**

- Deferred sub-issues may stagnate. The `deferred` label keeps them in
  the backlog, but without a milestone they are easy to overlook.
  Re-triage during the next milestone planning is the mitigation.

## Future home (if the work is revived)

A standalone sibling repo — e.g. `qte77/regime-hedging` — that:

- Consumes this repo's `results/fundamentals_<UTC>.json` for the
  resolved-ticker universe.
- Adds its own price-history fetch (pandas, yfinance `.history()`).
- Emits a separate ranking output file consumable alongside the KPI
  snapshot.

This matches the qte77 ecosystem pattern (separate repos for separate
single-purpose tools) and keeps the KPI CLI's dependency surface tight.

## Out of scope

- Reviving the epic inside the KPI CLI without a clear product reason
  to widen its scope.
- Backtesting, intraday RS, cross-asset RS, per-region benchmark
  routing — all deferred with the rest of the epic.
- Removing the deferred sub-issues from the tracker. They stay open
  with the `deferred` label so the work remains discoverable.

## References

- [#4](https://github.com/qte77/analyze-stock-kpi/issues/4) — RS
  hedging parent epic (deferred)
- [#8](https://github.com/qte77/analyze-stock-kpi/issues/8) —
  Mansfield RS sub-issue (deferred)
- [#9](https://github.com/qte77/analyze-stock-kpi/issues/9) —
  regime-split returns sub-issue (deferred)
- [#10](https://github.com/qte77/analyze-stock-kpi/issues/10) —
  long/short ranking + CLI sub-issue (deferred)
- [#55](https://github.com/qte77/analyze-stock-kpi/issues/55) — RS
  alternatives survey (closed by this ADR)
- [ADR-0002](0002-simplified-composites.md) — precedent for trimming
  formula complexity that does not earn its keep
- [AGENTS.md](../../AGENTS.md) — project's single-purpose-CLI scope
  statement
