from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .authority import (
    AUTHORITY_SOURCE_BOUNDARIES,
    import_doc_registry_authority,
    register_authority_source,
    render_doc_registry_authority_import_markdown,
    render_authority_source_markdown,
)
from .bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from .configure_goal import configure_goal, render_configure_goal_markdown
from .contract import check_contract, render_contract_markdown
from .demo import (
    DEFAULT_DEMO_AGENT_TODO,
    DEFAULT_DEMO_GOAL_ID,
    DEFAULT_DEMO_OBJECTIVE,
    DEFAULT_DEMO_PROJECT,
    DEFAULT_DEMO_USER_TODO,
    render_demo_markdown,
    run_demo,
)
from .doctor import collect_doctor, render_doctor_markdown
from .execution_profile import DEFAULT_EXECUTION_PROFILE
from .feedback import append_human_reward, compact_reward, render_reward_markdown
from .global_registry import render_global_sync_markdown, sync_project_registry_to_global
from .handoff_budget import build_handoff_interface_budget
from .heartbeat_prompt import build_heartbeat_prompt, render_heartbeat_prompt_markdown
from .history import (
    append_benchmark_comparison,
    append_benchmark_experiment_report,
    append_benchmark_result,
    append_benchmark_run,
    collect_history,
    load_registry,
    render_benchmark_comparison_append_markdown,
    render_benchmark_experiment_report_append_markdown,
    render_benchmark_result_append_markdown,
    render_benchmark_run_append_markdown,
    render_history_markdown,
)
from .operator_gate import (
    DEFAULT_OPERATOR_GATE,
    OPERATOR_GATE_DECISIONS,
    record_operator_gate,
    render_operator_gate_markdown,
)
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path, resolve_runtime_root
from .project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    build_new_project_prompt,
    render_new_project_prompt_markdown,
)
from .project_map import (
    DEFAULT_PROJECT_MAP_CLASSIFICATION,
    read_only_project_map_run,
    render_read_only_project_map_markdown,
)
from .promotion_gate import build_promotion_gate, render_promotion_gate_markdown
from .quota import (
    build_quota_plan,
    build_quota_should_run,
    render_quota_markdown,
    render_quota_should_run_markdown,
    render_quota_slot_preview_markdown,
    spend_quota_slot,
)
from .registry import inspect_registry, registry_goals, render_registry_markdown, resolve_state_file
from .review_packet import build_review_packet, render_review_packet_markdown
from .runtime import archive_runtime_goal, render_archive_runtime_markdown
from .state_refresh import (
    DEFAULT_REFRESH_ACTION,
    DEFAULT_REFRESH_CLASSIFICATION,
    DELIVERY_BATCH_SCALE_CHOICES,
    DELIVERY_OUTCOME_CHOICES,
    refresh_state_run,
    render_state_refresh_markdown,
)
from .status import (
    collect_status,
    compact_benchmark_comparison,
    compact_benchmark_experiment_report,
    compact_benchmark_result,
    compact_benchmark_run,
    render_status_markdown,
)
from .status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)
from .todos import add_goal_todo, render_todo_markdown
from .upgrade import build_upgrade_plan, render_upgrade_plan_markdown


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def add_subcommand_format(arg_parser: argparse.ArgumentParser) -> None:
    arg_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand. Equivalent to global --format before the command.",
    )


def output_format(args: argparse.Namespace, *local_dests: str) -> str:
    for dest in (*local_dests, "subcommand_format"):
        value = getattr(args, dest, None)
        if value:
            return str(value)
    return str(args.format)


def review_packet_handoff_only_payload(payload: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "ok": bool(payload.get("ok")),
        "goal_id": payload.get("goal_id"),
        "handoff_only": True,
    }
    if not payload.get("ok"):
        result["error"] = payload.get("error")
        return result
    handoff_text = str(payload.get("project_agent_handoff") or "")
    raw_contract = payload.get("handoff_delivery_contract")
    agent_contract = raw_contract
    if isinstance(raw_contract, dict):
        agent_contract = {
            "mode": raw_contract.get("mode"),
            "instruction": raw_contract.get("instruction"),
            "minimum_scale": raw_contract.get("minimum_scale"),
            "must_include": raw_contract.get("must_include"),
            "if_blocked": raw_contract.get("if_blocked"),
        }
    handoff_budget = payload.get("handoff_interface_budget")
    if not isinstance(handoff_budget, dict):
        handoff_budget = build_handoff_interface_budget(handoff_text)
    result.update(
        {
            "kind": payload.get("kind"),
            "status": payload.get("status"),
            "waiting_on": payload.get("waiting_on"),
            "project_agent_command": payload.get("project_agent_command"),
            "project_agent_handoff": handoff_text,
            "handoff_text": handoff_text,
            "benchmark_report_chain_handoff": payload.get("benchmark_report_chain_handoff"),
            "operator_gate_approved_handoff": payload.get("operator_gate_approved_handoff"),
            "connected_delivery_handoff": payload.get("connected_delivery_handoff"),
            "handoff_delivery_contract": agent_contract,
            "handoff_interface_budget": handoff_budget,
            "line_count": handoff_budget.get("line_count"),
            "char_count": handoff_budget.get("char_count"),
            "within_budget": handoff_budget.get("within_budget"),
        }
    )
    return result


def user_supplied_registry(argv: list[str] | None) -> bool:
    values = sys.argv[1:] if argv is None else argv
    return any(value == "--registry" or value.startswith("--registry=") for value in values)


def fallback_global_registry(registry_path: Path, runtime_root_arg: str | None) -> Path:
    if registry_path.exists():
        return registry_path
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    fallback_registry = global_registry_path(runtime_root)
    return fallback_registry if fallback_registry.exists() else registry_path


