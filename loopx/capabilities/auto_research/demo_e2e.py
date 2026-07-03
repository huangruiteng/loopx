from __future__ import annotations

import json
import shlex
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from .demo_supervisor import build_auto_research_demo_supervisor_plan
from .defaults import AUTO_RESEARCH_DEFAULT_GOAL_ID
from .live_evidence import load_live_codex_e2e_evidence
from .preset import (
    auto_research_seed_action_for_role,
    auto_research_seed_title,
    default_auto_research_agent_specs,
)
from .rollout_append import append_auto_research_rollout_events
from .worker_loop import run_auto_research_worker_loop


AppendEvidence = Callable[[str], dict[str, object]]
VisibleLauncher = Callable[..., dict[str, object]]
VisibleWake = Callable[[str, Sequence[str]], dict[str, object]]

AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION = "auto_research_demo_e2e_result_v0"


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
        "default_visible_workspace": "demo_owned_clean_workspace",
        "side_lane_workspace": "visible_codex_tui_workspace",
        "side_lane_worktree_count": 0,
        "side_lane_count": side_count,
        "trust_prompt_avoidance": (
            "demo_owned_clean_workspace_with_persisted_codex_trust_config"
        ),
        "mutation_isolation_policy": (
            "mutating attempts claim an execution boundary from inside the role; "
            "the first visible TUI uses the demo-owned clean workspace unless "
            "the operator passes --workspace"
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
    registry_payload = json.loads(control_registry.read_text(encoding="utf-8"))
    for goal in registry_payload.get("goals", []):
        if isinstance(goal, dict) and str(goal.get("id")) == goal_id:
            goal["workspace_guard_policy"] = {
                "schema_version": "loopx_workspace_guard_policy_v0",
                "side_agent_independent_worktree_required": False,
                "reason": (
                    "auto_research_demo_local_queue uses a demo-owned workspace and "
                    "writes only demo-local LoopX state/evidence; repository edits still "
                    "require an explicit lane-owned execution boundary"
                ),
            }
            break
    control_registry.write_text(
        json.dumps(registry_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    seeded_todos: list[dict[str, object]] = []
    for lane in lanes:
        agent_id = str(lane.get("agent_id") or "").strip()
        role_id = str(lane.get("role_id") or "").strip()
        lane_id = str(lane.get("lane_id") or "").strip()
        action_kind = auto_research_seed_action_for_role(role_id)
        title = auto_research_seed_title(
            action_kind=action_kind,
            role_id=role_id,
            lane_id=lane_id,
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
        "workspace_guard_policy": {
            "side_agent_independent_worktree_required": False,
            "repository_edits_still_require_lane_boundary": True,
        },
        "absolute_paths_recorded": False,
        "private_artifacts_recorded": False,
    }
    return summary, control_registry, str(control_runtime)


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
    wake_visible_after_launch: bool = False,
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
    if wake_visible_after_launch:
        parts.append("--wake-visible-after-launch")
    return " ".join(parts)


def _visible_worker_proof(*, launch_visible: bool) -> dict[str, object]:
    return {
        "schema_version": "auto_research_visible_worker_proof_v0",
        "lane_authored_evidence_loaded": False,
        "pane_local_a2a_rounds_loaded": False,
        "pane_local_a2a_round_count": 0,
        "decentralized_a2a_rounds_verified": False,
        "cadence_wake_loaded": False,
        "cadence_wake_verified": False,
        "visible_lanes_launched": bool(launch_visible),
        "visible_lanes_accepted": False,
        "evidence_source": "not_loaded",
        "reason": (
            "demo-e2e launches real visible Codex worker panes and can load compact "
            "lane-authored evidence; presentation-specific reporting stays outside "
            "the auto-research kernel."
        ),
        "next_step": [
            "let each visible pane run its LoopX frontier tick",
            "append public-safe lane evidence into LoopX state",
            "optionally pass --live-evidence to summarize the compact evidence",
        ],
    }


def _supervisor_summary(supervisor: dict[str, object]) -> dict[str, object]:
    product_spec = (
        supervisor.get("product_spec")
        if isinstance(supervisor.get("product_spec"), dict)
        else {}
    )
    runner_contract = (
        supervisor.get("runner_contract")
        if isinstance(supervisor.get("runner_contract"), dict)
        else {}
    )
    pane_local_a2a = (
        runner_contract.get("pane_local_a2a")
        if isinstance(runner_contract.get("pane_local_a2a"), dict)
        else {}
    )
    decentralized_a2a_driver = (
        runner_contract.get("decentralized_a2a_driver")
        if isinstance(runner_contract.get("decentralized_a2a_driver"), dict)
        else {}
    )
    cli_contract = (
        supervisor.get("cli_contract")
        if isinstance(supervisor.get("cli_contract"), dict)
        else {}
    )
    auto_research = (
        supervisor.get("auto_research")
        if isinstance(supervisor.get("auto_research"), dict)
        else {}
    )
    coordination_model = (
        supervisor.get("coordination_model")
        if isinstance(supervisor.get("coordination_model"), dict)
        else {}
    )
    return {
        "schema_version": supervisor.get("schema_version"),
        "mode": supervisor.get("mode"),
        "lane_count": len(supervisor.get("lanes") or []),
        "reasoning_contract": supervisor.get("reasoning_contract"),
        "uses_generic_runner": bool(
            product_spec.get("uses_generic_runner")
            or auto_research.get("uses_generic_runner")
        ),
        "generic_spec_schema": product_spec.get("schema_version"),
        "runner_contract_schema": runner_contract.get("schema_version"),
        "pane_local_a2a": {
            "tick_command": pane_local_a2a.get("tick_command"),
            "machine_json_policy": pane_local_a2a.get("machine_json_policy"),
            "machine_json_destination": pane_local_a2a.get("machine_json_destination"),
            "rounds_artifact": pane_local_a2a.get("rounds_artifact"),
            "human_default": pane_local_a2a.get("human_default"),
        },
        "decentralized_a2a_driver": {
            "schema_version": decentralized_a2a_driver.get("schema_version"),
            "owner_layer": decentralized_a2a_driver.get("owner_layer"),
            "driver_model": decentralized_a2a_driver.get("driver_model"),
            "coordination_pattern": decentralized_a2a_driver.get("coordination_pattern"),
            "broadcaster_decides_work": (
                decentralized_a2a_driver.get("broadcaster", {}).get("decides_work")
                if isinstance(decentralized_a2a_driver.get("broadcaster"), dict)
                else None
            ),
            "pane_decision_owner": (
                decentralized_a2a_driver.get("pane", {}).get("decision_owner")
                if isinstance(decentralized_a2a_driver.get("pane"), dict)
                else None
            ),
            "user_and_preset_do_not_own_tick_driver": (
                decentralized_a2a_driver.get("acceptance", {}).get(
                    "user_and_preset_do_not_own_tick_driver"
                )
                if isinstance(decentralized_a2a_driver.get("acceptance"), dict)
                else None
            ),
        },
        "machine_json_policy": cli_contract.get("machine_json_policy"),
        "domain_specific_runner_logic": bool(product_spec.get("domain_specific")),
        "kernel_boundary": {
            "state_bus": auto_research.get("state_bus"),
            "presentation_layers_in_kernel": bool(
                auto_research.get("presentation_layers_in_kernel")
            ),
            "coordination_pattern": coordination_model.get("pattern"),
        },
    }


def _compact_live_worker_evidence(evidence: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "auto_research_live_worker_evidence_summary_v0",
        "loaded": True,
        "source": evidence.get("source"),
        "goal_id": evidence.get("goal_id"),
        "agent_id": evidence.get("agent_id"),
        "lane_count": evidence.get("lane_count"),
        "evidence_event_count": evidence.get("evidence_event_count"),
        "result_status": evidence.get("result_status"),
        "protected_scope_clean": bool(evidence.get("protected_scope_clean")),
        "dev_metric": evidence.get("dev_metric"),
        "holdout_metric": evidence.get("holdout_metric"),
        "public_boundary": evidence.get("public_boundary"),
    }


def _compact_visible_pane_a2a_rounds(artifacts: list[dict[str, object]]) -> dict[str, object]:
    lanes = []
    for artifact in artifacts:
        rounds = artifact.get("rounds") if isinstance(artifact.get("rounds"), list) else []
        completed = int(artifact.get("rounds_completed") or 0)
        requested = int(artifact.get("rounds_requested") or 0)
        lanes.append(
            {
                "agent_id": artifact.get("agent_id"),
                "role_id": artifact.get("role_id"),
                "status": artifact.get("status"),
                "rounds_requested": requested,
                "rounds_completed": completed,
                "worker_label": artifact.get("worker_label"),
                "worker_configured": bool(artifact.get("worker_configured")),
                "round_count": len(rounds),
            }
        )
    max_completed = max((int(lane.get("rounds_completed") or 0) for lane in lanes), default=0)
    max_requested = max((int(lane.get("rounds_requested") or 0) for lane in lanes), default=0)
    total_completed = sum(int(lane.get("rounds_completed") or 0) for lane in lanes)
    return {
        "schema_version": "auto_research_visible_pane_a2a_rounds_summary_v0",
        "loaded": bool(lanes),
        "source": "visible_launcher_artifact",
        "coordination_model": "decentralized_state_a2a",
        "workflow_driver": False,
        "lane_count": len(lanes),
        "rounds_completed_total": total_completed,
        "max_rounds_requested": max_requested,
        "max_rounds_completed": max_completed,
        "multi_round_verified": max_completed >= 2,
        "lanes": lanes,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
        },
    }


def _discover_visible_pane_a2a_rounds(
    *,
    runtime_root_arg: str | None,
    session_name: str,
    goal_id: str,
    wait_seconds: float,
) -> dict[str, object] | None:
    if not runtime_root_arg:
        return None
    runtime_root = Path(runtime_root_arg)
    artifact_root = runtime_root / "visible-launcher-artifacts" / session_name

    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        artifacts = []
        if artifact_root.is_dir():
            for candidate in sorted(artifact_root.glob("*/pane-a2a-rounds.public.json")):
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(raw, dict):
                    continue
                if raw.get("schema_version") != "pane_local_a2a_tick_rounds_v0":
                    continue
                if raw.get("source") != "pane_local_a2a_tick":
                    continue
                if raw.get("goal_id") != goal_id:
                    continue
                boundary = raw.get("public_boundary") if isinstance(raw.get("public_boundary"), dict) else {}
                if any(
                    boundary.get(key) is not False
                    for key in (
                        "raw_logs_recorded",
                        "private_artifacts_recorded",
                        "absolute_paths_recorded",
                        "credentials_recorded",
                    )
                ):
                    continue
                artifacts.append(raw)
        if artifacts:
            summary = _compact_visible_pane_a2a_rounds(artifacts)
            if (
                bool(summary.get("multi_round_verified"))
                or int(summary.get("max_rounds_requested") or 0) < 2
                or time.monotonic() >= deadline
            ):
                return summary
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.5)


def _discover_visible_live_evidence(
    *,
    runtime_root_arg: str | None,
    session_name: str,
    goal_id: str,
    wait_seconds: float,
) -> dict[str, object] | None:
    if not runtime_root_arg:
        return None
    runtime_root = Path(runtime_root_arg)
    artifact_root = runtime_root / "visible-launcher-artifacts" / session_name

    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        candidates = []
        if artifact_root.is_dir():
            for artifact_name in (
                "live-codex-e2e-evidence.public.json",
                "live_codex_e2e_evidence.public.json",
            ):
                candidates.extend(artifact_root.glob(f"*/{artifact_name}"))
            candidates = sorted(set(candidates))
        for candidate in candidates:
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw, dict) or raw.get("goal_id") != goal_id:
                continue
            lane_agent_id = str(raw.get("agent_id") or "").strip()
            if not lane_agent_id:
                continue
            try:
                return load_live_codex_e2e_evidence(
                    evidence_path=str(candidate),
                    goal_id=goal_id,
                    agent_id=lane_agent_id,
                )
            except ValueError:
                continue
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.5)


