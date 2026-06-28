#!/usr/bin/env python3
"""Smoke-test private Terminal-Bench runner auth env guardrails."""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
    build_terminal_bench_managed_harbor_command,
    build_terminal_bench_harbor_result_benchmark_run,
    build_terminal_bench_private_runner_env,
    build_terminal_bench_private_runner_launch,
    build_terminal_bench_result_finalization_gate,
    build_terminal_bench_task_material_readiness,
    launch_terminal_bench_case_run,
    launch_terminal_bench_environment_setup_probe,
    launch_terminal_bench_worker_materialization_probe,
    normalize_terminal_bench_private_runner_invocation,
    observe_terminal_bench_post_materialization_closeout,
    poll_terminal_bench_worker_materialization_probe,
    resolve_terminal_bench_runner_binary,
    resume_terminal_bench_materialized_job,
    summarize_terminal_bench_post_launch_materialization,
    summarize_terminal_bench_private_runner_launch,
    wait_for_terminal_bench_launch_materialization,
)
from loopx.status import (  # noqa: E402
    _compact_benchmark_post_launch_materialization,
    compact_benchmark_run,
)


def expect_raises(callable_obj, needle: str) -> None:
    try:
        callable_obj()
    except ValueError as exc:
        assert needle in str(exc), str(exc)
        return
    raise AssertionError(f"expected ValueError containing {needle!r}")


