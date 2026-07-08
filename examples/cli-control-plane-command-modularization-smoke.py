#!/usr/bin/env python3
"""Smoke-test that todo/quota CLI groups live outside loopx/cli.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "loopx" / "cli.py"
INIT_PATH = REPO_ROOT / "loopx" / "cli_commands" / "__init__.py"
TODO_MODULE = REPO_ROOT / "loopx" / "cli_commands" / "todo.py"
QUOTA_MODULE = REPO_ROOT / "loopx" / "cli_commands" / "quota.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def assert_source_shape() -> None:
    cli_text = CLI_PATH.read_text(encoding="utf-8")
    init_text = INIT_PATH.read_text(encoding="utf-8")
    todo_text = TODO_MODULE.read_text(encoding="utf-8")
    quota_text = QUOTA_MODULE.read_text(encoding="utf-8")

    assert_contains(init_text, "register_todo_command", "__init__")
    assert_contains(init_text, "handle_todo_command", "__init__")
    assert_contains(init_text, "register_quota_command", "__init__")
    assert_contains(init_text, "handle_quota_command", "__init__")
    assert "todo_parser = sub.add_parser" not in cli_text
    assert "quota_parser = sub.add_parser" not in cli_text
    assert_contains(cli_text, "register_todo_command(sub)", "cli.py")
    assert_contains(cli_text, "register_quota_command(sub)", "cli.py")
    assert_contains(cli_text, "handle_todo_command(", "cli.py")
    assert_contains(cli_text, "handle_quota_command(", "cli.py")
    assert_contains(todo_text, "render_todo_markdown", "todo module")
    assert_contains(todo_text, "append_cli_rollout_event", "todo module")
    assert_contains(quota_text, "render_quota_should_run_markdown", "quota module")
    assert_contains(quota_text, "append_cli_rollout_event", "quota module")


def assert_help_surfaces() -> None:
    todo_help = run_cli("todo", "--help")
    assert todo_help.returncode == 0, todo_help.stderr
    assert_contains(todo_help.stdout, "archive-completed", "todo help")
    assert_contains(todo_help.stdout, "--side-agent-self-merged", "todo help")
    assert_contains(todo_help.stdout, "--next-agent-todo", "todo help")

    quota_help = run_cli("quota", "--help")
    assert quota_help.returncode == 0, quota_help.stderr
    assert_contains(quota_help.stdout, "should-run", "quota help")
    assert_contains(quota_help.stdout, "spend-slot", "quota help")
    assert_contains(quota_help.stdout, "--available-capability", "quota help")


def assert_todo_error_payload() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-cli-todo-modular-smoke-") as tmp:
        result = run_cli(
            "--format",
            "json",
            "--registry",
            str(Path(tmp) / "missing-registry.json"),
            "todo",
            "add",
            "--goal-id",
            "cli-modular-smoke",
            "--text",
            "Synthetic todo missing role.",
            "--dry-run",
        )
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert payload["goal_id"] == "cli-modular-smoke", payload
    assert payload["error"] == "todo add requires --role", payload


def assert_todo_markdown_error_payload() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-cli-todo-markdown-smoke-") as tmp:
        result = run_cli(
            "--registry",
            str(Path(tmp) / "missing-registry.json"),
            "todo",
            "add",
            "--goal-id",
            "cli-modular-smoke",
            "--text",
            "Synthetic todo missing role.",
            "--dry-run",
        )
    assert result.returncode == 1, result.stdout
    assert_contains(result.stdout, "# LoopX Todo", "todo markdown error")
    assert_contains(result.stdout, "- ok: `False`", "todo markdown error")
    assert_contains(result.stdout, "- error: todo add requires --role", "todo markdown error")


def main() -> int:
    assert_source_shape()
    assert_help_surfaces()
    assert_todo_error_payload()
    assert_todo_markdown_error_payload()
    print("cli-control-plane-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
