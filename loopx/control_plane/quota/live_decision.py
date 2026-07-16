from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...quota import build_quota_should_run
from ..scheduler.execution_context import (
    SchedulerExecutionContextResolution,
    resolve_scheduler_execution_context,
)


HostObservationResolver = Callable[..., Mapping[str, Any]]


def bind_scheduler_followup_cli_routes(
    payload: dict[str, Any],
    *,
    registry_path: Path,
    runtime_root: Path,
    source: str = "quota_cli_invocation",
) -> None:
    """Bind scheduler follow-ups to the registry/runtime that built the hint."""

    scheduler_hint = payload.get("scheduler_hint")
    if not isinstance(scheduler_hint, dict):
        return
    codex_app = scheduler_hint.get("codex_app")
    if not isinstance(codex_app, dict):
        return
    for hint_name in ("ack_hint", "failure_hint"):
        followup_hint = codex_app.get(hint_name)
        if not isinstance(followup_hint, dict):
            continue
        cli_args = followup_hint.get("cli_args")
        if not isinstance(cli_args, list) or not cli_args or cli_args[0] == "--registry":
            continue
        followup_hint["cli_args"] = [
            "--registry",
            str(registry_path.expanduser().resolve()),
            "--runtime-root",
            str(runtime_root.expanduser().resolve()),
            *cli_args,
        ]
        followup_hint["route_binding"] = {
            "schema_version": (
                "scheduler_ack_cli_route_v0"
                if hint_name == "ack_hint"
                else "scheduler_failure_cli_route_v0"
            ),
            "source": source,
            "registry_bound": True,
            "runtime_root_bound": True,
        }


def build_live_quota_should_run_decision(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
    available_capabilities: list[str] | None,
    include_scheduler_detail: bool,
    codex_app_current_rrule: str | None,
    registry_path: Path,
    runtime_root: Path,
    host_observation_resolver: HostObservationResolver | None = None,
    route_source: str = "quota_cli_invocation",
    scheduler_execution_context: Mapping[str, Any] | SchedulerExecutionContextResolution | None = None,
) -> dict[str, Any]:
    """Build one live CLI decision while keeping host observation injectable."""

    resolved_context = resolve_scheduler_execution_context(scheduler_execution_context)
    codex_app_applicable = (
        resolved_context.ok
        and resolved_context.context is not None
        and resolved_context.context.codex_app_applicable
    )
    observed_rrule = str(codex_app_current_rrule or "").strip()
    if (
        codex_app_applicable
        and not observed_rrule
        and host_observation_resolver is not None
    ):
        observation = host_observation_resolver(goal_id=goal_id, agent_id=agent_id)
        if observation.get("available") is True:
            observed_rrule = str(observation.get("rrule") or "")
    payload = build_quota_should_run(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
        available_capabilities=available_capabilities,
        include_scheduler_detail=include_scheduler_detail,
        codex_app_current_rrule=observed_rrule,
        scheduler_execution_context=resolved_context,
    )
    bind_scheduler_followup_cli_routes(
        payload,
        registry_path=registry_path,
        runtime_root=runtime_root,
        source=route_source,
    )
    return payload
