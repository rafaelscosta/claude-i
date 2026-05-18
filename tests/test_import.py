"""Smoke test — verify every public module of ``claude_i`` imports cleanly.

Satisfies AC-3 (modules exist) and AC-4 (pytest exit 0).
"""

from __future__ import annotations


def test_package_imports() -> None:
    """The top-level package imports and exposes a non-empty version."""
    import claude_i

    assert isinstance(claude_i.__version__, str)
    assert claude_i.__version__ != ""


def test_all_submodules_import() -> None:
    """Each module listed in STORY-001.0 AC-3 imports without ``ImportError``."""
    from claude_i import cli, deps, hook, reaper, runner, settings

    # Touch a public symbol per module so static analyzers don't flag the
    # imports as unused, and we get a fail-loud signal if a module is empty.
    assert callable(cli.main)
    assert callable(deps.check_deps)
    assert callable(deps.assert_not_windows)
    assert callable(hook.hook_installed)
    assert callable(hook.install_hook)
    assert callable(hook.ensure_hook)
    assert callable(reaper.reap_orphans)
    assert callable(reaper.register_cleanup)
    assert callable(runner.run)
    assert callable(runner.tmux)
    assert callable(runner.tail_pane)
    assert isinstance(settings.HOOK_CMD, str)
    assert settings.HOOK_CMD != ""


def test_hook_cmd_is_single_source_of_truth() -> None:
    """``settings.HOOK_CMD`` is the canonical constant referenced by ``hook``."""
    from claude_i import hook, settings

    # ``hook`` must import the constant from ``settings`` rather than redefine it.
    assert hook.HOOK_CMD is settings.HOOK_CMD


def test_expected_binaries_listed() -> None:
    """``deps.EXPECTED_BINARIES`` enumerates tmux and claude per AC-5 task 1.5."""
    from claude_i import deps

    assert "tmux" in deps.EXPECTED_BINARIES
    assert "claude" in deps.EXPECTED_BINARIES
