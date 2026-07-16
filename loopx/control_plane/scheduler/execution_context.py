from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


SCHEDULER_EXECUTION_CONTEXT_SCHEMA_VERSION = "scheduler_execution_context_v0"


class HostSurface(str, Enum):
    CODEX_APP = "codex_app"
    CODEX_CLI = "codex_cli"
    GENERIC_CLI = "generic_cli"
    CLAUDE_CODE = "claude_code"
    LOCAL_SCHEDULER = "local_scheduler"


class SchedulerOwner(str, Enum):
    HOST_AUTOMATION = "host_automation"
    AGENT_CLI_LOOP = "agent_cli_loop"
    OUTER_CONTROLLER = "outer_controller"
    NONE = "none"


class ExecutionMode(str, Enum):
    INTERACTIVE = "interactive"
    ISOLATED_HEADLESS = "isolated_headless"
    HOSTED_AUTOMATION = "hosted_automation"


@dataclass(frozen=True)
class SchedulerExecutionContext:
    host_surface: HostSurface
    scheduler_owner: SchedulerOwner
    execution_mode: ExecutionMode
    source: str

    @property
    def codex_app_applicable(self) -> bool:
        return (
            self.host_surface is HostSurface.CODEX_APP
            and self.scheduler_owner is SchedulerOwner.HOST_AUTOMATION
            and self.execution_mode is ExecutionMode.HOSTED_AUTOMATION
        )

    def projection(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEDULER_EXECUTION_CONTEXT_SCHEMA_VERSION,
            "host_surface": self.host_surface.value,
            "scheduler_owner": self.scheduler_owner.value,
            "execution_mode": self.execution_mode.value,
            "source": self.source,
            "valid": True,
            "codex_app_applicability": (
                "applicable" if self.codex_app_applicable else "not_applicable"
            ),
        }


