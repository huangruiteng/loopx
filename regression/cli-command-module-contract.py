#!/usr/bin/env python3
"""Regression for the first modular CLI command seam.

This protects the initial extraction from ``loopx.cli`` into
``loopx.cli_commands``. The old public invocation should keep working
while command registration/handling moves behind a small module contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.cli_commands import (
        handle_demo_command,
        handle_check_command,
        handle_doctor_command,
        handle_new_project_prompt_command,
        handle_review_packet_command,
        handle_status_command,
        register_doctor_command,
        register_starter_commands,
        register_status_commands,
    )

    assert callable(handle_demo_command)
    assert callable(handle_check_command)
    assert callable(register_doctor_command)
    assert callable(register_starter_commands)
    assert callable(register_status_commands)
    assert callable(handle_doctor_command)
    assert callable(handle_new_project_prompt_command)
    assert callable(handle_review_packet_command)
    assert callable(handle_status_command)

    doctor = run_cli("doctor")
    assert doctor.get("ok") is True, doctor
    assert "checks" in doctor, doctor

    prompt = run_cli(
        "new-project-prompt",
        "--project",
        "/tmp/loopx-command-module-fixture",
        "--goal-doc",
        "GOAL.md",
        "--goal-id",
        "command-module-fixture",
    )
    assert prompt.get("ok") is True, prompt
    assert prompt.get("goal_id") == "command-module-fixture", prompt
    assert "prompt" in prompt, prompt

    with tempfile.TemporaryDirectory(prefix="loopx-cli-command-module-") as raw_tmp:
        root = Path(raw_tmp)
        demo = run_cli(
            "--runtime-root",
            str(root / "runtime"),
            "demo",
            "--project",
            str(root / "project"),
            "--goal-id",
            "command-module-demo",
        )
    assert demo.get("ok") is True, demo
    assert demo.get("goal_id") == "command-module-demo", demo
    assert "quota" in demo, demo

    check = run_cli("check", "--scan-root", "README.md", "--limit", "1")
    assert check.get("ok") is True, check
    assert "summary" in check, check

    status = run_cli("status", "--limit", "1")
    assert status.get("ok") is True, status
    assert "attention_queue" in status, status

    review = run_cli("review-packet", "--goal-id", "loopx-meta", "--limit", "1")
    assert review.get("ok") is True, review
    assert review.get("goal_id") == "loopx-meta", review

    print("cli-command-module-contract-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
