#!/usr/bin/env python3
"""Smoke-test the minimal LoopX-selected auto-research worker turn."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e  # noqa: E402


GOAL_ID = "loopx-auto-research-knn"
CURATOR_AGENT_ID = "codex-product-capability"
MAPPER_AGENT_ID = "codex-side-bypass"
EVIDENCE_AGENT_ID = "codex-main-control"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http" + "://",
        "https" + "://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_worker_turn(
    *,
    registry: Path,
    runtime_root: str | None,
    workspace: Path,
    agent_id: str,
    execute: bool,
    complete: bool = False,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    args = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        "auto-research",
        "worker-turn",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        agent_id,
        "--lane-count",
        "3",
        "--visible-lanes-accepted",
    ]
    if execute:
        args.append("--execute")
    if complete:
        args.append("--complete-selected-todo")
    result = subprocess.run(
        args,
        cwd=workspace,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"worker-turn failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        captured: dict[str, Any] = {}

        def fake_append_evidence(_packet_path: str) -> dict[str, object]:
            return {
                "ok": True,
                "schema_version": "auto_research_rollout_append_v0",
                "goal_id": GOAL_ID,
                "dry_run": False,
                "event_count": 3,
                "appended_count": 3,
                "would_append_count": 3,
                "skipped_existing_count": 0,
                "event_ids": ["kernel-hypothesis", "kernel-dev", "kernel-holdout"],
                "appended_event_ids": ["kernel-hypothesis", "kernel-dev", "kernel-holdout"],
                "skipped_existing_event_ids": [],
                "counts_by_kind": {"research_evidence": 2, "research_hypothesis": 1},
                "packet_summary": {"goal_id": GOAL_ID},
                "public_boundary": {
                    "raw_logs_recorded": False,
                    "private_artifacts_recorded": False,
                    "absolute_paths_recorded": False,
                },
            }

        def fake_visible_launcher(
            _supervisor: dict[str, object],
            visible_registry: Path,
            visible_runtime_root: str | None,
            default_workspace: Path,
        ) -> dict[str, object]:
            curator_preview = run_worker_turn(
                registry=visible_registry,
                runtime_root=visible_runtime_root,
                workspace=default_workspace,
                agent_id=CURATOR_AGENT_ID,
                execute=False,
            )
            curator_executed = run_worker_turn(
                registry=visible_registry,
                runtime_root=visible_runtime_root,
                workspace=default_workspace,
                agent_id=CURATOR_AGENT_ID,
                execute=True,
                complete=True,
            )
            mapper_executed = run_worker_turn(
                registry=visible_registry,
                runtime_root=visible_runtime_root,
                workspace=default_workspace,
                agent_id=MAPPER_AGENT_ID,
                execute=True,
                complete=True,
            )
            evidence_executed = run_worker_turn(
                registry=visible_registry,
                runtime_root=visible_runtime_root,
                workspace=default_workspace,
                agent_id=EVIDENCE_AGENT_ID,
                execute=True,
                complete=True,
            )
            captured["curator_preview"] = curator_preview
            captured["curator_executed"] = curator_executed
            captured["mapper_executed"] = mapper_executed
            captured["evidence_executed"] = evidence_executed
            return {
                "ok": True,
                "schema_version": "auto_research_worker_turn_fake_launch_v0",
                "mode": "executed_visible_launch",
                "launch_result": {
                    "schema_version": "auto_research_worker_turn_fake_launch_result_v0",
                    "worker_turn_executed": bool(evidence_executed.get("executed")),
                    "worker_turn_count": 3,
                    "visible_acceptance": {
                        "accepted": bool(evidence_executed.get("executed")),
                        "worker_turn_schema": evidence_executed.get("schema_version"),
                    },
                },
                "public_boundary": {
                    "raw_logs_recorded": False,
                    "private_artifacts_recorded": False,
                    "absolute_paths_recorded": False,
                },
            }

        payload = run_auto_research_demo_e2e(
            agent_id="codex-side-bypass",
            goal_id=GOAL_ID,
            tracking_goal_id="loopx-meta",
            objective="Prove the visible worker can run a LoopX-selected auto-research evidence turn.",
            output_dir="auto_research_knn_pack",
            execute=True,
            launch_visible=True,
            keep_workspace=False,
            registry_path=registry,
            runtime_root_arg=str(runtime_root),
            session_name="loopx-auto-research-worker-turn-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
            live_evidence_path=None,
            append_evidence=fake_append_evidence,
            visible_launcher=fake_visible_launcher,
        )

        assert payload["ok"] is True, payload
        preview = captured["curator_preview"]
        curator_executed = captured["curator_executed"]
        mapper_executed = captured["mapper_executed"]
        executed = captured["evidence_executed"]
        assert preview["schema_version"] == "auto_research_worker_turn_v0", preview
        assert preview["mode"] == "dry_run", preview
        assert preview["selected_action"] == "write_research_contract", preview
        assert preview["selected_todo_id"], preview
        assert curator_executed["schema_version"] == "auto_research_worker_turn_v0", curator_executed
        assert curator_executed["mode"] == "execute", curator_executed
        assert curator_executed["selected_action"] == "write_research_contract", curator_executed
        assert curator_executed["artifact"]["kind"] == "research_contract", curator_executed
        assert curator_executed["artifact_status"] == "contract_written", curator_executed
        assert curator_executed["completion"]["status"] == "done", curator_executed
        assert mapper_executed["schema_version"] == "auto_research_worker_turn_v0", mapper_executed
        assert mapper_executed["mode"] == "execute", mapper_executed
        assert mapper_executed["selected_action"] == "propose_hypothesis", mapper_executed
        assert mapper_executed["artifact"]["kind"] == "research_hypothesis", mapper_executed
        assert mapper_executed["artifact_status"] == "hypothesis_mapped", mapper_executed
        assert mapper_executed["hypothesis_id"].startswith("hyp_"), mapper_executed
        assert mapper_executed["completion"]["status"] == "done", mapper_executed
        assert executed["schema_version"] == "auto_research_worker_turn_v0", executed
        assert executed["mode"] == "execute", executed
        assert executed["selected_action"] == "run_dev_eval", executed
        assert executed["executed"] is True, executed
        assert executed["dev_metric"] == 4.0, executed
        assert executed["packet_status"] == "supported", executed
        assert executed["completion"]["status"] == "done", executed
        assert executed["append"]["appended_count"] == 2, executed
        assert executed["append"]["counts_by_kind"] == {
            "research_evidence": 1,
            "research_hypothesis": 1,
        }, executed
        assert executed["live_evidence"]["written"] is True, executed
        assert executed["live_evidence"]["claim_source"] == "live_codex_lane_output", executed
        assert executed["live_evidence"]["dev_metric"] == 4.0, executed
        assert executed["frontier"]["frontier"]["selected"]["claimed_by"] == EVIDENCE_AGENT_ID, executed
        assert payload["visible_launch"]["launch_result"]["worker_turn_executed"] is True, payload
        assert payload["visible_launch"]["launch_result"]["worker_turn_count"] == 3, payload
        assert payload["live_codex_e2e"]["visible_lanes_accepted"] is True, payload
        assert_public_safe(preview)
        assert_public_safe(curator_executed)
        assert_public_safe(mapper_executed)
        assert_public_safe(executed)
        assert_public_safe(payload["visible_launch"])

    print("auto-research-worker-turn-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