def assert_no_execution_attempt_accounting(payload: dict[str, object]) -> None:
    attempt_accounting = payload["attempt_accounting"]
    assert isinstance(attempt_accounting, dict), payload
    assert (
        attempt_accounting["schema_version"] == "benchmark_attempt_accounting_v0"
    ), attempt_accounting
    assert attempt_accounting["lifecycle_phase"] == "not_started", attempt_accounting
    assert attempt_accounting["failure_label"] == "", attempt_accounting
    assert attempt_accounting["failure_class"] == "none", attempt_accounting
    assert attempt_accounting["launcher_attempt_countable"] is False, attempt_accounting
    assert attempt_accounting["case_attempt_countable"] is False, attempt_accounting
    assert attempt_accounting["solver_attempt_countable"] is False, attempt_accounting
    assert attempt_accounting["verifier_attempt_countable"] is False, attempt_accounting
    assert (
        attempt_accounting["official_score_attempt_countable"] is False
    ), attempt_accounting


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-task-material-") as tmp:
        dataset = Path(tmp) / "terminal-bench-local"
        good_task = dataset / "good-task"
        good_task.mkdir(parents=True)
        (good_task / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")
        (good_task / "instruction.md").write_text("fixture instruction\n", encoding="utf-8")
        bad_task = dataset / "bad-task"
        bad_task.mkdir(parents=True)
        (bad_task / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")

        good_material = build_terminal_bench_task_material_readiness(
            dataset=str(dataset),
            task_id="good-task",
        )
        assert good_material["checked"] is True, good_material
        assert good_material["ready"] is True, good_material
        assert good_material["status"] == "ready", good_material
        assert good_material["raw_paths_recorded"] is False, good_material

        bad_material = build_terminal_bench_task_material_readiness(
            dataset=str(dataset),
            task_id="bad-task",
        )
        assert bad_material["checked"] is True, bad_material
        assert bad_material["ready"] is False, bad_material
        assert bad_material["first_blocker"] == "task_material_missing_instruction_md", bad_material

        bad_launch = build_terminal_bench_private_runner_launch(
            dataset=str(dataset),
            task_id="bad-task",
            jobs_dir="<private-jobs-dir>",
            job_name="terminal_bench_bad_material_env_guard_smoke",
            loopx_mode="codex_loopx",
            loopx_goal_id="loopx-meta",
            loopx_cli_bridge_enabled=True,
        )
        assert bad_launch["first_blocker"] == "task_material_missing_instruction_md", bad_launch
        assert bad_launch["ready"] is False, bad_launch
        bad_summary = summarize_terminal_bench_private_runner_launch(bad_launch)
        assert bad_summary["task_material_readiness_checked"] is True, bad_summary
        assert bad_summary["task_material_ready_required"] is False, bad_summary
        assert bad_summary["task_material_ready"] is False, bad_summary
        assert bad_summary["task_material_first_blocker"] == "task_material_missing_instruction_md", bad_summary
        assert bad_summary["raw_paths_recorded"] is False, bad_summary

        strict_unknown_launch = build_terminal_bench_private_runner_launch(
            dataset=str(dataset),
            task_id="missing-task",
            jobs_dir="<private-jobs-dir>",
            job_name="terminal_bench_missing_material_env_guard_smoke",
            loopx_mode="codex_loopx",
            loopx_goal_id="loopx-meta",
            loopx_cli_bridge_enabled=True,
            require_task_material_ready=True,
        )
        assert (
            strict_unknown_launch["first_blocker"]
            == "task_material_not_cached_or_not_locally_resolved"
        ), strict_unknown_launch
        assert strict_unknown_launch["ready"] is False, strict_unknown_launch
        strict_unknown_summary = summarize_terminal_bench_private_runner_launch(
            strict_unknown_launch
        )
        assert strict_unknown_summary["task_material_readiness_checked"] is False, strict_unknown_summary
        assert strict_unknown_summary["task_material_ready_required"] is True, strict_unknown_summary
        assert strict_unknown_summary["task_material_ready"] is None, strict_unknown_summary
        assert (
            strict_unknown_summary["task_material_readiness_status"]
            == "not_cached_or_not_locally_resolved"
        ), strict_unknown_summary
        assert strict_unknown_summary["raw_paths_recorded"] is False, strict_unknown_summary

    previous = os.environ.get("CODEX_FORCE_AUTH_JSON")
    os.environ["CODEX_FORCE_AUTH_JSON"] = "****"
    try:
        env = build_terminal_bench_private_runner_env()
    finally:
        if previous is None:
            os.environ.pop("CODEX_FORCE_AUTH_JSON", None)
        else:
            os.environ["CODEX_FORCE_AUTH_JSON"] = previous

    assert env.get("CODEX_FORCE_AUTH_JSON") != "****", env.get("CODEX_FORCE_AUTH_JSON")

    replay = normalize_terminal_bench_private_runner_invocation(
        [
            "uvx",
            "harbor",
            "run",
            "--agent-env",
            "CODEX_FORCE_AUTH_JSON=****",
        ]
    )
    assert "CODEX_FORCE_AUTH_JSON=true" in replay, replay
    assert "CODEX_FORCE_AUTH_JSON=****" not in replay, replay

    expect_raises(
        lambda: normalize_terminal_bench_private_runner_invocation(
            ["uvx", "--agent-env", "OPENAI_API_KEY=****"]
        ),
        "OPENAI_API_KEY",
    )
    expect_raises(
        lambda: normalize_terminal_bench_private_runner_invocation(
            ["uvx", "--agent-env", "CODEX_FORCE_AUTH_JSON=sk-placeholder"]
        ),
        "CODEX_FORCE_AUTH_JSON",
    )

    generated = build_terminal_bench_managed_harbor_command(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
        loopx_mode="codex_loopx",
        loopx_goal_id="loopx-meta",
        loopx_cli_bridge_enabled=True,
        agent_timeout_multiplier=4,
    )
    assert "CODEX_FORCE_AUTH_JSON=true" in generated, generated
    assert "CODEX_FORCE_AUTH_JSON=****" not in generated, generated

    baseline_generated = build_terminal_bench_managed_harbor_command(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_hardened_baseline_env_guard_smoke",
        loopx_mode="hardened_codex_baseline",
        loopx_ablation_mode="hardened_codex_baseline",
        loopx_access_packet_mode="none",
        loopx_cli_bridge_enabled=False,
        agent_timeout_multiplier=4,
    )
    assert "--agent-import-path" in baseline_generated, baseline_generated
    assert "loopx_mode=hardened_codex_baseline" in baseline_generated, baseline_generated
    assert "loopx_access_packet_mode=none" in baseline_generated, baseline_generated
    assert "loopx_cli_bridge_enabled=true" not in baseline_generated, baseline_generated
    assert (
        "loopx_codex_install_strategy="
        + TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ) in baseline_generated, baseline_generated
    assert "--mounts" not in baseline_generated, baseline_generated
    assert "CODEX_FORCE_AUTH_JSON=true" in baseline_generated, baseline_generated

    launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
        loopx_mode="codex_loopx",
        loopx_goal_id="loopx-meta",
        loopx_cli_bridge_enabled=True,
        agent_timeout_multiplier=4,
        agent_setup_timeout_multiplier=3,
    )
    assert launch["schema_version"] == "terminal_bench_private_runner_launch_v0", launch
    assert launch["uses_private_runner_env"] is True, launch
    assert launch["argv"][0] == resolve_terminal_bench_runner_binary("uvx"), launch["argv"]
    assert launch["env"]["PATH"] == env["PATH"], launch["env"]["PATH"]
    assert str(REPO_ROOT) in launch["env"]["PYTHONPATH"].split(os.pathsep), launch["env"]["PYTHONPATH"]
    for expected_path in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin"):
        expected_path = str(Path(expected_path).expanduser())
        assert expected_path in launch["env"]["PATH"], launch["env"]["PATH"]
    assert launch["env"].get("CODEX_FORCE_AUTH_JSON") != "****", launch["env"].get("CODEX_FORCE_AUTH_JSON")
    assert launch["preflight_surface"]["boundary"]["no_upload"] is True, launch
    assert launch["ready"] == (
        launch["first_blocker"] == "ready_for_private_managed_no_upload_pilot_review"
    ), launch
    summary = summarize_terminal_bench_private_runner_launch(launch)
    assert summary["ready"] == launch["ready"], summary
    assert summary["first_blocker"] == launch["first_blocker"], summary
    assert summary["task_material_ready_required"] is False, summary
    assert summary["no_upload_boundary"] is True, summary
    assert summary["submit_eligible"] is False, summary
    assert summary["env_pythonpath_present"] is True, summary
    assert summary["loopx_project_root_pythonpath_present"] is True, summary
    assert summary["agent_name"] == "", summary
    assert summary["agent_import_path_present"] is True, summary
    assert summary["loopx_agent_kwargs_present"] is True, summary
    assert summary["loopx_worker_bridge_requested"] is True, summary
    timeout_policy = summary["timeout_multiplier_policy"]
    assert timeout_policy["schema_version"] == (
        "terminal_bench_launch_timeout_multiplier_policy_v0"
    ), timeout_policy
    assert timeout_policy["any_timeout_multiplier_present"] is True, timeout_policy
    assert timeout_policy["non_default_timeout_multiplier_present"] is True, timeout_policy
    assert timeout_policy["agent_setup_timeout_multiplier_present"] is True, timeout_policy
    assert timeout_policy["changes_official_benchmark_timeout"] is True, timeout_policy
    assert timeout_policy["leaderboard_claim_allowed"] is False, timeout_policy
    assert timeout_policy["raw_argv_recorded"] is False, timeout_policy
    assert timeout_policy["multipliers"]["agent_timeout_multiplier"] == 4, timeout_policy
    assert timeout_policy["multipliers"]["agent_setup_timeout_multiplier"] == 3, timeout_policy
    readiness = summary["agent_setup_readiness"]
    assert readiness["schema_version"] == "terminal_bench_agent_setup_readiness_v0", readiness
    assert readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ), readiness
    assert readiness["managed_codex_agent"] is True, readiness
    assert readiness["worker_bridge_requested"] is True, readiness
    assert readiness["runtime_codex_install_allowed"] is True, readiness
    assert readiness["fail_fast_install_strategy"] is False, readiness
    assert readiness["setup_timeout_budget_explicit"] is True, readiness
    assert readiness["agent_setup_timeout_multiplier"] == 3, readiness
    assert readiness["same_task_repeat_after_setup_timeout_allowed"] is False, readiness
    assert readiness["first_blocker"] == (
        "runtime_codex_install_can_exceed_setup_budget"
    ), readiness
    assert readiness["raw_logs_read"] is False, readiness
    assert readiness["credential_values_recorded"] is False, readiness
    launch_compact = compact_benchmark_run(
        {
            "schema_version": "benchmark_run_v0",
            "private_runner_launch_summary": summary,
        }
    )
    compact_policy = launch_compact["private_runner_launch_summary"][
        "timeout_multiplier_policy"
    ]
    assert compact_policy["agent_setup_timeout_multiplier_present"] is True, compact_policy
    assert compact_policy["multipliers"]["agent_setup_timeout_multiplier"] == 3, compact_policy
    assert compact_policy["raw_argv_recorded"] is False, compact_policy
    compact_readiness = launch_compact["private_runner_launch_summary"][
        "agent_setup_readiness"
    ]
    assert compact_readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ), compact_readiness
    assert compact_readiness[
        "same_task_repeat_after_setup_timeout_allowed"
    ] is False, compact_readiness
    assert compact_readiness["raw_logs_read"] is False, compact_readiness

    relative_jobs_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="relative-private-jobs",
        job_name="terminal_bench_relative_jobs_dir_env_guard_smoke",
        loopx_mode="codex_loopx",
        loopx_goal_id="loopx-meta",
        loopx_cli_bridge_enabled=True,
    )
    jobs_dir_index = relative_jobs_launch["argv"].index("--jobs-dir") + 1
    assert relative_jobs_launch["argv"][jobs_dir_index] == str(
        Path("relative-private-jobs").resolve()
    ), relative_jobs_launch["argv"]

    fail_fast_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_fail_fast_setup_env_guard_smoke",
        loopx_mode="codex_loopx",
        loopx_goal_id="loopx-meta",
        loopx_cli_bridge_enabled=True,
        agent_timeout_multiplier=4,
        agent_setup_timeout_multiplier=4,
        codex_install_strategy=TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
    )
    assert (
        "loopx_codex_install_strategy="
        + TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ) in fail_fast_launch["argv"], fail_fast_launch["argv"]
    fail_fast_summary = summarize_terminal_bench_private_runner_launch(fail_fast_launch)
    fail_fast_readiness = fail_fast_summary["agent_setup_readiness"]
    assert fail_fast_readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ), fail_fast_readiness
    assert fail_fast_readiness["runtime_codex_install_allowed"] is False, fail_fast_readiness
    assert fail_fast_readiness["fail_fast_install_strategy"] is True, fail_fast_readiness
    assert fail_fast_readiness["setup_timeout_budget_explicit"] is True, fail_fast_readiness
    assert fail_fast_readiness["codex_preflight_timeout_explicit"] is False, fail_fast_readiness
    assert fail_fast_readiness[
        "same_task_repeat_after_setup_timeout_allowed"
    ] is False, fail_fast_readiness
    assert (
        fail_fast_readiness["first_blocker"] == "codex_preflight_timeout_missing"
    ), fail_fast_readiness

    repair_profile_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_setup_timeout_repair_profile_env_guard_smoke",
        mode="codex-goal-mode",
        setup_timeout_repair_profile=True,
    )
    assert (
        "loopx_codex_install_strategy="
        + TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ) in repair_profile_launch["argv"], repair_profile_launch["argv"]
    assert "--agent-timeout-multiplier" in repair_profile_launch["argv"], repair_profile_launch["argv"]
    assert "--agent-setup-timeout-multiplier" in repair_profile_launch["argv"], repair_profile_launch["argv"]
    assert (
        "loopx_codex_preflight_timeout_sec="
        f"{TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC}"
    ) in repair_profile_launch["argv"], repair_profile_launch["argv"]
    repair_profile_summary = summarize_terminal_bench_private_runner_launch(
        repair_profile_launch
    )
    assert repair_profile_summary["setup_timeout_repair_profile"] is True, repair_profile_summary
    repair_profile = repair_profile_summary["repair_profile"]
    assert repair_profile["schema_version"] == (
        "terminal_bench_setup_timeout_repair_profile_v0"
    ), repair_profile
    assert repair_profile["required_launch_overrides"]["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ), repair_profile
    assert repair_profile["required_launch_overrides"]["agent_timeout_multiplier"] == 8, repair_profile
    assert repair_profile["required_launch_overrides"][
        "agent_setup_timeout_multiplier"
    ] == 8, repair_profile
    assert repair_profile["required_launch_overrides"][
        "codex_preflight_timeout_sec"
    ] == TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC, repair_profile
    assert repair_profile["disallowed_launch_overrides"]["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ), repair_profile

    default_goal_mode_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_default_two_hour_goal_mode_env_guard_smoke",
        mode="codex-goal-mode",
    )
    assert "--agent-timeout-multiplier" in default_goal_mode_launch["argv"], default_goal_mode_launch["argv"]
    assert (
        default_goal_mode_launch["argv"][
            default_goal_mode_launch["argv"].index("--agent-timeout-multiplier") + 1
        ]
        == "8"
    ), default_goal_mode_launch["argv"]
    assert "--agent-setup-timeout-multiplier" in default_goal_mode_launch["argv"], default_goal_mode_launch["argv"]
    assert (
        default_goal_mode_launch["argv"][
            default_goal_mode_launch["argv"].index("--agent-setup-timeout-multiplier") + 1
        ]
        == "8"
    ), default_goal_mode_launch["argv"]
    repair_profile_readiness = repair_profile_summary["agent_setup_readiness"]
    assert repair_profile_readiness["setup_timeout_repair_profile"] is True, repair_profile_readiness
    assert repair_profile_readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ), repair_profile_readiness
    assert repair_profile_readiness[
        "same_task_repeat_after_setup_timeout_allowed"
    ] is False, repair_profile_readiness
    assert repair_profile_readiness[
        "codex_preflight_timeout_explicit"
    ] is True, repair_profile_readiness
    assert repair_profile_readiness["codex_preflight_timeout_sec"] == (
        TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC
    ), repair_profile_readiness
    assert repair_profile_readiness["first_blocker"] == (
        "codex_worker_materialization_strategy_missing"
    ), repair_profile_readiness
    assert repair_profile_launch["ready"] is False, repair_profile_launch
    assert repair_profile_launch["first_blocker"] == (
        "codex_worker_materialization_strategy_missing"
    ), repair_profile_launch

    materialized_profile_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_setup_timeout_materialized_profile_env_guard_smoke",
        mode="codex-goal-mode",
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=(
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
        ),
    )
    assert (
        "loopx_worker_codex_materialization_strategy="
        + TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
    ) in materialized_profile_launch["argv"], materialized_profile_launch["argv"]
    materialized_profile_summary = summarize_terminal_bench_private_runner_launch(
        materialized_profile_launch
    )
    materialized_readiness = materialized_profile_summary["agent_setup_readiness"]
    assert materialized_readiness[
        "worker_path_preprovisioned_declared"
    ] is True, materialized_readiness
    assert materialized_readiness[
        "same_task_repeat_after_setup_timeout_allowed"
    ] is True, materialized_readiness
    assert materialized_readiness["first_blocker"] == (
        "ready_for_fail_fast_codex_setup_probe"
    ), materialized_readiness

    runtime_extended_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_setup_timeout_runtime_extended_env_guard_smoke",
        mode="codex-goal-mode",
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=(
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
        ),
    )
    assert (
        "loopx_worker_codex_materialization_strategy="
        + TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    ) in runtime_extended_launch["argv"], runtime_extended_launch["argv"]
    assert "--allow-environment-host" in runtime_extended_launch["argv"], (
        runtime_extended_launch["argv"]
    )
    runtime_extended_summary = summarize_terminal_bench_private_runner_launch(
        runtime_extended_launch
    )
    assert (
        runtime_extended_summary["codex_runtime_install_network_allowlist_present"]
        is True
    ), runtime_extended_summary
    assert runtime_extended_summary["environment_host_allowlist_count"] >= 3, (
        runtime_extended_summary
    )
    runtime_extended_readiness = runtime_extended_summary["agent_setup_readiness"]
    assert runtime_extended_readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ), runtime_extended_readiness
    assert runtime_extended_readiness[
        "runtime_install_extended_setup_declared"
    ] is True, runtime_extended_readiness
    assert runtime_extended_readiness[
        "same_task_repeat_after_setup_timeout_allowed"
    ] is True, runtime_extended_readiness
    assert runtime_extended_readiness["first_blocker"] == (
        "ready_for_runtime_codex_materialization_probe"
    ), runtime_extended_readiness
    assert runtime_extended_launch["ready"] is True, runtime_extended_launch
    runtime_extended_profile = runtime_extended_summary["repair_profile"]
    assert runtime_extended_profile["required_launch_overrides"][
        "codex_install_strategy"
    ] == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    assert runtime_extended_profile["required_launch_overrides"][
        "worker_codex_materialization_strategy"
    ] == TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    assert "codex_preflight_timeout_sec" not in runtime_extended_profile[
        "required_launch_overrides"
    ], runtime_extended_profile

    runtime_probe_launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_worker_materialization_probe_env_guard_smoke",
        mode="codex-goal-mode",
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=(
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
        ),
        worker_materialization_probe_only=True,
    )
    assert (
        "loopx_worker_materialization_probe_only=true"
        in runtime_probe_launch["argv"]
    ), runtime_probe_launch["argv"]
    runtime_probe_summary = summarize_terminal_bench_private_runner_launch(
        runtime_probe_launch
    )
    assert runtime_probe_summary["worker_materialization_probe_only"] is True, (
        runtime_probe_summary
    )
    assert runtime_probe_summary["agent_setup_readiness"][
        "worker_materialization_probe_only"
    ] is True, runtime_probe_summary
    assert runtime_probe_summary["agent_setup_readiness"]["first_blocker"] == (
        "ready_for_runtime_codex_materialization_probe"
    ), runtime_probe_summary

    worker_probe_payload = launch_terminal_bench_worker_materialization_probe(
        jobs_dir="<private-jobs-dir>",
        run_root="terminal-bench-worker-materialization-probe-smoke",
        job_name="terminal_bench_worker_materialization_probe_smoke",
        wait_seconds=0,
        execute=False,
    )
    assert worker_probe_payload["schema_version"] == (
        "terminal_bench_worker_materialization_probe_launch_v0"
    ), worker_probe_payload
    assert worker_probe_payload["dry_run"] is True, worker_probe_payload
    assert worker_probe_payload["process_started"] is False, worker_probe_payload
    assert worker_probe_payload["command_shape"][
        "worker_materialization_probe_only"
    ] is True, worker_probe_payload
    assert worker_probe_payload["command_shape"]["upload_flag_present"] is False, worker_probe_payload
    assert worker_probe_payload["boundary"]["no_upload"] is True, worker_probe_payload
    assert worker_probe_payload["boundary"]["submit_eligible"] is False, worker_probe_payload
    assert worker_probe_payload["boundary"][
        "task_solver_invoked_by_probe"
    ] is False, worker_probe_payload
    assert worker_probe_payload["boundary"]["model_api_expected"] is False, worker_probe_payload
    assert worker_probe_payload["boundary"]["raw_logs_read"] is False, worker_probe_payload
    assert worker_probe_payload["boundary"]["command_argv_recorded"] is False, worker_probe_payload
    assert worker_probe_payload["launch_summary"][
        "worker_materialization_probe_only"
    ] is True, worker_probe_payload
    assert worker_probe_payload["launch_summary"]["agent_setup_readiness"][
        "worker_materialization_probe_only"
    ] is True, worker_probe_payload
    worker_probe_readiness = worker_probe_payload["launch_summary"][
        "agent_setup_readiness"
    ]
    assert worker_probe_readiness["codex_install_strategy"] == (
        "require_existing_codex"
    ), worker_probe_readiness
    assert worker_probe_readiness["worker_codex_materialization_strategy"] == (
        TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
    ), worker_probe_readiness
    assert (
        worker_probe_readiness["first_blocker"]
        == "ready_for_fail_fast_codex_setup_probe"
    ), worker_probe_readiness
    assert worker_probe_readiness["setup_materialization_blocks_launch"] is False, (
        worker_probe_readiness
    )

    case_run_payload = launch_terminal_bench_case_run(
        jobs_dir="<private-jobs-dir>",
        run_root="terminal-bench-case-run-launch-smoke",
        job_name="terminal_bench_case_run_launch_smoke",
        mode="codex-goal-mode",
        task_id="multi-source-data-merger",
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=(
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
        ),
        wait_seconds=0,
        execute=False,
    )
    assert case_run_payload["schema_version"] == (
        "terminal_bench_case_run_launch_v0"
    ), case_run_payload
    assert case_run_payload["dry_run"] is True, case_run_payload
    assert case_run_payload["process_started"] is False, case_run_payload
    assert case_run_payload["materialization_wait_seconds"] == 0, case_run_payload
    assert case_run_payload["materialization_wait_timed_out"] is False, case_run_payload
    assert case_run_payload["command_shape"][
        "worker_materialization_probe_only"
    ] is False, case_run_payload
    assert case_run_payload["command_shape"]["upload_flag_present"] is False, case_run_payload
    assert case_run_payload["boundary"]["no_upload"] is True, case_run_payload
    assert case_run_payload["boundary"]["submit_eligible"] is False, case_run_payload
    assert case_run_payload["boundary"]["task_solver_invoked"] is False, case_run_payload
    assert case_run_payload["boundary"]["model_api_expected"] is False, case_run_payload
    assert case_run_payload["boundary"]["raw_logs_read"] is False, case_run_payload
    assert case_run_payload["boundary"]["command_argv_recorded"] is False, case_run_payload
    assert case_run_payload["run_permission_policy"]["schema_version"] == (
        "run_permission_policy_v0"
    ), case_run_payload
    assert case_run_payload["run_permission_policy"]["policy_id"] == (
        "terminal_bench_case_run_no_upload_policy"
    ), case_run_payload
    assert case_run_payload["run_permission_policy"]["no_upload_required"] is True, (
        case_run_payload
    )
    assert case_run_payload["run_permission_policy"]["submit_allowed"] is False, (
        case_run_payload
    )
    assert case_run_payload["run_permission_policy"][
        "leaderboard_claim_allowed"
    ] is False, case_run_payload
    assert case_run_payload["run_permission_quota_projection"][
        "schema_version"
    ] == "run_permission_quota_projection_v0", case_run_payload
    assert case_run_payload["run_permission_quota_projection"][
        "delivery_allowed"
    ] is True, case_run_payload
    assert case_run_payload["run_permission_quota_projection"][
        "compact_observation_only"
    ] is True, case_run_payload
    assert_no_execution_attempt_accounting(case_run_payload)
    assert case_run_payload["launch_summary"][
        "worker_materialization_probe_only"
    ] is False, case_run_payload
    assert case_run_payload["launch_summary"]["agent_setup_readiness"][
        "first_blocker"
    ] == "ready_for_runtime_codex_materialization_probe", case_run_payload

    managed_case_run_payload = launch_terminal_bench_case_run(
        jobs_dir="<private-jobs-dir>",
        run_root="terminal-bench-managed-case-run-launch-smoke",
        job_name="terminal_bench_managed_case_run_launch_smoke",
        mode="loopx-managed-codex",
        task_id="multi-source-data-merger",
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=(
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
        ),
        wait_seconds=0,
        execute=False,
    )
    assert managed_case_run_payload["ok"] is True, managed_case_run_payload
    assert managed_case_run_payload["dry_run"] is True, managed_case_run_payload
    assert managed_case_run_payload["process_started"] is False, managed_case_run_payload
    assert managed_case_run_payload["command_shape"][
        "agent_import_path_present"
    ] is True, managed_case_run_payload
    assert managed_case_run_payload["boundary"]["no_upload"] is True, (
        managed_case_run_payload
    )
    assert managed_case_run_payload["boundary"]["task_solver_invoked"] is False, (
        managed_case_run_payload
    )
    assert managed_case_run_payload["run_permission_policy"]["schema_version"] == (
        "run_permission_policy_v0"
    ), managed_case_run_payload
    assert managed_case_run_payload["run_permission_quota_projection"][
        "delivery_allowed"
    ] is True, managed_case_run_payload
    assert_no_execution_attempt_accounting(managed_case_run_payload)
    assert managed_case_run_payload["launch_summary"][
        "loopx_agent_kwargs_present"
    ] is True, managed_case_run_payload
    assert managed_case_run_payload["launch_summary"][
        "loopx_managed_codex_requested"
    ] is True, managed_case_run_payload

    with tempfile.TemporaryDirectory(prefix="loopx-prelaunch-block-") as tmp:
        prelaunch_root = Path(tmp) / "case-run"
        prelaunch_jobs = prelaunch_root / "jobs"
        blocked_case_run = launch_terminal_bench_case_run(
            jobs_dir=prelaunch_jobs,
            run_root=prelaunch_root,
            job_name="terminal_bench_case_run_prelaunch_block_smoke",
            mode="codex-goal-mode",
            task_id="multi-source-data-merger",
            setup_timeout_repair_profile=True,
            wait_seconds=0,
            materialization_wait_seconds=7,
            execute=True,
        )
        assert blocked_case_run["ok"] is True, blocked_case_run
        assert blocked_case_run["dry_run"] is False, blocked_case_run
        assert blocked_case_run["execution_ready"] is False, blocked_case_run
        assert blocked_case_run["launch_preflight_blocked"] is True, blocked_case_run
        assert blocked_case_run["launch_preflight_blocker"] == (
            "codex_worker_materialization_strategy_missing"
        ), blocked_case_run
        assert blocked_case_run["process_started"] is False, blocked_case_run
        assert blocked_case_run["process_state"] == "prelaunch_blocked", blocked_case_run
        assert blocked_case_run["ready_for_launch_state"] is False, blocked_case_run
        assert blocked_case_run["ready_for_compact_result_ingest"] is False, blocked_case_run
        assert blocked_case_run["ready_for_compact_failure_marker"] is True, blocked_case_run
        assert blocked_case_run["compact_failure_class"] == (
            "terminal_bench_prelaunch_readiness_blocked"
        ), blocked_case_run
        assert blocked_case_run["boundary"]["task_solver_invoked"] is False, blocked_case_run
        assert blocked_case_run["boundary"]["model_api_expected"] is False, blocked_case_run
        assert blocked_case_run["boundary"]["raw_logs_read"] is False, blocked_case_run
        assert blocked_case_run["boundary"]["upload_invoked"] is False, blocked_case_run
        prelaunch_marker = blocked_case_run["compact_failure_marker"]
        assert prelaunch_marker["lifecycle_stage"] == "job_materialization", prelaunch_marker
        assert prelaunch_marker["ledger_attempt_kind"] == "launcher_attempt", prelaunch_marker
        assert prelaunch_marker["case_attempt_countable"] is False, prelaunch_marker
        assert prelaunch_marker["benchmark_budget_countable"] is False, prelaunch_marker
        assert not (prelaunch_root / "terminal_bench_run.pid.private").exists()
        assert (prelaunch_root / "terminal_bench_run_launch.public.json").is_file()
        assert (prelaunch_root / "post_launch_summary.public.json").is_file()
        blocked_rendered = json.dumps(blocked_case_run, sort_keys=True)
        assert str(tmp) not in blocked_rendered, blocked_case_run

    with tempfile.TemporaryDirectory(prefix="loopx-existing-job-root-") as tmp:
        collision_root = Path(tmp) / "case-run"
        collision_jobs = collision_root / "jobs"
        collision_job_name = "terminal_bench_existing_stale_job_root_smoke"
        collision_job_root = collision_jobs / collision_job_name
        collision_job_root.mkdir(parents=True)
        (collision_job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        (collision_job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "updated_at": "2026-06-15T00:00:00Z",
                    "finished_at": None,
                    "stats": {
                        "n_completed_trials": 0,
                        "n_errored_trials": 0,
                        "n_running_trials": 1,
                        "n_pending_trials": 0,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        collision_case_run = launch_terminal_bench_case_run(
            jobs_dir=collision_jobs,
            run_root=collision_root,
            job_name=collision_job_name,
            mode="codex-goal-mode",
            task_id="multi-source-data-merger",
            setup_timeout_repair_profile=True,
            worker_codex_materialization_strategy=(
                TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
            ),
            wait_seconds=0,
            materialization_wait_seconds=7,
            execute=True,
            command_override=[
                sys.executable,
                "-c",
                "raise SystemExit('must not launch when job root exists')",
            ],
        )
        assert collision_case_run["ok"] is True, collision_case_run
        assert collision_case_run["execution_ready"] is True, collision_case_run
        assert (
            collision_case_run["prelaunch_job_root_guard_triggered"] is True
        ), collision_case_run
        assert collision_case_run["process_started"] is False, collision_case_run
        assert collision_case_run["process_state"] == "prelaunch_blocked", (
            collision_case_run
        )
        assert collision_case_run["first_blocker"] == (
            "prelaunch_existing_stale_active_job_without_trial_result"
        ), collision_case_run
        guard = collision_case_run["prelaunch_job_root_guard"]
        assert guard["allowed"] is False, guard
        assert guard["existing_job_root_present"] is True, guard
        assert guard["existing_compact_failure_class"] == (
            "stale_active_job_without_trial_result"
        ), guard
        assert guard["existing_job_active_without_trial_result"] is True, guard
        assert guard["existing_job_stale_active_without_trial_result"] is True, guard
        assert guard["next_allowed_action"] == (
            "repair_result_finalization_closeout_contract_before_rerun"
        ), guard
        assert collision_case_run["ready_for_compact_failure_marker"] is True, (
            collision_case_run
        )
        assert collision_case_run["compact_failure_class"] == (
            "terminal_bench_prelaunch_existing_job_root_blocked"
        ), collision_case_run
        collision_marker = collision_case_run["compact_failure_marker"]
        assert collision_marker["lifecycle_stage"] == "job_materialization", (
            collision_marker
        )
        assert collision_marker["ledger_attempt_kind"] == "launcher_attempt", (
            collision_marker
        )
        assert collision_marker["case_attempt_countable"] is False, collision_marker
        assert collision_marker["benchmark_budget_countable"] is False, collision_marker
        assert collision_case_run["boundary"]["task_solver_invoked"] is False, (
            collision_case_run
        )
        assert collision_case_run["boundary"]["model_api_expected"] is False, (
            collision_case_run
        )
        assert collision_case_run["boundary"]["raw_logs_read"] is False, (
            collision_case_run
        )
        assert not (collision_root / "terminal_bench_run.pid.private").exists()
        assert (collision_root / "terminal_bench_run_launch.public.json").is_file()
        assert (collision_root / "post_launch_summary.public.json").is_file()
        collision_rendered = json.dumps(collision_case_run, sort_keys=True)
        assert str(tmp) not in collision_rendered, collision_case_run

    with tempfile.TemporaryDirectory(prefix="loopx-launch-materialization-") as tmp:
        materialization_root = Path(tmp)
        materialization_jobs = materialization_root / "jobs"
        materialization_jobs.mkdir()
        failing_process = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        failed_materialization = wait_for_terminal_bench_launch_materialization(
            process=failing_process,
            jobs_dir=materialization_jobs,
            job_name="terminal_bench_missing_job_root_smoke",
            wait_seconds=2,
        )
        failing_process.wait(timeout=5)
        assert failed_materialization["schema_version"] == (
            "terminal_bench_launch_materialization_observation_v0"
        ), failed_materialization
        assert failed_materialization["process_state"] == "ended", failed_materialization
        assert failed_materialization["materialized"] is False, failed_materialization
        assert failed_materialization["terminal_compact_failure"] is True, failed_materialization
        assert failed_materialization["compact_failure_class"] == (
            "detached_worker_ended_without_job_root"
        ), failed_materialization
        failed_post_launch = failed_materialization["post_launch_materialization"]
        assert failed_post_launch["ready_for_compact_failure_marker"] is True, failed_post_launch
        assert failed_post_launch["compact_failure_marker"][
            "launch_state_countable"
        ] is False, failed_post_launch
        assert failed_post_launch["compact_failure_marker"]["ledger_attempt_kind"] == (
            "launcher_attempt"
        ), failed_post_launch
        assert failed_post_launch["compact_failure_marker"][
            "case_attempt_countable"
        ] is False, failed_post_launch
        assert failed_post_launch["compact_failure_marker"][
            "benchmark_budget_countable"
        ] is False, failed_post_launch
        assert failed_post_launch["compact_failure_marker"]["next_allowed_action"] == (
            "repair_job_materialization_before_baseline_rerun"
        ), failed_post_launch
        assert failed_materialization["read_boundary"]["raw_logs_read"] is False, failed_materialization
        assert failed_materialization["read_boundary"]["command_line_read"] is False, failed_materialization

        ready_job_name = "terminal_bench_ready_job_root_smoke"
        ready_job_root = materialization_jobs / ready_job_name
        ready_job_root.mkdir()
        (ready_job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        ready_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready_materialization = wait_for_terminal_bench_launch_materialization(
            process=ready_process,
            jobs_dir=materialization_jobs,
            job_name=ready_job_name,
            wait_seconds=2,
        )
        ready_process.terminate()
        ready_process.wait(timeout=5)
        assert ready_materialization["materialized"] is True, ready_materialization
        assert ready_materialization["terminal_compact_failure"] is False, ready_materialization
        assert ready_materialization["post_launch_materialization"][
            "ready_for_launch_state"
        ] is True, ready_materialization

        ended_active_job_name = "terminal_bench_ended_active_no_trial_smoke"
        ended_active_job_root = materialization_jobs / ended_active_job_name
        ended_active_job_root.mkdir()
        (ended_active_job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        (ended_active_job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": None,
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 0,
                        "n_errored_trials": 0,
                        "n_running_trials": 0,
                        "n_pending_trials": 1,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        ended_active_process = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ended_active_process.wait(timeout=5)
        closeout_observation = observe_terminal_bench_post_materialization_closeout(
            process=ended_active_process,
            jobs_dir=materialization_jobs,
            job_name=ended_active_job_name,
            wait_seconds=2,
        )
        assert closeout_observation["process_state"] == "ended", closeout_observation
        assert closeout_observation["terminal_compact_failure"] is False, (
            closeout_observation
        )
        assert closeout_observation["compact_failure_class"] is None, closeout_observation
        assert closeout_observation["first_blocker"] == (
            "resume_materialized_active_job_without_trial_result"
        ), closeout_observation
        closeout_post_launch = closeout_observation["post_launch_materialization"]
        assert closeout_post_launch["ready_for_compact_failure_marker"] is False, (
            closeout_post_launch
        )
        assert closeout_post_launch["job_pending_trial_count"] == 1, (
            closeout_post_launch
        )
        assert closeout_post_launch["resume_recommended"] is True, closeout_post_launch
        assert closeout_post_launch["active_job_resume_contract"][
            "resume_recommended"
        ] is True, closeout_post_launch
        assert closeout_observation["read_boundary"]["raw_logs_read"] is False, (
            closeout_observation
        )
        assert closeout_observation["read_boundary"]["command_line_read"] is False, (
            closeout_observation
        )

        resume_case_name = "terminal_bench_resume_after_materialization_smoke"
        resume_start = materialization_root / "fake_harbor_start.py"
        resume_driver = materialization_root / "fake_harbor_resume.py"
        resume_start.write_text(
            """
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

jobs_dir = Path(sys.argv[1])
job_name = sys.argv[2]
job = jobs_dir / job_name
job.mkdir(parents=True, exist_ok=True)
(job / "config.json").write_text(json.dumps({"job_name": job_name}) + "\\n")
(job / "lock.json").write_text(json.dumps({"trials": [{"task": "compact"}]}) + "\\n")
(job / "result.json").write_text(json.dumps({
    "started_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "finished_at": None,
    "n_total_trials": 1,
    "stats": {
        "n_completed_trials": 0,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 1,
    },
}) + "\\n")
""".lstrip(),
            encoding="utf-8",
        )
        resume_driver.write_text(
            """
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

job = Path(sys.argv[1]) / sys.argv[2]
(job / "result.json").write_text(json.dumps({
    "started_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "finished_at": None,
    "n_total_trials": 1,
    "stats": {
        "n_completed_trials": 0,
        "n_errored_trials": 0,
        "n_running_trials": 1,
        "n_pending_trials": 0,
    },
}) + "\\n")
time.sleep(3)
""".lstrip(),
            encoding="utf-8",
        )
        resumed_case = launch_terminal_bench_case_run(
            jobs_dir=materialization_jobs,
            run_root=materialization_root / "resume-case-run",
            job_name=resume_case_name,
            mode="codex-goal-mode",
            task_id="multi-source-data-merger",
            setup_timeout_repair_profile=True,
            worker_codex_materialization_strategy=(
                TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
            ),
            wait_seconds=1,
            materialization_wait_seconds=2,
            resume_after_materialization=True,
            execute=True,
            command_override=[
                sys.executable,
                str(resume_start),
                str(materialization_jobs),
                resume_case_name,
            ],
            resume_command_override=[
                sys.executable,
                str(resume_driver),
                str(materialization_jobs),
                resume_case_name,
            ],
        )
        assert resumed_case["resume_after_materialization_attempted"] is True, (
            resumed_case
        )
        assert resumed_case["detached_process_group"] is True, resumed_case
        assert resumed_case["boundary"]["resume_invoked"] is True, resumed_case
        assert resumed_case["process_state"] == "running", resumed_case
        assert resumed_case["exit_code_attribution"] == (
            "terminal_bench_resume_process_still_running"
        ), resumed_case
        resume_observation = resumed_case[
            "post_materialization_resume_observation"
        ]
        assert resume_observation["process_started"] is True, resume_observation
        assert resume_observation["detached_process_group"] is True, (
            resume_observation
        )
        assert resume_observation["process_state"] == "running", resume_observation
        assert resume_observation["boundary"]["raw_logs_read"] is False, (
            resume_observation
        )
        resume_post_launch = resumed_case["post_launch_materialization"]
        assert resume_post_launch["job_running_trial_count"] == 1, (
            resume_post_launch
        )
        assert resume_post_launch["ready_for_compact_failure_marker"] is False, (
            resume_post_launch
        )
        rendered_resume = json.dumps(resumed_case, sort_keys=True)
        assert str(materialization_root) not in rendered_resume, resumed_case

    cli_profile = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "run",
            "terminal-bench",
            "--goal-id",
            "loopx-meta",
            "--mode",
            "codex-goal-mode",
            "--preflight-guard",
            "--setup-timeout-repair-profile",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_payload = json.loads(cli_profile.stdout)
    cli_benchmark_run = cli_payload["benchmark_run"]
    cli_summary = cli_benchmark_run["private_runner_launch_summary"]
    assert cli_summary["setup_timeout_repair_profile"] is True, cli_summary
    assert cli_summary["agent_setup_readiness"]["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ), cli_summary
    assert cli_benchmark_run["setup_timeout_repair_profile"][
        "required_launch_overrides"
    ]["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    ), cli_benchmark_run["setup_timeout_repair_profile"]
    assert cli_benchmark_run["setup_timeout_repair_profile"][
        "required_launch_overrides"
    ]["codex_preflight_timeout_sec"] == (
        TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC
    ), cli_benchmark_run["setup_timeout_repair_profile"]

    cli_runtime_profile = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "run",
            "terminal-bench",
            "--goal-id",
            "loopx-meta",
            "--mode",
            "codex-goal-mode",
            "--preflight-guard",
            "--setup-timeout-repair-profile",
            "--worker-codex-materialization-strategy",
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
            "--worker-materialization-probe-only",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_runtime_payload = json.loads(cli_runtime_profile.stdout)
    cli_runtime_run = cli_runtime_payload["benchmark_run"]
    cli_runtime_summary = cli_runtime_run["private_runner_launch_summary"]
    assert cli_runtime_summary["ready"] is True, cli_runtime_summary
    assert cli_runtime_summary["agent_setup_readiness"]["first_blocker"] == (
        "ready_for_runtime_codex_materialization_probe"
    ), cli_runtime_summary
    assert cli_runtime_summary["worker_materialization_probe_only"] is True, (
        cli_runtime_summary
    )
    assert cli_runtime_summary["agent_setup_readiness"][
        "worker_materialization_probe_only"
    ] is True, cli_runtime_summary
    assert cli_runtime_run["setup_timeout_repair_profile"][
        "required_launch_overrides"
    ]["worker_codex_materialization_strategy"] == (
        TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    ), cli_runtime_run["setup_timeout_repair_profile"]

    cli_worker_probe = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "launch-worker-materialization-probe",
            "terminal-bench",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--run-root",
            "terminal-bench-worker-materialization-probe-cli-smoke",
            "--job-name",
            "terminal_bench_worker_materialization_probe_cli_smoke",
            "--wait-seconds",
            "0",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_worker_probe_payload = json.loads(cli_worker_probe.stdout)
    assert cli_worker_probe_payload["ok"] is True, cli_worker_probe_payload
    assert cli_worker_probe_payload["dry_run"] is True, cli_worker_probe_payload
    assert cli_worker_probe_payload["process_started"] is False, cli_worker_probe_payload
    assert cli_worker_probe_payload["command_shape"][
        "worker_materialization_probe_only"
    ] is True, cli_worker_probe_payload
    cli_worker_probe_readiness = cli_worker_probe_payload["launch_summary"][
        "agent_setup_readiness"
    ]
    assert cli_worker_probe_readiness["codex_install_strategy"] == (
        "require_existing_codex"
    ), cli_worker_probe_readiness
    assert cli_worker_probe_readiness["worker_codex_materialization_strategy"] == (
        TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
    ), cli_worker_probe_readiness
    assert (
        cli_worker_probe_readiness["first_blocker"]
        == "ready_for_fail_fast_codex_setup_probe"
    ), cli_worker_probe_readiness
    assert cli_worker_probe_payload["boundary"]["no_upload"] is True, cli_worker_probe_payload
    assert cli_worker_probe_payload["boundary"][
        "task_solver_invoked_by_probe"
    ] is False, cli_worker_probe_payload
    assert cli_worker_probe_payload["boundary"]["raw_logs_read"] is False, cli_worker_probe_payload
    assert cli_worker_probe_payload["boundary"][
        "command_argv_recorded"
    ] is False, cli_worker_probe_payload

    cli_worker_runtime_probe = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "launch-worker-materialization-probe",
            "terminal-bench",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--run-root",
            "terminal-bench-worker-materialization-runtime-probe-cli-smoke",
            "--job-name",
            "terminal_bench_worker_materialization_runtime_probe_cli_smoke",
            "--worker-codex-materialization-strategy",
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
            "--wait-seconds",
            "0",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_worker_runtime_probe_payload = json.loads(cli_worker_runtime_probe.stdout)
    assert cli_worker_runtime_probe_payload["ok"] is True, cli_worker_runtime_probe_payload
    runtime_probe_readiness = cli_worker_runtime_probe_payload["launch_summary"][
        "agent_setup_readiness"
    ]
    assert runtime_probe_readiness["codex_install_strategy"] == (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ), runtime_probe_readiness
    assert runtime_probe_readiness["worker_codex_materialization_strategy"] == (
        TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    ), runtime_probe_readiness
    assert runtime_probe_readiness["first_blocker"] == (
        "ready_for_runtime_codex_materialization_probe"
    ), runtime_probe_readiness
    assert (
        cli_worker_runtime_probe_payload["boundary"]["task_solver_invoked_by_probe"]
        is False
    ), cli_worker_runtime_probe_payload

    cli_case_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "launch-terminal-bench-run",
            "terminal-bench",
            "--mode",
            "codex-goal-mode",
            "--include-task-name",
            "multi-source-data-merger",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--run-root",
            "terminal-bench-case-run-launch-cli-smoke",
            "--job-name",
            "terminal_bench_case_run_launch_cli_smoke",
            "--setup-timeout-repair-profile",
            "--worker-codex-materialization-strategy",
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
            "--wait-seconds",
            "0",
            "--materialization-wait-seconds",
            "7",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_case_payload = json.loads(cli_case_run.stdout)
    assert cli_case_payload["ok"] is True, cli_case_payload
    assert cli_case_payload["dry_run"] is True, cli_case_payload
    assert cli_case_payload["process_started"] is False, cli_case_payload
    assert cli_case_payload["materialization_wait_seconds"] == 7, cli_case_payload
    assert cli_case_payload["materialization_wait_timed_out"] is False, cli_case_payload
    assert cli_case_payload["command_shape"][
        "worker_materialization_probe_only"
    ] is False, cli_case_payload
    assert cli_case_payload["boundary"]["no_upload"] is True, cli_case_payload
    assert cli_case_payload["boundary"]["task_solver_invoked"] is False, cli_case_payload
    assert cli_case_payload["boundary"]["model_api_expected"] is False, cli_case_payload
    assert cli_case_payload["boundary"]["raw_logs_read"] is False, cli_case_payload
    assert cli_case_payload["boundary"]["command_argv_recorded"] is False, cli_case_payload

    cli_app_server_goal = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "launch-terminal-bench-run",
            "terminal-bench",
            "--mode",
            "codex-app-server-goal",
            "--include-task-name",
            "multi-source-data-merger",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--run-root",
            "terminal-bench-app-server-goal-launch-cli-smoke",
            "--job-name",
            "terminal_bench_app_server_goal_launch_cli_smoke",
            "--wait-seconds",
            "0",
            "--materialization-wait-seconds",
            "0",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_app_server_payload = json.loads(cli_app_server_goal.stdout)
    assert cli_app_server_payload["ok"] is True, cli_app_server_payload
    assert cli_app_server_payload["dry_run"] is True, cli_app_server_payload
    assert cli_app_server_payload["execution_ready"] is False, cli_app_server_payload
    assert cli_app_server_payload["first_blocker"] == (
        "terminal_bench_app_server_goal_turn_start_proof_missing"
    ), cli_app_server_payload
    assert cli_app_server_payload["launch_summary"][
        "codex_goal_mode_invocation_surface"
    ] == "codex_app_server_thread_goal_set_get", cli_app_server_payload
    assert cli_app_server_payload["launch_summary"][
        "codex_goal_mode_baseline_claim_allowed"
    ] is False, cli_app_server_payload
    assert cli_app_server_payload["boundary"]["task_solver_invoked"] is False, cli_app_server_payload
    assert cli_app_server_payload["boundary"]["model_api_expected"] is False, cli_app_server_payload

    cli_managed_case_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "launch-terminal-bench-run",
            "terminal-bench",
            "--mode",
            "loopx-managed-codex",
            "--include-task-name",
            "multi-source-data-merger",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--run-root",
            "terminal-bench-managed-case-run-launch-cli-smoke",
            "--job-name",
            "terminal_bench_managed_case_run_launch_cli_smoke",
            "--setup-timeout-repair-profile",
            "--worker-codex-materialization-strategy",
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
            "--wait-seconds",
            "0",
            "--materialization-wait-seconds",
            "7",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    cli_managed_payload = json.loads(cli_managed_case_run.stdout)
    assert cli_managed_payload["ok"] is True, cli_managed_payload
    assert cli_managed_payload["dry_run"] is True, cli_managed_payload
    assert cli_managed_payload["process_started"] is False, cli_managed_payload
    assert cli_managed_payload["command_shape"][
        "agent_import_path_present"
    ] is True, cli_managed_payload
    assert cli_managed_payload["boundary"]["no_upload"] is True, cli_managed_payload
    assert cli_managed_payload["boundary"]["task_solver_invoked"] is False, (
        cli_managed_payload
    )
    assert cli_managed_payload["launch_summary"][
        "loopx_managed_codex_requested"
    ] is True, cli_managed_payload

    with tempfile.TemporaryDirectory(prefix="loopx-prelaunch-cli-block-") as tmp:
        cli_block_root = Path(tmp) / "case-run"
        cli_block = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "launch-terminal-bench-run",
                "terminal-bench",
                "--mode",
                "codex-goal-mode",
                "--include-task-name",
                "multi-source-data-merger",
                "--jobs-dir",
                str(cli_block_root / "jobs"),
                "--run-root",
                str(cli_block_root),
                "--job-name",
                "terminal_bench_case_run_prelaunch_cli_block_smoke",
                "--setup-timeout-repair-profile",
                "--execute",
                "--wait-seconds",
                "0",
                "--materialization-wait-seconds",
                "7",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        cli_block_payload = json.loads(cli_block.stdout)
        assert cli_block_payload["ok"] is True, cli_block_payload
        assert cli_block_payload["dry_run"] is False, cli_block_payload
        assert cli_block_payload["execution_ready"] is False, cli_block_payload
        assert cli_block_payload["launch_preflight_blocked"] is True, cli_block_payload
        assert cli_block_payload["launch_preflight_blocker"] == (
            "codex_worker_materialization_strategy_missing"
        ), cli_block_payload
        assert cli_block_payload["process_started"] is False, cli_block_payload
        assert cli_block_payload["process_state"] == "prelaunch_blocked", cli_block_payload
        assert cli_block_payload["compact_failure_marker"]["ledger_attempt_kind"] == (
            "launcher_attempt"
        ), cli_block_payload
        assert cli_block_payload["boundary"]["task_solver_invoked"] is False, cli_block_payload
        assert cli_block_payload["boundary"]["model_api_expected"] is False, cli_block_payload
        assert cli_block_payload["boundary"]["raw_logs_read"] is False, cli_block_payload
        assert not (cli_block_root / "terminal_bench_run.pid.private").exists()
        assert (cli_block_root / "terminal_bench_run_launch.public.json").is_file()
        assert (cli_block_root / "post_launch_summary.public.json").is_file()
        cli_block_rendered = json.dumps(cli_block_payload, sort_keys=True)
        assert str(tmp) not in cli_block_rendered, cli_block_payload

    with tempfile.TemporaryDirectory(prefix="loopx-worker-probe-poll-") as tmp:
        poll_root = Path(tmp) / "worker-probe"
        poll_jobs = poll_root / "jobs"
        poll_job_name = "terminal_bench_worker_probe_poll_smoke"
        poll_job_root = poll_jobs / poll_job_name
        poll_job_root.mkdir(parents=True)
        (poll_root / "worker_materialization_probe.pid.private").write_text(
            "99999999\n",
            encoding="utf-8",
        )
        (poll_job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        (poll_job_root / "result.json").write_text("{}\n", encoding="utf-8")
        poll_payload = poll_terminal_bench_worker_materialization_probe(
            jobs_dir=poll_jobs,
            run_root=poll_root,
            job_name=poll_job_name,
        )
        rendered_poll_payload = json.dumps(poll_payload, sort_keys=True)
        assert poll_payload["schema_version"] == (
            "terminal_bench_worker_materialization_probe_poll_v0"
        ), poll_payload
        assert poll_payload["process_state"] == "ended", poll_payload
        assert poll_payload["pid_state"]["pid_parse_ok"] is True, poll_payload
        assert poll_payload["ready_for_launch_state"] is True, poll_payload
        assert poll_payload["ready_for_compact_result_ingest"] is False, poll_payload
        assert poll_payload["ready_for_compact_failure_marker"] is True, poll_payload
        assert poll_payload["compact_failure_class"] == (
            "detached_worker_ended_without_trial_result"
        ), poll_payload
        assert poll_payload["boundary"]["raw_logs_read"] is False, poll_payload
        assert poll_payload["boundary"]["task_text_read"] is False, poll_payload
        assert poll_payload["boundary"]["command_line_read"] is False, poll_payload
        assert str(poll_root) not in rendered_poll_payload, rendered_poll_payload
        assert (poll_root / "worker_materialization_probe_poll.public.json").is_file()

        cli_poll = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "poll-worker-materialization-probe",
                "terminal-bench",
                "--jobs-dir",
                str(poll_jobs),
                "--run-root",
                str(poll_root),
                "--job-name",
                poll_job_name,
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        cli_poll_payload = json.loads(cli_poll.stdout)
        assert cli_poll_payload["ok"] is True, cli_poll_payload
        assert cli_poll_payload["process_state"] == "ended", cli_poll_payload
        assert cli_poll_payload["ready_for_compact_failure_marker"] is True, cli_poll_payload
        assert cli_poll_payload["boundary"]["raw_logs_read"] is False, cli_poll_payload
        assert cli_poll_payload["boundary"]["command_line_read"] is False, cli_poll_payload

    missing_materialization = summarize_terminal_bench_post_launch_materialization(
        "<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
    )
    assert missing_materialization["checked"] is False, missing_materialization
    assert missing_materialization["ready_for_launch_state"] is False, missing_materialization
    assert missing_materialization["first_blocker"] == "jobs_dir_placeholder", missing_materialization
    assert missing_materialization["raw_paths_recorded"] is False, missing_materialization

    probe_gate = {
        "schema_version": "terminal_bench_environment_setup_probe_gate_v0",
        "environment_setup_probe_allowed": True,
        "task_id": "mteb-retrieve",
        "probe_command_template": [
            "uvx",
            "--from",
            "git+https://example.invalid/harbor@fixture",
            "harbor",
            "run",
            "--include-task-name",
            "mteb-retrieve",
            "--agent",
            "nop",
            "--disable-verification",
            "--jobs-dir",
            "<private-jobs-dir>",
            "--job-name",
            "terminal_bench_env_probe_smoke",
        ],
        "probe_contract": {
            "agent": "nop",
            "codex_invoked": False,
            "verifier_disabled": True,
            "docker_task_may_start": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
    }
    with tempfile.TemporaryDirectory(prefix="loopx-probe-launch-") as tmp:
        probe_root = Path(tmp) / "probe"
        probe_payload = launch_terminal_bench_environment_setup_probe(
            gate=probe_gate,
            jobs_dir=probe_root / "jobs",
            run_root=probe_root,
            wait_seconds=5,
            execute=True,
            command_override=[
                sys.executable,
                "-c",
                "import sys; print('PRIVATE-LAUNCHER-STDOUT'); sys.exit(7)",
            ],
        )
        rendered_probe_payload = json.dumps(probe_payload, sort_keys=True)
        assert probe_payload["process_started"] is True, probe_payload
        assert probe_payload["process_state"] == "ended", probe_payload
        assert probe_payload["returncode"] == 7, probe_payload
        assert probe_payload["exit_code_attribution"] == "probe_process_nonzero_exit", probe_payload
        assert probe_payload["ready_for_compact_failure_marker"] is True, probe_payload
        assert probe_payload["compact_failure_class"] == (
            "detached_worker_ended_without_job_root"
        ), probe_payload
        assert probe_payload["boundary"]["raw_logs_read"] is False, probe_payload
        assert probe_payload["boundary"]["task_text_read"] is False, probe_payload
        assert probe_payload["boundary"]["command_argv_recorded"] is False, probe_payload
        assert "PRIVATE-LAUNCHER-STDOUT" not in rendered_probe_payload, rendered_probe_payload
        assert str(probe_root) not in rendered_probe_payload, rendered_probe_payload
        assert (probe_root / "launch_summary.public.json").is_file(), probe_payload

        gate_path = probe_root / "gate.public.json"
        gate_path.write_text(json.dumps(probe_gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        dry_run_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "launch-environment-setup-probe",
                "terminal-bench",
                "--gate-json",
                str(gate_path),
                "--run-root",
                str(probe_root / "dry-run"),
                "--jobs-dir",
                str(probe_root / "dry-run" / "jobs"),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        dry_run_payload = json.loads(dry_run_cli.stdout)
        assert dry_run_payload["ok"] is True, dry_run_payload
        assert dry_run_payload["dry_run"] is True, dry_run_payload
        assert dry_run_payload["process_started"] is False, dry_run_payload
        assert str(probe_root) not in dry_run_cli.stdout, dry_run_cli.stdout

    with tempfile.TemporaryDirectory(prefix="loopx-post-launch-ended-") as tmp:
        missing_jobs_dir = Path(tmp) / "missing-jobs"
        ended_without_jobs_dir = summarize_terminal_bench_post_launch_materialization(
            missing_jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
            detached_process_state="ended",
        )
        assert ended_without_jobs_dir["first_blocker"] == (
            "detached_worker_ended_without_jobs_dir"
        ), ended_without_jobs_dir
        assert ended_without_jobs_dir["ready_for_compact_failure_marker"] is True, (
            ended_without_jobs_dir
        )
        assert ended_without_jobs_dir["compact_failure_class"] == (
            "detached_worker_ended_without_jobs_dir"
        ), ended_without_jobs_dir
        marker = ended_without_jobs_dir["compact_failure_marker"]
        assert marker["launch_state_countable"] is False, marker
        assert marker["raw_logs_read"] is False, marker
        assert marker["raw_task_text_read"] is False, marker

    with tempfile.TemporaryDirectory(prefix="loopx-post-launch-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        jobs_dir.mkdir()
        ended_without_job_root = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
            detached_process_state="ended",
        )
        assert ended_without_job_root["first_blocker"] == (
            "detached_worker_ended_without_job_root"
        ), ended_without_job_root
        assert ended_without_job_root["ready_for_compact_failure_marker"] is True, (
            ended_without_job_root
        )
        assert ended_without_job_root["compact_failure_class"] == (
            "detached_worker_ended_without_job_root"
        ), ended_without_job_root
        marker = ended_without_job_root["compact_failure_marker"]
        assert marker["launch_state_countable"] is False, marker
        assert marker["raw_logs_read"] is False, marker
        assert marker["raw_task_text_read"] is False, marker

        job_root = jobs_dir / "terminal_bench_env_guard_smoke"
        job_root.mkdir(parents=True)
        job_root_pollable = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_pollable["jobs_dir_present"] is True, job_root_pollable
        assert job_root_pollable["job_root_present"] is True, job_root_pollable
        assert job_root_pollable["job_lock_present"] is False, job_root_pollable
        assert job_root_pollable["ready_for_launch_state"] is False, job_root_pollable
        assert job_root_pollable["first_blocker"] == "job_lock_missing", job_root_pollable

        blocked_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--require-ready-for-launch-state",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert blocked_cli.returncode == 1, blocked_cli.stdout + blocked_cli.stderr
        blocked_payload = json.loads(blocked_cli.stdout)
        assert blocked_payload["ok"] is False, blocked_payload
        assert blocked_payload["first_blocker"] == "job_lock_missing", blocked_payload
        assert str(jobs_dir) not in blocked_cli.stdout, blocked_cli.stdout

        (job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        job_root_pollable = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_pollable["job_lock_present"] is True, job_root_pollable
        assert job_root_pollable["ready_for_launch_state"] is True, job_root_pollable
        assert job_root_pollable["ready_for_compact_result_ingest"] is False, job_root_pollable
        assert job_root_pollable["first_blocker"] == "ready_for_compact_polling", job_root_pollable
        assert job_root_pollable["raw_logs_read"] is False, job_root_pollable
        ready_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--require-ready-for-launch-state",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ready_cli.returncode == 0, ready_cli.stdout + ready_cli.stderr
        ready_payload = json.loads(ready_cli.stdout)
        assert ready_payload["ok"] is True, ready_payload
        assert ready_payload["ready_for_launch_state"] is True, ready_payload
        assert ready_payload["raw_paths_recorded"] is False, ready_payload
        assert str(jobs_dir) not in ready_cli.stdout, ready_cli.stdout

        (job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "updated_at": "2026-06-15T00:00:00Z",
                    "finished_at": None,
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 0,
                        "n_errored_trials": 0,
                        "n_running_trials": 1,
                        "n_pending_trials": 0,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        active_without_trial = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
            detached_process_state="ended",
        )
        assert active_without_trial["ready_for_launch_state"] is True, (
            active_without_trial
        )
        assert active_without_trial["ready_for_compact_result_ingest"] is False, (
            active_without_trial
        )
        assert active_without_trial["ready_for_compact_failure_marker"] is False, (
            active_without_trial
        )
        assert active_without_trial["job_active_without_trial_result"] is True, (
            active_without_trial
        )
        assert active_without_trial[
            "job_stale_active_without_trial_result"
        ] is True, active_without_trial
        assert active_without_trial["compact_monitor_class"] == (
            "stale_active_job_without_trial_result"
        ), active_without_trial
        assert active_without_trial["job_active_stale_seconds_threshold"] == 600, (
            active_without_trial
        )
        assert active_without_trial["job_running_trial_count"] == 1, (
            active_without_trial
        )
        assert active_without_trial["first_blocker"] == "ready_for_compact_polling", (
            active_without_trial
        )
        assert active_without_trial["stale_active_reconcile_requested"] is False, (
            active_without_trial
        )
        reconciled_stale_active = (
            summarize_terminal_bench_post_launch_materialization(
                jobs_dir,
                job_name="terminal_bench_env_guard_smoke",
                detached_process_state="ended",
                reconcile_stale_active=True,
            )
        )
        assert reconciled_stale_active["ready_for_launch_state"] is True, (
            reconciled_stale_active
        )
        assert (
            reconciled_stale_active["ready_for_compact_result_ingest"] is False
        ), reconciled_stale_active
        assert (
            reconciled_stale_active["ready_for_compact_failure_marker"] is True
        ), reconciled_stale_active
        assert reconciled_stale_active["first_blocker"] == (
            "stale_active_job_without_trial_result"
        ), reconciled_stale_active
        assert reconciled_stale_active["compact_failure_class"] == (
            "stale_active_job_without_trial_result"
        ), reconciled_stale_active
        assert reconciled_stale_active["stale_active_reconcile_requested"] is True, (
            reconciled_stale_active
        )
        stale_marker = reconciled_stale_active["compact_failure_marker"]
        assert stale_marker["schema_version"] == (
            "terminal_bench_compact_failure_marker_v0"
        ), stale_marker
        assert stale_marker["failure_class"] == (
            "stale_active_job_without_trial_result"
        ), stale_marker
        assert stale_marker["evidence_kind"] == (
            "compact_stale_active_job_reconciliation"
        ), stale_marker
        assert stale_marker["job_result_present"] is True, stale_marker
        assert stale_marker["job_result_finished"] is False, stale_marker
        assert stale_marker["job_running_trial_count"] == 1, stale_marker
        assert stale_marker["trial_result_present_count"] == 0, stale_marker
        assert stale_marker["terminal_closeout"] is True, stale_marker
        assert stale_marker["lifecycle_stage"] == "result_finalization", stale_marker
        assert stale_marker["ledger_attempt_kind"] == (
            "runner_closeout_attempt"
        ), stale_marker
        assert stale_marker["case_attempt_countable"] is False, stale_marker
        assert stale_marker["benchmark_budget_countable"] is False, stale_marker
        assert stale_marker["next_allowed_action"] == (
            "repair_result_finalization_closeout_contract_before_rerun"
        ), stale_marker
        assert stale_marker["raw_logs_read"] is False, stale_marker
        assert stale_marker["trajectory_read"] is False, stale_marker
        compact_stale = _compact_benchmark_post_launch_materialization(
            reconciled_stale_active
        )
        assert compact_stale["compact_monitor_class"] == (
            "stale_active_job_without_trial_result"
        ), compact_stale
        assert compact_stale["ready_for_compact_failure_marker"] is True, (
            compact_stale
        )
        assert compact_stale["stale_active_reconcile_requested"] is True, (
            compact_stale
        )
        assert compact_stale["job_stale_active_without_trial_result"] is True, (
            compact_stale
        )
        compact_marker = compact_stale["compact_failure_marker"]
        assert compact_marker["job_running_trial_count"] == 1, compact_marker
        assert compact_marker["trial_result_present_count"] == 0, compact_marker
        assert compact_marker["terminal_closeout"] is True, compact_marker
        assert compact_marker["ledger_attempt_kind"] == (
            "runner_closeout_attempt"
        ), compact_marker
        assert compact_marker["case_attempt_countable"] is False, compact_marker
        assert compact_marker["benchmark_budget_countable"] is False, compact_marker
        stale_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--format",
                "json",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--detached-process-state",
                "ended",
                "--reconcile-stale-active",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert stale_cli.returncode == 0, stale_cli.stdout + stale_cli.stderr
        stale_cli_payload = json.loads(stale_cli.stdout)
        assert stale_cli_payload["ready_for_compact_failure_marker"] is True, (
            stale_cli_payload
        )
        assert stale_cli_payload["compact_failure_class"] == (
            "stale_active_job_without_trial_result"
        ), stale_cli_payload
        assert str(jobs_dir) not in stale_cli.stdout, stale_cli.stdout
        (job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": None,
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 0,
                        "n_errored_trials": 0,
                        "n_running_trials": 0,
                        "n_pending_trials": 1,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        recent_reconciled_active = (
            summarize_terminal_bench_post_launch_materialization(
                jobs_dir,
                job_name="terminal_bench_env_guard_smoke",
                detached_process_state="ended",
                reconcile_stale_active=True,
            )
        )
        assert recent_reconciled_active["ready_for_launch_state"] is True, (
            recent_reconciled_active
        )
        assert recent_reconciled_active["job_active_without_trial_result"] is True, (
            recent_reconciled_active
        )
        assert recent_reconciled_active[
            "job_stale_active_without_trial_result"
        ] is False, recent_reconciled_active
        assert (
            recent_reconciled_active["ready_for_compact_failure_marker"] is False
        ), recent_reconciled_active
        assert "compact_failure_class" not in recent_reconciled_active, (
            recent_reconciled_active
        )
        assert recent_reconciled_active["first_blocker"] == (
            "resume_materialized_active_job_without_trial_result"
        ), recent_reconciled_active
        assert recent_reconciled_active["resume_recommended"] is True, (
            recent_reconciled_active
        )
        recent_resume_contract = recent_reconciled_active[
            "active_job_resume_contract"
        ]
        assert recent_resume_contract["resume_recommended"] is True, (
            recent_resume_contract
        )
        assert recent_resume_contract["next_action"] == (
            "run_no_upload_harbor_job_resume_before_terminal_failure_marker"
        ), recent_resume_contract
        assert recent_reconciled_active["compact_monitor_class"] == (
            "detached_worker_ended_active_without_trial_result"
        ), recent_reconciled_active
        recent_gate = build_terminal_bench_result_finalization_gate(
            recent_reconciled_active
        )
        assert recent_gate["decision"] == (
            "resume_materialized_job_before_failure_marker"
        ), recent_gate
        assert recent_gate["first_blocker"] == (
            "resume_materialized_active_job_without_trial_result"
        ), recent_gate
        assert recent_gate["gate_conditions"]["resume_recommended"] is True, (
            recent_gate
        )
        resume_dry_run = resume_terminal_bench_materialized_job(
            jobs_dir=jobs_dir,
            run_root=Path(tmp) / "resume-dry-run",
            job_name="terminal_bench_env_guard_smoke",
            execute=False,
        )
        assert resume_dry_run["dry_run"] is True, resume_dry_run
        assert resume_dry_run["process_started"] is False, resume_dry_run
        assert resume_dry_run["command_shape"]["uses_harbor_job_resume"] is True, (
            resume_dry_run
        )
        assert resume_dry_run["command_shape"]["upload_flag_present"] is False, (
            resume_dry_run
        )
        assert resume_dry_run["boundary"]["no_upload"] is True, resume_dry_run
        assert resume_dry_run["boundary"]["raw_logs_read"] is False, resume_dry_run
        resume_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "benchmark",
                "resume-terminal-bench-job",
                "terminal-bench",
                "--format",
                "json",
                "--jobs-dir",
                str(jobs_dir),
                "--run-root",
                str(Path(tmp) / "resume-cli-dry-run"),
                "--job-name",
                "terminal_bench_env_guard_smoke",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert resume_cli.returncode == 0, resume_cli.stdout + resume_cli.stderr
        resume_cli_payload = json.loads(resume_cli.stdout)
        assert resume_cli_payload["dry_run"] is True, resume_cli_payload
        assert resume_cli_payload["command_shape"]["uses_harbor_job_resume"] is True, (
            resume_cli_payload
        )
        assert resume_cli_payload["boundary"]["upload_invoked"] is False, (
            resume_cli_payload
        )
        assert str(jobs_dir) not in resume_cli.stdout, resume_cli.stdout
        (job_root / "result.json").unlink()

        ended_without_result = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
            detached_process_state="ended",
        )
        assert ended_without_result["ready_for_launch_state"] is True, ended_without_result
        assert (
            ended_without_result["ready_for_compact_result_ingest"] is False
        ), ended_without_result
        assert (
            ended_without_result["ready_for_compact_failure_marker"] is True
        ), ended_without_result
        assert (
            ended_without_result["first_blocker"]
            == "detached_worker_ended_without_trial_result"
        ), ended_without_result
        assert ended_without_result["external_handle_terminal"] is True, ended_without_result
        assert (
            ended_without_result["raw_external_handle_payload_recorded"] is False
        ), ended_without_result
        marker = ended_without_result["compact_failure_marker"]
        assert marker["schema_version"] == "terminal_bench_compact_failure_marker_v0", marker
        assert marker["failure_class"] == "detached_worker_ended_without_trial_result", marker
        assert marker["job_result_present"] is False, marker
        assert marker["trial_result_present_count"] == 0, marker
        assert marker["terminal_closeout"] is True, marker
        assert marker["lifecycle_stage"] == "result_finalization", marker
        assert marker["ledger_attempt_kind"] == "runner_closeout_attempt", marker
        assert marker["case_attempt_countable"] is False, marker
        assert marker["benchmark_budget_countable"] is False, marker
        assert marker["raw_logs_read"] is False, marker
        assert marker["trajectory_read"] is False, marker

        terminal_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--detached-process-state",
                "ended",
                "--require-ready-for-launch-state",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert terminal_cli.returncode == 0, terminal_cli.stdout + terminal_cli.stderr
        terminal_payload = json.loads(terminal_cli.stdout)
        assert terminal_payload["ok"] is True, terminal_payload
        assert (
            terminal_payload["first_blocker"]
            == "detached_worker_ended_without_trial_result"
        ), terminal_payload
        assert terminal_payload["ready_for_compact_failure_marker"] is True, terminal_payload
        assert terminal_payload["raw_logs_read"] is False, terminal_payload
        assert str(jobs_dir) not in terminal_cli.stdout, terminal_cli.stdout

        summary_with_terminal_materialization = summarize_terminal_bench_private_runner_launch(
            launch,
            post_launch_materialization=ended_without_result,
        )
        compact_terminal = compact_benchmark_run(
            {
                "schema_version": "benchmark_run_v0",
                "private_runner_launch_summary": summary_with_terminal_materialization,
            }
        )
        compact_terminal_nested = compact_terminal["private_runner_launch_summary"][
            "post_launch_materialization"
        ]
        assert (
            compact_terminal_nested["first_blocker"]
            == "detached_worker_ended_without_trial_result"
        ), compact_terminal_nested
        assert (
            compact_terminal_nested["ready_for_compact_failure_marker"] is True
        ), compact_terminal_nested
        assert compact_terminal_nested["external_handle_terminal"] is True, compact_terminal_nested
        assert compact_terminal_nested["compact_failure_marker"]["failure_class"] == (
            "detached_worker_ended_without_trial_result"
        ), compact_terminal_nested

        probe_job_name = "terminal_bench_probe_contract_no_trial_smoke"
        probe_job_root = jobs_dir / probe_job_name
        probe_job_root.mkdir()
        probe_lock = {
            "invocation": ["harbor", "run", "--dataset", "terminal-bench"],
            "trials": [
                {
                    "task": {
                        "name": "good-task",
                        "source": "terminal-bench",
                    },
                    "agent": {
                        "name": "codex",
                        "import_path": (
                            "loopx.terminal_bench_agent:"
                            "GoalHarnessManagedCodex"
                        ),
                        "kwargs": {
                            "loopx_mode": "codex_goal_mode_baseline",
                            "loopx_access_packet_mode": "none",
                            "loopx_worker_materialization_probe_only": "true",
                        },
                    },
                }
            ],
        }
        (probe_job_root / "lock.json").write_text(
            json.dumps(probe_lock) + "\n",
            encoding="utf-8",
        )
        (probe_job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "finished_at": "2026-06-15T00:00:10Z",
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 0,
                        "n_errored_trials": 0,
                        "n_running_trials": 0,
                        "n_pending_trials": 0,
                        "n_cancelled_trials": 0,
                        "n_retries": 0,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        probe_contract_summary = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name=probe_job_name,
            detached_process_state="ended",
        )
        assert probe_contract_summary["ready_for_launch_state"] is True, (
            probe_contract_summary
        )
        assert probe_contract_summary["ready_for_compact_result_ingest"] is True, (
            probe_contract_summary
        )
        assert probe_contract_summary["ready_for_compact_failure_marker"] is True, (
            probe_contract_summary
        )
        assert probe_contract_summary["worker_materialization_probe_only"] is True, (
            probe_contract_summary
        )
        assert probe_contract_summary["probe_contract_result_present"] is True, (
            probe_contract_summary
        )
        assert (
            probe_contract_summary["first_blocker"]
            == "detached_worker_ended_without_trial_result"
        ), probe_contract_summary
        probe_marker = probe_contract_summary["compact_failure_marker"]
        assert probe_marker["worker_materialization_probe_only"] is True, probe_marker
        assert probe_marker["probe_contract_result_present"] is True, probe_marker
        assert probe_marker["ledger_attempt_kind"] == (
            "runner_closeout_attempt"
        ), probe_marker
        assert probe_marker["case_attempt_countable"] is False, probe_marker

        probe_benchmark_run = build_terminal_bench_harbor_result_benchmark_run(
            probe_job_root,
        )
        assert probe_benchmark_run["schema_version"] == "benchmark_run_v0", (
            probe_benchmark_run
        )
        assert probe_benchmark_run["worker_materialization_probe_only"] is True, (
            probe_benchmark_run
        )
        assert (
            probe_benchmark_run["worker_materialization_probe_no_trial_result"]
            is True
        ), probe_benchmark_run
        assert probe_benchmark_run["case_solution_attempted"] is False, (
            probe_benchmark_run
        )
        assert probe_benchmark_run["official_score"] is None, probe_benchmark_run
        assert (
            probe_benchmark_run["official_score_status"]
            == "not_applicable_worker_materialization_probe_no_trial_result"
        ), probe_benchmark_run
        assert probe_benchmark_run["official_task_score"]["kind"] == (
            "not_applicable_worker_materialization_probe_no_trial_result"
        ), probe_benchmark_run
        assert (
            probe_benchmark_run["worker_bridge_materialization_status"]
            == "probe_contract_no_trial_result"
        ), probe_benchmark_run
        assert (
            "worker_materialization_probe_no_trial_result"
            in probe_benchmark_run["failure_attribution_labels"]
        ), probe_benchmark_run
        assert (
            probe_benchmark_run["validation"]["trial_results_present"] is False
        ), probe_benchmark_run
        assert (
            probe_benchmark_run["validation"]["probe_contract_result_present"] is True
        ), probe_benchmark_run
        assert (
            probe_benchmark_run["progress"]["probe_contract_result_present"] is True
        ), probe_benchmark_run
        assert str(jobs_dir) not in json.dumps(probe_benchmark_run), (
            probe_benchmark_run
        )

        probe_trial_job_name = "terminal_bench_probe_contract_trial_smoke"
        probe_trial_job_root = jobs_dir / probe_trial_job_name
        probe_trial_job_root.mkdir()
        probe_trial_lock = {
            "invocation": ["harbor", "run", "--dataset", "terminal-bench"],
            "trials": [
                {
                    "task": {
                        "name": "good-task",
                        "source": "terminal-bench",
                    },
                    "agent": {
                        "name": "codex",
                        "import_path": (
                            "loopx.terminal_bench_agent:"
                            "GoalHarnessManagedCodex"
                        ),
                        "kwargs": {
                            "loopx_mode": "hardened_codex_baseline",
                            "loopx_access_packet_mode": "none",
                            "loopx_worker_materialization_probe_only": "true",
                        },
                    },
                }
            ],
        }
        (probe_trial_job_root / "lock.json").write_text(
            json.dumps(probe_trial_lock) + "\n",
            encoding="utf-8",
        )
        (probe_trial_job_root / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-06-15T00:00:00Z",
                    "finished_at": "2026-06-15T00:00:10Z",
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 1,
                        "n_errored_trials": 0,
                        "n_running_trials": 0,
                        "n_pending_trials": 0,
                        "n_cancelled_trials": 0,
                        "n_retries": 0,
                        "evals": {"reward": {"mean": 0.0}},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        probe_trial_root = probe_trial_job_root / "good-task__trial"
        probe_trial_agent_root = probe_trial_root / "agent"
        probe_trial_agent_root.mkdir(parents=True)
        (probe_trial_root / "result.json").write_text(
            json.dumps(
                {
                    "task_name": "good-task",
                    "trial_name": "good-task__trial",
                    "source": "terminal-bench",
                    "environment_setup": {
                        "started_at": "2026-06-15T00:00:00Z",
                        "finished_at": "2026-06-15T00:00:01Z",
                    },
                    "agent_setup": {
                        "started_at": "2026-06-15T00:00:01Z",
                        "finished_at": "2026-06-15T00:00:02Z",
                    },
                    "agent_execution": {
                        "started_at": "2026-06-15T00:00:02Z",
                        "finished_at": "2026-06-15T00:00:05Z",
                    },
                    "verifier": {
                        "started_at": "2026-06-15T00:00:05Z",
                        "finished_at": "2026-06-15T00:00:06Z",
                    },
                    "verifier_result": {"rewards": {"reward": 0.0}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (probe_trial_agent_root / "loopx-worker-setup-diagnostic.json").write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_worker_setup_diagnostic_v0",
                    "first_blocker": "codex_runtime_install_or_preflight_ok",
                    "pre_worker_startup_blocker": "none",
                    "worker_bridge_materialization_status": (
                        "worker_codex_materialization_verified"
                    ),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (probe_trial_agent_root / "loopx-worker-benchmark-run.json").write_text(
            json.dumps(
                {
                    "schema_version": "benchmark_run_v0",
                    "source_runner": "terminal_bench_worker_materialization_probe",
                    "benchmark_id": "terminal-bench-worker-materialization@v0",
                    "mode": "hardened_codex_baseline_worker_materialization_probe",
                    "worker_mode": "hardened_codex_baseline",
                    "worker_materialization_probe_only": True,
                    "worker_materialization_real_probe": True,
                    "real_run": False,
                    "submit_eligible": False,
                    "first_blocker": "none",
                    "repeat_blocked_by": "none",
                    "official_task_score": {
                        "kind": "not_run_worker_materialization_probe",
                        "value": None,
                        "passed": False,
                    },
                    "validation": {
                        "worker_bridge_materialized_when_required": True,
                        "worker_bridge_repeat_ready": True,
                        "no_model_task_solution_invoked": True,
                        "runner_return_completed_or_blocker_recorded": True,
                    },
                    "progress": {
                        "probe_contract_result_present": True,
                        "case_solution_attempted": False,
                    },
                    "worker_bridge_outcome": {
                        "runner_return_status": (
                            "worker_materialization_probe_completed"
                        ),
                        "official_score_status": (
                            "not_run_worker_materialization_probe"
                        ),
                        "worker_bridge_materialization_status": (
                            "worker_codex_materialization_verified"
                        ),
                        "worker_bridge_materialization_blocker": "none",
                        "next_action": "run the paired baseline or treatment slice",
                    },
                    "worker_bridge_materialization_status": (
                        "worker_codex_materialization_verified"
                    ),
                    "worker_bridge_materialization_blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        probe_trial_benchmark_run = build_terminal_bench_harbor_result_benchmark_run(
            probe_trial_job_root,
        )
        assert probe_trial_benchmark_run["source_runner"] == (
            "terminal_bench_worker_materialization_probe"
        ), probe_trial_benchmark_run
        assert probe_trial_benchmark_run["worker_materialization_probe_only"] is True, (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run[
            "worker_materialization_probe_contract_present"
        ] is True, probe_trial_benchmark_run
        assert probe_trial_benchmark_run[
            "worker_materialization_probe_no_trial_result"
        ] is False, probe_trial_benchmark_run
        assert probe_trial_benchmark_run["case_solution_attempted"] is False, (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run["real_run"] is False, (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run["official_score"] is None, (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run["official_score_status"] == (
            "not_run_worker_materialization_probe"
        ), probe_trial_benchmark_run
        assert probe_trial_benchmark_run["score_failure_attribution"] == (
            "not_applicable_worker_materialization_probe"
        ), probe_trial_benchmark_run
        assert probe_trial_benchmark_run["official_task_score"]["kind"] == (
            "not_run_worker_materialization_probe"
        ), probe_trial_benchmark_run
        assert probe_trial_benchmark_run[
            "worker_bridge_materialization_status"
        ] == "worker_codex_materialization_verified", probe_trial_benchmark_run
        assert probe_trial_benchmark_run["worker_bridge_materialization_blocker"] == (
            "none"
        ), probe_trial_benchmark_run
        assert probe_trial_benchmark_run["repeat_blocked_by"] == "none", (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run["worker_startup_blocker_count"] == 0, (
            probe_trial_benchmark_run
        )
        assert probe_trial_benchmark_run["worker_setup_diagnostic_blockers"] == [], (
            probe_trial_benchmark_run
        )
        assert "official_verifier_solution_failure" not in probe_trial_benchmark_run[
            "failure_attribution_labels"
        ], probe_trial_benchmark_run
        assert "pre_worker_startup_blocker_recorded" not in probe_trial_benchmark_run[
            "failure_attribution_labels"
        ], probe_trial_benchmark_run
        assert "codex_runtime_install_or_preflight_ok" not in probe_trial_benchmark_run[
            "failure_attribution_labels"
        ], probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["validation"]["trial_results_present"] is True
        ), probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["validation"]["probe_contract_result_present"]
            is True
        ), probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["validation"][
                "case_solution_attempted_or_not_required"
            ]
            is True
        ), probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["validation"][
                "case_solution_not_required_for_probe"
            ]
            is True
        ), probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["progress"]["probe_contract_result_present"]
            is True
        ), probe_trial_benchmark_run
        assert (
            probe_trial_benchmark_run["progress"]["case_solution_attempted"] is False
        ), probe_trial_benchmark_run

        (job_root / "result.json").write_text("{}\n", encoding="utf-8")
        trial_root = job_root / "good-task__trial"
        trial_root.mkdir()
        (trial_root / "result.json").write_text("{}\n", encoding="utf-8")
        job_root_complete = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_complete["ready_for_launch_state"] is True, job_root_complete
        assert job_root_complete["ready_for_compact_result_ingest"] is True, job_root_complete
        assert job_root_complete["trial_result_present_count"] == 1, job_root_complete
        assert job_root_complete["first_blocker"] == "ready_for_compact_result_ingest", job_root_complete

        summary_with_materialization = summarize_terminal_bench_private_runner_launch(
            launch,
            post_launch_materialization=job_root_complete,
        )
        nested = summary_with_materialization["post_launch_materialization"]
        assert nested["schema_version"] == "terminal_bench_post_launch_materialization_v0", nested
        assert nested["ready_for_launch_state"] is True, nested
        assert nested["raw_paths_recorded"] is False, nested
        compact = compact_benchmark_run(
            {
                "schema_version": "benchmark_run_v0",
                "private_runner_launch_summary": summary_with_materialization,
            }
        )
        compact_nested = compact["private_runner_launch_summary"][
            "post_launch_materialization"
        ]
        assert compact_nested["ready_for_launch_state"] is True, compact_nested
        assert compact_nested["raw_paths_recorded"] is False, compact_nested

    baseline_launch = build_terminal_bench_private_runner_launch(
        mode="hardened-codex",
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_hardened_baseline_env_guard_smoke",
        agent_timeout_multiplier=4,
    )
    assert baseline_launch["argv"][0] == resolve_terminal_bench_runner_binary("uvx"), baseline_launch["argv"]
    assert "--agent-import-path" in baseline_launch["argv"], baseline_launch["argv"]
    assert "loopx_mode=hardened_codex_baseline" in baseline_launch["argv"], baseline_launch["argv"]
    assert "--mounts" not in baseline_launch["argv"], baseline_launch["argv"]
    baseline_summary = summarize_terminal_bench_private_runner_launch(baseline_launch)
    assert baseline_summary["ready"] == baseline_launch["ready"], baseline_summary
    assert baseline_summary["first_blocker"] == baseline_launch["first_blocker"], baseline_summary
    assert baseline_summary["no_upload_boundary"] is True, baseline_summary
    assert baseline_summary["submit_eligible"] is False, baseline_summary
    assert baseline_summary["agent_import_path_present"] is True, baseline_summary
    assert baseline_summary["loopx_agent_kwargs_present"] is True, baseline_summary
    assert baseline_summary["loopx_worker_bridge_requested"] is False, baseline_summary

    goal_mode_launch = build_terminal_bench_private_runner_launch(
        mode="codex-goal-mode",
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_codex_goal_mode_baseline_env_guard_smoke",
        agent_timeout_multiplier=4,
        agent_setup_timeout_multiplier=4,
    )
    assert goal_mode_launch["argv"][0] == resolve_terminal_bench_runner_binary("uvx"), goal_mode_launch["argv"]
    assert "--agent-import-path" in goal_mode_launch["argv"], goal_mode_launch["argv"]
    assert "loopx_mode=codex_goal_mode_baseline" in goal_mode_launch["argv"], goal_mode_launch["argv"]
    assert "loopx_ablation_mode=codex_goal_mode_baseline" in goal_mode_launch["argv"], goal_mode_launch["argv"]
    assert "loopx_access_packet_mode=none" in goal_mode_launch["argv"], goal_mode_launch["argv"]
    assert "loopx_cli_bridge_enabled=true" not in goal_mode_launch["argv"], goal_mode_launch["argv"]
    assert "--mounts" not in goal_mode_launch["argv"], goal_mode_launch["argv"]
    goal_mode_summary = summarize_terminal_bench_private_runner_launch(goal_mode_launch)
    assert goal_mode_summary["ready"] == goal_mode_launch["ready"], goal_mode_summary
    assert goal_mode_summary["first_blocker"] == goal_mode_launch["first_blocker"], goal_mode_summary
    assert goal_mode_summary["codex_goal_mode_baseline_requested"] is True, goal_mode_summary
    assert goal_mode_summary["codex_goal_mode_invocation_surface"] == "slash_command", goal_mode_summary
    assert goal_mode_summary["codex_goal_mode_required_invocation_surface"] == (
        "codex_app_server_thread_goal_set_get"
    ), goal_mode_summary
    assert goal_mode_summary["codex_app_server_goal_proof_present"] is False, goal_mode_summary
    assert goal_mode_summary["codex_goal_mode_baseline_claim_allowed"] is False, goal_mode_summary
    assert goal_mode_summary["codex_goal_mode_baseline_claim_blocker"] == (
        "missing_codex_app_server_goal_proof"
    ), goal_mode_summary
    assert goal_mode_summary["loopx_access_packet_absent"] is True, goal_mode_summary
    assert goal_mode_summary["loopx_worker_bridge_requested"] is False, goal_mode_summary
    assert goal_mode_summary["no_upload_boundary"] is True, goal_mode_summary
    assert goal_mode_summary["submit_eligible"] is False, goal_mode_summary
    assert goal_mode_summary["timeout_multiplier_policy"][
        "agent_setup_timeout_multiplier_present"
    ] is True, goal_mode_summary
    assert goal_mode_summary["timeout_multiplier_policy"]["multipliers"][
        "agent_setup_timeout_multiplier"
    ] == 4, goal_mode_summary

    app_server_goal_launch = build_terminal_bench_private_runner_launch(
        mode="codex-app-server-goal",
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_codex_app_server_goal_baseline_env_guard_smoke",
        agent_timeout_multiplier=4,
        agent_setup_timeout_multiplier=4,
    )
    app_server_goal_summary = summarize_terminal_bench_private_runner_launch(
        app_server_goal_launch
    )
    assert app_server_goal_launch["ready"] is False, app_server_goal_launch
    assert app_server_goal_summary["codex_goal_mode_baseline_requested"] is True, app_server_goal_summary
    assert app_server_goal_summary["codex_app_server_goal_baseline_requested"] is True, app_server_goal_summary
    assert app_server_goal_summary["codex_goal_mode_invocation_surface"] == (
        "codex_app_server_thread_goal_set_get"
    ), app_server_goal_summary
    assert app_server_goal_summary["codex_app_server_goal_worker_adapter_present"] is True, app_server_goal_summary
    assert app_server_goal_summary["codex_app_server_goal_worker_plan_schema"] == (
        "codex_app_server_goal_worker_v0"
    ), app_server_goal_summary
    assert app_server_goal_summary[
        "codex_app_server_goal_worker_turn_start_required"
    ] is True, app_server_goal_summary
    assert app_server_goal_summary["codex_app_server_goal_proof_present"] is False, app_server_goal_summary
    assert app_server_goal_summary["codex_goal_mode_baseline_claim_allowed"] is False, app_server_goal_summary
    assert app_server_goal_summary["codex_goal_mode_baseline_claim_blocker"] == (
        "terminal_bench_app_server_goal_turn_start_proof_missing"
    ), app_server_goal_summary
    assert app_server_goal_summary["loopx_access_packet_absent"] is True, app_server_goal_summary
    assert app_server_goal_summary["first_blocker"] == (
        "terminal_bench_app_server_goal_turn_start_proof_missing"
    ), app_server_goal_summary

    expect_raises(
        lambda: build_terminal_bench_managed_harbor_command(
            loopx_mode="loopx_managed_codex",
            loopx_cli_bridge_enabled=True,
        ),
        "codex_loopx",
    )


if __name__ == "__main__":
    main()
