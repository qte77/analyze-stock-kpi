### Added

- `FundamentalsSnapshot` now stores `country` from yfinance `info` (e.g. "United States",
  "Taiwan"), so every demo snapshot carries it. The backtest's filing-lag rule reads it
  (#419).
