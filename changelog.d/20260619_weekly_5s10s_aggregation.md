### Changed

- **5s10s slope chart de-noised to a weekly mean on the wide windows.** The
  yield-curve tab now aggregates the daily 10y−5y slope to an ISO-week mean for
  the 5y / 10y / all windows (1y stays daily), mirroring the F&G long-term
  monthly view so multi-year context reads as trend rather than noise. New pure
  `ui/lib/weekly.js` (`aggregateWeekly`); client-side only — no change to the
  `data`-branch `results/series/yield_curve/` files. (#308)
