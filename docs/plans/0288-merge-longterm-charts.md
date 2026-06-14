# Plan 0288 — Merge long-term charts + SP500 overlay

Issue [#288](https://github.com/qte77/analyze-stock-kpi/issues/288) · status: proposed · depends on [0287](0287-backfill-history.md).

## Context

The long-term-context tab group has two separate charts — monthly CNN F&G and the
5s10s slope. Merge them into one chart and overlay **S&P 500 price on a log secondary
axis** for macro context.

## Approach

Collapse `renderMonthlyFearGreedChart` + `renderYieldCurveChart` (`ui/charts.js`,
wired by `bindLongTermTabs`) into a single Chart.js line chart with multiple datasets.
Reconcile the disparate scales: F&G is 0–100, 5s10s is bps/%, SP500 price spans orders
of magnitude (hence log).

## Steps

1. Add an **SP500 price** series: data source + backfill on the `data` branch
   (`results/sp500/…`) and a loader alongside the existing `lib/fetch.js` helpers.
2. New `renderLongTermCombined` in `ui/charts.js`; retire the monthly + yield tab panes.
3. Axes: F&G left (0–100); SP500 right (log). **Decide:** normalize 5s10s onto 0–100 to
   share the F&G axis, or add a third axis.
4. Window chips + the theme observer keep driving the combined chart.

## Open questions

- Two axes (normalize 5s10s) vs three axes (legibility cost on a small panel)?
- SP500 source — `^GSPC` via yfinance (consistent with the rest), on the data-branch cron?
- Does the F&G *rolling* (~1y) chart stay separate, or also fold in?

## References

- [#288](https://github.com/qte77/analyze-stock-kpi/issues/288); depends on [0287](0287-backfill-history.md) (deep history).
- `ui/charts.js` (`renderMonthlyFearGreedChart`, `renderYieldCurveChart`, `bindLongTermTabs`).
