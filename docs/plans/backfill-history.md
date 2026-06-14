# Plan — Backfill F&G long-term + 5s10s history

Issue [#287](https://github.com/qte77/analyze-stock-kpi/issues/287) · status: proposed.

## Context

History is shallow: CNN F&G long-term goes back only to **2025-05**, the 5s10s slope to
**2025-02**. Deeper history makes the long-term-context + slope charts (and the merged
chart, [merge-longterm-charts](merge-longterm-charts.md)) far more useful.

## Approach

Extend each per-year series on the `data` branch as far back as the upstream source
exposes, using the existing backfill paths — no schema change.

## Steps

1. **CNN F&G** — extend `results/cnn_fg/YYYY.json` earlier than 2025-05 via
   `src/analyze_stock_kpi/data_sources/sentiment_backfill.py`; verify CNN's API horizon.
2. **5s10s / yield curve** — extend `results/yield_curve/…` earlier than 2025-02 via
   `src/analyze_stock_kpi/data_sources/yield_curve.py`; verify the source horizon.
3. One-off backfill run, committed to `data` via the verified-commit path; the
   daily/weekly crons keep it current going forward.

## Open questions

- How far back does each source actually expose (CNN graphdata; the yield source)?
- Per-year file shape unchanged, so confirm no schema/loader work is needed.

## References

- [#287](https://github.com/qte77/analyze-stock-kpi/issues/287); unblocks [merge-longterm-charts](merge-longterm-charts.md).
- `src/analyze_stock_kpi/data_sources/{sentiment_backfill,yield_curve}.py`; `.github/workflows/{fear-greed,yield-curve}.yaml`.
