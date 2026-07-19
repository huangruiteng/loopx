from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .agent_registry import normalize_registered_agents
from .project_prompt import (
    render_available_capability_args,
    render_cli_preflight,
    render_quota_guard_command,
    render_quota_spend_command,
    render_refresh_state_command,
    render_scheduler_execution_args,
)
from .control_plane.todos.contract import (
    normalize_required_capabilities,
    normalize_todo_claimed_by,
)
from .control_plane.agents.runtime_model import (
    AgentRuntimeModel,
    PEER_AGENT_PROFILE_SCHEMA_VERSION,
)


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."
USER_TODO_FINAL_MESSAGE_RULE = (
    "notify=NOTIFY: concrete actions/todos, including non_blocking at false/0; "
    "never only \"owner gate\"; required missing -> "
    '"具体 user todo 未投影，需修复 LoopX 状态投影". '
    "Only notify=DONT_NOTIFY + false/0: quiet."
)
SCHEDULER_HINT_APPLICATION_RULE = (
    "`scheduler_hint` no-spend. host_action=pause_or_delete_current_heartbeat -> "
    "automation_update stop once, verify, end; else apply_needed -> RRULE then "
    "ack/failure_hint; ack_needed -> ack."
)
SCHEDULER_HINT_COMPACT_RULE = (
    "host_action=pause_or_delete_current_heartbeat: automation_update stop; "
    "else RRULE apply/ack/fail. No spend."
)
SCHEDULER_HINT_THIN_RULE = (
    "host_action=pause_or_delete_current_heartbeat->automation_update stop(no-spend); "
    "else RRULE/ack/fail."
)
RUNTIME_CAPABILITY_PROJECTION_THIN_RULE = (
    "Observed capabilities -> `--available-capability`; never user gates."
)
EXPLORE_GRAPH_DELIVERY_RULE = (
    "Graph-on: material refresh must sync configured sinks and verify "
    "row/result-id readback before final delivery; unsatisfied -> retry or "
    "blocker/successor. Explore Harness stays independent."
)
EXPLORE_GRAPH_DELIVERY_THIN_RULE = (
    "Graph-on: sync sinks; verify row/result-id readback before delivery; "
    "else retry/blocker/successor. "
    "Explore Harness independent."
)
INTERFACE_BUDGET_CHARS = {
    "full": 12_000,
    "compact": 6_200,
    "brief": 3_500,
    "thin": 1_570,
}


def heartbeat_prompt_mode(
    *,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
) -> str:
    if full:
        return "full"
    if thin:
        return "thin"
    if brief:
        return "brief"
    if compact:
        return "compact"
    return "thin"


def prompt_budget_text(text: str, *, goal_id: str, active_state: str) -> str:
    return text.replace(goal_id, "<GOAL_ID>").replace(active_state, "<ACTIVE_STATE>")


def normalize_agent_scope(value: Any) -> str | None:
    candidate = " ".join(str(value or "").strip().split())
    if not candidate:
        return None
    if len(candidate) > 180 or any(char in candidate for char in "<>"):
        raise ValueError("agent scope must be compact text without angle brackets")
    return candidate


def normalize_agent_scopes(values: list[str] | tuple[str, ...] | None) -> list[str]:
    scopes: list[str] = []
    for value in values or []:
        scope = normalize_agent_scope(value)
        if scope and scope not in scopes:
            scopes.append(scope)
    return scopes


def agent_profile_scopes(profile: dict[str, Any] | None) -> list[str]:
    if not isinstance(profile, dict):
        return []
    raw_scopes: list[Any] = []
    for key in ("scope_summary", "default_scope", "scope"):
        value = profile.get(key)
        if isinstance(value, list):
            raw_scopes.extend(value)
        elif value:
            raw_scopes.append(value)
    for key in ("scope_summaries", "default_scopes", "scopes"):
        value = profile.get(key)
        if isinstance(value, list):
            raw_scopes.extend(value)
    return normalize_agent_scopes(raw_scopes)


