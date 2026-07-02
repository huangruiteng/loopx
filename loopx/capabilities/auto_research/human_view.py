"""Human-readable auto-research renderers.

The auto-research kernel and state readers emit machine payloads. This module
keeps the optional Markdown view separate so production logic does not depend
on legacy presentation helpers.
"""

from __future__ import annotations

from .evidence_packet import AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION


AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION = "auto_research_demo_e2e_result_v0"


def render_auto_research_projection_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    if "frontier" not in payload or "evidence_graph" not in payload:
        return _render_generic(payload)
    frontier = payload["frontier"]  # type: ignore[index]
    graph = payload["evidence_graph"]  # type: ignore[index]
    selected = frontier.get("selected") if isinstance(frontier, dict) else None
    lines = [
        "# LoopX Auto Research Frontier",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- agent_id: `{frontier.get('agent_id')}`",
        f"- selected: `{selected.get('hypothesis_id') if isinstance(selected, dict) else 'none'}`",
        f"- hypotheses: `{graph.get('hypothesis_count')}`",
        f"- evidence events: `{graph.get('evidence_event_count')}`",
        f"- best dev metric: `{graph.get('best_dev_metric')}`",
        f"- best holdout metric: `{graph.get('best_holdout_metric')}`",
        f"- promotion candidates: `{len(frontier.get('promotion_candidates') or [])}`",
        f"- retirement candidates: `{len(frontier.get('retirement_candidates') or [])}`",
    ]
    return "\n".join(lines) + "\n"


def _render_worker_turn(payload: dict[str, object]) -> str:
    frontier_packet = payload.get("frontier") if isinstance(payload.get("frontier"), dict) else {}
    quota = frontier_packet.get("quota") if isinstance(frontier_packet.get("quota"), dict) else {}
    frontier = (
        frontier_packet.get("frontier")
        if isinstance(frontier_packet.get("frontier"), dict)
        else {}
    )
    selected = frontier.get("selected") if isinstance(frontier.get("selected"), dict) else {}
    completion = payload.get("completion") if isinstance(payload.get("completion"), dict) else {}
    append = payload.get("append") if isinstance(payload.get("append"), dict) else {}
    live_evidence = (
        payload.get("live_evidence")
        if isinstance(payload.get("live_evidence"), dict)
        else {}
    )
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    lines = [
        "# LoopX Auto Research Worker Turn",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- quota_should_run: `{quota.get('should_run')}`",
        f"- quota_state: `{quota.get('state')}`",
        f"- user_action_required: `{quota.get('user_action_required')}`",
        f"- selected_todo: `{payload.get('selected_todo_id') or selected.get('todo_id')}`",
        f"- selected_action: `{payload.get('selected_action') or selected.get('allowed_action')}`",
        f"- selected_title: {selected.get('title')}",
        f"- blocker: `{payload.get('blocker')}`",
        f"- blocker_detail: {payload.get('blocker_detail')}",
        f"- executed: `{payload.get('executed')}`",
        f"- would_execute: `{payload.get('would_execute')}`",
        f"- completion_status: `{completion.get('status')}`",
        f"- completion_executed: `{completion.get('executed')}`",
        f"- artifact: `{artifact.get('filename') or artifacts.get('evidence_packet')}`",
        f"- artifact_status: `{payload.get('artifact_status') or payload.get('packet_status')}`",
        f"- dev_metric: `{payload.get('dev_metric')}`",
        f"- holdout_metric: `{payload.get('holdout_metric')}`",
        f"- appended_count: `{append.get('appended_count')}`",
        f"- live_evidence_written: `{live_evidence.get('written')}`",
        f"- public_boundary: raw_logs=`False`, private_artifacts=`False`, paths=`local-only`",
    ]
    return "\n".join(lines) + "\n"


