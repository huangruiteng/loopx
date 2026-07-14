#!/usr/bin/env python3
"""Keep project-local refresh-state visible to its registered shared runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.runtime.shared_runtime_refresh_projection import (  # noqa: E402
    build_shared_runtime_projection,
    write_shared_runtime_projection,
)


AGENT_ID = "codex-shared-runtime-smoke"
GOAL_ID = "refresh-state-shared-runtime-smoke"
VISION_ACCEPTANCE = "Shared quota reads the newest project-local agent vision."


def run_cli(*args: str, cwd: Path, shared_runtime: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT),
            "LOOPX_RUNTIME_ROOT": str(shared_runtime),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    project_runtime = project / ".loopx" / "runtime"
    shared_runtime = root / "shared-runtime"
    source_registry = project / ".loopx" / "registry.json"
    shared_registry = shared_runtime / "registry.global.json"
    state_file = project / ".loopx" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\nstatus: active\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n\n"
        f"# {GOAL_ID}\n\n## Agent Todo\n\n"
        "- [ ] [P1] Verify the shared-runtime refresh projection.\n",
        encoding="utf-8",
    )
    goal = {
        "id": GOAL_ID,
        "domain": "refresh-state-shared-runtime-smoke",
        "status": "active",
        "repo": str(project),
        "state_file": str(state_file.relative_to(project)),
        "adapter": {"kind": "fixture", "status": "connected-read-only"},
        "coordination": {
            "registered_agents": [AGENT_ID],
            "agent_model": "peer_v1",
        },
        "quota": {"compute": 1.0, "window_hours": 24},
    }
    source_registry.parent.mkdir(parents=True, exist_ok=True)
    source_registry.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(project_runtime),
                "goals": [goal],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    shared_registry.parent.mkdir(parents=True)
    shared_registry.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "registry_role": "global-local",
                "common_runtime_root": str(shared_runtime),
                "goals": [
                    {
                        **goal,
                        "source_registry": str(source_registry.resolve()),
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return project, project_runtime, source_registry, shared_registry


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-refresh-shared-runtime-") as tmp:
        project, project_runtime, source_registry, shared_registry = write_fixture(
            Path(tmp)
        )
        shared_runtime = shared_registry.parent
        refresh = run_cli(
            "--registry",
            str(source_registry),
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--progress-scope",
            "agent_lane",
            "--classification",
            "shared_runtime_projection_verified",
            "--recommended-action",
            "Inspect PRIVATE_LOCAL_ACTION_MARKER in the source runtime only.",
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "outcome_progress",
            "--vision-state",
            "active",
            "--vision-summary",
            "Project-local material refresh should remain visible globally.",
            "--vision-acceptance",
            VISION_ACCEPTANCE,
            "--suppress-external-sinks",
            cwd=project,
            shared_runtime=shared_runtime,
        )

        assert Path(refresh["runtime_root"]).resolve() == project_runtime.resolve()
        assert Path(refresh["global_sync"]["global_registry"]).resolve() == shared_registry.resolve()
        projection = refresh["shared_runtime_projection"]
        assert projection["ok"] is True, projection
        assert projection["status"] == "projected", projection
        assert projection["raw_artifacts_copied"] is False, projection
        assert projection["recommended_action_copied"] is False, projection
        assert not (project_runtime / "registry.global.json").exists()

        shared_index = shared_runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        rows = [json.loads(line) for line in shared_index.read_text().splitlines()]
        latest = rows[-1]
        assert latest["classification"] == "shared_runtime_projection_verified"
        assert latest["agent_vision"]["vision_patch"]["acceptance_summary"] == VISION_ACCEPTANCE
        shared_record = Path(latest["json_path"]).read_text(encoding="utf-8")
        assert "PRIVATE_LOCAL_ACTION_MARKER" not in shared_record
        assert str(project) not in shared_record

        source_record = json.loads(Path(refresh["json_path"]).read_text(encoding="utf-8"))
        replay_record, replay_index = build_shared_runtime_projection(record=source_record)
        replay = write_shared_runtime_projection(
            shared_runtime_root=shared_runtime,
            goal_id=GOAL_ID,
            record=replay_record,
            index_record=replay_index,
            dry_run=False,
        )
        assert replay["status"] == "already_current", replay
        assert len(shared_index.read_text().splitlines()) == len(rows)

        source_record["state"]["frontmatter"]["updated_at"] = str(project)
        boundary_record, _ = build_shared_runtime_projection(record=source_record)
        assert boundary_record["state"]["frontmatter"]["updated_at"] is None
        assert str(project) not in json.dumps(boundary_record)

        quota = run_cli(
            "--registry",
            str(shared_registry),
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--available-capability",
            "shell",
            cwd=project,
            shared_runtime=shared_runtime,
        )
        audit = quota["interaction_contract"]["agent_channel"][
            "vision_continuation_audit"
        ]
        assert audit["acceptance_gaps"][0]["acceptance_summary"] == VISION_ACCEPTANCE

    print("refresh-state shared-runtime projection smoke passed")


if __name__ == "__main__":
    main()
