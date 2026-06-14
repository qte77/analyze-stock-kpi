# Compound Learning

Prevent repeated mistakes by systematically promoting learnings.

## Before Solving a Problem

Check AGENT_LEARNINGS.md for prior art. If a matching pattern exists, apply it.

## Promotion Path

1. **1st occurrence** — fix inline, move on
2. **2nd occurrence** — add to AGENT_LEARNINGS.md (pattern + solution)
3. **3rd occurrence** — promote to a plugin's `rules/` in `claude-code-plugins`,
   bump the plugin version, and ship via PR. Consumers receive the rule on next
   plugin update.
4. **Recurring workflow** — extract to a plugin's `skills/` (reusable capability)

## When Promoting (step 3)

- Verify the root cause is the same across occurrences
- Write the rule as a constraint ("do X", "never Y"), not a narrative
- Reference the AGENT_LEARNINGS.md entry being promoted
- Remove or link the original entry to avoid duplication
- **Choose host plugin**: pick the existing plugin whose domain matches the
  rule; if none fits, create a minimal plugin (see `plugins/planning/` as
  scaffold)
- **Bump version**: update `version` in both
  `plugins/<name>/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` — both must match
- **Sync shared rules**: if the rule belongs in the cross-cutting
  `.claude/rules/` set, run `make sync` to propagate copies into
  `workspace-setup` and `workspace-sandbox`, then bump those plugins' versions
- **Cross-repo workflow**: when the learning surfaces in a consumer repo
  (qte77/qte77, polyforge, office-forge, etc.), open the promotion PR against
  `claude-code-plugins`, not against the consumer
