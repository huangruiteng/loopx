from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from .core import (
    AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION,
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
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
from .kernel import run_builtin_lightweight_demo
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
VisibleLauncher = Callable[..., dict[str, object]]


def _safe_ref_fragment(value: object, *, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    return text[:48] or fallback


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _prepare_visible_demo_git_workspaces(
    *,
    control_project: Path,
    demo_root: Path,
    lanes: list[dict[str, object]],
    primary_agent: str | None,
) -> dict[str, object]:
    """Give side-agent lanes real git worktrees while sharing one LoopX state."""

    (control_project / ".gitignore").write_text(".local/\n", encoding="utf-8")
    _git(control_project, "init")
    _git(control_project, "config", "user.email", "loopx-demo@example.invalid")
    _git(control_project, "config", "user.name", "LoopX Demo")
    _git(control_project, "add", ".")
    _git(control_project, "commit", "-m", "seed visible auto research demo control plane")

    worktree_root = demo_root / "visible-lane-worktrees"
    side_count = 0
    for index, lane in enumerate(lanes, start=1):
        agent_id = str(lane.get("agent_id") or "").strip()
        if not agent_id or agent_id == primary_agent:
            lane["workspace_role"] = "primary_control_project"
            continue
        lane_id = _safe_ref_fragment(lane.get("lane_id"), fallback=f"lane-{index}")
        branch = f"demo/{_safe_ref_fragment(agent_id, fallback=f'agent-{index}')}-{index}"
        workspace = worktree_root / lane_id
        _git(control_project, "worktree", "add", "-b", branch, str(workspace))
        lane["workspace"] = str(workspace)
        lane["workspace_role"] = "independent_git_worktree"
        side_count += 1

    return {
        "schema_version": "auto_research_visible_demo_workspace_route_v0",
        "shared_goal_surface": "demo_local_loopx_registry_and_runtime",
        "primary_workspace": "control_project_git_worktree",
        "side_lane_workspace": "independent_git_worktree",
        "side_lane_worktree_count": side_count,
        "absolute_paths_recorded": False,
    }


def _seed_visible_demo_control_plane(
    *,
    demo_root: Path,
    goal_id: str,
    objective: str,
    supervisor: dict[str, object],
) -> tuple[dict[str, object], Path, str]:
    """Create a tiny demo-local LoopX queue for visible workers."""

    from ...bootstrap import bootstrap_project
    from ...configure_goal import configure_goal
    from ...todos import add_goal_todo

    control_project = demo_root / "visible-control-plane"
    control_registry = demo_root / "visible-control-plane.registry.json"
    control_runtime = demo_root / "visible-control-plane.runtime"
    bootstrap_project(
        project=control_project,
        registry_path=control_registry,
        runtime_root=control_runtime,
        goal_id=goal_id,
        objective=objective,
        domain="auto-research-demo",
        role="agent",
        parent_goal_id=None,
        state_file=None,
        goal_doc=None,
        adapter_kind="auto_research_demo_local_queue",
        adapter_status="connected",
        next_probe=None,
        spawn_allowed=True,
        max_children=3,
        allowed_domains=["auto-research-demo"],
        write_scope=["examples/**", "experiments/**", ".local/**"],
        claim_ttl_minutes=60,
        onboarding_scan_enabled=False,
        accept_onboarding_agent_todos=False,
        begin_autonomous_advance=True,
        codex_app_heartbeat="no",
        force=False,
        dry_run=False,
        sync_global=False,
    )

    lanes = [lane for lane in supervisor.get("lanes") or [] if isinstance(lane, dict)]
    agents = sorted(
        {
            str(lane.get("agent_id") or "").strip()
            for lane in lanes
            if str(lane.get("agent_id") or "").strip()
        }
    )
    primary_agent = (
        "codex-main-control"
        if "codex-main-control" in agents
        else (agents[0] if agents else None)
    )
    configure_goal(
        registry_path=control_registry,
        goal_id=goal_id,
        registered_agents=agents,
        primary_agent=primary_agent,
        waiting_on="codex",
        orchestration_mode="multi_subagent",
        spawn_allowed=True,
        execute=True,
    )

    seeded_todos: list[dict[str, object]] = []
    for lane in lanes:
        agent_id = str(lane.get("agent_id") or "").strip()
        role_id = str(lane.get("role_id") or "").strip()
        lane_id = str(lane.get("lane_id") or "").strip()
        profile = lane.get("role_profile") if isinstance(lane.get("role_profile"), dict) else {}
        allowed_actions = profile.get("allowed_actions") if isinstance(profile, dict) else []
        action_kind = str((allowed_actions or ["advance_todo"])[0])
        title_by_action = {
            "write_research_contract": (
                "Write the public-safe research contract for the quickstart k-NN hypothesis."
            ),
            "propose_hypothesis": (
                "Map the quickstart partial-selection idea into a todo-backed research hypothesis."
            ),
            "claim_attempt": (
                "Claim one visible attempt boundary for the selected quickstart hypothesis."
            ),
            "run_dev_eval": (
                "Run the selected quickstart hypothesis on the dev split and write public-safe evidence."
            ),
            "write_evaluation_summary": (
                "Verify the evidence packet and open the next validation or promotion gate."
            ),
        }
        title = title_by_action.get(
            action_kind,
            f"Run one role-compatible auto-research action for {role_id or lane_id}.",
        )
        result = add_goal_todo(
            registry_path=control_registry,
            goal_id=goal_id,
            role="agent",
            text=f"[P0-auto-research-live] {title}",
            task_class="advancement_task",
            action_kind=action_kind,
            claimed_by=agent_id or None,
            project=control_project,
        )
        seeded_todos.append(
            {
                "todo_id": result.get("todo_id"),
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": role_id,
                "action_kind": action_kind,
            }
        )

    workspace_route = _prepare_visible_demo_git_workspaces(
        control_project=control_project,
        demo_root=demo_root,
        lanes=lanes,
        primary_agent=primary_agent,
    )

    summary = {
        "schema_version": "auto_research_visible_demo_control_plane_v0",
        "mode": "demo_local_loopx_queue",
        "goal_id": goal_id,
        "registry_scope": "demo_local_runtime",
        "registered_agent_count": len(agents),
        "seeded_todo_count": len(seeded_todos),
        "seeded_todos": seeded_todos,
        "state_route": "visible_lanes_use_LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
        "workspace_route": workspace_route,
        "absolute_paths_recorded": False,
        "private_artifacts_recorded": False,
    }
    return summary, control_registry, str(control_runtime)


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
    claim_boundary = (
        board.get("claim_boundary")
        if isinstance(board.get("claim_boundary"), dict)
        else {}
    )
    return {
        "ok": bool(board.get("ok")),
        "rollout_backed": bool(binding.get("rollout_backed")),
        "promotion_candidate_count": len(decisions.get("promotion_candidates") or []),
        "retirement_candidate_count": len(decisions.get("retirement_candidates") or []),
        "claim_boundary": claim_boundary,
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
        "claim_boundary": board.get("claim_boundary") if isinstance(board.get("claim_boundary"), dict) else {},
    }


def _command_text(
    *,
    cli_bin: str,
    goal_id: str,
    agent_id: str,
    execute: bool,
    launch_visible: bool = False,
    live_evidence: bool = False,
    tracking_goal_id: str | None = None,
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
    if tracking_goal_id:
        parts.extend(["--tracking-goal-id", shlex.quote(tracking_goal_id)])
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
            "demo-e2e validates the lightweight multi-round research kernel and optional visible launcher; "
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
    tracking_goal_id: str | None,
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

    tracking_goal = tracking_goal_id.strip() if isinstance(tracking_goal_id, str) else ""
    if tracking_goal == goal_id:
        tracking_goal = ""
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
        "execution_kind": "multiround_research_kernel" if execute else "multiround_research_preview",
        "result_source": "lightweight_multiround_kernel" if execute else "lightweight_multiround_kernel_preview",
        "goal_id": goal_id,
        "tracking_goal_id": tracking_goal or None,
        "route_contract": {
            "schema_version": "auto_research_demo_frontier_route_v0",
            "frontier_goal_id": goal_id,
            "tracking_goal_id": tracking_goal or None,
            "tracking_goal_drives_frontier": False,
            "visible_lanes_read_goal_id": goal_id,
            "dedicated_positive_demo_frontier": goal_id == AUTO_RESEARCH_DEFAULT_GOAL_ID,
            "reason": (
                "Use --goal-id for the research frontier that visible lanes inspect. "
                "--tracking-goal-id is metadata for the parent productization goal and must not reroute panes."
            ),
        },
        "agent_id": agent_id,
        "reasoning_effort": reasoning_effort,
        "commands": {
            "multiround_kernel": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "multiround_kernel_with_visible_lanes": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                launch_visible=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "live_codex_claim_from_evidence": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                live_evidence=True,
                tracking_goal_id=tracking_goal or None,
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
        payload["protected_eval_result"] = {
            "executed": False,
            "result_source": "lightweight_multiround_kernel_preview",
            "expected_positive_result": "dev=4.0x holdout=4.5x after --execute",
        }
        payload["research_loop"] = {
            "executed": False,
            "result_source": "lightweight_multiround_kernel_preview",
            "expected_rounds": "two dev rounds plus holdout for the selected candidate after --execute",
            "expected_gain": "selected candidate improves from baseline 1.0x to dev=4.0x and holdout=4.5x",
        }
        return payload

    tmp_obj: tempfile.TemporaryDirectory[str] | None = None
    if keep_workspace or launch_visible:
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
        research_loop = run_builtin_lightweight_demo(goal_id=goal_id)
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
                "protected_eval_result": {
                    "executed": True,
                    "result_source": "generated_quickstart_pack_protected_eval",
                    "status": evidence.get("summary", {}).get("status"),
                    "dev_metric": (dev.get("metric") or {}).get("value"),
                    "holdout_metric": (holdout.get("metric") or {}).get("value"),
                    "dev_exact": bool(dev.get("exact")),
                    "holdout_exact": bool(holdout.get("exact")),
                    "protected_scope_clean": bool(evidence.get("summary", {}).get("protected_scope_clean")),
                },
                "research_loop": {
                    "executed": True,
                    "result_source": research_loop.get("result_source"),
                    "schema_version": research_loop.get("schema_version"),
                    "decision": research_loop.get("decision"),
                    "candidate_count": research_loop.get("candidate_count"),
                    "dev_round_count": research_loop.get("dev_round_count"),
                    "evidence_event_count": research_loop.get("evidence_event_count"),
                    "selected_hypothesis_id": research_loop.get("selected_hypothesis_id"),
                    "baseline_metric": 1.0,
                    "dev_metric": research_loop.get("dev_metric"),
                    "holdout_metric": research_loop.get("holdout_metric"),
                    "dev_gain_over_baseline": (
                        float(research_loop["dev_metric"]) - 1.0
                        if research_loop.get("dev_metric") is not None
                        else None
                    ),
                    "holdout_gain_over_baseline": (
                        float(research_loop["holdout_metric"]) - 1.0
                        if research_loop.get("holdout_metric") is not None
                        else None
                    ),
                    "worker_rounds": [
                        {
                            "round": 1,
                            "role": "hypothesis_mapper",
                            "transition": "seed_baseline_candidate",
                            "hypothesis_id": "hyp_full_sort",
                            "loopx_contract": "role_profile_quota_frontier_cli_writeback",
                        },
                        {
                            "round": 2,
                            "role": "evidence_runner",
                            "transition": "try_positive_candidate",
                            "hypothesis_id": "hyp_partial_selection",
                            "loopx_contract": "role_profile_quota_frontier_cli_writeback",
                        },
                        {
                            "round": 3,
                            "role": "evidence_verifier",
                            "transition": "holdout_validate_selected_candidate",
                            "hypothesis_id": research_loop.get("selected_hypothesis_id"),
                            "loopx_contract": "role_profile_quota_frontier_cli_writeback",
                        },
                    ],
                    "public_boundary": research_loop.get("public_boundary"),
                },
                "append": {
                    "appended_count": append_payload.get("appended_count"),
                    "skipped_existing_count": append_payload.get("skipped_existing_count"),
                    "counts_by_kind": append_payload.get("counts_by_kind"),
                },
                "board": _compact_board(board),
                "acceptance": _compact_acceptance(acceptance),
                "workspace_retained": keep_workspace or launch_visible,
            }
        )
        if launch_visible and visible_launcher is not None:
            (
                visible_control,
                visible_registry_path,
                visible_runtime_root_arg,
            ) = _seed_visible_demo_control_plane(
                demo_root=demo_root,
                goal_id=goal_id,
                objective=objective,
                supervisor=supervisor,
            )
            payload["visible_control_plane"] = visible_control
            visible_payload = visible_launcher(
                dict(supervisor),
                visible_registry_path,
                visible_runtime_root_arg,
                demo_root,
            )
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
