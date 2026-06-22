#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "loopx" / "cli.py"
BOOTSTRAP_MODULE = ROOT / "loopx" / "cli_commands" / "bootstrap_connect.py"
ROLLOUT_MODULE = ROOT / "loopx" / "cli_rollout.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise AssertionError(
            f"expected success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def require_json_success(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    stdout = require_success(result)
    payload = json.loads(stdout)
    require(payload.get("ok") is True, f"payload was not ok: {payload}")
    return payload


def assert_source_shape() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    bootstrap_source = BOOTSTRAP_MODULE.read_text(encoding="utf-8")
    rollout_source = ROLLOUT_MODULE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_cli_markers = [
        "bootstrap_parser = sub.add_parser",
        "bootstrap_project(",
        "render_bootstrap_markdown",
        "DEFAULT_OBJECTIVE",
        "DEFAULT_DOMAIN",
        'if args.command in {"bootstrap", "connect"}:',
        "def append_cli_rollout_event(",
        "def append_benchmark_run_rollout_event(",
        "def append_benchmark_result_rollout_event(",
        "def _benchmark_rollout_",
        "build_rollout_event(",
        "append_rollout_event(",
    ]
    for marker in forbidden_cli_markers:
        require(marker not in cli_source, f"bootstrap/rollout marker leaked into cli.py: {marker}")

    for marker in (
        "register_bootstrap_connect_command",
        "handle_bootstrap_connect_command",
        "bootstrap",
        "connect",
        "bootstrap_project(",
    ):
        require(marker in bootstrap_source, f"bootstrap module missing {marker}")
    for marker in (
        "append_cli_rollout_event",
        "append_benchmark_run_rollout_event",
        "append_benchmark_result_rollout_event",
        "build_rollout_event(",
    ):
        require(marker in rollout_source, f"rollout module missing {marker}")
    require("register_bootstrap_connect_command" in cli_source, "cli.py did not register bootstrap/connect")
    require("handle_bootstrap_connect_command" in cli_source, "cli.py did not dispatch bootstrap/connect")
    require("register_bootstrap_connect_command" in init_source, "__init__ omitted bootstrap registration")
    require("handle_bootstrap_connect_command" in init_source, "__init__ omitted bootstrap handler")


def assert_help_surfaces() -> None:
    for command in ("bootstrap", "connect"):
        help_text = require_success(run_cli(command, "--help"))
        for option in (
            "--fork-goal",
            "--execution-minimum-scale",
            "--accept-onboarding-agent-todos",
            "--replace-state",
            "--no-global-sync",
        ):
            require(option in help_text, f"{command} help omitted {option}")


def assert_bootstrap_dry_run() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-bootstrap-modular-smoke-") as tmp:
        root = Path(tmp)
        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text("# Bootstrap Smoke\n", encoding="utf-8")
        registry = project / ".loopx" / "registry.json"
        payload = require_json_success(
            run_cli(
                "--format",
                "json",
                "--registry",
                str(registry),
                "--runtime-root",
                str(root / "runtime"),
                "connect",
                "--project",
                str(project),
                "--goal-id",
                "bootstrap-modular-smoke",
                "--objective",
                "Validate bootstrap/connect command modularization.",
                "--domain",
                "smoke",
                "--adapter-kind",
                "read_only_project_map_v0",
                "--adapter-status",
                "connected-read-only",
                "--dry-run",
                "--no-global-sync",
            )
        )
        require(payload.get("dry_run") is True, payload)
        require(payload.get("goal_id") == "bootstrap-modular-smoke", payload)
        require(not registry.exists(), "bootstrap dry-run wrote the registry")


def main() -> None:
    assert_source_shape()
    assert_help_surfaces()
    assert_bootstrap_dry_run()
    print("cli-bootstrap-rollout-helper-modularization-smoke: ok")


if __name__ == "__main__":
    main()