def _load_live_worker_evidence_into_payload(
    *,
    payload: dict[str, object],
    evidence: dict[str, object],
    evidence_source: str,
) -> None:
    payload["live_worker_evidence"] = _compact_live_worker_evidence(evidence)
    visible_proof = payload["visible_worker_proof"]
    if isinstance(visible_proof, dict):
        visible_proof["lane_authored_evidence_loaded"] = True
        visible_proof["visible_lanes_launched"] = True
        visible_proof["visible_lanes_accepted"] = True
        visible_proof["evidence_source"] = evidence_source


def _load_visible_pane_a2a_rounds_into_payload(
    *,
    payload: dict[str, object],
    rounds: dict[str, object],
) -> None:
    payload["visible_pane_a2a_rounds"] = rounds
    visible_proof = payload["visible_worker_proof"]
    if isinstance(visible_proof, dict):
        visible_proof["pane_local_a2a_rounds_loaded"] = bool(rounds.get("loaded"))
        visible_proof["pane_local_a2a_round_count"] = rounds.get("max_rounds_completed")
        visible_proof["decentralized_a2a_rounds_verified"] = bool(
            rounds.get("multi_round_verified")
        )


def _load_visible_wake_into_payload(
    *,
    payload: dict[str, object],
    wake: dict[str, object],
) -> None:
    driver = (
        wake.get("driver_contract")
        if isinstance(wake.get("driver_contract"), dict)
        else {}
    )
    payload["visible_wake"] = {
        "schema_version": wake.get("schema_version"),
        "mode": wake.get("mode"),
        "session_name": wake.get("session_name"),
        "target_lanes": wake.get("target_lanes"),
        "prompt_hash": wake.get("prompt_hash"),
        "coordination_model": wake.get("coordination_model"),
        "wakeup_model": wake.get("wakeup_model"),
        "workflow_driver": bool(wake.get("workflow_driver")),
        "broadcaster_reads_frontier": bool(wake.get("broadcaster_reads_frontier")),
        "broadcaster_selects_todo": bool(wake.get("broadcaster_selects_todo")),
        "pane_decision_owner": wake.get("pane_decision_owner"),
        "driver_contract_schema": driver.get("schema_version"),
        "driver_owner_layer": driver.get("owner_layer"),
        "boundary": wake.get("boundary"),
    }
    visible_proof = payload["visible_worker_proof"]
    if isinstance(visible_proof, dict):
        visible_proof["cadence_wake_loaded"] = True
        visible_proof["cadence_wake_verified"] = (
            wake.get("mode") == "execute"
            and wake.get("coordination_model") == "decentralized_state_a2a"
            and wake.get("wakeup_model") == "fixed_prompt_broadcast"
            and wake.get("workflow_driver") is False
            and wake.get("broadcaster_reads_frontier") is False
            and wake.get("broadcaster_selects_todo") is False
        )