@dataclass(frozen=True)
class SchedulerExecutionContextResolution:
    context: SchedulerExecutionContext | None
    errors: tuple[str, ...] = ()
    supplied: Mapping[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.context is not None and not self.errors

    def projection(self) -> dict[str, Any]:
        if self.context is not None:
            return self.context.projection()
        supplied = dict(self.supplied or {})
        return {
            "schema_version": SCHEDULER_EXECUTION_CONTEXT_SCHEMA_VERSION,
            "host_surface": supplied.get("host_surface"),
            "scheduler_owner": supplied.get("scheduler_owner"),
            "execution_mode": supplied.get("execution_mode"),
            "source": supplied.get("source") or "explicit",
            "valid": False,
            "codex_app_applicability": "blocked_invalid_context",
            "errors": list(self.errors),
        }


def _validation_errors(context: SchedulerExecutionContext) -> list[str]:
    errors: list[str] = []
    cli_surfaces = {
        HostSurface.CODEX_CLI,
        HostSurface.GENERIC_CLI,
        HostSurface.CLAUDE_CODE,
    }
    if context.host_surface is HostSurface.CODEX_APP:
        if context.scheduler_owner is not SchedulerOwner.HOST_AUTOMATION:
            errors.append("codex_app requires scheduler_owner=host_automation")
        if context.execution_mode is not ExecutionMode.HOSTED_AUTOMATION:
            errors.append("codex_app requires execution_mode=hosted_automation")
    if context.host_surface is HostSurface.LOCAL_SCHEDULER:
        if context.scheduler_owner is not SchedulerOwner.HOST_AUTOMATION:
            errors.append("local_scheduler requires scheduler_owner=host_automation")
        if context.execution_mode is not ExecutionMode.HOSTED_AUTOMATION:
            errors.append("local_scheduler requires execution_mode=hosted_automation")
    if (
        context.host_surface in cli_surfaces
        and context.scheduler_owner is SchedulerOwner.HOST_AUTOMATION
    ):
        errors.append("CLI host surfaces cannot be owned by host_automation")
    if context.scheduler_owner is SchedulerOwner.OUTER_CONTROLLER:
        if context.host_surface not in cli_surfaces:
            errors.append("outer_controller requires a CLI host surface")
        if context.execution_mode is not ExecutionMode.ISOLATED_HEADLESS:
            errors.append("outer_controller requires execution_mode=isolated_headless")
    if context.scheduler_owner is SchedulerOwner.NONE:
        if context.host_surface not in cli_surfaces:
            errors.append("scheduler_owner=none requires a CLI host surface")
        if context.execution_mode is not ExecutionMode.INTERACTIVE:
            errors.append("scheduler_owner=none requires execution_mode=interactive")
    if context.scheduler_owner is SchedulerOwner.AGENT_CLI_LOOP:
        if context.host_surface not in cli_surfaces:
            errors.append("agent_cli_loop requires a CLI host surface")
        if context.execution_mode is ExecutionMode.HOSTED_AUTOMATION:
            errors.append("agent_cli_loop cannot use execution_mode=hosted_automation")
    if (
        context.execution_mode is ExecutionMode.HOSTED_AUTOMATION
        and context.scheduler_owner is not SchedulerOwner.HOST_AUTOMATION
    ):
        errors.append("hosted_automation requires scheduler_owner=host_automation")
    return errors


def resolve_scheduler_execution_context(
    value: Mapping[str, Any] | SchedulerExecutionContextResolution | None,
) -> SchedulerExecutionContextResolution:
    if isinstance(value, SchedulerExecutionContextResolution):
        return value
    if value is None:
        context = SchedulerExecutionContext(
            host_surface=HostSurface.CODEX_APP,
            scheduler_owner=SchedulerOwner.HOST_AUTOMATION,
            execution_mode=ExecutionMode.HOSTED_AUTOMATION,
            source="compatibility_default",
        )
        return SchedulerExecutionContextResolution(context=context)

    supplied = dict(value)
    missing = [
        field
        for field in ("host_surface", "scheduler_owner", "execution_mode")
        if not str(supplied.get(field) or "").strip()
    ]
    errors = [f"missing required field: {field}" for field in missing]
    try:
        host_surface = HostSurface(str(supplied.get("host_surface") or ""))
    except ValueError:
        host_surface = None
        if "host_surface" not in missing:
            errors.append("unsupported host_surface")
    try:
        scheduler_owner = SchedulerOwner(str(supplied.get("scheduler_owner") or ""))
    except ValueError:
        scheduler_owner = None
        if "scheduler_owner" not in missing:
            errors.append("unsupported scheduler_owner")
    try:
        execution_mode = ExecutionMode(str(supplied.get("execution_mode") or ""))
    except ValueError:
        execution_mode = None
        if "execution_mode" not in missing:
            errors.append("unsupported execution_mode")
    if errors:
        return SchedulerExecutionContextResolution(
            context=None,
            errors=tuple(errors),
            supplied=supplied,
        )
    context = SchedulerExecutionContext(
        host_surface=host_surface,
        scheduler_owner=scheduler_owner,
        execution_mode=execution_mode,
        source=str(supplied.get("source") or "explicit"),
    )
    errors = _validation_errors(context)
    return SchedulerExecutionContextResolution(
        context=context if not errors else None,
        errors=tuple(errors),
        supplied=supplied,
    )


def scheduler_execution_context_for_turn(
    *,
    host: str,
    execution_mode: str,
    scheduler_owner: str | None = None,
) -> SchedulerExecutionContextResolution:
    host_surface = {
        "codex-cli": HostSurface.CODEX_CLI.value,
        "generic-cli": HostSurface.GENERIC_CLI.value,
        "claude-code": HostSurface.CLAUDE_CODE.value,
    }.get(host, host)
    normalized_mode = {
        "interactive-visible": ExecutionMode.INTERACTIVE.value,
        "isolated-headless": ExecutionMode.ISOLATED_HEADLESS.value,
    }.get(execution_mode, execution_mode)
    owner = scheduler_owner or (
        SchedulerOwner.OUTER_CONTROLLER.value
        if host_surface == HostSurface.GENERIC_CLI.value
        else SchedulerOwner.AGENT_CLI_LOOP.value
    )
    return resolve_scheduler_execution_context(
        {
            "host_surface": host_surface,
            "scheduler_owner": owner,
            "execution_mode": normalized_mode,
            "source": "loopx_turn",
        }
    )


def apply_scheduler_execution_context(
    result: dict[str, Any],
    resolution: SchedulerExecutionContextResolution,
) -> dict[str, Any]:
    """Scope a generic cadence hint to the selected runtime owner."""

    if not resolution.ok or resolution.context is None:
        raise ValueError("cannot apply an invalid scheduler execution context")
    context = resolution.context
    if context.source == "compatibility_default":
        return result

    result["execution_context"] = resolution.projection()
    codex_app = (
        result.get("codex_app") if isinstance(result.get("codex_app"), dict) else {}
    )
    if context.codex_app_applicable:
        codex_app["applicability"] = "applicable"
        backoff = (
            codex_app.get("stateful_backoff")
            if isinstance(codex_app.get("stateful_backoff"), dict)
            else {}
        )
        apply_needed = (
            backoff.get("apply_needed") is True
            or codex_app.get("host_action_required") is True
        )
        ack_needed = backoff.get("ack_needed") is True
        result["codex_app"] = codex_app
        result["execution_phase"] = {
            "schema_version": "scheduler_execution_phase_v0",
            "host_surface": context.host_surface.value,
            "scheduler_owner": context.scheduler_owner.value,
            "disposition": (
                "host_action_required" if apply_needed or ack_needed else "not_required"
            ),
            "completed": not (apply_needed or ack_needed),
            "apply_needed": apply_needed,
            "ack_needed": ack_needed,
            "acknowledged": False,
        }
        return result

    result["codex_app"] = {
        "applicability": "not_applicable",
        "reason_code": f"cadence_owned_by_{context.scheduler_owner.value}",
        "apply": "none",
        "host_action": "none",
        "ack_required": False,
        "no_spend_for_cadence_change": True,
    }
    reset_policy = result.get("reset_policy")
    if isinstance(reset_policy, dict):
        for key in tuple(reset_policy):
            if key.startswith("codex_app_"):
                reset_policy.pop(key, None)
    cold_path = result.get("cold_path_detail")
    if isinstance(cold_path, dict):
        cold_path.pop("stateful_backoff_detail", None)
        reset_detail = cold_path.get("reset_policy_detail")
        if isinstance(reset_detail, dict):
            for key in tuple(reset_detail):
                if key.startswith("codex_app_"):
                    reset_detail.pop(key, None)
    owner = context.scheduler_owner.value
    result["execution_phase"] = {
        "schema_version": "scheduler_execution_phase_v0",
        "host_surface": context.host_surface.value,
        "scheduler_owner": owner,
        "disposition": f"{owner}_owned",
        "completed": True,
        "apply_needed": False,
        "ack_needed": False,
        "acknowledged": False,
        "completion_reason": (
            "selected scheduler owner requires no Codex App apply or ACK"
        ),
    }
    return result
