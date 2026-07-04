"""Human-readable auto-research renderers.

The auto-research kernel and state readers emit machine payloads. This module
keeps the optional Markdown view separate so production logic does not depend
on legacy presentation helpers.
"""

from __future__ import annotations

from .evidence_packet import AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION
from .user_contract import AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION


AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION = "auto_research_demo_e2e_result_v0"


def _join_or_none(values: object) -> str:
    if isinstance(values, list) and values:
        return ", ".join(str(item) for item in values)
    return "none"


def _dict_value(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _string_value(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _metric_sequence(value: object) -> str:
    if isinstance(value, list) and value:
        return " -> ".join(str(item) for item in value)
    return "none"


_ROLE_DESCRIPTIONS = {
    "research_curator": "research-curator / 研究策展：界定问题、指标和证据边界",
    "hypothesis_proposer": "hypothesis-proposer / 假设生成：提出下一轮可验证假设",
    "research_executor": "research-executor / 研究执行：运行 dev/holdout 证据",
    "evaluator_promoter": "evaluator-promoter / 评估推进：判断提升并触发后续 todo",
}

_AGENT_ROLE_IDS = {
    "research-curator": "research_curator",
    "hypothesis-proposer": "hypothesis_proposer",
    "research-executor": "research_executor",
    "evaluator-promoter": "evaluator_promoter",
}


def _role_description(agent_id: object, role_id: object) -> str:
    role = str(role_id or "").strip()
    agent = str(agent_id or "").strip()
    if not role:
        role = _AGENT_ROLE_IDS.get(agent, "")
    label = _ROLE_DESCRIPTIONS.get(role)
    if label:
        return label
    return agent or role or "unknown-role"


def _role_description_from_spec_line(raw: object) -> str:
    parts = [part.strip() for part in str(raw).split(":")]
    agent_id = parts[0] if parts else ""
    role_id = parts[2] if len(parts) >= 3 else ""
    return _role_description(agent_id, role_id)


def _render_research_roles(
    *,
    minimal_recipe: dict[str, object],
    collective_rounds: dict[str, object],
) -> list[str]:
    kernel = _dict_value(collective_rounds, "kernel_ledger")
    lanes = kernel.get("expected_lanes") if isinstance(kernel.get("expected_lanes"), list) else []
    role_lines: list[str] = []
    for lane in lanes:
        if isinstance(lane, dict):
            role_lines.append(
                f"- {_role_description(lane.get('agent_id'), lane.get('role_id'))}"
            )
    if not role_lines:
        for raw in minimal_recipe.get("preset_recipe_lines") or []:
            role_lines.append(f"- {_role_description_from_spec_line(raw)}")
    if not role_lines:
        return []
    return ["", "## Research Roles / 研究角色", "", *role_lines]


def _render_collective_round_summary(
    *,
    worker_loop: dict[str, object],
    collective_rounds: dict[str, object],
) -> list[str]:
    if not collective_rounds:
        return []
    kernel = _dict_value(collective_rounds, "kernel_ledger")
    outcomes = kernel.get("lane_outcomes") if isinstance(kernel.get("lane_outcomes"), list) else []
    by_round: dict[int, list[dict[str, object]]] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        try:
            round_index = int(outcome.get("round") or 0)
        except (TypeError, ValueError):
            continue
        if round_index > 0:
            by_round.setdefault(round_index, []).append(outcome)

    completed_turns = worker_loop.get("completed_turn_count")
    expected_turns = kernel.get("lane_outcome_count")
    lines = [
        "",
        "## Collective Rounds / 集体研究轮次",
        "",
        (
            f"- verified: `{collective_rounds.get('multi_round_research_verified')}`; "
            f"rounds: `{collective_rounds.get('collective_round_count')}`; "
            f"completed_turns: `{completed_turns}/{expected_turns}`"
        ),
        (
            f"- dev_metric_sequence: `{_metric_sequence(collective_rounds.get('dev_metric_sequence'))}`; "
            f"holdout_metric_sequence: `{_metric_sequence(collective_rounds.get('holdout_metric_sequence'))}`"
        ),
        (
            f"- holdout_improvement_count: `{collective_rounds.get('holdout_improvement_count')}` "
            f"(required `{collective_rounds.get('required_holdout_improvement_count')}`)"
        ),
        (
            "- round_semantics: one round is one quota/frontier opportunity for each "
            "research role; empty lanes are shown as no-op instead of hidden."
        ),
        "",
    ]
    for round_index in sorted(by_round):
        executed: list[str] = []
        noops: list[str] = []
        for outcome in by_round[round_index]:
            agent_id = str(outcome.get("agent_id") or "").strip()
            action = str(outcome.get("selected_action") or "").strip()
            if outcome.get("executed"):
                metric = ""
                if outcome.get("dev_metric") is not None:
                    metric = f" dev={outcome.get('dev_metric')}"
                if outcome.get("holdout_metric") is not None:
                    metric = f" holdout={outcome.get('holdout_metric')}"
                executed.append(f"{agent_id}:{action}{metric}")
            else:
                noops.append(agent_id)
        executed_text = "; ".join(executed) if executed else "none"
        noops_text = "; ".join(noops) if noops else "none"
        lines.append(f"- Round {round_index}: executed `{executed_text}`; no_op `{noops_text}`")
    return lines


def _render_operator_commands(payload: dict[str, object]) -> list[str]:
    commands = _dict_value(payload, "commands")
    user_contract = _dict_value(payload, "user_contract") or payload
    one_click_start = _dict_value(user_contract, "one_click_start")
    visible_launch = _dict_value(payload, "visible_launch")
    launch_result = _dict_value(visible_launch, "launch_result")
    default_start = (
        _string_value(one_click_start, "command")
        or _string_value(commands, "one_question_start_with_visible_wake")
        or _string_value(commands, "one_question_start")
    )
    takeover_start = _string_value(one_click_start, "operator_takeover_command")
    attach_semantics = _string_value(one_click_start, "attach_semantics")
    attach_command = _string_value(launch_result, "attach_command")
    stop_command = _string_value(launch_result, "stop_command")
    lines = ["", "## Operator Commands", ""]
    if default_start:
        lines.append(f"- evidence-first start: `{default_start}`")
    if takeover_start:
        lines.append(f"- immediate takeover: `{takeover_start}`")
    if attach_semantics:
        lines.append(f"- attach_semantics: {attach_semantics}")
    if attach_command:
        lines.append(f"- tmux attach: `{attach_command}`")
    if stop_command:
        lines.append(f"- tmux stop: `{stop_command}`")
    if len(lines) == 3:
        return []
    return lines


def _render_user_contract(payload: dict[str, object]) -> str:
    brief = payload.get("research_brief") if isinstance(payload.get("research_brief"), dict) else {}
    plan = payload.get("action_plan") if isinstance(payload.get("action_plan"), list) else []
    evidence = payload.get("evidence_refs") if isinstance(payload.get("evidence_refs"), dict) else {}
    minimal_recipe = (
        payload.get("minimal_a2a_recipe")
        if isinstance(payload.get("minimal_a2a_recipe"), dict)
        else {}
    )
    one_click_start = (
        payload.get("one_click_start")
        if isinstance(payload.get("one_click_start"), dict)
        else {}
    )
    next_step = (
        payload.get("next_executable_step")
        if isinstance(payload.get("next_executable_step"), dict)
        else {}
    )
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    gates = gate.get("user_judgment_needed") if isinstance(gate.get("user_judgment_needed"), list) else []
    lines = [
        "# LoopX Auto Research",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- question: {payload.get('open_question')}",
        "",
        "## Research Brief",
        "",
        f"- read: `{_join_or_none(brief.get('read'))}`",
        f"- not_read: `{_join_or_none(brief.get('not_read'))}`",
        f"- claim_boundary: {brief.get('claim_boundary')}",
        "",
        "## Action Plan",
        "",
    ]
    if not plan:
        lines.append("- none")
    for item in plan:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('priority')}: {item.get('todo')} "
            f"(`{item.get('owner_layer')}`)"
        )
    lines.extend(
        [
            "",
            "## Evidence Refs",
            "",
            f"- code: `{_join_or_none(evidence.get('code'))}`",
            f"- docs: `{_join_or_none(evidence.get('docs'))}`",
            f"- benchmarks: `{_join_or_none(evidence.get('benchmarks'))}`",
            f"- issues: `{_join_or_none(evidence.get('issues'))}`",
            f"- pull_requests: `{_join_or_none(evidence.get('pull_requests'))}`",
            "",
            "## One-Click Start",
            "",
            f"- command: `{one_click_start.get('command')}`",
            f"- operator_takeover: `{one_click_start.get('operator_takeover_command')}`",
            f"- preview: `{one_click_start.get('preview_command')}`",
            f"- starts: `{one_click_start.get('starts')}`",
            f"- coordination_model: `{one_click_start.get('coordination_model')}`",
            "",
            "## Minimal A2A Recipe",
            "",
            f"- user_lines: `{minimal_recipe.get('user_line_count')}`",
            f"- preset_role_spec_lines: `{minimal_recipe.get('preset_role_spec_line_count')}`",
            f"- user_plus_preset_lines: `{minimal_recipe.get('user_plus_preset_line_count')}`",
            f"- shared_kernel_counted: `{minimal_recipe.get('shared_kernel_counted_as_recipe_lines')}`",
            f"- claim_boundary: {minimal_recipe.get('claim_boundary')}",
        ]
    )
    for line in minimal_recipe.get("user_recipe_lines") or []:
        lines.append(f"- user: `{line}`")
    for line in minimal_recipe.get("preset_recipe_lines") or []:
        lines.append(f"- preset_role: {_role_description_from_spec_line(line)}")
    lines.extend(_render_operator_commands(payload))
    lines.extend(
        [
            "",
            "## Next Executable Step",
            "",
            f"- can_run_automatically: `{next_step.get('can_run_automatically')}`",
            f"- step: {next_step.get('step')}",
            "",
            "## Gate",
            "",
        ]
    )
    if not gates:
        lines.append("- none")
    for item in gates:
        lines.append(f"- {item}")
    lines.append(f"- default_without_user_gate: {gate.get('default_without_user_gate')}")
    return "\n".join(lines) + "\n"


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
            f"role `{turn.get('role_id')}` iteration `{turn.get('demo_iteration')}` "
            f"mode `{turn.get('mode')}` action `{turn.get('selected_action')}` "
            f"executed `{turn.get('executed')}` completion `{turn.get('completion_status')}` "
            f"dev `{turn.get('dev_metric')}` holdout `{turn.get('holdout_metric')}`"
        )
    return "\n".join(lines) + "\n"


