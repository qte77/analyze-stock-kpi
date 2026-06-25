### Added

- **Forks that enable Pages now self-host their own `data` branch.** The dashboard
  derives `DATA_BASE_URL` from the Pages origin (`<owner>.github.io/<repo>` →
  that owner/repo's `data` branch) via a new pure `ui/lib/data.js`; `?base=` still
  overrides, and the canonical qte77 deploy is unchanged. Prior art: the sibling
  `agentic-job-offer-to-application-kit` dashboard.
