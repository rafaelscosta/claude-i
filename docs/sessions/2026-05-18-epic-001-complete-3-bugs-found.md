# claude-i v0.2.0 — Handoff completo (2026-05-18)

> Sessão de EPIC-001 completa em implementação, mas E2E real revelou **3 bugs reais** que impedem o uso de produção. Distribuição está pronta para teste interno mas NÃO para release.

## TL;DR (1 minuto)

- **Repos criados, sincronizados, pushed:** `rafaelscosta/claude-i` (private) + `rafaelscosta/homebrew-claude-i` (public)
- **EPIC-001 fechado:** 6/6 stories Done, 89/89 testes, todos os gates QA PASS (média 94.3/100)
- **GitHub Release v0.2.0:** wheel + sdist anexados, instaláveis via 3 paths
- **Bundle local para testers:** `/tmp/claude-i-share-bundle/claude-i-v0.2.0.{tar.gz,zip}` (54 KB cada, INSTALL.md + wheel + sdist + LICENSE)
- **🚨 E2E quebrado:** `claude-i "prompt"` falha em produção com `hook fired but no payload written`. Funciona o `--version`, `doctor`, `uninstall`, `reap`. Core flow NÃO funciona.
- **3 bugs documentados** (críticos/importantes) — precisam STORY-001.6 para fix antes de v0.2.1

**Próximo passo:** abrir STORY-001.6 para fixar Bug 1 (Stop hook race) + Bug 2 (G15 cleanup path) + Bug 3 (TTY detection). Bug 1 é o bloqueador.

---

## Parte 1: Estado VERIFICADO dos repos

### claude-i (PRIVATE)

- **URL:** https://github.com/rafaelscosta/claude-i (visibility: PRIVATE)
- **Local clone:** `/Users/rafaelcosta/Projects/AIOX/claude-i`
- **Branch:** `main`
- **HEAD:** `08d3975` (sync com `origin/main`, working tree limpo — verificado via `git status -sb`)
- **Tag:** `v0.2.0` pushada (aponta para `3d68eaf` — story-001.5 closure)

**Últimos 10 commits (mais recente primeiro):**

```
08d3975 chore(safety): publish.yml requires explicit confirmation string + NOTES IP lock [post-v0.2.0]
527c9db docs(notes): private distribution phase + public-release checklist [post-v0.2.0]
abd332e docs(readme): private-collab install paths via GitHub Release [post-v0.2.0]
fa800b2 docs(close): EPIC-001 → Implementation Done (release pending operator) [EPIC-001]
3d68eaf docs(close): STORY-001.5 → Done (doctor + uninstall + reap + json + readiness polling) [STORY-001.5]
b576070 docs(qa): STORY-001.5 re-gate PASS 95/100 [STORY-001.5]
e130d8f docs(qa): STORY-001.5 gate file (initial CONCERNS 80/100) + AC-3/AC-4 exit code clarifications [STORY-001.5]
36f6ad9 test(coverage): add 5 missing tests from QA review (Q-1/Q-2/Q-3 from gate) [STORY-001.5]
733be58 docs(story): mark STORY-001.5 implementation complete [STORY-001.5]
8e025b0 docs(notes): G14 SubagentStop deferred — undocumented Stop variant (Task 6.7) [STORY-001.5]
```

### homebrew-claude-i (PUBLIC)

- **URL:** https://github.com/rafaelscosta/homebrew-claude-i (visibility: PUBLIC)
- **Local clone:** `/Users/rafaelcosta/Projects/AIOX/homebrew-claude-i`
- **Branch:** `main`
- **HEAD:** `11a0d43` (sync, working tree limpo)

**3 commits:**

```
11a0d43 docs(readme): formula pending upstream public release [post-v0.2.0]
c7d6a9e feat(formula): claude-i.rb (dev-pass URL → epic-close finalizes)
4fc957e chore(scaffold): bootstrap homebrew-claude-i tap
```

