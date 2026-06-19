### Changed

- **Merged long-term-context chart (#288).** The "CNN F&G long-term" and "5s10s
  slope" tabs collapse into one "Long-term context" chart: the F&G monthly median
  and the 5s10s monthly mean (normalized to 0-100) share the left axis, and the
  **SPY indexed return** sits on a **logarithmic right axis**. All three reconcile
  onto one monthly grid via the new pure `ui/lib/combined.js`
  (`normalizeSlope` / `aggregateMonthly` / `buildCombinedSeries`) +
  `logRightAxis` in `ui/lib/chart_axes.js`. SPY is the derived `equity_spy` series
  on the `data` branch (ADR-0011, never raw index levels).
