### Added

- **Relocated `llms.txt` under `ui/public/` and added `ui/public/robots.txt`
  with a `Content-Signal: ai-input=yes, ai-train=no` line (#361).** The
  GitHub Pages build only copies `ui/public/*` into the deployed site, so
  `docs/llms.txt` 404'd live even though it existed in source. The
  `qte77/gha-llms-txt-action` auto-generation step in
  `.github/workflows/llms-txt.yaml` now writes directly to
  `ui/public/llms.txt` via the action's `output_path` input, keeping the
  file a single generated source of truth rather than a hand-maintained
  duplicate.
