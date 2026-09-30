### Fixed

- The "Lint MD and Links" workflow failed with `startup_failure` on every run (#391). It now runs
  markdownlint and the lychee link checker in-repo, with no third-party actions (pinned
  versions, lychee's download checksum-verified), via the same `make lint_md` /
  `make lint_links` targets as locally. Its first online run found a dead link in ADR-0005
  (repointed) and root-relative links needing `--root-dir`.
