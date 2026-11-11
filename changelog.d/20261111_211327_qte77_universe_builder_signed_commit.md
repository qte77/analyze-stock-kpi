### Fixed

- Universe preset PRs can be merged again: `universe-builder.yaml` commits the preset refresh
  through the Git Data API (reusing `scripts/data-branch-commit.cjs`), so GitHub signs it. The old
  local `git commit` was unsigned, which the `required_signatures` ruleset rejects.
