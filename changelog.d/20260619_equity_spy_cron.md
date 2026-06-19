### Added

- **`equity-spy.yaml` daily cron (#288).** Recomputes the SPY indexed-return
  series and commits changed `results/series/equity_spy/YYYY.json` to the `data`
  branch via the shared verified-commit helper. Runs 23:00 UTC, staggered 30min
  after the yield-curve cron so the data-branch writers don't race the same ref.
  Mirrors `yield-curve.yaml` (same pinned action SHAs).
