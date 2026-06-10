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

**Status:** completed by the public `v0.2.4` release. The formula
`Formula/claude-i.rb` in `rafaelscosta/homebrew-claude-i` now points at the
canonical PyPI sdist for `claude-i 0.2.4`.

**Dev-pass artifact:**
- URL: `https://github.com/rafaelscosta/claude-i/releases/download/v0.2.0-pre/claude_i-0.2.0.tar.gz`
- SHA256: `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`

**Completion evidence:**
- PyPI sdist URL: `https://files.pythonhosted.org/packages/eb/e1/77672eeb8eace8dfe7b272a1226c4ae1b558aed2bd6715c682fed0c69508/claude_i-0.2.4.tar.gz`
- SHA256: `ca0a6575917f945fa6cb09c858130c0ae6094500500b70d7ffd9789219c3b9dc`
- Homebrew tap PR: `rafaelscosta/homebrew-claude-i#1`
- Validation: `brew audit`, `brew reinstall --build-from-source`, `brew test`,
  `claude-i --version`, and `claude-i doctor --json` all passed for `0.2.4`.

Full procedure documented in `docs/guides/homebrew-tap.md` § Release Update Procedure.


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

### Completed public-release paths

The public distribution surfaces are active as of `v0.2.4`:

- **PyPI** — `pipx install claude-i` / `uv tool install claude-i`.
- **Homebrew tap** — `brew install rafaelscosta/claude-i/claude-i`.
- **One-line bootstrap** — `curl -fsSL .../install.sh | bash`.

### Completed operator checklist — public release

The public-release checklist was completed across the v0.2.3 and v0.2.4
release work:

1. **Flip repo visibility:** `gh repo edit rafaelscosta/claude-i --visibility public --accept-visibility-change-consequences`.
   - Verify: `gh repo view rafaelscosta/claude-i --json visibility` → `"public"`.
   - Once flipped, `raw.githubusercontent.com/.../install.sh` returns 200 to anonymous.
2. **Configure PyPI Trusted Publisher:** completed for Project `claude-i`,
   Owner `rafaelscosta`, Repo `claude-i`, Workflow `publish.yml`,
   Environment `publish`.
3. **Create GitHub Environment `publish`:**
   - `gh api repos/rafaelscosta/claude-i/environments/publish --method PUT`
   - Add required reviewer (yourself) for a manual approval gate.
4. **Trigger PyPI publish:** completed for `v0.2.4`; workflow run
   `27287413340` succeeded after the `publish` environment approval.
5. **Capture canonical PyPI URL + SHA256:** completed from the public PyPI JSON.
6. **Update Homebrew formula:** completed in `rafaelscosta/homebrew-claude-i#1`;
   local Homebrew install/test passed for `0.2.4`.
7. **Cleanup pre-release:**
   - `gh release delete v0.2.0-pre --cleanup-tag -R rafaelscosta/claude-i`
   - This removes the dev-pass artifact once the canonical PyPI URL is live.
8. **Update homebrew-claude-i README:** completed in tap PR #1.
9. **Update claude-i README:** completed; public install matrix is active.

### v0.2.0 Release artifact checksums (canonical for this distribution phase)

- `claude_i-0.2.0-py3-none-any.whl` — SHA256
  `ee6a455efd90b279114eb460030d9c96ac83a0119b39621ae837b3c709268e10`
- `claude_i-0.2.0.tar.gz` — SHA256
  `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`

These match the wheel and sdist uploaded to the v0.2.0 GitHub Release.
The sdist SHA also matches the `v0.2.0-pre` dev-pass artifact referenced
in the homebrew-claude-i `Formula/claude-i.rb` `url` field (intentional —
same tarball content).


## IP Status — Public Release (effective 2026-05-19)

**Decision (operator, 2026-05-19):** IP-lock REVERSED. claude-i is published publicly.
- Repository: PUBLIC (flipped 2026-05-19)
- PyPI publication: LIVE — first Trusted Publisher release published as v0.2.4
- Current public release: v0.2.4 (2026-06-10)
- Public Homebrew formula: LIVE — `rafaelscosta/homebrew-claude-i` formula points at the canonical PyPI v0.2.4 sdist

