### Fixed

- Backtest rebalance schedule (#446):
  - Series A's "weekly" cadence traded on every snapshot (three times on 2026-06-08). Its
    cadences now use at most one snapshot per ISO week.
  - Trades are now filled by walking the calendar. Each day the newest decision fills on the
    first day all its names and the held names trade, and it replaces any older decision still
    waiting. Before, trade dates could go backwards (a newer book applied before an older one),
    and a waiting rebalance let the next one trade against the wrong book.
  - The rebalance log lists one entry per trade day that matches what was simulated. Series B's
    weekly log had three duplicated days. The null benchmark uses the same fill rule.
  - Series A is rebuilt once (`method_version` 2), and series B picks the fix up in its
    already-scheduled rebuild to `method_version` 3.
- The backtest caveats now say returns are total returns (split- and dividend-adjusted).