def _render_demo_e2e(payload: dict[str, object]) -> str:
    worker_loop = payload.get("worker_loop") if isinstance(payload.get("worker_loop"), dict) else {}
    user_contract = (
        payload.get("user_contract")
        if isinstance(payload.get("user_contract"), dict)
        else {}
    )
    minimal_recipe = (
        user_contract.get("minimal_a2a_recipe")
        if isinstance(user_contract.get("minimal_a2a_recipe"), dict)
        else {}
    )
    tonight = (
        payload.get("tonight_experience")
        if isinstance(payload.get("tonight_experience"), dict)
        else {}
    )
    supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
    route = payload.get("route_contract") if isinstance(payload.get("route_contract"), dict) else {}
    live = payload.get("visible_worker_proof") if isinstance(payload.get("visible_worker_proof"), dict) else {}
    pane_rounds = (
        payload.get("visible_pane_a2a_rounds")
        if isinstance(payload.get("visible_pane_a2a_rounds"), dict)
        else {}
    )
    collective_rounds = (
        payload.get("collective_research_rounds")
        if isinstance(payload.get("collective_research_rounds"), dict)
        else {}
    )
    readiness = (
        payload.get("visible_readiness")
        if isinstance(payload.get("visible_readiness"), dict)
        else {}
    )
    contract_acceptance = (
        payload.get("contract_acceptance")
        if isinstance(payload.get("contract_acceptance"), dict)
        else {}
    )
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    improvement = (
        readiness.get("improvement_summary")
        if isinstance(readiness.get("improvement_summary"), dict)
        else {}
    )
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
        f"- user_contract_accepted: `{contract_acceptance.get('accepted')}`",
        f"- one_question_contract: `{commands.get('one_question_contract')}`",
        f"- one_question_start: `{commands.get('one_question_start')}`",
        f"- minimal_a2a_user_plus_preset_lines: `{minimal_recipe.get('user_plus_preset_line_count')}`",
        f"- minimal_a2a_shared_kernel_counted: `{minimal_recipe.get('shared_kernel_counted_as_recipe_lines')}`",
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
        f"- visible_pane_local_ticks: `{pane_rounds.get('max_rounds_completed')}`",
        f"- pane_ticks_count_as_research_rounds: `{pane_rounds.get('counts_as_collective_research_round')}`",
        f"- collective_research_rounds: `{collective_rounds.get('collective_round_count')}`",
        f"- collective_research_rounds_verified: `{collective_rounds.get('multi_round_research_verified')}`",
        f"- holdout_metric_sequence: `{collective_rounds.get('holdout_metric_sequence')}`",
        f"- holdout_improvement_count: `{collective_rounds.get('holdout_improvement_count')}`",
        f"- decentralized_a2a_rounds_verified: `{live.get('decentralized_a2a_rounds_verified')}`",
        f"- visible_readiness_ready: `{readiness.get('ready')}`",
        f"- visible_readiness_level: `{readiness.get('readiness_level')}`",
        f"- visible_best_metric: `{improvement.get('best_metric')}`",
        f"- visible_holdout_delta_over_dev: `{improvement.get('holdout_delta_over_dev')}`",
        f"- supervisor_lanes: `{supervisor.get('lane_count')}`",
    ]
    lines.extend(
        _render_research_roles(
            minimal_recipe=minimal_recipe,
            collective_rounds=collective_rounds,
        )
    )
    lines.extend(
        _render_collective_round_summary(
            worker_loop=worker_loop,
            collective_rounds=collective_rounds,
        )
    )
    if minimal_recipe:
        lines.extend(
            [
                "",
                "## Minimal A2A Recipe",
                "",
                f"- user_plus_preset_lines: `{minimal_recipe.get('user_plus_preset_line_count')}`",
                f"- user_lines: `{minimal_recipe.get('user_line_count')}`",
                f"- preset_role_spec_lines: `{minimal_recipe.get('preset_role_spec_line_count')}`",
                f"- shared_kernel_counted: `{minimal_recipe.get('shared_kernel_counted_as_recipe_lines')}`",
                f"- coordination_model: `{minimal_recipe.get('coordination_model')}`",
            ]
        )
        for line in minimal_recipe.get("preset_recipe_lines") or []:
            lines.append(f"- preset_role: {_role_description_from_spec_line(line)}")
    lines.extend(_render_operator_commands(payload))
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
    minimal_recipe = (
        payload.get("minimal_a2a_recipe")
        if isinstance(payload.get("minimal_a2a_recipe"), dict)
        else {}
    )
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
            "## Minimal A2A Recipe",
            "",
            f"- user_plus_preset_lines: `{minimal_recipe.get('user_plus_preset_line_count')}`",
            f"- user_lines: `{minimal_recipe.get('user_line_count')}`",
            f"- preset_role_spec_lines: `{minimal_recipe.get('preset_role_spec_line_count')}`",
            f"- shared_kernel_counted: `{minimal_recipe.get('shared_kernel_counted_as_recipe_lines')}`",
            f"- coordination_model: `{minimal_recipe.get('coordination_model')}`",
            "",
            "",
            "## One-Click Dry Run",
            "",
            f"- mode: `{one_click.get('mode')}`",
            "- command: `loopx auto-research start \"<open question>\" --execute`",
            "- operator_takeover: `loopx auto-research start \"<open question>\" --execute --attach`",
            f"- machine_json_policy: `{cli_contract.get('machine_json_policy')}`",
            f"- tmux attach: `{tmux_lifecycle.get('attach_command')}`",
            f"- tmux stop: `{tmux_lifecycle.get('stop_command')}`",
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
    if schema == AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION:
        return _render_user_contract(payload)
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