**Rationale for reversal:** v0.2.2 reached production-ready automation reliability (STORY-001.7 closed; 10/10 reliability test with `--retries 3`). v0.2.3 then fixed the long-prompt paste/Enter race and chat-title/SKIP misattribution discovered in real AIOX prompt use (STORY-001.8). The IP-protection rationale from 2026-05-18 (preserving leverage during development) no longer applies once the product is stable and useful.

**Public distribution paths now active:**
- `pipx install claude-i` (PyPI)
- `uv tool install claude-i` (PyPI)
- `brew install rafaelscosta/claude-i/claude-i` (Homebrew tap — v0.2.4 PyPI sdist)
- `pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.4/claude_i-0.2.4-py3-none-any.whl` (GitHub Release)
- `pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.4/claude_i-0.2.4.tar.gz` (GitHub Release sdist)
- `pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.4` (git tag)

**PyPI publication — release path:**

The `publish.yml` workflow is wired for Trusted Publishing via OIDC. PyPI
rejected a prior v0.2.2 dispatch with `invalid-publisher` because no Trusted
Publisher was registered. On 2026-06-10 the Pending Publisher was configured,
`v0.2.4` was dispatched, environment `publish` was approved, and run
`27287413340` completed successfully. Public PyPI JSON now reports
`claude-i 0.2.4` with:

- Wheel SHA256: `6f945ae1be8c77fed6db259e7fec3cef749a3aea77164c3ec1d51cf39274c8cb`
- Sdist SHA256: `ca0a6575917f945fa6cb09c858130c0ae6094500500b70d7ffd9789219c3b9dc`

Smoke tests passed with `pip`, `pipx run`, and `uvx`.

**Guard preserved (defense-in-depth):** The `publish.yml` workflow still requires the `confirm_release=I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE` string for any future dispatch. This prevents accidental re-publish of stale/wrong artifacts. The guard is procedural, not policy — it gates dispatch, not the decision.

**Historical record:** The 2026-05-18 "Private Forever" decision is preserved in git history (commit `08d3975` introduced the section; this commit replaces it). The reversal is intentional and operator-approved.

## STORY-001.7 / Bug 4 + Bug 5 — Payload-first extraction + --retries

**Date:** 2026-05-19
**Author:** @dev (Dex) closing STORY-001.7

### Bug 4 — ELIMINATED via payload-first extraction

The Stop hook payload from Claude Code 2.1.143+ contains
``last_assistant_message`` (the full final assistant response). The runner
now reads this field FIRST and skips the transcript JSONL parse entirely
on the happy path. Eliminates both Bug 4a (assistant message not flushed)
and Bug 4b (transcript file never written; observed ~60% of test runs).

Fallback to transcript parsing preserved for older claude-code versions.

### Bug 5 — Anthropic-side session hang under burst load

**Symptom:** ``claude-i: No Stop hook signal after 90s``. Sub-claude
process hangs during prompt processing; Stop hook never fires; payload
never written.

**Empirical pattern:**
- Single manual shell invocation: 10/10 succeed (~5s each).
- 10 sequential Python ``subprocess.run`` calls in tight loop: 4-6/10
  hit 90s timeout without producing output.
- Bug rate scales with invocation tightness.

**Root cause:** Cannot be eliminated at claude-i layer. Sub-claude
itself is unresponsive — no Stop hook signal of any kind. Likely upstream
Anthropic rate limiting or session-bootstrap latency under burst load.

**Mitigation:** ``--retries N`` (default 0). Each retry tears down the
hung tmux session via the existing reaper and spawns a fresh one. Test
data with ``--retries 3``: 10/10 success in pytest's reliability test.

**Operator guidance:**
- Interactive single-shot use: ``claude-i "<prompt>"`` (no flag needed).
- Automation / CI / scripts: ``claude-i --retries 3 "<prompt>"``. Each
  retry adds ~5-10s to worst-case latency; happy path is unaffected.
- High-burst pipelines: consider ``--retries 5`` and inject ``sleep 2``
  between successive ``claude-i`` invocations.
