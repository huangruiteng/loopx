#!/usr/bin/env python3
"""Qualify the SkillsBench LoopX Turn route without a model or remote job."""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench import skillsbench_route_contract  # noqa: E402
from loopx.benchmark_adapters.skillsbench_acp_failure_policy import (  # noqa: E402
    recoverable_codex_turn_failure_message,
)
from loopx.benchmark_adapters.skillsbench_turn_runtime import (  # noqa: E402
    SkillsBenchTurnRuntimeConfig,
    build_skillsbench_loopx_turn_trace,
    run_skillsbench_loopx_turn,
)
from loopx.benchmark_adapters.skillsbench_turn_route import (  # noqa: E402
    sync_skillsbench_loopx_turn_trace_into_compact,
)
from loopx.benchmark_core import (  # noqa: E402
    LOOPX_TURN_AGENT_CLI_ROUTE,
    build_loopx_turn_benchmark_fidelity_check,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _host_local_acp_launch_command,
    _merge_host_local_acp_relay_trace_summary,
    build_plan,
    parse_args,
)


GOAL_ID = "skillsbench-turn-smoke"
AGENT_ID = "codex-benchmark-agent"
TODO_ID = "todo_skillsbenchturnsmoke01"


def _write_fixture(root: Path) -> dict[str, Path]:
    project = root / "project"
    runtime = root / "runtime"
    workspace = root / "workspace"
    runtime.mkdir(parents=True)
    workspace.mkdir(parents=True)
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# SkillsBench LoopX Turn Smoke",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Create the public smoke marker and validate it.",
                (
                    f"  <!-- loopx:todo todo_id={TODO_ID} status=open "
                    "task_class=advancement_task action_kind=benchmark_smoke "
                    f"claimed_by={AGENT_ID} priority=P0 -->"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "public-benchmark-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {"kind": "fixture_v0", "status": "connected"},
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                            "agent_profiles": {
                                AGENT_ID: {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "fixture",
                                    "scope": "public qualification",
                                }
                            },
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "project": project,
        "runtime": runtime,
        "workspace": workspace,
        "registry": registry,
    }


def _write_bridge(root: Path, workspace: Path) -> str:
    bridge = root / "bridge.py"
    bridge.write_text(
        f"""#!/usr/bin/env python3
import json
import subprocess
import sys

request = json.load(sys.stdin)
command = str(request.get("command") or "").replace("/app", {str(workspace)!r})
completed = subprocess.run(
    command,
    cwd={str(workspace)!r},
    shell=True,
    executable="/bin/bash",
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
print(json.dumps({{
    "schema_version": "skillsbench_remote_command_file_bridge_operation_response_v0",
    "ok": completed.returncode == 0,
    "exit_code": completed.returncode,
    "stdout": completed.stdout,
    "stderr": completed.stderr,
    "stdout_truncated": False,
    "stderr_truncated": False,
}}))
""",
        encoding="utf-8",
    )
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(bridge))}"


def _config(
    paths: dict[str, Path], *, validation_command: str
) -> SkillsBenchTurnRuntimeConfig:
    return SkillsBenchTurnRuntimeConfig(
        bridge_command=_write_bridge(paths["project"].parent, paths["workspace"]),
        validation_command=validation_command,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        runtime_root=paths["project"].parent / "turn-runtime",
        case_cli_path=str(REPO_ROOT / "scripts" / "loopx"),
        case_registry_path=str(paths["registry"]),
        case_runtime_root=str(paths["runtime"]),
    )


