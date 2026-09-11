"""Public CLI characterization for the Goal Channel runtime command family."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.cli import build_parser
from loopx.cli_commands import goal_channel, goal_channel_runtime


@pytest.fixture
def registry_path(tmp_path):
    path = tmp_path / ".loopx" / "registry.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": "synthetic-goal",
                        "repo": str(tmp_path),
                        "state_file": str(tmp_path / "state.md"),
                    }
                ]
            }
        )
    )
    return path


def argv(operation):
    args = ["goal-channel", "runtime", operation, "--goal-id", "synthetic-goal"]
    if operation == "setup":
        args += ["--bot-id", "synthetic-bot", "--chat-id", "synthetic-chat"]
    return args


@pytest.mark.parametrize(
    "operation", ["setup", "doctor", "trigger", "status", "disable"]
)
@pytest.mark.parametrize("execute", [False, True])
def test_runtime_dispatch_preserves_arguments_and_rendering(
    registry_path, monkeypatch, operation, execute
):
    calls, printed = [], []
    expected = {"ok": True, "provider": "botmux", "operation": f"runtime_{operation}"}

    def backend(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(goal_channel_runtime, f"{operation}_botmux_runtime", backend)
    options = argv(operation) + [
        "--runtime-binding-path",
        str(registry_path.parent / "binding.json"),
        "--format",
        "json",
    ]
    if execute and operation != "doctor":
        options += ["--execute"]
    args = build_parser().parse_args(options)
    code = goal_channel.handle_goal_channel_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=str(registry_path.parent / "runtime"),
        print_payload=lambda *items: printed.append(items),
        output_format=lambda args: args.subcommand_format,
    )
    assert code == 0
    assert len(calls) == 1
    actual = calls[0]
    assert actual["goal_id"] == "synthetic-goal"
    assert actual["binding_path"] == registry_path.parent / "binding.json"
    if operation != "doctor":
        assert actual["execute"] is execute
    if operation in {"setup", "trigger"}:
        assert actual["registry_path"] == registry_path
        assert actual["registry"]["goals"][0]["id"] == "synthetic-goal"
    if operation == "setup":
        assert actual["endpoint"] == "http://127.0.0.1:7891"
        assert actual["bot_id"] == "synthetic-bot"
        assert actual["chat_id"] == "synthetic-chat"
    if operation == "trigger":
        assert actual["instruction"] is None
        assert actual["turn_key"] is None
    assert printed == [(expected, "json", goal_channel.render_goal_channel_markdown)]


@pytest.mark.parametrize(
    "operation", ["setup", "doctor", "trigger", "status", "disable"]
)
def test_runtime_invalid_configuration_preserves_safe_error(
    registry_path, monkeypatch, operation
):
    def backend(**kwargs):
        raise ValueError("synthetic-private-error")

    monkeypatch.setattr(goal_channel_runtime, f"{operation}_botmux_runtime", backend)
    printed = []
    args = build_parser().parse_args(argv(operation))
    code = goal_channel.handle_goal_channel_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=str(registry_path.parent / "runtime"),
        print_payload=lambda payload, *_: printed.append(payload),
        output_format=lambda _: "json",
    )
    assert code == 1
    assert printed[0]["schema_version"] == "loopx_goal_channel_runtime_operation_v0"
    assert printed[0]["operation"] == f"runtime_{operation}"
    assert printed[0]["blocker"] == "invalid_configuration"
    assert printed[0]["external_write_performed"] is False
    assert "synthetic-private-error" not in json.dumps(printed)


@pytest.mark.parametrize("operation", ["doctor", "trigger", "status", "disable"])
def test_real_cli_missing_binding_preserves_unconfigured_state(
    registry_path, operation
):
    before = registry_path.read_bytes()
    result = run_cli(registry_path, argv(operation))
    assert result.returncode == (0 if operation == "disable" else 1)
    payload = json.loads(result.stdout)
    assert payload["ok"] is (operation == "disable")
    assert payload["provider"] == "botmux"
    assert payload["external_write_performed"] is False
    assert registry_path.read_bytes() == before
    assert not (registry_path.parent / "goal-channel-runtime.json").exists()


def run_cli(registry_path, options):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(registry_path.parent / "runtime"),
            "--format",
            "json",
            *options,
        ],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_real_cli_disable_preserves_preview_then_persists(registry_path):
    binding_path = registry_path.parent / "goal-channel-runtime.json"
    binding_path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_goal_channel_botmux_binding_v0",
                "bindings": {
                    "synthetic-goal": {
                        "enabled": True,
                        "session": {"session_id": "synthetic-session"},
                    }
                },
            }
        )
    )
    original = binding_path.read_bytes()
    preview = run_cli(registry_path, argv("disable"))
    assert preview.returncode == 0
    assert json.loads(preview.stdout)["execute"] is False
    assert binding_path.read_bytes() == original
    executed = run_cli(registry_path, [*argv("disable"), "--execute"])
    assert executed.returncode == 0
    assert json.loads(executed.stdout)["status"] == "disabled"
    persisted = json.loads(binding_path.read_text())["bindings"]["synthetic-goal"]
    assert persisted["enabled"] is False
    assert persisted["session"] == {}
