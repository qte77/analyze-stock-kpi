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

- **Dashboard "Score" column on `aggregated-scores-best`/`aggregated-scores-worst` now
  shows and sorts by the aggregator's actual ranking metric (mean of the 7 composite
  scores), not `screener_score`.** Previously the column always displayed
  `screener_score`, one of the seven, while the best/worst split is decided by the mean
  of all seven — a ticker could rank in worst-25 by mean while showing a comparatively
  high `screener_score`, or vice versa (e.g. Clear Secure Inc. sitting in best-25 with a
  visibly low 47). The mismatch was previously only explained via a hover tooltip; now
  the displayed and sorted value is the actual ranking metric itself. Every other
  universe is unaffected.