def _render_worker_loop(payload: dict[str, object]) -> str:
    turns = payload.get("turns") if isinstance(payload.get("turns"), list) else []
    lines = [
        "# LoopX Auto Research Worker Loop",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- round_count: `{payload.get('round_count')}`",
        f"- max_rounds: `{payload.get('max_rounds')}`",
        f"- stop_reason: `{payload.get('stop_reason')}`",
        f"- turn_count: `{payload.get('turn_count')}`",
        f"- executed_turn_count: `{payload.get('executed_turn_count')}`",
        f"- completed_turn_count: `{payload.get('completed_turn_count')}`",
        f"- selected_actions: `{', '.join(str(action) for action in payload.get('selected_actions') or [])}`",
        "",
        "## Turns",
        "",
    ]
    if not turns:
        lines.append("- none")
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        lines.append(
            f"- round `{turn.get('round')}` agent `{turn.get('agent_id')}` "
            f"mode `{turn.get('mode')}` action `{turn.get('selected_action')}` "
            f"executed `{turn.get('executed')}` completion `{turn.get('completion_status')}` "
            f"dev `{turn.get('dev_metric')}` holdout `{turn.get('holdout_metric')}`"
        )
    return "\n".join(lines) + "\n"


def _render_demo_e2e(payload: dict[str, object]) -> str:
    worker_loop = payload.get("worker_loop") if isinstance(payload.get("worker_loop"), dict) else {}
    tonight = (
        payload.get("tonight_experience")
        if isinstance(payload.get("tonight_experience"), dict)
        else {}
    )
    supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
    route = payload.get("route_contract") if isinstance(payload.get("route_contract"), dict) else {}
    live = payload.get("visible_worker_proof") if isinstance(payload.get("visible_worker_proof"), dict) else {}
    lines = [
        "# LoopX Auto Research Minimal E2E Demo",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- execution_kind: `{payload.get('execution_kind')}`",
        f"- result_source: `{payload.get('result_source')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- tracking_goal_id: `{payload.get('tracking_goal_id')}`",
        f"- frontier_goal_id: `{route.get('frontier_goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- reasoning_effort: `{payload.get('reasoning_effort')}`",
        f"- worker_loop_executed_turns: `{worker_loop.get('executed_turn_count')}`",
        f"- worker_loop_completed_turns: `{worker_loop.get('completed_turn_count')}`",
        f"- worker_loop_selected_actions: `{worker_loop.get('selected_actions')}`",
        f"- worker_loop_stop_reason: `{worker_loop.get('stop_reason')}`",
        f"- tonight_ready: `{tonight.get('ready')}`",
        f"- tonight_coordination_pattern: `{tonight.get('coordination_pattern')}`",
        f"- tonight_dev_metric: `{tonight.get('dev_metric')}`",
        f"- tonight_holdout_metric: `{tonight.get('holdout_metric')}`",
        f"- tonight_positive_result: `{tonight.get('positive_result')}`",
        f"- visible_lanes_launched: `{live.get('visible_lanes_launched')}`",
        f"- visible_lanes_accepted: `{live.get('visible_lanes_accepted')}`",
        f"- supervisor_lanes: `{supervisor.get('lane_count')}`",
    ]
    return "\n".join(lines) + "\n"


def _render_rollout_append(payload: dict[str, object]) -> str:
    lines = [
        "# LoopX Auto Research Rollout Append",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- events: `{payload.get('event_count')}`",
        f"- appended: `{payload.get('appended_count')}`",
        f"- would_append: `{payload.get('would_append_count')}`",
        f"- skipped_existing: `{payload.get('skipped_existing_count')}`",
    ]
    return "\n".join(lines) + "\n"


def _render_live_evidence(payload: dict[str, object]) -> str:
    visible = payload.get("visible_lanes") if isinstance(payload.get("visible_lanes"), dict) else {}
    evidence = payload.get("lane_evidence") if isinstance(payload.get("lane_evidence"), dict) else {}
    lines = [
        "# LoopX Auto Research Live Evidence",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- source: `{payload.get('source')}`",
        f"- visible_lanes_accepted: `{visible.get('accepted')}`",
        f"- lane_count: `{visible.get('lane_count')}`",
        f"- evidence_events: `{evidence.get('evidence_event_count')}`",
        f"- result_status: `{evidence.get('result_status')}`",
        f"- protected_scope_clean: `{evidence.get('protected_scope_clean')}`",
    ]
    return "\n".join(lines) + "\n"


