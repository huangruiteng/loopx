from __future__ import annotations

import json
import shlex
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from .legacy_core import (
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
)
from .live_evidence import (
    build_live_codex_claim_from_evidence,
    load_live_codex_e2e_evidence,
)
from .rollout_append import append_auto_research_rollout_events
from .worker_loop import run_auto_research_worker_loop
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import load_rollout_events, rollout_event_log_path
from ...status import collect_status


AppendEvidence = Callable[[str], dict[str, object]]
VisibleLauncher = Callable[..., dict[str, object]]

DEFAULT_WORKER_LOOP_AGENT_SPECS = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
]


def _prepare_visible_demo_workspace_route(
    *,
    control_project: Path,
    demo_root: Path,
    lanes: list[dict[str, object]],
    primary_agent: str | None,
) -> dict[str, object]:
    """Keep visible Codex TUIs off demo-local git worktrees.

    The demo still shares one LoopX state surface. Mutating attempts can claim
    their own execution boundary from inside the role, but the first visible TUI
    screen must not start in a freshly-created git worktree because Codex will
    stop on a trust prompt before the user sees the auto-research flow.
    """

    (control_project / ".gitignore").write_text(".local/\n", encoding="utf-8")

    side_count = 0
    for lane in lanes:
        agent_id = str(lane.get("agent_id") or "").strip()
        if not agent_id or agent_id == primary_agent:
            lane["workspace_role"] = "shared_visible_tui_workspace"
            continue
        lane["workspace_role"] = "shared_visible_tui_workspace"
        side_count += 1

    return {
        "schema_version": "auto_research_visible_demo_workspace_route_v0",
        "shared_goal_surface": "demo_local_loopx_registry_and_runtime",
        "primary_workspace": "visible_codex_tui_workspace",
        "side_lane_workspace": "visible_codex_tui_workspace",
        "side_lane_worktree_count": 0,
        "side_lane_count": side_count,
        "trust_prompt_avoidance": "do_not_start_codex_tui_in_demo_local_git_worktrees",
        "mutation_isolation_policy": (
            "mutating attempts claim an execution boundary from inside the role; "
            "the first visible TUI uses the operator-selected workspace"
        ),
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
        if role_id == "evidence_runner":
            action_kind = "run_dev_eval"
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
                "Run the selected quickstart hypothesis on the dev split, write public-safe evidence, append it, and capture live evidence."
            ),
            "run_holdout_eval": (
                "Run held-out validation for the dev-supported hypothesis, append public-safe evidence, and summarize promotion readiness."
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

    workspace_route = _prepare_visible_demo_workspace_route(
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
    run_worker_loop: bool = False,
    launch_visible: bool = False,
    headless: bool = False,
    attach: bool = False,
    no_attach: bool = False,
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
    if run_worker_loop:
        parts.append("--run-worker-loop")
    if headless:
        parts.append("--headless")
    if launch_visible:
        parts.append("--launch-visible")
    if attach:
        parts.append("--attach")
    if no_attach:
        parts.append("--no-attach")
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
            "demo-e2e validates the LoopX worker-loop state/A2A path and optional visible launcher; "
            "it does not prove a live Codex multi-agent research result."
        ),
        "required_for_live_claim": [
            "visible Codex lanes started from the launcher",
            "lane-authored evidence appended to LoopX state",
            "acceptance packet cites evidence_source=live_codex_lane_output",
        ],
    }


