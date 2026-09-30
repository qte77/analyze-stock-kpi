### Fixed

- Backtest series A only schedules rebalances from ISO weeks that have ended. Before, a
  mid-week snapshot (e.g. a manual run on a Wednesday) could be frozen as that week's
  rebalance, and the week's Sunday snapshot would then add a second one. The weekly cron
  snapshots on Sundays, so normal runs pick each week up at the same time as before, and the
  frozen history already matches this rule (no rebuild).