def agent_profile_prompt_projection(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(profile, dict):
        return None
    public_keys = {
        "schema_version",
        "agent_id",
        "profile_role",
        "scope_summary",
        "default_scope",
        "scope",
        "scope_summaries",
        "default_scopes",
        "scopes",
        "default_task_classes",
        "vision_requirement",
        "preferred_action_kinds",
        "avoid_action_kinds",
    }
    projection = {key: value for key, value in profile.items() if key in public_keys}
    projection["schema_version"] = PEER_AGENT_PROFILE_SCHEMA_VERSION
    return projection or None


def agent_prompt_command_args(*, agent_id: str | None, agent_scopes: list[str]) -> str:
    parts: list[str] = []
    if agent_id:
        parts.extend(["--agent-id", agent_id])
    for scope in agent_scopes:
        parts.extend(["--agent-scope", scope])
    return "".join(f" {shlex.quote(part)}" for part in parts)


def build_peer_identity_required_error(
    *,
    goal_id: str,
    cli_bin: str,
    active_state_arg: str,
    full: bool,
    compact: bool,
    brief: bool,
    thin: bool,
    registered_agents: list[str],
) -> str:
    mode_arg = (
        " --thin"
        if thin
        else " --brief"
        if brief
        else " --compact"
        if compact
        else " --full"
        if full
        else ""
    )
    base = (
        f"{cli_bin} heartbeat-prompt{mode_arg} "
        f"--goal-id {shlex.quote(goal_id)}{active_state_arg}"
    )
    examples = "; ".join(
        f"`{base} --agent-id {shlex.quote(agent)} "
        "--agent-scope 'peer task claims and leases'`"
        for agent in registered_agents[:2]
    )
    return (
        "identity-aware peer heartbeat prompt required: "
        f"coordination.registered_agents is configured for goal_id={goal_id!r}, "
        "so automation prompts without --agent-id are not accepted. Regenerate each "
        f"installed automation with its registered identity. Examples: {examples}."
    )


def render_peer_agent_scope_instruction(
    *,
    goal_id: str,
    agent_id: str | None,
    agent_scopes: list[str],
    cli_bin: str,
    compact: bool = False,
    thin: bool = False,
) -> str:
    if not agent_id and not agent_scopes:
        return ""
    identity = agent_id or "<registered-agent-id>"
    scope_text = "; ".join(agent_scopes) if agent_scopes else "registered peer lane"
    scope_text = scope_text.rstrip(".!?")
    claim_command = (
        f"{cli_bin} todo claim --goal-id {goal_id} --todo-id <todo_id> "
        f"--claimed-by {agent_id} --agent-id {agent_id}"
        if agent_id
        else f"{cli_bin} todo claim --goal-id {goal_id} --todo-id <todo_id> "
        "--claimed-by <agent_id> --agent-id <agent_id>"
    )
    peer_rule = (
        "You are an equal peer agent. Claim or lease in-scope work before delivery; "
        "use an independent worktree for repository writes; follow todo continuation "
        "policy for direct completion, same-agent continuation, or independent review. "
        "Task-scoped coordination does not grant durable authority over other agents."
    )
    if thin:
        return (
            f"Equal peer `{identity}` (peer_v1); scope: {scope_text}. Claim/lease first; "
            "independent repo worktree; todo continuation; no cross-agent authority; "
            "no scope in todo metadata."
        )
    if compact:
        return (
            f"Agent identity and scope: agent_id `{identity}`; model: peer_v1; "
            f"scope: {scope_text}. {peer_rule} Claim: `{claim_command}`. "
            "Do not write scope into todo metadata."
        )
    return f"""Agent identity and scope:

- agent_id: `{identity}`
- agent_model: `peer_v1`
- scope: {scope_text}

{peer_rule}

Before delivery, claim an in-scope open todo:

```bash
{claim_command}
```

If a todo is claimed or leased by another peer, choose another in-scope item or
report no in-scope work. Scope belongs in the heartbeat prompt, not todo metadata.
"""


def build_interface_budget(
    *,
    task_body: str,
    goal_id: str,
    active_state: str,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
) -> dict[str, Any]:
    mode = heartbeat_prompt_mode(full=full, compact=compact, brief=brief, thin=thin)
    budget_text = prompt_budget_text(task_body, goal_id=goal_id, active_state=active_state)
    budget_chars = len(budget_text)
    max_chars = INTERFACE_BUDGET_CHARS[mode]
    return {
        "mode": mode,
        "char_count": len(task_body),
        "line_count": len(task_body.splitlines()),
        "budget_char_count": budget_chars,
        "max_chars": max_chars,
        "within_budget": budget_chars <= max_chars,
    }


def build_heartbeat_prompt(
    *,
    goal_id: str,
    active_state: Path | None = None,
    active_state_source: str = "explicit",
    resolved_active_state: Path | None = None,
    material_queue_rule: str | None = None,
    permission_rule: str | None = None,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
    cli_bin: str = "loopx",
    agent_id: str | None = None,
    agent_scopes: list[str] | tuple[str, ...] | None = None,
    agent_profile: dict[str, Any] | None = None,
    registered_agents: list[str] | tuple[str, ...] | None = None,
    available_capabilities: list[str] | tuple[str, ...] | None = None,
    runtime_profile: str | None = None,
    scheduler_execution_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not (full or compact or brief or thin):
        thin = True
    effective_resolved_active_state = resolved_active_state or active_state
    active_state_text = str(active_state.expanduser()) if active_state else "the registry-declared active state"
    if active_state:
        resolved_active_state_source = active_state_source
    else:
        resolved_active_state_source = "registry" if active_state_source == "explicit" else active_state_source
    active_state_arg = f" --active-state {active_state_text}" if active_state else ""
    resolved_material_rule = material_queue_rule or DEFAULT_MATERIAL_QUEUE_RULE
    resolved_permission_rule = permission_rule or DEFAULT_PERMISSION_RULE
    normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    if agent_id and not normalized_agent_id:
        raise ValueError("agent_id must be a public-safe token such as codex-main-control")
    explicit_agent_scopes = normalize_agent_scopes(agent_scopes)
    profile_agent_scopes = agent_profile_scopes(agent_profile)
    normalized_agent_scopes = explicit_agent_scopes or profile_agent_scopes
    agent_scope_source = "argument" if explicit_agent_scopes else "agent_profile_v1" if profile_agent_scopes else None
    if normalized_agent_scopes and not normalized_agent_id:
        raise ValueError("--agent-scope requires --agent-id so claimed_by uses a registered agent")
    normalized_registered_agents = normalize_registered_agents(registered_agents)
    if normalized_registered_agents and not normalized_agent_id:
        raise ValueError(
            build_peer_identity_required_error(
                goal_id=goal_id,
                cli_bin=cli_bin,
                active_state_arg=active_state_arg,
                full=full,
                compact=compact,
                brief=brief,
                thin=thin,
                registered_agents=normalized_registered_agents,
            )
        )
    if normalized_agent_id:
        if registered_agents is not None and not normalized_registered_agents:
            raise ValueError("agent_id cannot be used until registered_agents are configured")
        if normalized_registered_agents and normalized_agent_id not in normalized_registered_agents:
            raise ValueError(
                f"agent_id={normalized_agent_id!r} is not registered; "
                f"registered_agents={', '.join(normalized_registered_agents)}"
            )
    agent_role = "peer-agent" if normalized_agent_id else None
    command_agent_scopes = explicit_agent_scopes
    agent_args = agent_prompt_command_args(
        agent_id=normalized_agent_id,
        agent_scopes=command_agent_scopes,
    )
    normalized_available_capabilities = normalize_required_capabilities(
        available_capabilities
    )
    capability_args = render_available_capability_args(
        normalized_available_capabilities
    )
    agent_scope_instruction = render_peer_agent_scope_instruction(
        goal_id=goal_id,
        agent_id=normalized_agent_id,
        agent_scopes=normalized_agent_scopes,
        cli_bin=cli_bin,
        compact=compact or brief,
        thin=thin,
    )
    quota_guard_command = render_quota_guard_command(
        goal_id,
        cli_bin=cli_bin,
        agent_id=normalized_agent_id,
        available_capabilities=normalized_available_capabilities,
        runtime_profile=runtime_profile,
        scheduler_execution_context=scheduler_execution_context,
    )
    quota_spend_command = render_quota_spend_command(
        goal_id,
        source="heartbeat",
        cli_bin=cli_bin,
        agent_id=normalized_agent_id,
        available_capabilities=normalized_available_capabilities,
    )
    refresh_state_command = render_refresh_state_command(
        goal_id,
        cli_bin=cli_bin,
        agent_id=normalized_agent_id,
    )
    progress_refresh_state_command = render_refresh_state_command(
        goal_id,
        cli_bin=cli_bin,
        agent_id=normalized_agent_id,
        classification="<PUBLIC_SAFE_PROGRESS_CLASSIFICATION>",
        delivery_batch_scale="multi_surface",
        delivery_outcome="outcome_progress",
    )
    cli_preflight = render_cli_preflight(cli_bin=cli_bin)
    scheduler_args = render_scheduler_execution_args(
        runtime_profile=runtime_profile,
        scheduler_execution_context=scheduler_execution_context,
    )
    expanded_prompt_command = f"{cli_bin} heartbeat-prompt --full --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}{scheduler_args}"
    compact_prompt_command = f"{cli_bin} heartbeat-prompt --compact --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}{scheduler_args}"
    brief_prompt_command = f"{cli_bin} heartbeat-prompt --brief --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}{scheduler_args}"
    thin_prompt_command = f"{cli_bin} heartbeat-prompt --thin --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}{scheduler_args}"
    if thin:
        task_body_renderer = render_thin_heartbeat_task_body
    elif brief:
        task_body_renderer = render_brief_heartbeat_task_body
    elif compact:
        task_body_renderer = render_compact_heartbeat_task_body
    else:
        task_body_renderer = render_heartbeat_task_body
    task_body = task_body_renderer(
        goal_id=goal_id,
        active_state=active_state_text,
        cli_preflight=cli_preflight,
        quota_guard_command=quota_guard_command,
        quota_spend_command=quota_spend_command,
        refresh_state_command=refresh_state_command,
        progress_refresh_state_command=progress_refresh_state_command,
        material_queue_rule=resolved_material_rule,
        permission_rule=resolved_permission_rule,
        cli_bin=cli_bin,
        agent_scope_instruction=agent_scope_instruction,
        expanded_prompt_command=expanded_prompt_command,
        compact_prompt_command=compact_prompt_command,
        brief_prompt_command=brief_prompt_command,
        thin_prompt_command=thin_prompt_command,
    )
    payload = {
        "ok": True,
        "goal_id": goal_id,
        "active_state": active_state_text,
        "active_state_source": resolved_active_state_source,
        "resolved_active_state": str(effective_resolved_active_state.expanduser())
        if effective_resolved_active_state
        else None,
        "compact": compact,
        "brief": brief,
        "thin": thin,
        "cli_bin": cli_bin,
        "agent_id": normalized_agent_id,
        "agent_role": agent_role,
        "agent_scopes": normalized_agent_scopes,
        "agent_scope_source": agent_scope_source,
        "agent_profile": agent_profile_prompt_projection(agent_profile),
        "registered_agents": normalized_registered_agents,
        "runtime_profile": runtime_profile,
        "scheduler_execution_context": scheduler_execution_context,
        "expanded_prompt_command": expanded_prompt_command,
        "compact_prompt_command": compact_prompt_command,
        "brief_prompt_command": brief_prompt_command,
        "thin_prompt_command": thin_prompt_command,
        "quota_guard_command": quota_guard_command,
        "quota_spend_command": quota_spend_command,
        "refresh_state_command": refresh_state_command,
        "progress_refresh_state_command": progress_refresh_state_command,
        "cli_preflight": cli_preflight,
        "material_queue_rule": resolved_material_rule,
        "permission_rule": resolved_permission_rule,
        "interface_budget": build_interface_budget(
            task_body=task_body,
            goal_id=goal_id,
            active_state=active_state_text,
            full=full,
            compact=compact,
            brief=brief,
            thin=thin,
        ),
        "task_body": task_body,
    }
    payload["agent_model"] = AgentRuntimeModel.PEER_V1.value
    if thin:
        payload.pop("compact_prompt_command", None)
        payload.pop("brief_prompt_command", None)
    return payload


def build_heartbeat_prompt_error_payload(
    *,
    goal_id: str,
    error: str,
    active_state: Path | None = None,
    active_state_source: str | None = None,
    resolved_active_state: Path | None = None,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
    cli_bin: str = "loopx",
    agent_id: str | None = None,
    agent_scopes: list[str] | tuple[str, ...] | None = None,
    registered_agents: list[str] | tuple[str, ...] | None = None,
    available_capabilities: list[str] | tuple[str, ...] | None = None,
    material_queue_rule: str | None = None,
    permission_rule: str | None = None,
) -> dict[str, Any]:
    if not (full or compact or brief or thin):
        thin = True
    active_state_text = str(active_state.expanduser()) if active_state else "the registry-declared active state"
    source = active_state_source or ("explicit" if active_state else "registry")
    active_state_arg = f" --active-state {active_state_text}" if active_state else ""
    projected_agent_scopes = []
    for value in agent_scopes or []:
        scope = " ".join(str(value or "").strip().split())
        if scope and scope not in projected_agent_scopes:
            projected_agent_scopes.append(scope)
    agent_args = agent_prompt_command_args(
        agent_id=str(agent_id).strip() if agent_id else None,
        agent_scopes=projected_agent_scopes,
    )
    projected_available_capabilities = normalize_required_capabilities(
        available_capabilities
    )
    capability_args = render_available_capability_args(
        projected_available_capabilities
    )
    expanded_prompt_command = f"{cli_bin} heartbeat-prompt --full --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}"
    compact_prompt_command = f"{cli_bin} heartbeat-prompt --compact --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}"
    brief_prompt_command = f"{cli_bin} heartbeat-prompt --brief --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}"
    thin_prompt_command = f"{cli_bin} heartbeat-prompt --thin --goal-id {goal_id}{active_state_arg}{agent_args}{capability_args}"
    normalized_registered_agents = normalize_registered_agents(registered_agents)
    payload = {
        "ok": False,
        "goal_id": goal_id,
        "error": error,
        "active_state": active_state_text,
        "active_state_source": source,
        "resolved_active_state": str(resolved_active_state.expanduser()) if resolved_active_state else None,
        "compact": compact,
        "brief": brief,
        "thin": thin,
        "cli_bin": cli_bin,
        "agent_id": str(agent_id).strip() if agent_id else None,
        "agent_role": None,
        "agent_scopes": projected_agent_scopes,
        "agent_scope_source": "argument" if projected_agent_scopes else None,
        "agent_profile": None,
        "registered_agents": normalized_registered_agents,
        "expanded_prompt_command": expanded_prompt_command,
        "compact_prompt_command": compact_prompt_command,
        "brief_prompt_command": brief_prompt_command,
        "thin_prompt_command": thin_prompt_command,
        "quota_guard_command": None,
        "quota_spend_command": None,
        "cli_preflight": None,
        "material_queue_rule": material_queue_rule,
        "permission_rule": permission_rule,
        "interface_budget": None,
        "task_body": None,
    }
    payload["agent_model"] = AgentRuntimeModel.PEER_V1.value
    return payload


def render_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    refresh_state_command: str,
    progress_refresh_state_command: str,
    material_queue_rule: str,
    permission_rule: str,
    cli_bin: str,
    agent_scope_instruction: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    scope_block = f"\n{agent_scope_instruction}\n" if agent_scope_instruction else ""
    return f"""Advance `{goal_id}` using `{active_state}`.

Generic LoopX lifecycle. Keep project-specific branching out of the
automation prompt. Put local policy in registry, active-state sections, adapter
output, `quota should-run.goal_boundary`, or boundary rules; if a lifecycle
rule is needed, update `{cli_bin} heartbeat-prompt` so all projects inherit it.
{scope_block}

Before spending delivery compute, first make the LoopX CLI reachable and
run the quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If that preflight still fails: no work/spend; quiet `DONT_NOTIFY`.

`lark_event_inbox`: `reply_due`: drain -> effect/reply/readback/ACK.

{USER_TODO_FINAL_MESSAGE_RULE}

If the result says `should_run=false`:

- If `state=operator_gate`, treat it as a user/controller interaction. Read
  `gate_prompt`, `operator_question`, `recommended_action`,
  `next_handoff_condition`, `missing_gates`, `user_todo_summary`, and
  `agent_todo_summary`. If not surfaced recently, return heartbeat `NOTIFY`
  with one concise Chinese question listing the gate and expected reply format.
  If `user_todo_summary.open_count > 0`, list existing open user todos even
  when nothing new was found; never say "no new user action".
  Do not execute `agent_command`, adapter work, write-control, production
  actions, or the gated path while asking.
- If `notify_user_on_open_todo=true`, existing open `user_todo_summary` is a
  blocker-push opportunity, not a silent skip. For focus/wait/evidence lanes,
  a user/owner answer can unlock progress. If the payload explicitly includes
  `open_todo_notification_policy=repeat_until_resolved`, repeat until resolved,
  except `user_gate_notification_cooldown.notification_suppressed=true`: keep
  the gate pending and `DONT_NOTIFY` until its reminder window/change.
  Else `NOTIFY` in Chinese with up to three
  `first_open_items`, `open_todo_notify_reason`, and reply format: `done`,
  `defer/not now`, or evidence link/date/conclusion. No delivery/spend.
- If the payload also says `safe_bypass_allowed=true` and the same gate has
  already been surfaced, the gate blocks only the gated delivery path. You may
  do exactly one bounded safe-bypass step from the Priority Stack that does not
  depend on that gate; validate, write back, optionally refresh, spend once, and
  report compactly. If `user_todo_summary.open_count > 0`, include those todos
  and do not say "no new user action". If none exists, report the gate.
- If `effective_action=monitor_quiet_skip`, run one no-spend
  `quota monitor-poll --goal-id {goal_id} --source heartbeat --execute`, rerun
  guard; quiet unless autonomous replan. No delivery edits/spend; unchanged
  monitor-only polls are not self-stop signals.
- If `waiting_on=external_evidence` or `state=waiting`, and this automation is
  explicitly a monitor, run at most one bounded read-only observation poll using
  project-approved status/log/metric/marker surfaces named in active state,
  `recommended_action`, or `goal_boundary.next_probe`. Unchanged evidence:
  quiet `DONT_NOTIFY`, no edits, no spend. New eval/fail/complete/blocker/
  approval/CI/deploy/data evidence: report, write back only allowed canonical
  state/board/ledger, add todos if needed, then spend once after validation.
  Still do not launch/stop/restart/sync/design code or mutate production unless
  `should_run=true` or the user explicitly authorizes it.
- Otherwise, do not do implementation work, adapter work, file edits, research,
  or project exploration in this turn. Return a quiet heartbeat `DONT_NOTIFY`
  response with the skip reason.
  {SCHEDULER_HINT_APPLICATION_RULE} Codex App cadence changes are host
  scheduling updates only; they never consume quota or authorize delivery work.

If the result says `should_run=true`:

1. Read the active state, Priority Stack, recent progress, and critic.
   When you inspect current LoopX routing, use the current status queue:
   `attention_queue.items` and each item's `project_asset` are authoritative
   for owner, gate, waiting party, and next action. If `project_asset` is absent
   or legacy/raw fallback, raw queue fields are not owner/gate/stop authority. Treat
   `run_history.latest_runs` as evidence and drill-down only; it may be limited
   by status command limits or filters, so do not decide whether a gate is
   pending or approved from latest runs alone. Also inspect `goal_boundary` and
   guard `user_todo_summary`. Stop for an open user/owner todo only when it
   belongs to this goal's guard payload or current project asset and blocks the
   selected path; then use the blocker-push pattern above. Dependency or
   sibling-goal todos found in `attention_queue.items` should be recorded as
   dependency blockers; they must not consume the whole eligible turn. Choose a
   gate-independent P0/P1/P2 candidate for this goal when one exists.
   If `effective_action=outcome_floor_recovery` or
   `recovery_delivery_allowed=true` or
   `safe_bypass_kind=outcome_floor_recovery`, produce the required
   ranker/cross-domain evidence artifact named by `must_advance`, or write back
   the concrete blocker. Do not fall through to ordinary delivery,
   surface propagation, or synthetic-only chains.
   Read `execution_obligation`: `notify` is not an execution gate;
   `must_attempt_work=true` means one bounded segment even with
   `notify=DONT_NOTIFY`; quiet no-op needs `must_attempt_work=false` and no
   `notify_user_on_open_todo=true` blocker-push notification. Use
   `scheduler_hint` for wakeup and unchanged-loop limits. For Codex App:
   `apply_needed=true` -> update `recommended_rrule` once; on success run
   `ack_hint.cli_args`; on failure/timeout do not retry or ack, run
   `failure_hint.cli_args` once. LoopX suppresses that target/host pair until
   either changes; continue under the observed host cadence. Else
   `ack_needed=true` -> run that bound ack directly; else skip.
   LoopX owns reset/progression state. It is scheduling only, not delivery
   permission. Then use
   `heartbeat_recommendation`: `recommended_mode=run_first_read_only_map` means
   run its `command` as a real read-only map, then
   validate/save the `read_only_project_map` result, append exactly one
   heartbeat spend, sync or refresh state if needed, and `NOTIFY`. If it says
   `recommended_mode=mapped_noop_if_unchanged` with `stop_if_unchanged=true`,
   and you find no new user instruction, owner evidence, agent todo, stale
   source, or safe handoff, return quiet `DONT_NOTIFY`: do not run, edit, or
   spend.
   Check `delivery_batch_scale`, `delivery_outcome`,
   `post_handoff_outcome_gap_streak`, and `handoff_delivery_contract`; for
   repeated-small or surface-only loops, obey the contract.
2. Run a short steering audit before choosing work: list at least three
   plausible next-action candidates across different P0/P1/P2 lanes when
   useful; if the same topic has consumed several recent delivery slices, apply
   a continuation check and state why continuing still wins; keep compute quota
   separate from focus quota; record any losing high-value candidate that should
   not be forgotten. Include a product bottleneck lens: ask whether the core
   goal is currently bottlenecked by user experience, agent capability,
   evidence quality, adapter readiness, or priority-rule gaps, and promote one
   concrete bottleneck candidate when it should outrank the nearest local TODO.
   Plan/top todo/route changes need todo/Next Action writeback or no-writeback rationale.
3. Run the no-progress self-repair check before choosing delivery work. Obey
   any machine-readable `autonomous_replan_obligation` or
   `execution_obligation.must_attempt_work=true` from `quota should-run`; that
   hard contract overrides a quiet no-op. Count a turn as no-progress only when
   it produced no substantive artifact, adapter/implementation progress,
   gate/user decision, or validation signal. If 2 consecutive eligible
   heartbeats are no-progress loops, run one bounded self-repair/replan segment
   before another quiet no-op. Delete/pause only when that repair path is stuck
   for 2 more eligible turns; no spend for the self-cancel turn.
4. Choose one bounded, verifiable progress segment from that audit. It may be a
   coherent batch across related implementation, test, doc, and state-writeback
   files when the write scope is clear and validation is explicit; it should not
   be forced into a tiny single-file step.
5. Do that segment only. Stay inside `goal_boundary` when present and keep
   public/private boundaries intact. Public-safe repo publication is not an
   operator gate by itself: for routine public project work, commit, push, and
   PR creation may proceed autonomously after validation and a clean
   public/private boundary scan. Stop and surface a user/controller gate only
   for private or company-internal material, credentials, destructive git
   operations, production actions, or repository rules that explicitly require
   review.
6. Run the smallest useful validation.
7. Write back changed files, validation, critic, and next action to the active
   state. If a user/owner todo appears, do not hide it in prose: use
   `{cli_bin} todo add --goal-id {goal_id} --role user --task-class user_gate --blocks-agent <agent-id>`
   or `{cli_bin} todo add --goal-id {goal_id} --role user --task-class user_action`.
   Use `--role agent` for project-agent follow-up work.
   For non-trivial feature slices, complete the current todo only after adding
   a successor todo, or include a compact no-follow-up rationale.
   For the full field contract, see `docs/project-agent-todo-contract.md` in
   the LoopX checkout.
   {EXPLORE_GRAPH_DELIVERY_RULE}
8. After validation and writeback complete, append exactly one spend event
   before any state-only refresh that might close the active delivery lane:

   ```bash
   {quota_spend_command}
   ```

   Do not append spend for quiet `should_run=false` skips, preflight failures,
   pure dry-run previews, or duplicate accounting attempts. If
   `should_run=false` but `safe_bypass_allowed=true` and you actually completed
   a bounded safe-bypass step, append this same spend event once after
   validation/writeback.

9. If the dashboard or controller needs state after spend, refresh:

   ```bash
   {refresh_state_command}
   ```

   For a validated progress artifact, add a public-safe classification and
   explicit delivery hints so readiness does not infer from classification
   names:

   ```bash
   {progress_refresh_state_command}
   ```

10. Return compactly. `NOTIFY` only for an artifact, gate, blocker, or self-stop;
    otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_brief_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    refresh_state_command: str,
    progress_refresh_state_command: str,
    material_queue_rule: str,
    permission_rule: str,
    cli_bin: str,
    agent_scope_instruction: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    scope_block = f"\n{agent_scope_instruction}\n" if agent_scope_instruction else ""
    return f"""Advance `{goal_id}` using `{active_state}`.

Brief installed LoopX heartbeat. Thin dispatcher; detail:
`{compact_prompt_command}`.
{scope_block}

Preflight and quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

Preflight fail: quiet.

User NOTIFY: Chinese actions incl. non_blocking at false/0; never only "owner
gate"; required missing -> "具体 user todo 未投影，需修复 LoopX 状态投影".
Only DONT_NOTIFY+false/0: quiet.

If `should_run=false`: no work/spend except `safe_bypass_allowed=true`;
external/wait monitor -> one read-only status/log/metric/marker poll; new
evidence -> writeback/spend. Otherwise obey user channel.
{SCHEDULER_HINT_THIN_RULE}
`lark_event_inbox`: reply_due: drain_command -> effect/reply/readback/ACK.

If `should_run=true`: fetch compact; read needed state priority slice + guard
payload. Use `status --limit 3`; `review-packet --handoff-only`.
Blocker-push first; obey
`execution_obligation`, `effective_action`, `recovery_delivery_allowed`,
`heartbeat_recommendation`, `safe_bypass_kind=outcome_floor_recovery`,
`goal_boundary`, `delivery_batch_scale`, `delivery_outcome`, outcome streaks,
`handoff_delivery_contract`; do 1 bounded segment/batch when
`execution_obligation.must_attempt_work=true`; if recovery, run
ranker/cross-domain evidence recovery or blocker writeback;
validate/writeback/todos; successor todo or no-follow-up rationale for
non-trivial feature slices; spend once; refresh with explicit delivery
scale/outcome for progress artifacts. Stop on private, credentials, destructive
git, prod, or review rules.
{EXPLORE_GRAPH_DELIVERY_RULE}

Spend exactly once only after completed delivery or safe-bypass work:
`{quota_spend_command}`

No spend for quiet skips, preflight failures, blocker-push asks, dry-runs, or
duplicate accounting. Compact return; `NOTIFY` only for artifact/gate/blocker/self-stop.

{material_queue_rule}
{permission_rule}"""


def render_compact_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    refresh_state_command: str,
    progress_refresh_state_command: str,
    material_queue_rule: str,
    permission_rule: str,
    cli_bin: str,
    agent_scope_instruction: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    scope_block = f"\n{agent_scope_instruction}\n" if agent_scope_instruction else ""
    return f"""Advance `{goal_id}` using `{active_state}`.

This compact LoopX heartbeat body stays generic; local policy:
registry/state/adapter/`goal_boundary`.
Expanded lifecycle contract: `{expanded_prompt_command}`.
{scope_block}

Preflight/guard:

```bash
{cli_preflight}
{quota_guard_command}
```

Preflight fail: quiet; no work/spend.

{SCHEDULER_HINT_COMPACT_RULE}

`lark_event_inbox`: reply_due: drain_command -> effect/reply/readback/ACK.

If `should_run=false`: `monitor_quiet_skip` -> one no-spend
`quota monitor-poll --execute`, rerun guard; quiet unless
`autonomous_replan_required` / `must_attempt_work=true`; no edits/spend;
unchanged monitor-only polls are not self-stop signals.
`state=operator_gate` / `notify_user_on_open_todo=true` /
`user_channel.notify=NOTIFY`: blocker-push including
non_blocking; `open_todo_notification_policy=repeat_until_resolved`: repeat;
cooldown:quiet;
never only "owner gate"; no delivery/spend. `safe_bypass_allowed=true`: one
gate-independent safe-bypass, validate/writeback/spend. External/wait monitor:
one read-only status/log/metric/marker poll; unchanged quiet, new evidence
writeback/spend. Otherwise quiet `DONT_NOTIFY`.

If `should_run=true`:
1. Read active state, Priority Stack, progress/critic, `goal_boundary`,
   `attention_queue.items` / `project_asset`, and guard `user_todo_summary`.
   Legacy/raw fallback is not owner/gate/stop authority. Treat
   `run_history.latest_runs` as drill-down only.
2. Stop only for this goal's own blocker todo: Chinese `NOTIFY`, no work/spend.
   Dependency/sibling todos: surface; continue audit.
3. If `effective_action=outcome_floor_recovery` or
   `recovery_delivery_allowed=true` or
   `safe_bypass_kind=outcome_floor_recovery`, run only ranker/cross-domain
   evidence artifact or blocker recovery; no ordinary delivery or
   surface/synthetic-only work.
4. Follow `execution_obligation`: `notify` is not an execution gate.
   `must_attempt_work=true` means one bounded segment even with
   `notify=DONT_NOTIFY`; quiet no-op needs `must_attempt_work=false` and no
   `notify_user_on_open_todo=true` blocker-push notification.
   Then follow `heartbeat_recommendation`:
   `run_first_read_only_map` means run exact real-map command, then
   validate/save/spend/refresh/`NOTIFY`; `mapped_noop_if_unchanged` plus
   `stop_if_unchanged=true` means quiet no-op if no new instruction/evidence/
   todo/stale source/safe handoff.
   `task_orchestration_contract`: activate/resume eligible peer lanes; the
   task-scoped coordinator reviews accepted evidence and writes this bundle.
   Check `delivery_batch_scale`, `delivery_outcome`,
   `post_handoff_outcome_gap_streak`, `handoff_delivery_contract`; obey
   repeated-small/surface-loop contracts.
5. Run steering audit: compare P0/P1/P2, continuation checks,
   compute/focus quota, bottleneck lens.
6. no-progress self-repair: obey `autonomous_replan_obligation` or
   `execution_obligation.must_attempt_work=true`; after 2 eligible stall
   heartbeats with only status/brief checks, replan before quiet no-op.
   Pause/delete only if repair stays stuck 2 more turns.
7. Choose one bounded segment; coherent batch is OK with clear validation.
   Public-safe commit/push/PR may proceed after validation/clean scan. Stop for
   private/company material, credentials, destructive git, production, or review rules.
8. Validate; write files/validation/critic/next action to active state;
   use `{cli_bin} todo add --goal-id {goal_id} --role user --task-class user_gate|user_action`
   for owner todos and `--role agent` for agent todos, not prose. Nontrivial done ->
   successor todo or no-follow-up rationale.
   {EXPLORE_GRAPH_DELIVERY_RULE}
9. After delivery/safe-bypass, spend once before refresh:

```bash
{quota_spend_command}
```

10. Refresh after spend if needed; progress: `{progress_refresh_state_command}`.

No spend for quiet skips, preflight failures, blocker-push asks, dry-runs,
self-cancel turns, or duplicate accounting.

Return compactly. Use heartbeat `NOTIFY` only for committed artifact, user gate,
real blocker, or self-stop; otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_thin_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    refresh_state_command: str,
    progress_refresh_state_command: str,
    material_queue_rule: str,
    permission_rule: str,
    cli_bin: str,
    agent_scope_instruction: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    permission_tail = "" if permission_rule == DEFAULT_PERMISSION_RULE else f" {permission_rule}"
    material_sentence = (
        "Do not consume learning queue unless asked."
        if material_queue_rule == DEFAULT_MATERIAL_QUEUE_RULE
        else material_queue_rule
    )
    scope_sentence = f"\n{agent_scope_instruction}" if agent_scope_instruction else ""
    quota_guard_instruction = (
        f"`{quota_guard_command}`"
        if any(
            marker in quota_guard_command
            for marker in (
                "--available-capability",
                "--runtime-profile",
                "--codex-app",
                "--host-surface",
                " -H ",
            )
        )
        else "`quota should-run`"
    )
    return f"""Advance `{goal_id}` from {active_state}.

Skills: `loopx-project`; surprise/tiny/conflict -> `loopx-self-repair`.
LoopX CLI = truth.
{scope_sentence}

Inspect registry/state/status/history/repo; run
{quota_guard_instruction}; follow `interaction_contract`.
User NOTIFY: concrete Chinese actions even non_blocking false/0; never only
"owner gate"; required missing -> "具体 user todo 未投影，需修复 LoopX 状态投影".
Quiet only if DONT_NOTIFY+false/0.
{RUNTIME_CAPABILITY_PROJECTION_THIN_RULE}
{SCHEDULER_HINT_THIN_RULE}
Batch/no-op; spend post-writeback.
Plans/done->todo/rationale; 2 stalls->self-repair.
`lark_event_inbox`: reply_due; drain_command/reply-readback/ACK.
{EXPLORE_GRAPH_DELIVERY_THIN_RULE}

P0 blocked: safe P1/P2; monitor-only quiet/no-spend.

No project branches; {material_sentence} Stop for private material,
credentials, destructive git, or unauthorized production actions{permission_tail}"""


def render_heartbeat_generator_inputs_markdown(payload: dict[str, Any]) -> str:
    interface_budget = payload.get("interface_budget") if isinstance(payload.get("interface_budget"), dict) else {}
    lines = [
        "## Generator Inputs",
        "",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- active_state: `{payload.get('active_state')}`",
        f"- active_state_source: `{payload.get('active_state_source')}`",
        f"- resolved_active_state: `{payload.get('resolved_active_state')}`",
        f"- compact: `{payload.get('compact')}`",
        f"- brief: `{payload.get('brief')}`",
        f"- thin: `{payload.get('thin')}`",
        f"- cli_bin: `{payload.get('cli_bin')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- agent_model: `{payload.get('agent_model')}`",
        f"- agent_role: `{payload.get('agent_role')}`",
    ]
    lines.extend(
        [
            f"- agent_scopes: `{payload.get('agent_scopes')}`",
            f"- expanded_prompt_command: `{payload.get('expanded_prompt_command')}`",
            f"- compact_prompt_command: `{payload.get('compact_prompt_command')}`",
            f"- brief_prompt_command: `{payload.get('brief_prompt_command')}`",
            f"- thin_prompt_command: `{payload.get('thin_prompt_command')}`",
            f"- quota_guard_command: `{payload.get('quota_guard_command')}`",
            f"- quota_spend_command: `{payload.get('quota_spend_command')}`",
            f"- cli_preflight: `{payload.get('cli_preflight')}`",
            "- interface_budget: "
            f"mode=`{interface_budget.get('mode')}` "
            f"budget_chars=`{interface_budget.get('budget_char_count')}` "
            f"max_chars=`{interface_budget.get('max_chars')}` "
            f"within_budget=`{interface_budget.get('within_budget')}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_heartbeat_prompt_error_markdown(payload: dict[str, Any]) -> str:
    return f"""# Heartbeat Automation Prompt Error

No heartbeat task body was generated.

## Error

```text
{payload.get("error") or "unknown heartbeat-prompt generation error"}
```

{render_heartbeat_generator_inputs_markdown(payload)}"""


def render_heartbeat_prompt_markdown(payload: dict[str, Any]) -> str:
    if payload.get("ok") is False:
        return render_heartbeat_prompt_error_markdown(payload)
    if payload.get("thin"):
        style = "thin "
    elif payload.get("brief"):
        style = "brief "
    elif payload.get("compact"):
        style = "compact "
    else:
        style = ""
    return f"""# Heartbeat Automation Prompt

Copy this {style}task body into a Codex App heartbeat automation.

````text
{payload.get("task_body", "")}
````

{render_heartbeat_generator_inputs_markdown(payload)}"""
