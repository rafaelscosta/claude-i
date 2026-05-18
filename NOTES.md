# claude-i — Operator Notes

Operator-facing notes that don't belong in committed source or stories.
Append-only; date every entry.

## Hook Matcher Support

**Investigation date:** 2026-05-17
**Investigator:** @dev (Dex) under STORY-001.1 Task 2.5
**Time spent:** ~15 minutes (cap was 90 min)
**Decision:** DEFER matcher addition — fall back to shell-guard-only.

### Sources consulted (in authority order)

1. `claude --help` and `claude hooks --help` — `claude --help` documents
   `--permission-mode` (confirming AC-1's flag choice). No `hooks`
   subcommand exists in the installed version, so no help text for it.
2. Local JSON schema search: `~/.claude/schema/` and
   `~/.claude/settings.schema.json` — neither file exists.
3. Existing `~/.claude/settings.json` on this dev machine — inspected
   programmatically. Findings:
   - `PreToolUse` groups use `matcher: "*"` (wildcard).
   - `PostToolUse` groups use `matcher: "*"`, `matcher: "Skill"`,
     `matcher: "Read"` — i.e. **tool-name regex / literal**.
   - `Stop` groups have NO `matcher` field — only `hooks`.
   - `SubagentStop` groups likewise have no `matcher`.
4. `~/.claude/commands/claude-code-mastery/hooks-architect.md` (the
   internal hooks reference): documents matchers as "regex matchers to
   narrow hook execution" and gives examples like `"Edit|Write"` — clearly
   **tool-name matching**, not arbitrary-condition matching. The Stop
   hook examples in the same file omit `matcher` entirely.

### Conclusion

The `matcher` field is supported for tool-event hooks (PreToolUse /
PostToolUse) where it filters by **tool name**. `Stop` is a session-level
event with no associated "tool" to match against, and the documented
Stop-hook schema has no `matcher` field. There is no documented schema
that would let us scope a Stop hook to fire only when `CLAUDE_I_SENTINEL`
is set; the closest thing — the shell guard `if [ -n "$CLAUDE_I_SENTINEL" ]`
inside `HOOK_CMD` — is already in the seed and remains the primary
isolation mechanism.

Hardcoding an unverified matcher schema for Stop would risk breaking
Claude Code's settings parsing on installs. Per @po's Task 2.5 decision
matrix, this maps to the **"Supported but schema undocumented for this
event" → DEFER** branch. AC-5's fallback clause covers it.

### What was implemented instead

- Tests/code accept both code paths (with and without a matcher field) —
  `hook_installed()` does a structural check that tolerates extra keys at
  the group level, and `install_hook()` writes the legacy format
  (matcher-less group) which is the documented Stop-hook shape.
- `hook_installed()` was tightened to look up entries inside the `Stop`
  list shape rather than the seed's loose string compare — this catches
  legacy malformed entries and is the foundation for any future matcher
  check.
- `install_hook()` was upgraded to APPEND to the existing `Stop` list
  (preserving any pre-existing hooks), not replace it — Task 2.7.

### What would need to change for a future story to revisit

1. Anthropic publishes a documented `matcher` (or equivalent scoping
   field) for `Stop` hooks — schema, allowed value types, semantics.
2. Or: Anthropic adds a new event type (e.g. `StopForSession`) that
   accepts a tool/session-name matcher.
3. At that point: extend `settings.HOOK_ENTRY` to include the matcher
   key, update `hook_installed()` Part B to verify it, update
   `install_hook()` to write it, and document the new field in this
   section.

Until then, the shell guard inside `HOOK_CMD`
(`if [ -n "$CLAUDE_I_SENTINEL" ]; then ...; fi`) is the sole and
sufficient isolation mechanism for the claude-i Stop hook.
