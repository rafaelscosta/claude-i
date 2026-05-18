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


## v0.2.0 Release Tag — Deferred to Epic Close

STORY-001.3 bumped the package to `0.2.0` (no `.dev0` suffix) but does
NOT push a `v0.2.0` git tag. The tag is deliberately deferred to the
final closure of EPIC-001 (after STORY-001.5 lands).

Rationale: a tag-triggered PyPI publish workflow is a one-shot event —
the same tag cannot fire it twice. STORY-001.4 (Homebrew formula,
install.sh, 3-OS smoke CI) and STORY-001.5 (doctor/uninstall/reap
subcommands, --output-format json, readiness polling, G14/G17 tests)
will land on `main` between now and release without bumping the version
again. The `v0.2.0` tag is created and pushed in ONE atomic operation
at the end of the epic, with a clean release notes pointing at the
final `main` SHA.

Publish workflow (`.github/workflows/publish.yml`) is `workflow_dispatch`
only for now — manual `gh workflow run publish.yml` after the tag lands.
This gives the operator a human gate without GitHub Environments
ceremony.


## STORY-001.4 — Homebrew Formula URL Finalization Deferred

**Status:** STORY-001.4 lands the formula `Formula/claude-i.rb` in
`rafaelscosta/homebrew-claude-i` with a **dev-pass URL** pointing at a
GitHub pre-release sdist (`v0.2.0-pre`). The canonical PyPI
`files.pythonhosted.org` URL is **not yet wired** because:

1. `v0.2.0` git tag is intentionally deferred (see section above).
2. `publish.yml` has not run, so the package is not on PyPI.

**Dev-pass artifact:**
- URL: `https://github.com/rafaelscosta/claude-i/releases/download/v0.2.0-pre/claude_i-0.2.0.tar.gz`
- SHA256: `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`

**Finalization checklist** (executed at epic close, per STORY-001.4 Task 5.9):
1. Tag and push `v0.2.0`.
2. Run `gh workflow run publish.yml` and approve the `publish` environment gate.
3. Capture canonical PyPI URL + SHA256 via `pip download`.
4. Update `Formula/claude-i.rb` `url` + `sha256`.
5. `brew untap` / `brew tap` / `brew install` / `brew test` cycle on clean macOS.
6. Commit + push the tap.
7. Optionally `gh release delete v0.2.0-pre --cleanup-tag` to remove the pre-release.

Full procedure documented in `docs/guides/homebrew-tap.md` § Epic-Close Finalization.
