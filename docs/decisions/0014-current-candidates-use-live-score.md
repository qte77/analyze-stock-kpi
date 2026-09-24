# ADR-0014 — Aggregated / long-short candidate lists reuse source-universe data; only the historical backfill stays point-in-time

**Status:** Accepted (2026-09-24) · **Amends in part** [ADR-0013](0013-point-in-time-backtest.md) (D2 —
narrows the reduced point-in-time score's role) · **Relates to:** [ADR-0005](0005-sentiment-risk-sources.md)
§"NOT a hedging primitive", [ADR-0007](0007-package-vs-infrastructure-boundary.md) (package vs
repo-infrastructure boundary — `scripts/` writes, `orchestrators/` computes).

## Context

Two related defects surfaced together on 2026-09-24:

1. **Aggregated / derived-universe display used a second, independent fetch.**
   `aggregated_scores_best_and_worst.build_universe` and `enhanced_kpi_screener_longshort.build_universe`
   rank/classify tickers from the seven base universes' `results/demo/<u>/` snapshots, then write a
   *preset* `.txt` (ticker list only). `.github/workflows/demo-snapshot.yaml` treated the four derived
   presets (`aggregated-scores-{best,worst}`, `enhanced-kpi-screener-{longs,shorts}`) as ordinary
   universes and re-fetched fresh yfinance data for them via `make run UNIVERSE=<preset>` (`__main__.py`
   → `fetch_universe_fundamentals` → `compute_scores`), independently and at a different fetch time than
   the ranking pass. A ticker's displayed `screener_score` in the aggregated/derived list could therefore
   disagree with the score its source universe showed for the same nominal snapshot date — observed live
   on the `data` branch: `results/demo/aggregated-scores-{best,worst}/2026-09-22.json` vs. the
   universe-builder ranking audit `results/audit/aggregated_scores_best_and_worst/2026-09-23.json`, where
   a worst-list ticker (BAYN.DE, 60.96) outscored a best-list ticker (YOU, 47.75).
2. **The backtest's "current candidates" display used the point-in-time score.** ADR-0013 D2 defined one
   reduced score (`score_bt`, six point-in-time-reconstructable inputs) for "both the backfill and the
   cron." `ui/app.js` rendered `results/backtest/lists/YYYY.json`'s most recent entry — ranked by
   `score_bt` — as the dashboard's "current" long/short book, alongside the same-named aggregated
   best/worst lists that use the full, live `screener_score`. Two different scores, same nominal concept.

Owner instruction (2026-09-24, verbatim): *"the aggregated lists should use the same data as the actual
original lists!"* and, extending to the backtest section: *"the aggregated and long/short candidates
lists have to just copy the best/worst candidates resp calculate the candidates using the same original
data!"* — today's candidates, wherever displayed, must never be a second, independently-scored pick.

## Decision

1. **No second fetch for derived universes (root fix).** `universe-builder.yaml`'s four derived-preset
   legs now write `results/demo/<preset>/<date>.json` + `index.json` directly, from the EXACT
   `FundamentalsSnapshot` objects `build_universe` ranked/classified
   (`aggregated_scores_best_and_worst.ranked_snapshots` / `enhanced_kpi_screener_longshort.ranked_snapshots`,
   `scripts/_demo_snapshot_loader._write_demo_snapshot`) — never a re-fetch. `demo-snapshot.yaml` excludes
   these four ids (`"derived": true` in `ui/public/universes.json`) from its own fan-out and
   `workflow_dispatch` choices. A ticker now shows the identical qte77 Score in the aggregated/derived
   list and in its source universe's own snapshot for the same date, and `min(best.screener_score) >=
   max(worst.screener_score)` holds by construction.
2. **The dashboard's "current candidates" panel is decoupled from the point-in-time backfill.**
   `ui/app.js`'s `loadCurrentAggregatedCandidates` sources the backtest section's "Current candidates"
   display from the `aggregated-scores-best`/`-worst` demo snapshots (decision 1's data — full, live
   `screener_score`) instead of `results/backtest/lists/*.json`'s latest entry. Long candidates = the
   `aggregated-scores-best` list; short candidates = `aggregated-scores-worst` — copied, not re-derived.
3. **`results/backtest/lists/*.json` stays a purely historical backfill.** Every entry, including the
   most recent rank date, continues to rank by the point-in-time-only `score_bt` (ADR-0013 D2, unchanged)
   — the file is written every Saturday exactly as before and remains internally consistent across its
   whole date range, but the dashboard no longer displays any entry from it as "today's" book. This
   **amends ADR-0013 D2**: the reduced score's role narrows from "both the backfill and the cron[-driven
   current display]" to "the historical backfill and the backtested returns simulation" — point-in-time
   reconstruction (`score_at`, `pit_fundamentals`) remains only where it is unavoidable: scoring *past*
   dates. `rank_dates`, `rebalance_dates`, `select`, `simulate`, `metrics` and the simulated gross/net
   returns are **unchanged** — the backtest's book still rebalances off the PIT-scored `ranked_by_date`
   because `forward_pe`/`trailing_peg_ratio`/`beta` cannot be reconstructed for a past date (ADR-0013's
   original premise, unaffected by this ADR).
4. **`enhanced-kpi-screener-longs/-shorts` keeps its own methodology.** It classifies via 15 long-side /
   14 short-side conjunctive gates over raw KPI fields (market cap, forward P/E, ROE, …) — it never
   ranked by `screener_score` and never used `score_at`. Its ONLY defect was decision 1's re-fetch (now
   fixed). It is **not** a subset of `aggregated-scores-best`/`-worst` by construction (a gate-passing
   pick and a top/bottom-25-by-score pick are different selections over the same data) — collapsing it
   into a copy of the aggregated lists was considered and rejected (see Alternatives). **Flagged for
   owner confirmation**, not assumed: if the owner wants `enhanced-kpi-screener-longs/-shorts` to
   literally equal or subset `aggregated-scores-best/-worst`, that is a methodology change beyond this
   ADR's scope and needs its own decision.

## Consequences

- A ticker shows one, identical qte77 Score everywhere it appears for a given snapshot date: its home
  universe, the aggregated best/worst lists, and the backtest section's current-candidates panel.
- The historical backfill/backtest chart, metrics table, null benchmark and fidelity check are
  byte-for-byte unaffected — same inputs, same `score_bt`, same simulation.
- `results/backtest/lists/*.json` is still written every Saturday but is no longer fetched by the
  dashboard; it remains available on the `data` branch for future analytical use (e.g. a "how did the
  point-in-time reduction track the live score" chart) — not built here (YAGNI).
- `universe-builder.yaml`'s four derived-preset legs now also pull their OWN prior `results/demo/<preset>/`
  history before running (mirrors `demo-snapshot.yaml`'s sparse-pull), so weekly demo-display dates
  accumulate instead of resetting to one date per run.

## Alternatives considered

- **Overwrite only the LATEST entry of `results/backtest/lists/YYYY.json` with a full-score-ranked
  entry each run:** rejected. `main()` is a full deterministic recompute (ADR-0013 D13); next Saturday
  the entry that was "latest" becomes historical and would need retroactive re-scoring with `score_bt`,
  breaking D13's idempotence and leaving one entry permanently on a different methodology than every
  other entry in the same file — an internally inconsistent time series.
- **Make `enhanced-kpi-screener-longs/-shorts` literally copy `aggregated-scores-best/-worst`:**
  rejected. It is a deliberately different, legitimate selection methodology (conjunctive gate vs.
  top/bottom-N by score); collapsing it into a copy would remove the feature's purpose. Its only real
  defect — the re-fetch — is fixed by decision 1 without touching its methodology.
- **Leave `results/backtest/lists`'s latest entry as the dashboard's current-candidates source, just
  relabel it:** rejected — the owner's requirement is that the *data*, not just the label, matches the
  aggregated best/worst lists (identical `screener_score` + KPI record), which `score_bt` cannot provide
  (it deliberately omits `forward_pe`/`trailing_peg_ratio`/`beta`).
