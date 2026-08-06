"""Narrow LoopX CLI seam for the native KunlunCode Goal controller."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from loopx.control_plane.agents.workspace_guard import capture_delivery_workspace


AVAILABLE_CAPABILITIES = ("shell", "filesystem_write")
VERIFIED_CLASSIFICATIONS = {
    "goal": "kunluncode_native_goal_verified",
    "goal-pro": "kunluncode_native_goal_pro_verified",
}


class KunlunNativeGoalRuntimeError(RuntimeError):
    """Raised when native Goal execution or LoopX reconciliation fails closed."""


def _default_loopx_prefix() -> list[str]:
    executable = shutil.which("loopx")
    return [executable] if executable else [sys.executable, "-m", "loopx.cli"]


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _default_command_runner(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class LoopXControlPlane:
    """JSON CLI operations used by the native KunlunCode controller."""

    def __init__(
        self,
        project: Path,
        context: Mapping[str, Any],
        *,
        command_prefix: list[str] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.project = project.resolve()
        self.registry = str(context.get("registry") or "")
        self.goal_id = str(context.get("goal_id") or "")
        self.agent_id = str(context.get("agent_id") or "")
        if not self.registry or not self.goal_id or not self.agent_id:
            raise KunlunNativeGoalRuntimeError(
                "KunlunCode binding is missing registry, goal, or agent identity"
            )
        self.command_prefix = list(command_prefix or _default_loopx_prefix())
        self.runner = runner or _default_command_runner

    def _run_json(self, arguments: list[str], *, timeout: int = 120) -> dict[str, Any]:
        command = [
            *self.command_prefix,
            "--registry",
            self.registry,
            "--format",
            "json",
            *arguments,
        ]
        result = self.runner(command, cwd=self.project, timeout=timeout)
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            diagnostic = (result.stderr or result.stdout or "")[-1200:]
            raise KunlunNativeGoalRuntimeError(
                "LoopX returned non-JSON output"
                + (f": {diagnostic}" if diagnostic else "")
            ) from exc
        if not isinstance(payload, dict):
            raise KunlunNativeGoalRuntimeError(
                "LoopX returned a non-object JSON payload"
            )
        if result.returncode != 0 or payload.get("ok") is False:
            reason = payload.get("error") or payload.get("reason") or result.stderr
            raise KunlunNativeGoalRuntimeError(
                "LoopX control-plane command failed: "
                + str(reason or "unknown error")[-1200:]
            )
        return payload

    @staticmethod
    def _capability_args() -> list[str]:
        return [
            argument
            for capability in AVAILABLE_CAPABILITIES
            for argument in ("--available-capability", capability)
        ]

    def should_run(self) -> dict[str, Any]:
        return self._run_json(
            [
                "quota",
                "should-run",
                "--goal-id",
                self.goal_id,
                "--agent-id",
                self.agent_id,
                "--runtime-profile",
                "kunluncode",
                *self._capability_args(),
            ]
        )

    def claim(self, todo_id: str) -> dict[str, Any]:
        return self._run_json(
            [
                "todo",
                "claim",
                "--goal-id",
                self.goal_id,
                "--todo-id",
                todo_id,
                "--claimed-by",
                self.agent_id,
                "--agent-id",
                self.agent_id,
            ]
        )

    def evidence_since(self, since: str) -> dict[str, Any]:
        return self._run_json(
            [
                "evidence-log",
                "--goal-id",
                self.goal_id,
                "--agent-id",
                self.agent_id,
                "--thin",
                "--since",
                since,
                "--limit",
                "128",
            ]
        )

    def record_verified_delivery(self, *, mode: str) -> dict[str, Any]:
        workspace_arguments = (
            ["--delivery-workspace-path", str(self.project)]
            if capture_delivery_workspace(self.project)
            else []
        )
        return self._run_json(
            [
                "refresh-state",
                "--goal-id",
                self.goal_id,
                "--project",
                str(self.project),
                "--classification",
                VERIFIED_CLASSIFICATIONS[mode],
                "--recommended-action",
                "Reconcile the verifier-approved KunlunCode todo and continue from LoopX quota.",
                "--delivery-batch-scale",
                "single_surface",
                "--delivery-outcome",
                "outcome_progress",
                *workspace_arguments,
                "--agent-id",
                self.agent_id,
                "--progress-scope",
                "goal",
                *self._capability_args(),
                "--suppress-external-sinks",
            ],
            timeout=300,
        )

    def complete(self, todo_id: str, *, evidence: str) -> dict[str, Any]:
        return self._run_json(
            [
                "todo",
                "complete",
                "--goal-id",
                self.goal_id,
                "--todo-id",
                todo_id,
                "--claimed-by",
                self.agent_id,
                "--agent-id",
                self.agent_id,
                "--evidence",
                evidence,
                "--no-follow-up",
            ]
        )

    def spend(self) -> dict[str, Any]:
        return self._run_json(
            [
                "quota",
                "spend-slot",
                "--goal-id",
                self.goal_id,
                "--slots",
                "1",
                "--source",
                "adapter",
                "--execute",
                "--agent-id",
                self.agent_id,
                *self._capability_args(),
            ],
            timeout=300,
        )
