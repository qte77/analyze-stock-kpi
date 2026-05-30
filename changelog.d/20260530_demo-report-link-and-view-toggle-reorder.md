### Added

- **Demo: "File feature request or bug" link in the header.** Sits to the right of the theme picker, displays a GitHub-mark octicon (inline SVG, `currentColor` so it tracks the link colour across themes), opens the repo's `/issues/new` in a new tab. Closes the feedback loop for demo visitors who notice a data quirk or UX nit. Muted styling matches the theme-picker visual weight — feedback hatch, not a primary action.

### Changed

- **Demo: simple/detailed toggle moves below the filter + CSV row and adopts the form-control aesthetic.** It's a universe-level control, not a header-level one — pairing it with the filter and CSV actions reduces the cognitive load on the header and groups related controls together. Visual style now matches its sibling controls (4px radius + `--bg` background, same as `#export-csv`) instead of the prior pill-shaped header button. Label is descriptive of the action rather than just the destination state — "Show all KPI columns ↗" (when in essentials view) / "Show essentials only ←" (when in all-columns view). Mobile hide behaviour preserved (existing `@media (max-width: 767px)` rule keys off `#view-toggle` by id, not its container).
