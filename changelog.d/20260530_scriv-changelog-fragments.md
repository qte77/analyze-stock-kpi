### Added

- **Changelog fragments via [scriv](https://github.com/nedbat/scriv).** Each PR now adds one small file under `changelog.d/` (created via `make changelog_new`) instead of editing `CHANGELOG.md` directly — eliminates the parallel-PR conflict on the `[Unreleased]` block that blocked PR #173 after #174 merged. `make changelog_preview` renders the assembled next-release entry without consuming fragments; `make changelog_release VERSION=X.Y.Z` collects them at release time before `bump-my-version`. `[tool.bumpversion]` no longer touches `CHANGELOG.md` — scriv owns it.
