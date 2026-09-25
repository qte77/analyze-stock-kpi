### Changed

- Series B's filing lag (D18) now uses each ticker's Yahoo `country` from the latest demo
  snapshot: 90 days for "United States", 120 days otherwise. A ticker with no country falls
  back to the old suffix/known-list/ADR-shape rule. `method_version` is now 3, so the next
  weekly `portfolio` run rebuilds series B once (#419).
