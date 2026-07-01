from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .core import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    build_auto_research_quickstart,
    build_live_auto_research_projection,
    load_auto_research_evidence_packet_inputs,
)
from .live_evidence import (
    LIVE_CODEX_E2E_DEFAULT_OUTPUT,
    build_live_codex_e2e_evidence_from_packet,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import load_rollout_events, rollout_event_log_path
from ...status import collect_status


AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION = "auto_research_worker_turn_v0"
AUTO_RESEARCH_WORKER_FRONTIER_SCHEMA_VERSION = "auto_research_worker_frontier_v0"
SUPPORTED_WORKER_ACTIONS = {"run_dev_eval", "write_evidence"}

AppendEvidence = Callable[[str], dict[str, object]]


def _slug(value: object, *, default: str = "item") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-._")
    return text[:80] or default


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_protected_eval(*, pack_dir: Path, split: str, output_path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(pack_dir / "protected_eval.py"),
            "--solution",
            str(pack_dir / "solution_candidate.py"),
            "--split",
            split,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    _write_json(output_path, payload)
    return payload


def _ensure_quickstart_pack(
    *,
    workspace: Path,
    output_dir: str,
    agent_id: str,
    goal_id: str,
    objective: str,
) -> tuple[Path, str]:
    pack_dir = (workspace / output_dir).resolve()
    if pack_dir.exists():
        return pack_dir, "existing"
    build_auto_research_quickstart(
        agent_id=agent_id,
        goal_id=goal_id,
        objective=objective,
        output_dir=output_dir,
        template=AUTO_RESEARCH_QUICKSTART_TEMPLATE,
        execute=True,
        cwd=workspace,
    )
    return pack_dir, "created"


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
    output_dir: str = "auto_research_knn_pack",
    evidence_dir: str = ".local/auto-research-worker",
    execute: bool = False,
    append_evidence: AppendEvidence | None = None,
    lane_count: int = 1,
    visible_lanes_accepted: bool = False,
    live_evidence_output: str = LIVE_CODEX_E2E_DEFAULT_OUTPUT,
) -> dict[str, object]:
    """Run one LoopX-selected visible worker action.

    The worker does not choose its own work. It reads quota/frontier, checks the
    selected action, then performs only the small public k-NN dev-eval evidence
    turn that the visible auto-research demo currently needs.
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
    action = str((selected or {}).get("allowed_action") or "")
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
            "would_execute": "quickstart_dev_eval_then_append_public_evidence",
            "frontier": frontier_packet,
        }
    if append_evidence is None:
        raise ValueError("execute requires an append_evidence callback")

    pack_dir, pack_mode = _ensure_quickstart_pack(
        workspace=workspace,
        output_dir=output_dir,
        agent_id=agent_id,
        goal_id=goal_id,
        objective=objective,
    )
    run_dir = workspace / evidence_dir / _slug(agent_id, default="agent") / _slug(todo_id, default="todo")
    dev_result_path = run_dir / "dev-result.public.json"
    evidence_packet_path = run_dir / "evidence.public.json"
    append_result_path = run_dir / "append-result.public.json"
    live_evidence_path = run_dir / live_evidence_output

    dev_result = _run_protected_eval(pack_dir=pack_dir, split="dev", output_path=dev_result_path)
    packet = load_auto_research_evidence_packet_inputs(
        contract_path=pack_dir / "research_contract.json",
        eval_result_paths=[dev_result_path],
        hypothesis_id=f"hyp_{_slug(todo_id, default='todo')}_partial_selection",
        todo_id=todo_id,
        agent_id=agent_id,
        claimed_by=agent_id,
        mechanism_family="partial_selection",
        hypothesis="Use exact partial selection to avoid full distance sorting.",
        grounding_refs=["quickstart:knn_exact_pack"],
        attempt_start=1,
    )
    _write_json(evidence_packet_path, packet)
    append_result = append_evidence(str(evidence_packet_path))
    _write_json(append_result_path, append_result)

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
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
        "mode": "execute",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "selected_todo_id": todo_id,
        "selected_action": action,
        "executed": True,
        "pack_mode": pack_mode,
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
        "live_evidence": {
            "written": live_evidence is not None,
            "claim_source": live_evidence.get("source") if live_evidence else None,
            "dev_metric": live_lane_evidence.get("dev_metric"),
        },
        "artifacts": {
            "paths_are_local_only": True,
            "evidence_packet": "evidence.public.json",
            "append_result": "append-result.public.json",
            "live_evidence": live_evidence_output if live_evidence else None,
        },
        "frontier": frontier_packet,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }
