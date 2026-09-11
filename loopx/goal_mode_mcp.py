"""Shared MCP control plane for host-specific LoopX goal adapters."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

try:  # pydantic ships with the FastMCP extra; base installs have no pydantic.
    from pydantic import Strict
except ImportError:  # pragma: no cover - exercised on base installs only
    class Strict:  # type: ignore[no-redef]
        """Inert stand-in so the shared annotation still evaluates without
        pydantic; FastMCP cannot run on such an install anyway."""

from .control_plane.host_adapter_settlement import (
    HostTodoSettlementRequest,
    settle_host_todo_completion,
)


ContextResolver = Callable[[], dict[str, Any] | None]

# The one boundary type for a caller-supplied lease version. FastMCP validates
# tool arguments with pydantic, and lax pydantic coerces JSON true to 1 before
# any loopx code runs, so strictness must live in the annotation itself; the
# control-plane method and the FastMCP wrapper share this alias so the two
# signatures cannot drift.
ExpectedTaskLeaseVersion = Annotated[int, Strict()] | None


@dataclass(frozen=True)
class GoalModeMCPConfig:
    server_name: str
    runtime_profile: str
    legacy_host_surface: str
    scheduler_owner: str = "agent_cli_loop"
    execution_mode: str = "interactive"
    setup_hint: str = "connect this host adapter first"


class GoalModeMCPControlPlane:
    """Deterministic lifecycle operations exposed through FastMCP."""

    def __init__(self, config: GoalModeMCPConfig, context_resolver: ContextResolver):
        self.config = config
        self.context_resolver = context_resolver

    def state(self) -> dict[str, Any]:
        return self.context_resolver() or {}

    def context(self) -> tuple[str | None, str | None]:
        state = self.state()
        return state.get("goal_id"), state.get("registry")

    def bound_agent_id(self) -> str | None:
        return self.state().get("agent_id")

    def command_prefix(self) -> list[str]:
        executable = shutil.which("loopx")
        return [executable] if executable else [sys.executable, "-m", "loopx.cli"]

    @staticmethod
    def _runtime_profile_flag_is_unsupported(
        result: subprocess.CompletedProcess[str],
    ) -> bool:
        diagnostic = str(result.stderr or "").lower()
        return (
            result.returncode == 2
            and "--runtime-profile" in diagnostic
            and (
                "unrecognized arguments" in diagnostic
                or "invalid choice" in diagnostic
            )
        )

    def run_cli(
        self,
        args: list[str],
        *,
        legacy_args: list[str] | None = None,
    ) -> str:
        _, registry = self.context()
        command = self.command_prefix()
        if registry:
            command += ["--registry", registry]
        command += ["--format", "json"]
        result = subprocess.run(
            [*command, *args], capture_output=True, text=True, timeout=30
        )
        if legacy_args is not None and self._runtime_profile_flag_is_unsupported(result):
            result = subprocess.run(
                [*command, *legacy_args], capture_output=True, text=True, timeout=30
            )
        return (result.stdout or "") + (
            ("\n" + result.stderr) if result.returncode else ""
        )

    def no_goal_message(self) -> str:
        return json.dumps(
            {
                "ok": False,
                "error": "goal-mode is not active for this host in this project",
                "next_action": self.config.setup_hint,
            }
        )

    def _identity_error(self, requested_agent_id: str) -> str | None:
        bound = self.bound_agent_id()
        if bound and requested_agent_id == bound:
            return None
        return json.dumps(
            {
                "ok": False,
                "error": "agent_id does not match the host binding",
                "requested_agent_id": requested_agent_id,
                "bound_agent_id": bound,
            }
        )

    def should_run_args(self, goal_id: str, agent_id: str | None) -> tuple[list[str], list[str]]:
        common = ["quota", "should-run", "--goal-id", goal_id]
        if agent_id:
            common += ["--agent-id", agent_id]
        return (
            [*common, "--runtime-profile", self.config.runtime_profile],
            [
                *common,
                "--host-surface",
                self.config.legacy_host_surface,
                "--scheduler-owner",
                self.config.scheduler_owner,
                "--execution-mode",
                self.config.execution_mode,
            ],
        )

    def should_run(self) -> str:
        goal_id, _ = self.context()
        if not goal_id:
            return self.no_goal_message()
        args, legacy_args = self.should_run_args(goal_id, self.bound_agent_id())
        return self.run_cli(args, legacy_args=legacy_args)

    def list_todos(self) -> str:
        return self.should_run()

    def host_prompt(self) -> str:
        from .claude_goal_mode.scripts.goalmode_cmd import loop_execution_content
        state = self.state()
        goal_id, agent_id = state.get("goal_id"), state.get("agent_id")
        if not goal_id or not agent_id:
            return json.dumps({"ok": False, "error": "bound Goal and agent are required"})
        return json.dumps({"ok": True, "goal_id": goal_id, "agent_id": agent_id,
                           "task_body": loop_execution_content(goal_id, agent_id)})

    def claim_task(self, todo_id: str, agent_id: str) -> str:
        goal_id, _ = self.context()
        if not goal_id:
            return self.no_goal_message()
        identity_error = self._identity_error(agent_id)
        if identity_error:
            return identity_error
        return self.run_cli(
            [
                "todo",
                "claim",
                "--goal-id",
                goal_id,
                "--todo-id",
                todo_id,
                "--claimed-by",
                agent_id,
                "--agent-id",
                agent_id,
            ]
        )

    def complete_task(
        self,
        todo_id: str,
        agent_id: str,
        evidence: str,
        next_agent_todo: str = "",
        task_lease_idempotency_key: str = "",
        task_lease_expected_version: ExpectedTaskLeaseVersion = None,
        no_follow_up: bool = False,
        successor_todo_ids: list[str] | None = None,
    ) -> str:
        goal_id, _ = self.context()
        if not goal_id:
            return self.no_goal_message()
        identity_error = self._identity_error(agent_id)
        if identity_error:
            return identity_error
        if next_agent_todo and no_follow_up:
            return json.dumps(
                {
                    "ok": False,
                    "error": "next_agent_todo and no_follow_up are mutually exclusive",
                }
            )
        if successor_todo_ids is not None and (
            not isinstance(successor_todo_ids, list)
            or any(not isinstance(value, str) or not value.strip() for value in successor_todo_ids)
        ):
            return json.dumps({"ok": False, "error": "successor_todo_ids must be a list of nonempty ids"})
        if successor_todo_ids and (next_agent_todo or no_follow_up):
            return json.dumps({"ok": False, "error": "choose existing successors, a new successor, or no follow-up"})
        args = [
            "todo",
            "complete",
            "--goal-id",
            goal_id,
            "--todo-id",
            todo_id,
            "--claimed-by",
            agent_id,
            "--agent-id",
            agent_id,
            "--evidence",
            evidence,
        ]
        if next_agent_todo:
            args += ["--next-agent-todo", next_agent_todo]
        for successor in successor_todo_ids or []:
            args += ["--successor-todo-id", successor]
        if task_lease_idempotency_key:
            args += ["--task-lease-idempotency-key", task_lease_idempotency_key]
        if task_lease_expected_version is not None:
            args += [
                "--task-lease-expected-version",
                str(task_lease_expected_version),
            ]
        if no_follow_up:
            args.append("--no-follow-up")
        return settle_host_todo_completion(
            HostTodoSettlementRequest(
                goal_id=goal_id,
                agent_id=agent_id,
                todo_id=todo_id,
                runtime_profile=self.config.runtime_profile,
                legacy_host_surface=self.config.legacy_host_surface,
                scheduler_owner=self.config.scheduler_owner,
                execution_mode=self.config.execution_mode,
                completion_args=tuple(args),
                no_follow_up=no_follow_up,
            ),
            run_cli=self.run_cli,
        )


def create_fastmcp_server(
    config: GoalModeMCPConfig,
    context_resolver: ContextResolver,
):
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - exercised by real adapter startup
        raise SystemExit(
            "MCP SDK v1 is required. Install the adapter with loopx-kunluncode install.\n"
            + str(exc)
        ) from exc

    control = GoalModeMCPControlPlane(config, context_resolver)
    server = FastMCP(config.server_name)

    if config.legacy_host_surface == "claude_code":
        @server.tool()
        def host_prompt() -> str:
            """Read current Claude Goal execution rules for this server's bound identity."""
            return control.host_prompt()

    @server.tool()
    def should_run() -> str:
        """Whether the bound goal and agent should run now."""
        return control.should_run()

    @server.tool()
    def list_todos() -> str:
        """List open todos visible to the bound agent."""
        return control.list_todos()

    @server.tool()
    def claim_task(todo_id: str, agent_id: str) -> str:
        """Claim one todo as the bound agent."""
        return control.claim_task(todo_id, agent_id)

    @server.tool()
    def complete_task(
        todo_id: str,
        agent_id: str,
        evidence: str,
        next_agent_todo: str = "",
        task_lease_idempotency_key: str = "",
        task_lease_expected_version: ExpectedTaskLeaseVersion = None,
        no_follow_up: bool = False,
        successor_todo_ids: list[str] | None = None,
    ) -> str:
        """Complete verified work and settle once. Link existing planned successors
        with successor_todo_ids; next_agent_todo creates a NEW Todo, not an id link.
        Use no_follow_up only for terminal intent. Do not duplicate existing work.
        """
        return control.complete_task(
            todo_id,
            agent_id,
            evidence,
            next_agent_todo=next_agent_todo,
            task_lease_idempotency_key=task_lease_idempotency_key,
            task_lease_expected_version=task_lease_expected_version,
            no_follow_up=no_follow_up,
            successor_todo_ids=successor_todo_ids,
        )

    return server, control
