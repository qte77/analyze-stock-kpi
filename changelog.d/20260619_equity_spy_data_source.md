### Added

- **`equity_spy` data source — SPY indexed-return series (#288).** New
  `analyze_stock_kpi.data_sources.equity_spy` fetches SPY (the SPDR S&P 500 ETF)
  via yfinance and emits a **derived rebased index** (`ret_indexed = close /
  epoch_close * 100`, epoch = first close ≥ 2011) — never the raw close and never
  the S&P 500 index level (ADR-0011). Same per-year `results/series/<kind>/`
  shape + wrap-degrade boundary as `yield_curve`. Backend only here; the
  data-branch backfill, the cron, and the merged-chart UI follow separately.
