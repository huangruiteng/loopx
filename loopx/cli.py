from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from .benchmark_core import (
    build_split_control_remote_executor_readiness,
)
from .cli_commands import (
    handle_agents_last_exam_command,
    handle_agentissue_runner_flow_command,
    handle_benchmark_review_lifecycle_command,
    handle_benchmark_run_ledger_command,
    handle_benchmark_boundary_command,
    handle_check_command,
    handle_codex_cli_bounded_visible_pilot_adapter_command,
    handle_codex_cli_bootstrap_message_command,
    handle_codex_cli_exec_handoff_command,
    handle_codex_cli_visible_first_response_capture_plan_command,
    handle_codex_cli_local_driver_plan_command,
    handle_codex_cli_local_scheduler_exec_command,
    handle_codex_cli_local_scheduler_tick_command,
    handle_codex_cli_one_message_loop_pilot_command,
    handle_codex_cli_runtime_idle_detector_command,
    handle_codex_cli_session_probe_command,
    handle_codex_cli_tui_bootstrap_smoke_bundle_command,
    handle_codex_cli_visible_attach_acceptance_command,
    handle_codex_cli_visible_local_driver_pilot_command,
    handle_codex_cli_visible_driver_run_command,
    handle_codex_cli_visible_driver_plan_command,
    handle_codex_cli_visible_session_proof_command,
    handle_diagnose_command,
    handle_demo_command,
    handle_doctor_command,
    handle_dreaming_command,
    handle_history_command,
    handle_ml_experiment_command,
    handle_new_project_prompt_command,
    handle_project_lifecycle_command,
    handle_quota_command,
    handle_registry_admin_command,
    handle_review_packet_command,
    handle_status_command,
    handle_support_control_command,
    handle_todo_command,
    handle_terminal_bench_adapter_command,
    handle_terminal_bench_environment_result_command,
    handle_worker_bridge_command,
    register_agents_last_exam_commands,
    register_agentissue_runner_flow_commands,
    register_benchmark_review_lifecycle_commands,
    register_benchmark_run_ledger_commands,
    register_benchmark_boundary_commands,
    register_doctor_command,
    register_dreaming_commands,
    register_history_command,
    register_ml_experiment_commands,
    register_project_lifecycle_commands,
    register_quota_command,
    register_registry_admin_commands,
    register_starter_commands,
    register_status_commands,
    register_support_control_commands,
    register_todo_command,
    register_terminal_bench_adapter_commands,
    register_terminal_bench_environment_result_commands,
    register_worker_bridge_commands,
)
from .execution_profile import DEFAULT_EXECUTION_PROFILE
from .history import load_registry
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path, resolve_runtime_root
from .rollout_event_log import (
    append_rollout_event,
    build_rollout_event,
    rollout_event_log_path,
)

def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def build_version_payload() -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "loopx_version_v0",
        "name": "loopx",
        "version": __version__,
    }


def render_version_markdown(payload: dict[str, object]) -> str:
    return f"{payload.get('name')} {payload.get('version')}\n"


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


def user_supplied_registry(argv: list[str] | None) -> bool:
    values = sys.argv[1:] if argv is None else argv
    return any(value == "--registry" or value.startswith("--registry=") for value in values)


def append_cli_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    event_kind: str,
    agent_id: str | None = None,
    todo_id: str | None = None,
    benchmark_id: str | None = None,
    case_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    labels: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    details: dict[str, object] | None = None,
    allow_failed: bool = False,
) -> dict[str, object]:
    """Append a compact rollout event for core CLI lifecycle commands.

    Rollout logging is intentionally best-effort so the diagnostic log cannot
    turn a successful state transition into a failed CLI command. Failures are
    surfaced in the command payload as compact metadata.
    """

    if not payload.get("ok") and not allow_failed:
        return payload
    goal_id = str(payload.get("goal_id") or "").strip()
    if not goal_id:
        return payload
    try:
        runtime_root_value = payload.get("runtime_root")
        if runtime_root_value:
            runtime_root = Path(str(runtime_root_value)).expanduser()
        else:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, runtime_root_arg)
        event = build_rollout_event(
            goal_id=goal_id,
            event_kind=event_kind,
            agent_id=agent_id or str(payload.get("agent_id") or "").strip() or None,
            todo_id=todo_id or str(payload.get("todo_id") or "").strip() or None,
            benchmark_id=benchmark_id,
            case_id=case_id,
            run_id=run_id,
            status=status,
            classification=str(payload.get("classification") or "").strip() or None,
            delivery_outcome=str(payload.get("delivery_outcome") or "").strip() or None,
            labels=labels,
            summary=summary,
            artifact_refs=artifact_refs,
            details=details,
        )
        appended = append_rollout_event(rollout_event_log_path(runtime_root, goal_id), event)
        payload["rollout_event"] = {
            "schema_version": appended["schema_version"],
            "event_id": appended["event_id"],
            "event_kind": appended["event_kind"],
            "recorded_at": appended["recorded_at"],
            "status": appended.get("status"),
        }
    except Exception as exc:
        payload["rollout_event_log_error"] = {
            "recorded": False,
            "error_type": type(exc).__name__,
            "message": "rollout event append failed; primary command payload remains authoritative",
        }
    return payload


