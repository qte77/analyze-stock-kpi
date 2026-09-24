<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Added

- A bullet item for the Added category.

-->
<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
<!--
### Removed

- A bullet item for the Removed category.

-->
### Fixed

- **Aggregated/derived-universe display lists (`aggregated-scores-{best,worst}`,
  `enhanced-kpi-screener-{longs,shorts}`) no longer re-fetch data independently of the
  ranking/classification pass that built them.** `demo-snapshot.yaml` treated these four
  presets as ordinary universes and re-fetched fresh yfinance data for them, so a
  ticker's displayed qte77 Score could disagree with the score it was ranked by (e.g. a
  worst-list ticker outscoring a best-list one). `universe-builder.yaml`'s build scripts
  now write each preset's `results/demo/<preset>/<date>.json` display snapshot directly
  from the exact `FundamentalsSnapshot` records they ranked/classified
  (`ranked_snapshots`); `demo-snapshot.yaml` excludes these `"derived": true` universes
  from its own fan-out and dispatch choices.
- **The dashboard's backtest section no longer shows point-in-time-scored (`score_bt`)
  candidates as "today's" long/short book.** It now reads the `aggregated-scores-best`/
  `-worst` demo snapshots directly (full, live qte77 Score) for its "Current candidates"
  panel; `results/backtest/lists/*.json` remains a purely historical backfill, unchanged
  and still ranked by `score_bt` for the historical chart/metrics simulation (ADR-0014
  amends ADR-0013 D2 accordingly).
<!--
### Security

- A bullet item for the Security category.

-->
