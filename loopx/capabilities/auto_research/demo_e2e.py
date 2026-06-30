from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from .core import (
    AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION,
    AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
    build_auto_research_board_projection,
    build_auto_research_demo_acceptance_packet,
    build_auto_research_demo_supervisor_plan,
    build_auto_research_quickstart,
    build_live_auto_research_projection,
    build_research_artifact_packet,
    build_research_decision_candidates,
    build_research_evidence_graph_from_rollout_events,
    load_auto_research_evidence_packet_inputs,
)
from .live_evidence import (
    build_live_codex_claim_from_evidence,
    load_live_codex_e2e_evidence,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import load_rollout_events, rollout_event_log_path
from ...status import collect_status


AppendEvidence = Callable[[str], dict[str, object]]
VisibleLauncher = Callable[[dict[str, object]], dict[str, object]]


def _live_board_and_acceptance(
    *,
    goal_id: str,
    agent_id: str,
    objective: str,
    supervisor: dict[str, object],
    registry_path: Path,
    runtime_root_arg: str | None,
) -> tuple[dict[str, object], dict[str, object]]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    rollout_events = load_rollout_events(rollout_event_log_path(runtime_root, goal_id))
    status_payload = collect_status(
        registry_path=registry_path,
        runtime_root_override=runtime_root_arg,
        scan_roots=[Path.cwd()],
        limit=5,
    )
    quota_payload = build_quota_should_run(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    if quota_payload.get("ok"):
        projection = build_live_auto_research_projection(
            goal_id=goal_id,
            agent_id=agent_id,
            quota_payload=quota_payload,
            rollout_events=rollout_events,
        )
    else:
        graph = build_research_evidence_graph_from_rollout_events(
            goal_id=goal_id,
            rollout_events=rollout_events,
        )
        decisions = build_research_decision_candidates(graph)
        projection = {
            "ok": True,
            "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
            "source_schema_version": "loopx_rollout_event_log",
            "frontier": {
                "schema_version": "decentralized_research_frontier_v0",
                "goal_id": goal_id,
                "agent_id": agent_id,
                "selected": None,
                "runnable": [],
                "blocked": [
                    {
                        "todo_id": "goal_not_connected",
                        "claimed_by": agent_id,
                        "status": "blocked",
                        "blocked_by": "quota_unavailable_for_unconnected_demo_goal",
                    }
                ],
                "promotion_candidates": decisions["promotion_candidates"],
                "retirement_candidates": decisions["retirement_candidates"],
            },
            "evidence_graph": graph,
            "showcase_projection": {
                "schema_version": "research_showcase_projection_v0",
                "title": "Decentralized Auto Research: k-NN Speedup",
                "goal_id": goal_id,
                "objective": objective,
                "metric": graph.get("metric") or {},
                "baseline_metric": graph.get("baseline_metric"),
            },
            "artifact_packet": build_research_artifact_packet(
                graph,
                question=objective,
            ),
            "public_boundary": {
                "raw_logs_recorded": False,
                "private_artifacts_recorded": False,
                "source": "rollout_evidence_without_connected_goal",
            },
        }
    board = build_auto_research_board_projection(projection)
    acceptance = build_auto_research_demo_acceptance_packet(board, supervisor)
    return board, acceptance


def _run_protected_eval(
    *,
    pack_dir: Path,
    split: str,
) -> dict[str, object]:
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
    (pack_dir / f"{split}-result.public.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _compact_board(board: dict[str, object]) -> dict[str, object]:
    decisions = board.get("decision_candidates") if isinstance(board.get("decision_candidates"), dict) else {}
    binding = board.get("projection_binding") if isinstance(board.get("projection_binding"), dict) else {}
    return {
        "ok": bool(board.get("ok")),
        "rollout_backed": bool(binding.get("rollout_backed")),
        "promotion_candidate_count": len(decisions.get("promotion_candidates") or []),
        "retirement_candidate_count": len(decisions.get("retirement_candidates") or []),
        "value_metrics": board.get("value_metrics") or [],
    }


def _compact_acceptance(acceptance: dict[str, object]) -> dict[str, object]:
    summary = (
        acceptance.get("readiness_summary")
        if isinstance(acceptance.get("readiness_summary"), dict)
        else {}
    )
    board = (
        acceptance.get("board_output")
        if isinstance(acceptance.get("board_output"), dict)
        else {}
    )
    return {
        "ok": bool(acceptance.get("ok")),
        "ready_for_real_launch": bool(summary.get("ready_for_real_launch")),
        "promotion_candidate_count": int(board.get("promotion_candidate_count") or 0),
        "rollout_backed": bool(board.get("rollout_backed")),
    }


def _command_text(
    *,
    cli_bin: str,
    goal_id: str,
    agent_id: str,
    execute: bool,
    launch_visible: bool = False,
    live_evidence: bool = False,
) -> str:
    parts = [
        shlex.quote(cli_bin),
        "--format",
        "json",
        "auto-research",
        "demo-e2e",
        "--goal-id",
        shlex.quote(goal_id),
        "--agent-id",
        shlex.quote(agent_id),
    ]
    if execute:
        parts.append("--execute")
    if launch_visible:
        parts.append("--launch-visible")
    if live_evidence:
        parts.extend(["--live-evidence", "<public-safe-live-evidence.json>"])
    return " ".join(parts)


def _live_codex_truth_boundary(*, launch_visible: bool) -> dict[str, object]:
    return {
        "executed": False,
        "claim_allowed": False,
        "visible_lanes_launched": bool(launch_visible),
        "visible_lanes_accepted": False,
        "evidence_source": "not_collected_from_codex_lane_output",
        "reason": (
            "demo-e2e validates the deterministic positive replay and optional visible launcher; "
            "it does not prove a live Codex multi-agent research result."
        ),
        "required_for_live_claim": [
            "visible Codex lanes started from the launcher",
            "lane-authored evidence appended to LoopX state",
            "acceptance packet cites evidence_source=live_codex_lane_output",
        ],
    }


def run_auto_research_demo_e2e(
    *,
    agent_id: str,
    goal_id: str,
    objective: str,
    output_dir: str,
    execute: bool,
    launch_visible: bool,
    keep_workspace: bool,
    registry_path: Path,
    runtime_root_arg: str | None,
    session_name: str,
    cli_bin: str,
    codex_bin: str,
    tmux_bin: str,
    reasoning_effort: str,
    live_evidence_path: str | None,
    append_evidence: AppendEvidence,
    visible_launcher: VisibleLauncher | None = None,
) -> dict[str, object]:
    if launch_visible and not execute:
        raise ValueError("--launch-visible requires --execute")
    if launch_visible and visible_launcher is None:
        raise ValueError("--launch-visible requires a visible launcher callback")
    if live_evidence_path and not execute:
        raise ValueError("--live-evidence requires --execute")

    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=goal_id,
        session_name=session_name,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        tmux_bin=tmux_bin,
        reasoning_effort=reasoning_effort,
    )
    payload: dict[str, object] = {
        "ok": True,
        "schema_version": AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "execution_kind": "deterministic_replay" if execute else "deterministic_replay_preview",
        "result_source": "generated_quickstart_pack_protected_eval_replay",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "reasoning_effort": reasoning_effort,
        "commands": {
            "deterministic_replay": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
            ),
            "deterministic_replay_with_visible_lanes": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                launch_visible=True,
            ),
            "live_codex_claim_from_evidence": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                live_evidence=True,
            ),
        },
        "supervisor": {
            "schema_version": supervisor.get("schema_version"),
            "mode": supervisor.get("mode"),
            "lane_count": len(supervisor.get("lanes") or []),
            "reasoning_contract": supervisor.get("reasoning_contract"),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
            "writes_loopx_state": bool(execute),
            "launches_visible_lanes": bool(launch_visible),
            "live_codex_sessions_recorded": False,
        },
        "live_codex_e2e": _live_codex_truth_boundary(launch_visible=launch_visible),
    }
    if not execute:
        quickstart = build_auto_research_quickstart(
            agent_id=agent_id,
            goal_id=goal_id,
            objective=objective,
            output_dir=output_dir,
            execute=False,
            cwd=Path.cwd(),
        )
        payload["quickstart_preview"] = {
            "schema_version": quickstart.get("schema_version"),
            "mode": quickstart.get("mode"),
            "template": quickstart.get("template"),
            "next_commands": quickstart.get("next_commands"),
        }
        payload["replay_result"] = {
            "executed": False,
            "result_source": "deterministic_replay_preview",
            "expected_positive_result": "dev=4.0x holdout=4.5x after --execute",
        }
        return payload

    tmp_obj: tempfile.TemporaryDirectory[str] | None = None
    if keep_workspace:
        demo_root = Path(tempfile.mkdtemp(prefix="loopx-auto-research-demo-e2e."))
    else:
        tmp_obj = tempfile.TemporaryDirectory(prefix="loopx-auto-research-demo-e2e.")
        demo_root = Path(tmp_obj.name)
    try:
        quickstart = build_auto_research_quickstart(
            agent_id=agent_id,
            goal_id=goal_id,
            objective=objective,
            output_dir=output_dir,
            execute=True,
            cwd=demo_root,
        )
        pack_dir = demo_root / str(quickstart["pack_dir"])
        dev = _run_protected_eval(pack_dir=pack_dir, split="dev")
        holdout = _run_protected_eval(pack_dir=pack_dir, split="holdout")
        evidence = load_auto_research_evidence_packet_inputs(
            contract_path=str(pack_dir / "research_contract.json"),
            eval_result_paths=[
                str(pack_dir / "dev-result.public.json"),
                str(pack_dir / "holdout-result.public.json"),
            ],
            hypothesis_id="hyp_quickstart_partial_selection",
            todo_id="todo_auto_research_quickstart_001",
            agent_id=agent_id,
            claimed_by=agent_id,
            mechanism_family="partial_selection",
            hypothesis="Use exact partial selection to avoid full distance sorting.",
            parent_hypothesis_id=None,
            grounding_refs=["quickstart:knn_exact_pack"],
            novelty_audit_ref=None,
            branch_ref=None,
            attempt_start=1,
        )
        evidence_path = pack_dir / "evidence.public.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        append_payload = append_evidence(str(evidence_path))
        board, acceptance = _live_board_and_acceptance(
            goal_id=goal_id,
            agent_id=agent_id,
            objective=objective,
            supervisor=supervisor,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
        )
        payload.update(
            {
                "quickstart": {
                    "schema_version": quickstart.get("schema_version"),
                    "mode": quickstart.get("mode"),
                    "template": quickstart.get("template"),
                },
                "replay_result": {
                    "executed": True,
                    "result_source": "generated_quickstart_pack_protected_eval_replay",
                    "status": evidence.get("summary", {}).get("status"),
                    "dev_metric": (dev.get("metric") or {}).get("value"),
                    "holdout_metric": (holdout.get("metric") or {}).get("value"),
                    "dev_exact": bool(dev.get("exact")),
                    "holdout_exact": bool(holdout.get("exact")),
                    "protected_scope_clean": bool(evidence.get("summary", {}).get("protected_scope_clean")),
                },
                "append": {
                    "appended_count": append_payload.get("appended_count"),
                    "skipped_existing_count": append_payload.get("skipped_existing_count"),
                    "counts_by_kind": append_payload.get("counts_by_kind"),
                },
                "board": _compact_board(board),
                "acceptance": _compact_acceptance(acceptance),
                "workspace_retained": keep_workspace,
            }
        )
        if launch_visible and visible_launcher is not None:
            visible_payload = visible_launcher(dict(supervisor))
            launch_result = (
                visible_payload.get("launch_result")
                if isinstance(visible_payload.get("launch_result"), dict)
                else {}
            )
            visible_acceptance = (
                launch_result.get("visible_acceptance")
                if isinstance(launch_result.get("visible_acceptance"), dict)
                else {}
            )
            payload["visible_launch"] = {
                "mode": visible_payload.get("mode"),
                "launch_result": launch_result,
                "boundary": visible_payload.get("boundary"),
            }
            live_boundary = payload["live_codex_e2e"]
            if isinstance(live_boundary, dict):
                live_boundary["visible_lanes_launched"] = True
                live_boundary["visible_lanes_accepted"] = bool(visible_acceptance.get("accepted"))
        if live_evidence_path:
            live_evidence = load_live_codex_e2e_evidence(
                evidence_path=live_evidence_path,
                goal_id=goal_id,
                agent_id=agent_id,
            )
            payload["live_codex_e2e"] = build_live_codex_claim_from_evidence(live_evidence)
        return payload
    finally:
        if tmp_obj is not None:
            tmp_obj.cleanup()
