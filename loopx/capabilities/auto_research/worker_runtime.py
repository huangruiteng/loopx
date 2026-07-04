from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .defaults import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
)
from .evidence_packet import (
    RESEARCH_CONTRACT_SCHEMA_VERSION,
    RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
    load_auto_research_evidence_packet_inputs,
    validate_research_hypothesis,
)
from .kernel import (
    LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION,
    lightweight_hypothesis,
    run_lightweight_auto_research,
)
from .live_evidence import (
    LIVE_CODEX_E2E_DEFAULT_OUTPUT,
    build_live_codex_e2e_evidence_from_packet,
)
from .preset import (
    auto_research_role_id_for_action,
    auto_research_successor_specs_for_action,
)
from .research_state import (
    build_live_auto_research_projection,
    build_research_decision_candidates,
    build_research_evidence_graph_from_rollout_events,
    normalize_auto_research_action,
)
from ..multi_agent.role_successor import (
    apply_role_successor_todos,
    first_successor_followup,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import load_rollout_events, rollout_event_log_path
from ...status import collect_status
from ...todos import complete_goal_todo


AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION = "auto_research_worker_turn_v0"
AUTO_RESEARCH_WORKER_FRONTIER_SCHEMA_VERSION = "auto_research_worker_frontier_v0"
SUPPORTED_WORKER_ACTIONS = {
    "write_research_contract",
    "propose_hypothesis",
    "run_dev_eval",
    "run_holdout_eval",
    "write_evidence",
    "classify_evidence",
    "summarize_evidence",
    "write_evaluation_summary",
}
GENERIC_VERIFIER_HANDOFF_KEYWORDS = (
    "verify",
    "verifier",
    "validate",
    "validation",
    "evidence",
    "holdout",
    "promotion",
    "promote",
)

AppendEvidence = Callable[[str], dict[str, object]]
AUTO_RESEARCH_BUILTIN_KERNEL_MODE = "builtin_lightweight_metric_kernel"
AUTO_RESEARCH_BUILTIN_EVAL_SCHEMA_VERSION = "auto_research_lightweight_eval_result_v0"
AUTO_RESEARCH_DEMO_METRIC_NAME = "demo_quality_score"
AUTO_RESEARCH_DEMO_BASELINE = 1.0
AUTO_RESEARCH_DEMO_MECHANISM_FAMILY = "state_a2a_iteration"
AUTO_RESEARCH_DEMO_CANDIDATE_KEY = "state_a2a_round"
AUTO_RESEARCH_DEMO_HYPOTHESIS_TEXT = (
    "Use a small state-mediated handoff loop so each role can improve the shared candidate."
)


def _slug(value: object, *, default: str = "item") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-._")
    return text[:80] or default


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_summary(kind: str, *, filename: str) -> dict[str, object]:
    return {
        "kind": kind,
        "filename": filename,
        "paths_are_local_only": True,
    }


def _demo_research_contract(*, goal_id: str, objective: str) -> dict[str, object]:
    return {
        "schema_version": RESEARCH_CONTRACT_SCHEMA_VERSION,
        "goal_id": goal_id,
        "research_objective": objective,
        "editable_scope": [
            "candidate_strategy",
            "hypothesis_text",
            "todo_handoff",
        ],
        "protected_scope": [
            "metric_definition",
            "baseline_metric",
            "holdout_split",
        ],
        "metric": {
            "name": AUTO_RESEARCH_DEMO_METRIC_NAME,
            "direction": "maximize",
            "baseline": AUTO_RESEARCH_DEMO_BASELINE,
        },
        "dev_eval": "builtin lightweight metric evaluator on dev split",
        "holdout_eval": "builtin lightweight metric evaluator on holdout split",
        "promotion_policy": "dev_and_holdout_improved",
    }


def _demo_metric_evaluator(hypothesis: dict[str, Any], split: str) -> dict[str, object]:
    candidate_key = str(hypothesis.get("candidate_key") or AUTO_RESEARCH_DEMO_CANDIDATE_KEY)
    metric_by_split = {
        "dev": 4.0,
        "holdout": 4.5,
    }
    metric = metric_by_split.get(split, AUTO_RESEARCH_DEMO_BASELINE)
    return {
        "metric": metric,
        "exact": True,
        "protected_scope_clean": True,
        "strategy": candidate_key,
        "artifact_refs": [f"public_metric:{split}:{candidate_key}"],
        "result_source": "builtin_metric_evaluator",
    }


def _demo_kernel_result(*, goal_id: str, todo_id: str, agent_id: str) -> dict[str, object]:
    hypothesis = lightweight_hypothesis(
        hypothesis_id=f"hyp_{_slug(todo_id, default='todo')}_{AUTO_RESEARCH_DEMO_CANDIDATE_KEY}",
        todo_id=todo_id,
        claimed_by=agent_id,
        text=AUTO_RESEARCH_DEMO_HYPOTHESIS_TEXT,
        candidate_key=AUTO_RESEARCH_DEMO_CANDIDATE_KEY,
    )
    return run_lightweight_auto_research(
        goal_id=goal_id,
        hypotheses=[hypothesis],
        evaluate=_demo_metric_evaluator,
        baseline=AUTO_RESEARCH_DEMO_BASELINE,
        direction="maximize",
        max_dev_rounds=1,
    )


def _demo_eval_result(
    *,
    goal_id: str,
    todo_id: str,
    agent_id: str,
    split: str,
) -> dict[str, object]:
    kernel_result = _demo_kernel_result(goal_id=goal_id, todo_id=todo_id, agent_id=agent_id)
    if kernel_result.get("schema_version") != LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION:
        raise ValueError("unexpected lightweight auto-research kernel result")
    matching = [
        event
        for event in kernel_result.get("evidence") or []
        if isinstance(event, dict) and event.get("split") == split
    ]
    if not matching:
        raise ValueError(f"lightweight auto-research kernel produced no {split} evidence")
    event = matching[0]
    improved = event.get("status") == "improved"
    return {
        "schema_version": AUTO_RESEARCH_BUILTIN_EVAL_SCHEMA_VERSION,
        "split": split,
        "metric": {
            "name": AUTO_RESEARCH_DEMO_METRIC_NAME,
            "value": event.get("metric"),
            "direction": event.get("direction") or "maximize",
            "baseline": event.get("baseline"),
        },
        "eval_status": "scored",
        "primary_metric_status": "improved" if improved else "regressed",
        "artifact_refs": event.get("artifact_refs") or [],
        "protected_scope_clean": bool(event.get("protected_scope_clean")),
        "no_upload": True,
        "kernel_schema_version": kernel_result.get("schema_version"),
        "result_source": event.get("result_source"),
    }


def _write_contract_artifact(
    *,
    output_path: Path,
    goal_id: str,
    objective: str,
    todo_id: str,
    agent_id: str,
) -> dict[str, object]:
    contract = _demo_research_contract(goal_id=goal_id, objective=objective)
    artifact = {
        "ok": True,
        "schema_version": "auto_research_worker_contract_artifact_v0",
        "goal_id": goal_id,
        "todo_id": todo_id,
        "agent_id": agent_id,
        "research_contract": contract,
        "summary": {
            "status": "contract_written",
            "metric": contract.get("metric"),
            "promotion_policy": contract.get("promotion_policy"),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
    _write_json(output_path, artifact)
    return artifact


def _write_hypothesis_artifact(
    *,
    output_path: Path,
    goal_id: str,
    todo_id: str,
    agent_id: str,
) -> dict[str, object]:
    hypothesis = validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": f"hyp_{_slug(todo_id, default='todo')}_{AUTO_RESEARCH_DEMO_CANDIDATE_KEY}",
            "parent_hypothesis_id": None,
            "todo_id": todo_id,
            "claimed_by": agent_id,
            "mechanism_family": AUTO_RESEARCH_DEMO_MECHANISM_FAMILY,
            "hypothesis": AUTO_RESEARCH_DEMO_HYPOTHESIS_TEXT,
            "status": "active",
            "grounding_refs": ["kernel:state_a2a_metric_demo"],
            "blocked_by": [],
        }
    )
    artifact = {
        "ok": True,
        "schema_version": "auto_research_worker_hypothesis_artifact_v0",
        "goal_id": goal_id,
        "todo_id": todo_id,
        "agent_id": agent_id,
        "hypothesis": hypothesis,
        "summary": {
            "status": "hypothesis_mapped",
            "hypothesis_id": hypothesis["hypothesis_id"],
            "mechanism_family": hypothesis["mechanism_family"],
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
    _write_json(output_path, artifact)
    return artifact


def _write_evaluation_summary_artifact(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_path: Path,
    goal_id: str,
    todo_id: str,
    agent_id: str,
) -> dict[str, object]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    rollout_events = load_rollout_events(rollout_event_log_path(runtime_root, goal_id))
    graph = build_research_evidence_graph_from_rollout_events(
        goal_id=goal_id,
        rollout_events=rollout_events,
    )
    decisions = build_research_decision_candidates(graph)
    artifact = {
        "ok": True,
        "schema_version": "auto_research_worker_evaluation_summary_v0",
        "goal_id": goal_id,
        "todo_id": todo_id,
        "agent_id": agent_id,
        "evidence_graph_summary": {
            "event_count": graph.get("event_count"),
            "hypothesis_count": graph.get("hypothesis_count"),
            "best_dev_metric": graph.get("best_dev_metric"),
            "best_holdout_metric": graph.get("best_holdout_metric"),
            "holdout_improved": graph.get("holdout_improved"),
            "negative_evidence_count": graph.get("negative_evidence_count"),
        },
        "decision_summary": {
            "dev_promotion_candidate_count": len(decisions.get("dev_promotion_candidates") or []),
            "validated_promotion_candidate_count": len(decisions.get("validated_promotion_candidates") or []),
            "promotion_candidate_count": len(decisions.get("promotion_candidates") or []),
            "retirement_candidate_count": len(decisions.get("retirement_candidates") or []),
        },
        "summary": {
            "status": "evaluation_summary_written",
            "claim_allowed": bool(decisions.get("validated_promotion_candidates")),
            "promotion_decision_made": False,
        },
        "public_boundary": {
            "source": "loopx_rollout_event_log",
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
    _write_json(output_path, artifact)
    return artifact


def _select_holdout_candidate(graph: dict[str, object]) -> dict[str, object]:
    metric = graph.get("metric") if isinstance(graph.get("metric"), dict) else {}
    direction = str(metric.get("direction") or "maximize")
    candidates: list[dict[str, object]] = []
    for item in graph.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        if item.get("best_holdout_metric") is not None:
            continue
        if int(item.get("negative_evidence_count") or 0) > 0:
            continue
        if item.get("best_dev_metric") is None:
            continue
        if not item.get("dev_improved"):
            continue
        candidates.append(item)
    if not candidates:
        raise ValueError("no dev-supported auto-research hypothesis is ready for holdout validation")
    reverse = direction != "minimize"
    return sorted(
        candidates,
        key=lambda item: float(item.get("best_dev_metric") or 0.0),
        reverse=reverse,
    )[0]


def _maybe_add_role_successor_todos(
    *,
    registry_path: Path,
    goal_id: str,
    source_todo_id: str,
    agent_id: str,
    role_id: str,
    action: str,
    decision_summary: dict[str, object],
    execute: bool,
) -> dict[str, object]:
    return apply_role_successor_todos(
        registry_path=registry_path,
        goal_id=goal_id,
        source_todo_id=source_todo_id,
        current_agent_id=agent_id,
        role_id=role_id,
        action=action,
        successor_specs=auto_research_successor_specs_for_action(role_id=role_id, action=action),
        decision_summary=decision_summary,
        execute=execute,
    )


def _generic_handoff_is_satisfied(
    *,
    selected: dict[str, object],
    evidence_graph: dict[str, object],
    decisions: dict[str, list[dict[str, object]]],
) -> bool:
    if not decisions.get("validated_promotion_candidates"):
        return False
    if not evidence_graph.get("holdout_improved"):
        return False
    selected_text = " ".join(
        str(selected.get(key) or "")
        for key in ("title", "mechanism_family", "source_kind", "todo_id")
    ).lower()
    return any(keyword in selected_text for keyword in GENERIC_VERIFIER_HANDOFF_KEYWORDS)


def _maybe_close_satisfied_generic_handoff(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
    todo_id: str,
    agent_id: str,
    selected: dict[str, object],
    action: str,
    execute: bool,
    complete_selected_todo: bool,
    frontier_packet: dict[str, object],
) -> dict[str, object] | None:
    if action != "advance_todo":
        return None
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    graph = build_research_evidence_graph_from_rollout_events(
        goal_id=goal_id,
        rollout_events=load_rollout_events(rollout_event_log_path(runtime_root, goal_id)),
    )
    decisions = build_research_decision_candidates(graph)
    if not _generic_handoff_is_satisfied(
        selected=selected,
        evidence_graph=graph,
        decisions=decisions,
    ):
        return None

    completion = (
        _complete_selected_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
            action="satisfied_generic_handoff",
            execute=True,
        )
        if execute and complete_selected_todo
        else {"requested": complete_selected_todo, "executed": False}
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "selected_todo_id": todo_id,
        "selected_action": action,
        "executed": bool(execute and complete_selected_todo),
        "artifact_status": "satisfied_generic_handoff_closed",
        "decision_summary": {
            "validated_promotion_candidate_count": len(decisions.get("validated_promotion_candidates") or []),
            "holdout_improved": bool(graph.get("holdout_improved")),
        },
        "completion": completion,
        "frontier": frontier_packet,
        "public_boundary": {
            "source": "rollout_event_log_and_todo_projection",
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }


def _complete_selected_todo(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    agent_id: str,
    action: str,
    execute: bool,
) -> dict[str, object]:
    if not execute:
        return {"requested": True, "executed": False}
    result = complete_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
        role="agent",
        claimed_by=agent_id,
        note=f"auto-research worker-turn completed {action}",
        evidence=(
            f"worker-turn agent={agent_id} action={action} wrote public-safe local artifact "
            "and obeyed quota/frontier before completion"
        ),
        no_followup=True,
        side_agent_self_merged=True,
        dry_run=False,
    )
    return {
        "requested": True,
        "executed": True,
        "ok": bool(result.get("ok")),
        "changed": bool(result.get("changed")),
        "todo_id": result.get("todo_id"),
        "status": "done" if result.get("completed") else None,
        "side_agent_self_merged": bool(result.get("side_agent_self_merged")),
    }


def load_auto_research_worker_frontier(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
    agent_id: str,
    workspace: Path,
) -> dict[str, object]:
    """Read the same quota/frontier surfaces a visible worker must obey."""

    status_payload = collect_status(
        registry_path=registry_path,
        runtime_root_override=runtime_root_arg,
        scan_roots=[workspace],
        limit=5,
        goal_id=goal_id,
    )
    quota_payload = build_quota_should_run(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    projection = build_live_auto_research_projection(
        goal_id=goal_id,
        agent_id=agent_id,
        quota_payload=quota_payload,
        rollout_events=load_rollout_events(rollout_event_log_path(runtime_root, goal_id)),
    )
    frontier = projection["frontier"]
    selected = frontier.get("selected") if isinstance(frontier, dict) else None
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_WORKER_FRONTIER_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "quota": {
            "ok": bool(quota_payload.get("ok")),
            "should_run": bool(quota_payload.get("should_run")),
            "state": quota_payload.get("state"),
            "user_action_required": bool(
                ((quota_payload.get("interaction_contract") or {}).get("user_channel") or {}).get(
                    "action_required"
                )
            ),
        },
        "frontier": {
            "selected": selected,
            "runnable_count": len(frontier.get("runnable") or []) if isinstance(frontier, dict) else 0,
            "blocked_count": len(frontier.get("blocked") or []) if isinstance(frontier, dict) else 0,
            "source_kind": frontier.get("source_kind") if isinstance(frontier, dict) else None,
        },
        "public_boundary": {
            "source": "loopx_quota_and_auto_research_frontier",
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
        },
    }


def run_auto_research_worker_turn(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    agent_id: str,
    objective: str = AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    workspace: Path,
    output_dir: str = "auto_research_lightweight_kernel",
    evidence_dir: str = ".local/auto-research-worker",
    execute: bool = False,
    append_evidence: AppendEvidence | None = None,
    lane_count: int = 1,
    visible_lanes_accepted: bool = False,
    live_evidence_output: str = LIVE_CODEX_E2E_DEFAULT_OUTPUT,
    complete_selected_todo: bool = False,
) -> dict[str, object]:
    """Run one LoopX-selected visible worker action.

    The worker does not choose its own work. It reads quota/frontier, checks the
    selected action, then performs one small public-safe research turn.
    """

    workspace = workspace.resolve()
    frontier_packet = load_auto_research_worker_frontier(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=goal_id,
        agent_id=agent_id,
        workspace=workspace,
    )
    selected = frontier_packet["frontier"].get("selected") if isinstance(frontier_packet["frontier"], dict) else None
    raw_action = str((selected or {}).get("allowed_action") or "")
    action = normalize_auto_research_action(raw_action)
    todo_id = str((selected or {}).get("todo_id") or "")
    if not selected or not todo_id:
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "no_action",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "executed": False,
            "frontier": frontier_packet,
        }
    cleanup = _maybe_close_satisfied_generic_handoff(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=goal_id,
        todo_id=todo_id,
        agent_id=agent_id,
        selected=selected,
        action=action,
        execute=execute,
        complete_selected_todo=complete_selected_todo,
        frontier_packet=frontier_packet,
    )
    if cleanup is not None:
        return cleanup
    if action not in SUPPORTED_WORKER_ACTIONS:
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "unsupported_action",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "supported_actions": sorted(SUPPORTED_WORKER_ACTIONS),
            "executed": False,
            "frontier": frontier_packet,
        }
    if not execute:
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "dry_run",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "would_execute": action,
            "completion": {"requested": complete_selected_todo, "executed": False},
            "frontier": frontier_packet,
        }
    if action in {"run_dev_eval", "run_holdout_eval", "write_evidence"} and append_evidence is None:
        raise ValueError("execute requires an append_evidence callback")

    run_dir = workspace / evidence_dir / _slug(agent_id, default="agent") / _slug(todo_id, default="todo")
    contract_artifact_path = run_dir / "research-contract.public.json"
    contract_input_path = run_dir / "research-contract-input.public.json"
    hypothesis_artifact_path = run_dir / "hypothesis.public.json"
    evaluation_summary_path = run_dir / "evaluation-summary.public.json"
    dev_result_path = run_dir / "dev-result.public.json"
    holdout_result_path = run_dir / "holdout-result.public.json"
    evidence_packet_path = run_dir / "evidence.public.json"
    append_result_path = run_dir / "append-result.public.json"
    live_evidence_path = run_dir / live_evidence_output

    if action == "write_research_contract":
        artifact = _write_contract_artifact(
            output_path=contract_artifact_path,
            goal_id=goal_id,
            objective=objective,
            todo_id=todo_id,
            agent_id=agent_id,
        )
        completion = (
            _complete_selected_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                todo_id=todo_id,
                agent_id=agent_id,
                action=action,
                execute=True,
            )
            if complete_selected_todo
            else {"requested": False}
        )
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "execute",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "executed": True,
            "kernel_mode": AUTO_RESEARCH_BUILTIN_KERNEL_MODE,
            "artifact": _artifact_summary("research_contract", filename="research-contract.public.json"),
            "artifact_status": artifact["summary"]["status"],
            "completion": completion,
            "frontier": frontier_packet,
            "public_boundary": {
                "raw_logs_recorded": False,
                "private_artifacts_recorded": False,
                "absolute_paths_recorded": False,
                "credentials_recorded": False,
            },
        }

    if action == "propose_hypothesis":
        artifact = _write_hypothesis_artifact(
            output_path=hypothesis_artifact_path,
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
        )
        completion = (
            _complete_selected_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                todo_id=todo_id,
                agent_id=agent_id,
                action=action,
                execute=True,
            )
            if complete_selected_todo
            else {"requested": False}
        )
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "execute",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "executed": True,
            "kernel_mode": AUTO_RESEARCH_BUILTIN_KERNEL_MODE,
            "artifact": _artifact_summary("research_hypothesis", filename="hypothesis.public.json"),
            "artifact_status": artifact["summary"]["status"],
            "hypothesis_id": artifact["summary"]["hypothesis_id"],
            "completion": completion,
            "frontier": frontier_packet,
            "public_boundary": {
                "raw_logs_recorded": False,
                "private_artifacts_recorded": False,
                "absolute_paths_recorded": False,
                "credentials_recorded": False,
            },
        }

    if action in {"classify_evidence", "summarize_evidence", "write_evaluation_summary"}:
        artifact = _write_evaluation_summary_artifact(
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            output_path=evaluation_summary_path,
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
        )
        role_id = auto_research_role_id_for_action(action)
        successor_todos = _maybe_add_role_successor_todos(
            registry_path=registry_path,
            goal_id=goal_id,
            source_todo_id=todo_id,
            agent_id=agent_id,
            role_id=role_id,
            action=action,
            decision_summary=artifact["decision_summary"],
            execute=True,
        )
        followup = first_successor_followup(successor_todos)
        completion = (
            _complete_selected_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                todo_id=todo_id,
                agent_id=agent_id,
                action=action,
                execute=True,
            )
            if complete_selected_todo
            else {"requested": False}
        )
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "execute",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "executed": True,
            "kernel_mode": AUTO_RESEARCH_BUILTIN_KERNEL_MODE,
            "artifact": _artifact_summary("evaluation_summary", filename="evaluation-summary.public.json"),
            "artifact_status": artifact["summary"]["status"],
            "claim_allowed": artifact["summary"]["claim_allowed"],
            "promotion_decision_made": artifact["summary"]["promotion_decision_made"],
            "role_id": role_id,
            "successor_todos": successor_todos,
            "followup": followup,
            "completion": completion,
            "frontier": frontier_packet,
            "public_boundary": {
                "raw_logs_recorded": False,
                "private_artifacts_recorded": False,
                "absolute_paths_recorded": False,
                "credentials_recorded": False,
            },
        }

    if action == "run_holdout_eval":
        registry = load_registry(registry_path)
        runtime_root = resolve_runtime_root(registry, runtime_root_arg)
        rollout_events = load_rollout_events(rollout_event_log_path(runtime_root, goal_id))
        graph = build_research_evidence_graph_from_rollout_events(
            goal_id=goal_id,
            rollout_events=rollout_events,
        )
        try:
            candidate = _select_holdout_candidate(graph)
        except ValueError as exc:
            return {
                "ok": True,
                "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
                "mode": "blocked",
                "goal_id": goal_id,
                "agent_id": agent_id,
                "selected_todo_id": todo_id,
                "selected_action": action,
                "executed": False,
                "blocker": "waiting_for_dev_evidence",
                "blocker_detail": str(exc),
                "completion": {"requested": complete_selected_todo, "executed": False},
                "frontier": frontier_packet,
                "public_boundary": {
                    "raw_logs_recorded": False,
                    "private_artifacts_recorded": False,
                    "absolute_paths_recorded": False,
                    "credentials_recorded": False,
                },
            }
        contract_artifact = _write_contract_artifact(
            output_path=contract_artifact_path,
            goal_id=goal_id,
            objective=objective,
            todo_id=todo_id,
            agent_id=agent_id,
        )
        _write_json(contract_input_path, contract_artifact["research_contract"])
        holdout_result = _demo_eval_result(
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
            split="holdout",
        )
        _write_json(holdout_result_path, holdout_result)
        packet = load_auto_research_evidence_packet_inputs(
            contract_path=contract_input_path,
            eval_result_paths=[holdout_result_path],
            hypothesis_id=str(candidate["hypothesis_id"]),
            todo_id=str(candidate["todo_id"]),
            agent_id=agent_id,
            claimed_by=str(candidate.get("claimed_by") or agent_id),
            mechanism_family=str(candidate.get("mechanism_family") or AUTO_RESEARCH_DEMO_MECHANISM_FAMILY),
            hypothesis=str(candidate.get("hypothesis") or AUTO_RESEARCH_DEMO_HYPOTHESIS_TEXT),
            parent_hypothesis_id=str(candidate.get("parent_hypothesis_id") or "") or None,
            grounding_refs=[
                str(ref)
                for ref in candidate.get("grounding_refs") or ["kernel:state_a2a_metric_demo"]
                if str(ref).strip()
            ],
            novelty_audit_ref=str(candidate.get("novelty_audit_ref") or "") or None,
            attempt_start=int(candidate.get("evidence_event_count") or 1) + 1,
        )
        _write_json(evidence_packet_path, packet)
        append_result = append_evidence(str(evidence_packet_path))
        _write_json(append_result_path, append_result)
        summary_artifact = _write_evaluation_summary_artifact(
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            output_path=evaluation_summary_path,
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
        )
        role_id = auto_research_role_id_for_action(action)
        successor_todos = _maybe_add_role_successor_todos(
            registry_path=registry_path,
            goal_id=goal_id,
            source_todo_id=todo_id,
            agent_id=agent_id,
            role_id=role_id,
            action=action,
            decision_summary=summary_artifact["decision_summary"],
            execute=True,
        )
        followup = first_successor_followup(successor_todos)
        live_evidence: dict[str, object] | None = None
        if visible_lanes_accepted:
            live_evidence = build_live_codex_e2e_evidence_from_packet(
                packet=packet,
                append_result=append_result,
                agent_id=agent_id,
                lane_count=lane_count,
                visible_lanes_accepted=True,
            )
            _write_json(live_evidence_path, live_evidence)
        live_lane_evidence = (
            live_evidence.get("lane_evidence")
            if isinstance(live_evidence, dict) and isinstance(live_evidence.get("lane_evidence"), dict)
            else {}
        )
        completion = (
            _complete_selected_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                todo_id=todo_id,
                agent_id=agent_id,
                action=action,
                execute=True,
            )
            if complete_selected_todo
            else {"requested": False}
        )
        return {
            "ok": True,
            "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
            "mode": "execute",
            "goal_id": goal_id,
            "agent_id": agent_id,
            "selected_todo_id": todo_id,
            "selected_action": action,
            "executed": True,
            "kernel_mode": AUTO_RESEARCH_BUILTIN_KERNEL_MODE,
            "contract_status": contract_artifact["summary"]["status"],
            "validated_hypothesis_id": candidate["hypothesis_id"],
            "holdout_metric": (holdout_result.get("metric") or {}).get("value")
            if isinstance(holdout_result.get("metric"), dict)
            else None,
            "packet_status": packet["summary"]["status"],
            "append": {
                "schema_version": append_result.get("schema_version"),
                "goal_id": append_result.get("goal_id"),
                "appended_count": append_result.get("appended_count"),
                "counts_by_kind": append_result.get("counts_by_kind"),
            },
            "evaluation_summary": {
                "claim_allowed": summary_artifact["summary"]["claim_allowed"],
                "best_dev_metric": summary_artifact["evidence_graph_summary"]["best_dev_metric"],
                "best_holdout_metric": summary_artifact["evidence_graph_summary"]["best_holdout_metric"],
                "validated_promotion_candidate_count": summary_artifact["decision_summary"][
                    "validated_promotion_candidate_count"
                ],
            },
            "live_evidence": {
                "written": live_evidence is not None,
                "evidence_source": live_evidence.get("source") if live_evidence else None,
                "holdout_metric": live_lane_evidence.get("holdout_metric"),
            },
            "role_id": role_id,
            "successor_todos": successor_todos,
            "followup": followup,
            "artifact": _artifact_summary("holdout_validation", filename="evaluation-summary.public.json"),
            "artifact_status": "holdout_evidence_appended",
            "completion": completion,
            "frontier": frontier_packet,
            "public_boundary": {
                "raw_logs_recorded": False,
                "private_artifacts_recorded": False,
                "absolute_paths_recorded": False,
                "credentials_recorded": False,
            },
        }

    contract_artifact = _write_contract_artifact(
        output_path=contract_artifact_path,
        goal_id=goal_id,
        objective=objective,
        todo_id=todo_id,
        agent_id=agent_id,
    )
    _write_json(contract_input_path, contract_artifact["research_contract"])
    dev_result = _demo_eval_result(
        goal_id=goal_id,
        todo_id=todo_id,
        agent_id=agent_id,
        split="dev",
    )
    _write_json(dev_result_path, dev_result)
    packet = load_auto_research_evidence_packet_inputs(
        contract_path=contract_input_path,
        eval_result_paths=[dev_result_path],
        hypothesis_id=f"hyp_{_slug(todo_id, default='todo')}_{AUTO_RESEARCH_DEMO_CANDIDATE_KEY}",
        todo_id=todo_id,
        agent_id=agent_id,
        claimed_by=agent_id,
        mechanism_family=AUTO_RESEARCH_DEMO_MECHANISM_FAMILY,
        hypothesis=AUTO_RESEARCH_DEMO_HYPOTHESIS_TEXT,
        grounding_refs=["kernel:state_a2a_metric_demo"],
        attempt_start=1,
    )
    _write_json(evidence_packet_path, packet)
    append_result = append_evidence(str(evidence_packet_path))
    _write_json(append_result_path, append_result)
    summary_artifact = _write_evaluation_summary_artifact(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        output_path=evaluation_summary_path,
        goal_id=goal_id,
        todo_id=todo_id,
        agent_id=agent_id,
    )
    role_id = auto_research_role_id_for_action(action)
    successor_todos = _maybe_add_role_successor_todos(
        registry_path=registry_path,
        goal_id=goal_id,
        source_todo_id=todo_id,
        agent_id=agent_id,
        role_id=role_id,
        action=action,
        decision_summary=summary_artifact["decision_summary"],
        execute=True,
    )
    followup = first_successor_followup(successor_todos)

    live_evidence: dict[str, object] | None = None
    if visible_lanes_accepted:
        live_evidence = build_live_codex_e2e_evidence_from_packet(
            packet=packet,
            append_result=append_result,
            agent_id=agent_id,
            lane_count=lane_count,
            visible_lanes_accepted=True,
        )
        _write_json(live_evidence_path, live_evidence)

    live_lane_evidence = (
        live_evidence.get("lane_evidence")
        if isinstance(live_evidence, dict) and isinstance(live_evidence.get("lane_evidence"), dict)
        else {}
    )
    completion = (
        _complete_selected_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            agent_id=agent_id,
            action=action,
            execute=True,
        )
        if complete_selected_todo
        else {"requested": False}
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
        "mode": "execute",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "selected_todo_id": todo_id,
        "selected_action": action,
        "executed": True,
        "kernel_mode": AUTO_RESEARCH_BUILTIN_KERNEL_MODE,
        "contract_status": contract_artifact["summary"]["status"],
        "dev_metric": (dev_result.get("metric") or {}).get("value")
        if isinstance(dev_result.get("metric"), dict)
        else None,
        "packet_status": packet["summary"]["status"],
        "append": {
            "schema_version": append_result.get("schema_version"),
            "goal_id": append_result.get("goal_id"),
            "appended_count": append_result.get("appended_count"),
            "counts_by_kind": append_result.get("counts_by_kind"),
        },
        "evaluation_summary": {
            "claim_allowed": summary_artifact["summary"]["claim_allowed"],
            "best_dev_metric": summary_artifact["evidence_graph_summary"]["best_dev_metric"],
            "best_holdout_metric": summary_artifact["evidence_graph_summary"]["best_holdout_metric"],
            "validated_promotion_candidate_count": summary_artifact["decision_summary"][
                "validated_promotion_candidate_count"
            ],
        },
        "live_evidence": {
            "written": live_evidence is not None,
            "evidence_source": live_evidence.get("source") if live_evidence else None,
            "dev_metric": live_lane_evidence.get("dev_metric"),
        },
        "role_id": role_id,
        "successor_todos": successor_todos,
        "followup": followup,
        "artifacts": {
            "paths_are_local_only": True,
            "evidence_packet": "evidence.public.json",
            "append_result": "append-result.public.json",
            "live_evidence": live_evidence_output if live_evidence else None,
        },
        "completion": completion,
        "frontier": frontier_packet,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }
