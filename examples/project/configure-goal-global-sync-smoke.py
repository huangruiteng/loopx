#!/usr/bin/env python3
"""Guard configure-goal shared-runtime routing and exact readback."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "configure-goal-global-sync-fixture"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def source_goal(project: Path) -> dict:
    return {
        "id": GOAL_ID,
        "status": "active",
        "domain": "configure-goal-global-sync",
        "repo": str(project),
        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
        "quota": {"compute": 1, "window_hours": 24},
        "waiting_on": "codex",
    }


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    source_registry = project / ".loopx" / "registry.json"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("# Active Goal State\n", encoding="utf-8")
    goal = source_goal(project)
    write_json(
        source_registry,
        {
            "schema_version": "0.1",
            "common_runtime_root": ".loopx/runtime",
            "goals": [goal],
        },
    )

    shared_runtime = root / "shared-runtime"
    write_json(
        shared_runtime / "registry.global.json",
        {
            "schema_version": "0.1",
            "registry_role": "global-local",
            "common_runtime_root": str(shared_runtime),
            "goals": [
                {
                    **goal,
                    "source_registry": str(source_registry.resolve()),
                    "synced_at": "2026-01-01T00:00:00+00:00",
                    "authority_source_count": 0,
                    "authority_registry": {
                        "schema_version": "authority_registry_v0",
                        "entries": [],
                    },
                }
            ],
        },
    )
    return source_registry, shared_runtime


def run_cli(
    source_registry: Path,
    shared_runtime: Path,
    *args: str,
    runtime_root: Path | None = None,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--format",
        "json",
        "--registry",
        str(source_registry),
    ]
    if runtime_root is not None:
        command.extend(["--runtime-root", str(runtime_root)])
    command.extend(args)
    env = dict(os.environ, LOOPX_RUNTIME_ROOT=str(shared_runtime))
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def only_goal(registry: Path) -> dict:
    return json.loads(registry.read_text(encoding="utf-8"))["goals"][0]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-configure-global-sync-") as tmp:
        root = Path(tmp)
        source_registry, shared_runtime = write_fixture(root)
        shared_registry = shared_runtime / "registry.global.json"
        project_runtime_registry = (
            source_registry.parent / "runtime" / "registry.global.json"
        )

        preview = run_cli(
            source_registry,
            shared_runtime,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--waiting-on",
            "external_evidence",
        )
        assert preview["global_sync"]["enabled"] is True, preview
        assert preview["global_sync"]["executed"] is False, preview
        assert preview["global_sync"]["readback"]["status"] == "not_executed", preview
        assert preview["global_sync"]["selected_target"]["global_registry"] == str(
            shared_registry.resolve()
        ), preview

        applied = run_cli(
            source_registry,
            shared_runtime,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--waiting-on",
            "external_evidence",
            "--execute",
        )
        sync = applied["global_sync"]
        assert applied["ok"] is True and applied["written"] is True, applied
        assert sync["target_resolution"]["status"] == "resolved", sync
        assert sync["selected_target"]["global_registry"] == str(
            shared_registry.resolve()
        ), sync
        assert sync["readback"]["status"] == "verified", sync
        assert (
            sync["readback"]["expected_goal_sha256_16"]
            == sync["readback"]["target_goal_sha256_16"]
        ), sync
        assert only_goal(source_registry)["waiting_on"] == "external_evidence"
        assert only_goal(shared_registry)["waiting_on"] == "external_evidence"
        assert not project_runtime_registry.exists(), project_runtime_registry

        explicit_runtime = root / "explicit-runtime"
        explicit = run_cli(
            source_registry,
            shared_runtime,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--waiting-on",
            "controller",
            "--execute",
            runtime_root=explicit_runtime,
        )
        explicit_sync = explicit["global_sync"]
        explicit_registry = explicit_runtime / "registry.global.json"
        assert explicit_sync["target_resolution"]["status"] == "explicit_override"
        assert explicit_sync["selected_target"]["global_registry"] == str(
            explicit_registry.resolve()
        )
        assert explicit_sync["readback"]["verified"] is True
        assert only_goal(source_registry)["waiting_on"] == "controller"
        assert only_goal(explicit_registry)["waiting_on"] == "controller"
        assert only_goal(shared_registry)["waiting_on"] == "external_evidence"

    print("configure-goal-global-sync-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
