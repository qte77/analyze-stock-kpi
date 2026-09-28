### Changed

- Series B's filing lag (D18) also treats a ticker as non-US (120 days instead of 90) when its
  Yahoo `country` in the latest demo snapshot is not the United States. The country can only
  lengthen the lag, never shorten it below the old suffix/known-list/ADR-shape rule. On the
  2026-09-27 data this moves 9 of 314 tickers to 120 days. `method_version` is now 3, so the next
  weekly `portfolio` run rebuilds series B once (#419).
