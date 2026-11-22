### Added

- `portfolio.yaml` can restore and save the backtest's `results/prices/` cache from the private repo
  `qte77/__analyze-stock-kpi-cache` (#418), so statement history outlives yfinance's ~4-5 fiscal-year window.
  It is dormant until the `CACHE_REPO_SSH_KEY` secret (a write-enabled deploy key on that repo) exists;
  without it the run is unchanged. Nothing from the cache reaches the public `data` branch.
