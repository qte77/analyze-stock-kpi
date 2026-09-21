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

- **`universe-builder.yaml` now triggers on `demo-snapshot`'s completion instead of its
  own independent cron.** The two workflows' schedules raced: `universe-builder` fired at
  Sunday 02:00 UTC, a full 4h15m *before* `demo-snapshot`'s 06:15 UTC snapshot refresh, so
  the `aggregated-scores-best`/`-worst` and `enhanced-kpi-screener-longs`/`-shorts` legs
  (which read `results/demo/<universe>/` from the `data` branch) were always ranking
  against the *previous* week's data by construction. Switching to a `workflow_run`
  trigger keyed to `demo-snapshot`, guarded to skip on a failed/cancelled upstream run,
  removes the race entirely.
