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


## STORY-001.5 — G14 SubagentStop Deferred

**Status:** G14 (SubagentStop hook event handling) is **DEFERRED** from
STORY-001.5 — the field name that would distinguish `SubagentStop` from
`Stop` is not publicly documented in Anthropic's hook payload schema as
of 2026-05-18 (`claude-code` CLI 2.1.x).

### What was investigated
- `claude-code` source on GitHub: no public reference to `SubagentStop`
  event in user-facing docs (docs.claude.com/claude-code).
- Hook payload structure in `transcript_path` JSONL events: only
  `Stop` events appear; subagent boundaries are implicit (via tool_use
  blocks for Task tool).
- Empirical test on `claude-code` 2.1.143: a Task subagent invocation
  fires Stop hook with payload containing `transcript_path` pointing
  at the parent transcript — no distinct `SubagentStop` event observed.

### What was implemented
- Nothing for `SubagentStop` per se — there's no signal to gate on.
- Existing `Stop` handler (from STORY-001.0 seed) continues to work for
  both top-level and subagent-containing transcripts; the last
  assistant message in the transcript is the right thing to extract
  regardless of subagent nesting.

### When to revisit
1. Anthropic publishes documented `SubagentStop` event with payload
   schema (search docs for `SubagentStop` keyword).
2. Empirical test shows distinct `SubagentStop` payload (rerun
   `claude-i -v "use Task to spawn subagent"` and inspect transcript).
3. At that point: add `hook.handle_subagent_stop()` + tests, update
   this section.

Reference: STORY-001.5 Task 6.7 (deferred), AC-8 (G14 tests acknowledge
deferral via `tests/test_hook.py::test_subagent_stop_deferred` marker).


## Private Distribution Phase (2026-05-18)

**Status:** `claude-i` repo remains PRIVATE post-`v0.2.0`. The canonical install
asset for collaborators with read access is the GitHub Release v0.2.0:
https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.0

### Active install paths (private repo)

1. `pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.0`
   (requires `gh auth login` or `GH_TOKEN`/`GITHUB_TOKEN` with `repo` scope)
2. `gh release download v0.2.0 --pattern '*.whl' -R rafaelscosta/claude-i && pipx install ./claude_i-0.2.0-py3-none-any.whl`
3. `gh release download v0.2.0 --pattern '*.tar.gz' -R rafaelscosta/claude-i && uv tool install ./claude_i-0.2.0.tar.gz`

### Deferred (public-release paths)

The following install surfaces are wired in code but inert until the repo
flips public:

- **PyPI** — `pipx install claude-i` / `uv tool install claude-i`. Blocked
  on running `gh workflow run publish.yml --ref v0.2.0` against a public
  repo with the `publish` GitHub Environment + PyPI Trusted Publisher
  (`pending_publisher`) configured.
- **Homebrew tap** — `brew install rafaelscosta/claude-i/claude-i`. Blocked
  on STORY-001.4 Task 5.9 (canonical PyPI URL + SHA256 in
  `Formula/claude-i.rb`). The current formula at
  `rafaelscosta/homebrew-claude-i@main` points at a dev-pass URL
  (`v0.2.0-pre` GitHub release) — works locally, NOT for strangers.
- **One-line bootstrap** — `curl -fsSL .../install.sh | bash`. The
  `raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh` URL
  returns 404 to anonymous fetches while the repo is private.

### Operator checklist — enable public release

When the decision is made to go public, run these steps in order:

1. **Flip repo visibility:** `gh repo edit rafaelscosta/claude-i --visibility public --accept-visibility-change-consequences`.
   - Verify: `gh repo view rafaelscosta/claude-i --json visibility` → `"public"`.
   - Once flipped, `raw.githubusercontent.com/.../install.sh` returns 200 to anonymous.
2. **Configure PyPI Trusted Publisher (pending):**
   - PyPI account → Account → Publishing → Add a pending publisher
   - Project name: `claude-i`, Owner: `rafaelscosta`, Repo: `claude-i`,
     Workflow: `publish.yml`, Environment: `publish`
3. **Create GitHub Environment `publish`:**
   - `gh api repos/rafaelscosta/claude-i/environments/publish --method PUT`
   - Add required reviewer (yourself) for a manual approval gate.