def _demo_claim_summary(payload: dict[str, object]) -> dict[str, object]:
    """Keep user-facing claims anchored to worker-loop or live evidence."""

    live = payload.get("live_codex_e2e") if isinstance(payload.get("live_codex_e2e"), dict) else {}
    tonight = (
        payload.get("tonight_experience")
        if isinstance(payload.get("tonight_experience"), dict)
        else {}
    )
    live_claim_allowed = bool(live.get("claim_allowed"))
    if live_claim_allowed:
        cannot_claim: list[str] = []
        if not live.get("holdout_claim_allowed"):
            cannot_claim.append("live_holdout_metric_or_claim")
        if not live.get("promotion_claim_allowed"):
            cannot_claim.append("automatic_promotion_success")
        return {
            "schema_version": "auto_research_demo_claim_summary_v0",
            "status": "live_worker_dev_evidence_ready",
            "claim_basis": "live_codex_lane_output",
            "live_worker_claim_allowed": True,
            "live_worker_authored": True,
            "can_claim": ["visible_worker_live_dev_evidence_supported"],
            "cannot_claim": cannot_claim,
            "dev_metric": live.get("dev_metric"),
            "holdout_metric": live.get("holdout_metric"),
            "holdout_metric_redacted": bool(live.get("holdout_metric_redacted")),
            "next_required": (
                "separate held-out live evidence or owner-approved claim authority "
                "is required before holdout or promotion claims"
            ),
        }

    if tonight.get("ready") and tonight.get("positive_result"):
        return {
            "schema_version": "auto_research_demo_claim_summary_v0",
            "status": "loopx_worker_loop_positive",
            "claim_basis": "loopx_worker_loop_public_evidence",
            "live_worker_claim_allowed": False,
            "live_worker_authored": False,
            "can_claim": ["one_command_loopx_worker_loop_positive_result"],
            "cannot_claim": [
                "visible_codex_tui_authored_result",
                "automatic_promotion_success",
            ],
            "dev_metric": tonight.get("dev_metric"),
            "holdout_metric": tonight.get("holdout_metric"),
            "holdout_metric_redacted": False,
            "next_required": (
                "launch visible Codex panes or pass compact live evidence before claiming "
                "Codex TUI workers authored the same result"
            ),
        }

    visible_launch = (
        payload.get("visible_launch")
        if isinstance(payload.get("visible_launch"), dict)
        else {}
    )
    if payload.get("mode") == "execute" and visible_launch:
        return {
            "schema_version": "auto_research_demo_claim_summary_v0",
            "status": "visible_worker_queue_started",
            "claim_basis": "demo_local_loopx_queue_and_visible_codex_panes",
            "live_worker_claim_allowed": False,
            "live_worker_authored": False,
            "can_claim": ["visible_role_todo_flow_started"],
            "cannot_claim": [
                "visible_codex_workers_completed_result",
                "live_holdout_metric_or_claim",
                "automatic_promotion_success",
            ],
            "dev_metric": None,
            "holdout_metric": None,
            "holdout_metric_redacted": False,
            "next_required": (
                "let the visible Codex panes run the printed worker-turn commands; "
                "then pass compact live evidence before claiming a completed live result"
            ),
        }

    return {
        "schema_version": "auto_research_demo_claim_summary_v0",
        "status": "preview_only",
        "claim_basis": "dry_run_preview",
        "live_worker_claim_allowed": False,
        "live_worker_authored": False,
        "can_claim": ["one_command_preview_available"],
        "cannot_claim": [
            "visible_codex_workers_authored_result",
            "live_holdout_metric_or_claim",
            "automatic_promotion_success",
        ],
        "dev_metric": None,
        "holdout_metric": None,
        "holdout_metric_redacted": False,
        "next_required": (
            "run --execute to seed a demo-local LoopX queue and launch visible Codex lanes"
        ),
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
    goal_surface_mode: str = "explicit_goal",
    agent_specs: Sequence[str] | None = None,
    run_worker_loop: bool = False,
    worker_loop_rounds: int = 2,
) -> dict[str, object]:
    if launch_visible and not execute:
        raise ValueError("--launch-visible requires --execute")
    if run_worker_loop and not execute:
        raise ValueError("--run-worker-loop requires --execute")
    if worker_loop_rounds < 1:
        raise ValueError("--worker-loop-rounds must be >= 1")
    if launch_visible and visible_launcher is None:
        raise ValueError("--launch-visible requires a visible launcher callback")
    if live_evidence_path and not execute:
        raise ValueError("--live-evidence requires --execute")

    tracking_goal = tracking_goal_id.strip() if isinstance(tracking_goal_id, str) else ""
    if tracking_goal == goal_id:
        tracking_goal = ""
    reuses_default_internal_goal = goal_id == AUTO_RESEARCH_DEFAULT_GOAL_ID
    effective_agent_specs = list(agent_specs or [])
    if (run_worker_loop or launch_visible) and not effective_agent_specs:
        effective_agent_specs = list(DEFAULT_WORKER_LOOP_AGENT_SPECS)
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=goal_id,
        agent_specs=effective_agent_specs,
        session_name=session_name,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        tmux_bin=tmux_bin,
        reasoning_effort=reasoning_effort,
    )
    execution_kind = (
        "loopx_worker_loop"
        if execute and run_worker_loop
        else "visible_worker_launch"
        if execute and launch_visible
        else "worker_loop_preview"
    )
    result_source = (
        "loopx_worker_loop_public_evidence"
        if execute and run_worker_loop
        else "visible_worker_launcher"
        if execute and launch_visible
        else "dry_run_preview"
    )
    payload: dict[str, object] = {
        "ok": True,
        "schema_version": AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "execution_kind": execution_kind,
        "result_source": result_source,
        "goal_id": goal_id,
        "tracking_goal_id": tracking_goal or None,
        "route_contract": {
            "schema_version": "auto_research_demo_frontier_route_v0",
            "goal_surface_mode": goal_surface_mode,
            "frontier_goal_id": goal_id,
            "tracking_goal_id": tracking_goal or None,
            "tracking_goal_drives_frontier": False,
            "visible_lanes_read_goal_id": goal_id,
            "fresh_goal_default": goal_surface_mode == "fresh_demo_goal",
            "inherits_default_goal": goal_surface_mode == "inherited_default_goal",
            "reuses_default_internal_goal": reuses_default_internal_goal,
            "default_internal_goal_id": AUTO_RESEARCH_DEFAULT_GOAL_ID,
            "dedicated_positive_demo_frontier": not reuses_default_internal_goal,
            "reason": (
                "Omitting --goal-id creates an isolated demo goal surface. "
                "Use --goal-id to target a specific research frontier, or --inherit-default-goal "
                "to intentionally reuse the internal shared demo goal. --tracking-goal-id is metadata "
                "for the parent productization goal and must not reroute panes."
            ),
        },
        "agent_id": agent_id,
        "reasoning_effort": reasoning_effort,
        "commands": {
            "one_command_worker_loop": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                run_worker_loop=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "headless_worker_loop": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                run_worker_loop=True,
                headless=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "start_visible_lanes_without_attach": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                run_worker_loop=True,
                no_attach=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "one_command_worker_loop_with_visible_lanes": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                run_worker_loop=True,
                launch_visible=True,
                attach=True,
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
        payload["worker_loop_preview"] = {
            "executed": False,
            "result_source": "dry_run_preview",
            "expected_steps": (
                "seed a demo-local LoopX queue, let role-compatible workers claim "
                "frontier todos, write public-safe evidence, append rollout events, "
                "and read board/acceptance from state"
            ),
            "coordination_pattern": "decentralized_state_a2a",
        }
        payload["claim_summary"] = _demo_claim_summary(payload)
        return payload

    tmp_obj: tempfile.TemporaryDirectory[str] | None = None
    if keep_workspace or launch_visible:
        demo_root = Path(tempfile.mkdtemp(prefix="loopx-auto-research-demo-e2e."))
    else:
        tmp_obj = tempfile.TemporaryDirectory(prefix="loopx-auto-research-demo-e2e.")
        demo_root = Path(tmp_obj.name)
    try:
        visible_control: dict[str, object] | None = None
        visible_registry_path: Path | None = None
        visible_runtime_root_arg: str | None = None

        def ensure_visible_control_plane() -> tuple[dict[str, object], Path, str | None]:
            nonlocal visible_control, visible_registry_path, visible_runtime_root_arg
            if visible_control is None or visible_registry_path is None:
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
            return visible_control, visible_registry_path, visible_runtime_root_arg

        visible_control, visible_registry_path, visible_runtime_root_arg = ensure_visible_control_plane()
        if run_worker_loop:
            worker_agent_ids = [
                str(lane.get("agent_id") or "").strip()
                for lane in supervisor.get("lanes") or []
                if isinstance(lane, dict) and str(lane.get("agent_id") or "").strip()
            ]

            def append_worker_evidence(packet_path: str) -> dict[str, object]:
                return append_auto_research_rollout_events(
                    packet_path=packet_path,
                    registry_path=visible_registry_path,
                    runtime_root_arg=visible_runtime_root_arg,
                    dry_run=False,
                )

            worker_loop = run_auto_research_worker_loop(
                registry_path=visible_registry_path,
                runtime_root_arg=visible_runtime_root_arg,
                goal_id=goal_id,
                agent_ids=worker_agent_ids,
                objective=objective,
                workspace=demo_root / "visible-control-plane",
                output_dir=output_dir,
                execute=True,
                append_evidence=append_worker_evidence,
                lane_count=len(worker_agent_ids),
                visible_lanes_accepted=True,
                complete_selected_todo=True,
                max_rounds=worker_loop_rounds,
            )
            payload["worker_loop"] = worker_loop
            turns = worker_loop.get("turns") if isinstance(worker_loop.get("turns"), list) else []
            dev_metric = next(
                (turn.get("dev_metric") for turn in turns if isinstance(turn, dict) and turn.get("dev_metric") is not None),
                None,
            )
            holdout_metric = next(
                (
                    turn.get("holdout_metric")
                    for turn in turns
                    if isinstance(turn, dict) and turn.get("holdout_metric") is not None
                ),
                None,
            )
            payload["tonight_experience"] = {
                "schema_version": "auto_research_tonight_experience_v0",
                "ready": bool(worker_loop.get("executed_turn_count")),
                "one_command": payload["commands"]["one_command_worker_loop"],
                "goal_id": goal_id,
                "goal_surface_mode": goal_surface_mode,
                "coordination_pattern": "decentralized_state_a2a",
                "workflow_model": "state_projected_frontier_not_dynamic_workflow",
                "driver_role": "polling_driver_only",
                "leader_agent_required": False,
                "worker_loop_round_count": worker_loop.get("round_count"),
                "executed_turn_count": worker_loop.get("executed_turn_count"),
                "completed_turn_count": worker_loop.get("completed_turn_count"),
                "selected_actions": worker_loop.get("selected_actions"),
                "dev_metric": dev_metric,
                "holdout_metric": holdout_metric,
                "positive_result": dev_metric is not None and holdout_metric is not None,
                "state_surfaces": [
                    "demo-local LoopX registry",
                    "quota/frontier selection",
                    "todo completion",
                    "rollout event log",
                ],
                "worker_contract": (
                    "Each role reads the shared LoopX state surface, accepts only its projected "
                    "frontier item, writes public-safe evidence, and completes the selected todo."
                ),
                "public_boundary": {
                    "raw_logs_recorded": False,
                    "private_artifacts_recorded": False,
                    "absolute_paths_recorded": False,
                    "visible_codex_lane_authored": False,
                },
            }
        if launch_visible and visible_launcher is not None:
            (
                visible_control,
                visible_registry_path,
                visible_runtime_root_arg,
            ) = ensure_visible_control_plane()
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
        board, acceptance = _live_board_and_acceptance(
            goal_id=goal_id,
            agent_id=agent_id,
            objective=objective,
            supervisor=supervisor,
            registry_path=visible_registry_path,
            runtime_root_arg=visible_runtime_root_arg,
        )
        payload["board"] = _compact_board(board)
        payload["acceptance"] = _compact_acceptance(acceptance)
        payload["workspace_retained"] = keep_workspace or launch_visible
        if live_evidence_path:
            live_evidence = load_live_codex_e2e_evidence(
                evidence_path=live_evidence_path,
                goal_id=goal_id,
                agent_id=agent_id,
            )
            payload["live_codex_e2e"] = build_live_codex_claim_from_evidence(live_evidence)
        payload["claim_summary"] = _demo_claim_summary(payload)
        return payload
    finally:
        if tmp_obj is not None:
            tmp_obj.cleanup()
