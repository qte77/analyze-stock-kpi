### Added

- **Demo: "Report" link next to the theme picker.** Opens the repo's GitHub issues page in a new tab — closes the feedback loop for demo visitors who notice a data quirk or UX nit. Muted styling matches the theme-picker visual weight (it's a hatch, not a primary action).

### Changed

- **Demo: simple/detailed toggle moves below the filter + CSV row.** It's a universe-level control, not a header-level one — pairing it with the filter and CSV actions reduces the cognitive load on the header and groups related controls together. Mobile hide behaviour preserved (existing `@media (max-width: 767px)` rule keys off `#view-toggle` by id, not its container).
