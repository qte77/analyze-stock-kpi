### Changed

- Claude Code `.claude/settings.json` sets `BASH_MAX_OUTPUT_LENGTH` to `15000` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` to `50` ([env vars](https://code.claude.com/docs/en/env-vars)); `.claude/scripts/statusline.sh` is refreshed from claude-code-plugins 60388b9e: it shows context used and the autocompact point, and guards non-numeric input
