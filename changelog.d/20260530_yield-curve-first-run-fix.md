### Fixed

- **`yield-curve.yaml` cron silently skipped commit on first run.** `git status --porcelain` summarises untracked directories instead of enumerating their contents; the detect-step's awk regex then matched nothing and the workflow reported "no yield-curve history changes". `-uall` enumerates files inside untracked dirs so the first run writes to `data` branch as intended. Same `-uall` defensive fix applied to `fear-greed.yaml`.
- **Yield-curve first run now backfills 5 years of history** instead of writing only today's reading. `main()` detects an empty `results/yield_curve/` and calls the new `fetch_yield_curve_history(period="5y")`; subsequent daily runs continue to fetch just today's snapshot. Chart now paints something useful on first deploy.
