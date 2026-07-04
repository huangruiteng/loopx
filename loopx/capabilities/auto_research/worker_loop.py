from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from .worker_runtime import run_auto_research_worker_turn


AUTO_RESEARCH_WORKER_LOOP_SCHEMA_VERSION = "auto_research_worker_loop_v0"

AppendEvidence = Callable[[str], dict[str, object]]


def _compact_turn(turn: dict[str, object], *, round_index: int) -> dict[str, object]:
    completion = turn.get("completion") if isinstance(turn.get("completion"), dict) else {}
    append = turn.get("append") if isinstance(turn.get("append"), dict) else {}
    live_evidence = turn.get("live_evidence") if isinstance(turn.get("live_evidence"), dict) else {}
    evaluation_summary = (
        turn.get("evaluation_summary") if isinstance(turn.get("evaluation_summary"), dict) else {}
    )
    successor_todos = (
        turn.get("successor_todos") if isinstance(turn.get("successor_todos"), dict) else {}
    )
    successors = (
        successor_todos.get("successors")
        if isinstance(successor_todos.get("successors"), list)
        else []
    )
    return {
        "round": round_index,
        "agent_id": turn.get("agent_id"),
        "role_id": turn.get("role_id"),
        "mode": turn.get("mode"),
        "executed": bool(turn.get("executed")),
        "selected_todo_id": turn.get("selected_todo_id"),
        "selected_action": turn.get("selected_action"),
        "demo_iteration": turn.get("demo_iteration"),
        "completion_status": completion.get("status"),
        "appended_count": append.get("appended_count"),
        "dev_metric": turn.get("dev_metric"),
        "holdout_metric": turn.get("holdout_metric"),
        "claim_allowed": evaluation_summary.get("claim_allowed"),
        "best_holdout_metric": evaluation_summary.get("best_holdout_metric"),
        "holdout_metric_sequence": evaluation_summary.get("holdout_metric_sequence"),
        "holdout_improvement_count": evaluation_summary.get("holdout_improvement_count"),
        "live_evidence_written": bool(live_evidence.get("written")),
        "successor_todo_count": len(successors),
        "successor_todos": [
            {
                "todo_id": successor.get("todo_id"),
                "target_agent_id": successor.get("target_agent_id")
                or successor.get("claimed_by"),
                "target_role_id": successor.get("target_role_id"),
                "source_todo_id": successor.get("unblocks_todo_id"),
                "action_kind": successor.get("action_kind"),
            }
            for successor in successors
            if isinstance(successor, dict)
        ],
    }


def run_auto_research_worker_loop(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
    agent_ids: Sequence[str],
    objective: str,
    workspace: Path,
    output_dir: str = "auto_research_lightweight_kernel",
    evidence_dir: str = ".local/auto-research-worker",
    execute: bool = False,
    append_evidence: AppendEvidence | None = None,
    lane_count: int | None = None,
    visible_lanes_accepted: bool = False,
    live_evidence_output: str = "live-codex-e2e-evidence.public.json",
    complete_selected_todo: bool = False,
    max_rounds: int = 4,
) -> dict[str, object]:
    """Run repeated LoopX-selected worker turns for a fixed visible lane set.

    The loop is intentionally thin: it does not pick research work itself. Each
    pass delegates to worker-turn, so every lane re-reads quota/frontier before
    writing any evidence.
    """

    clean_agents = [agent.strip() for agent in agent_ids if agent.strip()]
    if not clean_agents:
        raise ValueError("worker-loop requires at least one --agent-id")
    if max_rounds < 1:
        raise ValueError("worker-loop requires --max-rounds >= 1")
    if execute and append_evidence is None:
        raise ValueError("worker-loop --execute requires an append_evidence callback")

    workspace = workspace.resolve()
    effective_lane_count = lane_count or len(clean_agents)
    turns: list[dict[str, object]] = []
    stop_reason = "max_rounds"
    for round_index in range(1, max_rounds + 1):
        round_turns: list[dict[str, object]] = []
        for agent_id in clean_agents:
            turn = run_auto_research_worker_turn(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                goal_id=goal_id,
                agent_id=agent_id,
                objective=objective,
                workspace=workspace,
                output_dir=output_dir,
                evidence_dir=evidence_dir,
                execute=execute,
                append_evidence=append_evidence if execute else None,
                lane_count=effective_lane_count,
                visible_lanes_accepted=visible_lanes_accepted,
                live_evidence_output=live_evidence_output,
                complete_selected_todo=complete_selected_todo,
            )
            compact = _compact_turn(turn, round_index=round_index)
            turns.append(compact)
            round_turns.append(compact)
        if not any(turn.get("mode") != "no_action" for turn in round_turns):
            stop_reason = "no_runnable_frontier"
            break
        if execute and not any(turn.get("executed") for turn in round_turns):
            stop_reason = "no_executed_turns"
            break

    executed_turns = [turn for turn in turns if turn.get("executed")]
    completed_turns = [turn for turn in turns if turn.get("completion_status") == "done"]
    selected_actions = [
        str(turn.get("selected_action"))
        for turn in turns
        if turn.get("selected_action")
    ]
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_WORKER_LOOP_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "goal_id": goal_id,
        "agent_ids": clean_agents,
        "round_count": max((int(turn["round"]) for turn in turns), default=0),
        "max_rounds": max_rounds,
        "stop_reason": stop_reason,
        "turn_count": len(turns),
        "executed_turn_count": len(executed_turns),
        "completed_turn_count": len(completed_turns),
        "selected_actions": selected_actions,
        "turns": turns,
        "public_boundary": {
            "source": "loopx_quota_frontier_worker_turns",
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }
