from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_registry import registered_agent_ids_from_registry
from .bootstrap import default_goal_id
from .host_loop_activation import agent_type_for_host_surface, build_host_loop_activation_packet
from .project_alias import resolve_canonical_project_alias
from .project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    render_available_capability_args,
    render_quota_guard_command,
    shell_arg,
)
from .registry import registry_goals, resolve_state_file
from .slash_commands import build_slash_command_catalog


SCHEMA_VERSION = "loopx_bootstrap_command_pack_v0"
CANONICAL_SLASH_COMMAND = "/loopx"
GOAL_START_SCHEMA_VERSION = "loopx_goal_start_command_v0"
GUIDED_START_SCHEMA_VERSION = "loopx_start_goal_guided_v0"
PACKET_SUMMARY_SCHEMA_VERSION = "loopx_start_goal_packet_summary_v0"
PACKET_MEASUREMENT_SCHEMA_VERSION = "loopx_packet_duplication_measurement_v0"
GUIDED_COMMAND_PACK_PROJECTION_SCHEMA_VERSION = (
    "loopx_guided_command_pack_projection_v0"
)
HOST_SURFACE_SELECTION_SCHEMA_VERSION = "loopx_host_surface_selection_gate_v0"
START_GOAL_HOST_SURFACES = (
    "codex-app",
    "codex-ide",
    "codex-cli-tui",
    "claude-code",
    "shell",
)


