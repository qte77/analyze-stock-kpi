### Added

- **Governance for the #288 equity-macro overlay (ADR-0011).** Records the
  decision to source the equity line from **SPY** (an ETF security, not the S&P
  Dow Jones index) and commit only a **derived indexed-return** series — never
  raw index levels — keeping it at the same redistribution tier as the existing
  `yield_curve` slope. Adds a `docs/data-sources.md` guardrail row and a repo
  `NOTICE` recording the non-commercial/educational, derived-data posture and
  the upstream ToS. (#288)