4. **Trigger PyPI publish:**
   - `gh workflow run publish.yml --ref v0.2.0 -R rafaelscosta/claude-i`
   - Approve the `publish` environment gate when prompted.
   - Verify: `pip download claude-i==0.2.0 -d /tmp/pypi-verify --no-deps`
5. **Capture canonical PyPI URL + SHA256:**
   - `shasum -a 256 /tmp/pypi-verify/claude_i-0.2.0.tar.gz`
   - Note `files.pythonhosted.org` URL from `pip download -v` output.
6. **Update Homebrew formula** (STORY-001.4 Task 5.9):
   - Edit `rafaelscosta/homebrew-claude-i:Formula/claude-i.rb` →
     replace `url` + `sha256` with PyPI canonical values.
   - `brew untap rafaelscosta/claude-i && brew tap rafaelscosta/claude-i`
   - `brew install --force claude-i && brew test claude-i` on clean macOS.
   - Commit + push tap.
7. **Cleanup pre-release:**
   - `gh release delete v0.2.0-pre --cleanup-tag -R rafaelscosta/claude-i`
   - This removes the dev-pass artifact once the canonical PyPI URL is live.
8. **Update homebrew-claude-i README** — remove "PENDING UPSTREAM PUBLICATION"
   section, re-enable the simple `brew tap / brew install` matrix.
9. **Update claude-i README** — collapse the "Private Repo" section back
   into the public install matrix (Homebrew + pipx + uv + curl bootstrap).

### v0.2.0 Release artifact checksums (canonical for this distribution phase)

- `claude_i-0.2.0-py3-none-any.whl` — SHA256
  `ee6a455efd90b279114eb460030d9c96ac83a0119b39621ae837b3c709268e10`
- `claude_i-0.2.0.tar.gz` — SHA256
  `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`

These match the wheel and sdist uploaded to the v0.2.0 GitHub Release.
The sdist SHA also matches the `v0.2.0-pre` dev-pass artifact referenced
in the homebrew-claude-i `Formula/claude-i.rb` `url` field (intentional —
same tarball content).


## IP Status — Private Forever (as of 2026-05-18)

**Decision (operator, 2026-05-18):** claude-i is IP-protected.
- Repository: PERMANENTLY PRIVATE
- PyPI publication: PERMANENTLY FORBIDDEN
- Public Homebrew formula: PERMANENTLY FORBIDDEN
- The `publish.yml` workflow remains in the repo but is guarded by a required confirmation string that makes accidental dispatch impossible.

**Reason:** Code contains IP that must not be exposed publicly. The sdist artifact (which PyPI publishing produces) contains `src/` and would constitute a leak.

**Distribution path that respects IP status:**
- GitHub Release v0.2.0 with .whl + .tar.gz assets (private repo — only collaborators with read access can download)
- `pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.0` (gh CLI authenticated)

**Technical enforcement in place:**

1. **`publish.yml` confirm_release input** — `workflow_dispatch` requires the exact 49-character string `I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE`. Empty or wrong values fail the first step before any build/publish runs. Validated 2026-05-18.
2. **GitHub `publish` environment** — created 2026-05-18 via `gh api`, restricted via `deployment_branch_policy` to `main` branch and `v*.*.*` tags only. Required reviewers not available on Free plan for private repos; the input guard compensates.
3. **No `push: tags` trigger** — deliberately omitted from `publish.yml`. Tag-triggered dispatch would have no `inputs.confirm_release` to validate and would bypass the guard. Re-introducing it requires updating this section first.
4. **NOTES.md visibility** — this section is the source of truth read by both operator and any future @devops agent before invoking publish.

**Conditions to reverse this decision:**

The IP-protected status is set by operator (rafaelscosta). To unlock public distribution:
1. Operator explicitly updates this section with a new decision date + rationale.
2. Operator runs `gh workflow run publish.yml --ref v0.2.0 --field confirm_release=I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE`.
3. Operator configures PyPI Pending Publisher (see § Private Distribution Phase § Operator checklist).
4. Operator flips repo to PUBLIC (optional but recommended for transparency).

This section is the source of truth. The workflow guard is the technical enforcement.
