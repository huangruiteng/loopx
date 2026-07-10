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


def _args(codex_bin: str, *, relay_command: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        host_local_acp_launch=True,
        local_acp_relay_command=relay_command,
        local_codex_bin=codex_bin,
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
    assert prerequisites["host_local_codex_cli_preflight_path_recorded"] is False
    assert str(codex) not in json.dumps(prerequisites, sort_keys=True)

    public = skillsbench_loop._public_runner_prerequisites(prerequisites)
    assert public["host_local_codex_cli_preflight_status"] == "ready"
    assert public["host_local_codex_cli_preflight_version_probe_invoked"] is True


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
