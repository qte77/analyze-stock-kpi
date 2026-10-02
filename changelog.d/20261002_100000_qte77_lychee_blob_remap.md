### Fixed

- CI link check: github.com file links (`/blob/`) are checked on `raw.githubusercontent.com`,
  because github.com answers 503 to the CI crawler for file pages (since 2026-10-02; other
  github.com links unaffected). A missing file still fails the check.
