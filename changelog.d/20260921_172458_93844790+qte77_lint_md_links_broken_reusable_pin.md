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

- **`lint-md-links.yml` was silently `startup_failure`-ing on every push and PR.** Its
  pinned `qte77/.github` reusable workflow revision (2026-04-27) referenced an invalid
  `actions/github-script` commit inside its conditional `notify` job — GitHub resolves
  every `uses:` in a reusable workflow's full job graph at startup, even for jobs an
  `if:` would skip at runtime, so that one bad pin failed the entire workflow. Re-pinned
  to `qte77/.github`'s current `main` HEAD, which already fixed that reference upstream.