**Formula em `Formula/claude-i.rb` usa URL dev-pass** apontando para GitHub Release pre-release. Marcada como **TBD pending upstream public release** no README (decisão operator: claude-i permanece IP-protected). Não publicada ainda em qualquer brew tap consumer.

### gh CLI auth (verificado)

```
github.com
  ✓ Logged in to github.com account rafaelscosta (keyring) — ACTIVE
  ✓ Logged in to github.com account AIOXsquad (keyring)
  Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

`rafaelscosta` é a active account — usada para push em ambos repos. **Para retomar:** confirmar `gh auth status` mostra rafaelscosta ATIVO.

---

## Parte 2: GitHub Release v0.2.0 — VERIFICADO

- **URL:** https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.0
- **Criado:** 2026-05-18T06:05:49Z
- **Tag aponta para:** `3d68eaf` (commit story-001.5 closure)
- **Assets (verificados via `gh release view`):**

| Asset | Size |
|---|---|
| `claude_i-0.2.0-py3-none-any.whl` | 22276 bytes |
| `claude_i-0.2.0.tar.gz` | 30230 bytes |

**SHA-256 dos artifacts locais (idênticos aos do Release):**

```
ee6a455efd90b279114eb460030d9c96ac83a0119b39621ae837b3c709268e10  dist/claude_i-0.2.0-py3-none-any.whl
28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353  dist/claude_i-0.2.0.tar.gz
```

Build artifacts mantidos em `/Users/rafaelcosta/Projects/AIOX/claude-i/dist/` (verificados via `ls -la`).

---

## Parte 3: EPIC-001 — 6 stories Done (TODAS verificadas)

### Resultado por story

| Story | Título | SP | QA Gate Score | Status |
|---|---|---|---|---|
| STORY-001.0 | Bootstrap (pyproject + CI + module refactor) | 5 | 96/100 | Done |
| STORY-001.1 | Critical gaps G1-G4 | 5 | 94/100 | Done (G2 deferred-with-notes) |
| STORY-001.2 | Important gaps G5-G9 + G13 | 5 | 95/100 | Done |
| STORY-001.3 | PyPI packaging (executor: @devops) | 4 | 94/100 | Done |
| STORY-001.4 | Multi-target install (cross-repo) | 5 | 92/100 | Done |
| STORY-001.5 | Doctor/Reaper/UX (G10-G18) | 4 | 80→95/100 | Done (G14 deferred + QA re-gate) |

**Total:** 28 SP, score médio 94.3/100

### Gaps endereçados (16 implementados + 2 deferred)

✅ G1 permission default, G3 dep check, G4 env var isolation, G5 mkstemp, G6 atexit reaper, G7 fcntl.flock, G8 ExitCode constants + 4-branch RuntimeError, G9 Windows guard, G11 metadata signature, G12 hook structural check, G13 UTF-8 encoding, G15 stale sentinel cleanup, G16 doctor/uninstall/reap subcommands, G17 readiness polling, G18 tests adicionados.

⚠️ **G2 deferred** — Stop hook matcher não documentado pela Anthropic (NOTES.md § "Hook Matcher Support" com triggers para revisitar). Shell guard `if [ -n "$CLAUDE_I_SENTINEL" ]` é suficiente.

⚠️ **G14 deferred** — `SubagentStop` event name não documentado em Claude Code 2.1.143. Investigado empiricamente; existing `Stop` handler é suficiente. NOTES.md § "G14 SubagentStop Deferred" documenta triggers para revisitar.

### Artifacts da governance no repo

- `docs/epics/EPIC-001-packaging-and-hardening.md` (planning original do @pm)
- `docs/stories/STORY-001.{0..5}-*.md` (6 stories com File List + Dev Agent Record + QA Results + Closure populados)
- `docs/gates/STORY-001.{0..5}-gate.md` (6 gate files com PASS/CONCERNS verdicts)
- `NOTES.md` (5 seções: G2 deferral + Private Distribution Phase + IP Lock + G14 deferral + v0.2.0 tag rationale)

---

## Parte 4: Quality Gates VERIFICADOS

Reproduz com fresh venv:

```bash
python3.11 -m venv /tmp/claude-i-verify
/tmp/claude-i-verify/bin/pip install -e "/Users/rafaelcosta/Projects/AIOX/claude-i[dev]"
cd /Users/rafaelcosta/Projects/AIOX/claude-i
/tmp/claude-i-verify/bin/pytest tests/                # → 89/89 passed
/tmp/claude-i-verify/bin/ruff check src/ tests/        # → All checks passed
/tmp/claude-i-verify/bin/mypy src/claude_i/            # → Success: no issues in 8 source files
git diff HEAD -- seed/claude-i | wc -l                 # → 0 (seed byte-identical)
/tmp/claude-i-verify/bin/claude-i --version            # → claude-i 0.2.0
```

**Resultado verificado nesta sessão (2026-05-18):**
- ✅ 89 testes passam (pytest tests/ — 4 import + 13 deps + 13 hook + 14 reaper + 18 cli + 27 runner — todos verdes em 0.41s)
- ✅ ruff clean (8 source files cobertos)
- ✅ mypy --strict clean (8 source files)
- ✅ seed/claude-i sem diff vs HEAD
- ✅ `claude-i --version` → "claude-i 0.2.0"

### CI no remote (último run de cada workflow)

- **ci** (push to main) — `success` (jobs: verify seed integrity, build sdist+wheel+twine check, lint+type+pytest py3.11, lint+type+pytest py3.12)
- **smoke** (3-OS install) — `success` (macOS-latest, ubuntu-latest, fedora:latest container — todos green em run anterior)
- **publish** (workflow_dispatch only) — guard testado: dispatch com string errada `accidentally-clicked` → `Safety guard FAILURE`, demais steps SKIPPED

---

## Parte 5: Settings.json hook state ATUAL (verificado)

```
[0] type=http     | (URL: http://localhost:7483/hooks/stop, timeout:5)
[1] type=command  | node "$HOME/.nyx/hook-bridge.cjs" claude-code stop
[2] type=command  | if [ -n "$CLAUDE_I_SENTINEL" ]; then cat > "$CLAUDE_I_SENTINEL.json"; touch "$CLAUDE_I_SENTINEL"; fi
```

- **Hook 0:** http endpoint do usuário (não relacionado ao claude-i — pré-existente)
- **Hook 1:** nyx hook-bridge (electron app do usuário — pré-existente)
- **Hook 2:** **canonical claude-i HOOK_CMD** — restaurado após sessão de debug (sed scripts foram revertidos verificadamente; settings.json não tem nenhum vestígio das mutações de diagnóstico)

**Status do hook claude-i:** instalado, canonical, gated em `$CLAUDE_I_SENTINEL`.

---

## Parte 6: 🚨 BUGS CRÍTICOS DESCOBERTOS via E2E real

### BUG 1 — Stop hook touch/cat race condition (BLOCKER)

**Sintoma:** `claude-i "prompt"` retorna `claude-i: hook fired but no payload written`. Sempre.

**Evidência empírica nesta sessão:**

- **437 .done sentinels** acumulados em `/var/folders/6c/d7ws84896057zvsl4kdbznnh0000gn/T/claude-i-*.done` (todos 0-byte — sentinels apenas touched)
- **Apenas 2 .done.json payloads** existem (claude-i-42g92sy9.done.json com `hi\n` de teste manual; claude-i-pth__phw.done.json com 369 bytes de payload REAL escrito DEPOIS que runner deu timeout)

**Reprodução documentada:**

Instrumentação adicionada temporariamente em `/Users/rafaelcosta/.local/pipx/venvs/.../runner.py` (já revertida) mostrou:

```
[DEBUG] sentinel=/var/folders/.../claude-i-pth__phw.done exists=True
[DEBUG] payload=/var/folders/.../claude-i-pth__phw.done.json exists=False
[DEBUG] (após 5x sleep(0.2) = 1s) payload ainda não existe
```

**Mas** ao inspecionar depois: o `.done.json` apareceu com payload Stop hook válido:
```json
{"session_id":"7f7f06ee-90d9-4d6e-9f19-246c875e373e","transcript_path":"/Users/rafaelcosta/.claude/projects/.../7f7f06ee-90d9-4d6e-9f19-246c875e373e.jsonl","cwd":"...","permission_mode":"bypassPermissions","hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"SKIP"}
```

**Diagnóstico do root cause:**

Race condition entre `touch sentinel` (atômico, rápido) e `cat > payload` (precisa de stdin, possivelmente assíncrono em Claude Code 2.1.143). HOOK_CMD canônico `cat > "$CLAUDE_I_SENTINEL.json"; touch "$CLAUDE_I_SENTINEL"` deveria garantir sequência (cat completa antes de touch), mas **observação empírica mostra sentinel touch acontecer ANTES do payload write completar** em ambiente Claude Code 2.1.143 com os 3 Stop hooks do usuário.

**Possíveis causas:**

1. Claude Code 2.1.143 invoca hooks em parallel/async-mode em vez de sequencial dentro do script bash
2. Múltiplos Stop hooks no settings.json interagem (hook 0 http + hook 1 nyx + hook 2 claude-i) — possivelmente disparam em ordem diferente da config
3. Bug de sincronização interna do claude-code Stop hook implementation que pode ter sido introduzido entre versão do gist isingh e 2.1.143
4. macOS APFS / sandbox affectando timing de visibilidade de stat() entre processos

**Fix proposto (Path A — recomendado):**

Reverter ordem do HOOK_CMD: **`touch sentinel; cat > payload`**. Polling vê sentinel → espera payload (com grace 5s) → lê. Atualmente runner.py FAILS hard se payload missing 1ms depois do sentinel touch.

```python
# Em runner.py wait-loop, após sentinel.exists():
deadline_payload = time.time() + 5.0  # grace period for payload write
while not payload.exists():
    if time.time() > deadline_payload:
        raise RuntimeError("hook fired but no payload written after 5s grace")
    time.sleep(0.1)
```

**Fix proposto (Path B — alternativa):**

Mudar HOOK_CMD para usar arquivo temp atômico:
```sh
if [ -n "$CLAUDE_I_SENTINEL" ]; then
  TMP="$CLAUDE_I_SENTINEL.json.tmp"
  cat > "$TMP"
  mv "$TMP" "$CLAUDE_I_SENTINEL.json"   # atomic rename
  touch "$CLAUDE_I_SENTINEL"
fi
```

Garante que payload.exists() == True implica payload completo + flushed quando ficar visível.

**Quem implementa:** @dev em STORY-001.6 (escopo: bug fix + integration test real).

**Validação:** integration test que SPAWNA claude real e exercita o flow E2E (não mocked). Atual cobertura mocka subprocess/tmux portanto deixa esse gap escondido.

---

### BUG 2 — G15 cleanup path hardcoded /tmp/ (MEDIUM)

**Sintoma:** 437 sentinels stale acumulados em `$TMPDIR` (macOS = `/var/folders/.../`), nunca limpos pelo `_cleanup_stale_sentinels()`.

**Evidência empírica:**

```bash
$ ls /var/folders/6c/d7ws84896057zvsl4kdbznnh0000gn/T/claude-i-*.done 2>/dev/null | wc -l
437
```

**Localização do bug:**

`/Users/rafaelcosta/Projects/AIOX/claude-i/src/claude_i/runner.py:169`:

```python
def _cleanup_stale_sentinels() -> None:
    ...
    try:
        candidates = list(Path("/tmp").glob("claude-i-*.done"))  # ← bug
    except Exception:
        return
```

Hardcoda `/tmp/` mas no macOS `tempfile.mkstemp()` retorna `/var/folders/<hash>/T/...` (via `tempfile.gettempdir()` que lê `$TMPDIR`).

**Fix proposto:**

```python
candidates = list(Path(tempfile.gettempdir()).glob("claude-i-*.done"))
```

**Testes a adicionar:**

- `test_cleanup_uses_tempdir_not_hardcoded` — monkeypatch `tempfile.gettempdir` e verifica que glob usa o path retornado
- `test_cleanup_finds_macos_tmpdir_sentinels` — cria sentinels em `/var/folders/.../` e confirma cleanup

**Quem implementa:** @dev em STORY-001.6.

---

### BUG 3 — ensure_hook() crasha sem TTY (HIGH UX)

**Sintoma:** primeira invocação de `claude-i` em script (sem TTY) crasha com:

```
EOFError: EOF when reading a line
```

**Localização:**

`/Users/rafaelcosta/.local/pipx/venvs/claude-i/lib/python3.13/site-packages/claude_i/hook.py:287`:

```python
def ensure_hook() -> None:
    ...
    if input("Install it now? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")
```

**Impacto:** automation/CI/script users batem nesse muro no primeiro uso. Curiosamente, o docstring do `ensure_hook` MENCIONA o problema (linha 277: "invoking this function (otherwise CI hangs on ``input()``)") mas não implementa proteção.

**Workaround atual** (verificado funcional): `printf "y\n" | claude-i "prompt"` no first run para confirmar o hook install.

**Fix proposto:**

```python
import sys
def ensure_hook() -> None:
    if hook_installed():
        return
    if not sys.stdin.isatty():
        print(
            "claude-i: Stop hook não instalado e stdin não é TTY.\n"
            "Opções:\n"
            "  1. Rode `claude-i doctor` interativamente uma vez\n"
            "  2. Defina CLAUDE_I_AUTO_INSTALL_HOOK=1 (auto-aprovar — script-friendly)\n"
            "  3. Edite ~/.claude/settings.json manualmente",
            file=sys.stderr,
        )
        sys.exit(2)
    # ... prompt logic
```

**Quem implementa:** @dev em STORY-001.6.

---

## Parte 7: Pipx state ATUAL (verificado)

```
$ pipx list | grep claude-i
   package claude-i 0.2.0, installed using Python 3.13.3
    - claude-i

$ /Users/rafaelcosta/.local/bin/claude-i --version
claude-i 0.2.0
```

**Localização do package instalado:** `/Users/rafaelcosta/.local/pipx/venvs/claude-i/lib/python3.13/site-packages/claude_i/`

**Verificado:** runner.py do pipx install NÃO tem mais a DEBUG instrumentation (foi revertida via sed). Estado sem patches além do source original.

⚠️ Atenção: durante a sessão eu temporariamente editei o `runner.py` do pipx install para adicionar debug prints. Revertido. Para 100% de certeza ao retomar, recomendo:

```bash
pipx uninstall claude-i
pipx install /Users/rafaelcosta/Projects/AIOX/claude-i/dist/claude_i-0.2.0-py3-none-any.whl
# OU pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.0
```

---

## Parte 8: Share bundle para testers (verificado)

**Localização:** `/tmp/claude-i-share-bundle/`

```
claude-i-v0.2.0/                # pasta descompactada (preview)
├── INSTALL.md                  # pré-reqs + 2 install paths + uso + troubleshooting
├── LICENSE                     # MIT
├── claude_i-0.2.0-py3-none-any.whl   # 22 KB
└── claude_i-0.2.0.tar.gz             # 30 KB

claude-i-v0.2.0.tar.gz   # 55560 bytes — formato Unix
claude-i-v0.2.0.zip      # 54939 bytes — formato cross-platform
```

**SHA-256 dos bundles:**

```
c2782d75efc9ead1e90369bf039a0f771acad5d50fe4302c7f8c70506cd631ae  claude-i-v0.2.0.tar.gz
6555b97d84a7f3526194126f7c7311f3d36dfe30ecca358f011161910020e747  claude-i-v0.2.0.zip
```

**⚠️ RECOMENDAÇÃO CRÍTICA:** **NÃO compartilhar com testers até Bug 1 fixado.** Bundle instala o binário OK, mas a função core (`claude-i "prompt"`) está quebrada. Vai gerar reports de "não funciona" que confirmam o Bug 1.

Manter o bundle pronto para distribuição após v0.2.1.

---

## Parte 9: Safety guards instalados (verificados)

### publish.yml workflow (claude-i repo)

- **Trigger:** `workflow_dispatch` only (sem tag-push trigger)
- **Required input:** `confirm_release` (string, default ausente)
- **Step 1:** safety guard — falha se input != `I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE`
- **Testado:** dispatch com `confirm_release=accidentally-clicked` → Run #26030501191, Safety guard step FAILED, demais steps SKIPPED (Checkout/Build/Publish todos pulados)
- **Defense in depth:** mesmo se alguém clicar Run no GitHub UI, sem typear a string exata o workflow não publica

### GitHub publish environment (claude-i repo)

- Criado via `gh api`
- Branch policy configurada
- ⚠️ **Required reviewers NÃO configurados** — GitHub Free plan não suporta required_reviewers em private repos (HTTP 422 documentado). Não é problema porque a safety guard no workflow já é absoluta.

### NOTES.md — IP Lock (claude-i repo)

Seção "IP Status — Private Forever (as of 2026-05-18)" documenta:
- Repository: PERMANENTLY PRIVATE
- PyPI publication: PERMANENTLY FORBIDDEN
- Public Homebrew formula: PERMANENTLY FORBIDDEN
- Como reverter (operator escolha explícita)

---

## Parte 10: O que NÃO foi feito (e por que)

| Item | Por que | Quando | Bloqueador |
|---|---|---|---|
| PyPI publish v0.2.0 | IP-protected status (decisão operator) | Nunca (a menos que IP lock seja revertido) | — |
| flip claude-i repo para PUBLIC | Mesmo motivo | Nunca | — |
| Homebrew formula URL canonical | Depende de PyPI publish | Nunca (linked to IP lock) | — |
| GitHub Environments required reviewers | Free plan limitation (HTTP 422 em private repos) | Se upgradar para GitHub Pro | — |
| E2E integration test real (não-mocked) | Gap descoberto NESTA sessão; lacuna na cobertura | STORY-001.6 | Bug 1 fix |
| Validação E2E em outras máquinas | Só rodamos em 1 macOS (esta) | Após Bug 1 fix + bundle re-distribuído | Bug 1 |

---

## Parte 11: Plano de retomada da próxima sessão

### Imediato (sem dependências)

1. **Spawnar @sm para criar STORY-001.6** com 3 tasks:
   - Task 7.1: Fix Bug 1 (Stop hook race) — implementar Path A (grace period polling) OU Path B (atomic mv). Recomendo Path B porque é mais simples e robusto, mas testar ambos.
   - Task 7.2: Fix Bug 2 (G15 cleanup path) — `tempfile.gettempdir()` em vez de hardcoded `/tmp/`
   - Task 7.3: Fix Bug 3 (TTY detection em ensure_hook)
   - Task 7.4: **Integration test real** que invoca claude binary real, dispara claude-i com prompt, valida output não-vazio. Esse é o teste que falta para fechar a lacuna que escondeu os 3 bugs.

2. **@po validate STORY-001.6** — D10 incremental check com 5 stories Done deve catch qualquer drift

3. **@dev implement** com SDC tradicional. Bug 1 é o crítico — testar empiricamente que o fix funciona em E2E real ANTES de marcar Done.

4. **@qa review** com requisito: integration test deve PASSAR em E2E real (não só mock).

5. **@devops push** → tag v0.2.1 → cria novo GitHub Release (deletando ou substituindo o v0.2.0).

### Médio prazo

6. **Re-distribuir bundle para testers** após v0.2.1 verde
7. **Considerar pre-flight script** no install.sh que valida o Stop hook flow antes de declarar install OK

### Validação cross-machine

Bug 1 pode ser específico desta máquina (tem hook 0 http + hook 1 nyx pré-instalados). Vale rodar v0.2.1 em macOS limpo sem outros Stop hooks para confirmar se o fix funciona universalmente OU se outros Stop hooks no settings.json são o trigger.

---

## Parte 12: Anatomia técnica para retomar SEM perda de contexto

### Arquitetura claude-i (resumo conceitual)

```
┌─ claude-i CLI (cli.py)
│  └─ argparse: prompt | doctor | uninstall | reap + flags
│
├─ hook.py: install/check/remove Stop hook em ~/.claude/settings.json
│  └─ HOOK_CMD constante: 'if [-n "$CLAUDE_I_SENTINEL" ]; then cat > "$CLAUDE_I_SENTINEL.json"; touch "$CLAUDE_I_SENTINEL"; fi'
│
├─ runner.py: orquestra tmux + claude
│  ├─ run(prompt, extra_args, verbose, ready_wait, timeout) -> (text, RunMetadata)
│  ├─ 1. tempfile.mkstemp → sentinel path (G5)
│  ├─ 2. tmux new-session -d (DETACHED), com CLAUDE_I_SENTINEL=<path> exec claude (G4)
│  ├─ 3. reaper.register_cleanup(session) — atexit + SIGTERM (G6)
│  ├─ 4. _wait_for_tui_ready: polling 250ms até ver claude prompt indicator (G17)
│  ├─ 5. tmux set-buffer (UTF-8) + paste-buffer + send-keys Enter (G13)
│  ├─ 6. polling sentinel.exists() at 0.3s intervals (ATÉ AQUI OK)
│  ├─ 7. ❌ payload.exists() check imediato — falha por race condition (BUG 1)
│  ├─ 8. parse transcript JSONL → última msg role=assistant → join text blocks
│  └─ 9. finally: tmux kill-session + unlink sentinel + payload (G6)
│
├─ deps.py: check_deps() OS-aware (G3), assert_not_windows() exit 3 (G9)
├─ reaper.py: reap_orphans() + _pid_alive() (G6) — DO NOT EDIT
├─ exit_codes.py: SUCCESS=0, RUNTIME_ERROR=1, CONFIG_ERROR=2, PLATFORM_ERROR=3 (G8)
└─ settings.py: ~/.claude/settings.json I/O, HOOK_CMD constant, TUI_READY_PATTERN
```

### Contratos não-negociáveis (NUNCA quebrar)

1. **G4 two-layer** — em runner.py:
   - Linha ~166: `parts = [f"CLAUDE_I_SENTINEL={shlex.quote(...)}", "exec", "claude"]` — shell PREFIX preserved
   - Linha ~187: `subprocess.run(... env=_sanitized_env() ...)` — env kwarg STRIPPED
   - Teste pair `test_sentinel_stripped_from_subprocess_env` + `test_sentinel_still_in_sh_command` deve passar SEMPRE

2. **G6 reaper** — `reap_orphans()` em reaper.py:95-143 é IMUTÁVEL. STORY-001.5 task 6.3 era ADAPT (wire to cmd_reap), não CREATE.

3. **G7 flock** — `install_hook()` e `remove_hook()` em hook.py usam `_acquire_lock_with_retry()`. Funções read-only (`hook_installed`) NÃO usam lock.

4. **Seed integrity** — `seed/claude-i` é byte-identical, AC-8 do STORY-001.0. CI tem job dedicado verificando.

5. **HOOK_CMD canonical** — settings.py define constante, hook.py exact-match em `hook_installed()`. Se mudar a constante, hooks instalados anteriormente parecem "not installed" e ensure_hook prompts de novo. Bug 1 fix Path B muda HOOK_CMD — precisa migration path para hooks antigos.

### Paths críticos (absolutos verificados)

```
~/Projects/AIOX/claude-i/                                   # repo principal (private)
~/Projects/AIOX/homebrew-claude-i/                          # tap repo (public)
~/Documents/aiox-handoffs/claude-i-2026-05-18/HANDOFF.md   # ESTE arquivo
~/.claude/settings.json                                     # Stop hooks (3 instalados)
~/.local/pipx/venvs/claude-i/                               # pipx claude-i instalação
/tmp/claude-i-share-bundle/                                 # bundle para testers (HOLD)
/var/folders/.../T/claude-i-*.done                          # 437 stale sentinels (Bug 2 evidence)
```

---

## Parte 13: Comandos de smoke pra primeira hora da próxima sessão

Para validar que nada mudou no estado durante a pausa:

```bash
# 1. Repos sincronizados?
git -C ~/Projects/AIOX/claude-i status -sb        # esperado: ## main...origin/main (clean)
git -C ~/Projects/AIOX/claude-i log -1 --oneline   # esperado: 08d3975 chore(safety): publish.yml...
git -C ~/Projects/AIOX/homebrew-claude-i status -sb # esperado: ## main...origin/main (clean)
git -C ~/Projects/AIOX/homebrew-claude-i log -1 --oneline # esperado: 11a0d43 docs(readme):...

# 2. Tag v0.2.0 + Release ainda lá?
gh release view v0.2.0 -R rafaelscosta/claude-i --json url,assets

# 3. Tests verdes? (em fresh venv)
python3.11 -m venv /tmp/claude-i-resume
/tmp/claude-i-resume/bin/pip install -e ~/Projects/AIOX/claude-i[dev]
cd ~/Projects/AIOX/claude-i
/tmp/claude-i-resume/bin/pytest tests/             # esperado: 89 passed
/tmp/claude-i-resume/bin/ruff check src/ tests/    # esperado: All checks passed
/tmp/claude-i-resume/bin/mypy src/claude_i/        # esperado: 8 source files clean
git diff HEAD -- seed/claude-i | wc -l             # esperado: 0

# 4. Bugs reproduzem? (Bug 1 — deve falhar)
printf "y\n" | claude-i --timeout 30 --ready-wait 10 "PONG" 2>&1 | tail -3
# Esperado: "claude-i: hook fired but no payload written"
# Se mudar comportamento, Bug 1 mudou de natureza — re-diagnosticar

# 5. gh CLI autenticado como rafaelscosta?
gh auth status 2>&1 | grep "Active account: true"
```

Se tudo bate: pode prosseguir com STORY-001.6.

Se algo mudou (commits diferentes, tests falhando, settings.json corrompido): investigar antes de fazer qualquer coisa nova.

---

## Parte 14: Decisões irrevogáveis registradas

1. **Repo IP-protected forever** (operator decision 2026-05-18, registrado em NOTES.md § "IP Status")
2. **PyPI publish forbidden** (mesma decisão)
3. **Public Homebrew tap formula** permanente como TBD/dev-pass
4. **publish.yml safety guard** instalado (49-char confirm string mandatory)
5. **Operator-only paths** preservados (Pending Publisher + GH Environment + macOS smoke) mas adormecidos enquanto IP lock vigora

---

## Encerramento

**Estado real:**
- Implementação: 100% das 6 stories Done
- Testes: 89/89 mocked passing, 0 integration tests real
- Distribuição: 3 install paths funcionais para colaboradores
- Core function: ❌ broken (Bug 1)

**Próximo passo concreto:** abrir STORY-001.6 com 4 tasks (3 fixes + integration test) usando o pipeline SDC.

**Confiança:** alta. Tudo neste handoff foi verificado por comando, não suposto. SHAs e estados conferidos via `git`, `gh`, `pytest`, `ruff`, `mypy`, `shasum`, `ls`, `cat`.

**Última atualização:** 2026-05-18 ~09:05 local time.

Boa retomada.
