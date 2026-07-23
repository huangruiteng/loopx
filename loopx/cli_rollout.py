from __future__ import annotations

from pathlib import Path

from .history import load_registry
from .paths import resolve_runtime_root
from .rollout_event_log import (
    append_rollout_event,
    append_rollout_event_once,
    build_rollout_event,
    rollout_event_log_path,
)


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
    idempotency_fields: list[str] | None = None,
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
        log_path = rollout_event_log_path(runtime_root, goal_id)
        if idempotency_fields:
            appended, newly_appended = append_rollout_event_once(
                log_path,
                event,
                identity_fields=idempotency_fields,
            )
        else:
            appended = append_rollout_event(log_path, event)
            newly_appended = True
        rollout_event_view = {
            "schema_version": appended["schema_version"],
            "event_id": appended["event_id"],
            "event_kind": appended["event_kind"],
            "recorded_at": appended["recorded_at"],
            "status": appended.get("status"),
        }
        if idempotency_fields:
            rollout_event_view["appended"] = newly_appended
        payload["rollout_event"] = rollout_event_view
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