def _render_supervisor(payload: dict[str, object]) -> str:
    lanes = payload.get("lanes") if isinstance(payload.get("lanes"), list) else []
    route = payload.get("goal_surface_route") if isinstance(payload.get("goal_surface_route"), dict) else {}
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    coordination = (
        payload.get("coordination_model")
        if isinstance(payload.get("coordination_model"), dict)
        else {}
    )
    runner = (
        payload.get("runner_contract")
        if isinstance(payload.get("runner_contract"), dict)
        else {}
    )
    tmux_lifecycle = (
        runner.get("tmux_lifecycle")
        if isinstance(runner.get("tmux_lifecycle"), dict)
        else {}
    )
    one_click = (
        payload.get("one_click_demo")
        if isinstance(payload.get("one_click_demo"), dict)
        else {}
    )
    cli_contract = (
        payload.get("cli_contract")
        if isinstance(payload.get("cli_contract"), dict)
        else {}
    )
    lines = [
        "# LoopX Auto Research Demo Supervisor",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- session_name: `{payload.get('session_name')}`",
        f"- lane_count: `{len(lanes)}`",
        f"- frontier_goal_id: `{route.get('frontier_goal_id')}`",
        f"- leader_agent_required: `{coordination.get('leader_agent_required')}`",
        f"- coordination_pattern: `{coordination.get('pattern')}`",
        f"- starts_tmux: `{boundary.get('starts_tmux')}`",
        f"- runs_codex: `{boundary.get('runs_codex')}`",
        f"- attach: `{tmux_lifecycle.get('attach_command')}`",
        "- start_script: `machine_json_only`",
        "",
        "## Role Profiles",
        "",
    ]
    if not lanes:
        lines.append("- none")
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        profile = (
            lane.get("role_profile")
            if isinstance(lane.get("role_profile"), dict)
            else {}
        )
        lines.append(
            f"- `{lane.get('lane_id')}` agent `{lane.get('agent_id')}` role `{lane.get('role_id')}`"
        )
        lines.append(
            f"  - required_worker_playbook: `{profile.get('required_skill')}`"
        )
        lines.append(f"  - skill_distribution: `{profile.get('skill_distribution')}`")
        lines.append(f"  - worker_skill_source: `{profile.get('worker_skill_source')}`")
    lines.extend(["", "## Lane Timeline", ""])
    if not lanes:
        lines.append("- none")
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        timeline = lane.get("lane_timeline") if isinstance(lane.get("lane_timeline"), list) else []
        lines.append(f"- `{lane.get('lane_id')}`: `{' -> '.join(str(item) for item in timeline)}`")
    lines.extend(
        [
            "",
            "## One-Click Dry Run",
            "",
            f"- mode: `{one_click.get('mode')}`",
            "- command: `loopx auto-research demo-e2e --execute`",
            f"- machine_json_policy: `{cli_contract.get('machine_json_policy')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_evidence_packet(payload: dict[str, object]) -> str:
    hypothesis = payload.get("hypothesis") if isinstance(payload.get("hypothesis"), dict) else {}
    summary = (
        payload.get("evidence_summary")
        if isinstance(payload.get("evidence_summary"), dict)
        else {}
    )
    lines = [
        "# LoopX Auto Research Evidence Packet",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- hypothesis: `{hypothesis.get('hypothesis_id')}`",
        f"- todo: `{hypothesis.get('todo_id')}`",
        f"- status: `{hypothesis.get('status')}`",
        f"- evidence events: `{summary.get('evidence_event_count')}`",
        f"- splits: `{', '.join(summary.get('splits', []))}`",
        f"- negative evidence: `{summary.get('negative_evidence_count')}`",
        f"- protected scope clean: `{summary.get('protected_scope_clean')}`",
    ]
    return "\n".join(lines) + "\n"


def _render_generic(payload: dict[str, object]) -> str:
    lines = [
        "# LoopX Auto Research",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
    ]
    return "\n".join(lines) + "\n"


def render_auto_research_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    schema = payload.get("schema_version")
    if schema == "auto_research_worker_turn_v0":
        return _render_worker_turn(payload)
    if schema == "auto_research_worker_loop_v0":
        return _render_worker_loop(payload)
    if schema == AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION:
        return _render_demo_e2e(payload)
    if schema == "auto_research_demo_supervisor_plan_v0":
        return _render_supervisor(payload)
    if schema == AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION:
        return _render_rollout_append(payload)
    if schema == "auto_research_live_codex_lane_e2e_evidence_v0":
        return _render_live_evidence(payload)
    if schema == "auto_research_evidence_packet_v0":
        return _render_evidence_packet(payload)
    return render_auto_research_projection_markdown(payload)
