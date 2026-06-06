#!/usr/bin/env python3
"""Run the first isolated long-run regression shim.

This intentionally uses Goal Harness CLI commands, not Codex CLI, so the
fixture, JSONL log, quota, writeback, and spend contracts can stabilize before a
real worker process is introduced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "codex-cli-long-run-fixture"
STEP_COUNT = 3


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_registry(root: Path) -> tuple[Path, Path, Path]:
    home = root / "home"
    project = root / "project"
    runtime = home / ".codex" / "goal-harness"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Codex CLI Long-Run Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Complete three isolated worker steps with validation and spend accounting.\n\n"
        "## Progress Ledger\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "codex-cli-long-run-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, project, runtime


def run_cli(
    *,
    registry_path: Path,
    runtime_root: Path,
    home: Path,
    args: list[str],
    scan_root: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "goal_harness.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        *args,
    ]
    if scan_root is not None:
        command.extend(["--scan-root", str(scan_root)])
    env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def queue_status(status_payload: dict[str, Any]) -> str:
    items = status_payload.get("attention_queue", {}).get("items", [])
    for item in items:
        if isinstance(item, dict) and item.get("goal_id") == GOAL_ID:
            return str(item.get("status") or "")
    return "missing"


def append_progress(project: Path, *, step_index: int, artifact_path: str) -> None:
    state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    with state_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n- step {step_index}: validated `{artifact_path}`\n")


def assert_public_log(rows: list[dict[str, Any]]) -> None:
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    forbidden = ("/Users/", "~/.codex/sessions", "raw_thread", "session_history")
    for marker in forbidden:
        assert marker not in text, marker


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-codex-cli-long-run-") as tmp:
        root = Path(tmp)
        registry_path, project, runtime_root = write_registry(root)
        home = root / "home"
        log_path = root / "run-log.jsonl"
        rows: list[dict[str, Any]] = []

        for step_index in range(1, STEP_COUNT + 1):
            started_at = iso_now()
            started = time.perf_counter()
            status_before = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["status"],
                scan_root=project,
            )
            quota_before = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["quota", "should-run", "--goal-id", GOAL_ID],
                scan_root=project,
            )
            should_run = bool(quota_before.get("should_run"))
            row: dict[str, Any] = {
                "step_index": step_index,
                "started_at": started_at,
                "goal_id": GOAL_ID,
                "status_before": queue_status(status_before),
                "should_run_before": should_run,
            }
            if not should_run:
                row.update(
                    {
                        "action_kind": "no_spend_stop",
                        "artifact_path": None,
                        "validation": {"passed": False, "command": "quota should-run"},
                        "writeback_event": None,
                        "spend_event": None,
                    }
                )
                rows.append(row)
                break

            artifact = project / "artifacts" / f"step-{step_index}.txt"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            marker = f"validated step {step_index}"
            artifact.write_text(marker + "\n", encoding="utf-8")
            artifact_rel = artifact.relative_to(project).as_posix()
            validation_passed = marker in artifact.read_text(encoding="utf-8")
            assert validation_passed, artifact
            append_progress(project, step_index=step_index, artifact_path=artifact_rel)

            classification = (
                "long_run_regression_terminal"
                if step_index == STEP_COUNT
                else f"long_run_regression_step_{step_index}"
            )
            refresh = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=[
                    "refresh-state",
                    "--goal-id",
                    GOAL_ID,
                    "--classification",
                    classification,
                    "--recommended-action",
                    f"Fixture step {step_index} validated {artifact_rel}.",
                    "--delivery-batch-scale",
                    "implementation",
                    "--delivery-outcome",
                    "outcome_progress",
                ],
            )
            spend = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=[
                    "quota",
                    "spend-slot",
                    "--goal-id",
                    GOAL_ID,
                    "--slots",
                    "1",
                    "--source",
                    "heartbeat",
                    "--execute",
                ],
                scan_root=project,
            )
            status_after = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["status"],
                scan_root=project,
            )
            finished_at = iso_now()
            row.update(
                {
                    "finished_at": finished_at,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "status_after": queue_status(status_after),
                    "action_kind": "fixture_artifact_write",
                    "artifact_path": artifact_rel,
                    "validation": {
                        "command": f"artifact contains {marker!r}",
                        "passed": validation_passed,
                    },
                    "writeback_event": {
                        "classification": refresh.get("classification"),
                        "json_path": Path(str(refresh.get("json_path"))).name,
                    },
                    "spend_event": {
                        "classification": spend.get("classification"),
                        "json_path": Path(str(spend.get("json_path"))).name,
                    },
                }
            )
            rows.append(row)

        log_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

        assert len(rows) == STEP_COUNT, rows
        assert rows[-1]["status_after"] == "long_run_regression_terminal", rows[-1]
        for row in rows:
            assert row["should_run_before"] is True, row
            assert row["duration_ms"] >= 0, row
            assert row["validation"]["passed"] is True, row
            assert row["writeback_event"]["classification"], row
            assert row["spend_event"]["classification"] == "quota_slot_spent", row
            assert (project / str(row["artifact_path"])).exists(), row

        run_index = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
        classifications = [
            json.loads(line)["classification"]
            for line in run_index.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert classifications.count("quota_slot_spent") == STEP_COUNT, classifications
        assert "long_run_regression_terminal" in classifications, classifications
        assert_public_log(rows)

        print(f"steps={len(rows)} log_rows={len(log_path.read_text(encoding='utf-8').splitlines())}")
    print("codex-cli-long-run-regression-runner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
