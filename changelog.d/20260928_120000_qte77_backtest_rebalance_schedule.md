### Fixed

- Backtest rebalance schedule (#446):
  - Series A's "weekly" cadence traded on every snapshot (three times on 2026-06-08). Its
    cadences now use at most one snapshot per ISO week.
  - A rebalance whose trade day can't be resolved yet now holds back later ones, instead of
    letting them trade against the older book.
  - The rebalance log lists one entry per trade day that matches what was simulated. Series B's
    weekly log had three duplicated days.
  - Series A is rebuilt once (`method_version` 2), and series B picks the fix up in its
    already-scheduled rebuild to `method_version` 3.
- The backtest caveats now say returns are total returns (split- and dividend-adjusted).
