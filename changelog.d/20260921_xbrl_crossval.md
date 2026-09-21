### Added

- **SEC XBRL cross-validation of yfinance fundamentals.** New
  `src/analyze_stock_kpi/data_sources/sec/xbrl.py` fetches SEC XBRL `companyconcept` revenue,
  net-income, and basic-EPS facts and cross-validates them against the matching yfinance
  values, attaching `sec_revenue_delta_pct` / `sec_net_income_delta_pct` / `sec_eps_delta_pct`
  to every `FundamentalsSnapshot`. `total_revenue` / `net_income_to_common` are promoted to
  permanent snapshot fields; foreign filers and non-SEC-registered symbols skip gracefully
  (all three delta fields stay `None`). Closes #101.
