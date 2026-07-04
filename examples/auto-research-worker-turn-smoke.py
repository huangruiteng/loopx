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

from loopx.capabilities.auto_research.demo_e2e import _seed_visible_demo_control_plane  # noqa: E402
from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e  # noqa: E402
from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    build_auto_research_demo_supervisor_plan,
)
from loopx.todos import add_goal_todo, update_goal_todo  # noqa: E402


GOAL_ID = "loopx-auto-research-demo"
CURATOR_AGENT_ID = "codex-product-capability"
MAPPER_AGENT_ID = "codex-side-bypass"
EVIDENCE_AGENT_ID = "codex-main-control"
VERIFIER_AGENT_ID = "codex-value-explorer"
ALT_EVIDENCE_AGENT_ID = "codex-alt-evidence"
FOUR_LANES = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
]


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
    result = run_worker_turn_process(
        registry=registry,
        runtime_root=runtime_root,
        workspace=workspace,
        agent_id=agent_id,
        execute=execute,
        complete=complete,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"worker-turn failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def run_worker_turn_process(
    *,
    registry: Path,
    runtime_root: str | None,
    workspace: Path,
    agent_id: str,
    execute: bool,
    complete: bool = False,
) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(
        args,
        cwd=workspace,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


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
            output_dir="auto_research_lightweight_kernel",
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
            output_language="en",
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
        assert executed["live_evidence"]["evidence_source"] == "live_codex_lane_output", executed
        assert executed["live_evidence"]["dev_metric"] == 4.0, executed
        assert executed["successor_todos"]["schema_version"] == "multi_agent_role_successor_todos_v0", executed
        assert executed["successor_todos"]["source"] == "role_profile_todo_command_template", executed
        assert executed["successor_todos"]["role_id"] == "evidence_runner", executed
        assert executed["successor_todos"]["action"] == "run_dev_eval", executed
        successor = executed["successor_todos"]["successors"][0]
        assert successor["target_role_id"] == "evidence_runner", executed
        assert successor["condition"]["all"][0]["path"] == (
            "decision_summary.dev_promotion_candidate_count"
        ), executed
        assert successor["todo_command"].startswith("loopx todo add "), executed
        assert "--claimed-by codex-main-control" in successor["todo_command"], executed
        assert executed["followup"]["needed"] is True, executed
        assert executed["followup"]["action_kind"] == "run_holdout_eval", executed
        assert executed["followup"]["claimed_by"] == EVIDENCE_AGENT_ID, executed
        assert executed["followup"]["source"] == "role_profile_todo_command_template", executed
        assert executed["frontier"]["frontier"]["selected"]["claimed_by"] == EVIDENCE_AGENT_ID, executed
        assert payload["visible_launch"]["launch_result"]["worker_turn_executed"] is True, payload
        assert payload["visible_launch"]["launch_result"]["worker_turn_count"] == 3, payload
        assert payload["visible_worker_proof"]["visible_lanes_accepted"] is True, payload
        assert_public_safe(preview)
        assert_public_safe(curator_executed)
        assert_public_safe(mapper_executed)
        assert_public_safe(executed)
        assert_public_safe(payload["visible_launch"])

        supervisor = build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=FOUR_LANES,
            reasoning_effort="high",
        )
        four_lane_root = temp / "four-lane-queue"
        summary, four_registry, four_runtime_root = _seed_visible_demo_control_plane(
            demo_root=four_lane_root,
            goal_id=GOAL_ID,
            objective="Prove every visible auto-research role can run one LoopX-selected worker turn.",
            supervisor=supervisor,
        )
        evidence_seed = next(
            item for item in summary["seeded_todos"] if item["agent_id"] == EVIDENCE_AGENT_ID
        )
        alias_update = update_goal_todo(
            registry_path=four_registry,
            goal_id=GOAL_ID,
            todo_id=str(evidence_seed["todo_id"]),
            action_kind="run_read_only_adapter_tick",
        )
        assert alias_update["action_kind"] == "run_read_only_adapter_tick", alias_update
        four_workspace = four_lane_root / "visible-control-plane"
        for agent in [CURATOR_AGENT_ID, MAPPER_AGENT_ID, EVIDENCE_AGENT_ID]:
            turn = run_worker_turn(
                registry=four_registry,
                runtime_root=four_runtime_root,
                workspace=four_workspace,
                agent_id=agent,
                execute=True,
                complete=True,
            )
            if agent == EVIDENCE_AGENT_ID:
                assert turn["mode"] == "execute", turn
                assert turn["selected_action"] == "run_dev_eval", turn
                assert turn["frontier"]["frontier"]["selected"]["mechanism_family"] == (
                    "run_read_only_adapter_tick"
                ), turn
                assert turn["frontier"]["frontier"]["selected"]["allowed_action"] == "run_dev_eval", turn
                assert turn["live_evidence"]["written"] is True, turn
        projected_holdout = run_worker_turn(
            registry=four_registry,
            runtime_root=four_runtime_root,
            workspace=four_workspace,
            agent_id=EVIDENCE_AGENT_ID,
            execute=False,
        )
        assert projected_holdout["mode"] == "dry_run", projected_holdout
        assert projected_holdout["selected_action"] == "run_holdout_eval", projected_holdout
        assert projected_holdout["frontier"]["frontier"]["selected"]["claimed_by"] == (
            EVIDENCE_AGENT_ID
        ), projected_holdout
        assert projected_holdout["frontier"]["frontier"]["selected"]["todo_id"] == (
            turn["followup"]["todo_id"]
        ), projected_holdout
        holdout = run_worker_turn(
            registry=four_registry,
            runtime_root=four_runtime_root,
            workspace=four_workspace,
            agent_id=EVIDENCE_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert holdout["mode"] == "execute", holdout
        assert holdout["selected_action"] == "run_holdout_eval", holdout
        assert holdout["holdout_metric"] == 4.5, holdout
        assert holdout["completion"]["status"] == "done", holdout
        verifier = run_worker_turn(
            registry=four_registry,
            runtime_root=four_runtime_root,
            workspace=four_workspace,
            agent_id=VERIFIER_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert verifier["schema_version"] == "auto_research_worker_turn_v0", verifier
        assert verifier["mode"] == "execute", verifier
        assert verifier["selected_action"] == "summarize_evidence", verifier
        assert verifier["artifact"]["kind"] == "evaluation_summary", verifier
        assert verifier["artifact_status"] == "evaluation_summary_written", verifier
        assert verifier["claim_allowed"] is True, verifier
        assert verifier["promotion_decision_made"] is False, verifier
        assert verifier["followup"]["needed"] is False, verifier
        assert verifier["followup"]["reason"] in {
            "holdout_already_validated",
            "no_dev_promotion_candidate",
        }, verifier
        assert verifier["completion"]["status"] == "done", verifier
        assert_public_safe(verifier)
        generic = add_goal_todo(
            registry_path=four_registry,
            goal_id=GOAL_ID,
            role="agent",
            text="[P0-auto-research-verify] Verify supported dev evidence and close the promotion handoff.",
            task_class="advancement_task",
            claimed_by=VERIFIER_AGENT_ID,
            project=four_workspace,
        )
        assert generic["added"] is True, generic
        cleanup = run_worker_turn(
            registry=four_registry,
            runtime_root=four_runtime_root,
            workspace=four_workspace,
            agent_id=VERIFIER_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert cleanup["mode"] == "execute", cleanup
        if cleanup["selected_action"] == "write_evaluation_summary":
            assert cleanup["artifact_status"] == "evaluation_summary_written", cleanup
            assert cleanup["claim_allowed"] is True, cleanup
            cleanup = run_worker_turn(
                registry=four_registry,
                runtime_root=four_runtime_root,
                workspace=four_workspace,
                agent_id=VERIFIER_AGENT_ID,
                execute=True,
                complete=True,
            )
        assert cleanup["selected_action"] == "advance_todo", cleanup
        assert cleanup["artifact_status"] == "satisfied_generic_handoff_closed", cleanup
        assert cleanup["completion"]["status"] == "done", cleanup
        assert cleanup["decision_summary"]["validated_promotion_candidate_count"] == 1, cleanup
        assert_public_safe(holdout)
        assert_public_safe(cleanup)

        alt_supervisor = build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=[
                "codex-alt-curator:research-curator:research_curator",
                "codex-alt-mapper:hypothesis-mapper:hypothesis_mapper",
                f"{ALT_EVIDENCE_AGENT_ID}:evidence-runner:evidence_runner",
                "codex-alt-verifier:evidence-verifier:evidence_verifier",
            ],
            reasoning_effort="high",
        )
        alt_root = temp / "missing-successor-target"
        _alt_summary, alt_registry, alt_runtime_root = _seed_visible_demo_control_plane(
            demo_root=alt_root,
            goal_id=GOAL_ID,
            objective="Prove role-declared successor targets fail closed when the target agent is not registered.",
            supervisor=alt_supervisor,
        )
        alt_workspace = alt_root / "visible-control-plane"
        for agent in ["codex-alt-curator", "codex-alt-mapper"]:
            turn = run_worker_turn(
                registry=alt_registry,
                runtime_root=alt_runtime_root,
                workspace=alt_workspace,
                agent_id=agent,
                execute=True,
                complete=True,
            )
            assert turn["mode"] == "execute", turn
        missing_target = run_worker_turn_process(
            registry=alt_registry,
            runtime_root=alt_runtime_root,
            workspace=alt_workspace,
            agent_id=ALT_EVIDENCE_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert missing_target.returncode != 0, missing_target.stdout
        assert "successor target_agent_id 'codex-main-control' is not registered" in (
            missing_target.stdout + missing_target.stderr
        ), missing_target

    print("auto-research-worker-turn-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
