### Added

- **`publish-release.yaml` — opt-in GitHub Release publication (#208).** `tag-release.yaml` creates the annotated `v{version}` git tag on every bump merge but never published a Release object — the Releases page has stayed empty across every prior version. New `workflow_dispatch` workflow publishes a Release for an existing tag (defaults to the latest `v*`), extracting the matching `## [version]` block from `CHANGELOG.md` as release notes (falls back to `--generate-notes` when empty). Decoupled from `tag-release.yaml` so the auto path stays tag-only; operator opts in via `gh workflow run publish-release.yaml`.

### Changed

- **`bump-my-version.yaml` collects changelog fragments inside the workflow (#208).** Adds a `scriv collect --version $NEW` step after the version bump so the release PR carries `pyproject.toml` + README badge + `CHANGELOG.md` in one shot. Eliminates the "remember to run `make changelog_release` first" footgun documented in `pyproject.toml:142`. No-op when `changelog.d/` is empty (patch bumps without fragments still work).