def _numeric_metric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_visible_readiness(payload: dict[str, object]) -> dict[str, object]:
    proof = (
        payload.get("visible_worker_proof")
        if isinstance(payload.get("visible_worker_proof"), dict)
        else {}
    )
    rounds = (
        payload.get("visible_pane_a2a_rounds")
        if isinstance(payload.get("visible_pane_a2a_rounds"), dict)
        else {}
    )
    evidence = (
        payload.get("live_worker_evidence")
        if isinstance(payload.get("live_worker_evidence"), dict)
        else {}
    )
    wake = payload.get("visible_wake") if isinstance(payload.get("visible_wake"), dict) else {}
    supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
    driver = (
        supervisor.get("decentralized_a2a_driver")
        if isinstance(supervisor.get("decentralized_a2a_driver"), dict)
        else {}
    )
    baseline = 1.0
    dev_metric = _numeric_metric(evidence.get("dev_metric"))
    holdout_metric = _numeric_metric(evidence.get("holdout_metric"))
    best_metric = holdout_metric if holdout_metric is not None else dev_metric
    best_source = (
        "round_2_holdout"
        if holdout_metric is not None
        else "round_1_dev"
        if dev_metric is not None
        else None
    )
    protected_scope_clean = evidence.get("protected_scope_clean") is True
    checks = {
        "visible_lanes_accepted": proof.get("visible_lanes_accepted") is True,
        "cadence_wake_verified": proof.get("cadence_wake_verified") is True,
        "pane_local_multi_round_verified": rounds.get("multi_round_verified") is True,
        "lane_authored_evidence_loaded": proof.get("lane_authored_evidence_loaded") is True,
        "protected_scope_clean": protected_scope_clean,
        "positive_metric_over_baseline": (
            best_metric is not None and best_metric > baseline
        ),
        "workflow_driver_false": (
            rounds.get("workflow_driver") is False and wake.get("workflow_driver") is False
        ),
        "kernel_driver_contract_loaded": (
            driver.get("owner_layer") == "generic_multi_agent_kernel"
            and driver.get("user_and_preset_do_not_own_tick_driver") is True
        ),
    }
    ready = all(checks.values())
    return {
        "schema_version": "auto_research_visible_readiness_v0",
        "ready": ready,
        "readiness_level": "ready" if ready else "collecting_evidence",
        "one_command": payload.get("commands", {}).get("one_command_visible_wake_demo")
        if isinstance(payload.get("commands"), dict)
        else None,
        "coordination_pattern": "decentralized_state_a2a",
        "wake_model": wake.get("wakeup_model"),
        "workflow_model": driver.get("driver_model")
        or "fixed_prompt_broadcast_plus_pane_local_state_tick",
        "driver_owner_layer": driver.get("owner_layer"),
        "auto_research_preset_role": "thin_domain_defaults_only",
        "leader_agent_required": False,
        "manual_artifact_inspection_required": not ready,
        "checks": checks,
        "missing_requirements": [key for key, passed in checks.items() if not passed],
        "rounds": {
            "max_completed": rounds.get("max_rounds_completed"),
            "total_completed": rounds.get("rounds_completed_total"),
            "lane_count": rounds.get("lane_count"),
        },
        "improvement_summary": {
            "baseline_metric": baseline,
            "round_1_dev_metric": dev_metric,
            "round_2_holdout_metric": holdout_metric,
            "best_metric": best_metric,
            "best_metric_source": best_source,
            "improved_over_baseline": best_metric is not None and best_metric > baseline,
            "holdout_delta_over_dev": (
                holdout_metric - dev_metric
                if holdout_metric is not None and dev_metric is not None
                else None
            ),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }


def _load_visible_readiness_into_payload(payload: dict[str, object]) -> None:
    payload["visible_readiness"] = _build_visible_readiness(payload)


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
    visible_wake: VisibleWake | None = None,
    wake_visible_after_launch: bool = False,
    goal_surface_mode: str = "explicit_goal",
    agent_specs: Sequence[str] | None = None,
    run_worker_loop: bool = False,
    worker_loop_rounds: int = 3,
    visible_live_evidence_wait_seconds: float = 30.0,
) -> dict[str, object]:
    if launch_visible and not execute:
        raise ValueError("--launch-visible requires --execute")
    if run_worker_loop and not execute:
        raise ValueError("--run-worker-loop requires --execute")
    if worker_loop_rounds < 1:
        raise ValueError("--worker-loop-rounds must be >= 1")
    if launch_visible and visible_launcher is None:
        raise ValueError("--launch-visible requires a visible launcher callback")
    if wake_visible_after_launch and not launch_visible:
        raise ValueError("--wake-visible-after-launch requires --launch-visible")
    if wake_visible_after_launch and visible_wake is None:
        raise ValueError("--wake-visible-after-launch requires a visible wake callback")
    if live_evidence_path and not execute:
        raise ValueError("--live-evidence requires --execute")

    tracking_goal = tracking_goal_id.strip() if isinstance(tracking_goal_id, str) else ""
    if tracking_goal == goal_id:
        tracking_goal = ""
    reuses_default_internal_goal = goal_id == AUTO_RESEARCH_DEFAULT_GOAL_ID
    effective_agent_specs = list(agent_specs or [])
    if (run_worker_loop or launch_visible) and not effective_agent_specs:
        effective_agent_specs = default_auto_research_agent_specs()
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
                launch_visible=True,
                no_attach=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "one_command_visible_wake_demo": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                launch_visible=True,
                no_attach=True,
                wake_visible_after_launch=True,
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
            "load_live_worker_evidence": _command_text(
                cli_bin=cli_bin,
                goal_id=goal_id,
                agent_id=agent_id,
                execute=True,
                live_evidence=True,
                tracking_goal_id=tracking_goal or None,
            ),
            "wake_visible_lanes": (
                f"{shlex.quote(cli_bin)} --format json multi-agent wake --session-name "
                f"{shlex.quote(session_name)} --execute"
            ),
        },
        "supervisor": _supervisor_summary(supervisor),
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
            "writes_loopx_state": bool(execute),
            "launches_visible_lanes": bool(launch_visible),
            "visible_codex_sessions_recorded": False,
        },
        "visible_worker_proof": _visible_worker_proof(launch_visible=launch_visible),
    }
    if not execute:
        payload["worker_loop_preview"] = {
            "executed": False,
            "result_source": "dry_run_preview",
            "expected_steps": (
                "seed a demo-local LoopX queue, let role-compatible workers claim "
                "frontier todos, write public-safe evidence, append rollout events, "
                "and read compact evidence from state"
            ),
            "coordination_pattern": "decentralized_state_a2a",
        }
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
                "positive_result": holdout_metric is not None or dev_metric is not None,
                "positive_result_basis": (
                    "public_safe_dev_and_holdout_evidence"
                    if holdout_metric is not None
                    else "public_safe_dev_evidence"
                ),
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
            visible_proof = payload["visible_worker_proof"]
            if isinstance(visible_proof, dict):
                visible_proof["visible_lanes_launched"] = True
                visible_proof["visible_lanes_accepted"] = bool(visible_acceptance.get("accepted"))
                visible_proof["evidence_source"] = "visible_launcher"
            if wake_visible_after_launch and visible_wake is not None:
                lane_ids = [
                    str(lane).strip()
                    for lane in launch_result.get("started_lanes") or []
                    if str(lane).strip()
                ]
                wake_payload = visible_wake(
                    str(launch_result.get("session_name") or session_name),
                    lane_ids,
                )
                _load_visible_wake_into_payload(
                    payload=payload,
                    wake=wake_payload,
                )
            pane_rounds = _discover_visible_pane_a2a_rounds(
                runtime_root_arg=visible_runtime_root_arg,
                session_name=str(launch_result.get("session_name") or session_name),
                goal_id=goal_id,
                wait_seconds=visible_live_evidence_wait_seconds,
            )
            if pane_rounds is not None:
                _load_visible_pane_a2a_rounds_into_payload(
                    payload=payload,
                    rounds=pane_rounds,
                )
            live_evidence = _discover_visible_live_evidence(
                runtime_root_arg=visible_runtime_root_arg,
                session_name=str(launch_result.get("session_name") or session_name),
                goal_id=goal_id,
                wait_seconds=visible_live_evidence_wait_seconds,
            )
            if live_evidence is not None:
                _load_live_worker_evidence_into_payload(
                    payload=payload,
                    evidence=live_evidence,
                    evidence_source="visible_launcher_artifact",
                )
            _load_visible_readiness_into_payload(payload)
        payload["workspace_retained"] = keep_workspace or launch_visible
        if live_evidence_path:
            live_evidence = load_live_codex_e2e_evidence(
                evidence_path=live_evidence_path,
                goal_id=goal_id,
                agent_id=agent_id,
            )
            _load_live_worker_evidence_into_payload(
                payload=payload,
                evidence=live_evidence,
                evidence_source="live_worker_evidence",
            )
        return payload
    finally:
        if tmp_obj is not None:
            tmp_obj.cleanup()