def _run_success(root: Path) -> dict[str, Any]:
    paths = _write_fixture(root)

    def agent_runner(_prompt: str) -> str:
        (paths["workspace"] / "solution.ok").write_text("ok\n", encoding="utf-8")
        return "agent completed the public smoke task"

    config = _config(paths, validation_command="test -f /app/solution.ok")
    execution, validation = run_skillsbench_loopx_turn(
        prompt="Create the requested public smoke marker.",
        agent_runner=agent_runner,
        config=config,
    )
    second_execution, second_validation = run_skillsbench_loopx_turn(
        prompt="Reinspect the same task without verifier feedback.",
        agent_runner=agent_runner,
        config=config,
    )
    trace_dir = root / "public-trace"
    trace_dir.mkdir()
    for index, (turn_execution, turn_validation) in enumerate(
        ((execution, validation), (second_execution, second_validation)),
        start=1,
    ):
        trace_payload = build_skillsbench_loopx_turn_trace(
            route=LOOPX_TURN_AGENT_CLI_ROUTE,
            benchmark_id="skillsbench",
            task_id="public-smoke-case",
            execution=turn_execution,
            scored_workspace_validation=turn_validation,
        )
        (trace_dir / f"turn-{index}.compact.json").write_text(
            json.dumps(trace_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    controller_trace: dict[str, Any] = {}
    plan = {
        "route": LOOPX_TURN_AGENT_CLI_ROUTE,
        "host_local_acp_relay_trace_dir": str(trace_dir),
        "runner_prerequisites": {},
    }
    _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
    compact = {
        "benchmark_id": "skillsbench",
        "case_id": "public-smoke-case",
        "route": LOOPX_TURN_AGENT_CLI_ROUTE,
    }
    sync_skillsbench_loopx_turn_trace_into_compact(compact, controller_trace)
    fidelity = build_loopx_turn_benchmark_fidelity_check(compact)
    assert execution.get("status") == "committed", execution
    assert execution.get("execution_mode") == "isolated-headless", execution
    assert execution.get("quota_slot_spend_count") == 1, execution
    assert execution.get("effects") == {
        "host_invoked": True,
        "state_written": True,
        "quota_spent": True,
        "scheduler_acknowledged": False,
    }, execution
    assert validation.get("status") == "passed", validation
    assert validation.get("meaningful_operation_count") == 1, validation
    assert second_execution.get("status") == "committed", second_execution
    assert second_execution.get("replayed") is False, second_execution
    assert second_execution.get("resume_turn_key") != execution.get(
        "resume_turn_key"
    ), (execution, second_execution)
    assert second_validation.get("status") == "passed", second_validation
    assert fidelity.get("turn_treatment_fidelity_allowed") is True, fidelity
    assert len(compact.get("loopx_turn_executions", [])) == 2, compact
    return {
        "execution_status": execution.get("status"),
        "receipt_status": execution.get("receipt", {}).get("status"),
        "validation_status": validation.get("status"),
        "fidelity_allowed": fidelity.get("turn_treatment_fidelity_allowed"),
        "compact_turn_count": len(compact.get("loopx_turn_executions", [])),
    }


def _run_failure(root: Path) -> dict[str, Any]:
    paths = _write_fixture(root)
    execution, validation = run_skillsbench_loopx_turn(
        prompt="Do not create a marker.",
        agent_runner=lambda _prompt: "agent returned without satisfying the task",
        config=_config(paths, validation_command="false"),
    )
    effects = execution.get("effects")
    assert execution.get("status") == "failed", execution
    assert execution.get("receipt", {}).get("failed_phase") == "validation", execution
    assert isinstance(effects, dict) and effects.get("state_written") is False, (
        execution
    )
    assert isinstance(effects, dict) and effects.get("quota_spent") is False, execution
    assert validation.get("status") == "failed", validation
    return {
        "execution_status": execution.get("status"),
        "failed_phase": execution.get("receipt", {}).get("failed_phase"),
        "validation_status": validation.get("status"),
        "quota_spent": effects.get("quota_spent")
        if isinstance(effects, dict)
        else None,
    }


def _run_recoverable_host_failure(root: Path) -> dict[str, Any]:
    paths = _write_fixture(root)
    execution, validation = run_skillsbench_loopx_turn(
        prompt="Encounter a recoverable host failure.",
        agent_runner=lambda _prompt: recoverable_codex_turn_failure_message(
            "codex_exec_timeout"
        ),
        config=_config(paths, validation_command="true"),
    )
    effects = execution.get("effects")
    assert execution.get("status") == "failed", execution
    assert execution.get("receipt", {}).get("failed_phase") == "host_execute", execution
    assert isinstance(effects, dict) and effects.get("state_written") is False, (
        execution
    )
    assert isinstance(effects, dict) and effects.get("quota_spent") is False, execution
    assert validation.get("meaningful_operation_count") == 0, validation
    return {
        "execution_status": execution.get("status"),
        "failed_phase": execution.get("receipt", {}).get("failed_phase"),
        "quota_spent": effects.get("quota_spent")
        if isinstance(effects, dict)
        else None,
        "validator_invoked": validation.get("meaningful_operation_count") != 0,
    }


def main() -> int:
    route_contract = skillsbench_route_contract(LOOPX_TURN_AGENT_CLI_ROUTE)
    assert route_contract.get("product_mode") is True, route_contract
    assert route_contract.get("official_feedback_blinded") is True, route_contract
    assert route_contract.get("official_score_comparable_to_loopx_treatment") is True, (
        route_contract
    )
    runner_args = parse_args(
        [
            "--task-id",
            "public-smoke-case",
            "--route",
            LOOPX_TURN_AGENT_CLI_ROUTE,
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--remote-command-file-bridge-solver-command",
            "private-bridge-command",
            "--loopx-turn-validation-command",
            "test -f /app/solution.ok",
        ]
    )
    runner_plan = build_plan(runner_args)
    launch_command = _host_local_acp_launch_command(runner_args, runner_plan)
    assert "--loopx-turn-agent-cli" in launch_command, launch_command
    assert "--loopx-turn-validation-command" in launch_command, launch_command
    assert "--loopx-workflow-lifecycle-checkpoint" not in launch_command, launch_command
    prerequisites = runner_plan.get("runner_prerequisites", {})
    assert prerequisites.get("loopx_turn_validation_configured") is True, prerequisites
    assert prerequisites.get("loopx_turn_validation_command_recorded") is False, (
        prerequisites
    )

    with tempfile.TemporaryDirectory(prefix="skillsbench-loopx-turn-success-") as value:
        success = _run_success(Path(value))
    with tempfile.TemporaryDirectory(prefix="skillsbench-loopx-turn-failure-") as value:
        failure = _run_failure(Path(value))
    with tempfile.TemporaryDirectory(
        prefix="skillsbench-loopx-turn-host-failure-"
    ) as value:
        recoverable_host_failure = _run_recoverable_host_failure(Path(value))
    with tempfile.TemporaryDirectory(prefix="skillsbench-loopx-turn-missing-") as value:
        paths = _write_fixture(Path(value))
        try:
            run_skillsbench_loopx_turn(
                prompt="missing validator",
                agent_runner=lambda _prompt: "unused",
                config=_config(paths, validation_command=""),
            )
        except ValueError as exc:
            assert "validation command" in str(exc), exc
        else:
            raise AssertionError("missing independent validator must fail closed")

    print(
        json.dumps(
            {
                "schema_version": "skillsbench_loopx_turn_agent_cli_smoke_v0",
                "route": LOOPX_TURN_AGENT_CLI_ROUTE,
                "route_contract": route_contract,
                "runner_launch_contract": {
                    "loopx_turn_agent_cli": True,
                    "independent_validation_configured": True,
                    "legacy_lifecycle_checkpoint": False,
                },
                "success": success,
                "failure": failure,
                "recoverable_host_failure": recoverable_host_failure,
                "missing_validator_failed_closed": True,
                "model_invoked": False,
                "remote_job_launched": False,
                "raw_material_recorded": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