def explicit_global_registry(runtime_root_arg: str | None) -> Path:
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    return global_registry_path(runtime_root)


def resolve_heartbeat_active_state(
    *,
    goal_id: str,
    active_state_arg: str | None,
    registry_path: Path,
    runtime_root_arg: str | None,
) -> tuple[Path | None, Path | None, str]:
    if active_state_arg:
        active_state = Path(active_state_arg).expanduser()
        return active_state, active_state, "explicit"

    resolved_registry = fallback_global_registry(registry_path, runtime_root_arg)
    registry = load_registry(resolved_registry)
    goal = next((item for item in registry_goals(registry) if item.get("id") == goal_id), None)
    if goal is None:
        raise ValueError(f"goal_id not found in registry for heartbeat active-state lookup: {goal_id}")
    repo_text = str(goal.get("repo") or "")
    if not repo_text:
        raise ValueError(f"{goal_id}: registry goal has no repo for active-state lookup")
    state_file = resolve_state_file(Path(repo_text).expanduser(), goal.get("state_file"))
    if state_file is None:
        raise ValueError(f"{goal_id}: registry goal has no state_file for active-state lookup")
    if not state_file.exists():
        raise FileNotFoundError(f"{goal_id}: registry-declared active state file does not exist: {state_file}")
    return None, state_file, f"registry:{resolved_registry}"


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal Harness control-plane helper.")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = sub.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE, help="Initial goal objective.")
    bootstrap_parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Goal domain label.")
    bootstrap_parser.add_argument("--role", choices=["controller", "subagent"], default="controller")
    bootstrap_parser.add_argument("--parent-goal-id", help="Parent goal id when --role subagent.")
    bootstrap_parser.add_argument("--state-file", help="Active goal state path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--goal-doc", help="Primary goal document path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--adapter-kind", default="generic_project_goal_v0")
    bootstrap_parser.add_argument("--adapter-status", default="connected")
    bootstrap_parser.add_argument("--next-probe", help="Optional project-specific pre-tick command.")
    bootstrap_parser.add_argument("--spawn-allowed", action="store_true", help="Declare that this controller may spawn child agents.")
    bootstrap_parser.add_argument("--max-children", type=int, default=3)
    bootstrap_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    bootstrap_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")
    bootstrap_parser.add_argument("--claim-ttl-minutes", type=int, default=30)
    bootstrap_parser.add_argument(
        "--execution-minimum-scale",
        default=str(DEFAULT_EXECUTION_PROFILE["minimum_scale"]),
        help="Minimum delivery scale after repeated small follow-through.",
    )
    bootstrap_parser.add_argument(
        "--execution-must-include",
        action="append",
        default=[],
        help="Required delivery component. Repeatable; defaults to artifact, validation, and state writeback.",
    )
    bootstrap_parser.add_argument(
        "--execution-small-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["degradation_policy"]["small_scale_streak_threshold"]),
        help="Repeated small-scale streak that triggers the delivery contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-marker",
        action="append",
        default=[],
        help="Classification substring that counts as primary outcome/evidence progress. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-only-hint",
        action="append",
        default=[],
        help="Classification substring that counts as surface-only progress unless an outcome marker is present. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["outcome_floor"]["surface_streak_threshold"]),
        help="Surface-progress streak that triggers the outcome-floor contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-must-advance",
        action="append",
        default=[],
        help="Outcome/evidence floor label that future delivery must advance. Repeatable.",
    )
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    bootstrap_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not merge this project registry into the shared global registry.",
    )

    prompt_parser = sub.add_parser(
        "new-project-prompt",
        help="Generate a copy-paste Codex prompt for connecting a project from a goal document.",
    )
    prompt_parser.add_argument("--project", required=True, help="Project directory the target Codex session can access.")
    prompt_parser.add_argument("--goal-doc", required=True, help="Goal document path for the target project.")
    prompt_parser.add_argument("--goal-id", help="Initial stable goal id. Defaults to <project-name>-goal.")
    prompt_parser.add_argument("--objective", help="Initial objective. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--domain", help="Initial domain label. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--adapter-kind", default=DEFAULT_HANDOFF_ADAPTER_KIND)
    prompt_parser.add_argument("--adapter-status", default=DEFAULT_HANDOFF_ADAPTER_STATUS)
    prompt_parser.add_argument("--next-probe", help="Optional read-only pre-tick command for the target project.")
    prompt_parser.add_argument("--spawn-allowed", action="store_true", help="Include controller/sub-agent flags.")
    prompt_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    prompt_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")

    heartbeat_prompt_parser = sub.add_parser(
        "heartbeat-prompt",
        help="Generate a guarded Codex App heartbeat automation task body.",
    )
    add_subcommand_format(heartbeat_prompt_parser)
    heartbeat_prompt_parser.add_argument("--goal-id", required=True, help="Stable Goal Harness goal id.")
    heartbeat_prompt_parser.add_argument(
        "--active-state",
        help="Active goal state file the heartbeat should read and write back. Defaults to the registry goal state_file.",
    )
    heartbeat_prompt_parser.add_argument(
        "--material-rule",
        help="Optional project-specific material queue rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--permission-rule",
        help="Optional trusted-session permission rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Command name embedded in generated preflight/guard/spend commands. Use goal-harness-canary for gray rollout targets.",
    )
    heartbeat_style_group = heartbeat_prompt_parser.add_mutually_exclusive_group()
    heartbeat_style_group.add_argument(
        "--compact",
        action="store_true",
        help="Generate a shorter automation body that points edge cases back to the expanded lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--brief",
        action="store_true",
        help="Generate a minimal installed automation body that delegates details to the compact lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--thin",
        action="store_true",
        help="Generate the thinnest generic dispatcher body for trusted agents that inspect Goal Harness state themselves.",
    )

    demo_parser = sub.add_parser(
        "demo",
        help="Create a disposable local demo goal and show status/quota output.",
    )
    demo_parser.add_argument(
        "--project",
        default=str(DEFAULT_DEMO_PROJECT),
        help=f"Disposable demo project directory. Defaults to {DEFAULT_DEMO_PROJECT}.",
    )
    demo_parser.add_argument("--goal-id", default=DEFAULT_DEMO_GOAL_ID)
    demo_parser.add_argument("--objective", default=DEFAULT_DEMO_OBJECTIVE)
    demo_parser.add_argument("--user-todo", default=DEFAULT_DEMO_USER_TODO)
    demo_parser.add_argument("--agent-todo", default=DEFAULT_DEMO_AGENT_TODO)

    sub.add_parser("doctor", help="Diagnose local CLI installation, PATH, wrapper, and import health.")

    promotion_gate_parser = sub.add_parser(
        "promotion-gate",
        help="Emit a compact machine-readable canary promotion readiness gate result.",
    )
    add_subcommand_format(promotion_gate_parser)

    upgrade_plan_parser = sub.add_parser(
        "upgrade-plan",
        help="Plan local default upgrade propagation for managed heartbeat automations.",
    )
    add_subcommand_format(upgrade_plan_parser)
    upgrade_plan_parser.add_argument("--goal-id", action="append", default=[], help="Only include one goal id. Repeatable.")
    upgrade_plan_parser.add_argument(
        "--installed-manifest",
        help=(
            "Optional JSON manifest of installed automations with goal_id, mode, automation_id, and "
            "prompt_sha256/task_body. If omitted, upgrade-plan auto-discovers Codex App heartbeat "
            "automations from $CODEX_HOME/automations or ~/.codex/automations."
        ),
    )
    upgrade_plan_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="CLI command embedded in generated heartbeat prompts for the promoted default.",
    )
    upgrade_plan_parser.add_argument(
        "--mode",
        action="append",
        choices=["thin", "brief", "compact"],
        default=[],
        help="Prompt mode to compare. Repeatable; defaults to the thin installed heartbeat contract.",
    )

    sub.add_parser("registry", help="Inspect registry goals and adapter declarations.")

    configure_goal_parser = sub.add_parser(
        "configure-goal",
        help="Preview or apply per-goal registry settings for quota, self-repair, and orchestration.",
    )
    configure_goal_parser.add_argument("--goal-id", required=True, help="Goal id to configure.")
    configure_goal_parser.add_argument("--quota-compute", type=float, help="Per-goal quota compute multiplier.")
    configure_goal_parser.add_argument("--quota-window-hours", type=float, help="Quota rolling window in hours.")
    configure_goal_parser.add_argument(
        "--self-repair-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control_plane.self_repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-health",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control-plane health blocker repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-waiting-projection",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable waiting-projection repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--orchestration-mode",
        choices=["default", "multi_subagent"],
        help="Per-goal orchestration mode.",
    )
    configure_goal_parser.add_argument(
        "--spawn-allowed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow or block sub-agent spawning for this goal.",
    )
    configure_goal_parser.add_argument("--max-children", type=int, help="Maximum child agents for orchestration.")
    configure_goal_parser.add_argument(
        "--allowed-domain",
        action="append",
        default=None,
        help="Allowed child-agent domain. Repeatable; comma-separated values are also accepted.",
    )
    configure_goal_parser.add_argument(
        "--clear-allowed-domains",
        action="store_true",
        help="Clear allowed child-agent domains.",
    )
    configure_goal_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the registry. Without this flag, configure-goal is a dry-run preview.",
    )

    history_parser = sub.add_parser("history", help="Read compact run history from the shared runtime root.")
    history_parser.add_argument(
        "history_action",
        nargs="?",
        choices=[
            "append-benchmark-run",
            "append-benchmark-result",
            "append-benchmark-comparison",
            "append-benchmark-report",
        ],
        help="Append a compact benchmark_run_v0, benchmark_result_v0, benchmark_comparison_v0, or benchmark_experiment_report_v0 event.",
    )
    history_parser.add_argument("--goal-id", help="Only show one goal.")
    history_parser.add_argument("--limit", type=int, default=10)
    history_parser.add_argument(
        "--benchmark-run-json",
        help="Path to a benchmark_run_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-result-json",
        help="Path to a benchmark_result_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-comparison-json",
        help="Path to a benchmark_comparison_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-report-json",
        help="Path to a benchmark_experiment_report_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument("--classification")
    history_parser.add_argument(
        "--recommended-action",
        help="Recommended next action for the compact append event.",
    )
    history_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    history_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    history_parser.add_argument("--dry-run", action="store_true", help="Preview append without writing. This is the default.")
    history_parser.add_argument("--execute", action="store_true", help="Append the compact benchmark event.")
    history_parser.add_argument("--no-global-sync", action="store_true", help="Skip global registry sync after append.")

    archive_runtime_parser = sub.add_parser(
        "archive-runtime",
        help="Move an obsolete runtime goal directory into the archive area. Defaults to dry-run.",
    )
    archive_runtime_parser.add_argument("--goal-id", required=True, help="Runtime goal id to archive.")
    archive_runtime_parser.add_argument(
        "--archive-root",
        help="Archive directory. Defaults to <runtime-root>/archived-goals.",
    )
    archive_runtime_parser.add_argument(
        "--allow-registered",
        action="store_true",
        help="Allow archiving a goal that is still present in the registry.",
    )
    archive_runtime_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move the runtime directory. Without this flag the command is a dry-run.",
    )

    sync_global_parser = sub.add_parser(
        "sync-global",
        help="Merge this project-local registry into the shared global registry.",
    )
    sync_global_parser.add_argument("--goal-id", help="Only sync one goal id from the source registry.")
    sync_global_parser.add_argument("--dry-run", action="store_true", help="Preview the global registry merge.")

    refresh_state_parser = sub.add_parser(
        "refresh-state",
        help="Append a read-only run from active goal state after state-only updates.",
    )
    refresh_state_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose active state should be refreshed.",
    )
    refresh_state_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    refresh_state_parser.add_argument(
        "--state-file",
        help="Active goal state path. Defaults to the registry goal state_file.",
    )
    refresh_state_parser.add_argument(
        "--classification",
        default=DEFAULT_REFRESH_CLASSIFICATION,
        help=f"Refresh run classification. Defaults to {DEFAULT_REFRESH_CLASSIFICATION}.",
    )
    refresh_state_parser.add_argument(
        "--recommended-action",
        help=f"Public-safe next action. Defaults to: {DEFAULT_REFRESH_ACTION}",
    )
    refresh_state_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional explicit delivery scale for this refresh run, overriding classification-name inference.",
    )
    refresh_state_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional explicit outcome-floor signal for this refresh run.",
    )
    refresh_state_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the refresh payload without appending.",
    )
    refresh_state_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the state run.",
    )

    read_only_map_parser = sub.add_parser(
        "read-only-map",
        help="Append a generic read-only project-map run for a connected project.",
    )
    read_only_map_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose project should be mapped.",
    )
    read_only_map_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    read_only_map_parser.add_argument(
        "--state-file",
        help="Active goal state path. Defaults to the registry goal state_file.",
    )
    read_only_map_parser.add_argument(
        "--classification",
        default=DEFAULT_PROJECT_MAP_CLASSIFICATION,
        help=f"Project-map run classification. Defaults to {DEFAULT_PROJECT_MAP_CLASSIFICATION}.",
    )
    read_only_map_parser.add_argument(
        "--recommended-action",
        help="Public-safe next action. Defaults to the first public-safe item from the active state's Next Action.",
    )
    read_only_map_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the project-map payload without appending.",
    )
    read_only_map_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the project-map run.",
    )

    reward_parser = sub.add_parser(
        "reward",
        help="Append a compact human reward overlay to a goal run index.",
    )
    reward_parser.add_argument("--goal-id", required=True, help="Goal id whose latest run should receive feedback.")
    reward_parser.add_argument(
        "--run-generated-at",
        help="Exact run generated_at timestamp. Defaults to the latest compact run for the goal.",
    )
    reward_parser.add_argument("--recorded-at", help="Reward timestamp. Defaults to current UTC time.")
    reward_parser.add_argument("--decision", required=True, help="Operator decision label, such as continue_route.")
    reward_parser.add_argument(
        "--reward",
        required=True,
        choices=["positive", "negative", "mixed", "neutral"],
        help="Compact reward polarity.",
    )
    reward_parser.add_argument(
        "--reason-summary",
        required=True,
        help="Short public-safe reason. Do not include raw private evidence.",
    )
    reward_parser.add_argument("--follow-up", help="Optional next handoff or experiment condition.")
    reward_parser.add_argument(
        "--state-file",
        help="Active goal state path for optional summary writeback. Defaults to the registry goal state_file.",
    )
    reward_parser.add_argument(
        "--write-active-state-summary",
        action="store_true",
        help="After a real append, also add the returned active_state_summary to the active state's Progress Ledger. With --dry-run, preview only.",
    )
    reward_parser.add_argument("--dry-run", action="store_true", help="Print the overlay without appending it.")

    gate_parser = sub.add_parser(
        "operator-gate",
        help="Record an operator gate decision such as read-only map opt-in.",
    )
    gate_parser.add_argument("--goal-id", required=True, help="Goal id whose operator gate is being judged.")
    gate_parser.add_argument("--gate", default=DEFAULT_OPERATOR_GATE, help=f"Gate id. Defaults to {DEFAULT_OPERATOR_GATE}.")
    gate_parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(OPERATOR_GATE_DECISIONS),
        help="Operator decision for this gate.",
    )
    gate_parser.add_argument("--recorded-at", help="Decision timestamp. Defaults to current local time.")
    gate_parser.add_argument(
        "--operator-question",
        help="Human-facing question being answered. Defaults from --gate and --goal-id.",
    )
    gate_parser.add_argument(
        "--reason-summary",
        required=True,
        help="Short public-safe reason. Do not include raw private evidence.",
    )
    gate_parser.add_argument("--follow-up", help="Optional next handoff or evidence condition.")
    gate_parser.add_argument(
        "--agent-command",
        help="Target-agent command that becomes valid after approval. Defaults for read_only_map_opt_in approvals.",
    )
    gate_parser.add_argument("--recommended-action", help="Public-safe next action for status/dashboard.")
    gate_parser.add_argument("--dry-run", action="store_true", help="Print the decision run without appending it.")
    gate_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the gate decision.",
    )

    authority_parser = sub.add_parser(
        "register-authority-source",
        help="Register a redacted local authority/material source for a goal.",
    )
    authority_parser.add_argument("--goal-id", required=True, help="Goal id whose local registry should be updated.")
    authority_parser.add_argument("--source-id", required=True, help="Stable local source id.")
    authority_parser.add_argument(
        "--source-ref",
        help="Raw local source reference to hash and redact. The raw value is never stored.",
    )
    authority_parser.add_argument("--source-kind", required=True, help="Public-safe source kind, such as doc or repository.")
    authority_parser.add_argument("--role", required=True, help="Public-safe material role.")
    authority_parser.add_argument("--freshness", required=True, help="Public-safe freshness state.")
    authority_parser.add_argument("--owner-status", help="Optional public-safe owner/review status.")
    authority_parser.add_argument("--gate-status", help="Optional public-safe gate status.")
    authority_parser.add_argument(
        "--boundary",
        choices=sorted(AUTHORITY_SOURCE_BOUNDARIES),
        default="private_redacted",
        help="Public/private boundary for this source. Defaults to private_redacted.",
    )
    authority_parser.add_argument("--revision", help="Optional public-safe revision label.")
    authority_parser.add_argument("--conflict-rule", help="Optional public-safe conflict rule.")
    authority_parser.add_argument("--topic", help="Optional topic_authority key to map to this source id.")
    authority_parser.add_argument("--dry-run", action="store_true", help="Preview the registry update without writing.")
    authority_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the local source registry.",
    )

    doc_registry_authority_parser = sub.add_parser(
        "import-doc-registry-authority",
        help="Import a redacted DOC_REGISTRY summary as a local authority/material source.",
    )
    doc_registry_authority_parser.add_argument(
        "--goal-id", required=True, help="Goal id whose local registry should be updated."
    )
    doc_registry_authority_parser.add_argument("--source-id", required=True, help="Stable local source id.")
    doc_registry_authority_parser.add_argument(
        "--doc-registry-path",
        required=True,
        help="Local DOC_REGISTRY.yaml path to read. The raw path is hashed and not stored.",
    )
    doc_registry_authority_parser.add_argument(
        "--source-kind",
        default="doc_registry",
        help="Public-safe source kind. Defaults to doc_registry.",
    )
    doc_registry_authority_parser.add_argument(
        "--role",
        default="external_doc_authority_registry",
        help="Public-safe material role. Defaults to external_doc_authority_registry.",
    )
    doc_registry_authority_parser.add_argument(
        "--freshness",
        default="current",
        help="Public-safe freshness state. Defaults to current.",
    )
    doc_registry_authority_parser.add_argument("--owner-status", help="Optional public-safe owner/review status.")
    doc_registry_authority_parser.add_argument("--gate-status", help="Optional public-safe gate status.")
    doc_registry_authority_parser.add_argument(
        "--boundary",
        choices=sorted(AUTHORITY_SOURCE_BOUNDARIES),
        default="private_redacted",
        help="Public/private boundary for this source. Defaults to private_redacted.",
    )
    doc_registry_authority_parser.add_argument("--revision", help="Optional public-safe revision label.")
    doc_registry_authority_parser.add_argument("--conflict-rule", help="Optional public-safe conflict rule.")
    doc_registry_authority_parser.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Additional local topic_authority key to map to this source id. Repeatable.",
    )
    doc_registry_authority_parser.add_argument(
        "--import-topic-prefix",
        help="Prefix imported DOC_REGISTRY topic keys with this value before mapping them to the source id.",
    )
    doc_registry_authority_parser.add_argument(
        "--max-imported-topics",
        type=int,
        default=50,
        help="Maximum DOC_REGISTRY topics to map when --import-topic-prefix is set. Defaults to 50.",
    )
    doc_registry_authority_parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    doc_registry_authority_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the local source registry.",
    )

    check_parser = sub.add_parser("check", help="Run a read-only contract and public/private boundary check.")
    check_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    check_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    check_parser.add_argument("--limit", type=int, default=5)

    status_parser = sub.add_parser("status", help="Show a first-screen goal status and attention queue.")
    add_subcommand_format(status_parser)
    status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    status_parser.add_argument("--limit", type=int, default=5)

    review_packet_parser = sub.add_parser(
        "review-packet",
        help="Generate a CLI-visible Review Packet from the current status contract.",
    )
    review_packet_parser.add_argument("--goal-id", required=True, help="Goal id to package for review or handoff.")
    review_packet_parser.add_argument(
        "--action-kind",
        choices=["reward", "controller", "codex", "evidence", "health"],
        help="Override inferred action kind. Defaults to the goal's current attention item.",
    )
    review_packet_parser.add_argument("--review-url", help="Optional dashboard review URL to include in the packet.")
    review_packet_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    review_packet_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    review_packet_parser.add_argument(
        "--handoff-only",
        action="store_true",
        help="Print only the target project-agent handoff in markdown output; JSON output returns a minimized handoff payload.",
    )
    review_packet_parser.add_argument(
        "--format",
        dest="review_packet_format",
        choices=["markdown", "json"],
        help="Output format for review-packet. This mirrors the global --format flag and may appear after the subcommand.",
    )
    review_packet_parser.add_argument("--limit", type=int, default=5)

    todo_parser = sub.add_parser(
        "todo",
        help="Add a user or agent todo to a goal's active state.",
    )
    todo_parser.add_argument(
        "todo_command",
        nargs="?",
        choices=["add"],
        default="add",
        help="Use add to append a checkbox todo to the active state.",
    )
    todo_parser.add_argument("--goal-id", required=True, help="Goal id whose active state should receive the todo.")
    todo_parser.add_argument("--role", required=True, choices=["user", "agent"], help="Todo owner.")
    todo_parser.add_argument("--text", required=True, help="Todo text. Keep it short and public-safe enough for local status.")
    todo_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    todo_parser.add_argument("--state-file", help="Active goal state path. Defaults to the registry goal state_file.")
    todo_parser.add_argument("--dry-run", action="store_true", help="Preview the active-state edit without writing.")

    quota_parser = sub.add_parser(
        "quota",
        help="Show agent-facing compute quota status or next-turn plan.",
    )
    quota_parser.add_argument(
        "quota_command",
        nargs="?",
        choices=["status", "plan", "should-run", "spend-slot"],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, or spend-slot for a slot accounting preview/write.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for `quota should-run` and `quota spend-slot`.")
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument("--source", choices=["heartbeat", "controller", "adapter"], default="heartbeat", help="Source label for `quota spend-slot`.")
    quota_parser.add_argument("--dry-run", action="store_true", help="Keep `quota spend-slot` as preview-only. This is the default.")
    quota_parser.add_argument("--execute", action="store_true", help="Append the compact quota_slot_spent runtime event for `quota spend-slot`.")
    quota_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    quota_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    quota_parser.add_argument("--limit", type=int, default=5)

    serve_status_parser = sub.add_parser("serve-status", help="Serve live status JSON for the local dashboard.")
    serve_status_parser.add_argument("--host", default=DEFAULT_STATUS_HOST, help="Bind host. Defaults to localhost only.")
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status JSON route.")
    serve_status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    serve_status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    serve_status_parser.add_argument("--limit", type=int, default=5)
    serve_status_parser.add_argument(
        "--enable-reward-write-api",
        action="store_true",
        help="Enable POST /reward/append on loopback only so the dashboard can append human_reward overlays.",
    )
    serve_status_parser.add_argument(
        "--enable-control-plane-write-api",
        action="store_true",
        help="Enable POST /control-plane/configure-goal/apply on loopback only so the dashboard can write registry settings.",
    )
    serve_status_parser.add_argument(
        "--global-registry",
        action="store_true",
        help="Serve the shared global registry view even when invoked from a project directory.",
    )
    serve_status_parser.add_argument("--verbose", action="store_true", help="Print HTTP request logs.")

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {"bootstrap", "connect", "demo", "doctor", "new-project-prompt", "heartbeat-prompt", "sync-global"}
        and not user_supplied_registry(argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    if args.command in {"bootstrap", "connect"}:
        try:
            runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            state_file = Path(args.state_file).expanduser() if args.state_file else None
            goal_doc = Path(args.goal_doc).expanduser() if args.goal_doc else None
            payload = bootstrap_project(
                project=Path(args.project),
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                objective=args.objective,
                domain=args.domain,
                role=args.role,
                parent_goal_id=args.parent_goal_id,
                state_file=state_file,
                goal_doc=goal_doc,
                adapter_kind=args.adapter_kind,
                adapter_status=args.adapter_status,
                next_probe=args.next_probe,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                write_scope=args.write_scope,
                claim_ttl_minutes=args.claim_ttl_minutes,
                execution_minimum_scale=args.execution_minimum_scale,
                execution_must_include=args.execution_must_include or None,
                execution_small_streak_threshold=args.execution_small_streak_threshold,
                execution_outcome_markers=args.execution_outcome_marker or None,
                execution_surface_only_hints=args.execution_surface_only_hint or None,
                execution_surface_streak_threshold=args.execution_surface_streak_threshold,
                execution_outcome_must_advance=args.execution_outcome_must_advance or None,
                force=args.force,
                dry_run=args.dry_run,
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_bootstrap_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "new-project-prompt":
        payload = build_new_project_prompt(
            project=Path(args.project),
            goal_doc=Path(args.goal_doc),
            goal_id=args.goal_id,
            objective=args.objective,
            domain=args.domain,
            adapter_kind=args.adapter_kind,
            adapter_status=args.adapter_status,
            next_probe=args.next_probe,
            spawn_allowed=bool(args.spawn_allowed),
            allowed_domains=args.allowed_domain,
            write_scope=args.write_scope,
        )
        print_payload(payload, args.format, render_new_project_prompt_markdown)
        return 0

    if args.command == "heartbeat-prompt":
        try:
            active_state, resolved_active_state, active_state_source = resolve_heartbeat_active_state(
                goal_id=args.goal_id,
                active_state_arg=args.active_state,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
            )
            payload = build_heartbeat_prompt(
                goal_id=args.goal_id,
                active_state=active_state,
                active_state_source=active_state_source,
                resolved_active_state=resolved_active_state,
                material_queue_rule=args.material_rule,
                permission_rule=args.permission_rule,
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "goal_id": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, output_format(args), render_heartbeat_prompt_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "demo":
        try:
            payload = run_demo(
                project=Path(args.project).expanduser(),
                runtime_root=Path(args.runtime_root).expanduser() if args.runtime_root else None,
                goal_id=args.goal_id,
                objective=args.objective,
                user_todo=args.user_todo,
                agent_todo=args.agent_todo,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "project": args.project,
                "goal_id": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_demo_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "doctor":
        payload = collect_doctor()
        print_payload(payload, args.format, render_doctor_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "promotion-gate":
        try:
            payload = build_promotion_gate(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "gate": "promotion_readiness",
                "gate_state": "error",
                "can_promote": False,
                "should_warn": True,
                "non_blocking": True,
                "error": str(exc),
                "recommended_action": "fix promotion readiness gate collection before promotion",
            }
        print_payload(payload, output_format(args), render_promotion_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "upgrade-plan":
        try:
            payload = build_upgrade_plan(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                installed_manifest=Path(args.installed_manifest).expanduser() if args.installed_manifest else None,
                cli_bin=args.cli_bin,
                modes=args.mode or None,
                goal_ids=args.goal_id or None,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "mode": "upgrade-plan",
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "summary": {
                    "managed_goal_count": 0,
                    "current_prompt_count": 0,
                    "stale_prompt_count": 0,
                    "unknown_prompt_count": 0,
                    "not_installed_prompt_count": 0,
                    "stage_deferred_goal_count": 0,
                    "ready_for_default_promotion": False,
                    "installed_manifest_available": False,
                    "installed_manifest_source": None,
                    "installed_manifest_entry_count": 0,
                    "installed_manifest_task_body_count": 0,
                    "installed_manifest_has_task_body": False,
                },
                "recommended_action": "fix upgrade-plan collection before default promotion",
            }
        print_payload(payload, output_format(args), render_upgrade_plan_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry":
        payload = inspect_registry(registry_path)
        print_payload(payload, args.format, render_registry_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "configure-goal":
        try:
            payload = configure_goal(
                registry_path=registry_path,
                goal_id=args.goal_id,
                quota_compute=args.quota_compute,
                quota_window_hours=args.quota_window_hours,
                self_repair_enabled=args.self_repair_enabled,
                self_repair_health=args.self_repair_health,
                self_repair_waiting_projection=args.self_repair_waiting_projection,
                orchestration_mode=args.orchestration_mode,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                clear_allowed_domains=bool(args.clear_allowed_domains),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "registry": str(registry_path),
                "goal_id": args.goal_id,
                "changed": False,
                "written": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_configure_goal_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "history":
        if args.history_action == "append-benchmark-run":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-run accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-run requires --goal-id")
                if not args.benchmark_run_json:
                    raise ValueError("history append-benchmark-run requires --benchmark-run-json")

                if args.benchmark_run_json == "-":
                    benchmark_run_input = json.loads(sys.stdin.read())
                else:
                    benchmark_run_input = json.loads(Path(args.benchmark_run_json).expanduser().read_text(encoding="utf-8"))
                if not isinstance(benchmark_run_input, dict):
                    raise ValueError("--benchmark-run-json must contain a JSON object")
                benchmark_run = compact_benchmark_run(benchmark_run_input)
                if not benchmark_run:
                    raise ValueError("--benchmark-run-json did not contain a compactable benchmark_run_v0 object")

                dry_run = not bool(args.execute)
                payload = append_benchmark_run(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_run=benchmark_run,
                    classification=args.classification or "benchmark_run_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_run_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_run_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-result":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-result accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-result requires --goal-id")
                if not args.benchmark_result_json:
                    raise ValueError("history append-benchmark-result requires --benchmark-result-json")

                if args.benchmark_result_json == "-":
                    benchmark_result_input = json.loads(sys.stdin.read())
                else:
                    benchmark_result_input = json.loads(Path(args.benchmark_result_json).expanduser().read_text(encoding="utf-8"))
                if not isinstance(benchmark_result_input, dict):
                    raise ValueError("--benchmark-result-json must contain a JSON object")
                benchmark_result = compact_benchmark_result(benchmark_result_input)
                if not benchmark_result:
                    raise ValueError("--benchmark-result-json did not contain a compactable benchmark_result_v0 object")

                dry_run = not bool(args.execute)
                payload = append_benchmark_result(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_result=benchmark_result,
                    classification=args.classification or "benchmark_result_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_result_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_result_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-comparison":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-comparison accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-comparison requires --goal-id")
                if not args.benchmark_comparison_json:
                    raise ValueError("history append-benchmark-comparison requires --benchmark-comparison-json")

                if args.benchmark_comparison_json == "-":
                    benchmark_comparison_input = json.loads(sys.stdin.read())
                else:
                    benchmark_comparison_input = json.loads(
                        Path(args.benchmark_comparison_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(benchmark_comparison_input, dict):
                    raise ValueError("--benchmark-comparison-json must contain a JSON object")
                benchmark_comparison = compact_benchmark_comparison(benchmark_comparison_input)
                if not benchmark_comparison:
                    raise ValueError(
                        "--benchmark-comparison-json did not contain a compactable benchmark_comparison_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_comparison(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_comparison=benchmark_comparison,
                    classification=args.classification or "benchmark_comparison_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_comparison_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_comparison_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-report":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-report accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-report requires --goal-id")
                if not args.benchmark_report_json:
                    raise ValueError("history append-benchmark-report requires --benchmark-report-json")

                if args.benchmark_report_json == "-":
                    benchmark_report_input = json.loads(sys.stdin.read())
                else:
                    benchmark_report_input = json.loads(
                        Path(args.benchmark_report_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(benchmark_report_input, dict):
                    raise ValueError("--benchmark-report-json must contain a JSON object")
                benchmark_report = compact_benchmark_experiment_report(benchmark_report_input)
                if not benchmark_report:
                    raise ValueError(
                        "--benchmark-report-json did not contain a compactable benchmark_experiment_report_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_experiment_report(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_experiment_report=benchmark_report,
                    classification=args.classification or "benchmark_experiment_report_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_experiment_report_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_experiment_report_append_markdown)
            return 0 if payload.get("ok") else 1

        try:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = collect_history(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_history_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "archive-runtime":
        try:
            payload = archive_runtime_goal(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                archive_root=Path(args.archive_root).expanduser() if args.archive_root else None,
                allow_registered=bool(args.allow_registered),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "dry_run": not bool(args.execute),
                "archived": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_archive_runtime_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "sync-global":
        try:
            payload = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": str(runtime_root),
                "global_registry": str(global_registry_path(runtime_root)),
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_global_sync_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "refresh-state":
        try:
            payload = refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                classification=args.classification,
                recommended_action=args.recommended_action,
                delivery_batch_scale=args.delivery_batch_scale,
                delivery_outcome=args.delivery_outcome,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "classification": args.classification,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_state_refresh_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "read-only-map":
        try:
            payload = read_only_project_map_run(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                classification=args.classification,
                recommended_action=args.recommended_action,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "classification": args.classification,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_read_only_project_map_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "reward":
        try:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
            )
            payload = append_human_reward(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                run_generated_at=args.run_generated_at,
                reward=reward,
                dry_run=bool(args.dry_run),
                state_file_override=Path(args.state_file).expanduser() if args.state_file else None,
                write_active_state_summary=bool(args.write_active_state_summary),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_reward_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "operator-gate":
        try:
            payload = record_operator_gate(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                gate=args.gate,
                decision=args.decision,
                operator_question=args.operator_question,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
                agent_command=args.agent_command,
                recommended_action=args.recommended_action,
                recorded_at=args.recorded_at,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_operator_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "register-authority-source":
        try:
            payload = register_authority_source(
                registry_path=registry_path,
                goal_id=args.goal_id,
                source_id=args.source_id,
                source_ref=args.source_ref,
                source_kind=args.source_kind,
                role=args.role,
                freshness=args.freshness,
                owner_status=args.owner_status,
                gate_status=args.gate_status,
                boundary=args.boundary,
                revision=args.revision,
                conflict_rule=args.conflict_rule,
                topic=args.topic,
                dry_run=bool(args.dry_run),
            )
            if not bool(args.no_global_sync):
                if args.dry_run:
                    payload["global_sync"] = {"enabled": True, "dry_run": True, "wrote": False}
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=False,
                    )
            else:
                payload["global_sync"] = {"enabled": False}
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "source_id": getattr(args, "source_id", None),
                "written": False,
                "dry_run": bool(getattr(args, "dry_run", False)),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_authority_source_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "import-doc-registry-authority":
        try:
            payload = import_doc_registry_authority(
                registry_path=registry_path,
                goal_id=args.goal_id,
                source_id=args.source_id,
                doc_registry_path=Path(args.doc_registry_path),
                source_kind=args.source_kind,
                role=args.role,
                freshness=args.freshness,
                owner_status=args.owner_status,
                gate_status=args.gate_status,
                boundary=args.boundary,
                revision=args.revision,
                conflict_rule=args.conflict_rule,
                topics=list(args.topic or []),
                import_topic_prefix=args.import_topic_prefix,
                max_imported_topics=int(args.max_imported_topics),
                dry_run=bool(args.dry_run),
            )
            if not bool(args.no_global_sync):
                if args.dry_run:
                    payload["global_sync"] = {"enabled": True, "dry_run": True, "wrote": False}
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=False,
                    )
            else:
                payload["global_sync"] = {"enabled": False}
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "source_id": getattr(args, "source_id", None),
                "written": False,
                "dry_run": bool(getattr(args, "dry_run", False)),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_doc_registry_authority_import_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "check":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = check_contract(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                allow_missing_registry=not user_supplied_registry(argv),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "scan_roots": args.scan_path or [args.scan_root],
                "summary": {"errors": 1, "warnings": 0, "checks": 0},
                "errors": [str(exc)],
                "warnings": [],
                "checks": [],
            }
        print_payload(payload, args.format, render_contract_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "status":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "attention_queue": {
                    "available": False,
                    "item_count": 1,
                    "needs_user_or_controller": 0,
                    "needs_codex": 1,
                    "watching_external_evidence": 0,
                    "items": [
                        {
                            "goal_id": "goal-harness-status",
                            "status": "status_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "status",
                        }
                    ],
                },
            }
        print_payload(payload, output_format(args), render_status_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "review-packet":
        selected_format = output_format(args, "review_packet_format")
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
            payload = build_review_packet(
                status_payload,
                goal_id=args.goal_id,
                action_kind=args.action_kind,
                review_url=args.review_url,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "goal_id": args.goal_id,
                "error": str(exc),
            }
        if args.handoff_only:
            payload = review_packet_handoff_only_payload(payload)
        if args.handoff_only and selected_format != "json" and payload.get("ok"):
            print(str(payload.get("handoff_text") or ""))
        else:
            print_payload(payload, selected_format, render_review_packet_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "todo":
        try:
            if args.todo_command != "add":
                raise ValueError("only `goal-harness todo add` is supported")
            payload = add_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                text=args.text,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": bool(args.dry_run),
                "added": False,
                "already_exists": False,
                "goal_id": args.goal_id,
                "role": args.role,
                "todo": args.text,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_todo_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "quota":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
            if args.quota_command == "should-run":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota should-run` requires --goal-id")
                payload = build_quota_should_run(status_payload, goal_id=args.goal_id)
            elif args.quota_command == "spend-slot":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota spend-slot` requires --goal-id")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota spend-slot` accepts only one of --dry-run or --execute")
                payload = spend_quota_slot(
                    status_payload,
                    goal_id=args.goal_id,
                    slots=args.slots,
                    execute=bool(args.execute),
                    source=args.source,
                )
            else:
                payload = build_quota_plan(status_payload, mode=args.quota_command)
        except Exception as exc:
            if args.quota_command in {"should-run", "spend-slot"}:
                payload = {
                    "ok": False,
                    "mode": args.quota_command,
                    "goal_id": args.goal_id,
                    "decision": "skip",
                    "should_run": False,
                    "reason": str(exc),
                    "state": "blocked_health",
                    "waiting_on": "codex",
                    "status": "quota_collection_failed",
                    "source": "quota",
                    "recommended_action": "fix quota/status collection before spending automatic compute",
                }
            else:
                payload = {
                    "ok": False,
                    "mode": args.quota_command,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "error": str(exc),
                    "summary": {
                        "registered_goals": 0,
                        "health_blockers": 1,
                        "next_automatic_turn": None,
                        "states": {},
                    },
                    "groups": {},
                    "health_items": [
                        {
                            "goal_id": "goal-harness-quota",
                            "status": "quota_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "quota",
                        }
                    ],
                }
        renderer = (
            render_quota_should_run_markdown
            if args.quota_command == "should-run"
            else render_quota_slot_preview_markdown
            if args.quota_command == "spend-slot"
            else render_quota_markdown
        )
        print_payload(payload, args.format, renderer)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            status_registry_path = explicit_global_registry(args.runtime_root) if args.global_registry else registry_path
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            serve_status(
                registry_path=status_registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                status_path=args.path,
                enable_reward_write_api=bool(args.enable_reward_write_api),
                enable_control_plane_write_api=bool(args.enable_control_plane_write_api),
                verbose=bool(args.verbose),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(status_registry_path if "status_registry_path" in locals() else registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
