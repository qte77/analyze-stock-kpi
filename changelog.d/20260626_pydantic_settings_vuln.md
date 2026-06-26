### Security

- **Bump `pydantic-settings` 2.14.1 → 2.14.2 (GHSA-4xgf-cpjx-pc3j).** Patches a
  path-traversal / symlink-following issue in `NestedSecretsSettingsSource`
  (`secrets_nested_subdir=True`). Practical exposure here was nil — the app uses
  `BaseSettings(cli_parse_args=True)`, not the nested-secrets source — but the patch is
  trivial to ship. `[tool.uv].exclude-newer` rolled 2026-05-31 → 2026-06-20 so the patched
  release (2026-06-19) is reachable; no other package moved.
