### Added

- **5s10s US Treasury slope tab in the long-term-context panel (#165).** Daily cron (22:30 UTC) pulls yfinance `^TNX` − `^FVX` (percentage points) and commits per-year history to the `data` branch. New "Why these charts?" tab explains the timeframe choices. yfinance fetch is `wrap-degrade` per leg; both legs failing → no write.

### Changed

- **Demo: dashboard layout polish.** `#universe-header` rows all share a width (filter+CSV defines the max); `Universe:` prefix dropped (label now `aria-label`); chart-wrap rules collapsed into a grouped selector.
