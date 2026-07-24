from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopx.benchmark_adapters.skillsbench_acp_relay import (
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)
from loopx.benchmark_adapters import skillsbench_codex_runtime as codex_runtime
from loopx.codex_cli_goal_tui import resolve_codex_cli_binary
from scripts import skillsbench_automation_loop as skillsbench_loop


def _args(
    codex_bin: str,
    *,
    relay_command: str | None = None,
    sandbox: str = "workspace-write",
) -> SimpleNamespace:
    return SimpleNamespace(
        host_local_acp_launch=True,
        local_acp_relay_command=relay_command,
        local_codex_bin=codex_bin,
        local_codex_sandbox=sandbox,
    )


def test_host_local_codex_cli_preflight_is_public_and_fail_fast(tmp_path: Path) -> None:
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o755)
    assert resolve_codex_cli_binary(str(codex)) == str(codex)

    plan = {"runner_prerequisites": {}}
    codex_runtime.run_preflight(_args(str(codex)), plan)
    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["host_local_codex_cli_preflight_status"] == "ready"
    assert prerequisites["host_local_codex_cli_preflight_ready"] is True
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_required"]
        is True
    )
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_invoked"]
        is True
    )
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_ready"]
        is True
    )
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_status"]
        == "ready"
    )
    assert prerequisites["host_local_codex_cli_preflight_path_recorded"] is False
    assert str(codex) not in json.dumps(prerequisites, sort_keys=True)

    public = skillsbench_loop._public_runner_prerequisites(prerequisites)
    assert public["host_local_codex_cli_preflight_status"] == "ready"
    assert public["host_local_codex_cli_preflight_version_probe_invoked"] is True
    assert public["host_local_codex_cli_preflight_sandbox_probe_ready"] is True


def test_missing_codex_cli_has_precise_runner_attribution(tmp_path: Path) -> None:
    plan = {"runner_prerequisites": {}}
    with pytest.raises(RuntimeError, match="Codex CLI unavailable"):
        codex_runtime.run_preflight(
            _args(str(tmp_path / "missing-codex")), plan
        )
    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["host_local_codex_cli_preflight_status"] == "failed"
    assert prerequisites["host_local_codex_cli_preflight_first_blocker"] == (
        "skillsbench_host_local_codex_cli_unavailable"
    )
    attribution = skillsbench_loop._runner_prerequisite_failure_attribution(
        prerequisites
    )
    assert attribution is not None
    assert attribution[0].endswith("_codex_cli_not_on_path")
    assert codex_runtime.preflight_required(_args("codex"))
    assert not codex_runtime.preflight_required(
        _args("unused", relay_command="custom-relay")
    )


def test_host_local_codex_cli_preflight_fails_when_selected_sandbox_cannot_run(
    tmp_path: Path,
) -> None:
    raw_failure = (
        "bwrap: No permissions to create new namespace at "
        "/private/runner/workspace\n"
    )
    codex = tmp_path / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then exit 0; fi\n"
        "if [ \"$1\" = \"sandbox\" ] && "
        "[ \"$2\" = \"-c\" ] && "
        "[ \"$3\" = 'sandbox_mode=\"workspace-write\"' ]; then "
        f"printf '%s' '{raw_failure}' >&2; exit 101; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    plan = {"runner_prerequisites": {}}

    with pytest.raises(RuntimeError, match="sandbox probe failed"):
        codex_runtime.run_preflight(_args(str(codex)), plan)

    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["host_local_codex_cli_preflight_status"] == "failed"
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_invoked"]
        is True
    )
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_ready"]
        is False
    )
    assert prerequisites["host_local_codex_cli_preflight_first_blocker"] == (
        "skillsbench_host_local_codex_cli_sandbox_probe_failed"
    )
    assert prerequisites[
        "host_local_codex_cli_preflight_sandbox_failure_subtype"
    ] == "linux_user_namespace_unavailable"
    serialized = json.dumps(prerequisites, sort_keys=True)
    assert raw_failure.strip() not in serialized
    assert "/private/runner/workspace" not in serialized
    public = skillsbench_loop._public_runner_prerequisites(prerequisites)
    assert public[
        "host_local_codex_cli_preflight_sandbox_failure_subtype"
    ] == "linux_user_namespace_unavailable"
    assert "/private/runner/workspace" not in json.dumps(public, sort_keys=True)
    attribution = skillsbench_loop._runner_prerequisite_failure_attribution(
        prerequisites
    )
    assert attribution is not None
    assert attribution[0].endswith("_codex_cli_sandbox_probe_failed")


