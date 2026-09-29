### Fixed

- The weekly `portfolio` backtest run now fails if it can't check out its inputs from the `data`
  branch. Before, it silently fell back to "first run": it recomputed and overwrote frozen
  history, or ran a one-time `method_version` rebuild without the demo snapshots (no countries,
  no series A).