def _compact_benchmark_rollout_label(value: object, *, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _first_benchmark_trial_value(
    benchmark_record: dict[str, object],
    key: str,
) -> object | None:
    trials = benchmark_record.get("trials")
    if not isinstance(trials, list):
        return None
    for trial in trials:
        if isinstance(trial, dict) and trial.get(key) is not None:
            return trial.get(key)
    return None


def _benchmark_rollout_case_id(benchmark_record: dict[str, object]) -> str | None:
    return _compact_benchmark_rollout_label(
        benchmark_record.get("case_id")
        or benchmark_record.get("task_id")
        or _first_benchmark_trial_value(benchmark_record, "task_id")
        or benchmark_record.get("scenario_id")
    )


def _benchmark_official_score_summary(
    benchmark_record: dict[str, object],
) -> tuple[object | None, object | None, str | None]:
    official = benchmark_record.get("official_task_score")
    if isinstance(official, dict):
        return (
            official.get("value"),
            official.get("passed"),
            _compact_benchmark_rollout_label(
                official.get("status") or official.get("kind")
            ),
        )
    return (
        benchmark_record.get("official_score"),
        benchmark_record.get("official_score_passed"),
        _compact_benchmark_rollout_label(benchmark_record.get("official_score_status")),
    )


def _benchmark_rollout_status(benchmark_record: dict[str, object]) -> str:
    failure_attribution = _compact_benchmark_rollout_label(
        benchmark_record.get("score_failure_attribution")
        or benchmark_record.get("failure_attribution")
    )
    score, passed, score_status = _benchmark_official_score_summary(benchmark_record)
    if failure_attribution and failure_attribution not in {
        "none",
        "no_score_failure",
    }:
        return "precise_blocker"
    if passed is True:
        return "passed"
    if passed is False:
        return "failed"
    if score_status == "not_run":
        return "not_run"
    runner_status = _compact_benchmark_rollout_label(
        benchmark_record.get("runner_return_status")
        or benchmark_record.get("terminal_state")
    )
    if runner_status:
        return runner_status
    if score is not None:
        return "scored"
    return "appended"


def _benchmark_rollout_event_kind(benchmark_record: dict[str, object]) -> str:
    return (
        "compact_blocker"
        if _benchmark_rollout_status(benchmark_record) == "precise_blocker"
        else "compact_case_result"
    )


def _benchmark_rollout_labels(benchmark_record: dict[str, object]) -> list[str]:
    labels: list[str] = []
    for value in (
        benchmark_record.get("mode"),
        benchmark_record.get("source_runner"),
        benchmark_record.get("runner_return_status"),
        benchmark_record.get("official_score_status"),
        benchmark_record.get("score_failure_attribution"),
        benchmark_record.get("failure_attribution"),
    ):
        label = _compact_benchmark_rollout_label(value, limit=80)
        if label and label not in labels:
            labels.append(label)
    return labels


def _benchmark_rollout_details(
    benchmark_record: dict[str, object],
    *,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    score, passed, score_status = _benchmark_official_score_summary(benchmark_record)
    progress = (
        benchmark_record.get("progress")
        if isinstance(benchmark_record.get("progress"), dict)
        else {}
    )
    trials = benchmark_record.get("trials")
    return {
        "command": command,
        "action": action or "",
        "mode": benchmark_record.get("mode") or "",
        "source_runner": benchmark_record.get("source_runner") or "",
        "runner_status": benchmark_record.get("runner_return_status") or "",
        "score_status": score_status or "",
        "official_score": score if isinstance(score, (int, float)) else "",
        "official_passed": passed if isinstance(passed, bool) else "",
        "failure_attribution": benchmark_record.get("score_failure_attribution")
        or benchmark_record.get("failure_attribution")
        or "",
        "trial_count": len(trials) if isinstance(trials, list) else "",
        "progress_completed": progress.get("n_completed_trials") or "",
        "progress_total": progress.get("n_total_trials") or "",
    }


def append_benchmark_run_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    benchmark_run = (
        payload.get("benchmark_run")
        if isinstance(payload.get("benchmark_run"), dict)
        else {}
    )
    if not benchmark_run or payload.get("dry_run") or not payload.get("appended"):
        return payload
    benchmark_id = _compact_benchmark_rollout_label(benchmark_run.get("benchmark_id"))
    case_id = _benchmark_rollout_case_id(benchmark_run)
    status = _benchmark_rollout_status(benchmark_run)
    return append_cli_rollout_event(
        payload,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        event_kind=_benchmark_rollout_event_kind(benchmark_run),
        benchmark_id=benchmark_id,
        case_id=case_id,
        run_id=_compact_benchmark_rollout_label(payload.get("generated_at")),
        status=status,
        summary=(
            "benchmark_run compact lifecycle event recorded: "
            f"benchmark={benchmark_id or 'unknown'} "
            f"case={case_id or 'unknown'} status={status}"
        ),
        labels=_benchmark_rollout_labels(benchmark_run),
        details=_benchmark_rollout_details(
            benchmark_run,
            command=command,
            action=action,
        ),
    )


def append_benchmark_result_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    benchmark_result = (
        payload.get("benchmark_result")
        if isinstance(payload.get("benchmark_result"), dict)
        else {}
    )
    if not benchmark_result or payload.get("dry_run") or not payload.get("appended"):
        return payload
    benchmark_id = _compact_benchmark_rollout_label(
        benchmark_result.get("benchmark_id") or "benchmark_result"
    )
    case_id = _benchmark_rollout_case_id(benchmark_result)
    status = _benchmark_rollout_status(benchmark_result)
    return append_cli_rollout_event(
        payload,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        event_kind=_benchmark_rollout_event_kind(benchmark_result),
        benchmark_id=benchmark_id,
        case_id=case_id,
        run_id=_compact_benchmark_rollout_label(payload.get("generated_at")),
        status=status,
        summary=(
            "benchmark_result compact lifecycle event recorded: "
            f"benchmark={benchmark_id or 'unknown'} "
            f"case={case_id or 'unknown'} status={status}"
        ),
        labels=_benchmark_rollout_labels(benchmark_result),
        details=_benchmark_rollout_details(
            benchmark_result,
            command=command,
            action=action,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoopX control-plane helper.")
    parser.add_argument("--version", action="version", version=f"loopx {__version__}")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the installed LoopX version.")

    bootstrap_parser = sub.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument(
        "--fork-goal",
        help="Create a new forked goal id instead of reusing an existing global goal route.",
    )
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
    bootstrap_parser.add_argument(
        "--no-onboarding-scan",
        action="store_true",
        help="Skip the fast first-connect repository scan and todo candidate proposal.",
    )
    bootstrap_parser.add_argument(
        "--accept-onboarding-agent-todos",
        action="store_true",
        help="Write all proposed onboarding agent todos into the initial active state.",
    )
    bootstrap_parser.add_argument(
        "--begin-autonomous-advance",
        action="store_true",
        help="Record that Codex may begin from accepted onboarding agent todos after the quota guard permits work.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-commits",
        type=int,
        default=5,
        help="Maximum recent commits sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-status-paths",
        type=int,
        default=12,
        help="Maximum git status lines sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-top-level-files",
        type=int,
        default=24,
        help="Maximum top-level names sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument(
        "--replace-state",
        action="store_true",
        help=(
            "Allow replacing an existing global route for the same goal id. "
            "Writes a global registry backup before changing the route."
        ),
    )
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    bootstrap_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not merge this project registry into the shared global registry.",
    )

    register_starter_commands(sub)

    register_doctor_command(sub)

    register_worker_bridge_commands(sub, add_subcommand_format)

    register_support_control_commands(sub, add_subcommand_format)

    register_ml_experiment_commands(sub, add_subcommand_format)

    register_registry_admin_commands(sub)

    register_history_command(sub)

    benchmark_parser = sub.add_parser(
        "benchmark",
        help="Benchmark runner skeletons. Current public surface is fixture-only and no-run by default.",
    )
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    register_benchmark_run_ledger_commands(benchmark_sub, add_subcommand_format)

    register_agentissue_runner_flow_commands(benchmark_sub, add_subcommand_format)
    register_benchmark_boundary_commands(benchmark_sub, add_subcommand_format)
    register_terminal_bench_adapter_commands(benchmark_sub, add_subcommand_format)

    register_agents_last_exam_commands(benchmark_sub, add_subcommand_format)

    register_benchmark_review_lifecycle_commands(benchmark_sub, add_subcommand_format)
    register_terminal_bench_environment_result_commands(benchmark_sub, add_subcommand_format)

    register_project_lifecycle_commands(sub, add_subcommand_format)

    register_status_commands(sub, add_subcommand_format)
    register_dreaming_commands(sub, add_subcommand_format)
    register_todo_command(sub)
    register_quota_command(sub)

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {
            "bootstrap",
            "connect",
            "codex-cli-bootstrap-message",
            "codex-cli-bounded-visible-pilot-adapter",
            "codex-cli-exec-handoff",
            "codex-cli-visible-first-response-capture-plan",
            "codex-cli-local-driver-plan",
            "codex-cli-local-scheduler-exec",
            "codex-cli-local-scheduler-tick",
            "codex-cli-one-message-loop-pilot",
            "codex-cli-runtime-idle-detector",
            "codex-cli-session-probe",
            "codex-cli-visible-attach-acceptance",
            "codex-cli-visible-local-driver-pilot",
            "codex-cli-visible-driver-run",
            "codex-cli-visible-driver-plan",
            "codex-cli-visible-session-proof",
            "demo",
            "doctor",
            "new-project-prompt",
            "heartbeat-prompt",
            "sync-global",
            "version",
        }
        and not user_supplied_registry(argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    if args.command == "version":
        print_payload(build_version_payload(), args.format, render_version_markdown)
        return 0

    if args.command in {"bootstrap", "connect"}:
        try:
            runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            state_file = Path(args.state_file).expanduser() if args.state_file else None
            goal_doc = Path(args.goal_doc).expanduser() if args.goal_doc else None
            if args.fork_goal and args.goal_id and args.fork_goal != args.goal_id:
                raise ValueError("--fork-goal cannot be combined with a different --goal-id")
            goal_id = args.fork_goal or args.goal_id
            payload = bootstrap_project(
                project=Path(args.project),
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=goal_id,
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
                onboarding_scan_enabled=not bool(args.no_onboarding_scan),
                accept_onboarding_agent_todos=bool(args.accept_onboarding_agent_todos),
                begin_autonomous_advance=bool(args.begin_autonomous_advance),
                onboarding_max_commits=args.onboarding_max_commits,
                onboarding_max_status_paths=args.onboarding_max_status_paths,
                onboarding_max_top_level_files=args.onboarding_max_top_level_files,
                force=args.force,
                dry_run=args.dry_run,
                sync_global=not bool(args.no_global_sync),
                allow_global_route_replacement=bool(args.replace_state),
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
        return handle_new_project_prompt_command(args, print_payload)

    if args.command == "codex-cli-bootstrap-message":
        return handle_codex_cli_bootstrap_message_command(args, print_payload)

    if args.command == "codex-cli-tui-bootstrap-smoke-bundle":
        return handle_codex_cli_tui_bootstrap_smoke_bundle_command(args, print_payload)

    if args.command == "codex-cli-one-message-loop-pilot":
        return handle_codex_cli_one_message_loop_pilot_command(args, print_payload)

    if args.command == "codex-cli-visible-local-driver-pilot":
        return handle_codex_cli_visible_local_driver_pilot_command(args, print_payload)

    if args.command == "codex-cli-bounded-visible-pilot-adapter":
        return handle_codex_cli_bounded_visible_pilot_adapter_command(args, print_payload)

    if args.command == "codex-cli-visible-first-response-capture-plan":
        return handle_codex_cli_visible_first_response_capture_plan_command(args, print_payload)

    if args.command == "codex-cli-visible-attach-acceptance":
        return handle_codex_cli_visible_attach_acceptance_command(args, print_payload)

    if args.command == "codex-cli-exec-handoff":
        return handle_codex_cli_exec_handoff_command(args, print_payload)

    if args.command == "codex-cli-session-probe":
        return handle_codex_cli_session_probe_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-plan":
        return handle_codex_cli_visible_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-local-driver-plan":
        return handle_codex_cli_local_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-run":
        return handle_codex_cli_visible_driver_run_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-tick":
        return handle_codex_cli_local_scheduler_tick_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-exec":
        return handle_codex_cli_local_scheduler_exec_command(args, print_payload)

    if args.command == "codex-cli-visible-session-proof":
        return handle_codex_cli_visible_session_proof_command(args, print_payload)

    if args.command == "codex-cli-runtime-idle-detector":
        return handle_codex_cli_runtime_idle_detector_command(args, print_payload)

    if args.command == "demo":
        return handle_demo_command(args, print_payload)

    if args.command == "doctor":
        return handle_doctor_command(args, print_payload)

    worker_bridge_result = handle_worker_bridge_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if worker_bridge_result is not None:
        return worker_bridge_result

    support_control_result = handle_support_control_command(
        args,
        registry_path=registry_path,
        registry_was_supplied=user_supplied_registry(argv),
        print_payload=print_payload,
        output_format=output_format,
    )
    if support_control_result is not None:
        return support_control_result

    if args.command == "ml-experiment":
        return handle_ml_experiment_command(args, output_format=output_format, print_payload=print_payload)

    registry_admin_result = handle_registry_admin_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
    if registry_admin_result is not None:
        return registry_admin_result

    if args.command == "benchmark":
        agentissue_runner_flow_result = handle_agentissue_runner_flow_command(
            args,
            registry_path=registry_path,
            print_payload=print_payload,
        )
        if agentissue_runner_flow_result is not None:
            return agentissue_runner_flow_result
        benchmark_boundary_result = handle_benchmark_boundary_command(
            args,
            print_payload=print_payload,
            output_format=output_format,
        )
        if benchmark_boundary_result is not None:
            return benchmark_boundary_result
        terminal_bench_adapter_result = handle_terminal_bench_adapter_command(
            args,
            print_payload=print_payload,
            output_format=output_format,
        )
        if terminal_bench_adapter_result is not None:
            return terminal_bench_adapter_result
        agents_last_exam_result = handle_agents_last_exam_command(
            args,
            print_payload=print_payload,
            output_format=output_format,
        )
        if agents_last_exam_result is not None:
            return agents_last_exam_result
        benchmark_review_lifecycle_result = handle_benchmark_review_lifecycle_command(
            args,
            registry_path=registry_path,
            print_payload=print_payload,
            output_format=output_format,
        )
        if benchmark_review_lifecycle_result is not None:
            return benchmark_review_lifecycle_result
        terminal_bench_environment_result = handle_terminal_bench_environment_result_command(
            args,
            print_payload=print_payload,
            output_format=output_format,
        )
        if terminal_bench_environment_result is not None:
            return terminal_bench_environment_result
        benchmark_run_ledger_result = handle_benchmark_run_ledger_command(
            args,
            registry_path=registry_path,
            print_payload=print_payload,
            output_format=output_format,
            append_benchmark_run_rollout_event=append_benchmark_run_rollout_event,
        )
        if benchmark_run_ledger_result is not None:
            return benchmark_run_ledger_result
    if args.command == "history":
        return handle_history_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_benchmark_run_rollout_event=append_benchmark_run_rollout_event,
            append_benchmark_result_rollout_event=append_benchmark_result_rollout_event,
        )

    project_lifecycle_result = handle_project_lifecycle_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
        append_cli_rollout_event=append_cli_rollout_event,
    )
    if project_lifecycle_result is not None:
        return project_lifecycle_result

    if args.command == "check":
        return handle_check_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            allow_missing_registry=not user_supplied_registry(argv),
            print_payload=print_payload,
        )

    if args.command == "status":
        return handle_status_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "diagnose":
        return handle_diagnose_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "review-packet":
        return handle_review_packet_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "dreaming":
        return handle_dreaming_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "todo":
        return handle_todo_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_cli_rollout_event=append_cli_rollout_event,
        )

    if args.command == "quota":
        return handle_quota_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_cli_rollout_event=append_cli_rollout_event,
        )

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
