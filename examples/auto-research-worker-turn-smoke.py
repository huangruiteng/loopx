#!/usr/bin/env python3
"""Smoke-test that auto-research worker-turn does not fake research output."""

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
from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    build_auto_research_demo_supervisor_plan,
)
from loopx.capabilities.auto_research.evidence_packet import (  # noqa: E402
    build_auto_research_evidence_packet,
)
from loopx.capabilities.auto_research.preset import (  # noqa: E402
    auto_research_successor_specs_for_action,
)
from loopx.capabilities.auto_research.rollout_append import (  # noqa: E402
    append_auto_research_rollout_events,
)
from loopx.capabilities.multi_agent.role_successor import apply_role_successor_todos  # noqa: E402
from loopx.todos import add_goal_todo, complete_goal_todo  # noqa: E402

from examples.auto_research_lightweight_fixture import (  # noqa: E402
    AGENT_ID as EVIDENCE_AGENT_ID,
    GROUNDING_REF,
    HYPOTHESIS_ID,
    HYPOTHESIS_TEXT,
    MECHANISM_FAMILY,
    TODO_ID as EVIDENCE_TODO_ID,
    eval_result,
    research_contract,
)


GOAL_ID = "loopx-auto-research-demo"
CURATOR_AGENT_ID = "research-curator"
HYPOTHESIS_AGENT_ID = "hypothesis-proposer"
EXECUTOR_AGENT_ID = "research-executor"
EVALUATOR_AGENT_ID = "evaluator-promoter"
LANES = [
    "research-curator:research-curator:research_curator",
    "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
    "research-executor:research-executor:research_executor",
    "evaluator-promoter:evaluator-promoter:evaluator_promoter",
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
        "4",
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


def assert_manual_research_required(payload: dict[str, Any], *, action: str) -> None:
    assert payload["schema_version"] == "auto_research_worker_turn_v0", payload
    assert payload["mode"] == "manual_research_required", payload
    assert payload["selected_action"] == action, payload
    assert payload["executed"] is False, payload
    assert payload["manual_research_required"] is True, payload
    assert payload["completion"]["executed"] is False, payload
    assert payload["public_boundary"]["fake_metrics_recorded"] is False, payload
    assert "dev_metric" not in payload, payload
    assert "holdout_metric" not in payload, payload
    assert "live_evidence" not in payload, payload
    assert_public_safe(payload)


def assert_no_action(payload: dict[str, Any], *, agent_id: str) -> None:
    assert payload["schema_version"] == "auto_research_worker_turn_v0", payload
    assert payload["mode"] == "no_action", payload
    assert payload["agent_id"] == agent_id, payload
    assert payload["executed"] is False, payload
    assert payload["frontier"]["frontier"]["selected"] is None, payload
    assert payload["frontier"]["frontier"]["runnable_count"] == 0, payload
    assert_public_safe(payload)


def write_summary_state(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Auto Research Worker Summary Smoke",
                "",
                "## User Todo / Owner Review Reading Queue",
                "",
                "## Agent Todo",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_registry(path: Path, *, project: Path, state_file: Path, runtime_root: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "auto_research_smoke",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_file),
                        "coordination": {
                            "primary_agent": CURATOR_AGENT_ID,
                            "registered_agents": [
                                CURATOR_AGENT_ID,
                                HYPOTHESIS_AGENT_ID,
                                EXECUTOR_AGENT_ID,
                                EVALUATOR_AGENT_ID,
                            ]
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


def append_real_fixture_evidence(*, registry: Path, runtime_root: Path, temp: Path) -> None:
    packet = build_auto_research_evidence_packet(
        contract=research_contract(goal_id=GOAL_ID),
        eval_results=[eval_result("dev"), eval_result("holdout")],
        hypothesis_id=HYPOTHESIS_ID,
        todo_id=EVIDENCE_TODO_ID,
        agent_id=EVIDENCE_AGENT_ID,
        claimed_by=EVIDENCE_AGENT_ID,
        mechanism_family=MECHANISM_FAMILY,
        hypothesis=HYPOTHESIS_TEXT,
        grounding_refs=[GROUNDING_REF],
        branch_ref="codex/auto-research-worker-turn-smoke",
    )
    packet_path = temp / "real-evidence-packet.public.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    appended = append_auto_research_rollout_events(
        packet_path=str(packet_path),
        registry_path=registry,
        runtime_root_arg=str(runtime_root),
        dry_run=False,
    )
    assert appended["appended_count"] == 3, appended
    assert_public_safe(appended)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        supervisor = build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=LANES,
            session_name="loopx-auto-research-worker-turn-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
        )
        visible_control, registry, runtime_root = _seed_visible_demo_control_plane(
            demo_root=temp,
            goal_id=GOAL_ID,
            objective="Verify visible auto-research requires real role-authored evidence.",
            supervisor=supervisor,
        )
        seeded_todos = visible_control["seeded_todos"]
        executor_seed = next(item for item in seeded_todos if item["agent_id"] == EXECUTOR_AGENT_ID)
        evaluator_seed = next(item for item in seeded_todos if item["agent_id"] == EVALUATOR_AGENT_ID)
        assert evaluator_seed["resume_when"] == f"todo_done:{executor_seed['todo_id']}", visible_control
        workspace = temp / "visible-workspace"
        workspace.mkdir()

        curator_preview = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=CURATOR_AGENT_ID,
            execute=False,
        )
        assert curator_preview["mode"] == "dry_run", curator_preview
        assert curator_preview["selected_action"] == "write_research_contract", curator_preview

        curator_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=CURATOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert_manual_research_required(curator_execute, action="write_research_contract")

        executor_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EXECUTOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert_no_action(executor_execute, agent_id=EXECUTOR_AGENT_ID)

        evaluator_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EVALUATOR_AGENT_ID,
            execute=True,
            complete=False,
        )
        assert_no_action(evaluator_execute, agent_id=EVALUATOR_AGENT_ID)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        project = temp / "project"
        project.mkdir()
        state_file = project / "ACTIVE_GOAL_STATE.md"
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        write_summary_state(state_file)
        write_registry(registry, project=project, state_file=state_file, runtime_root=runtime_root)
        summary_todo = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text=(
                "[P0-auto-research-live] Summarize visible held-out evidence and "
                "open the next research round."
            ),
            task_class="advancement_task",
            action_kind="summarize_evidence",
            claimed_by=EVALUATOR_AGENT_ID,
            dry_run=False,
        )
        summary_todo_id = summary_todo["todo_id"]
        append_real_fixture_evidence(registry=registry, runtime_root=runtime_root, temp=temp)
        workspace = project / "visible-workspace"
        workspace.mkdir()

        evaluator_summary = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EVALUATOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert evaluator_summary["mode"] == "execute", evaluator_summary
        assert evaluator_summary["selected_action"] == "summarize_evidence", evaluator_summary
        successor_todos = evaluator_summary["successor_todos"]
        assert successor_todos["executed"] is True, successor_todos
        successor_ids = [
            successor["todo_id"]
            for successor in successor_todos["successors"]
            if successor.get("todo_id")
        ]
        assert len(successor_ids) == 1, successor_todos
        assert successor_todos["successors"][0]["claimed_by"] == CURATOR_AGENT_ID, successor_todos
        assert successor_todos["successors"][0]["action_kind"] == "review_research_contract", successor_todos
        completion = evaluator_summary["completion"]
        assert completion["executed"] is True, completion
        assert completion["successor_todo_ids"] == successor_ids, evaluator_summary
        state_text = state_file.read_text(encoding="utf-8")
        assert f"todo_id={summary_todo_id} status=done" in state_text, state_text
        assert "no_followup=true" not in state_text, state_text
        for successor_id in successor_ids:
            assert successor_id in state_text, state_text
        assert_public_safe(evaluator_summary)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        project = temp / "project"
        project.mkdir()
        state_file = project / "ACTIVE_GOAL_STATE.md"
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        write_summary_state(state_file)
        write_registry(registry, project=project, state_file=state_file, runtime_root=runtime_root)
        promotion_todo = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text=(
                "[P0-auto-research-live] Review promotion readiness and "
                "open the next research round when acceptance is not met."
            ),
            task_class="advancement_task",
            action_kind="review_promotion_readiness",
            claimed_by=EVALUATOR_AGENT_ID,
            dry_run=False,
        )
        promotion_todo_id = promotion_todo["todo_id"]
        append_real_fixture_evidence(registry=registry, runtime_root=runtime_root, temp=temp)
        workspace = project / "visible-workspace"
        workspace.mkdir()

        promotion_review = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EVALUATOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert promotion_review["mode"] == "execute", promotion_review
        assert promotion_review["selected_action"] == "review_promotion_readiness", promotion_review
        assert promotion_review["evaluation_summary"]["holdout_improvement_count"] == 1, promotion_review
        successor_todos = promotion_review["successor_todos"]
        assert successor_todos["executed"] is True, successor_todos
        successor_ids = [
            successor["todo_id"]
            for successor in successor_todos["successors"]
            if successor.get("todo_id")
        ]
        assert len(successor_ids) == 1, successor_todos
        assert successor_todos["successors"][0]["claimed_by"] == CURATOR_AGENT_ID, successor_todos
        assert successor_todos["successors"][0]["action_kind"] == "review_research_contract", successor_todos
        completion = promotion_review["completion"]
        assert completion["executed"] is True, completion
        assert completion["successor_todo_ids"] == successor_ids, promotion_review
        state_text = state_file.read_text(encoding="utf-8")
        assert f"todo_id={promotion_todo_id} status=done" in state_text, state_text
        assert "no_followup=true" not in state_text, state_text
        for successor_id in successor_ids:
            assert successor_id in state_text, state_text
        assert_public_safe(promotion_review)

        curator_handoff = apply_role_successor_todos(
            registry_path=registry,
            goal_id=GOAL_ID,
            source_todo_id=successor_ids[0],
            current_agent_id=CURATOR_AGENT_ID,
            role_id="research_curator",
            action="review_research_contract",
            successor_specs=auto_research_successor_specs_for_action(
                role_id="research_curator",
                action="review_research_contract",
            ),
            decision_summary={
                "validated_promotion_candidate_count": 1,
                "holdout_improvement_count": 1,
            },
            execute=True,
        )
        assert curator_handoff["executed"] is True, curator_handoff
        curator_successor_ids = [
            successor["todo_id"]
            for successor in curator_handoff["successors"]
            if successor.get("todo_id")
        ]
        assert len(curator_successor_ids) == 1, curator_handoff
        assert curator_handoff["successors"][0]["claimed_by"] == HYPOTHESIS_AGENT_ID, curator_handoff
        assert curator_handoff["successors"][0]["action_kind"] == "propose_hypothesis", curator_handoff
        curator_completion = complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=successor_ids[0],
            role="agent",
            claimed_by=CURATOR_AGENT_ID,
            note="auto-research curator review routed the next hypothesis round",
            evidence="state-summary agent=research-curator action=review_research_contract linked next hypothesis successor",
            successor_todo_ids=curator_successor_ids,
            side_agent_self_merged=True,
            dry_run=False,
        )
        assert curator_completion["completed"] is True, curator_completion
        assert curator_completion["successor_todo_ids"] == curator_successor_ids, curator_completion
        state_text = state_file.read_text(encoding="utf-8")
        assert "no_followup=true" not in state_text, state_text
        for successor_id in curator_successor_ids:
            assert successor_id in state_text, state_text
        assert_public_safe(curator_handoff)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        project = temp / "project"
        project.mkdir()
        state_file = project / "ACTIVE_GOAL_STATE.md"
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        write_summary_state(state_file)
        write_registry(registry, project=project, state_file=state_file, runtime_root=runtime_root)
        generic_todo = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text=(
                "[P1] Fix auto-research completion projection after validated "
                "promotion and holdout evidence."
            ),
            task_class="advancement_task",
            claimed_by=EVALUATOR_AGENT_ID,
            dry_run=False,
        )
        generic_todo_id = generic_todo["todo_id"]
        append_real_fixture_evidence(registry=registry, runtime_root=runtime_root, temp=temp)
        workspace = project / "visible-workspace"
        workspace.mkdir()

        generic_turn = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EVALUATOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert generic_turn["mode"] == "unsupported_action", generic_turn
        assert generic_turn["selected_action"] == "advance_todo", generic_turn
        assert generic_turn["executed"] is False, generic_turn
        state_text = state_file.read_text(encoding="utf-8")
        assert f"todo_id={generic_todo_id} status=done" not in state_text, state_text
        assert "satisfied_generic_handoff_closed" not in json.dumps(generic_turn), generic_turn
        assert_public_safe(generic_turn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
