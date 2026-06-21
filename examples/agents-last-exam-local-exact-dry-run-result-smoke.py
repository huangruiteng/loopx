#!/usr/bin/env python3
"""Smoke-test compact ALE dry-run stdout reduction."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_agents_last_exam_local_exact_dry_run_result,
)


STDOUT = """experiment: loopx_ale_docker_no_cloud_dry_run_os_log_permission_guard_v1
environment: docker (cpu-free-ubuntu->docker)
output:     /private/example/.local/ale-logs/should-not-leak
concurrency: 1
units (1):
  codex                 computing_math/os_log_permission_guard_v1  v0
"""


def assert_public_safe(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/private/example",
        "should-not-leak",
        "output:",
        "units (1):",
        "trajectory.json",
        "screenshot.png",
        "secret-value",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked


def main() -> None:
    payload = build_agents_last_exam_local_exact_dry_run_result(
        stdout_text=STDOUT,
        exit_code=0,
        expected_agent_id="codex",
        expected_task_id="computing_math/os_log_permission_guard_v1",
    )
    assert payload["schema_version"] == "agents_last_exam_local_exact_dry_run_result_v0", payload
    assert payload["ready"] is True, payload
    assert payload["first_blocker"] == "ready_for_compact_ale_dry_run_result_ingest", payload
    assert payload["exit_code"] == 0, payload
    assert payload["environment"]["kind"] == "docker", payload
    assert payload["unit_count_declared"] == 1, payload
    assert payload["unit_count_parsed"] == 1, payload
    assert payload["units"] == [
        {
            "agent": "codex",
            "task": "computing_math__os_log_permission_guard_v1",
            "variant": "v0",
        }
    ], payload
    assert payload["boundary"]["raw_stdout_recorded"] is False, payload
    assert payload["boundary"]["local_paths_recorded"] is False, payload
    assert payload["boundary"]["task_body_read"] is False, payload
    assert_public_safe(payload)

    blocked = build_agents_last_exam_local_exact_dry_run_result(
        stdout_text=STDOUT,
        exit_code=2,
        expected_agent_id="codex",
        expected_task_id="computing_math/os_log_permission_guard_v1",
    )
    assert blocked["ready"] is False, blocked
    assert blocked["first_blocker"] == "ale_dry_run_exit_nonzero", blocked
    assert_public_safe(blocked)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8") as stdout_file:
        stdout_file.write(STDOUT)
        stdout_file.flush()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-local-exact-dry-run-result",
                "--stdout-file",
                stdout_file.name,
                "--exit-code",
                "0",
                "--expected-agent-id",
                "codex",
                "--expected-task-id",
                "computing_math/os_log_permission_guard_v1",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    cli_payload = json.loads(result.stdout)
    assert cli_payload["ok"] is True, cli_payload
    assert cli_payload["ready"] is True, cli_payload
    assert cli_payload["unit_count_parsed"] == 1, cli_payload
    assert_public_safe(cli_payload)
    print("agents-last-exam-local-exact-dry-run-result-smoke ok")


if __name__ == "__main__":
    main()
