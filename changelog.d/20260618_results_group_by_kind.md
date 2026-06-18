### Changed

- **Data-branch `results/` layout grouped by kind.** Per-year series moved to
  `results/series/{cnn_fg,yield_curve}/`; every per-universe audit JSON moved
  under `results/audit/<universe>/` (federal-contractors, aggregated-scores,
  enhanced-kpi-screener). Demo snapshots (`results/demo/`) and the universe
  audit (`results/audit/universes-*.json`) are unchanged. Config, the snapshot
  workflows, the demo loader, and docs all route through the new paths; the
  `data` branch is migrated in lockstep so the live demo never 404s. Plan:
  `docs/plans/restructure-results.md`.