- STORY-001.11 updates the final stderr UX: when the terminal error contains
  ``No Stop hook signal``, the CLI now names documented Bug 5, suggests
  ``--retries 3`` for single-shot callers, suggests ``--retries 5`` plus
  pacing after exhausted retries, and points operators to ``claude-i doctor``.

### Integration test surface

- ``test_e2e_single_shot_smoke``: 1 invocation with ``--retries 0``.
  Always asserts Bug 1 / Bug 3b regression strings are absent.
  Does NOT assert exit 0 (Bug 5 absorption).
- ``test_e2e_reliability_with_retries``: 10 invocations with ``--retries 3``.
  Locks the automation-reliability contract — all 10 must succeed.
  If this test starts flaking, Bug 5 upstream rate has risen above the
  3-retry design point.

## STORY-001.8 / Bug 6 + Bug 9 — prompt delivery + chat-title misattribution

**Date:** 2026-05-20
**Author:** @dev (Dex) closing STORY-001.8

### Bug 6 — tmux paste/Enter race (FIXED)

The seed's `set-buffer + paste-buffer + send-keys Enter` delivers prompts
async to the TUI. For prompts >~40 chars, Enter landed before the paste
completed → silent no-op, `AGT idle`, Stop hook never fired. Symptom:
`No Stop hook signal after Ns` for any non-trivial prompt.

Two-part fix:
1. `tmux send-keys -l <prompt>` — literal keystroke injection.
2. `_wait_for_pane_to_contain()` — poll capture-pane until a 24-char prompt
   suffix is visible, THEN dispatch Enter.

### Bug 9 — Stop hook fires TWICE (FIXED)

claude-code 2.1.143 fires the Stop hook twice per prompt:
- 1st fire: title-generation artifact (`"Chat: X"`, `"Docs: Y"`, `"SKIP"`, ...)
- 2nd fire (5-15s later): the real assistant response

v0.2.2 returned the first fire → users got `"SKIP"` / chat-titles instead
of answers. Fix: `_looks_like_chat_title()` (generic `^[A-Z][a-zA-Z0-9]*: [A-Z]`
single-line ≤60-char shape + literal `SKIP`) drops title fires; the wait
loop keeps polling for the real response within `--timeout`.

### Empirical validation (2026-05-20, real claude)

- 70-char prompt: 7s, full Rayleigh answer (was timeout).
- `@analyst` 125-char: 23s, full Atlas risk analysis (was `"SKIP"`).
- `/idea` slash skill: 49s, skill executed + wrote `docs/inbox/ideas.md` (was `"SKIP"`).
- 10× math single-shot: 10/10, 0 chat-title contamination.

### Host-saturation caveat (Bug 5 amplification)

After a long test bench, host load average climbs (22+ observed) and Bug 5
(Anthropic burst hang) becomes very aggressive — even mid-length prompts
time out across all `--retries`. This is environmental, not a claude-i
regression. The `/idea` integration test skips (not fails) under this
condition. Re-run on an idle host to see the green path. Production
mitigation remains `--retries 3`.

## STORY-001.12 / GitHub Actions Node 24 hardening

**Date:** 2026-06-10
**Author:** @devops (Gage) closing STORY-001.12

### Node.js 20 action runtime deprecation (FIXED)

Post-merge CI for STORY-001.10 and STORY-001.11 passed, but GitHub Actions
annotated every job that used `actions/checkout@v4` and
`actions/setup-python@v5` with the Node.js 20 runtime deprecation warning.
This was environmental/release-infrastructure drift, not an application
failure.

Resolution:
- `actions/checkout@v4` -> `actions/checkout@v5`
- `actions/setup-python@v5` -> `actions/setup-python@v6`
- Fedora smoke container `fedora:latest` -> `registry.fedoraproject.org/fedora:latest`
  after repeated Docker Hub pull timeouts during PR validation.

Scope:
- `.github/workflows/ci.yml`
- `.github/workflows/smoke.yml`
- `.github/workflows/publish.yml`

The publish workflow remains `workflow_dispatch`-only and guarded by the
existing confirmation string plus `environment: publish`. PyPI publication is
live; future releases should reuse the same Trusted Publisher and environment
gate.
