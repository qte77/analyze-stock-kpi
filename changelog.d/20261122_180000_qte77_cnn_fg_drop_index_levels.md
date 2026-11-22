### Fixed

- The CNN Fear & Greed series no longer stores the S&P 500 and VIX index levels (and their 125-day and
  50-day averages) that four sub-indicators carry as `raw_value`; their score and rating stay. Rows loaded
  from older year files are scrubbed too, so the next cron run rewrites the 2025 and 2026 files on the `data`
  branch without them. See the ADR-0011 amendment of 2026-11-22.
