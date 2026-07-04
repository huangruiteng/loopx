#!/usr/bin/env python3
"""Smoke-test opt-in status projection cache behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.status_projection_cache import write_status_projection_cache

GOAL_ID = "status-projection-cache-fixture"
AGENT_ID = "codex-main-control"
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
        "# Status Projection Cache Fixture\n\n"
        "## Objective\n\n"
        "Validate opt-in status projection cache behavior.\n\n"
        "## Next Action\n\n"
        "- Exercise the status/quota projection cache.\n",
        encoding="utf-8",
    )
    public_doc.write_text("Public smoke fixture for status projection cache.\n", encoding="utf-8")

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
                        "domain": "status-projection-cache",
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
    return registry_path, runtime, public_doc


def run_cli_result(
    registry_path: Path,
    *args: str,
    check: bool = True,
) -> tuple[dict[str, Any], int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
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
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}
    return payload, result.returncode, result.stderr


def run_cli(registry_path: Path, *args: str) -> dict[str, Any]:
    payload, _returncode, _stderr = run_cli_result(registry_path, *args)
    return payload


def assert_cache_hit(payload: dict[str, Any]) -> None:
    cache = payload.get("projection_cache")
    if not isinstance(cache, dict):
        cache = payload.get("status_projection_cache")
    assert isinstance(cache, dict), payload
    assert cache.get("schema_version") == "status_projection_cache_v0", cache
    assert cache.get("hit") is True, cache


def assert_cache_written(payload: dict[str, Any]) -> None:
    cache = payload.get("projection_cache")
    if not isinstance(cache, dict):
        cache = payload.get("status_projection_cache")
    assert isinstance(cache, dict), payload
    assert cache.get("schema_version") == "status_projection_cache_v0", cache
    assert cache.get("written") is True, cache
    assert cache.get("hit") is False, cache
    assert Path(str(cache.get("path"))).exists(), cache


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-status-projection-cache-") as tmp:
        registry_path, runtime, public_doc = write_fixture(Path(tmp))

        todo_payload = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Validate status projection cache.",
            "--claimed-by",
            AGENT_ID,
        )
        assert todo_payload.get("ok") is True, todo_payload

        status_write = run_cli(
            registry_path,
            "status",
            "--scan-path",
            str(public_doc),
            "--limit",
            "5",
            "--write-projection-cache",
        )
        assert status_write.get("ok") is True, status_write
        assert_cache_written(status_write)

        status_cached = run_cli(
            registry_path,
            "status",
            "--scan-path",
            str(public_doc),
            "--limit",
            "5",
            "--use-projection-cache",
        )
        assert status_cached.get("ok") is True, status_cached
        assert_cache_hit(status_cached)

        quota_write = run_cli(
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
            "--write-projection-cache",
        )
        assert quota_write.get("ok") is True, quota_write
        assert quota_write.get("should_run") is True, quota_write
        assert_cache_written(quota_write)

        quota_cached = run_cli(
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
            "--use-projection-cache",
        )
        assert quota_cached.get("ok") is True, quota_cached
        assert quota_cached.get("should_run") is True, quota_cached
        assert_cache_hit(quota_cached)

        public_doc.write_text(
            f"Public leak probe must still be caught by default quota scan: {PRIVATE_DOC_MARKER}\n",
            encoding="utf-8",
        )
        leak_payload, leak_returncode, leak_stderr = run_cli_result(
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

        cache_dir = runtime / "status-projection-cache"
        assert cache_dir.exists(), cache_dir
        assert list(cache_dir.glob("*.json")), cache_dir
        with ThreadPoolExecutor(max_workers=8) as executor:
            writes = list(
                executor.map(
                    lambda index: write_status_projection_cache(
                        registry_path=registry_path,
                        runtime_root=runtime,
                        scan_roots=[public_doc],
                        limit=5,
                        include_task_graph=False,
                        goal_id=GOAL_ID,
                        payload={"ok": True, "concurrent_write": index},
                        max_age_seconds=120,
                    ),
                    range(16),
                )
            )
        assert all(item.get("written") is True for item in writes), writes
        concurrent_cache_path = Path(str(writes[-1]["path"]))
        assert json.loads(concurrent_cache_path.read_text(encoding="utf-8"))["payload"]["ok"] is True

    print("status-projection-cache-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
