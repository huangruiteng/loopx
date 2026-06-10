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
from .benchmark import (
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_DEFAULT_TASK,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE,
    TERMINAL_BENCH_MODES,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_harbor_result_benchmark_run,
    collect_terminal_bench_goal_harness_cli_bridge_trace,
    terminal_bench_recommended_action,
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
    append_active_user_assisted_pilot,
    append_benchmark_comparison,
    append_benchmark_experiment_report,
    append_benchmark_result,
    append_benchmark_run,
    collect_history,
    load_registry,
    render_active_user_assisted_pilot_append_markdown,
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
    void_quota_slot,
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
    compact_active_user_assisted_pilot,
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
from .worker_bridge import (
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    DEFAULT_WORKER_BRIDGE_MODULE,
    DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
    DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
    build_active_user_intervention,
    build_active_user_intervention_channel_contract,
    build_worker_bridge_benchmark_run,
    build_worker_bridge_install_contract,
    build_worker_bridge_outcome,
    observe_active_user_intervention_feed,
    render_worker_bridge_install_contract_markdown,
    write_active_user_observation_file,
)


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

    worker_bridge_parser = sub.add_parser(
        "worker-bridge",
        help="Render runner-agnostic worker bridge/install contracts.",
    )
    worker_bridge_sub = worker_bridge_parser.add_subparsers(dest="worker_bridge_command")
    worker_bridge_contract_parser = worker_bridge_sub.add_parser(
        "contract",
        help="Render a Goal Harness worker bridge/install contract.",
    )
    add_subcommand_format(worker_bridge_contract_parser)
    worker_bridge_contract_parser.add_argument(
        "--project-root",
        default=GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness project root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--runtime-root",
        dest="worker_bridge_runtime_root",
        default=GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness runtime root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    worker_bridge_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="Goal Harness CLI module import path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--scan-path",
        help="Container-visible public scan path. Defaults to the Goal Harness benchmark module.",
    )
    worker_bridge_contract_parser.add_argument(
        "--benchmark-run-json",
        default=DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
        help="Worker-visible benchmark_run_v0 JSON write path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--counter-trace-json",
        default=DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
        help="Worker-visible compact counter trace JSONL path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--classification",
        default="<classification>",
        help="Classification label for worker-side compact writeback.",
    )
    worker_bridge_outcome_parser = worker_bridge_sub.add_parser(
        "outcome",
        help="Render compact worker bridge evidence and runner-return outcome.",
    )
    add_subcommand_format(worker_bridge_outcome_parser)
    worker_bridge_outcome_parser.add_argument(
        "--worker-cli-call-total",
        type=int,
        default=0,
        help="Compact count of in-worker Goal Harness CLI calls.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--required-worker-cli-call-total-min",
        type=int,
        default=1,
        help="Minimum worker CLI call count required to claim bridge verification.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--counter-trace-present",
        action="store_true",
        help="Whether a compact worker counter trace was observed.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--runner-return-completed",
        action="store_true",
        help="Whether the runner returned a completed case result.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--official-score-completed",
        action="store_true",
        help="Whether an official task score is available.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--official-score-value",
        type=float,
        help="Official task score value when --official-score-completed is set.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--interrupted",
        action="store_true",
        help="Whether the controller interrupted the worker run.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--interrupt-reason",
        default="",
        help="Public-safe interrupt reason label.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--wall-time-seconds",
        type=float,
        help="Observed wall time in seconds, if available.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--wall-time-limit-seconds",
        type=float,
        default=DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
        help="Controller wall-time limit for this worker bridge outcome.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--side-effect-audit-failed",
        action="store_true",
        help="Mark the side-effect audit as failed.",
    )
    worker_bridge_benchmark_run_parser = worker_bridge_sub.add_parser(
        "benchmark-run",
        help="Render a worker-side benchmark_run_v0 writeback payload.",
    )
    add_subcommand_format(worker_bridge_benchmark_run_parser)
    worker_bridge_benchmark_run_parser.add_argument(
        "--source-runner",
        default="worker_bridge_runner",
        help="Public-safe runner label for the worker-side benchmark_run_v0 payload.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--benchmark-id",
        default="worker-bridge-sample@v0",
        help="Public-safe benchmark id.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--job-name",
        default="goal_harness_worker_bridge_sample",
        help="Public-safe job name.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--mode",
        dest="worker_bridge_benchmark_mode",
        default="codex_goal_harness_active_worker",
        help="Benchmark treatment mode.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--worker-mode",
        default="codex_goal_harness_cli",
        help="Worker mode label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--task-id",
        default="worker-bridge-sample",
        help="Public-safe task id.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--trial-name",
        default="worker-bridge-sample-worker",
        help="Public-safe trial name.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-kind",
        help="Official score kind label. Defaults to a blocker or sample-success label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--worker-cli-call-total",
        type=int,
        default=0,
        help="Compact count of in-worker Goal Harness CLI calls.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--required-worker-cli-call-total-min",
        type=int,
        default=1,
        help="Minimum worker CLI call count required to claim bridge verification.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--counter-trace-present",
        action="store_true",
        help="Whether a compact worker counter trace was observed.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--runner-return-completed",
        action="store_true",
        help="Whether the runner returned a completed case result.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-completed",
        action="store_true",
        help="Whether an official task score is available.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-value",
        type=float,
        help="Official task score value when --official-score-completed is set.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--interrupted",
        action="store_true",
        help="Whether the controller interrupted the worker run.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--interrupt-reason",
        default="",
        help="Public-safe interrupt reason label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--wall-time-seconds",
        type=float,
        help="Observed wall time in seconds, if available.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--wall-time-limit-seconds",
        type=float,
        default=DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
        help="Controller wall-time limit for this worker bridge outcome.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--side-effect-audit-failed",
        action="store_true",
        help="Mark the side-effect audit as failed.",
    )
    active_user_contract_parser = worker_bridge_sub.add_parser(
        "active-user-contract",
        help="Render the active-user simulator external-update channel contract.",
    )
    add_subcommand_format(active_user_contract_parser)
    active_user_contract_parser.add_argument(
        "--project-root",
        default=GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness project root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--runtime-root",
        dest="active_user_runtime_root",
        default=GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness runtime root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    active_user_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="Goal Harness CLI module import path.",
    )
    active_user_contract_parser.add_argument(
        "--feed-jsonl",
        default=DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        help="Worker-visible active-user intervention feed JSONL path.",
    )
    active_user_contract_parser.add_argument(
        "--observation-json",
        default=DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
        help="Worker-visible active-user observation JSON path.",
    )
    active_user_contract_parser.add_argument(
        "--min-interval-seconds",
        type=int,
        default=300,
        help="Minimum interval between proactive simulator interventions.",
    )
    active_user_contract_parser.add_argument(
        "--max-interventions-per-task",
        type=int,
        default=3,
        help="Maximum proactive simulator interventions per task.",
    )
    active_user_intervention_parser = worker_bridge_sub.add_parser(
        "active-user-intervention",
        help="Render one public-safe active-user simulator intervention event.",
    )
    add_subcommand_format(active_user_intervention_parser)
    active_user_intervention_parser.add_argument("--seq", type=int, required=True)
    active_user_intervention_parser.add_argument("--message", required=True)
    active_user_intervention_parser.add_argument(
        "--trigger",
        default="public_progress_or_stall_signal",
        help="Public-safe intervention trigger label.",
    )
    active_user_intervention_parser.add_argument(
        "--channel",
        default="simulator_proactive_user_message",
        help="Public-safe intervention channel label.",
    )
    active_user_intervention_parser.add_argument(
        "--before-worker-start",
        action="store_true",
        help="Mark this intervention as created before the worker start marker.",
    )
    active_user_observe_parser = worker_bridge_sub.add_parser(
        "active-user-observe",
        help="Observe active-user interventions created after the worker start marker.",
    )
    add_subcommand_format(active_user_observe_parser)
    active_user_observe_parser.add_argument(
        "--feed-jsonl",
        required=True,
        help="Active-user intervention feed JSONL path to read.",
    )
    active_user_observe_parser.add_argument(
        "--worker-start-seq",
        type=int,
        default=0,
        help="Worker start marker sequence; only later interventions are observable.",
    )
    active_user_observe_parser.add_argument(
        "--observation-json",
        help="Optional path to write the compact observation JSON.",
    )

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
            "append-active-user-assisted-pilot",
        ],
        help="Append a compact benchmark_run_v0, benchmark_result_v0, benchmark_comparison_v0, benchmark_experiment_report_v0, or active_user_assisted_pilot_v0 event.",
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
    history_parser.add_argument(
        "--active-user-pilot-json",
        help="Path to an active_user_assisted_pilot_v0 JSON object. Use '-' to read stdin.",
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

    benchmark_parser = sub.add_parser(
        "benchmark",
        help="Benchmark runner skeletons. Current public surface is fixture-only and no-run by default.",
    )
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run_parser = benchmark_sub.add_parser(
        "run",
        help="Build or append a compact benchmark_run_v0 fixture or ingest a Harbor job result.",
    )
    benchmark_run_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench has a public fixture skeleton.",
    )
    benchmark_run_parser.add_argument("--goal-id", required=True, help="Goal id for dry-run/append context.")
    benchmark_run_parser.add_argument(
        "--mode",
        choices=TERMINAL_BENCH_MODES,
        default="goal-harness-managed-codex",
        help="Terminal-Bench worker mode. Defaults to the managed Goal Harness treatment.",
    )
    benchmark_run_parser.add_argument("--dataset", default=TERMINAL_BENCH_DEFAULT_DATASET)
    benchmark_run_parser.add_argument("--include-task-name", default=TERMINAL_BENCH_DEFAULT_TASK)
    benchmark_run_parser.add_argument("--runner", choices=["harbor"], default="harbor")
    benchmark_run_parser.add_argument("--agent", choices=["codex"], default="codex")
    benchmark_run_parser.add_argument("--model", default=TERMINAL_BENCH_DEFAULT_MODEL)
    benchmark_run_parser.add_argument(
        "--timeout-multiplier",
        type=float,
        help="Preview Harbor --timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--agent-timeout-multiplier",
        type=float,
        help="Preview Harbor --agent-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--verifier-timeout-multiplier",
        type=float,
        help="Preview Harbor --verifier-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--agent-setup-timeout-multiplier",
        type=float,
        help="Preview Harbor --agent-setup-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--environment-build-timeout-multiplier",
        type=float,
        help="Preview Harbor --environment-build-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--harbor-job-dir",
        help=(
            "Ingest an existing Harbor job directory into a compact benchmark_run_v0. "
            "This reads runner artifacts and worker counter files only; it does not run "
            "Harbor, Terminal-Bench, Codex, Docker, model APIs, or upload."
        ),
    )
    benchmark_run_parser.add_argument(
        "--fake-worker",
        action="store_true",
        help="Use the deterministic fake managed-worker event path. No real Codex is invoked.",
    )
    benchmark_run_parser.add_argument(
        "--preflight-guard",
        action="store_true",
        help=(
            "Build a managed real-run preflight guard event. This may probe local CLI surfaces "
            "but does not run Harbor, Terminal-Bench, Codex workers, task containers, or uploads."
        ),
    )
    benchmark_run_parser.add_argument(
        "--cli-bridge-contract",
        action="store_true",
        help=(
            "Execute the host-agent Goal Harness CLI bridge contract fixture for "
            "codex-goal-harness. This runs Goal Harness CLI read commands and an "
            "append-benchmark-run dry-run only; no Harbor, Terminal-Bench, Codex "
            "worker, model API, or upload is invoked."
        ),
    )
    benchmark_run_parser.add_argument(
        "--worker-cli-bridge-fixture",
        action="store_true",
        help=(
            "Build the codex-goal-harness worker in-case CLI bridge fixture. "
            "This records worker-side Goal Harness call counters separately "
            "from runner bridge calls and does not run Harbor, Terminal-Bench, "
            "Codex workers, model APIs, or uploads."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-cli-bridge",
        action="store_true",
        help=(
            "With codex-goal-harness --preflight-guard, build the private no-upload "
            "repeat preflight that enables the worker Goal Harness CLI bridge and "
            "requires worker-side CLI call counters before any in-case use claim."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-user-assisted-treatment",
        action="store_true",
        help=(
            "With codex-goal-harness --preflight-guard --active-cli-bridge, build "
            "the active-user assisted treatment preflight contract. This does not "
            "run Harbor, Codex, a simulator, or inject user messages."
        ),
    )
    benchmark_run_parser.add_argument("--classification")
    benchmark_run_parser.add_argument("--recommended-action")
    benchmark_run_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    benchmark_run_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    benchmark_run_parser.add_argument("--dry-run", action="store_true", help="Preview append without writing. This is the default.")
    benchmark_run_parser.add_argument("--execute", action="store_true", help="Append the compact fixture event.")
    benchmark_run_parser.add_argument("--no-global-sync", action="store_true", help="Skip global registry sync after append.")

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
        choices=["status", "plan", "should-run", "spend-slot", "void-slot"],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, spend-slot for accounting, or void-slot for a non-destructive accounting correction.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for `quota should-run`, `quota spend-slot`, and `quota void-slot`.")
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument("--source", choices=["heartbeat", "controller", "adapter"], default="heartbeat", help="Source label for `quota spend-slot`.")
    quota_parser.add_argument("--void-generated-at", help="generated_at timestamp of the quota_slot_spent run to void.")
    quota_parser.add_argument("--reason-summary", help="Public-safe reason for `quota void-slot`.")
    quota_parser.add_argument("--dry-run", action="store_true", help="Keep quota accounting writes as preview-only. This is the default.")
    quota_parser.add_argument("--execute", action="store_true", help="Append the compact quota accounting runtime event for spend-slot or void-slot.")
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

    if args.command == "worker-bridge":
        if args.worker_bridge_command not in (
            "contract",
            "outcome",
            "benchmark-run",
            "active-user-contract",
            "active-user-intervention",
            "active-user-observe",
        ):
            payload = {
                "ok": False,
                "mode": "worker-bridge",
                "error": (
                    "worker-bridge requires a subcommand; use `contract`, "
                    "`outcome`, `benchmark-run`, `active-user-contract`, "
                    "`active-user-intervention`, or `active-user-observe`."
                ),
            }
            print_payload(payload, args.format, render_worker_bridge_install_contract_markdown)
            return 1
        try:
            if args.worker_bridge_command == "contract":
                payload = build_worker_bridge_install_contract(
                    project_root=args.project_root,
                    runtime_root=args.worker_bridge_runtime_root,
                    python_bin=args.python_bin,
                    module=args.module,
                    scan_path=args.scan_path,
                    benchmark_run_json=args.benchmark_run_json,
                    counter_trace_json=args.counter_trace_json,
                    classification=args.classification,
                )
            elif args.worker_bridge_command == "outcome":
                payload = build_worker_bridge_outcome(
                    worker_goal_harness_cli_call_total=args.worker_cli_call_total,
                    counter_trace_present=bool(args.counter_trace_present),
                    runner_return_completed=bool(args.runner_return_completed),
                    official_score_completed=bool(args.official_score_completed),
                    official_score_value=args.official_score_value,
                    interrupted=bool(args.interrupted),
                    interrupt_reason=args.interrupt_reason,
                    wall_time_seconds=args.wall_time_seconds,
                    wall_time_limit_seconds=args.wall_time_limit_seconds,
                    required_worker_goal_harness_cli_call_total_min=(
                        args.required_worker_cli_call_total_min
                    ),
                    side_effect_audit_passed=not bool(args.side_effect_audit_failed),
                )
            elif args.worker_bridge_command == "benchmark-run":
                payload = build_worker_bridge_benchmark_run(
                    source_runner=args.source_runner,
                    benchmark_id=args.benchmark_id,
                    job_name=args.job_name,
                    mode=args.worker_bridge_benchmark_mode,
                    worker_mode=args.worker_mode,
                    task_id=args.task_id,
                    trial_name=args.trial_name,
                    official_score_kind=args.official_score_kind,
                    worker_goal_harness_cli_call_total=args.worker_cli_call_total,
                    counter_trace_present=bool(args.counter_trace_present),
                    runner_return_completed=bool(args.runner_return_completed),
                    official_score_completed=bool(args.official_score_completed),
                    official_score_value=args.official_score_value,
                    interrupted=bool(args.interrupted),
                    interrupt_reason=args.interrupt_reason,
                    wall_time_seconds=args.wall_time_seconds,
                    wall_time_limit_seconds=args.wall_time_limit_seconds,
                    required_worker_goal_harness_cli_call_total_min=(
                        args.required_worker_cli_call_total_min
                    ),
                    side_effect_audit_passed=not bool(args.side_effect_audit_failed),
                )
            elif args.worker_bridge_command == "active-user-contract":
                payload = build_active_user_intervention_channel_contract(
                    project_root=args.project_root,
                    runtime_root=args.active_user_runtime_root,
                    python_bin=args.python_bin,
                    module=args.module,
                    feed_jsonl=args.feed_jsonl,
                    observation_json=args.observation_json,
                    min_interval_seconds=args.min_interval_seconds,
                    max_interventions_per_task=args.max_interventions_per_task,
                )
            elif args.worker_bridge_command == "active-user-intervention":
                payload = build_active_user_intervention(
                    seq=args.seq,
                    message=args.message,
                    trigger=args.trigger,
                    channel=args.channel,
                    created_after_worker_start=not bool(args.before_worker_start),
                )
            else:
                payload = observe_active_user_intervention_feed(
                    args.feed_jsonl,
                    worker_start_seq=args.worker_start_seq,
                )
                if args.observation_json:
                    payload["observation_written"] = write_active_user_observation_file(
                        args.observation_json,
                        payload,
                    )
        except Exception as exc:
            payload = {
                "ok": False,
                "mode": "worker-bridge",
                "error": str(exc),
            }
        print_payload(payload, output_format(args), render_worker_bridge_install_contract_markdown)
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

    if args.command == "benchmark":
        if args.benchmark_command == "run":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("benchmark run accepts either --dry-run or --execute, not both")
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                classification = args.classification or (
                    "terminal_bench_harbor_runner_result_ingest_v0"
                    if args.harbor_job_dir
                    else
                    "terminal_bench_active_user_assisted_treatment_preflight_v0"
                    if args.active_user_assisted_treatment
                    else
                    "terminal_bench_codex_goal_harness_active_cli_bridge_preflight_v0"
                    if args.active_cli_bridge
                    else
                    "terminal_bench_codex_goal_harness_worker_cli_bridge_fixture_v0"
                    if args.worker_cli_bridge_fixture
                    else
                    "terminal_bench_codex_goal_harness_cli_bridge_contract_runner_fixture_v0"
                    if args.cli_bridge_contract
                    else (
                        (
                            "terminal_bench_codex_goal_harness_preflight_guard_v0"
                            if args.mode == "codex-goal-harness"
                            else (
                                TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE
                                + "_v0"
                            )
                            if args.mode == "hardened-codex"
                            else "terminal_bench_managed_real_run_preflight_guard_v0"
                        )
                        if args.preflight_guard
                        else (
                            (
                                "terminal_bench_codex_goal_harness_fake_worker_v0"
                                if args.mode == "codex-goal-harness"
                                else "terminal_bench_cli_fake_worker_v0"
                            )
                            if args.fake_worker
                            else (
                                "terminal_bench_codex_goal_harness_dry_run_v0"
                                if args.mode == "codex-goal-harness"
                                else "terminal_bench_cli_dry_run_v0"
                            )
                        )
                    )
                )
                if args.harbor_job_dir and (
                    args.fake_worker
                    or args.preflight_guard
                    or args.cli_bridge_contract
                    or args.worker_cli_bridge_fixture
                    or args.active_cli_bridge
                    or args.active_user_assisted_treatment
                ):
                    raise ValueError(
                        "--harbor-job-dir cannot be combined with fixture or preflight flags"
                    )
                timeout_multiplier_preview_requested = any(
                    value is not None
                    for value in (
                        args.timeout_multiplier,
                        args.agent_timeout_multiplier,
                        args.verifier_timeout_multiplier,
                        args.agent_setup_timeout_multiplier,
                        args.environment_build_timeout_multiplier,
                    )
                )
                timeout_multiplier_preview_defaulted = (
                    args.active_cli_bridge and args.agent_timeout_multiplier is None
                )
                if args.harbor_job_dir and timeout_multiplier_preview_requested:
                    raise ValueError(
                        "--harbor-job-dir reads timeout policy from Harbor artifacts; "
                        "do not pass preview timeout multiplier flags"
                    )
                cli_bridge_trace = None
                if args.cli_bridge_contract:
                    runtime_root = resolve_runtime_root(
                        load_registry(registry_path),
                        args.runtime_root,
                    )
                    cli_bridge_trace = collect_terminal_bench_goal_harness_cli_bridge_trace(
                        goal_id=args.goal_id,
                        registry=str(registry_path),
                        runtime_root=str(runtime_root),
                        command_prefix=[sys.executable, "-m", "goal_harness.cli"],
                        scan_path="goal_harness/benchmark.py",
                        classification=classification,
                    )
                if args.harbor_job_dir:
                    benchmark_run_input = build_terminal_bench_harbor_result_benchmark_run(
                        args.harbor_job_dir,
                    )
                else:
                    benchmark_run_input = build_terminal_bench_benchmark_run(
                        mode=args.mode,
                        dataset=args.dataset,
                        task_id=args.include_task_name,
                        runner=args.runner,
                        agent=args.agent,
                        model=args.model,
                        fake_worker=bool(args.fake_worker),
                        preflight_guard=bool(args.preflight_guard),
                        cli_bridge_contract=bool(args.cli_bridge_contract),
                        cli_bridge_trace=cli_bridge_trace,
                        worker_cli_bridge_fixture=bool(args.worker_cli_bridge_fixture),
                        active_cli_bridge_preflight=bool(args.active_cli_bridge),
                        active_user_assisted_treatment_preflight=bool(
                            args.active_user_assisted_treatment
                        ),
                        timeout_multiplier=args.timeout_multiplier,
                        agent_timeout_multiplier=args.agent_timeout_multiplier,
                        verifier_timeout_multiplier=args.verifier_timeout_multiplier,
                        agent_setup_timeout_multiplier=args.agent_setup_timeout_multiplier,
                        environment_build_timeout_multiplier=args.environment_build_timeout_multiplier,
                    )
                benchmark_run = compact_benchmark_run(benchmark_run_input)
                if not benchmark_run:
                    raise ValueError("terminal-bench benchmark command did not produce a compactable benchmark_run_v0")
                benchmark_cli_mode = (
                    str(benchmark_run.get("mode") or args.mode)
                    if args.harbor_job_dir
                    else args.mode
                )
                benchmark_cli_mode_source = (
                    "harbor_job_result" if args.harbor_job_dir else "cli_arg"
                )

                dry_run = not bool(args.execute)
                payload = append_benchmark_run(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_run=benchmark_run,
                    classification=classification,
                    recommended_action=args.recommended_action
                    or (
                        "inspect runner-side Terminal-Bench result and refine worker closure/writeback"
                        if args.harbor_job_dir
                        else terminal_bench_recommended_action(
                        mode=args.mode,
                        fake_worker=bool(args.fake_worker),
                        preflight_guard=bool(args.preflight_guard),
                        cli_bridge_contract=bool(args.cli_bridge_contract),
                        worker_cli_bridge_fixture=bool(args.worker_cli_bridge_fixture),
                        active_cli_bridge_preflight=bool(args.active_cli_bridge),
                        active_user_assisted_treatment_preflight=bool(
                            args.active_user_assisted_treatment
                        ),
                        )
                    ),
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                payload["benchmark_cli"] = {
                    "benchmark": args.benchmark_name,
                    "mode": benchmark_cli_mode,
                    "requested_mode": args.mode,
                    "mode_source": benchmark_cli_mode_source,
                    "fake_worker": bool(args.fake_worker),
                    "preflight_guard": bool(args.preflight_guard),
                    "cli_bridge_contract": bool(args.cli_bridge_contract),
                    "worker_cli_bridge_fixture": bool(args.worker_cli_bridge_fixture),
                    "active_cli_bridge": bool(args.active_cli_bridge),
                    "active_user_assisted_treatment": bool(
                        args.active_user_assisted_treatment
                    ),
                    "harbor_job_result_ingested": bool(args.harbor_job_dir),
                    "timeout_multiplier_preview_requested": (
                        timeout_multiplier_preview_requested
                        or timeout_multiplier_preview_defaulted
                    ),
                    "timeout_multiplier_preview_defaulted": timeout_multiplier_preview_defaulted,
                    "cli_bridge_trace_observed": bool(
                        isinstance(cli_bridge_trace, dict)
                        and cli_bridge_trace.get("bridge_available") is True
                    ),
                    "real_runner_invoked": False,
                    "real_codex_invoked": False,
                    "auth_values_read": False,
                    "submit_eligible": False,
                }
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
                    "classification": args.classification
                    or (
                        "terminal_bench_active_user_assisted_treatment_preflight_v0"
                        if getattr(args, "active_user_assisted_treatment", False)
                        else
                        "terminal_bench_codex_goal_harness_worker_cli_bridge_fixture_v0"
                        if getattr(args, "worker_cli_bridge_fixture", False)
                        else
                        "terminal_bench_codex_goal_harness_cli_bridge_contract_runner_fixture_v0"
                        if getattr(args, "cli_bridge_contract", False)
                        else "terminal_bench_managed_real_run_preflight_guard_v0"
                        if getattr(args, "preflight_guard", False)
                        else "terminal_bench_cli_dry_run_v0"
                    ),
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_run_append_markdown)
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

        if args.history_action == "append-active-user-assisted-pilot":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "history append-active-user-assisted-pilot accepts either --dry-run or --execute, not both"
                    )
                if not args.goal_id:
                    raise ValueError("history append-active-user-assisted-pilot requires --goal-id")
                if not args.active_user_pilot_json:
                    raise ValueError(
                        "history append-active-user-assisted-pilot requires --active-user-pilot-json"
                    )

                if args.active_user_pilot_json == "-":
                    active_user_pilot_input = json.loads(sys.stdin.read())
                else:
                    active_user_pilot_input = json.loads(
                        Path(args.active_user_pilot_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(active_user_pilot_input, dict):
                    raise ValueError("--active-user-pilot-json must contain a JSON object")
                active_user_pilot = compact_active_user_assisted_pilot(active_user_pilot_input)
                if not active_user_pilot:
                    raise ValueError(
                        "--active-user-pilot-json did not contain a compactable active_user_assisted_pilot_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_active_user_assisted_pilot(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    active_user_assisted_pilot=active_user_pilot,
                    classification=args.classification or "active_user_assisted_pilot_v0",
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
                    "classification": args.classification or "active_user_assisted_pilot_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_active_user_assisted_pilot_append_markdown)
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
            elif args.quota_command == "void-slot":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota void-slot` requires --goal-id")
                if not args.void_generated_at:
                    raise ValueError("`goal-harness quota void-slot` requires --void-generated-at")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota void-slot` accepts only one of --dry-run or --execute")
                payload = void_quota_slot(
                    status_payload,
                    goal_id=args.goal_id,
                    voided_run_generated_at=args.void_generated_at,
                    execute=bool(args.execute),
                    source=args.source,
                    reason_summary=args.reason_summary,
                )
            else:
                payload = build_quota_plan(status_payload, mode=args.quota_command)
        except Exception as exc:
            if args.quota_command in {"should-run", "spend-slot", "void-slot"}:
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
            if args.quota_command in {"spend-slot", "void-slot"}
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