def _iter_string_leaves(
    value: Any, path: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], str]]:
    leaves: list[tuple[tuple[str, ...], str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "packet_summary":
                continue
            leaves.extend(_iter_string_leaves(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(_iter_string_leaves(child, (*path, str(index))))
    elif isinstance(value, str):
        leaves.append((path, value))
    return leaves


def _without_packet_summary(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_packet_summary(child)
            for key, child in value.items()
            if key != "packet_summary"
        }
    if isinstance(value, list):
        return [_without_packet_summary(child) for child in value]
    return value


def _is_command_value(path: tuple[str, ...]) -> bool:
    if not path:
        return False
    leaf = path[-1]
    return (
        (len(path) >= 2 and path[-2] == "commands")
        or leaf in {"command", "command_template", "prompt", "canonical_cli_command"}
        or leaf.endswith("_command")
        or leaf.endswith("_prompt")
        or leaf.endswith("_command_if_needed")
    )


def _measure_packet_duplication(
    payload: dict[str, Any], *, objective: str | None
) -> dict[str, Any]:
    compatibility_payload = _without_packet_summary(payload)
    leaves = _iter_string_leaves(compatibility_payload)
    objective_occurrences = 0
    objective_field_count = 0
    if objective:
        for _, value in leaves:
            count = value.count(objective)
            if count:
                objective_occurrences += count
                objective_field_count += 1

    command_values: list[str] = []
    for path, value in leaves:
        if not value or not _is_command_value(path):
            continue
        command_values.append(value)
    unique_command_count = len(set(command_values))

    compatibility_json = json.dumps(
        compatibility_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "schema_version": PACKET_MEASUREMENT_SCHEMA_VERSION,
        "measurement_scope": "compatibility_projection_without_packet_summary",
        "serialized_bytes": len(compatibility_json.encode("utf-8")),
        "objective_content": {
            "substring_occurrences": objective_occurrences,
            "containing_field_count": objective_field_count,
            "duplicate_occurrences": max(0, objective_occurrences - 1),
        },
        "command_content": {
            "candidate_occurrences": len(command_values),
            "unique_values": unique_command_count,
            "duplicate_occurrences": len(command_values) - unique_command_count,
        },
    }


def _build_packet_summary(
    payload: dict[str, Any],
    *,
    packet_kind: str,
    detail_refs: dict[str, str],
    legacy_fields_retained: bool = True,
    compact_projection_default: bool = False,
) -> dict[str, Any]:
    next_step = payload.get("recommended_next_step")
    next_step = next_step if isinstance(next_step, dict) else {}
    return {
        "schema_version": PACKET_SUMMARY_SCHEMA_VERSION,
        "packet_kind": packet_kind,
        "goal_id": payload.get("goal_id"),
        "objective": payload.get("goal_text"),
        "next_step_kind": next_step.get("kind"),
        "detail_refs": {
            name: {
                "schema_version": "loopx_packet_json_pointer_ref_v0",
                "json_pointer": pointer,
            }
            for name, pointer in detail_refs.items()
        },
        "compatibility": {
            "legacy_fields_retained": legacy_fields_retained,
            "compact_projection_default": compact_projection_default,
            "removal_gate": "explicit_host_shadow_parity",
        },
        "duplication_measurement": _measure_packet_duplication(
            payload,
            objective=str(payload.get("goal_text"))
            if payload.get("goal_text")
            else None,
        ),
    }


def _start_goal_detail_command(
    *,
    project: str,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
    goal_text: str,
    available_capabilities: list[str] | None,
) -> str:
    return (
        f"{shell_arg(cli_bin)} --format json start-goal --guided "
        f"--project {shell_arg(project)}"
        + (f" --goal-id {shell_arg(goal_id)}" if goal_id else "")
        + (f" --agent-id {shell_arg(agent_id)}" if agent_id else "")
        + f" --host-surface {shell_arg(host_surface)}"
        + render_available_capability_args(available_capabilities)
        + f" --goal-text {shell_arg(goal_text)}"
        + " --include-command-pack-detail"
    )


def _guided_command_pack_projection(
    command_pack: dict[str, Any],
    *,
    detail_command: str,
) -> dict[str, Any]:
    """Keep the guided hot path actionable without nesting the full host packet."""

    projection: dict[str, Any] = {
        "ok": command_pack.get("ok"),
        "schema_version": command_pack.get("schema_version"),
        "projection_schema_version": GUIDED_COMMAND_PACK_PROJECTION_SCHEMA_VERSION,
        "projection_mode": "guided_start_compatibility",
        "read_only": command_pack.get("read_only"),
        "project": command_pack.get("project"),
        "goal_id": command_pack.get("goal_id"),
        "agent_id": command_pack.get("agent_id"),
        "host_surface": command_pack.get("host_surface"),
        "goal_text": command_pack.get("goal_text"),
        "goal_start_contract": command_pack.get("goal_start_contract"),
        "commands": command_pack.get("commands"),
        "host_loop_activation": command_pack.get("host_loop_activation"),
        "safety_contract": command_pack.get("safety_contract"),
        "detail_command": detail_command,
    }
    projection["packet_summary"] = _build_packet_summary(
        projection,
        packet_kind="bootstrap_command_pack_projection",
        detail_refs={
            "goal_start_contract": "#/goal_start_contract",
            "commands": "#/commands",
            "host_loop_activation": "#/host_loop_activation",
            "safety_contract": "#/safety_contract",
            "full_command_pack": "#/detail_command",
        },
        legacy_fields_retained=False,
        compact_projection_default=True,
    )
    return projection


def build_start_goal_host_surface_selection_packet(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    goal_text: str,
    available_capabilities: list[str] | None = None,
    include_command_pack_detail: bool = False,
) -> dict[str, Any]:
    """Fail closed when the caller has not identified the current Codex host."""

    resolved_project = str(_resolve_project(project))
    normalized_goal_text = " ".join(goal_text.split())
    host_descriptions = {
        "codex-app": "Codex desktop app with heartbeat automation support",
        "codex-ide": "Codex IDE extension; activate its visible goal mode",
        "codex-cli-tui": "terminal Codex TUI with visible /goal support",
        "claude-code": "Claude Code with native /loop",
        "shell": "manual shell or an explicitly configured external scheduler",
    }
    choices: list[dict[str, Any]] = []
    for host_surface in START_GOAL_HOST_SURFACES:
        rerun_command = (
            f"{shell_arg(cli_bin)} start-goal --guided "
            f"--project {shell_arg(resolved_project)}"
            + (f" --goal-id {shell_arg(goal_id)}" if goal_id else "")
            + (f" --agent-id {shell_arg(agent_id)}" if agent_id else "")
            + f" --host-surface {shell_arg(host_surface)}"
            + render_available_capability_args(available_capabilities)
            + f" --goal-text {shell_arg(normalized_goal_text)}"
            + (" --include-command-pack-detail" if include_command_pack_detail else "")
        )
        choices.append(
            {
                "host_surface": host_surface,
                "description": host_descriptions[host_surface],
                "rerun_command": rerun_command,
            }
        )
    reason = (
        "host surface is required because Codex App, Codex IDE, and Codex CLI "
        "have different continuation contracts"
    )
    gate = {
        "schema_version": HOST_SURFACE_SELECTION_SCHEMA_VERSION,
        "state": "selection_required",
        "action_required": True,
        "reason": reason,
        "required_cli_arg": "--host-surface <exact-host-surface>",
        "choices": choices,
    }
    transaction = {
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "mode": "dry_run_preview",
        "writes_now": False,
        "spends_quota_now": False,
        "goal_text": normalized_goal_text,
        "blocked_by": "host_surface_selection",
        "host_surface_selection_gate": gate,
        "ordered_steps": [
            {
                "id": "select_host_surface",
                "kind": "host_surface_selection_gate",
                "choices": choices,
                "purpose": "select the current host before planning, mutation, or loop activation",
            }
        ],
        "idempotency_policy": {"safe_to_rerun_preview": True},
        "preserve_todos_policy": {
            "force_bootstrap_default": "forbidden_in_guided_flow",
            "before_destructive_reconnect": "select a host before any mutation",
            "preferred_scope_change": "select a host before any mutation",
        },
    }
    payload: dict[str, Any] = {
        "ok": True,
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "read_only": True,
        "guided": True,
        "project": resolved_project,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "host_surface": None,
        "goal_text": normalized_goal_text,
        "host_surface_selection_gate": gate,
        "recommended_next_step": {
            "kind": "select_host_surface",
            "requires_user_confirmation": False,
            "requires_host_surface_selection": True,
            "summary": reason,
        },
        "guided_transaction": transaction,
        "command_pack_detail_included": include_command_pack_detail,
        "safety_contract": {
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_commands_are_previewed": False,
            "force_bootstrap_allowed": False,
        },
    }
    payload["message"] = render_start_goal_guided_markdown(payload)
    payload["packet_summary"] = _build_packet_summary(
        payload,
        packet_kind="guided_start_host_surface_selection",
        detail_refs={
            "host_surface_selection_gate": "#/host_surface_selection_gate",
            "guided_transaction": "#/guided_transaction",
            "safety_contract": "#/safety_contract",
            "compatibility_message": "#/message",
        },
    )
    return payload


def _resolve_project(project: Path) -> Path:
    project = project.expanduser()
    try:
        return project.resolve()
    except OSError:
        return project.absolute()


def _read_registry(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return None, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "registry root must be a JSON object"
    return payload, None


def _select_goal(goals: list[dict[str, Any]], goal_id: str | None) -> tuple[str, dict[str, Any] | None]:
    if goal_id:
        for goal in goals:
            if goal.get("id") == goal_id:
                return goal_id, goal
        return goal_id, None
    if goals:
        first_goal_id = str(goals[0].get("id"))
        return first_goal_id, goals[0]
    return "", None


def inspect_bootstrap_connection(project: Path, *, goal_id: str | None = None) -> dict[str, Any]:
    input_project = _resolve_project(project)
    alias = resolve_canonical_project_alias(input_project, goal_id=goal_id)
    resolved_project = (
        _resolve_project(Path(str(alias.get("canonical_project"))))
        if alias.get("applied") and alias.get("canonical_project")
        else input_project
    )
    registry_path = resolved_project / ".loopx" / "registry.json"
    registry_exists = registry_path.exists()
    registry, registry_error = _read_registry(registry_path) if registry_exists else (None, None)
    inferred_goal_id = goal_id or default_goal_id(resolved_project)
    state_file = resolved_project / ".codex" / "goals" / inferred_goal_id / "ACTIVE_GOAL_STATE.md"
    base_connection = {
        "input_project": str(input_project),
        "project": str(resolved_project),
        "canonical_project_alias": alias,
        "registry": str(registry_path),
    }

    if registry_error:
        return {
            **base_connection,
            "registry_exists": registry_exists,
            "goal_id": inferred_goal_id,
            "goal_found": False,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_invalid",
            "mutation_confirmation_required": True,
            "reason": registry_error,
        }

    if not registry:
        return {
            **base_connection,
            "registry_exists": False,
            "goal_id": inferred_goal_id,
            "goal_found": False,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "not_connected",
            "mutation_confirmation_required": True,
            "reason": "project-local .loopx/registry.json is missing",
        }

    goals = registry_goals(registry)
    selected_goal_id, selected_goal = _select_goal(goals, goal_id)
    resolved_goal_id = selected_goal_id or inferred_goal_id
    fallback_state_file = resolved_project / ".codex" / "goals" / resolved_goal_id / "ACTIVE_GOAL_STATE.md"
    goal_state_file = (
        resolve_state_file(resolved_project, str(selected_goal.get("state_file")))
        if selected_goal and selected_goal.get("state_file")
        else None
    )
    state_file = goal_state_file or fallback_state_file

    if selected_goal is None:
        return {
            **base_connection,
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": False,
            "known_goal_ids": [str(goal.get("id")) for goal in goals],
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_without_goal",
            "mutation_confirmation_required": True,
            "reason": "registry exists but no matching goal entry was found",
        }

    if not selected_goal.get("state_file"):
        return {
            **base_connection,
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": True,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_goal_missing_state_file",
            "mutation_confirmation_required": True,
            "reason": "goal entry does not declare state_file",
        }

    if not state_file.exists():
        return {
            **base_connection,
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": True,
            "state_file": str(state_file),
            "state_file_exists": False,
            "connection_state": "state_file_missing",
            "mutation_confirmation_required": True,
            "reason": "registry goal points at a state_file that is missing",
        }

    return {
        **base_connection,
        "registry_exists": True,
        "goal_id": resolved_goal_id,
        "goal_found": True,
        "state_file": str(state_file),
        "state_file_exists": True,
        "connection_state": "connected",
        "mutation_confirmation_required": False,
        "reason": "registry goal and active state_file are present",
    }


def _bootstrap_command(
    *,
    project: str,
    goal_id: str,
    cli_bin: str,
    dry_run: bool,
) -> str:
    lines = [
        f"cd {shell_arg(project)}",
        f"{shell_arg(cli_bin)} bootstrap \\",
        "  --project . \\",
        f"  --goal-id {shell_arg(goal_id)} \\",
        f"  --adapter-kind {shell_arg(DEFAULT_HANDOFF_ADAPTER_KIND)} \\",
        f"  --adapter-status {shell_arg(DEFAULT_HANDOFF_ADAPTER_STATUS)} \\",
        "  --codex-app-heartbeat ask",
    ]
    if dry_run:
        lines[-1] += " \\"
        lines.append("  --dry-run")
    return "\n".join(lines)


def _project_command(project: str, command: str) -> str:
    return "\n".join([f"cd {shell_arg(project)}", command])


def _goal_start_bootstrap_command(
    *,
    project: str,
    goal_id: str,
    goal_text: str | None,
    cli_bin: str,
) -> str:
    objective = goal_text or "<exact /loopx goal text>"
    lines = [
        f"cd {shell_arg(project)}",
        f"{shell_arg(cli_bin)} bootstrap \\",
        "  --project . \\",
        f"  --goal-id {shell_arg(goal_id)} \\",
        f"  --objective {shell_arg(objective)} \\",
        f"  --adapter-kind {shell_arg(DEFAULT_HANDOFF_ADAPTER_KIND)} \\",
        f"  --adapter-status {shell_arg(DEFAULT_HANDOFF_ADAPTER_STATUS)} \\",
        "  --no-onboarding-scan \\",
        "  --codex-app-heartbeat ask",
    ]
    return "\n".join(lines)


def _goal_start_contract(*, goal_text: str | None, connected: bool, agent_type: str) -> dict[str, Any]:
    return {
        "schema_version": GOAL_START_SCHEMA_VERSION,
        "slash_syntax": "/loopx <goal text>",
        "goal_text": goal_text,
        "explicit_invocation_confirms_project_local_state_writes": True,
        "connect_if_needed": True,
        "bootstrap_policy": "create project-local LoopX state only when no matching registry goal exists",
        "planner": {
            "required_before_todo_write": True,
            "default_profile": "open_ended_product_direction",
            "profile_selection": (
                "Use open_ended_product_direction when the user's goal is a broad, "
                "fuzzy product direction or new initiative. Use clear_bounded_problem "
                "when the target is a concrete task with a clear success condition. "
                "In both cases, let the model produce a real ordered plan before writes."
            ),
            "profiles": {
                "open_ended_product_direction": {
                    "suggested_items_min": 2,
                    "suggested_items_max": 5,
                    "intent": (
                        "turn an ambiguous product direction into public-safe, ranked "
                        "todo options before execution"
                    ),
                },
                "clear_bounded_problem": {
                    "item_count_policy": "planner_sized",
                    "may_reuse_current_todo_when_it_already_represents_the_plan": True,
                    "intent": (
                        "make the approach explicit with enough concise ordered todos, "
                        "without arbitrary caps or management-only filler"
                    ),
                },
            },
            "allowed_priorities": ["P0", "P1", "P2"],
            "default_role": "agent",
            "default_task_class": "advancement_task",
            "required_fields": ["priority", "text", "task_class", "action_kind"],
            "public_safe_only": True,
            "budget_policy": (
                "For clear bounded problems, planning should sharpen action selection "
                "rather than crowd out task work; prefer the minimum sufficient ordered "
                "todo plan over fixed-count filler."
            ),
        },
        "priority_ordering": {
            "bucket_order": ["P0", "P1", "P2"],
            "same_priority_tie_breaker": "planner_order_then_todo_write_order",
            "prompt_constraint": (
                "Sort planned todos by priority bucket and relative rank before writing. "
                "For multiple P0/P1/P2 items, earlier items are higher rank; preserve that "
                "exact order when running todo add commands."
            ),
            "storage_contract": (
                "LoopX status/quota already use todo index as the same-priority tie-breaker, "
                "so host integrations must write todos in planner order instead of adding "
                "a separate rank field."
            ),
        },
        "activation": {
            "after_write": ["refresh-state", "host_loop_activation", "quota should-run"],
            "host_loop_required_after_todo_writeback": True,
            "agent_type": agent_type,
            "agent_type_discovery": "loopx agent-onboard --list-agent-types",
            "host_surfaces": {
                "codex-app": "Codex App heartbeat automation",
                "codex-cli": "visible Codex CLI `/goal <task_body>`",
                "claude-code": "Claude Code native `/loop` after `/loopx <task>` arms LoopX",
                "manual": "external scheduler or manual quota/status loop",
                "other-agent": "custom host loop driver using the returned task body and quota guard",
            },
            "missing_host_loop_policy": (
                "Do not claim autonomous setup complete from registry/quota identity alone. "
                "If the host cannot mutate its loop surface, report the exact pasteable gate."
            ),
            "low_cost_recheck_policy": (
                "Only recompute onboarding/activation when activation is missing, unknown, stale, "
                "or the agent type changed; normal ticks should read quota/status/state directly."
            ),
            "begin_automation_when_quota_allows": True,
            "spend_quota_after_writeback": True,
        },
        "domain_route_hints": {
            "issue_fix_workflow": {
                "when": "goal text contains a public GitHub issue/PR URL or asks for an issue-fix workflow",
                "preview_command": (
                    "loopx issue-fix workflow-plan --url <github-issue-or-pr-url> "
                    "--repo-path <approved-repo> --repository-context-json "
                    "<compact-context.json> --validation-label '<validation command>' --format json"
                ),
                "decision_command": (
                    "loopx issue-fix feasibility --url <github-issue-url> "
                    "--reproduction-status <state> --scope-class <scope> "
                    "--repository-context-json <compact-context.json> "
                    "--goal-id <goal-id> --format json"
                ),
                "post_pr_reviewer_request_command": (
                    "loopx issue-fix reviewer-request --url <github-pr-url> "
                    "--repo-path <approved-repo> --base-ref <base-ref> "
                    "--execute --format json"
                ),
                "post_pr_monitor_command": (
                    "loopx issue-fix pr-lifecycle --url <github-pr-url> "
                    "--goal-id <goal-id> --format json"
                ),
                "writeback": (
                    "write metadata classification plus the feasibility checkpoint first, then "
                    "write only its selected route successor or no-follow-up; "
                    "private repro material, issue body/comment reads, external comments, PR creation, "
                    "merge, publish, destructive git, and production actions stay explicit gates; "
                    "after PR creation, use active external-review-request authority to call "
                    "reviewer-request, verify the formal request or its permission-only reviewer "
                    "comment fallback, then use one monitor per PR state bucket, never per PR; "
                    "actions/messages stay one-shot; domain-state stays compact"
                ),
            }
        },
        "connected_at_preview_time": connected,
        "stop_conditions": [
            "private material requested before a public-safe todo can be written",
            "credentials or secrets are required",
            "destructive git or production operation would be needed",
            "the host cannot execute shell/CLI/tool calls or persist LoopX state",
            "the host cannot activate or expose the required host loop and no concrete pasteable gate can be shown",
        ],
    }


def _goal_start_prompt(*, goal_text: str | None, goal_id: str, agent_id: str | None) -> str:
    goal_clause = (
        f"Goal text: {goal_text}"
        if goal_text
        else "Goal text: use the text after `/loopx`; if it is empty, handle bare `/loopx` instead."
    )
    agent_clause = f" Use agent id `{agent_id}` for quota/claim commands." if agent_id else ""
    return f"""Plan before writing todos for `/loopx <goal text>`.

{goal_clause}
Goal id: {goal_id}.{agent_clause}

Planning rules:
1. Choose the planning profile: broad or fuzzy product direction uses 2-5 public-safe todos; clear bounded problems use a planner-sized ordered todo plan with enough steps to make the approach explicit.
2. Plan before any `loopx todo add`; keep each item concise and avoid management-only filler.
3. Every new todo starts with `[P0]`, `[P1]`, or `[P2]`; include at least one `[P0]` unless the first useful step is blocked by a user gate.
4. If several todos share the same priority, their listed order is their relative priority. Preserve that exact order when writing them.
5. Prefer executable Agent Todo items with `task_class=advancement_task`; use User Todo only for concrete owner decisions or private-material gates.
6. After writing todos, run `loopx refresh-state --goal-id {goal_id}`, activate the host loop if it is missing, unknown, or stale (Codex App automation, Codex CLI `/goal <task_body>`, Claude Code `/loop`, or a custom host-loop gate), then run `loopx quota should-run --goal-id {goal_id}` and begin the first allowed bounded segment.
7. If the goal is a GitHub issue/PR fix, first preview `loopx issue-fix workflow-plan --url <github-issue-or-pr-url> --repo-path <approved-repo> --repository-context-json <compact-context.json> --validation-label '<validation command>' --format json`; write only metadata classification plus the feasibility checkpoint. Repository context should pin current repo policy, architecture, change-scope, reproduction, and validation refs; memory and external experts remain advisory until verified against the pinned revision. After a compact public-safe observation, run `loopx issue-fix feasibility --url <github-issue-url> --reproduction-status <state> --scope-class <scope> --repository-context-json <compact-context.json> --goal-id {goal_id} --format json` and write only its selected route successor or no-follow-up. Keep private repro material, body/comment reads, arbitrary external comments, PR creation, merge, publish, destructive git, and production actions as explicit gates. After a PR exists and `external_review_request` or `publish` authority is active, call `loopx issue-fix reviewer-request --url <github-pr-url> --repo-path <approved-repo> --base-ref <base-ref> --execute --format json`; it should try the formal request first and, only on confirmed permission denial, post one reviewer-tagging fallback comment. Do not mark notification complete until the request or fallback comment is visible on the PR. Then call `loopx issue-fix pr-lifecycle --url <github-pr-url> --goal-id {goal_id} --format json`; use `grouped_monitor_projection` for one monitor per nonempty state bucket. Never create one monitor per PR. Keep PR actions one-shot and messages at one PR per message.
"""


def build_loopx_bootstrap_command_pack(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
    goal_text: str | None = None,
    available_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    inspection = inspect_bootstrap_connection(project, goal_id=goal_id)
    resolved_project = str(inspection["project"])
    resolved_goal_id = str(inspection["goal_id"])
    connected = inspection.get("connection_state") == "connected"
    mutation_confirmation_required = bool(inspection.get("mutation_confirmation_required"))
    normalized_goal_text = " ".join(goal_text.split()) if goal_text else None
    explicit_goal_start = bool(normalized_goal_text)
    agent_type = agent_type_for_host_surface(host_surface)
    registry_path = Path(str(inspection["registry"]))
    registered_agents = registered_agent_ids_from_registry(
        registry_path,
        resolved_goal_id,
    )

    bootstrap_preview_command = _bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        dry_run=True,
    )
    bootstrap_after_confirmation_command = _bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        dry_run=False,
    )
    host_loop_activation = build_host_loop_activation_packet(
        agent_type=agent_type,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
        registered_agents=registered_agents,
        available_capabilities=available_capabilities,
    )
    selected_agent_id = host_loop_activation.get("agent_id")
    activation_allowed = bool(host_loop_activation.get("activation_allowed"))
    activation_commands = host_loop_activation.get("commands")
    activation_commands = activation_commands if isinstance(activation_commands, dict) else {}
    heartbeat_prompt_command = activation_commands.get("heartbeat_prompt")
    heartbeat_prompt_json_command = activation_commands.get("heartbeat_prompt_json")
    quota_guard_command = (
        render_quota_guard_command(
            resolved_goal_id,
            cli_bin=cli_bin,
            agent_id=str(selected_agent_id) if selected_agent_id else None,
            available_capabilities=available_capabilities,
        )
        if activation_allowed
        else None
    )
    status_command = _project_command(resolved_project, f"{shell_arg(cli_bin)} status")
    goal_start_bootstrap_command = _goal_start_bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        goal_text=normalized_goal_text,
        cli_bin=cli_bin,
    )
    goal_start_plan_prompt = _goal_start_prompt(
        goal_text=normalized_goal_text,
        goal_id=resolved_goal_id,
        agent_id=str(selected_agent_id) if selected_agent_id else None,
    )
    slash_command_catalog = build_slash_command_catalog(cli_bin=cli_bin)

    identity_selection_gate = host_loop_activation.get("identity_selection_gate")
    if isinstance(identity_selection_gate, dict):
        recommended_next_step = {
            "kind": "select_agent_identity",
            "requires_user_confirmation": False,
            "requires_agent_selection": True,
            "summary": identity_selection_gate.get("reason"),
            "identity_selection_gate": identity_selection_gate,
        }
    elif explicit_goal_start:
        recommended_next_step = {
            "kind": "goal_plan_write_and_activate",
            "requires_user_confirmation": False,
            "confirmation_source": "/loopx <goal text>",
            "summary": (
                "The slash command includes an explicit goal. Connect the project if needed, plan ranked todos, "
                "write them in exact plan order, refresh state, activate the host loop if missing/stale, "
                "and enter the quota-gated automation flow."
            ),
            "connect_command_if_needed": goal_start_bootstrap_command,
            "plan_prompt": goal_start_plan_prompt,
        }
    else:
        recommended_next_step = {
            "kind": "status_and_loop_activation" if connected else "confirm_before_bootstrap_mutation",
            "requires_user_confirmation": mutation_confirmation_required,
            "summary": (
                "Project is connected; show status, then generate the heartbeat prompt only if the user wants a loop surface."
                if connected
                else "Project is not fully connected; show the dry-run preview and ask before running bootstrap/connect."
            ),
        }
        if mutation_confirmation_required:
            recommended_next_step["dry_run_command"] = bootstrap_preview_command
            recommended_next_step["after_confirmation_command"] = bootstrap_after_confirmation_command

    payload: dict[str, Any] = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "slash_command": CANONICAL_SLASH_COMMAND,
        "slash_forms": [
            {"form": "/loopx", "mode": "inspect_or_connect_preview"},
            {"form": "/loopx <goal text>", "mode": "goal_plan_write_and_activate"},
        ],
        "canonical_cli_command": (
            f"{shell_arg(cli_bin)} bootstrap-command-pack --project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(resolved_goal_id)}"
            + (
                f" --agent-id {shell_arg(str(selected_agent_id))}"
                if selected_agent_id
                else ""
            )
        ),
        "read_only": True,
        "goal_text": normalized_goal_text,
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": selected_agent_id,
        "requested_agent_id": agent_id,
        "agent_type": agent_type,
        "host_surface": host_surface,
        "project_connection": inspection,
        "host_loop_activation": host_loop_activation,
        "available_slash_commands": slash_command_catalog,
        "onboarding_hint": slash_command_catalog["onboarding"],
        "recommended_next_step": recommended_next_step,
        "goal_start_contract": _goal_start_contract(
            goal_text=normalized_goal_text,
            connected=connected,
            agent_type=agent_type,
        ),
        "commands": {
            "doctor": f"{shell_arg(cli_bin)} doctor",
            "status": status_command,
            "quota_guard": quota_guard_command,
            "heartbeat_prompt": heartbeat_prompt_command,
            "heartbeat_prompt_json": heartbeat_prompt_json_command,
            "bootstrap_dry_run_preview": bootstrap_preview_command,
            "bootstrap_after_user_confirmation": bootstrap_after_confirmation_command,
            "goal_start_connect_if_needed": goal_start_bootstrap_command,
            "goal_start_plan_prompt": goal_start_plan_prompt,
            "goal_start_refresh_state": f"{shell_arg(cli_bin)} refresh-state --goal-id {shell_arg(resolved_goal_id)}",
            "goal_start_host_loop_activation": host_loop_activation.get("activation_input_command"),
            "goal_start_agent_onboard_recheck": (
                f"{shell_arg(cli_bin)} agent-onboard "
                f"--agent-type {shell_arg(agent_type)} "
                f"--project {shell_arg(resolved_project)} "
                f"--goal-id {shell_arg(resolved_goal_id)}"
                + (
                    f" --agent-id {shell_arg(str(selected_agent_id))}"
                    if selected_agent_id
                    else ""
                )
                + render_available_capability_args(available_capabilities)
            ),
            "goal_start_quota_should_run": (
                (
                    f"{shell_arg(cli_bin)} quota should-run --goal-id "
                    f"{shell_arg(resolved_goal_id)}"
                    + (
                        f" --agent-id {shell_arg(str(selected_agent_id))}"
                        if selected_agent_id
                        else ""
                    )
                    + render_available_capability_args(available_capabilities)
                )
                if activation_allowed
                else None
            ),
            "identity_selection_choices": (
                identity_selection_gate.get("choices")
                if isinstance(identity_selection_gate, dict)
                else []
            ),
            "issue_fix_workflow_plan_template": (
                f"{shell_arg(cli_bin)} issue-fix workflow-plan "
                "--url <github-issue-or-pr-url> "
                "--repo-path <approved-repo> "
                "--repository-context-json <compact-context.json> "
                "--validation-label '<validation command>' "
                "--format json"
            ),
            "issue_fix_feasibility_template": (
                f"{shell_arg(cli_bin)} issue-fix feasibility "
                "--url <github-issue-url> "
                "--reproduction-status <confirmed|planned|missing|blocked> "
                "--scope-class <bounded|uncertain|oversized> "
                "--repository-context-json <compact-context.json> "
                f"--goal-id {shell_arg(resolved_goal_id)} "
                "--format json"
            ),
            "issue_fix_pr_lifecycle_template": (
                f"{shell_arg(cli_bin)} issue-fix pr-lifecycle "
                "--url <github-pr-url> "
                f"--goal-id {shell_arg(resolved_goal_id)} "
                "--format json"
            ),
            "issue_fix_reviewer_request_template": (
                f"{shell_arg(cli_bin)} issue-fix reviewer-request "
                "--url <github-pr-url> "
                "--repo-path <approved-repo> "
                "--base-ref <base-ref> "
                "--execute --format json"
            ),
        },
        "safety_contract": {
            "runs_bootstrap": False,
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_requires_user_confirmation": mutation_confirmation_required and not explicit_goal_start,
            "bare_command_mutation_requires_user_confirmation": mutation_confirmation_required,
            "explicit_goal_start_may_write_project_local_state": explicit_goal_start,
            "explicit_goal_start_must_activate_host_loop": explicit_goal_start,
            "host_loop_activation_allowed": activation_allowed,
        },
    }
    payload["message"] = render_loopx_bootstrap_command_pack_message(payload)
    payload["packet_summary"] = _build_packet_summary(
        payload,
        packet_kind="bootstrap_command_pack",
        detail_refs={
            "project_connection": "#/project_connection",
            "host_loop_activation": "#/host_loop_activation",
            "recommended_next_step": "#/recommended_next_step",
            "goal_start_contract": "#/goal_start_contract",
            "commands": "#/commands",
            "safety_contract": "#/safety_contract",
            "compatibility_message": "#/message",
        },
    )
    return payload


def _build_multi_goal_start_selection_packet(
    *,
    project: Path,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
    goal_text: str,
    available_capabilities: list[str] | None,
    include_command_pack_detail: bool,
) -> dict[str, Any] | None:
    inspection = inspect_bootstrap_connection(project)
    registry_path = Path(str(inspection.get("registry") or ""))
    registry, registry_error = _read_registry(registry_path)
    if registry_error or not registry:
        return None
    goals = registry_goals(registry)
    if len(goals) <= 1:
        return None

    normalized_goal_text = " ".join(goal_text.split())
    resolved_project = str(inspection["project"])
    choices: list[dict[str, Any]] = []
    for goal in goals:
        candidate_goal_id = str(goal.get("id") or "").strip()
        if not candidate_goal_id:
            continue
        rerun_command = (
            f"{shell_arg(cli_bin)} start-goal --guided "
            f"--project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(candidate_goal_id)}"
            + (f" --agent-id {shell_arg(agent_id)}" if agent_id else "")
            + f" --host-surface {shell_arg(host_surface)}"
            + render_available_capability_args(available_capabilities)
            + f" --goal-text {shell_arg(normalized_goal_text)}"
        )
        choices.append(
            {
                "goal_id": candidate_goal_id,
                "status": goal.get("status"),
                "state_file": goal.get("state_file"),
                "registered_agents": registered_agent_ids_from_registry(
                    registry_path,
                    candidate_goal_id,
                ),
                "rerun_command": rerun_command,
            }
        )

    reason = (
        "multiple registered goals exist for this project; select one explicitly before "
        "planning todos, registering an agent, or activating a host loop"
    )
    goal_selection_gate = {
        "schema_version": "loopx_goal_selection_gate_v0",
        "state": "selection_required",
        "action_required": True,
        "reason": reason,
        "required_cli_arg": "--goal-id <registered-goal-id>",
        "choices": choices,
    }
    connection = {
        **inspection,
        "goal_id": None,
        "goal_found": False,
        "state_file": None,
        "state_file_exists": None,
        "known_goal_ids": [choice["goal_id"] for choice in choices],
        "connection_state": "goal_selection_required",
        "mutation_confirmation_required": False,
        "reason": reason,
    }
    recommended_next_step = {
        "kind": "select_goal",
        "requires_user_confirmation": False,
        "requires_goal_selection": True,
        "summary": reason,
        "goal_selection_gate": goal_selection_gate,
    }
    slash_command_catalog = build_slash_command_catalog(cli_bin=cli_bin)
    command_pack: dict[str, Any] = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "slash_command": CANONICAL_SLASH_COMMAND,
        "slash_forms": [
            {"form": "/loopx", "mode": "inspect_or_connect_preview"},
            {"form": "/loopx <goal text>", "mode": "goal_plan_write_and_activate"},
        ],
        "canonical_cli_command": None,
        "read_only": True,
        "goal_text": normalized_goal_text,
        "project": resolved_project,
        "goal_id": None,
        "agent_id": None,
        "requested_agent_id": agent_id,
        "agent_type": agent_type_for_host_surface(host_surface),
        "host_surface": host_surface,
        "project_connection": connection,
        "goal_selection_gate": goal_selection_gate,
        "host_loop_activation": {
            "activation_state": "goal_selection_required",
            "activation_allowed": False,
        },
        "available_slash_commands": slash_command_catalog,
        "onboarding_hint": slash_command_catalog["onboarding"],
        "recommended_next_step": recommended_next_step,
        "goal_start_contract": _goal_start_contract(
            goal_text=normalized_goal_text,
            connected=True,
            agent_type=agent_type_for_host_surface(host_surface),
        ),
        "commands": {
            "doctor": f"{shell_arg(cli_bin)} doctor",
            "status": _project_command(resolved_project, f"{shell_arg(cli_bin)} status"),
            "goal_selection_choices": choices,
            "goal_start_connect_if_needed": None,
            "goal_start_refresh_state": None,
            "goal_start_host_loop_activation": None,
            "goal_start_quota_should_run": None,
        },
        "safety_contract": {
            "runs_bootstrap": False,
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "explicit_goal_start_may_write_project_local_state": False,
            "explicit_goal_start_must_activate_host_loop": False,
            "host_loop_activation_allowed": False,
        },
    }
    command_pack["message"] = (
        f"{reason}. Rerun exactly one goal_selection_gate choice; no mutation or host-loop "
        "command is valid before that selection."
    )
    command_pack["packet_summary"] = _build_packet_summary(
        command_pack,
        packet_kind="bootstrap_command_pack",
        detail_refs={
            "project_connection": "#/project_connection",
            "goal_selection_gate": "#/goal_selection_gate",
            "recommended_next_step": "#/recommended_next_step",
            "commands": "#/commands",
            "safety_contract": "#/safety_contract",
            "compatibility_message": "#/message",
        },
    )
    guided_transaction = {
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "mode": "dry_run_preview",
        "writes_now": False,
        "spends_quota_now": False,
        "goal_text": normalized_goal_text,
        "blocked_by": "goal_selection",
        "goal_selection_gate": goal_selection_gate,
        "ordered_steps": [
            {
                "id": "inspect_connection",
                "kind": "read_only",
                "purpose": "resolve the canonical project and discover registered goals",
            },
            {
                "id": "select_goal",
                "kind": "goal_selection_gate",
                "choices": choices,
                "purpose": "select one registered goal before any todo, agent, state, or host-loop mutation",
            },
        ],
        "idempotency_policy": {
            "safe_to_rerun_preview": True,
            "reuse_connected_goal": True,
        },
        "preserve_todos_policy": {
            "force_bootstrap_default": "forbidden_in_guided_flow",
            "before_destructive_reconnect": "run backup-state and stop for an explicit preserve-todos confirmation",
            "preferred_scope_change": "use configure-goal incremental updates instead of force bootstrap when state already exists",
        },
    }
    detail_command = _start_goal_detail_command(
        project=resolved_project,
        goal_id=None,
        agent_id=agent_id,
        cli_bin=cli_bin,
        host_surface=host_surface,
        goal_text=normalized_goal_text,
        available_capabilities=available_capabilities,
    )
    selected_command_pack = (
        command_pack
        if include_command_pack_detail
        else _guided_command_pack_projection(
            command_pack,
            detail_command=detail_command,
        )
    )
    payload: dict[str, Any] = {
        "ok": True,
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "read_only": True,
        "guided": True,
        "project": resolved_project,
        "goal_id": None,
        "agent_id": None,
        "host_surface": host_surface,
        "goal_text": normalized_goal_text,
        "project_connection": connection,
        "goal_selection_gate": goal_selection_gate,
        "recommended_next_step": recommended_next_step,
        "guided_transaction": guided_transaction,
        "command_pack": selected_command_pack,
        "command_pack_detail_included": include_command_pack_detail,
        "safety_contract": {
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_commands_are_previewed": False,
            "force_bootstrap_allowed": False,
        },
    }
    payload["message"] = render_start_goal_guided_markdown(payload)
    payload["packet_summary"] = _build_packet_summary(
        payload,
        packet_kind="guided_start_goal",
        detail_refs={
            "command_pack_summary": "#/command_pack/packet_summary",
            "project_connection": "#/project_connection",
            "goal_selection_gate": "#/goal_selection_gate",
            "recommended_next_step": "#/recommended_next_step",
            "guided_transaction": "#/guided_transaction",
            "commands": "#/guided_transaction/ordered_steps",
            "safety_contract": "#/safety_contract",
            "compatibility_message": "#/message",
        },
        legacy_fields_retained=include_command_pack_detail,
        compact_projection_default=not include_command_pack_detail,
    )
    return payload


def build_start_goal_guided_packet(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
    goal_text: str,
    available_capabilities: list[str] | None = None,
    include_command_pack_detail: bool = False,
) -> dict[str, Any]:
    if goal_id is None:
        selection_packet = _build_multi_goal_start_selection_packet(
            project=project,
            agent_id=agent_id,
            cli_bin=cli_bin,
            host_surface=host_surface,
            goal_text=goal_text,
            available_capabilities=available_capabilities,
            include_command_pack_detail=include_command_pack_detail,
        )
        if selection_packet is not None:
            return selection_packet
    command_pack = build_loopx_bootstrap_command_pack(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        host_surface=host_surface,
        goal_text=goal_text,
        available_capabilities=available_capabilities,
    )
    commands = command_pack.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    activation = command_pack.get("host_loop_activation")
    activation = activation if isinstance(activation, dict) else {}
    identity_selection_gate = activation.get("identity_selection_gate")
    guided_transaction = {
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "mode": "dry_run_preview",
        "writes_now": False,
        "spends_quota_now": False,
        "goal_text": command_pack.get("goal_text"),
        "ordered_steps": [
            {
                "id": "inspect_connection",
                "kind": "read_only",
                "command": command_pack.get("canonical_cli_command"),
                "purpose": "resolve canonical project, goal id, registry, and active state before any mutation",
            },
            {
                "id": "connect_if_needed",
                "kind": "conditional_mutation",
                "command": commands.get("goal_start_connect_if_needed"),
                "purpose": "create or reuse project-local LoopX state only when no matching goal exists",
            },
            {
                "id": "plan_ranked_todos",
                "kind": "model_checkpoint",
                "prompt": commands.get("goal_start_plan_prompt"),
                "purpose": "produce concise public-safe P0/P1/P2 todos before todo writeback",
            },
            {
                "id": "write_ordered_todos",
                "kind": "operator_or_agent_actions",
                "command_template": (
                    f"{shell_arg(cli_bin)} todo add --goal-id "
                    f"{shell_arg(str(command_pack.get('goal_id') or ''))} --role agent "
                    "--task-class advancement_task --action-kind <action_kind> --text '<[P0/P1/P2] ...>'"
                ),
                "purpose": "write todos in planner order so same-priority ordering stays deterministic",
            },
            {
                "id": "refresh_state",
                "kind": "state_sync",
                "command": commands.get("goal_start_refresh_state"),
                "purpose": "project the accepted plan and next action into active state/history",
            },
            {
                "id": "activate_host_loop",
                "kind": "identity_gate" if identity_selection_gate else "host_loop",
                "command": commands.get("goal_start_host_loop_activation"),
                "purpose": "install or refresh the host loop only when it is missing, unknown, stale, or agent type changed",
            },
            {
                "id": "quota_guard",
                "kind": "guard",
                "command": commands.get("goal_start_quota_should_run"),
                "purpose": "let LoopX choose the first bounded segment and scheduler cadence",
            },
            {
                "id": "scheduler_ack_when_needed",
                "kind": "scheduler_state",
                "command_source": "quota.should-run.scheduler_hint.codex_app.ack_hint.cli_args",
                "purpose": "ack an applied Codex App RRULE without spending quota",
            },
        ],
        "idempotency_policy": {
            "safe_to_rerun_preview": True,
            "reuse_connected_goal": True,
            "do_not_duplicate_existing_todos": (
                "Do not duplicate existing todos; before writing, compare active todos by text/action_kind "
                "and update or skip matching items."
            ),
            "host_loop_recheck": (
                "Only regenerate or update automation when the host loop is missing, unknown, stale, or agent type changed."
            ),
        },
        "preserve_todos_policy": {
            "force_bootstrap_default": "forbidden_in_guided_flow",
            "before_destructive_reconnect": "run backup-state and stop for an explicit preserve-todos confirmation",
            "preferred_scope_change": "use configure-goal incremental updates instead of force bootstrap when state already exists",
        },
    }
    if isinstance(identity_selection_gate, dict):
        guided_transaction["blocked_by"] = "agent_identity_selection"
        guided_transaction["identity_selection_gate"] = identity_selection_gate
        guided_transaction["ordered_steps"].insert(
            1,
            {
                "id": "select_agent_identity",
                "kind": "identity_gate",
                "choices": identity_selection_gate.get("choices") or [],
                "purpose": "select one registered agent lane before generating heartbeat or quota commands",
            },
        )
    detail_command = _start_goal_detail_command(
        project=str(command_pack.get("project") or project),
        goal_id=str(command_pack.get("goal_id") or "") or None,
        agent_id=str(command_pack.get("agent_id") or "") or None,
        cli_bin=cli_bin,
        host_surface=host_surface,
        goal_text=str(command_pack.get("goal_text") or goal_text),
        available_capabilities=available_capabilities,
    )
    selected_command_pack = (
        command_pack
        if include_command_pack_detail
        else _guided_command_pack_projection(
            command_pack,
            detail_command=detail_command,
        )
    )
    payload = {
        "ok": True,
        "schema_version": GUIDED_START_SCHEMA_VERSION,
        "read_only": True,
        "guided": True,
        "project": command_pack.get("project"),
        "goal_id": command_pack.get("goal_id"),
        "agent_id": command_pack.get("agent_id"),
        "host_surface": command_pack.get("host_surface"),
        "goal_text": command_pack.get("goal_text"),
        "project_connection": command_pack.get("project_connection"),
        "recommended_next_step": command_pack.get("recommended_next_step"),
        "guided_transaction": guided_transaction,
        "command_pack": selected_command_pack,
        "command_pack_detail_included": include_command_pack_detail,
        "safety_contract": {
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_commands_are_previewed": True,
            "force_bootstrap_allowed": False,
        },
    }
    payload["message"] = render_start_goal_guided_markdown(payload)
    payload["packet_summary"] = _build_packet_summary(
        payload,
        packet_kind="guided_start_goal",
        detail_refs={
            "command_pack_summary": "#/command_pack/packet_summary",
            "project_connection": "#/project_connection",
            "recommended_next_step": "#/recommended_next_step",
            "guided_transaction": "#/guided_transaction",
            "commands": "#/guided_transaction/ordered_steps",
            "safety_contract": "#/safety_contract",
            "compatibility_message": "#/message",
        },
        legacy_fields_retained=include_command_pack_detail,
        compact_projection_default=not include_command_pack_detail,
    )
    return payload


def render_start_goal_guided_markdown(payload: dict[str, Any]) -> str:
    transaction = payload.get("guided_transaction")
    transaction = transaction if isinstance(transaction, dict) else {}
    steps = transaction.get("ordered_steps")
    steps = steps if isinstance(steps, list) else []
    step_lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        command = step.get("command") or step.get("command_template") or step.get("command_source") or step.get("prompt")
        step_lines.extend(
            [
                f"{index}. `{step.get('id')}` ({step.get('kind')})",
                f"   - purpose: {step.get('purpose')}",
            ]
        )
        if command:
            step_lines.append(f"   - command/source: `{str(command).splitlines()[0]}`")
    preserve = transaction.get("preserve_todos_policy")
    preserve = preserve if isinstance(preserve, dict) else {}
    identity_gate = transaction.get("identity_selection_gate")
    identity_gate = identity_gate if isinstance(identity_gate, dict) else {}
    identity_gate_lines = ""
    if identity_gate:
        choices = [
            f"- `{choice.get('agent_id')}` ({choice.get('role')}): "
            f"`{choice.get('heartbeat_prompt_json')}`"
            for choice in identity_gate.get("choices") or []
            if isinstance(choice, dict)
        ]
        identity_gate_lines = (
            "\n## Agent Identity Gate\n\n"
            f"{identity_gate.get('reason')}\n\n"
            + "\n".join(choices)
            + "\n"
        )
    goal_gate = transaction.get("goal_selection_gate")
    goal_gate = goal_gate if isinstance(goal_gate, dict) else {}
    goal_gate_lines = ""
    if goal_gate:
        choices = [
            f"- `{choice.get('goal_id')}` status=`{choice.get('status')}`: "
            f"`{choice.get('rerun_command')}`"
            for choice in goal_gate.get("choices") or []
            if isinstance(choice, dict)
        ]
        goal_gate_lines = (
            "\n## Goal Selection Gate\n\n"
            f"{goal_gate.get('reason')}\n\n"
            + "\n".join(choices)
            + "\n"
        )
    host_gate = transaction.get("host_surface_selection_gate")
    host_gate = host_gate if isinstance(host_gate, dict) else {}
    host_gate_lines = ""
    if host_gate:
        choices = [
            f"- `{choice.get('host_surface')}`: {choice.get('description')}  "
            f"\n  `{choice.get('rerun_command')}`"
            for choice in host_gate.get("choices") or []
            if isinstance(choice, dict)
        ]
        host_gate_lines = (
            "\n## Host Surface Gate\n\n"
            f"{host_gate.get('reason')}\n\n"
            + "\n".join(choices)
            + "\n"
        )
    return f"""# Guided Start Goal

- schema: `{payload.get("schema_version")}`
- read_only: `{payload.get("read_only")}`
- project: `{payload.get("project")}`
- goal_id: `{payload.get("goal_id")}`
- goal_text: `{payload.get("goal_text")}`

This is a guided dry-run packet. It previews the transaction and keeps mutation
behind explicit command execution by the host/agent.

## Ordered Transaction

{chr(10).join(step_lines)}
{host_gate_lines}
{goal_gate_lines}
{identity_gate_lines}

## Todo Preservation

- force_bootstrap_default: `{preserve.get("force_bootstrap_default")}`
- before_destructive_reconnect: {preserve.get("before_destructive_reconnect")}
- preferred_scope_change: {preserve.get("preferred_scope_change")}
"""


def render_loopx_bootstrap_command_pack_message(payload: dict[str, Any]) -> str:
    connection = payload.get("project_connection")
    connection = connection if isinstance(connection, dict) else {}
    commands = payload.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    next_step = payload.get("recommended_next_step")
    next_step = next_step if isinstance(next_step, dict) else {}
    requires_confirmation = bool(next_step.get("requires_user_confirmation"))
    project = payload.get("project")
    goal_id = payload.get("goal_id")
    goal_text = payload.get("goal_text")
    state = connection.get("connection_state")
    reason = connection.get("reason")
    alias = connection.get("canonical_project_alias")
    alias = alias if isinstance(alias, dict) else {}
    alias_note = (
        f"\nInput project: `{connection.get('input_project')}`\n"
        f"Canonical route: `{alias.get('canonical_project')}` via `{alias.get('source_registry')}`\n"
        if alias.get("applied")
        else ""
    )
    goal_start_contract = payload.get("goal_start_contract")
    goal_start_contract = goal_start_contract if isinstance(goal_start_contract, dict) else {}
    onboarding = payload.get("onboarding_hint")
    onboarding = onboarding if isinstance(onboarding, dict) else {}
    activation = payload.get("host_loop_activation")
    activation = activation if isinstance(activation, dict) else {}
    identity_gate = activation.get("identity_selection_gate")
    identity_gate = identity_gate if isinstance(identity_gate, dict) else {}

    if identity_gate:
        choices = "\n".join(
            f"- `{choice.get('agent_id')}` ({choice.get('role')}): "
            f"`{choice.get('heartbeat_prompt_json')}`"
            for choice in identity_gate.get("choices") or []
            if isinstance(choice, dict)
        )
        action = f"""Select one registered agent lane before planning writes or host-loop activation.
No unscoped heartbeat or quota command is advertised for this multi-agent goal.

Reason: {identity_gate.get("reason")}

Identity-aware choices:
{choices}

Rerun `{payload.get("canonical_cli_command")} --agent-id <registered-agent-id>`
with the selected identity before continuing."""
    elif goal_text:
        action = f"""This is an explicit goal-start invocation. Connect project-local LoopX state if needed:

```bash
{commands.get("goal_start_connect_if_needed", "")}
```

Then plan before writing todos. Preserve relative priority by write order:

````text
{commands.get("goal_start_plan_prompt", "")}
````

Write the planned todos with `loopx todo add` in the exact planned order. Same-priority items use that write order as the tie-breaker.

For GitHub issue/PR fix goals, preview the issue-fix route before todo writeback:

```bash
{commands.get("issue_fix_workflow_plan_template", "")}
```

Write only metadata classification plus the feasibility checkpoint from this preview. Then run the compact decision and write only its selected successor or no-follow-up:

```bash
{commands.get("issue_fix_feasibility_template", "")}
```

Private repro material, issue body/comment reads, external comments, PR creation, merge, publish, destructive git, and production actions stay explicit gates.

After a PR exists and external-review-request authority is active, request the default top requestable non-author reviewer and require post-write verification:

```bash
{commands.get("issue_fix_reviewer_request_template", "")}
```

After a PR exists, the PR lifecycle monitor should observe compact public PR state and write issue-fix domain state by default:

```bash
{commands.get("issue_fix_pr_lifecycle_template", "")}
```

After todo writeback:

```bash
{commands.get("goal_start_refresh_state", "")}
{commands.get("goal_start_host_loop_activation", "")}
{commands.get("goal_start_quota_should_run", "")}
```

Host loop activation is part of setup, not a nice-to-have:
- agent_type: `{payload.get("agent_type")}`
- host_surface: `{activation.get("host_surface")}`
- activation_method: `{activation.get("activation_method")}`

If the host loop is already proven current, skip the mutation. If it is missing,
unknown, or stale, use the command above to obtain `task_body` and activate the
right host loop: Codex App automation, Codex CLI `/goal <task_body>`, Claude
Code `/loop`, or the custom host-loop gate. If this session cannot mutate that
host surface, report the exact gate; do not claim autonomous setup complete.
Use `{commands.get("goal_start_agent_onboard_recheck", "")}` only when
activation state is missing/unknown/stale or the agent type changed."""
    elif requires_confirmation:
        action = f"""First show this dry-run preview, then ask me before running the mutation:

```bash
{commands.get("bootstrap_dry_run_preview", "")}
```

If I confirm, run:

```bash
{commands.get("bootstrap_after_user_confirmation", "")}
```"""
    else:
        action = f"""Start with the current LoopX status and do not reconnect:

```bash
{commands.get("status", "")}
```

Only after I ask for a recurring loop surface, generate the heartbeat body:

```bash
{commands.get("heartbeat_prompt", "")}
```"""

    return f"""Handle `{CANONICAL_SLASH_COMMAND}` for this project with explicit mutation boundaries.

Project: `{project}`
Goal id: `{goal_id}`
Goal text: `{goal_text or ""}`
Detected state: `{state}` ({reason})
{alias_note}

Rules:
- This command pack preview is read-only. Do not run bootstrap/connect, create heartbeat automation, or spend quota while only previewing it.
- Bare `/loopx` is read/status-first: if the project is not fully connected, ask for explicit user confirmation before any command that writes `.loopx/` or `.codex/goals/`.
- `/loopx <goal text>` is explicit goal-start intent: it may create project-local LoopX state, but it must run the profile-appropriate planning checkpoint before writing todos, then activate the correct host loop if missing/stale.
- Same-priority todos are ranked by planner order, then by `todo add` write order; preserve the order exactly.
- If the project is connected, reuse the existing state and show the status/gate/todo snapshot.

Goal-start contract: `{goal_start_contract.get("schema_version")}`

Suggested new-user note:

```text
{onboarding.get("suggested_user_note", "")}
```

{action}

For ongoing work after the project is connected, use the quota guard:

```bash
{commands.get("quota_guard", "")}
```
"""


def render_loopx_bootstrap_command_pack_markdown(payload: dict[str, Any]) -> str:
    connection = payload.get("project_connection")
    connection = connection if isinstance(connection, dict) else {}
    next_step = payload.get("recommended_next_step")
    next_step = next_step if isinstance(next_step, dict) else {}
    safety = payload.get("safety_contract")
    safety = safety if isinstance(safety, dict) else {}
    commands = payload.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    onboarding = payload.get("onboarding_hint")
    onboarding = onboarding if isinstance(onboarding, dict) else {}
    slash_catalog = payload.get("available_slash_commands")
    slash_catalog = slash_catalog if isinstance(slash_catalog, dict) else {}
    goal_start = payload.get("goal_start_contract")
    goal_start = goal_start if isinstance(goal_start, dict) else {}
    activation = payload.get("host_loop_activation")
    activation = activation if isinstance(activation, dict) else {}
    ordering = goal_start.get("priority_ordering")
    ordering = ordering if isinstance(ordering, dict) else {}
    return f"""# /loopx Bootstrap Command Pack

Canonical slash command: `{payload.get("slash_command")}`
Supported forms: `/loopx`, `/loopx <goal text>`

## Detected Project State

- project: `{payload.get("project")}`
- input_project: `{connection.get("input_project")}`
- goal_id: `{payload.get("goal_id")}`
- agent_type: `{payload.get("agent_type")}`
- goal_text: `{payload.get("goal_text") or ""}`
- connection_state: `{connection.get("connection_state")}`
- reason: `{connection.get("reason")}`
- registry: `{connection.get("registry")}`
- state_file: `{connection.get("state_file")}`
- canonical_project_alias: `{(connection.get("canonical_project_alias") or {}).get("kind") if isinstance(connection.get("canonical_project_alias"), dict) else None}`

## Recommended Next Step

- kind: `{next_step.get("kind")}`
- requires_user_confirmation: `{next_step.get("requires_user_confirmation")}`
- summary: {next_step.get("summary")}

## New User Command Hint

````text
{onboarding.get("suggested_user_note", "")}
````

- CLI help: `{(slash_catalog.get("help") or {}).get("cli_command") if isinstance(slash_catalog.get("help"), dict) else "loopx slash-commands"}`

## Paste Message

````text
{payload.get("message", "")}
````

## Goal Start Contract

- schema: `{goal_start.get("schema_version")}`
- planner_required_before_todo_write: `{(goal_start.get("planner") or {}).get("required_before_todo_write") if isinstance(goal_start.get("planner"), dict) else None}`
- same_priority_tie_breaker: `{ordering.get("same_priority_tie_breaker")}`
- prompt_constraint: {ordering.get("prompt_constraint")}
- host_loop_required_after_todo_writeback: `{(goal_start.get("activation") or {}).get("host_loop_required_after_todo_writeback") if isinstance(goal_start.get("activation"), dict) else None}`

## Host Loop Activation

- host_surface: `{activation.get("host_surface")}`
- activation_method: `{activation.get("activation_method")}`
- entry_command_hint: `{activation.get("entry_command_hint")}`
- activation_input_command: `{activation.get("activation_input_command")}`
- recheck_command: `{commands.get("goal_start_agent_onboard_recheck")}`

## Key Commands

```bash
{commands.get("status", "")}
```

```bash
{commands.get("bootstrap_dry_run_preview", "")}
```

```bash
{commands.get("goal_start_connect_if_needed", "")}
```

```bash
{commands.get("issue_fix_workflow_plan_template", "")}
```

## Safety Contract

- read_only: `{payload.get("read_only")}`
- writes_registry: `{safety.get("writes_registry")}`
- writes_state_file: `{safety.get("writes_state_file")}`
- creates_heartbeat: `{safety.get("creates_heartbeat")}`
- spends_quota: `{safety.get("spends_quota")}`
- explicit_goal_start_may_write_project_local_state: `{safety.get("explicit_goal_start_may_write_project_local_state")}`
- explicit_goal_start_must_activate_host_loop: `{safety.get("explicit_goal_start_must_activate_host_loop")}`
"""
