#!/usr/bin/env python3
"""Smoke-test status/quota latency with large ignored local state trees."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "status-quota-perf-budget-fixture"
AGENT_ID = "codex-main-control"
IGNORED_FILE_COUNT = 1_200
STATUS_BUDGET_SECONDS = 3.5
QUOTA_BUDGET_SECONDS = 3.5
PRIVATE_DOC_MARKER = "https://" + "la" + "rk" + "office.example/doc"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_rel = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_file = project / state_rel
    registry_path = project / ".loopx" / "registry.json"
    public_doc = project / "README.md"

    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Status Quota Perf Budget Fixture\n\n"
        "## Objective\n\n"
        "Keep status and quota hot paths fast without skipping public scans.\n\n"
        "## Next Action\n\n"
        "- Validate the selected hot-path budget todo.\n",
        encoding="utf-8",
    )
    public_doc.write_text("Public smoke fixture for status/quota perf budgets.\n", encoding="utf-8")

    ignored_root = project / ".local" / "large-state-tree"
    ignored_root.mkdir(parents=True)
    for index in range(IGNORED_FILE_COUNT):
        shard = ignored_root / f"shard-{index // 100:02d}"
        shard.mkdir(exist_ok=True)
        (shard / f"private-state-{index:04d}.txt").write_text(
            "ignored local runtime state\n",
            encoding="utf-8",
        )

    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "status-quota-perf-budget",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_rel,
                        "adapter": {
                            "kind": "generic_project_goal_v0",
                            "status": "connected",
                        },
                        "coordination": {
                            "registered_agents": [AGENT_ID],
                            "primary_agent": AGENT_ID,
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, project, public_doc


def run_cli_result(
    registry_path: Path,
    *args: str,
    check: bool = True,
) -> tuple[dict[str, Any], float, int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    started = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    elapsed = time.perf_counter() - started
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}
    return payload, elapsed, result.returncode, result.stderr


def run_cli(registry_path: Path, *args: str) -> tuple[dict[str, Any], float]:
    payload, elapsed, _returncode, _stderr = run_cli_result(registry_path, *args)
    return payload, elapsed


def assert_public_scan(payload: dict[str, Any]) -> None:
    checks = "\n".join(
        str(item)
        for item in [
            *(payload.get("checks") or []),
            *((payload.get("contract") or {}).get("checks") or []),
        ]
    )
    assert "public boundary scan clean: 1 files" in checks, payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-status-quota-perf-budget-") as tmp:
        root = Path(tmp)
        registry_path, _project, public_doc = write_fixture(root)

        todo_payload, _todo_elapsed = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Validate status/quota perf budget.",
            "--claimed-by",
            AGENT_ID,
        )
        assert todo_payload.get("ok") is True, todo_payload

        status_payload, status_elapsed = run_cli(
            registry_path,
            "status",
            "--scan-path",
            str(public_doc),
            "--limit",
            "5",
            "--agent-id",
            AGENT_ID,
        )
        assert status_payload.get("ok") is True, status_payload
        assert_public_scan(status_payload)
        assert status_elapsed <= STATUS_BUDGET_SECONDS, (
            status_elapsed,
            STATUS_BUDGET_SECONDS,
            IGNORED_FILE_COUNT,
        )

        quota_payload, quota_elapsed = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--available-capability",
            "shell",
            "--scan-path",
            str(public_doc),
            "--limit",
            "5",
        )
        assert quota_payload.get("ok") is True, quota_payload
        assert quota_payload.get("should_run") is True, quota_payload
        assert quota_elapsed <= QUOTA_BUDGET_SECONDS, (
            quota_elapsed,
            QUOTA_BUDGET_SECONDS,
            IGNORED_FILE_COUNT,
        )

        public_doc.write_text(
            f"Public leak probe must be caught by quota scan: {PRIVATE_DOC_MARKER}\n",
            encoding="utf-8",
        )
        leak_payload, _leak_elapsed, leak_returncode, leak_stderr = run_cli_result(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--scan-path",
            str(public_doc),
            check=False,
        )
        assert leak_returncode != 0 or leak_payload.get("status_health_ok") is False, leak_payload
        assert "status or contract health" in json.dumps(leak_payload) + leak_stderr, leak_payload

        print(
            "status_quota_perf_budget: "
            f"ignored_files={IGNORED_FILE_COUNT} "
            f"status={status_elapsed:.3f}s/{STATUS_BUDGET_SECONDS:.1f}s "
            f"quota={quota_elapsed:.3f}s/{QUOTA_BUDGET_SECONDS:.1f}s"
        )
    print("status-quota-perf-budget-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
