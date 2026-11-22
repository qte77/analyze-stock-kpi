### Added

- `analyze_stock_kpi.data_sources.options_oi` (plan 011): collects SPY option open interest for the nearest and the
  monthly expiry and derives max pain, call wall, put floor and put/call OI ratio into per-year
  `results/series/options_oi/YYYY.json`; raw chains go only to the gitignored private cache path.