def test_explicit_danger_full_access_does_not_require_a_codex_sandbox_probe(
    tmp_path: Path,
) -> None:
    codex = tmp_path / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"sandbox\" ]; then exit 101; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    plan = {"runner_prerequisites": {}}

    codex_runtime.run_preflight(
        _args(str(codex), sandbox="danger-full-access"), plan
    )

    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["host_local_codex_cli_preflight_status"] == "ready"
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_required"]
        is False
    )
    assert (
        prerequisites["host_local_codex_cli_preflight_sandbox_probe_invoked"]
        is False
    )
    assert prerequisites["host_local_codex_cli_preflight_sandbox_probe_status"] == (
        "not_required"
    )


def test_reverse_channel_cli_goal_requires_fixed_pre_agent_bridge_receipt() -> None:
    args = SimpleNamespace(
        setup_only_public_preflight=False,
        route="codex-cli-goal-baseline",
        host_local_acp_launch=True,
        local_codex_provider="reverse-channel",
        host_local_acp_codex_exec_preflight=True,
        remote_command_file_bridge_solver_command="private-solver-command",
        remote_command_file_bridge_ready=True,
        remote_command_file_bridge_probe=False,
    )

    assert skillsbench_loop._host_local_acp_codex_exec_preflight_should_run(args)
    assert skillsbench_loop._host_local_acp_codex_exec_preflight_requires_bridge_action(
        args
    )

    args.setup_only_public_preflight = True
    assert skillsbench_loop._host_local_acp_codex_exec_preflight_should_run(args)

    args.local_codex_provider = "exact-host"
    assert not skillsbench_loop._host_local_acp_codex_exec_preflight_should_run(args)
    assert not (
        skillsbench_loop._host_local_acp_codex_exec_preflight_requires_bridge_action(
            args
        )
    )


def test_materialized_sandbox_bridge_requires_successful_pre_agent_action() -> None:
    args = SimpleNamespace(
        route="codex-cli-goal-baseline",
        host_local_acp_launch=True,
        local_codex_provider="reverse-channel",
        remote_command_file_bridge_solver_command="",
        remote_command_file_bridge_ready=False,
        remote_command_file_bridge_probe=True,
    )

    assert not skillsbench_loop._host_local_acp_codex_exec_preflight_requires_bridge_action(
        args
    )
    assert skillsbench_loop._host_local_acp_codex_exec_preflight_requires_bridge_action(
        args,
        require_materialized_sandbox_bridge=True,
    )
    assert skillsbench_loop._host_local_acp_codex_exec_preflight_requires_bridge_action(
        args,
        sandbox_bridge_command="materialized-sandbox-bridge",
    )


def test_pre_agent_receipt_rebinds_to_materialized_sandbox_bridge() -> None:
    args = skillsbench_loop.parse_args(
        [
            "--task-id",
            "public-case-id",
            "--route",
            "codex-cli-goal-baseline",
            "--host-local-acp-launch",
            "--local-codex-provider",
            "reverse-channel",
            "--host-local-acp-codex-exec-preflight",
            "--remote-command-file-bridge-probe",
            "--remote-command-file-bridge-solver-command",
            "task-free-placeholder",
        ]
    )

    command = skillsbench_loop._host_local_acp_codex_exec_preflight_command(
        args,
        {"runner_prerequisites": {}},
        sandbox_bridge_command="materialized-sandbox-bridge",
    )

    bridge_index = command.index("--remote-command-file-bridge-command")
    agent_bridge_index = command.index("--remote-command-file-bridge-agent-command")
    assert command[bridge_index + 1] == "materialized-sandbox-bridge"
    assert command[agent_bridge_index + 1] == "materialized-sandbox-bridge"
    assert "task-free-placeholder" not in command


def test_early_tui_failure_does_not_claim_goal_submission(tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(worker_public_trace_dir=str(trace_dir))
    )
    relay._publish_codex_cli_goal_trace(
        ok=False,
        stage="tui_ready_timeout",
        goal_active_observed=False,
        goal_terminal_observed=False,
        first_action_observed=False,
        bridge_summary_path=None,
        goal_slash_command_submitted=False,
    )
    trace = json.loads(next(trace_dir.glob("*.compact.json")).read_text())
    assert trace["codex_cli_goal"]["goal_slash_command_submitted"] is False
    assert trace["boundary"]["raw_task_text_recorded"] is False
