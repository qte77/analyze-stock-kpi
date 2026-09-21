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
<!--
### Fixed

- A bullet item for the Fixed category.

-->

### Security

- **Remove `[tool.uv].exclude-newer` dependency-resolution cap and bump 4 vulnerable
  transitive packages.** The cap (pinned to 2026-06-20) was blocking `uv lock` from ever
  resolving the patched versions of 8 open Dependabot alerts (1 critical, 2 high, 5
  moderate) since those fixes were published after the cap date. Bumped `anyio`
  4.13.0 → 4.14.2 (GHSA-82r6-8w77-94w6, GHSA-5p39-cfhj-2xmp), `soupsieve` 2.8.4 → 2.9.2
  (GHSA-gjv8-xp57-g29c, GHSA-j934-xhv5-fg8f), `httpx2` / `httpcore2` (transitive via
  `bump-my-version`) 2.4.0 → 2.13.0 (GHSA-8xx6-hgc6-gc2m, GHSA-h4x7-gw46-3wm6,
  GHSA-pf96-p4fj-6566, GHSA-7mj9-2mp8-4m2p).
