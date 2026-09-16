"""Refs GH-C06: the `refresh-state` group still belongs to the project lifecycle commands.

`refresh-state` was extracted from `cli_commands/project_lifecycle.py` into
`cli_commands/project_lifecycle_refresh_state.py` to bring that module back under
the 1000-line default budget. The extraction must not change the public
invocation, so these cases pin the two things that could silently break it: the
command must still be part of the project lifecycle set, and it must still be
registered exactly once.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from loopx.cli_commands import project_lifecycle
from loopx.cli_commands import project_lifecycle_refresh_state as refresh_module

COMMANDS_DIR = Path(refresh_module.__file__).resolve().parent
ADD_PARSER_RE = re.compile(
    r"subparsers\.add_parser\(\s*(?:\n\s*)?[\"'](?P<command>[^\"']+)[\"']",
    re.MULTILINE,
)


def registered_commands() -> dict[str, list[str]]:
    registrations: dict[str, list[str]] = {}
    for path in sorted(COMMANDS_DIR.glob("*.py")):
        for match in ADD_PARSER_RE.finditer(path.read_text(encoding="utf-8")):
            registrations.setdefault(match.group("command"), []).append(path.name)
    return registrations


def test_refresh_state_is_still_a_project_lifecycle_command() -> None:
    assert "refresh-state" in project_lifecycle.PROJECT_LIFECYCLE_COMMANDS


def test_refresh_state_is_registered_exactly_once() -> None:
    registrations = registered_commands()
    assert registrations["refresh-state"] == ["project_lifecycle_refresh_state.py"]


def test_owner_module_exposes_both_halves() -> None:
    """Registration and dispatch moved together, so both live in the new module."""
    assert callable(refresh_module.register_refresh_state_command)
    assert callable(refresh_module.handle_refresh_state_command)


def test_dispatch_ignores_other_commands() -> None:
    """A non-refresh-state command must fall through untouched, before any work."""
    args = argparse.Namespace(command="reward")
    assert (
        refresh_module.handle_refresh_state_command(
            args,
            registry_path=Path("/nonexistent-registry"),
            print_payload=lambda *_args: None,
            output_format=lambda *_args: "json",
            append_cli_rollout_event=lambda *_args, **_kwargs: {},
        )
        is None
    )
