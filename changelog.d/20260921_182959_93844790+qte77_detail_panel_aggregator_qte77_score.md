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

- **Row detail panel's "qte77 Score" now matches the table's Score column on
  `aggregated-scores-best`/`aggregated-scores-worst`.** Follow-up to the table Score
  fix: the detail panel (opened by clicking a row) had the same `screener_score`-only
  bug — it always showed `screener_score` regardless of universe, so it could disagree
  with the table's own Score cell for the same ticker on aggregator universes. Now
  reuses `effectiveScore()` from the table, with an updated tooltip explaining the mean
  is the aggregator's actual ranking metric. Every other universe is unaffected.
