#!/usr/bin/env python3
"""Smoke-test the SkillsBench compact adapter and ledger route."""

from __future__ import annotations

import contextlib
import io
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_benchmark_claim_review,
    build_benchmark_verifier_attribution_review,
    build_skillsbench_benchmark_run,
    build_skillsbench_benchflow_result_benchmark_run,
    build_skillsbench_local_driver_a2a_contract,
    build_skillsbench_worker_handshake_preflight,
    SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION,
    SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION,
)
from loopx.benchmark_ledger import (  # noqa: E402
    load_benchmark_run_ledger,
    update_benchmark_run_ledger,
)
from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION,
    SkillsBenchLocalAcpRelay,
    _codex_exec_failure_category,
    _prompt_requires_bridge_first_action as _relay_prompt_requires_bridge_first_action,
    run_skillsbench_local_acp_relay_probe,
)
from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION,
    run_skillsbench_remote_command_file_bridge_probe,
    skillsbench_remote_command_file_bridge_command_is_fixture_probe,
)
from loopx.benchmark_adapters.skillsbench import (  # noqa: E402
    apply_skillsbench_pre_agent_setup_diagnostic_attribution,
    skillsbench_runner_error_attribution,
    skillsbench_runner_error_fingerprint,
)
from loopx.benchmark_adapters.skillsbench_batch import parallel_batch_requires_subprocess_isolation  # noqa: E402
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID,
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
)
from loopx.status import (  # noqa: E402
    build_skillsbench_post_run_debug_gate,
    compact_benchmark_run,
)
from examples.skillsbench_fixtures import (  # noqa: E402
    write_official_skillsbench_app_mount_failure,
    write_official_skillsbench_app_skills_mount_failure,
    write_official_skillsbench_app_skills_permission_failure,
    write_official_skillsbench_codex_acp_glibc_failure,
    write_official_skillsbench_codex_acp_internal_error,
    write_official_skillsbench_codex_acp_launch_preflight_failure,
    write_official_skillsbench_codex_acp_libssl_failure,
    write_official_skillsbench_codex_acp_provider_zero_activity,
    write_official_skillsbench_docker_apt_failure,
    write_official_skillsbench_docker_daemon_unavailable_failure,
    write_official_skillsbench_docker_port_conflict_failure,
    write_official_skillsbench_oracle_reward_artifact_recovery_result,
    write_official_skillsbench_passed_bool_result,
    write_official_skillsbench_result,
    write_official_skillsbench_reward_artifact_recovery_result,
    write_official_skillsbench_runner_error_zero_reward_result,
    write_official_skillsbench_unclassified_compose_failure,
    write_official_skillsbench_volume_mount_failure,
)
from loopx.benchmark_adapters.skillsbench_codex_runtime import (  # noqa: E402
    LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
    materialize_local_codex_participant,
)
from loopx.benchmark_adapters import (  # noqa: E402
    skillsbench_dockerfile_runtime as dockerfile_runtime,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD,
    CODEX_ACP_RUNTIME_DEPS_SETUP_CMD,
    CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD,
    DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC,
    DEFAULT_LEDGER,
    DEFAULT_MAX_ROUNDS,
    DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY,
    DEFAULT_SOFT_VERIFIER_TIMEOUT_SEC,
    DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST,
    DEFAULT_DOCKER_MAVEN_MIRROR_HOST,
    DEFAULT_DOCKER_MAVEN_MIRROR_URL,
    DEFAULT_DOCKER_MAVEN_SETTINGS_PATH,
    DEFAULT_DOCKER_PIP_INDEX_HOST,
    DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST,
    DECLARED_DONE_MARKER,
    DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN,
    DOCKER_APT_RETRY_BEGIN,
    DOCKER_APP_SKILLS_MOUNT_BEGIN,
    DOCKER_APP_SKILLS_MOUNT_KEEP_FILE,
    DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN,
    DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN,
    DOCKER_GCR_MIRROR_BEGIN,
    DOCKER_MAVEN_MIRROR_BEGIN,
    DOCKER_MAVEN_MIRROR_END,
    DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN,
    DOCKER_PIP_BOOTSTRAP_BEGIN,
    DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN,
    DOCKER_HOST_CPU_ENV,
    HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC,
    PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS,
    PRODUCT_MODE_CASE_STATE_PATH,
    PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION,
    PUBLIC_BENCHMARK_RUN_LEDGER,
    RUNNER_CONFIG_PUBLIC_FILENAME,
    RUNNER_PREREQUISITES_PUBLIC_FILENAME,
    SkillsBenchProductModeNoLifecycleRequests,
    VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN,
    VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN,
    _tail,
    _apply_app_server_goal_round_semantics_to_controller_trace,
    _apply_agent_message_only_no_tool_calls_attribution,
    _apply_native_goal_worker_finish_guard_attribution,
    _blind_loop_persistent_continuation_clause,
    _build_goal_start_product_mode_control_score,
    _build_product_mode_user,
    _copy_loopx_source_subset,
    _host_local_acp_launch_command,
    _effective_local_codex_first_action_timeout_sec,
    _first_bridge_failure_category,
    _host_local_acp_codex_exec_preflight_bridge_success_observed,
    _loopx_case_init_failure_blocker,
    _loopx_case_source_path_for_container,
    _loopx_source_mount_contract,
    _loopx_source_mounts,
    _product_mode_depth_gate_satisfied,
    _merge_app_server_goal_worker_trace_summary,
    _merge_acp_trajectory_summary,
    _merge_final_result_round_reward,
    _merge_host_local_acp_relay_trace_summary,
    _new_controller_trace,
    _summarize_host_local_acp_preflight_bridge_trace,
    _round_result_declared_done,
    build_compose_setup_diagnostic,
    build_plan,
    cleanup_benchflow_setup_stall_children,
    cleanup_host_local_acp_attempt_children,
    cleanup_benchflow_soft_verify_timeout_children,
    install_benchflow_user_loop_final_verify_recovery,
    install_benchflow_verifier_prep_timeout_override,
    append_history,
    build_runner_failure_compact,
    main as skillsbench_automation_loop_main,
    inspect_skillsbench_worker_handshake,
    parse_args,
    product_mode_case_state_seed_text,
    product_mode_soft_verify_policy_for_route,
    reduce_result,
    update_ledger as update_skillsbench_ledger,
    _runner_prerequisite_failure_attribution,
    _subcommand_family_count,
    _sync_relay_closeout_counts_into_compact,
    summarize_acp_trajectory,
    stage_task_for_sandbox,
)
import scripts.skillsbench_automation_loop as skillsbench_loop  # noqa: E402
from scripts.skillsbench_reverse_channel_bridge import (  # noqa: E402
    _prompt_requires_bridge_first_action as _reverse_prompt_requires_bridge_first_action,
    _run_codex_payload,
)


GOAL_ID = "skillsbench-benchmark-run-fixture"


def assert_prerequisites_include(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, value in expected.items():
        assert actual.get(key) == value, (key, actual)


def test_skillsbench_default_route_is_goal_baseline() -> None:
    args = parse_args([])
    assert args.max_rounds == DEFAULT_MAX_ROUNDS == 16, args
    assert args.route == "codex-cli-goal-baseline", args
    assert args.route != "codex-goal-mode-baseline", args
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            parse_args(["--route", "codex-goal-mode-baseline"])
        except SystemExit as exc:
            assert exc.code == 2, exc
        else:
            raise AssertionError("deprecated codex-goal-mode-baseline route parsed")


def test_skillsbench_default_ledger_is_private_unless_published() -> None:
    args = parse_args([])
    assert Path(args.ledger_path) == DEFAULT_LEDGER, args
    assert Path(args.global_ledger_path) == DEFAULT_LEDGER, args
    assert ".local" in Path(args.ledger_path).parts, args
    assert "docs" not in Path(args.ledger_path).parts, args

    publish_args = parse_args(["--publish-public-ledger"])
    assert (
        Path(publish_args.ledger_path) == PUBLIC_BENCHMARK_RUN_LEDGER
    ), publish_args
    assert (
        Path(publish_args.global_ledger_path) == PUBLIC_BENCHMARK_RUN_LEDGER
    ), publish_args

    explicit_args = parse_args(
        [
            "--publish-public-ledger",
            "--ledger-path",
            "explicit-run-group-ledger.json",
        ]
    )
    assert Path(explicit_args.ledger_path) == Path(
        "explicit-run-group-ledger.json"
    ), explicit_args
    assert (
        Path(explicit_args.global_ledger_path) == PUBLIC_BENCHMARK_RUN_LEDGER
    ), explicit_args


def test_codex_app_server_goal_requires_public_safe_codex_api_tunnel_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-api-tunnel-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        proxy_url = "http://127.0.0.1:18080"
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--codex-api-egress-mode",
                "reverse-tunnel",
                "--codex-api-reverse-tunnel-proxy",
                proxy_url,
                "--app-server-reasoning-effort",
                "xhigh",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs"),
            ]
        )
        plan = build_plan(args)
        egress = plan["codex_api_egress_preflight"]
        assert egress["required"] is True, egress
        assert egress["ready"] is False, egress
        assert egress["status"] == "pending", egress
        assert egress["requested_mode"] == "reverse-tunnel", egress
        assert egress["resolved_mode"] == "reverse-tunnel", egress
        assert egress["reverse_tunnel_required"] is True, egress
        assert egress["proxy_configured"] is True, egress
        assert egress["proxy_source"] == "cli", egress
        assert egress["proxy_scheme"] == "http", egress
        assert egress["proxy_endpoint_kind"] == "loopback", egress
        assert egress["proxy_endpoint_port"] == 18080, egress
        assert egress["proxy_url_recorded"] is False, egress
        assert proxy_url not in json.dumps(plan, sort_keys=True), plan

        target_env = skillsbench_loop._host_local_acp_target_env({}, args=args)
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
            assert target_env[key] == proxy_url, target_env
        assert target_env["LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY"] == proxy_url
        assert "127.0.0.1" in target_env["NO_PROXY"], target_env

        config = plan["runner_config"]
        assert plan["app_server_reasoning_effort"] == "xhigh", plan
        assert config["app_server_reasoning_effort"] == "xhigh", config
        assert config["codex_api_egress_preflight_required"] is True, config
        assert config["codex_api_egress_mode_requested"] == "reverse-tunnel", config
        assert config["codex_api_egress_mode_resolved"] == "reverse-tunnel", config
        assert config["codex_api_reverse_tunnel_required"] is True, config
        assert config["codex_api_reverse_tunnel_proxy_configured"] is True, config
        assert config["codex_api_reverse_tunnel_proxy_endpoint_port"] == 18080, config
        assert config["codex_api_reverse_tunnel_proxy_url_recorded"] is False, config
        assert proxy_url not in json.dumps(config, sort_keys=True), config

        benchmark_proxy_url = "http://benchmark-proxy.example.invalid:3128"
        codex_acp_args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--host-local-acp-launch",
                "--codex-api-egress-mode",
                "reverse-tunnel",
                "--codex-api-reverse-tunnel-proxy",
                proxy_url,
                "--benchmark-egress-proxy",
                benchmark_proxy_url,
                "--benchmark-egress-proxy-mode",
                "require",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs-codex-acp"),
            ]
        )
        codex_acp_plan = build_plan(codex_acp_args)
        codex_acp_egress = codex_acp_plan["codex_api_egress_preflight"]
        assert codex_acp_egress["required"] is True, codex_acp_egress
        assert codex_acp_egress["resolved_mode"] == "reverse-tunnel", codex_acp_egress
        assert codex_acp_egress["reverse_tunnel_required"] is True, codex_acp_egress
        codex_acp_config = codex_acp_plan["runner_config"]
        assert (
            codex_acp_config["codex_api_egress_mode_resolved"] == "reverse-tunnel"
        ), codex_acp_config
        assert codex_acp_config["codex_api_reverse_tunnel_required"] is True, (
            codex_acp_config
        )
        agent_env = {
            "HTTPS_PROXY": benchmark_proxy_url,
            "HTTP_PROXY": benchmark_proxy_url,
            "ALL_PROXY": benchmark_proxy_url,
            "LOOPX_SKILLSBENCH_EGRESS_PROXY": benchmark_proxy_url,
        }
        codex_acp_target_env = skillsbench_loop._host_local_acp_target_env(
            agent_env,
            args=codex_acp_args,
        )
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
            assert codex_acp_target_env[key] == proxy_url, codex_acp_target_env
        assert (
            codex_acp_target_env["LOOPX_SKILLSBENCH_EGRESS_PROXY"]
            == benchmark_proxy_url
        ), codex_acp_target_env
        assert benchmark_proxy_url not in json.dumps(
            codex_acp_config,
            sort_keys=True,
        ), codex_acp_config


def test_generic_reasoning_effort_reaches_codex_exec_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-reasoning-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--host-local-acp-launch",
                "--reasoning-effort",
                "xhigh",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs"),
            ]
        )
        plan = build_plan(args)
        command = _host_local_acp_launch_command(args, plan)
        assert plan["reasoning_effort"] == "xhigh", plan
        assert plan["codex_cli_reasoning_effort"] == "xhigh", plan
        assert plan["app_server_reasoning_effort"] == "", plan
        assert command[command.index("--reasoning-effort") + 1] == "xhigh", command
        config = plan["runner_config"]
        assert config["reasoning_effort"] == "xhigh", config
        assert config["codex_cli_reasoning_effort"] == "xhigh", config
        assert "app_server_reasoning_effort" not in config, config


def test_codex_exec_relay_maps_reasoning_effort_to_cli_config() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-cli-effort-") as tmp:
        root = Path(tmp)
        fake_codex = root / "fake-codex"
        argv_path = root / "argv.json"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

Path(os.environ["LOOPX_FAKE_CODEX_ARGV_PATH"]).write_text(json.dumps(sys.argv), encoding="utf-8")
output_path = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
output_path.write_text("relay ok", encoding="utf-8")
raise SystemExit(0)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)

        old_env = os.environ.get("LOOPX_FAKE_CODEX_ARGV_PATH")
        os.environ["LOOPX_FAKE_CODEX_ARGV_PATH"] = str(argv_path)
        try:
            relay = SkillsBenchLocalAcpRelay(
                CodexExecConfig(
                    codex_bin=str(fake_codex),
                    route="codex-acp-blind-loop-baseline",
                    timeout_sec=5,
                    reasoning_effort="xhigh",
                )
            )
            response = relay._run_codex(
                "public-safe prompt placeholder",
                session={"cwd": str(root)},
                session_id="session-cli-effort",
                stdout=io.StringIO(),
            )
        finally:
            if old_env is None:
                os.environ.pop("LOOPX_FAKE_CODEX_ARGV_PATH", None)
            else:
                os.environ["LOOPX_FAKE_CODEX_ARGV_PATH"] = old_env

        assert response == "relay ok", response
        argv = json.loads(argv_path.read_text(encoding="utf-8"))
        assert "-c" in argv, argv
        config_value = argv[argv.index("-c") + 1]
        assert config_value == 'model_reasoning_effort="xhigh"', argv


def test_benchmark_egress_proxy_env_is_public_safe_and_forwarded() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-benchmark-egress-proxy-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        proxy_url = "http://benchmark-proxy.example.invalid:18080"
        previous = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY")
        os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = proxy_url
        try:
            args = parse_args(
                [
                    "--task-id",
                    "citation-check",
                    "--route",
                    "codex-app-server-goal-baseline",
                    "--host-local-acp-launch",
                    "--remote-command-file-bridge-ready",
                    "--skillsbench-root",
                    str(skillsbench_root),
                    "--jobs-dir",
                    str(root / "jobs"),
                    "--benchmark-egress-no-proxy",
                    "example-cache.invalid,127.0.0.1",
                ]
            )
            plan = build_plan(args)
            egress = plan["benchmark_egress_proxy"]
            assert egress["requested_mode"] == "require", egress
            assert egress["proxy_required"] is True, egress
            assert egress["proxy_configured"] is True, egress
            assert egress["proxy_source"] == "env", egress
            assert egress["proxy_env_key"] == "LOOPX_SKILLSBENCH_EGRESS_PROXY", egress
            assert egress["proxy_scheme"] == "http", egress
            assert egress["proxy_endpoint_kind"] == "public_or_unknown", egress
            assert egress["proxy_endpoint_port"] == 18080, egress
            assert egress["no_proxy_configured"] is True, egress
            assert egress["no_proxy_entry_count"] >= 5, egress
            assert egress["no_proxy_raw_value_recorded"] is False, egress
            assert egress["proxy_url_recorded"] is False, egress
            assert egress["raw_proxy_url_recorded"] is False, egress
            assert proxy_url not in json.dumps(plan, sort_keys=True), plan
            assert "example-cache.invalid" not in json.dumps(plan, sort_keys=True), plan

            private_env = skillsbench_loop._benchmark_egress_proxy_env(args)
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                assert private_env[key] == proxy_url, private_env
            assert "127.0.0.1" in private_env["NO_PROXY"], private_env
            assert "hifis-storage.desy.de" in private_env["NO_PROXY"], private_env
            assert "example-cache.invalid" in private_env["NO_PROXY"], private_env

            target_env = skillsbench_loop._host_local_acp_target_env({}, args=args)
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                assert target_env[key] == proxy_url, target_env
            assert target_env["LOOPX_SKILLSBENCH_EGRESS_PROXY"] == proxy_url
            assert "127.0.0.1" in target_env["NO_PROXY"], target_env
            assert "hifis-storage.desy.de" in target_env["NO_PROXY"], target_env
            assert "example-cache.invalid" in target_env["NO_PROXY"], target_env

            previous_docker_config = os.environ.get("DOCKER_CONFIG")
            with skillsbench_loop._benchmark_egress_proxy_env_applied(args, plan=plan):
                docker_config_dir = Path(os.environ["DOCKER_CONFIG"])
                docker_config_path = docker_config_dir / "config.json"
                docker_config = json.loads(docker_config_path.read_text(encoding="utf-8"))
                docker_proxy = docker_config["proxies"]["default"]
                assert docker_proxy["httpProxy"] == proxy_url, docker_proxy
                assert docker_proxy["httpsProxy"] == proxy_url, docker_proxy
                assert "127.0.0.1" in docker_proxy["noProxy"], docker_proxy
                assert "hifis-storage.desy.de" in docker_proxy["noProxy"], docker_proxy
                assert "example-cache.invalid" in docker_proxy["noProxy"], docker_proxy
            if previous_docker_config is None:
                assert "DOCKER_CONFIG" not in os.environ
            else:
                assert os.environ["DOCKER_CONFIG"] == previous_docker_config
            assert not docker_config_dir.exists(), docker_config_dir

            config = skillsbench_loop._public_runner_config(plan)
            assert config["benchmark_egress_proxy_required"] is True, config
            assert config["benchmark_egress_proxy_mode_requested"] == "require", config
            assert config["benchmark_egress_proxy_configured"] is True, config
            assert config["benchmark_egress_proxy_endpoint_kind"] == "public_or_unknown", config
            assert config["benchmark_egress_proxy_endpoint_port"] == 18080, config
            assert config["benchmark_egress_no_proxy_configured"] is True, config
            assert config["benchmark_egress_no_proxy_entry_count"] >= 5, config
            assert config["benchmark_egress_no_proxy_raw_value_recorded"] is False, config
            assert config["benchmark_egress_proxy_url_recorded"] is False, config
            assert config["benchmark_egress_proxy_docker_config_injected"] is True, config
            assert config["benchmark_egress_proxy_docker_config_path_recorded"] is False, config
            assert config["benchmark_egress_proxy_docker_config_raw_proxy_recorded"] is False, config
            assert proxy_url not in json.dumps(config, sort_keys=True), config
            assert "example-cache.invalid" not in json.dumps(config, sort_keys=True), config
        finally:
            if previous is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = previous


def test_benchmark_egress_proxy_require_mode_blocks_without_proxy() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-benchmark-egress-require-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        previous = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY")
        os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
        try:
            args = parse_args(
                [
                    "--task-id",
                    "citation-check",
                    "--benchmark-egress-proxy-mode",
                    "require",
                    "--skillsbench-root",
                    str(skillsbench_root),
                    "--jobs-dir",
                    str(root / "jobs"),
                ]
            )
            plan = build_plan(args)
            try:
                skillsbench_loop._run_benchmark_egress_proxy_preflight(args, plan)
            except skillsbench_loop.SkillsBenchSetupPreflightBlocked:
                pass
            else:  # pragma: no cover - assertion path for script-style smoke
                raise AssertionError("require mode without proxy should block preflight")

            egress = plan["benchmark_egress_proxy"]
            assert egress["status"] == "missing_required_proxy", egress
            assert egress["ready"] is False, egress
            assert egress["proxy_configured"] is False, egress
            assert egress["proxy_url_recorded"] is False, egress
            assert egress["raw_proxy_url_recorded"] is False, egress
        finally:
            if previous is not None:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = previous


def test_benchmark_egress_proxy_auto_falls_back_to_direct_without_leaking_proxy() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-benchmark-egress-auto-direct-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        proxy_url = "http://benchmark-proxy.example.invalid:18080"
        previous = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY")
        previous_proxy_probe = skillsbench_loop._probe_http_connect_proxy
        previous_direct_probe = skillsbench_loop._probe_direct_tcp_egress
        os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = proxy_url
        try:
            skillsbench_loop._probe_http_connect_proxy = (  # type: ignore[assignment]
                lambda **_kwargs: "proxy_connect_rejected"
            )
            skillsbench_loop._probe_direct_tcp_egress = (  # type: ignore[assignment]
                lambda **_kwargs: "direct_tcp_ready"
            )
            args = parse_args(
                [
                    "--task-id",
                    "citation-check",
                    "--benchmark-egress-proxy-mode",
                    "auto",
                    "--skillsbench-root",
                    str(skillsbench_root),
                    "--jobs-dir",
                    str(root / "jobs"),
                ]
            )
            plan = build_plan(args)
            egress = skillsbench_loop._run_benchmark_egress_proxy_preflight(args, plan)

            assert egress["ready"] is True, egress
            assert egress["status"] == "direct_tcp_ready_after_proxy_failure", egress
            assert egress["effective_mode"] == "direct", egress
            assert egress["direct_fallback_allowed"] is True, egress
            assert egress["direct_fallback_active"] is True, egress
            assert egress["proxy_url_recorded"] is False, egress
            assert egress["raw_proxy_url_recorded"] is False, egress
            assert proxy_url not in json.dumps(plan, sort_keys=True), plan

            private_env = skillsbench_loop._benchmark_egress_proxy_env(args)
            assert private_env == {}, private_env
            target_env = skillsbench_loop._host_local_acp_target_env({}, args=args)
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                assert target_env.get(key) != proxy_url, target_env

            prereqs = plan["runner_prerequisites"]
            assert prereqs["benchmark_egress_proxy_ready"] is True, prereqs
            assert prereqs["benchmark_egress_proxy_mode_requested"] == "auto", prereqs
            assert prereqs["benchmark_egress_proxy_mode_effective"] == "direct", prereqs
            assert prereqs["benchmark_egress_direct_fallback_active"] is True, prereqs
        finally:
            skillsbench_loop._probe_http_connect_proxy = previous_proxy_probe  # type: ignore[assignment]
            skillsbench_loop._probe_direct_tcp_egress = previous_direct_probe  # type: ignore[assignment]
            if previous is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = previous


def test_benchmark_egress_proxy_auto_ignores_shell_placeholder() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-benchmark-egress-placeholder-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--benchmark-egress-proxy",
                "${BENCHMARK_PROXY}",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs"),
            ]
        )
        plan = build_plan(args)
        egress = plan["benchmark_egress_proxy"]
        assert egress["status"] == "invalid_proxy_value", egress
        assert egress["ready"] is True, egress
        assert egress["proxy_configured"] is False, egress
        assert egress["proxy_value_valid"] is False, egress
        assert egress["proxy_invalid_reason"] == "unexpanded_placeholder", egress
        assert egress["effective_mode"] == "direct", egress
        assert "${BENCHMARK_PROXY}" not in json.dumps(plan, sort_keys=True), plan

        assert skillsbench_loop._benchmark_egress_proxy_env(args) == {}
        target_env = skillsbench_loop._host_local_acp_target_env({}, args=args)
        assert "LOOPX_SKILLSBENCH_EGRESS_PROXY" not in target_env, target_env
        assert "HTTP_PROXY" not in target_env, target_env


def test_benchmark_egress_proxy_require_blocks_shell_placeholder() -> None:
    with tempfile.TemporaryDirectory(
        prefix="skillsbench-benchmark-egress-placeholder-require-"
    ) as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--benchmark-egress-proxy",
                "${BENCHMARK_PROXY}",
                "--benchmark-egress-proxy-mode",
                "require",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs"),
            ]
        )
        plan = build_plan(args)
        try:
            skillsbench_loop._run_benchmark_egress_proxy_preflight(args, plan)
        except skillsbench_loop.SkillsBenchSetupPreflightBlocked:
            pass
        else:  # pragma: no cover - assertion path for script-style smoke
            raise AssertionError("require mode placeholder should block preflight")

        egress = plan["benchmark_egress_proxy"]
        assert egress["status"] == "invalid_proxy_value", egress
        assert egress["ready"] is False, egress
        assert egress["proxy_configured"] is False, egress
        assert egress["proxy_value_valid"] is False, egress
        assert egress["proxy_invalid_reason"] == "unexpanded_placeholder", egress
        assert egress["error_kind"] == "unexpanded_placeholder", egress
        assert "${BENCHMARK_PROXY}" not in json.dumps(plan, sort_keys=True), plan


def test_codex_app_server_goal_rejects_non_http_codex_api_proxy_scheme() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-api-proxy-scheme-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        proxy_url = "socks5://127.0.0.1:18080"
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--codex-api-egress-mode",
                "reverse-tunnel",
                "--codex-api-reverse-tunnel-proxy",
                proxy_url,
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(root / "jobs"),
            ]
        )
        plan = build_plan(args)
        try:
            skillsbench_loop._run_codex_api_egress_preflight(args, plan)
        except skillsbench_loop.SkillsBenchSetupPreflightBlocked:
            pass
        else:  # pragma: no cover - assertion path for script-style smoke
            raise AssertionError("unsupported proxy scheme should block preflight")

        egress = plan["codex_api_egress_preflight"]
        assert egress["status"] == "unsupported_proxy_scheme", egress
        assert egress["ready"] is False, egress
        assert egress["resolved_mode"] == "reverse-tunnel", egress
        assert egress["proxy_scheme"] == "socks5", egress
        assert egress["proxy_url_recorded"] is False, egress
        assert proxy_url not in json.dumps(plan, sort_keys=True), plan


def test_codex_app_server_goal_blocks_without_codex_api_egress() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-api-egress-block-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task_dir = skillsbench_root / "tasks" / "citation-check"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        codex_bin = root / "codex"
        codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        codex_bin.chmod(0o755)

        original_create_connection = skillsbench_loop.socket.create_connection

        def fake_create_connection(*_args: Any, **_kwargs: Any) -> None:
            raise TimeoutError("simulated blocked codex api egress")

        skillsbench_loop.socket.create_connection = fake_create_connection
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "citation-check",
                        "--route",
                        "codex-app-server-goal-baseline",
                        "--allow-deprecated-app-server-goal-route",
                        "--host-local-acp-launch",
                        "--local-codex-bin",
                        str(codex_bin),
                        "--remote-command-file-bridge-ready",
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--jobs-dir",
                        str(root / "jobs"),
                        "--job-name",
                        "skillsbench-codex-api-egress-block",
                        "--rollout-name",
                        "citation-check__codex_app_server_goal",
                    ]
                )
        finally:
            skillsbench_loop.socket.create_connection = original_create_connection

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        assert payload["compact_closeout_recorded"] is True, payload
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        prereqs = compact["runner_prerequisites"]
        assert prereqs["codex_api_egress_preflight_required"] is True, compact
        assert prereqs["codex_api_egress_preflight_ready"] is False, compact
        assert prereqs["codex_api_egress_preflight_status"] == (
            "missing_reverse_tunnel_proxy"
        ), compact
        assert prereqs["codex_api_egress_mode_requested"] == "auto", compact
        assert prereqs["codex_api_egress_mode_resolved"] == "reverse-tunnel", compact
        assert prereqs["codex_api_reverse_tunnel_required"] is True, compact
        assert prereqs["codex_api_reverse_tunnel_proxy_configured"] is False, compact
        assert prereqs["codex_api_reverse_tunnel_proxy_url_recorded"] is False, compact
        assert "codex_api_egress_failure" in compact["runner_failure_fingerprint"][
            "matched_patterns"
        ], compact
        assert "simulated blocked codex api egress" not in json.dumps(compact), compact


def test_skillsbench_plan_only_batch_parallel_case_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-plan-batch-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        for task_id in ("citation-check", "3d-scan-calc"):
            task_dir = skillsbench_root / "tasks" / task_id
            task_dir.mkdir(parents=True)
            (task_dir / "task.toml").write_text(
                "version = \"1.1\"\n",
                encoding="utf-8",
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-ids",
                    "citation-check,3d-scan-calc",
                    "--parallel-cases",
                    "2",
                    "--route",
                    "loopx-goal-start-product-mode",
                    "--host-local-acp-launch",
                    "--remote-command-file-bridge-ready",
                    "--skillsbench-root",
                    str(skillsbench_root),
                    "--jobs-dir",
                    str(root / "jobs"),
                    "--run-group-id",
                    "skillsbench-plan-batch-fixture",
                    "--plan-only",
                ]
            )

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        assert payload["ok"] is True, payload
        assert payload["batch"] is True, payload
        assert payload["task_count"] == 2, payload
        assert payload["parallel_cases"] == 2, payload
        assert payload["run_group_id"] == "skillsbench-plan-batch-fixture", payload
        results = payload["results"]
        assert [result["launch_plan"]["task_id"] for result in results] == [
            "citation-check",
            "3d-scan-calc",
        ], results
        plans = [result["launch_plan"] for result in results]
        assert {plan["run_group_id"] for plan in plans} == {
            "skillsbench-plan-batch-fixture"
        }, plans
        assert len({plan["job_name"] for plan in plans}) == 2, plans
        assert len({plan["result_json"] for plan in plans}) == 2, plans
    for result in results:
        assert result["ok"] is True, result
        assert result["plan_only"] is True, result
        assert result["launch_plan"]["host_local_acp_launch"] is True, result
        assert result["launch_plan"]["runner_prerequisites"][
            "host_local_acp_launch"
        ] is True, result


def test_skillsbench_batch_case_cli_filters_internal_aggregate_flag() -> None:
    args = parse_args(
        [
            "--task-ids",
            "citation-check,3d-scan-calc",
            "--parallel-cases",
            "2",
            "--route",
            "codex-app-server-goal-baseline",
            "--allow-deprecated-app-server-goal-route",
            "--update-ledger",
            "--plan-only",
        ]
    )
    case_args = skillsbench_loop._clone_args_for_batch_case(
        args,
        task_id="citation-check",
        index=0,
        total=2,
        run_group_id="skillsbench-batch-cli-fixture",
    )
    child_cli = skillsbench_loop._batch_case_args_to_cli(case_args)

    assert "--update-current-aggregate" not in child_cli, child_cli
    assert "--skip-current-aggregate-update" not in child_cli, child_cli
    assert "--current-aggregate-path" in child_cli, child_cli
    assert child_cli[child_cli.index("--parallel-cases") + 1] == "1", child_cli


def test_skillsbench_formal_product_mode_rejects_tiny_round_budget() -> None:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            parse_args(
                [
                    "--route",
                    "loopx-goal-start-product-mode",
                    "--max-rounds",
                    str(PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS - 1),
                ]
            )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("formal product-mode accepted a tiny max-round budget")

    args = parse_args(
        [
            "--route",
            "loopx-goal-start-product-mode",
            "--max-rounds",
            str(PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS),
        ]
    )
    assert args.max_rounds == PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS, args

    reduce_args = parse_args(
        [
            "--route",
            "loopx-goal-start-product-mode",
            "--max-rounds",
            "2",
            "--reduce-only",
        ]
    )
    assert reduce_args.max_rounds == 2, reduce_args


def test_skillsbench_product_mode_soft_verify_default_is_every_round() -> None:
    args = parse_args(["--route", "loopx-product-mode"])
    assert args.product_mode_soft_verify_policy == (
        DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY
    ) == "every-round"
    assert args.soft_verifier_timeout_sec == DEFAULT_SOFT_VERIFIER_TIMEOUT_SEC == 600
    assert (
        product_mode_soft_verify_policy_for_route(
            "loopx-product-mode",
            args.product_mode_soft_verify_policy,
        )
        == "every-round"
    )


def test_skillsbench_turn_uses_final_only_soft_verify() -> None:
    args = parse_args(["--route", "loopx-turn-agent-cli"])
    assert args.product_mode_soft_verify_policy == "every-round"
    assert (
        product_mode_soft_verify_policy_for_route(
            "loopx-turn-agent-cli",
            args.product_mode_soft_verify_policy,
        )
        == "final-only"
    )


def test_reverse_channel_first_action_timeout_stops_codex_process() -> None:
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(30)"],
            "stdin": (
                "LoopX bridge action preflight. Your first tool action should "
                "be a shell pipeline that sends JSON to the private bridge.\n\n"
                "Private bridge command:\nfixture-bridge"
            ),
            "timeout_sec": 20,
        },
        codex_bin=sys.executable,
        default_timeout_sec=20,
        prompt_bridge_command="unused {private_bridge_command_sh}",
        first_action_timeout_sec=1,
    )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_first_action_timeout\n"
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_timeout_survives_blocked_stdin_write() -> None:
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(30)"],
            "stdin": "x" * 2_000_000,
            "timeout_sec": 1,
        },
        codex_bin=sys.executable,
        default_timeout_sec=1,
        prompt_bridge_command=None,
    )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_timeout\n"
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_raw_prompt_does_not_require_bridge_first_action() -> None:
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(2)"],
            "stdin": (
                "Raw Codex autonomous baseline prompt with a bridge packet.\n\n"
                "Private bridge command:\nfixture-bridge"
            ),
            "timeout_sec": 10,
        },
        codex_bin=sys.executable,
        default_timeout_sec=10,
        prompt_bridge_command="unused {private_bridge_command_sh}",
        first_action_timeout_sec=1,
    )
    assert time.monotonic() - start >= 1.5
    assert response["exit_code"] == 0, response
    assert response["stderr"] != "codex_exec_first_action_timeout\n"
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_bridge_idle_waits_for_bridge_activity() -> None:
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(30)"],
            "stdin": (
                "Raw Codex autonomous baseline prompt with a bridge packet.\n\n"
                "Private bridge command:\nfixture-bridge"
            ),
            "timeout_sec": 1,
        },
        codex_bin=sys.executable,
        default_timeout_sec=1,
        prompt_bridge_command="unused {private_bridge_command_sh}",
        bridge_idle_timeout_sec=0.2,
    )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_timeout\n", response
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_bridge_operation_failure_is_categorized() -> None:
    with tempfile.TemporaryDirectory(prefix="reverse-bridge-failure-") as tmp:
        tmp_path = Path(tmp)
        fake_codex = tmp_path / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

prompt = sys.stdin.read()
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({"operation": "preflight"}),
    text=True,
    shell=True,
)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        failing_bridge = tmp_path / "failing-bridge"
        failing_bridge.write_text(
            """#!/usr/bin/env python3
import sys

sys.stdin.read()
print("PermissionError: [Errno 1] Operation not permitted", file=sys.stderr)
raise SystemExit(1)
""",
            encoding="utf-8",
        )
        failing_bridge.chmod(0o700)
        response = _run_codex_payload(
            {
                "args": ["exec"],
                "stdin": (
                    "LoopX bridge action preflight. Your first tool action "
                    "should call the private bridge.\n\n"
                    "Private bridge command:\nfixture-bridge"
                ),
                "timeout_sec": 10,
            },
            codex_bin=str(fake_codex),
            default_timeout_sec=10,
            prompt_bridge_command=f"{sys.executable} {failing_bridge}",
            first_action_timeout_sec=5,
        )
        records = [
            json.loads(line)
            for line in response["agent_operations_jsonl"].splitlines()
            if line.strip()
        ]
        assert len(records) == 2, records
        assert records[1]["returncode"] == 1, records
        assert records[1]["success"] is False, records
        assert records[1]["failure_category"] == "bridge_client_permission_error"
        assert response["raw_task_text_recorded"] is False
        assert response["credential_values_recorded"] is False


def test_host_local_codex_exec_preflight_requires_successful_bridge_action() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-preflight-summary-") as tmp:
        trace_dir = Path(tmp)
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "trace_kind": "remote_command_file_bridge_agent_operations",
            "remote_command_file_bridge_agent_operations": {
                "schema_version": (
                    "skillsbench_remote_command_file_bridge_agent_operations_v0"
                ),
                "request_count": 1,
                "success_count": 0,
                "failure_count": 1,
                "operation_counts": {"preflight": 1},
                "returncode_counts": {"1": 1},
                "failure_category_counts": {
                    "bridge_client_permission_error": 1,
                },
                "task_facing_operation_count": 0,
                "raw_material_recorded": False,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "credential_values_recorded": False,
            },
        }
        (trace_dir / "agent-ops.compact.json").write_text(
            json.dumps(trace),
            encoding="utf-8",
        )
        summary = _summarize_host_local_acp_preflight_bridge_trace(trace_dir)
        assert summary["trace_present"] is True, summary
        assert summary["preflight_operation_count"] == 1, summary
        assert summary["success_count"] == 0, summary
        assert summary["failure_count"] == 1, summary
        assert summary["returncode_counts"] == {"1": 1}, summary
        assert summary["failure_category_counts"] == {
            "bridge_client_permission_error": 1,
        }, summary
        assert (
            _host_local_acp_codex_exec_preflight_bridge_success_observed(summary)
            is False
        )
        assert _first_bridge_failure_category(summary) == (
            "bridge_client_permission_error"
        )


def test_reverse_channel_goal_start_prompt_requires_bridge_first_action() -> None:
    prompt = (
        "LoopX product-mode lifecycle contract. This route simulates "
        "`/loopx <task objective>` goal start: a compact ranked 3-todo plan "
        "must exist before todo writes, with selected runnable P0 todo "
        "`todo_example` entering the lifecycle. Before prose planning, "
        "your first agent action must be a task-facing shell/tool call through "
        "the available sandbox bridge.\n\n"
        "Private bridge command:\nfixture-bridge"
    )
    assert _reverse_prompt_requires_bridge_first_action(prompt) is True
    assert _relay_prompt_requires_bridge_first_action(prompt) is True
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(30)"],
            "stdin": prompt,
            "timeout_sec": 20,
        },
        codex_bin=sys.executable,
        default_timeout_sec=20,
        prompt_bridge_command="unused {private_bridge_command_sh}",
        first_action_timeout_sec=1,
    )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_first_action_timeout\n"
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_product_mode_checkpoint_requires_bridge_first_action() -> None:
    prompt = (
        "Mandatory product-mode solver checkpoint before round 7 continues. "
        "The next agent turn must start with either a task-facing sandbox "
        "bridge operation from `/app`, or, if local validation already proves "
        "the selected P0 is complete, the selected P0 closeout sequence.\n\n"
        "Private bridge command:\nfixture-bridge"
    )
    assert _reverse_prompt_requires_bridge_first_action(prompt) is True
    assert _relay_prompt_requires_bridge_first_action(prompt) is True
    start = time.monotonic()
    response = _run_codex_payload(
        {
            "args": ["-c", "import time; time.sleep(30)"],
            "stdin": prompt,
            "timeout_sec": 20,
        },
        codex_bin=sys.executable,
        default_timeout_sec=20,
        prompt_bridge_command="unused {private_bridge_command_sh}",
        first_action_timeout_sec=1,
        bridge_idle_timeout_sec=30,
    )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_first_action_timeout\n"
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False


def test_reverse_channel_bridge_idle_timeout_stops_codex_process() -> None:
    with tempfile.TemporaryDirectory(prefix="reverse-bridge-idle-") as tmp:
        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import time

prompt = sys.stdin.read()
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "python - <<'PY'\\nprint('task-facing')\\nPY",
        "timeout_sec": 10,
    }),
    text=True,
    shell=True,
    check=True,
)
time.sleep(30)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        start = time.monotonic()
        response = _run_codex_payload(
            {
                "args": ["exec"],
                "stdin": (
                    "LoopX bridge action preflight. Your first tool action should "
                    "be a shell pipeline that sends JSON to the private bridge.\n\n"
                    "Private bridge command:\ncat >/dev/null"
                ),
                "timeout_sec": 20,
            },
            codex_bin=str(fake_codex),
            default_timeout_sec=20,
            prompt_bridge_command="sh -lc {private_bridge_command_sh}",
            first_action_timeout_sec=3,
            bridge_idle_timeout_sec=1,
        )
    assert time.monotonic() - start < 8
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_bridge_idle_timeout\n", response
    assert response["raw_task_text_recorded"] is False
    assert response["credential_values_recorded"] is False
    records = [
        json.loads(line)
        for line in response["agent_operations_jsonl"].splitlines()
        if line.strip()
    ]
    assert len(records) == 2, records
    assert records[0]["record_phase"] == "start", records
    assert records[1]["record_phase"] == "complete", records
    assert records[0]["operation_observed"] is True
    assert records[0]["task_facing_operation"] is True
    assert records[0]["raw_request_recorded"] is False
    assert records[1]["returncode"] == 0


def test_reverse_channel_bridge_idle_timeout_ignores_inflight_bridge_command() -> None:
    with tempfile.TemporaryDirectory(prefix="reverse-bridge-inflight-") as tmp:
        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

prompt = sys.stdin.read()
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "python - <<'PY'\\nprint('task-facing')\\nPY",
        "timeout_sec": 10,
    }),
    text=True,
    shell=True,
    check=False,
)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        start = time.monotonic()
        response = _run_codex_payload(
            {
                "args": ["exec"],
                "stdin": (
                    "LoopX bridge action preflight. Your first tool action should "
                    "be a shell pipeline that sends JSON to the private bridge.\n\n"
                    "Private bridge command:\npython -c 'import time; time.sleep(5)'"
                ),
                "timeout_sec": 2,
            },
            codex_bin=str(fake_codex),
            default_timeout_sec=2,
            prompt_bridge_command="sh -lc {private_bridge_command_sh}",
            first_action_timeout_sec=1,
            bridge_idle_timeout_sec=1,
        )
    elapsed = time.monotonic() - start
    assert 1.5 <= elapsed < 5, elapsed
    assert response["exit_code"] == 124
    assert response["stderr"] == "codex_exec_timeout\n", response
    records = [
        json.loads(line)
        for line in response["agent_operations_jsonl"].splitlines()
        if line.strip()
    ]
    assert len(records) == 1, records
    assert records[0]["record_phase"] == "start", records
    assert records[0]["task_facing_operation"] is True


def test_product_mode_initial_prompt_keeps_task_visible_after_lifecycle_gate() -> None:
    trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-product-mode",
        "heartbeat_count": 0,
        "controller_action_decisions": 0,
        "initial_prompt_count": 0,
        "followup_prompt_count": 0,
        "stop_decision_count": 0,
        "reward_observation_count": 0,
        "round_rewards": [],
    }
    saved_modules = {
        name: sys.modules.get(name)
        for name in (
            "benchflow",
            "benchflow.sandbox",
            "benchflow.sandbox.user",
        )
    }
    fake_benchflow = types.ModuleType("benchflow")
    fake_sandbox = types.ModuleType("benchflow.sandbox")
    fake_user = types.ModuleType("benchflow.sandbox.user")

    class FakeBaseUser:
        pass

    class FakeRoundResultBase:
        pass

    class FakeRoundResult:
        rewards: dict[str, float] = {}
        n_tool_calls = 0
        trajectory: list[object] = []

    fake_user.BaseUser = FakeBaseUser
    fake_user.RoundResult = FakeRoundResultBase
    sys.modules["benchflow"] = fake_benchflow
    sys.modules["benchflow.sandbox"] = fake_sandbox
    sys.modules["benchflow.sandbox.user"] = fake_user
    try:
        user = _build_product_mode_user(
            route="loopx-product-mode",
            max_rounds=8,
            trace=trace,
            plan={
                "runner_prerequisites": {
                    "loopx_workflow_lifecycle_checkpoint": True,
                    "loopx_product_mode_lifecycle_driver_kind": (
                        "orchestrated_agentloop_loopx_cli"
                    ),
                }
            },
            case_payload={"canonical_product_mode_lifecycle_driver": True},
        )
    finally:
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    prompt = asyncio.run(user.run(0, "Compute the requested coefficient."))
    assert prompt is not None
    assert "--- LOOPX PRODUCT-MODE CONTROL PLANE ---" in prompt
    assert "--- TASK INSTRUCTION ---" in prompt
    assert "Compute the requested coefficient." in prompt
    assert "task semantics stay aligned with the baseline" in prompt
    assert "canonical workflow lifecycle driver has already" in prompt
    assert "Do not repeat setup lifecycle" in prompt
    assert "`pwd && ls -la`" in prompt
    assert "first agent action a task-facing sandbox bridge exec" in prompt
    assert "Do not run case closeout" in prompt
    assert "quota should-run --goal-id skillsbench-case" not in prompt
    assert "todo claim --goal-id skillsbench-case" not in prompt
    assert "task-facing work must wait" not in prompt
    assert "todo complete --goal-id skillsbench-case" not in prompt
    assert "benchmark_case_agent_closeout" not in prompt
    assert "quota spend-slot --goal-id skillsbench-case" not in prompt
    assert trace["last_decision"] == "send_initial_product_mode_prompt", trace
    assert trace["initial_prompt_count"] == 1, trace
    assert trace["product_mode_task_instruction_deferred_until_agent_lifecycle"] is False
    assert trace["product_mode_task_instruction_sent_initially"] is True

    trace.update(
        {
            "remote_command_file_bridge_agent_operation_trace_required": True,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 2,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 1,
        }
    )
    task_prompt = asyncio.run(
        user.run(1, "Compute the requested coefficient.", FakeRoundResult())
    )
    assert task_prompt is not None
    assert "--- TASK INSTRUCTION ---" in task_prompt
    assert "Compute the requested coefficient." in task_prompt
    assert "The task above remains the primary objective" in task_prompt
    assert "write or validate that path before closeout" in task_prompt
    assert "The task packet is now available" not in task_prompt
    assert "Mandatory product-mode solver checkpoint" in task_prompt
    assert "task-facing sandbox bridge operation" in task_prompt
    assert "selected P0 closeout sequence" in task_prompt
    assert "official reward" in task_prompt
    assert (
        trace["last_decision"]
        == "send_product_mode_solver_activity_continuation"
    ), trace
    assert trace.get("product_mode_task_instruction_sent_after_agent_lifecycle") is not True
    assert trace["followup_prompt_count"] == 1, trace


def test_goal_start_agent_runs_guided_slash_contract_before_solving() -> None:
    trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-goal-start-product-mode",
        "heartbeat_count": 0,
        "controller_action_decisions": 0,
        "initial_prompt_count": 0,
        "followup_prompt_count": 0,
        "stop_decision_count": 0,
        "reward_observation_count": 0,
        "round_rewards": [],
    }
    saved_modules = {
        name: sys.modules.get(name)
        for name in (
            "benchflow",
            "benchflow.sandbox",
            "benchflow.sandbox.user",
        )
    }
    fake_benchflow = types.ModuleType("benchflow")
    fake_sandbox = types.ModuleType("benchflow.sandbox")
    fake_user = types.ModuleType("benchflow.sandbox.user")

    class FakeBaseUser:
        pass

    class FakeRoundResultBase:
        pass

    fake_user.BaseUser = FakeBaseUser
    fake_user.RoundResult = FakeRoundResultBase
    sys.modules["benchflow"] = fake_benchflow
    sys.modules["benchflow.sandbox"] = fake_sandbox
    sys.modules["benchflow.sandbox.user"] = fake_user
    try:
        user = _build_product_mode_user(
            route="loopx-goal-start-product-mode",
            max_rounds=8,
            trace=trace,
            plan={
                "runner_prerequisites": {
                    "loopx_workflow_lifecycle_checkpoint": False,
                    "loopx_product_mode_lifecycle_driver_kind": (
                        "prompt_driven_loopx_cli"
                    ),
                    "goal_start_guided_command_required": True,
                    "goal_start_agent_authored_plan_required": True,
                    "goal_start_host_preseed_forbidden": True,
                }
            },
            case_payload={
                "canonical_product_mode_lifecycle_driver": True,
                "case_todo_seeded": False,
                "planned_todo_count": 0,
                "selected_p0_todo_id": "todo_goalstart_p0",
            },
        )
    finally:
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    prompt = asyncio.run(user.run(0, "Compute the requested coefficient."))
    assert prompt is not None
    assert "--- LOOPX PRODUCT-MODE CONTROL PLANE ---" in prompt
    assert "--- TASK INSTRUCTION ---" in prompt
    assert "Compute the requested coefficient." in prompt
    assert "actual agent contract for `/loopx <task objective>`" in prompt
    assert "start-goal --guided --project /app" in prompt
    assert "exact visible TASK INSTRUCTION" in prompt
    assert "--goal-text" in prompt
    assert "no plan or todo has been seeded" in prompt
    assert "todo add" in prompt
    assert "refresh-state" in prompt
    assert "quota should-run" in prompt
    assert "todo claim" in prompt
    assert "host-preseeded approximation" in prompt
    assert "heartbeat-prompt" in prompt
    assert "Codex CLI TUI `/goal`" in prompt
    assert "interaction_contract" in prompt
    assert "workspace_guard" in prompt
    assert "goal_boundary" in prompt
    assert "execution_obligation" in prompt
    assert "scheduler_hint" in prompt
    assert "there is no human available" in prompt
    assert "do not ask or wait for the user" in prompt
    assert "proceed with the task-facing work" in prompt
    assert "Only record a blocker when the sandbox bridge" in prompt
    assert "ordinary benchmark routing" in prompt
    assert "never authorizes quota spend" in prompt
    assert trace["product_mode_task_instruction_deferred_until_agent_lifecycle"] is False
    assert trace["product_mode_task_instruction_sent_initially"] is True
    assert trace["last_decision"] == "send_initial_product_mode_prompt"


def test_loopx_subcommand_family_counts_include_arguments() -> None:
    counts = {
        "todo complete": 2,
        "todo update blocked": 1,
        "refresh-state implementation": 3,
        "quota spend-slot": 4,
        "quota should-run": 5,
    }
    assert _subcommand_family_count(counts, "todo complete", "todo update") == 3
    assert _subcommand_family_count(counts, "refresh-state") == 3
    assert _subcommand_family_count(counts, "quota spend-slot") == 4


def test_relay_closeout_counts_sync_into_final_compact() -> None:
    compact = {
        "interaction_counters": {
            "remote_command_file_bridge_agent_refresh_state_count": 0,
        },
        "product_mode_lifecycle_contract": {
            "agent_bridge_todo_closeout_count": 2,
            "agent_bridge_refresh_state_count": 0,
            "agent_bridge_quota_spend_slot_count": 1,
        },
    }
    _sync_relay_closeout_counts_into_compact(
        compact,
        {
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 1,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        },
    )
    assert compact["interaction_counters"][
        "remote_command_file_bridge_agent_refresh_state_count"
    ] == 1
    assert compact["product_mode_lifecycle_contract"][
        "agent_bridge_refresh_state_count"
    ] == 1
    assert compact["product_mode_lifecycle_contract"]["closeout_satisfied"] is True


def test_skillsbench_append_history_missing_registry_is_nonfatal() -> None:
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-history-") as tmp:
        root = Path(tmp)
        compact_path = root / "benchmark_run.compact.json"
        compact_path.write_text(
            json.dumps(
                {
                    "schema_version": "benchmark_run_v0",
                    "benchmark": "skillsbench",
                    "case_id": "hello-world",
                    "score": 0.0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = parse_args(
            [
                "--route",
                "loopx-product-mode",
                "--append-history",
                "--registry",
                str(root / "missing" / ".loopx" / "registry.json"),
                "--runtime-root",
                str(root / "runtime"),
            ]
        )
        payload = append_history(args, compact_path)
        assert payload["schema_version"] == "skillsbench_history_append_result_v0"
        assert payload["requested"] is True
        assert payload["appended"] is False
        assert payload["failure_kind"] == "missing_registry", payload
        assert payload["registry_exists"] is False, payload
        assert payload["raw_cli_output_recorded"] is False, payload
        assert "/missing/.loopx/" not in json.dumps(payload), payload


def test_skillsbench_final_verifier_timeout_override_records_public_state() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

        async def soft_verify(self) -> None:
            return await self._env.exec("echo soft", timeout_sec=10)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        if "/verifier/test.sh" in command:
            raise asyncio.TimeoutError("final verifier timed out")
        return types.SimpleNamespace(return_code=0)

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=7,
        plan=plan,
        trace=trace,
    )
    try:
        try:
            asyncio.run(rollout.verify())
        except asyncio.TimeoutError:
            pass
        else:  # pragma: no cover - defensive, this is a smoke script
            raise AssertionError("expected final verifier timeout")
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert calls == [("/verifier/test.sh", {"timeout_sec": 7})], calls
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_final_verifier_timeout_enabled"] is True, prereqs
    assert prereqs["benchflow_final_verifier_timeout_sec"] == 7, prereqs
    assert prereqs["benchflow_final_verifier_timeout_override_count"] == 1, prereqs
    assert prereqs["benchflow_final_verifier_timeout_triggered"] is True, prereqs
    assert prereqs["benchflow_final_verifier_timeout_raw_command_recorded"] is False
    assert prereqs["benchflow_final_verifier_timeout_raw_output_recorded"] is False
    assert trace["benchflow_final_verifier_timeout_triggered"] is True, trace


def test_skillsbench_final_verifier_timeout_override_can_extend_timeout() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()
            self._task = types.SimpleNamespace(
                config=types.SimpleNamespace(
                    verifier=types.SimpleNamespace(timeout_sec=300)
                )
            )

        async def verify(self) -> None:
            assert self._task.config.verifier.timeout_sec == 1800
            return await self._env.exec("/verifier/test.sh", timeout_sec=900)

        async def soft_verify(self) -> None:
            return await self._env.exec("echo soft", timeout_sec=10)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        return types.SimpleNamespace(return_code=0)

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=1800,
        plan=plan,
        trace=trace,
    )
    try:
        asyncio.run(rollout.verify())
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert calls == [("/verifier/test.sh", {"timeout_sec": 1800})], calls
    assert rollout._task.config.verifier.timeout_sec == 300
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_final_verifier_timeout_enabled"] is True, prereqs
    assert prereqs["benchflow_final_verifier_timeout_sec"] == 1800, prereqs
    assert prereqs["benchflow_final_verifier_timeout_override_count"] == 1, prereqs
    assert (
        prereqs["benchflow_final_verifier_outer_timeout_override_count"] == 1
    ), prereqs
    assert "benchflow_final_verifier_timeout_triggered" not in prereqs, prereqs
    assert prereqs["benchflow_final_verifier_timeout_raw_command_recorded"] is False
    assert "test.sh" not in json.dumps(prereqs)


def test_skillsbench_intermediate_soft_verifier_timeout_override_records_public_state() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("echo final", timeout_sec=10)

        async def soft_verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        if "/verifier/test.sh" in command:
            raise TimeoutError("soft verifier timed out")
        return types.SimpleNamespace(return_code=0)

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=0,
        soft_verifier_timeout_sec=5,
        plan=plan,
        trace=trace,
    )
    try:
        try:
            asyncio.run(rollout.soft_verify())
        except (TimeoutError, asyncio.TimeoutError):
            pass
        else:  # pragma: no cover - defensive, this is a smoke script
            raise AssertionError("expected soft verifier timeout")
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert calls == [("/verifier/test.sh", {"timeout_sec": 5})], calls
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_intermediate_soft_verify_timeout_enabled"] is True
    assert prereqs["benchflow_intermediate_soft_verify_timeout_sec"] == 5
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_override_count"] == 1
    )
    assert prereqs["benchflow_intermediate_soft_verify_timeout_triggered"] is True
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_raw_output_recorded"]
        is False
    )
    assert trace["benchflow_intermediate_soft_verify_timeout_triggered"] is True
    assert "test.sh" not in json.dumps(prereqs)


def test_skillsbench_intermediate_soft_verifier_timeout_is_independent() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("echo final", timeout_sec=10)

        async def soft_verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        return types.SimpleNamespace(return_code=0)

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=10,
        final_verifier_timeout_sec=0,
        soft_verifier_timeout_sec=5,
        plan=plan,
        trace=trace,
    )
    try:
        asyncio.run(rollout.soft_verify())
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert calls == [("/verifier/test.sh", {"timeout_sec": 5})], calls
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_intermediate_soft_verify_timeout_enabled"] is True
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_override_count"] == 1
    )
    assert prereqs["benchflow_verifier_prep_timeout_override_enabled"] is False


def test_skillsbench_intermediate_soft_verifier_timeout_triggers_cleanup() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("echo final", timeout_sec=10)

        async def soft_verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        if "/verifier/test.sh" in command:
            raise TimeoutError("soft verifier timed out")
        return types.SimpleNamespace(return_code=0)

    cleanup_calls: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    def fake_cleanup(
        cleanup_plan: dict[str, Any],
        *,
        trace: dict[str, Any] | None = None,
        grace_seconds: float = 3.0,
    ) -> dict[str, Any]:
        cleanup_calls.append((cleanup_plan, trace))
        prereqs = cleanup_plan.setdefault("runner_prerequisites", {})
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_requested"
        ] = True
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read"
        ] = False
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_status"
        ] = "terminated"
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_container_count"
        ] = 1
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_match_count"
        ] = 3
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_alive_after_count"
        ] = 0
        if isinstance(trace, dict):
            trace[
                "benchflow_intermediate_soft_verify_timeout_cleanup_status"
            ] = "terminated"
        return {"status": "terminated", "match_count": 3}

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_cleanup = skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children
    skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = fake_cleanup
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=0,
        soft_verifier_timeout_sec=5,
        plan=plan,
        trace=trace,
    )
    try:
        try:
            asyncio.run(rollout.soft_verify())
        except (TimeoutError, asyncio.TimeoutError):
            pass
        else:  # pragma: no cover - defensive, this is a smoke script
            raise AssertionError("expected soft verifier timeout")
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify
        skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = (
            original_cleanup
        )

    assert len(cleanup_calls) == 1, cleanup_calls
    prereqs = plan["runner_prerequisites"]
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_cleanup_requested"]
        is True
    )
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read"]
        is False
    )
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_cleanup_status"]
        == "terminated"
    )
    assert (
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_container_count"
        ]
        == 1
    )
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_cleanup_match_count"]
        == 3
    )
    assert (
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_alive_after_count"
        ]
        == 0
    )
    assert "test.sh" not in json.dumps(prereqs)


def test_skillsbench_intermediate_soft_verifier_phase_timeout_bounds_hung_exec() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("echo final", timeout_sec=10)

        async def soft_verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        await asyncio.sleep(30)
        return types.SimpleNamespace(return_code=0)

    cleanup_calls: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    def fake_cleanup(
        cleanup_plan: dict[str, Any],
        *,
        trace: dict[str, Any] | None = None,
        grace_seconds: float = 3.0,
    ) -> dict[str, Any]:
        cleanup_calls.append((cleanup_plan, trace))
        prereqs = cleanup_plan.setdefault("runner_prerequisites", {})
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_requested"
        ] = True
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read"
        ] = False
        prereqs[
            "benchflow_intermediate_soft_verify_timeout_cleanup_status"
        ] = "terminated"
        return {"status": "terminated"}

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_cleanup = skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children
    skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = fake_cleanup
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=0,
        soft_verifier_timeout_sec=0.01,
        plan=plan,
        trace=trace,
    )
    try:
        try:
            asyncio.run(rollout.soft_verify())
        except (TimeoutError, asyncio.TimeoutError):
            pass
        else:  # pragma: no cover - defensive, this is a smoke script
            raise AssertionError("expected phase-level soft verifier timeout")
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify
        skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = (
            original_cleanup
        )

    assert calls == [("/verifier/test.sh", {"timeout_sec": 0.01})], calls
    assert len(cleanup_calls) == 1, cleanup_calls
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_intermediate_soft_verify_timeout_triggered"] is True
    assert prereqs["benchflow_intermediate_soft_verify_timeout_cleanup_requested"]
    assert (
        prereqs["benchflow_intermediate_soft_verify_timeout_raw_output_recorded"]
        is False
    )
    assert "test.sh" not in json.dumps(prereqs)


def test_skillsbench_final_verifier_phase_timeout_bounds_hung_exec() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

        async def soft_verify(self) -> None:
            return await self._env.exec("echo soft", timeout_sec=10)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        await asyncio.sleep(30)
        return types.SimpleNamespace(return_code=0)

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=0.01,
        plan=plan,
        trace=trace,
    )
    try:
        try:
            asyncio.run(rollout.verify())
        except (TimeoutError, asyncio.TimeoutError):
            pass
        else:  # pragma: no cover - defensive, this is a smoke script
            raise AssertionError("expected phase-level final verifier timeout")
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert calls == [("/verifier/test.sh", {"timeout_sec": 0.01})], calls
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_final_verifier_timeout_triggered"] is True
    assert prereqs["benchflow_final_verifier_timeout_raw_command_recorded"] is False
    assert prereqs["benchflow_final_verifier_timeout_raw_output_recorded"] is False
    assert "test.sh" not in json.dumps(prereqs)


def test_skillsbench_intermediate_soft_verifier_return_cleans_orphan_processes() -> None:
    class FakeRollout:
        def __init__(self) -> None:
            self._env = types.SimpleNamespace()

        async def verify(self) -> None:
            return await self._env.exec("echo final", timeout_sec=10)

        async def soft_verify(self) -> None:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_exec(command: str, **kwargs: Any) -> Any:
        calls.append((command, dict(kwargs)))
        return types.SimpleNamespace(return_code=0)

    cleanup_calls: list[tuple[str, str]] = []

    def fake_cleanup(
        cleanup_plan: dict[str, Any],
        *,
        trace: dict[str, Any] | None = None,
        grace_seconds: float = 3.0,
        metric_prefix: str = "benchflow_intermediate_soft_verify_timeout_cleanup",
        schema_version: str = "skillsbench_soft_verify_timeout_process_cleanup_v0",
    ) -> dict[str, Any]:
        cleanup_calls.append((metric_prefix, schema_version))
        prereqs = cleanup_plan.setdefault("runner_prerequisites", {})
        prereqs[f"{metric_prefix}_requested"] = True
        prereqs[f"{metric_prefix}_raw_logs_read"] = False
        prereqs[f"{metric_prefix}_status"] = "terminated"
        prereqs[f"{metric_prefix}_match_count"] = 2
        if isinstance(trace, dict):
            trace[f"{metric_prefix}_status"] = "terminated"
        return {"status": "terminated", "match_count": 2}

    rollout = FakeRollout()
    rollout._env.exec = fake_exec
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_cleanup = skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children
    skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = fake_cleanup
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=0,
        soft_verifier_timeout_sec=5,
        plan=plan,
        trace=trace,
    )
    try:
        asyncio.run(rollout.soft_verify())
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify
        skillsbench_loop.cleanup_benchflow_soft_verify_timeout_children = (
            original_cleanup
        )

    assert calls == [("/verifier/test.sh", {"timeout_sec": 5})], calls
    assert cleanup_calls == [
        (
            "benchflow_intermediate_soft_verify_orphan_cleanup",
            "skillsbench_soft_verify_orphan_process_cleanup_v0",
        )
    ]
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_intermediate_soft_verify_orphan_cleanup_requested"]
    assert (
        prereqs["benchflow_intermediate_soft_verify_orphan_cleanup_raw_logs_read"]
        is False
    )
    assert (
        prereqs["benchflow_intermediate_soft_verify_orphan_cleanup_status"]
        == "terminated"
    )
    assert (
        prereqs["benchflow_intermediate_soft_verify_orphan_cleanup_match_count"]
        == 2
    )
    assert "benchflow_intermediate_soft_verify_timeout_cleanup_requested" not in prereqs


def test_skillsbench_local_driver_a2a_contract_keeps_codex_local() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_a2a_participant_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_local_codex_cli_participant_not_materialized"
    ), payload
    assert payload["local_driver_contract"]["ready"] is False, payload
    assert (
        payload["local_driver_contract"]["codex_cli_participant_materialized"]
        is False
    ), payload
    assert (
        payload["local_driver_contract"]["a2a_worker_handshake_materialized"]
        is False
    ), payload
    assert payload["local_driver_contract"]["credential_sync_allowed"] is False, payload
    assert payload["remote_executor_contract"]["ready"] is True, payload
    assert (
        payload["remote_executor_contract"]["remote_codex_runtime_allowed"] is False
    ), payload
    assert (
        payload["remote_executor_contract"]["remote_model_api_invocation_allowed"]
        is False
    ), payload
    assert payload["boundary"]["upload_allowed"] is False, payload
    assert payload["boundary"]["submit_allowed"] is False, payload
    assert payload["mini_pair"]["routes"] == [
        "raw-codex-autonomous-max5",
        "loopx-goal-start-product-mode",
    ], payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in (
        "/Users/",
        "~/.codex",
        "OPENAI_API_KEY",
        "HF_TOKEN",
        "raw_task_text_publication_allowed",
    ):
        assert forbidden not in text, forbidden


def test_skillsbench_local_driver_a2a_contract_ready_only_after_both_sides() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_a2a_participant_ready=True,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"]
        == "ready_for_skillsbench_local_driver_a2a_mini_pair"
    ), payload
    assert (
        payload["next_action"] == "launch_no_upload_skillsbench_local_driver_a2a_mini_pair"
    ), payload
    assert payload["local_driver_contract"]["ready"] is True, payload
    assert payload["remote_executor_contract"]["ready"] is True, payload
    assert payload["boundary"]["raw_logs_public"] is False, payload
    assert payload["read_boundary"]["compact_only"] is True, payload


def test_skillsbench_local_driver_a2a_contract_distinguishes_cli_from_handshake() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_codex_cli_participant_ready=True,
        local_a2a_worker_handshake_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_local_acp_relay_missing"
    ), payload
    assert (
        payload["next_action"]
        == "wire_local_acp_relay_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["codex_cli_participant_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"]["a2a_worker_handshake_materialized"]
        is False
    ), payload
    assert payload["local_driver_contract"]["worker_protocol"] == "acp_stdio", payload


def test_skillsbench_worker_handshake_preflight_exposes_acp_relay_gap() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "skillsbench_local_acp_relay_missing", payload
    assert payload["next_action"] == "implement_local_acp_stdio_relay_before_mini_pair", payload
    assert payload["benchflow_contract"]["worker_protocol"] == "acp_stdio", payload
    assert payload["benchflow_contract"]["stdio_transport_required"] is True, payload
    assert payload["local_driver_contract"]["remote_codex_runtime_allowed"] is False, payload
    assert payload["boundary"]["raw_task_text_read"] is False, payload
    assert payload["boundary"]["credential_values_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_distinguishes_host_transport() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"] == "skillsbench_host_local_acp_transport_missing"
    ), payload
    assert (
        payload["next_action"] == "wire_host_local_acp_transport_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["acp_relay_materialized"] is True
    ), payload
    assert (
        payload["local_driver_contract"]["host_local_acp_transport_materialized"]
        is False
    ), payload


def test_skillsbench_worker_handshake_preflight_distinguishes_remote_bridge() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=True,
        remote_command_file_bridge_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "skillsbench_remote_command_file_bridge_missing"
    assert (
        payload["next_action"]
        == "wire_bounded_remote_command_file_bridge_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["host_local_acp_transport_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_materialized"]
        is False
    ), payload


def test_skillsbench_remote_command_file_bridge_probe_requires_command() -> None:
    payload = run_skillsbench_remote_command_file_bridge_probe(None)
    assert (
        payload["schema_version"]
        == SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_remote_command_file_bridge_probe_command_missing"
    ), payload
    assert payload["bridge_command_invoked"] is False, payload
    assert payload["raw_command_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload


def test_skillsbench_remote_command_file_bridge_probe_fake_bridge_ready() -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/skillsbench_remote_command_file_bridge.py"),
        "--serve-probe",
    ]
    assert skillsbench_remote_command_file_bridge_command_is_fixture_probe(command)
    assert not skillsbench_remote_command_file_bridge_command_is_fixture_probe(
        [sys.executable, "private-skillsbench-sandbox-bridge", "--serve-probe"]
    )
    payload = run_skillsbench_remote_command_file_bridge_probe(command)
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"] == "skillsbench_remote_command_file_bridge_ready"
    ), payload
    assert payload["bridge_command_invoked"] is True, payload
    assert payload["operation_count"] == 4, payload
    assert payload["missing_operations"] == [], payload
    assert payload["failed_operations"] == [], payload
    assert payload["boundary_violations"] == [], payload
    assert {item["kind"] for item in payload["operations"]} == {
        "exec",
        "write_file",
        "read_file",
        "cleanup",
    }, payload
    assert payload["raw_command_recorded"] is False, payload
    assert payload["raw_stdout_recorded"] is False, payload
    assert payload["raw_stderr_recorded"] is False, payload
    assert payload["raw_task_text_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload
    assert payload["remote_paths_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_remote_command_file_bridge_probe_preserves_response_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake_bridge = Path(tmp) / "fake-bridge-failure.py"
        fake_bridge.write_text(
            f"""#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, {str(REPO_ROOT)!r})
from loopx.benchmark_adapters.skillsbench_remote_bridge import (
    build_skillsbench_remote_command_file_bridge_probe_response,
)

print(json.dumps(build_skillsbench_remote_command_file_bridge_probe_response(
    ready=False,
    first_blocker="skillsbench_remote_bridge_target_env_missing",
    stage="remote_ssh_probe",
    operations=[
        {{"kind": "exec", "label": "bounded_noop_command", "status": "blocked", "exit_code_zero": False}},
        {{"kind": "write_file", "label": "probe_marker_write", "status": "blocked"}},
        {{"kind": "read_file", "label": "probe_marker_read", "status": "blocked", "content_match": False}},
        {{"kind": "cleanup", "label": "probe_marker_cleanup", "status": "blocked"}},
    ],
), sort_keys=True))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o755)

        payload = run_skillsbench_remote_command_file_bridge_probe(
            [sys.executable, str(fake_bridge)]
        )

    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_remote_command_file_bridge_operation_failed"
    ), payload
    assert (
        payload["response_first_blocker"]
        == "skillsbench_remote_bridge_target_env_missing"
    ), payload
    assert payload["failed_operations"] == [
        "exec",
        "write_file",
        "read_file",
        "cleanup",
    ], payload
    assert payload["stage"] == "remote_ssh_probe", payload


def test_skillsbench_worker_handshake_preflight_accepts_bridge_probe() -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/skillsbench_remote_command_file_bridge.py"),
        "--serve-probe",
    ]
    bridge_probe = run_skillsbench_remote_command_file_bridge_probe(command)
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=True,
        remote_command_file_bridge_probe=bridge_probe,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"]
        == "ready_for_skillsbench_local_driver_worker_handshake"
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"][
            "remote_command_file_bridge_readiness_source"
        ]
        == "probe"
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_probe"]["ready"]
        is True
    ), payload
    assert payload["remote_executor_contract"]["command_file_bridge_ready"] is True
    assert "skillsbench_remote_command_file_bridge_missing" not in payload["blockers"]


def test_skillsbench_local_acp_relay_probe_completes_stdio_handshake() -> None:
    payload = run_skillsbench_local_acp_relay_probe(timeout_sec=10)
    assert (
        payload["schema_version"]
        == SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is True, payload
    assert payload["first_blocker"] == "skillsbench_local_acp_relay_ready", payload
    assert payload["worker_protocol"] == "acp_stdio", payload
    assert payload["request_count"] == 4, payload
    assert payload["codex_cli_invoked"] is False, payload
    assert payload["raw_output_recorded"] is False, payload
    assert payload["raw_event_jsonl_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_host_local_acp_transport_probe_uses_benchflow_client() -> None:
    skillsbench_root = REPO_ROOT / ".local/benchmark/externals/skillsbench"
    if not (skillsbench_root / ".venv").exists():
        return
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/skillsbench_automation_loop.py"),
            "--route",
            "codex-acp-blind-loop-baseline",
            "--local-driver-worker-handshake-preflight",
            "--local-codex-cli-participant-ready",
            "--local-acp-relay-probe",
            "--host-local-acp-transport-probe",
            "--task-id",
            "ada-bathroom-plan-repair",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    probe = payload["local_driver_contract"]["host_local_acp_transport_probe"]
    assert probe["ready"] is True, payload
    assert probe["first_blocker"] == "skillsbench_host_local_acp_transport_ready"
    assert probe["benchflow_acp_client_used"] is True, payload
    assert probe["transport"] == "host_local_stdio", payload
    assert probe["container_transport_used"] is False, payload
    assert probe["request_count"] == 4, payload
    assert probe["codex_cli_invoked"] is False, payload
    assert probe["raw_output_recorded"] is False, payload
    assert probe["raw_event_jsonl_recorded"] is False, payload
    assert probe["credential_values_recorded"] is False, payload
    assert probe["host_paths_recorded"] is False, payload
    assert payload["first_blocker"] == "skillsbench_remote_command_file_bridge_missing"
    assert (
        payload["next_action"]
        == "wire_bounded_remote_command_file_bridge_before_mini_pair"
    ), payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_probe_clears_relay_gap() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-worker-preflight-") as tmp:
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/skillsbench_automation_loop.py"),
                "--route",
                "codex-acp-blind-loop-baseline",
                "--local-driver-worker-handshake-preflight",
                "--skillsbench-root",
                str(Path(tmp) / "missing-skillsbench"),
                "--local-codex-cli-participant-ready",
                "--local-acp-relay-probe",
                "--task-id",
                "ada-bathroom-plan-repair",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
    assert payload["local_driver_contract"]["acp_relay_materialized"] is True, payload
    assert (
        payload["local_driver_contract"]["acp_relay_probe"]["ready"] is True
    ), payload
    assert "skillsbench_local_acp_relay_missing" not in payload["blockers"], payload
    assert payload["first_blocker"] == "skillsbench_benchflow_runtime_missing"
    assert payload["next_action"] == "install_or_select_skillsbench_benchflow_runtime"
    assert payload["boundary"]["credential_values_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_missing_runtime_is_compact() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-worker-preflight-") as tmp:
        payload = inspect_skillsbench_worker_handshake(
            skillsbench_root=Path(tmp) / "missing-skillsbench",
            dataset="skillsbench@1.1",
            task_id="ada-bathroom-plan-repair",
            local_codex_cli_participant_ready=True,
        )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert "skillsbench_local_acp_relay_missing" in payload["blockers"], payload
    assert payload["boundary"]["host_paths_recorded"] is False, payload


def test_local_codex_participant_ping_missing_binary_is_compact() -> None:
    payload = materialize_local_codex_participant(
        codex_bin="/definitely/missing/loopx-codex",
        timeout_sec=1,
    )
    assert (
        payload["schema_version"]
        == LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "local_codex_cli_not_on_path", payload
    assert payload["codex_cli_invoked"] is False, payload
    assert payload["raw_output_recorded"] is False, payload
    assert payload["raw_event_jsonl_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload


def test_blind_loop_continuation_reprojects_round_one_constraints() -> None:
    clause = _blind_loop_persistent_continuation_clause(
        "Inspect /app/trl only. Do not modify /app/train_grpo.py or "
        "/app/reward_fn.py. Avoid broad rewrites."
    )
    assert "do not invoke /goal mode" in clause, clause
    assert "external LoopX CLI" in clause, clause
    assert "upload, submit" in clause, clause
    assert "ask the human" in clause, clause
    assert "/app/train_grpo.py" in clause, clause
    assert "/app/reward_fn.py" in clause, clause
    assert "/app/trl" not in clause, clause


def test_product_mode_declared_done_marker_detection() -> None:
    class FakeRoundResult:
        trajectory = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": f"Done. {DECLARED_DONE_MARKER}",
                    }
                ],
            }
        ]

    assert _round_result_declared_done(FakeRoundResult()) is True


def test_product_mode_declared_done_ignores_user_prompt_marker() -> None:
    class FakeRoundResult:
        trajectory = [
            {
                "role": "user",
                "type": "message",
                "content": (
                    "Only end with "
                    f"{DECLARED_DONE_MARKER} after no remaining goals."
                ),
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Not complete; more local task work remains.",
                    }
                ],
            },
        ]

    assert _round_result_declared_done(FakeRoundResult()) is False


def test_skillsbench_codex_exec_failure_category_is_actionable() -> None:
    assert (
        _codex_exec_failure_category(
            returncode=1,
            stderr_text="Not authenticated. Please login before running codex exec.",
        )
        == "codex_auth_or_login_required"
    )
    assert (
        _codex_exec_failure_category(
            returncode=1,
            stderr_text="Requested model loopx-test-model does not exist.",
        )
        == "codex_model_unavailable"
    )
    assert (
        _codex_exec_failure_category(
            returncode=1,
            stderr_text=(
                "The 'gpt-5' model is not supported when using Codex "
                "with a ChatGPT account."
            ),
        )
        == "codex_model_unavailable"
    )
    assert (
        _codex_exec_failure_category(
            returncode=1,
            stderr_text=(
                "failed to connect to websocket: IO error: Connection refused "
                "(os error 111), url: "
                "wss://chatgpt.com/backend-api/codex/responses"
            ),
        )
        == "codex_responses_stream_unavailable"
    )
    assert (
        _codex_exec_failure_category(
            returncode=1,
            stderr_text="codex: No such file or directory",
        )
        == "codex_cli_or_environment_missing"
    )
    assert (
        _codex_exec_failure_category(returncode=1, stderr_text="unexpected failure")
        == "codex_exec_exit_1"
    )


def test_host_local_relay_timeout_returns_recoverable_turn_message() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-recoverable-timeout-") as tmp:
        root = Path(tmp)
        fake_codex = root / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import sys

print("codex_exec_bridge_idle_timeout", file=sys.stderr)
raise SystemExit(124)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        trace_dir = root / "traces"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                codex_bin=str(fake_codex),
                route="loopx-goal-start-product-mode",
                timeout_sec=5,
                worker_public_trace_dir=str(trace_dir),
            )
        )
        response = relay._run_codex(
            "public-safe prompt placeholder",
            session={"cwd": str(root)},
            session_id="session-recoverable-timeout",
            stdout=io.StringIO(),
        )
        assert "LoopX recoverable Codex turn failure" in response
        assert "codex_exec_bridge_idle_timeout" in response
        trace_text = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(trace_dir.glob("*.json"))
        )
        assert "codex_exec_bridge_idle_timeout" in trace_text
        assert '"raw_task_text_recorded": false' in trace_text
        assert '"credential_values_recorded": false' in trace_text


def test_product_mode_case_state_seed_uses_active_goal_shape() -> None:
    seed = product_mode_case_state_seed_text(
        task_id="sample-task",
        route="loopx-product-mode",
        max_rounds=5,
    )
    assert f"goal_id: {skillsbench_loop.PRODUCT_MODE_CASE_GOAL_ID}" in seed
    assert f"schema_version: {PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION}" in seed
    assert f"case_state_path: `{PRODUCT_MODE_CASE_STATE_PATH}`" in seed
    assert "## Agent Todo" in seed
    assert "## Local Evidence" in seed
    assert "## Replan Log" in seed
    assert "## Remaining Goals" in seed
    assert ".loopx-case-state.md" not in seed


def test_product_mode_declared_done_requires_case_state_depth() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-depth-gate-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_depth_gate_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": f"Maintain {PRODUCT_MODE_CASE_STATE_PATH}.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=5,
                trace=trace,
                plan=plan,
            )
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Done. {DECLARED_DONE_MARKER}",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                1,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "Mandatory LoopX lifecycle checkpoint" in prompt
        assert "quota should-run --goal-id skillsbench-case" in prompt
        assert "todo claim --goal-id skillsbench-case" in prompt
        assert "todo update --goal-id skillsbench-case" in prompt
        assert "refresh-state --goal-id skillsbench-case" in prompt
        assert "You declared done" in prompt
        assert PRODUCT_MODE_CASE_STATE_PATH in prompt
        assert trace["product_mode_depth_gate_gap"] is True, trace
        assert trace["product_mode_depth_gate_gap_round"] == 1, trace
        assert (
            trace["last_decision"]
            == "send_product_mode_lifecycle_checkpoint_continuation"
        )
        assert trace["product_mode_lifecycle_checkpoint_required"] is True, trace
        assert trace["product_mode_lifecycle_checkpoint_round"] == 1, trace
        assert trace["product_mode_lifecycle_checkpoint_count"] == 1, trace
        assert trace["product_mode_lifecycle_checkpoint_missing_reason"] == (
            "missing_case_local_loopx_state_read_or_write"
        )
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 0, trace
        assert trace.get("agent_declared_done") is not True, trace


def test_product_mode_declared_done_requires_solver_activity_after_driver_lifecycle() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-solver-activity-gate-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_solver_activity_gate_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": "LoopX product-mode treatment round 1.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 1,
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 3,
            "remote_command_file_bridge_agent_loopx_state_read_count": 2,
            "remote_command_file_bridge_agent_loopx_state_write_count": 1,
            "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
            "remote_command_file_bridge_agent_todo_closeout_count": 0,
            "remote_command_file_bridge_agent_refresh_state_count": 0,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 0,
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=5,
                trace=trace,
                plan=plan,
            )
            user._task_instruction_sent = True
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            n_tool_calls = 0
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Done. {DECLARED_DONE_MARKER}",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                1,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "Mandatory product-mode solver checkpoint" in prompt
        assert "selected P0 solver/closeout evidence" in prompt
        assert "--- TASK INSTRUCTION ---" in prompt
        assert "Fix the fixture." in prompt
        assert "The task above remains the primary objective" in prompt
        assert "write or validate that path before closeout" in prompt
        assert "task-facing sandbox bridge operation" in prompt
        assert "todo complete" in prompt
        assert "benchmark_case_agent_closeout" in prompt
        assert "quota spend-slot" in prompt
        assert "--source adapter --execute" in prompt
        assert "Read-only LoopX calls" in prompt
        assert "state edits without a spend event" in prompt
        assert "Do not answer with prose only" in prompt
        assert (
            trace["last_decision"]
            == "send_product_mode_solver_activity_continuation"
        )
        assert trace["product_mode_solver_activity_required"] is True, trace
        assert trace["product_mode_solver_activity_gap"] is True, trace
        assert trace["product_mode_solver_activity_gap_round"] == 1, trace
        assert trace["product_mode_solver_activity_gap_count"] == 1, trace
        assert trace["product_mode_solver_activity_missing_reason"] == (
            "missing_task_facing_activity_or_agent_closeout_before_declared_done"
        )
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 0, trace
        assert trace.get("agent_declared_done") is not True, trace


def test_product_mode_declared_done_runs_one_typed_repair_then_stops_without_delta() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-declared-done-score-zero-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_declared_done_score_zero_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": "LoopX product-mode treatment round 1.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
            "selected_p0_todo_id": "todo_fixture_primary",
            "remote_command_file_bridge_agent_successful_loopx_command_records": [
                {
                    "subcommand": "todo complete",
                    "todo_id": "todo_fixture_primary",
                }
            ],
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 2,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 10,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 6,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 5,
            "remote_command_file_bridge_agent_task_facing_operation_count": 4,
            "remote_command_file_bridge_agent_task_facing_success_count": 4,
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 1,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=24,
                trace=trace,
                plan=plan,
            )
            user._task_instruction_sent = True
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            n_tool_calls = 0
            rewards = {"reward": 0.0}
            verifier_error = None
            verifier_output = None
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Done. {DECLARED_DONE_MARKER}",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                2,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "Scheduled typed repair/replan round 3 of 24" in prompt
        assert "create one scoped successor agent todo" in prompt
        assert "successful task-facing/validation operation" in prompt
        assert "reward" not in prompt.lower()
        assert "verifier" not in prompt.lower()
        assert trace["last_decision"] == (
            "send_product_mode_typed_repair_after_declared_done"
        )
        assert trace["agent_declared_done"] is True, trace
        assert trace["declared_done_round"] == 2, trace
        assert trace["declared_done_score"] == 0.0, trace
        assert trace["product_mode_declared_done_below_passing_reward"] is True
        assert trace["product_mode_declared_done_below_passing_reward_round"] == 2
        assert trace["product_mode_declared_done_below_passing_reward_count"] == 1
        assert trace["product_mode_declared_done_below_passing_reward_score"] == 0.0
        assert trace["product_mode_declared_done_policy"] == (
            "one_typed_repair_then_delta_gated_continue_or_terminal"
        )
        assert trace["product_mode_typed_repair_pending"] is True
        assert trace["product_mode_typed_repair_round_entered"] == 3
        assert trace["product_mode_typed_repair_round_entered_count"] == 1
        assert trace["product_mode_typed_repair_todo_identity_observed"] is False
        assert trace["product_mode_typed_repair_task_or_validation_delta"] is False
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 0, trace

        prompt = asyncio.run(
            user.run(
                3,
                "Continue fixing the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is None, trace
        assert trace["last_decision"] == (
            "stop_after_product_mode_typed_repair_without_delta"
        )
        assert trace["agent_declared_done"] is True, trace
        assert trace["declared_done_round"] == 2, trace
        assert trace["declared_done_score"] == 0.0, trace
        assert trace["product_mode_declared_done_below_passing_reward_count"] == 1
        assert trace["product_mode_typed_repair_pending"] is False
        assert trace["product_mode_typed_repair_delta_observed"] is False
        assert trace["product_mode_typed_repair_terminal"] is True
        assert trace["product_mode_typed_repair_terminal_round"] == 3
        assert trace["product_mode_typed_repair_terminal_receipt_consistent"] is True
        receipt = trace["product_mode_typed_repair_terminal_receipt"]
        assert receipt["status"] == "terminal", receipt
        assert receipt["reason"] == (
            "repair_round_without_todo_task_or_validation_delta"
        )
        assert receipt["repair_round_entered"] == 3, receipt
        assert receipt["repair_todo_identity_observed"] is False, receipt
        assert receipt["repair_task_or_validation_delta"] is False, receipt
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 1, trace


def test_product_mode_closeout_without_done_does_not_trigger_typed_repair() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-closeout-score-zero-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_closeout_score_zero_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": "LoopX product-mode treatment round 1.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 2,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 10,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 6,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 5,
            "remote_command_file_bridge_agent_task_facing_operation_count": 4,
            "remote_command_file_bridge_agent_task_facing_success_count": 4,
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 1,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=24,
                trace=trace,
                plan=plan,
            )
            user._task_instruction_sent = True
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            n_tool_calls = 0
            rewards = {"reward": 0.0}
            verifier_error = None
            verifier_output = None
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Case-local LoopX closeout completed.",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                2,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert trace.get("agent_declared_done") is not True, trace
        assert trace.get("product_mode_typed_repair_required") is not True, trace
        assert trace["stop_decision_count"] == 0, trace

        prompt = asyncio.run(
            user.run(
                3,
                "Continue fixing the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert trace.get("agent_declared_done") is not True, trace
        assert trace.get("product_mode_typed_repair_required") is not True, trace
        assert trace["last_decision"] == "send_product_mode_scheduled_continuation"
        assert trace["followup_prompt_count"] == 2, trace
        assert trace["stop_decision_count"] == 0, trace


def test_product_mode_declared_done_missing_reward_continues() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-declared-done-no-reward-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_declared_done_missing_reward_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": "LoopX product-mode treatment round 1.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 2,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 10,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 6,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 5,
            "remote_command_file_bridge_agent_task_facing_operation_count": 4,
            "remote_command_file_bridge_agent_task_facing_success_count": 4,
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 1,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=24,
                trace=trace,
                plan=plan,
            )
            user._task_instruction_sent = True
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            n_tool_calls = 0
            rewards = {}
            verifier_error = None
            verifier_output = None
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Done. {DECLARED_DONE_MARKER}",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                2,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "Scheduled product-mode continuation round 3 of 24" in prompt
        assert "official verifier passed or failed" in prompt
        assert trace["last_decision"] == (
            "send_product_mode_success_or_budget_continuation_after_declared_done"
        )
        assert trace["agent_declared_done"] is True, trace
        assert trace["declared_done_round"] == 2, trace
        assert "declared_done_score" not in trace, trace
        assert trace["product_mode_declared_done_below_passing_reward"] is True
        assert trace["product_mode_declared_done_below_passing_reward_round"] == 2
        assert trace["product_mode_declared_done_below_passing_reward_count"] == 1
        assert (
            trace["product_mode_declared_done_below_passing_reward_score_status"]
            == "missing"
        )
        assert trace["product_mode_declared_done_policy"] == (
            "continue_until_official_success_or_budget"
        )
        assert trace.get("product_mode_typed_repair_required") is not True
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 0, trace


def test_product_mode_missing_lifecycle_prompts_exact_checkpoint() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-lifecycle-checkpoint-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_lifecycle_checkpoint_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": "LoopX product-mode treatment round 1.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=5,
                trace=trace,
                plan=plan,
            )
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Still working.",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                1,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "Mandatory LoopX lifecycle checkpoint" in prompt
        assert "quota should-run --goal-id skillsbench-case" in prompt
        assert "todo claim --goal-id skillsbench-case" in prompt
        assert "todo update --goal-id skillsbench-case" in prompt
        assert "refresh-state --goal-id skillsbench-case" in prompt
        assert "Do not answer with prose only" in prompt
        assert (
            trace["last_decision"]
            == "send_product_mode_lifecycle_checkpoint_continuation"
        )
        assert trace["product_mode_lifecycle_checkpoint_required"] is True
        assert trace["product_mode_lifecycle_checkpoint_round"] == 1
        assert trace["product_mode_lifecycle_checkpoint_count"] == 1
        assert trace["product_mode_lifecycle_checkpoint_missing_reason"] == (
            "missing_case_local_loopx_state_read_or_write"
        )
        assert trace["followup_prompt_count"] == 1
        assert trace["stop_decision_count"] == 0


def test_product_mode_no_tool_call_continues_before_checkpoint_loop() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-tool-lifecycle-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_no_tool_lifecycle_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "user_message",
                            "text": "LoopX product-mode treatment round 1.",
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "type": "agent_message",
                            "text": "I cannot continue without more context.",
                        },
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=8,
                trace=trace,
                plan=plan,
            )
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "I cannot continue without more context.",
                        }
                    ],
                }
            ]
            n_tool_calls = 0

        prompt = asyncio.run(
            user.run(
                1,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None
        assert "not a valid closeout" in prompt
        assert "command/file bridge" in prompt
        assert (
            trace["last_decision"]
            == "send_followup_after_product_mode_no_tool_calls_without_lifecycle"
        )
        assert trace["product_mode_lifecycle_checkpoint_required"] is True
        assert trace["product_mode_lifecycle_checkpoint_count"] == 1
        assert trace["product_mode_lifecycle_checkpoint_round"] == 1
        assert trace.get("product_mode_no_tool_call_lifecycle_abort") is not True
        assert trace["followup_prompt_count"] == 1
        assert trace["stop_decision_count"] == 0


def test_product_mode_workflow_driver_task_bridge_activity_avoids_no_tool_abort() -> None:
    trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-product-mode",
        "loopx_state_reads": 0,
        "loopx_state_writes": 0,
        "loopx_case_state_reads": 0,
        "loopx_case_state_writes": 0,
        "remote_command_file_bridge_driver_lifecycle_execution_style": (
            "orchestrated_agentloop_loopx_cli"
        ),
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
        "remote_command_file_bridge_driver_lifecycle_success_count": 4,
        "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
        "remote_command_file_bridge_agent_operation_trace_status": (
            "agent_operation_trace_recorded"
        ),
        "remote_command_file_bridge_agent_operation_trace_count": 1,
        "remote_command_file_bridge_agent_request_count": 1,
        "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
        "heartbeat_count": 0,
        "controller_action_decisions": 0,
        "initial_prompt_count": 0,
        "followup_prompt_count": 0,
        "stop_decision_count": 0,
        "reward_observation_count": 0,
        "round_rewards": [],
    }
    plan = {
        "runner_prerequisites": {
            "loopx_workflow_lifecycle_checkpoint": True,
            "loopx_product_mode_lifecycle_driver_kind": (
                "orchestrated_agentloop_loopx_cli"
            ),
        }
    }
    saved_modules = {
        name: sys.modules.get(name)
        for name in (
            "benchflow",
            "benchflow.sandbox",
            "benchflow.sandbox.user",
        )
    }
    fake_benchflow = types.ModuleType("benchflow")
    fake_sandbox = types.ModuleType("benchflow.sandbox")
    fake_user = types.ModuleType("benchflow.sandbox.user")

    class FakeBaseUser:
        pass

    class FakeRoundResultBase:
        pass

    fake_user.BaseUser = FakeBaseUser
    fake_user.RoundResult = FakeRoundResultBase
    sys.modules["benchflow"] = fake_benchflow
    sys.modules["benchflow.sandbox"] = fake_sandbox
    sys.modules["benchflow.sandbox.user"] = fake_user
    try:
        user = _build_product_mode_user(
            route="loopx-product-mode",
            max_rounds=8,
            trace=trace,
            plan=plan,
            case_payload={"canonical_product_mode_lifecycle_driver": True},
        )
    finally:
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    initial_prompt = asyncio.run(user.run(0, "Fix the fixture."))
    assert initial_prompt is not None, trace
    assert "canonical workflow lifecycle driver has already" in initial_prompt

    class FakeRoundResult:
        rewards = {}
        trajectory = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Inspected the sandbox through the bridge.",
                    }
                ],
            }
        ]
        n_tool_calls = 0

    prompt = asyncio.run(
        user.run(
            1,
            "Fix the fixture.",
            round_result=FakeRoundResult(),
        )
    )
    assert prompt is not None, trace
    assert "Mandatory product-mode solver checkpoint" in prompt
    assert "--- TASK INSTRUCTION ---" in prompt
    assert "Fix the fixture." in prompt
    assert "The task above remains the primary objective" in prompt
    assert "write or validate that path before closeout" in prompt
    assert "task-facing sandbox bridge operation" in prompt
    assert "selected P0 closeout sequence" in prompt
    assert (
        trace["last_decision"]
        == "send_product_mode_solver_activity_continuation"
    ), trace
    assert trace["product_mode_solver_activity_gap"] is True, trace
    assert trace["product_mode_solver_activity_gap_count"] == 1, trace
    assert trace["product_mode_solver_activity_gap_round"] == 1, trace
    assert trace.get("product_mode_no_tool_call_lifecycle_abort") is not True, trace
    assert trace.get("product_mode_no_lifecycle_request_abort") is not True, trace
    assert trace["followup_prompt_count"] == 1, trace
    assert trace["stop_decision_count"] == 0, trace


def test_product_mode_official_success_stops_without_final_closeout_checkpoint() -> None:
    trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-goal-start-product-mode",
        "loopx_state_reads": 0,
        "loopx_state_writes": 0,
        "loopx_case_state_reads": 0,
        "loopx_case_state_writes": 0,
        "remote_command_file_bridge_driver_lifecycle_execution_style": (
            "orchestrated_agentloop_loopx_cli"
        ),
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
        "remote_command_file_bridge_driver_lifecycle_success_count": 4,
        "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
        "remote_command_file_bridge_agent_operation_trace_status": (
            "agent_operation_trace_recorded"
        ),
        "remote_command_file_bridge_agent_operation_trace_count": 4,
        "remote_command_file_bridge_agent_request_count": 4,
        "remote_command_file_bridge_agent_task_facing_operation_count": 3,
            "remote_command_file_bridge_agent_task_facing_success_count": 3,
        "remote_command_file_bridge_agent_todo_closeout_count": 0,
        "remote_command_file_bridge_agent_refresh_state_count": 0,
        "remote_command_file_bridge_agent_quota_spend_slot_count": 0,
        "heartbeat_count": 0,
        "controller_action_decisions": 0,
        "initial_prompt_count": 0,
        "followup_prompt_count": 0,
        "stop_decision_count": 0,
        "reward_observation_count": 0,
        "round_rewards": [],
    }
    plan = {
        "runner_prerequisites": {
            "loopx_workflow_lifecycle_checkpoint": True,
            "loopx_product_mode_lifecycle_driver_kind": (
                "orchestrated_agentloop_loopx_cli"
            ),
        }
    }
    saved_modules = {
        name: sys.modules.get(name)
        for name in (
            "benchflow",
            "benchflow.sandbox",
            "benchflow.sandbox.user",
        )
    }
    fake_benchflow = types.ModuleType("benchflow")
    fake_sandbox = types.ModuleType("benchflow.sandbox")
    fake_user = types.ModuleType("benchflow.sandbox.user")

    class FakeBaseUser:
        pass

    class FakeRoundResultBase:
        pass

    fake_user.BaseUser = FakeBaseUser
    fake_user.RoundResult = FakeRoundResultBase
    sys.modules["benchflow"] = fake_benchflow
    sys.modules["benchflow.sandbox"] = fake_sandbox
    sys.modules["benchflow.sandbox.user"] = fake_user
    try:
        user = _build_product_mode_user(
            route="loopx-product-mode",
            max_rounds=2,
            trace=trace,
            plan=plan,
            case_payload={"canonical_product_mode_lifecycle_driver": True},
        )
        user._task_instruction_sent = True
    finally:
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    class FakeRoundResult:
        rewards = {"reward": 1.0}
        n_tool_calls = 0
        trajectory = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Local validation completed through bridge commands.",
                    }
                ],
            }
        ]

    prompt = asyncio.run(
        user.run(
            2,
            "Fix the fixture.",
            round_result=FakeRoundResult(),
        )
    )
    assert prompt is None, trace
    assert (
        trace["last_decision"]
        == "stop_after_product_mode_official_success_observed_without_feedback"
    ), trace
    assert trace["official_success_observed"] is True, trace
    assert (
        trace["product_mode_final_closeout_superseded_by_official_success"] is True
    ), trace
    assert trace["product_mode_final_closeout_superseded_round"] == 2, trace
    assert trace["product_mode_final_closeout_superseded_reason"] == (
        "official_success_observed_before_selected_p0_closeout"
    )
    assert trace.get("product_mode_final_closeout_required") is not True, trace
    assert trace.get("product_mode_final_closeout_checkpoint_count", 0) == 0, trace
    assert trace.get("product_mode_solver_activity_gap") is not True, trace
    assert trace["followup_prompt_count"] == 0, trace
    assert trace["stop_decision_count"] == 1, trace
    with tempfile.TemporaryDirectory(
        prefix="skillsbench-success-supersedes-closeout-"
    ) as tmp:
        result_path = write_official_skillsbench_result(
            Path(tmp),
            reward=1.0,
            task_id="sample-task",
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert (
            counters["product_mode_final_closeout_superseded_by_official_success"]
            is True
        ), compact
        assert counters["product_mode_final_closeout_superseded_round"] == 2, compact
        assert counters["product_mode_final_closeout_superseded_reason"] == (
            "official_success_observed_before_selected_p0_closeout"
        ), compact


def test_product_mode_agent_trace_no_requests_stops_before_verifier() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-agent-requests-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_no_agent_requests_fixture"
        rollout_name = "case__loopx_product_mode"
        trace_dir = root / "public-traces"
        trace_dir.mkdir(parents=True)
        write_json(
            trace_dir / "agent-ops.compact.json",
            {
                "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
                "trace_kind": "remote_command_file_bridge_agent_operations",
                "boundary": {
                    "raw_command_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "upload_performed": False,
                    "submit_performed": False,
                },
                "remote_command_file_bridge_agent_operations": {
                    "request_count": 0,
                    "loopx_cli_call_count": 0,
                    "loopx_state_read_count": 0,
                    "loopx_state_write_count": 0,
                    "operation_counts": {},
                    "loopx_cli_subcommand_counts": {},
                    "raw_material_recorded": False,
                },
            },
        )
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_operation_trace_required": True,
            },
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="loopx-product-mode",
                max_rounds=8,
                trace=trace,
                plan=plan,
            )
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "I used ordinary tools, but not LoopX.",
                        }
                    ],
                }
            ]
            n_tool_calls = 2

        try:
            asyncio.run(
                user.run(
                    1,
                    "Fix the fixture.",
                    round_result=FakeRoundResult(),
                )
            )
        except SkillsBenchProductModeNoLifecycleRequests as exc:
            assert "no case-local LoopX lifecycle request" in str(exc)
        else:
            raise AssertionError("product-mode no-request trace must stop early")
        assert (
            trace["last_decision"]
            == "stop_after_product_mode_agent_no_lifecycle_requests"
        ), trace
        assert trace["remote_command_file_bridge_agent_operation_trace_status"] == (
            "agent_operation_trace_present_no_requests"
        )
        assert trace["remote_command_file_bridge_agent_operation_trace_count"] == 1
        assert trace["remote_command_file_bridge_agent_request_count"] == 0
        assert trace["product_mode_no_lifecycle_request_abort"] is True
        assert trace["product_mode_no_lifecycle_request_abort_count"] == 1
        assert trace["product_mode_no_lifecycle_request_abort_round"] == 1
        assert trace.get("product_mode_no_tool_call_lifecycle_abort") is not True
        assert trace["followup_prompt_count"] == 0
        assert trace["stop_decision_count"] == 1
        assert plan["runner_prerequisites"][
            "remote_command_file_bridge_agent_operation_trace_status"
        ] == "agent_operation_trace_present_no_requests"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_registry(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-14T00:00:00+00:00\n"
        "---\n\n"
        "# SkillsBench Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Build a compact SkillsBench adapter skeleton.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-14T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-ledger",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ],
        },
    )
    return registry_path, runtime


def compact_skillsbench_run(
    *,
    task_id: str,
    mode: str,
    score: float,
    passed: bool,
    exception_type: str = "",
    round_reward_trace: dict[str, Any] | None = None,
    payload_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trial: dict[str, Any] = {
        "task_id": task_id,
        "trial_name": f"{task_id}_{mode}",
        "source": "skillsbench@1.1",
        "reward": {"reward": score},
        "trajectory_present": False,
        "verifier_reward_present": True,
        "artifact_manifest_present": True,
        "trial_result_present": True,
    }
    if exception_type:
        trial["exception_type"] = exception_type
    payload = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "job_name": f"skillsbench_1_1_{task_id}_{mode}",
        "mode": mode,
        "agent": {"name": "codex", "model": "gpt-5.5"},
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "value": score,
            "passed": passed,
        },
        "leaderboard_evidence": False,
        "submit_eligible": False,
        "trials": [trial],
    }
    if round_reward_trace is not None:
        payload["round_reward_trace"] = round_reward_trace
    if payload_overrides:
        payload.update(payload_overrides)
    compact = compact_benchmark_run(payload)
    assert compact is not None, payload
    return compact


def test_skillsbench_skeleton_builder() -> None:
    compact = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="loopx-goal-start-product-mode",
            task_id="citation-check",
        )
    )
    assert compact is not None
    assert compact["benchmark_id"] == "skillsbench@1.1", compact
    assert compact["mode"] == "skillsbench_loopx_goal_start_product_mode_treatment"
    assert compact["real_run"] is False, compact
    assert compact["submit_eligible"] is False, compact
    assert compact["leaderboard_evidence"] is False, compact
    assert compact["validation"]["all_passed"] is True, compact
    attempt_accounting = compact["attempt_accounting"]
    assert attempt_accounting["schema_version"] == "benchmark_attempt_accounting_v0"
    assert attempt_accounting["case_attempt_countable"] is False, compact
    assert attempt_accounting["solver_attempt_countable"] is False, compact
    assert attempt_accounting["verifier_attempt_countable"] is False, compact
    assert attempt_accounting["official_score_attempt_countable"] is False, compact
    assert "do_not_read_raw_task_prompt_solution_or_trajectory" in compact[
        "stop_conditions"
    ], compact
    assert compact["loopx_inside_case"] is True, compact
    assert compact["episode_policy"]["raw_trace_recorded"] is False, compact
    assert compact["native_goal_mode_invoked"] is False, compact
    assert compact["codex_acp_protocol_used"] is True, compact
    assert compact["blind_loop"] is False, compact
    assert compact["official_feedback_blinded"] is True, compact
    assert compact["reward_feedback_forwarded"] is False, compact
    assert compact["skillsbench_route_semantics"] == (
        "codex_agent_executes_guided_loopx_slash_start_then_authors_ranked_todos_and_selected_p0_lifecycle_no_reward_feedback"
    ), compact

    blind_baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="codex-acp-blind-loop-baseline",
            task_id="citation-check",
        )
    )
    assert blind_baseline is not None
    assert blind_baseline["mode"] == "skillsbench_codex_acp_blind_loop_baseline"
    assert blind_baseline["loopx_automation_loop"] is False, blind_baseline
    assert blind_baseline["blind_loop"] is True, blind_baseline
    assert blind_baseline["official_feedback_blinded"] is True, blind_baseline
    assert blind_baseline["reward_feedback_forwarded"] is False, blind_baseline

    cli_goal_baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="codex-cli-goal-baseline",
            task_id="citation-check",
        )
    )
    assert cli_goal_baseline is not None
    assert cli_goal_baseline["mode"] == "skillsbench_codex_cli_goal_baseline", (
        cli_goal_baseline
    )
    assert cli_goal_baseline["native_goal_mode_requested"] is True, cli_goal_baseline
    assert cli_goal_baseline["native_goal_mode_invoked"] is True, cli_goal_baseline
    assert cli_goal_baseline["native_goal_mode_confirmation_status"] == (
        "requires_cli_slash_goal_compact_proof"
    ), cli_goal_baseline
    assert cli_goal_baseline["codex_acp_protocol_used"] is False, cli_goal_baseline
    assert cli_goal_baseline["inner_codex_goal_mode"] is True, cli_goal_baseline
    assert cli_goal_baseline["skillsbench_route_semantics"] == (
        "host_codex_cli_tui_slash_goal_no_reward_feedback"
    ), cli_goal_baseline

    raw_product_baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="raw-codex-autonomous-max5",
            task_id="citation-check",
        )
    )
    assert raw_product_baseline is not None
    assert raw_product_baseline["mode"] == (
        "skillsbench_raw_codex_autonomous_max5_baseline"
    ), raw_product_baseline
    assert raw_product_baseline["product_mode"] is True, raw_product_baseline
    assert raw_product_baseline["loopx_automation_loop"] is False, (
        raw_product_baseline
    )
    assert raw_product_baseline["official_feedback_blinded"] is True, (
        raw_product_baseline
    )
    assert raw_product_baseline["reward_feedback_forwarded"] is False, (
        raw_product_baseline
    )

    product_treatment = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="loopx-product-mode",
            task_id="citation-check",
        )
    )
    assert product_treatment is not None
    assert product_treatment["mode"] == (
        "skillsbench_loopx_product_mode_treatment"
    ), product_treatment
    assert product_treatment["product_mode"] is True, product_treatment
    assert product_treatment["loopx_automation_loop"] is True, (
        product_treatment
    )
    assert product_treatment["loopx_inside_case"] is True, product_treatment
    assert product_treatment["case_semantics_changed_by_harness"] is True, (
        product_treatment
    )
    assert product_treatment["official_feedback_blinded"] is True, product_treatment
    assert product_treatment["reward_feedback_forwarded"] is False, product_treatment


def test_skillsbench_verifier_tail_disabled_at_zero() -> None:
    assert _tail("private verifier output", limit=0) == ""
    assert _tail("private verifier output", limit=-1) == ""
    assert _tail("abcdef", limit=3) == "def"
    args = parse_args(["--task-id", "sample-task", "--route", "loopx-goal-start-product-mode"])
    assert args.max_verifier_output_chars == 0, args
    default_args = parse_args(["--task-id", "sample-task"])
    assert default_args.route == "codex-cli-goal-baseline", default_args


def test_skillsbench_official_result_builder() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-result-builder-") as tmp:
        result_path = write_official_skillsbench_result(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["source_runner"] == "official_skillsbench_benchflow_result"
        assert compact["real_run"] is True
        assert compact["submit_eligible"] is False
        assert compact["leaderboard_evidence"] is False
        assert compact["official_task_score"]["value"] == 0.0
        assert compact["official_task_score"]["passed"] is False
        attempt_accounting = compact["attempt_accounting"]
        assert attempt_accounting["failure_class"] == "solver_failed", compact
        assert attempt_accounting["lifecycle_phase"] == "verifier_scored", compact
        assert attempt_accounting["case_attempt_countable"] is True, compact
        assert attempt_accounting["solver_attempt_countable"] is True, compact
        assert attempt_accounting["verifier_attempt_countable"] is True, compact
        assert attempt_accounting["official_score_attempt_countable"] is True, compact
        assert compact["score_failure_attribution"] == (
            "official_verifier_solution_failure"
        )
        assert "official_verifier_solution_failure" in compact[
            "failure_attribution_labels"
        ]
        review = build_benchmark_verifier_attribution_review(benchmark_runs=[compact])
        assert review["decision"]["baseline_claim_caveat_resolved"] is True, review
        assert review["routing"]["treatment_eligible"] is True, review
        assert review["run_reviews"][0]["attribution_class"] == (
            "model_or_solution_failure"
        ), review
        assert compact["trials"][0]["task_id"] == "sample-task"
        assert compact["read_boundary"]["compact_only"] is True
        assert compact["read_boundary"]["trajectory_read"] is False


def test_skillsbench_passed_bool_result_is_countable_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-passed-bool-") as tmp:
        result_path = write_official_skillsbench_passed_bool_result(
            Path(tmp),
            passed=False,
            task_id="travel-planning",
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-cli-goal-baseline",
            )
        )
        assert compact is not None
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 0.0, compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_passed_bool",
            "value": 0.0,
            "passed": False,
        }, compact
        assert compact["official_score_source"] == (
            "official_skillsbench_benchflow_result_rewards_passed_bool"
        ), compact
        assert compact["score_failure_attribution"] == (
            "official_verifier_solution_failure"
        ), compact
        assert "verifier_infrastructure_failure" not in compact[
            "failure_attribution_labels"
        ], compact
        attempt_accounting = compact["attempt_accounting"]
        assert attempt_accounting["official_score_attempt_countable"] is True, compact
        assert attempt_accounting["verifier_attempt_countable"] is True, compact
        assert attempt_accounting["solver_attempt_countable"] is True, compact


def test_skillsbench_verifier_uv_bootstrap_error_is_not_solution_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-uv-bootstrap-result-") as tmp:
        root = Path(tmp)
        run_dir = root / "official" / "2026-07-01__12-00-00" / "citation-check__abc123"
        result_path = run_dir / "result.json"
        write_json(
            result_path,
            {
                "task_name": "citation-check",
                "rollout_name": "citation-check__abc123",
                "rewards": {"reward": 0.0},
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 5,
                "n_prompts": 1,
                "error": None,
                "verifier_error": (
                    "downloading uv 0.9.7 x86_64-unknown-linux-gnu\n"
                    "failed to download https://releases.astral.sh/github/uv/"
                    "releases/download/0.9.7/uv-x86_64-unknown-linux-gnu.tar.gz\n"
                    "/verifier/test.sh: line 27: uvx: command not found"
                ),
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(run_dir / "timing.json", {"agent_execution": 5.0, "total": 65.0})

        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-app-server-goal-baseline",
            )
        )

        assert compact is not None
        assert compact["official_score_status"] == "missing", compact
        assert "official_score" not in compact, compact
        assert "value" not in compact["official_task_score"], compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_verifier_uv_bootstrap_failure"
        ), compact
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_verifier_uv_bootstrap_failure" in labels, compact
        assert "skillsbench_verifier_bootstrap_failure" in labels, compact
        assert "verifier_infrastructure_failure" in labels, compact
        assert "official_verifier_solution_failure" not in labels, compact
        assert "official_score_zero_case_failure" not in labels, compact
        assert "skillsbench_verifier_uv_bootstrap_zero_reward_ignored" in compact[
            "runner_warning_labels"
        ], compact
        accounting = compact["attempt_accounting"]
        assert accounting["failure_class"] == "verifier_failed", compact
        assert accounting["case_attempt_countable"] is True, compact
        assert accounting["solver_attempt_countable"] is True, compact
        assert accounting["verifier_attempt_countable"] is True, compact
        assert accounting["official_score_attempt_countable"] is False, compact


def test_skillsbench_result_reward_artifact_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-reward-recovery-") as tmp:
        result_path = write_official_skillsbench_reward_artifact_recovery_result(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["official_task_score"]["value"] == 1.0, compact
        assert compact["official_task_score"]["passed"] is True, compact
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score_source"] == (
            "official_skillsbench_rollout_verifier_reward_txt"
        ), compact
        assert compact["score_failure_attribution"] == "none", compact
        assert "verifier_infrastructure_failure" not in compact.get(
            "failure_attribution_labels", []
        ), compact
        assert "official_skillsbench:verifier/reward.txt" in compact[
            "evidence_files"
        ], compact
        assert compact["validation"]["validation_scope"] == (
            "official_benchflow_result_json_plus_rollout_reward_artifact"
        ), compact
        assert compact["progress"]["n_completed_trials"] == 1, compact
        assert compact["progress"]["n_errored_trials"] == 0, compact


def test_skillsbench_runner_error_zero_reward_is_case_score_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-zero-reward-") as tmp:
        result_path = write_official_skillsbench_runner_error_zero_reward_result(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_reward_txt",
            "passed": False,
            "value": 0.0,
        }, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_runner_error"
        ), compact
        assert compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), compact
        assert "skillsbench_runner_error" in compact["failure_attribution_labels"]
        assert "official_score_zero_case_failure" in compact[
            "failure_attribution_labels"
        ]
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-travel-planning-zero-score",
            dry_run=False,
        )
        assert update["entry"]["score_status"] == "failed", update
        assert update["entry"]["failure_class"] == (
            "official_score_zero_case_failure"
        ), update
        assert update["entry"]["failure_scope"] == "case_or_solution", update


def test_skillsbench_oracle_result_reward_artifact_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-oracle-reward-") as tmp:
        result_path = (
            write_official_skillsbench_oracle_reward_artifact_recovery_result(
                Path(tmp)
            )
        )
        full_run = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route="loopx-product-mode",
        )
        compact = compact_benchmark_run(full_run)
        assert compact is not None
        assert compact["agent"]["name"] == "oracle", compact
        assert compact["agent"]["model"] == "not_applicable_oracle_runner", compact
        assert compact["official_task_score"]["value"] == 1.0, compact
        assert compact["official_task_score"]["passed"] is True, compact
        assert compact["progress"]["n_completed_trials"] == 1, compact
        assert compact["progress"]["n_errored_trials"] == 0, compact
        assert compact["model_control"]["control_status"] == (
            "not_applicable_oracle_runner"
        ), compact
        assert compact["model_control"]["actual_model_verified"] is True, compact
        assert full_run["interaction_counters"]["codex_acp_protocol_used"] is False
        assert full_run["episode_policy"]["inner_case_actor"] == (
            "skillsbench_oracle_solution_runner"
        ), full_run
        assert full_run["mode_contract"]["codex_acp_protocol_used"] is False, full_run
        assert full_run["mode_contract"]["loopx_inside_case"] is False, full_run
        assert full_run["mode_contract"]["official_score_comparable_to_native_codex"] is False
        assert full_run["mode_contract"][
            "official_score_comparable_to_loopx_treatment"
        ] is False
        assert "verifier_infrastructure_failure" not in compact.get(
            "failure_attribution_labels", []
        ), compact


def test_skillsbench_app_mount_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-mount-failure-") as tmp:
        result_path = write_official_skillsbench_app_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["progress"]["n_completed_trials"] == 0, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        text = json.dumps(compact, sort_keys=True)
        assert "/Users/" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_app_skills_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-skills-failure-") as tmp:
        result_path = write_official_skillsbench_app_skills_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_app_skills_permission_failure_not_overridden_by_worker_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-skills-perm-") as tmp:
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": False,
            "native_goal_worker_connect_count": 0,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        result_path = write_official_skillsbench_app_skills_permission_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-app-server-goal-baseline",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_native_goal_worker_uncountable_baseline" not in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact


def test_skillsbench_docker_port_conflict_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-port-") as tmp:
        result_path = write_official_skillsbench_docker_port_conflict_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_port_conflict"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        text = json.dumps(compact, sort_keys=True)
        assert "port is already allocated" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_docker_apt_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-apt-") as tmp:
        result_path = write_official_skillsbench_docker_apt_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_apt_repository_failure"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert "apt_failure" in fingerprint["matched_patterns"], fingerprint
        assert fingerprint["failure_line_dependency_classes"] == [
            "system_package"
        ], fingerprint
        text = json.dumps(compact, sort_keys=True)
        assert "Hash Sum mismatch" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_docker_daemon_unavailable_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-daemon-") as tmp:
        result_path = write_official_skillsbench_docker_daemon_unavailable_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_daemon_unavailable"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert "docker_daemon_unavailable" in fingerprint["matched_patterns"], (
            fingerprint
        )
        plan = {
            "route": "raw-codex-autonomous-max5",
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "pending",
            },
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        assert reduced["compose_setup_diagnostic"][
            "docker_daemon_unavailable"
        ] is True, reduced
        assert reduced["compose_setup_diagnostic"][
            "unclassified_compose_failure"
        ] is False, reduced
        text = json.dumps(compact, sort_keys=True)
        assert "docker.sock" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_unclassified_compose_failure_fingerprint() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-compose-generic-") as tmp:
        result_path = write_official_skillsbench_unclassified_compose_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_setup_failure"
        ), compact
        assert "skillsbench_docker_compose_unclassified_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert fingerprint["schema_version"] == (
            "skillsbench_runner_failure_fingerprint_v0"
        ), fingerprint
        assert fingerprint["matched_patterns"] == [
            "docker_compose_command_failed"
        ], fingerprint
        assert fingerprint["has_host_paths"] is True, fingerprint
        assert fingerprint["raw_error_recorded"] is False, fingerprint
        plan = {
            "route": "raw-codex-autonomous-max5",
            "task_id": "paratransit-routing",
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_status": "ok",
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        diagnostic = reduced["compose_setup_diagnostic"]
        assert diagnostic["schema_version"] == (
            "skillsbench_compose_setup_diagnostic_v0"
        ), diagnostic
        assert diagnostic["status"] == (
            "compose_setup_blocked_before_agent_rounds"
        ), diagnostic
        assert diagnostic["agent_rounds_started"] is False, diagnostic
        assert diagnostic["case_attempt_budget_should_count"] is False, diagnostic
        assert diagnostic["official_score_missing"] is True, diagnostic
        assert diagnostic["raw_logs_read"] is False, diagnostic
        assert diagnostic["raw_task_text_read"] is False, diagnostic
        assert diagnostic["raw_trajectory_read"] is False, diagnostic
        text = json.dumps(compact, sort_keys=True)
        assert "Docker compose command failed" not in text, compact
        assert "/Users/example/private/job/root" not in text, compact


def test_skillsbench_app_server_pre_agent_setup_overrides_route_selected_gap() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-appserver-preagent-") as tmp:
        root = Path(tmp)
        run_dir = (
            root
            / "official"
            / "2026-07-01__09-50-00"
            / "fix-build-agentops__preagent"
        )
        result_path = run_dir / "result.json"
        write_json(
            result_path,
            {
                "task_name": "fix-build-agentops",
                "rollout_name": "fix-build-agentops__preagent",
                "rewards": None,
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 1,
                "error": "BenchFlow setup blocked before agent lifecycle",
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": None,
            },
        )
        write_json(run_dir / "timing.json", {"environment_setup": 1.0, "total": 1.0})
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "last_decision": "host_app_server_goal_worker_selected",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": False,
            "native_goal_worker_trace_dir_present": False,
            "native_goal_worker_public_trace_read": False,
            "native_goal_worker_trace_count": 0,
            "native_goal_worker_connect_count": 0,
        }
        compact = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route="codex-app-server-goal-baseline",
            controller_trace=controller_trace,
        )
        assert compact["score_failure_attribution"] == (
            "skillsbench_native_goal_worker_uncountable_worker_route_selected_not_connected"
        ), compact
        compact["compose_setup_diagnostic"] = {
            "schema_version": "skillsbench_compose_setup_diagnostic_v0",
            "status": "runner_setup_blocked_before_agent_rounds",
            "route": "codex-app-server-goal-baseline",
            "failure_class": compact["score_failure_attribution"],
            "agent_rounds_started": False,
            "official_score_missing": True,
            "case_attempt_budget_should_count": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }

        legacy_reduced = compact_benchmark_run(compact)
        assert legacy_reduced is not None
        assert legacy_reduced["score_failure_attribution"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        ), legacy_reduced
        assert "native_goal_worker_public_trace_missing" not in legacy_reduced[
            "validation"
        ]["failed_checks"], legacy_reduced
        assert "pre_agent_setup_materialization_blocked" in legacy_reduced[
            "validation"
        ]["failed_checks"], legacy_reduced

        apply_skillsbench_pre_agent_setup_diagnostic_attribution(compact)
        assert compact["score_failure_attribution"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        ), compact
        accounting = compact["attempt_accounting"]
        assert accounting["failure_label"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        ), accounting
        assert accounting["failure_class"] == "job_materialization_failed", accounting

        ledger_path = root / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-appserver-preagent-test",
            arm_id="baseline",
            dry_run=False,
        )
        entry = update["entry"]
        assert entry["arm_id"] == "codex_app_server_goal_baseline", entry
        assert entry["failure_class"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        ), entry
        assert entry["attempt_failure_label"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        ), entry


def test_skillsbench_volume_mount_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-volume-mount-") as tmp:
        result_path = write_official_skillsbench_volume_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_volume_mount_failure"
        ), compact
        attempt_accounting = compact["attempt_accounting"]
        assert attempt_accounting["failure_class"] == (
            "job_materialization_failed"
        ), compact
        assert attempt_accounting["case_attempt_countable"] is False, compact
        assert attempt_accounting["solver_attempt_countable"] is False, compact
        assert attempt_accounting["verifier_attempt_countable"] is False, compact
        assert attempt_accounting["official_score_attempt_countable"] is False, compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_docker_compose_unclassified_setup_failure" not in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert "volume_mount_failure" in fingerprint["matched_patterns"], fingerprint
        plan = {
            "route": "loopx-product-mode",
            "task_id": "suricata-custom-exfil",
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "pending",
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        diagnostic = reduced["compose_setup_diagnostic"]
        assert diagnostic["volume_mount_failure"] is True, diagnostic
        assert diagnostic["unclassified_compose_failure"] is False, diagnostic
        assert diagnostic["next_diagnostic_action"] == (
            "repair_task_volume_mount_setup_before_product_treatment"
        ), diagnostic
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=reduced,
            run_group_id="skillsbench-volume-mount-repair-test",
            dry_run=False,
        )
        ledger_diagnostic = update["entry"]["compose_setup_diagnostic"]
        assert ledger_diagnostic["volume_mount_failure"] is True, ledger_diagnostic
        assert ledger_diagnostic["unclassified_compose_failure"] is False, (
            ledger_diagnostic
        )
        text = json.dumps(compact, sort_keys=True)
        assert "bind source path" not in text, compact
        assert "/Users/example/private/job/root" not in text, compact


def test_skillsbench_codex_acp_libssl_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-libssl-") as tmp:
        result_path = write_official_skillsbench_codex_acp_libssl_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_runtime_libssl_missing"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_codex_acp_glibc_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-glibc-") as tmp:
        result_path = write_official_skillsbench_codex_acp_glibc_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_glibc_incompatible"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_codex_acp_launch_preflight_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-launch-") as tmp:
        result_path = write_official_skillsbench_codex_acp_launch_preflight_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-ada-bathroom-plan-repair-pair-test",
            dry_run=False,
        )
        assert update["case_decision"]["decision"] == (
            "baseline_codex_acp_runtime_preflight_required"
        ), update
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "ada-bathroom-plan-repair"
        ]
        run = case["runs"][0]
        repair = run["repair_profile"]
        assert repair["repair_class"] == "skillsbench_codex_acp_runtime_preflight"
        assert "codex_acp_runtime_launch_preflight" in repair["required_preflight"]


def test_skillsbench_codex_acp_internal_error_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-internal-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), compact
        assert "skillsbench_codex_acp_transport_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"] == {
            "exception_type": "skillsbench_codex_acp_jsonrpc_internal_error",
            "failure_class": "skillsbench_codex_acp_jsonrpc_internal_error",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_runner_failure_v0",
        }, compact
        assert compact["progress"]["n_completed_trials"] == 0, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        text = json.dumps(compact, sort_keys=True)
        assert "ACP error -32603" not in text, compact
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-llm-prefix-cache-replay-pair-test",
            dry_run=False,
        )
        assert update["entry"]["failure_class"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), update
        assert update["entry"]["repair_class"] == (
            "skillsbench_codex_acp_runtime_preflight"
        ), update
        assert update["case_decision"]["decision"] == (
            "baseline_codex_acp_runtime_preflight_required"
        ), update


def test_skillsbench_codex_acp_provider_zero_activity_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-zero-activity-") as tmp:
        result_path = write_official_skillsbench_codex_acp_provider_zero_activity(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_provider_zero_activity"
        ), compact
        assert "skillsbench_codex_acp_provider_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_acp_zero_tool_call_observed" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"] == {
            "exception_type": "skillsbench_codex_acp_provider_zero_activity",
            "failure_class": "skillsbench_codex_acp_provider_zero_activity",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_runner_failure_v0",
        }, compact


def test_skillsbench_no_tool_postprocess_preserves_provider_zero_activity() -> None:
    compact = {
        "official_score_status": "missing",
        "score_failure_attribution": "skillsbench_codex_acp_provider_zero_activity",
        "first_blocker": "skillsbench_codex_acp_provider_zero_activity",
        "failure_attribution_labels": [
            "skillsbench_codex_acp_provider_zero_activity",
            "skillsbench_codex_acp_provider_error",
        ],
        "interaction_counters": {
            "private_trajectory_event_count": 2,
            "private_trajectory_round_count": 1,
            "private_trajectory_tool_call_count": 0,
            "controller_action_decisions": 1,
        },
    }

    assert _apply_agent_message_only_no_tool_calls_attribution(compact) is True
    assert compact["score_failure_attribution"] == (
        "skillsbench_codex_acp_provider_zero_activity"
    ), compact
    assert compact["first_blocker"] == (
        "skillsbench_codex_acp_provider_zero_activity"
    ), compact
    assert "skillsbench_acp_agent_message_only_no_tool_calls" in compact[
        "failure_attribution_labels"
    ], compact
    assert "skillsbench_agent_behavior_gap" not in compact[
        "failure_attribution_labels"
    ], compact


def test_skillsbench_no_tool_postprocess_preserves_agent_bridge_activity() -> None:
    compact = {
        "official_score_status": "missing",
        "score_failure_attribution": "verifier_infrastructure_failure",
        "failure_attribution_labels": [
            "skillsbench_runner_error",
            "verifier_infrastructure_failure",
        ],
        "interaction_counters": {
            "private_trajectory_event_count": 3,
            "private_trajectory_round_count": 1,
            "private_trajectory_tool_call_count": 0,
            "controller_action_decisions": 1,
            "remote_command_file_bridge_agent_request_count": 28,
            "remote_command_file_bridge_agent_loopx_state_write_count": 14,
            "remote_command_file_bridge_agent_task_facing_operation_count": 12,
            "remote_command_file_bridge_agent_task_facing_success_count": 12,
        },
    }

    assert _apply_agent_message_only_no_tool_calls_attribution(compact) is False
    assert compact["score_failure_attribution"] == (
        "verifier_infrastructure_failure"
    ), compact
    assert "skillsbench_acp_agent_message_only_no_tool_calls" not in compact[
        "failure_attribution_labels"
    ], compact
    assert "skillsbench_agent_behavior_gap" not in compact[
        "failure_attribution_labels"
    ], compact


def test_skillsbench_codex_acp_post_success_trace_recovers_score() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-trace-score-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "official_feedback_blinded_count": 2,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 38,
                },
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 30,
                },
                {
                    "agent_round": 3,
                    "reward_present": False,
                    "passed": False,
                },
            ],
            "official_success_observed": True,
            "official_success_observation_count": 2,
            "first_success_round": 1,
            "official_feedback_forwarded": False,
            "product_mode": True,
            "max_rounds_budget": 5,
            "last_decision": (
                "stop_after_product_mode_official_success_observed_without_feedback"
            ),
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 1.0, compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_controller_trace",
            "passed": True,
            "value": 1.0,
        }, compact
        assert compact["official_score_source"] == (
            "loopx_controller_trace_best_round_reward_post_success_acp_closeout"
        ), compact
        assert compact["score_failure_attribution"] == "none", compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), compact
        assert "skillsbench_codex_acp_transport_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["validation"]["official_case_success"] is True, compact
        assert compact["validation"]["official_verifier_status"] == "completed", compact
        assert compact["validation"]["validation_scope"] == (
            "official_benchflow_result_json_plus_loopx_controller_trace"
        ), compact
        round_trace = compact["round_reward_trace"]
        assert round_trace["official_score_recovered_from_controller_trace"] is True
        assert round_trace["official_score_recovered_round"] == 1
        assert round_trace["official_score_policy"] == (
            "best_round_for_post_success_acp_closeout_recovery"
        )
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-acp-post-success-score-recovery",
            dry_run=False,
        )
        assert update["entry"]["score_status"] == "passed", update
        assert update["entry"]["failure_scope"] == "passed", update
        assert update["entry"]["failure_class"] == "none", update
        assert update["entry"]["official_score"] == 1.0, update


def test_skillsbench_codex_acp_post_success_finalization_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-post-success-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
            )
        )
        assert compact is not None
        compact["runner_prerequisites"] = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "codex_acp_runtime_launch_preflight": True,
            "codex_acp_runtime_launch_preflight_status": "passed",
        }
        compact["round_reward_trace"] = {
            "schema_version": "benchmark_round_reward_trace_v0",
            "source": "loopx_controller_trace",
            "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
            "records": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                }
            ],
            "first_success_round": 1,
            "success_observed": True,
            "max_rounds_budget": 5,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
        }
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-post-success-acp-finalization-test",
            dry_run=False,
        )
        entry = update["entry"]
        assert entry["repair_class"] == (
            "skillsbench_codex_acp_post_success_finalization"
        ), update
        assert entry["round_success_observed"] is True, update
        assert entry["first_success_round"] == 1, update
        assert entry["codex_acp_runtime_preflight_passed"] is True, update
        assert entry["score_status"] == "missing", update
        assert entry["failure_scope"] == "score_missing", update
        repair = entry["repair_profile"]
        assert "round_reward_trace.success_observed" in repair["required_preflight"]
        ledger = load_benchmark_run_ledger(ledger_path)
        run = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "llm-prefix-cache-replay"
        ]["runs"][0]
        assert run["repair_class"] == (
            "skillsbench_codex_acp_post_success_finalization"
        ), run


def test_skillsbench_docker_task_staging_adds_app_skills_mount() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "citation-check"
        dockerfile = task / "environment" / "Dockerfile"
        dockerignore = task / "environment" / ".dockerignore"
        skills = task / "environment" / "skills" / "citation"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: citation\n---\n", encoding="utf-8")
        original_text = "FROM ubuntu:24.04\n\nWORKDIR /root\n"
        dockerfile.write_text(original_text, encoding="utf-8")
        dockerignore.write_text("*\n", encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="citation-check-setup-probe",
            sandbox="docker",
        )

        assert metadata["staged"] is True, metadata
        assert metadata["app_skills_mount_patch_applied"] is True, metadata
        assert metadata["original_task_mutated"] is False, metadata
        assert staged_path != task, staged_path
        assert dockerfile.read_text(encoding="utf-8") == original_text
        assert dockerignore.read_text(encoding="utf-8") == "*\n"
        staged_dockerfile = staged_path / "environment" / "Dockerfile"
        staged_text = staged_dockerfile.read_text(encoding="utf-8")
        assert DOCKER_APP_SKILLS_MOUNT_BEGIN in staged_text, staged_text
        assert (
            f"COPY {DOCKER_APP_SKILLS_MOUNT_KEEP_FILE} /app/skills/.loopx_keep"
            in staged_text
        ), staged_text
        assert "RUN mkdir -p /app /app/skills" not in staged_text, staged_text
        assert (
            staged_path / "environment" / DOCKER_APP_SKILLS_MOUNT_KEEP_FILE
        ).is_file()
        staged_dockerignore = (
            staged_path / "environment" / ".dockerignore"
        ).read_text(encoding="utf-8")
        assert f"!{DOCKER_APP_SKILLS_MOUNT_KEEP_FILE}" in staged_dockerignore


def test_skillsbench_no_skill_route_removes_staged_task_skills() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-skill-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "software-dependency-audit"
        dockerfile = task / "environment" / "Dockerfile"
        skills = task / "environment" / "skills" / "audit"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: audit\n---\n", encoding="utf-8")
        original_text = "FROM ubuntu:24.04\n\nWORKDIR /root\n"
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="software-dependency-audit-baseline",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["include_task_skills"] is False, metadata
        assert metadata["task_skills_removed"] is True, metadata
        assert metadata["app_skills_mount_patch_applied"] is True, metadata
        assert (task / "environment" / "skills").exists()
        assert not (staged_path / "environment" / "skills").exists()
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APP_SKILLS_MOUNT_BEGIN in staged_text, staged_text
        assert (
            f"COPY {DOCKER_APP_SKILLS_MOUNT_KEEP_FILE} /app/skills/.loopx_keep"
            in staged_text
        ), staged_text
        assert "RUN mkdir -p /app /app/skills" not in staged_text, staged_text
        assert (
            staged_path / "environment" / DOCKER_APP_SKILLS_MOUNT_KEEP_FILE
        ).is_file()


def test_skillsbench_docker_task_staging_adds_apt_retry_patch() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "setup-fuzzing-py"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM ubuntu:20.04\n\n"
            "RUN apt-get update && apt-get install -y curl\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="setup-fuzzing-py-baseline",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["apt_setup_risk_detected"] is True, metadata
        assert metadata["apt_retry_patch_required"] is True, metadata
        assert metadata["apt_risk_preflight_blocked"] is False, metadata
        assert metadata["apt_retry_patch_applied"] is True, metadata
        assert (
            metadata["dockerfile_ubuntu_apt_mirror_patch_required"] is True
        ), metadata
        assert (
            metadata["dockerfile_ubuntu_apt_mirror_patch_applied"] is True
        ), metadata
        assert metadata["dockerfile_ubuntu_apt_mirror_host"] == (
            dockerfile_runtime.DEFAULT_UBUNTU_APT_MIRROR_HOST
        ), metadata
        assert (
            metadata["dockerfile_ubuntu_apt_mirror_raw_url_recorded"] is False
        ), metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        assert metadata["original_task_mutated"] is False, metadata
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APT_RETRY_BEGIN in staged_text, staged_text
        assert dockerfile_runtime.UBUNTU_APT_MIRROR_BEGIN in staged_text, staged_text
        assert dockerfile_runtime.DEFAULT_UBUNTU_APT_MIRROR_BASE in staged_text
        assert "archive.ubuntu.com/ubuntu" in staged_text
        assert "security.ubuntu.com/ubuntu" in staged_text
        assert DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in staged_text, staged_text
        assert 'Acquire::Retries "5";' in staged_text, staged_text


def test_skillsbench_docker_task_staging_apt_retry_is_nonroot_safe() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-nonroot-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "fix-build-google-auto"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM example.invalid/nonroot-base:latest\n"
            "RUN apt-get update && apt-get install -y curl\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="fix-build-google-auto-baseline",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["apt_retry_patch_required"] is True, metadata
        assert metadata["apt_retry_patch_applied"] is True, metadata
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APT_RETRY_BEGIN in staged_text, staged_text
        assert "if mkdir -p /etc/apt/apt.conf.d 2>/dev/null" in staged_text
        assert "[ -w /etc/apt/apt.conf.d ]" in staged_text
        assert "apt config directory is not writable" in staged_text
        assert dockerfile.read_text(encoding="utf-8") == original_text


def test_skillsbench_docker_task_staging_rewrites_gcr_oss_fuzz_base() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-gcr-mirror-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "setup-fuzzing-py"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM gcr.io/oss-fuzz-base/base-builder-python:latest\n"
            "RUN true\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        mirror_prefix = "mirror.example.invalid/cache"

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="setup-fuzzing-py-goal",
            sandbox="docker",
            include_task_skills=False,
            docker_gcr_mirror_prefix=mirror_prefix,
        )

        assert metadata["dockerfile_gcr_mirror_configured"] is True, metadata
        assert metadata["dockerfile_gcr_mirror_patch_required"] is True, metadata
        assert metadata["dockerfile_gcr_mirror_patch_applied"] is True, metadata
        assert metadata["dockerfile_gcr_mirror_raw_prefix_recorded"] is False, metadata
        assert dockerfile.read_text(encoding="utf-8") == original_text
        assert mirror_prefix not in json.dumps(metadata, sort_keys=True), metadata
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_GCR_MIRROR_BEGIN in staged_text, staged_text
        assert (
            "FROM mirror.example.invalid/cache/gcr.io/oss-fuzz-base/"
            "base-builder-python:latest"
        ) in staged_text, staged_text


def test_skillsbench_docker_task_staging_hardens_elan_toolchain_install() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-elan-retry-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "lean4-proof"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM ubuntu:24.04\n"
            "RUN elan toolchain install $(cat /app/workspace/lean-toolchain) && \\\n"
            "    elan default $(cat /app/workspace/lean-toolchain)\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="lean4-proof-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_elan_toolchain_retry_patch_required"] is True, (
            metadata
        )
        assert metadata["dockerfile_elan_toolchain_retry_patch_applied"] is True, (
            metadata
        )
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN in staged_text, staged_text
        assert "for loopx_attempt in 1 2 3 4 5" in staged_text, staged_text
        assert "elan toolchain install \"${loopx_lean_toolchain}\"" in staged_text
        assert "elan default \"${loopx_lean_toolchain}\"" in staged_text


def test_skillsbench_docker_task_staging_rewrites_wget_gpg_key_download() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-wget-gpg-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "software-dependency-audit"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM python:3.12-slim\n"
            "RUN wget -qO - https://example.invalid/public.key | "
            "gpg --dearmor -o /usr/share/keyrings/example.gpg\n"
            "RUN curl -fsSL --retry 5 --retry-delay 2 --connect-timeout 30 "
            "https://aquasecurity.github.io/trivy-repo/deb/public.key | "
            "gpg --dearmor -o /usr/share/keyrings/trivy.gpg\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="software-dependency-audit-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_wget_gpg_key_retry_patch_required"] is True, (
            metadata
        )
        assert metadata["dockerfile_wget_gpg_key_retry_patch_applied"] is True, (
            metadata
        )
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert "wget -qO -" not in staged_text, staged_text
        curl_retry_all_errors_arg = skillsbench_loop._dockerfile_curl_retry_all_errors_arg()
        assert (
            f"curl -fsSL --retry 8 {curl_retry_all_errors_arg} --retry-delay 3 "
            "--connect-timeout 60 --max-time 300 "
            "https://example.invalid/public.key | gpg --dearmor"
        ) in staged_text, staged_text
        assert (
            f"curl -fsSL --retry 8 {curl_retry_all_errors_arg} --retry-delay 3 "
            "--connect-timeout 60 --max-time 300 "
            "https://aquasecurity.github.io/trivy-repo/deb/public.key | "
            "gpg --dearmor"
        ) in staged_text, staged_text


def test_skillsbench_docker_task_staging_hardens_build_downloads() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-build-download-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "fix-druid-loophole-cve"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM ubuntu:24.04\n"
            "RUN wget "
            "https://archive.apache.org/dist/druid/0.20.0/"
            "apache-druid-0.20.0-bin.tar.gz && \\\n"
            "    curl -fL https://github.com/coursier/coursier/releases/download/"
            "v2.1.25-M23/cs-x86_64-pc-linux.gz -o cs.gz && \\\n"
            "    git clone https://github.com/example/project.git && \\\n"
            "    mvn dependency:resolve -DskipTests\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="fix-druid-loophole-cve-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_network_download_retry_patch_required"] is True, (
            metadata
        )
        assert metadata["dockerfile_network_download_retry_patch_applied"] is True, (
            metadata
        )
        assert (
            metadata["dockerfile_apache_archive_mirror_patch_required"] is True
        ), metadata
        assert metadata["dockerfile_apache_archive_mirror_patch_applied"] is True, (
            metadata
        )
        assert (
            metadata["dockerfile_apache_archive_mirror_host"]
            == DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
        ), metadata
        assert metadata["dockerfile_apache_archive_raw_url_recorded"] is False, (
            metadata
        )
        assert metadata["dockerfile_maven_mirror_patch_required"] is True, metadata
        assert metadata["dockerfile_maven_mirror_patch_applied"] is True, metadata
        assert (
            metadata["dockerfile_maven_mirror_host"]
            == DEFAULT_DOCKER_MAVEN_MIRROR_HOST
        ), metadata
        assert metadata["dockerfile_maven_mirror_raw_url_recorded"] is False, (
            metadata
        )
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN in staged_text, staged_text
        assert "GIT_HTTP_LOW_SPEED_LIMIT=1000" in staged_text, staged_text
        assert "maven.wagon.http.retryHandler.count=5" in staged_text, staged_text
        assert "https://archive.apache.org/dist/druid/" not in staged_text, staged_text
        assert (
            "https://mirrors.huaweicloud.com/apache/druid/0.20.0/"
            "apache-druid-0.20.0-bin.tar.gz"
        ) in staged_text, staged_text
        assert "# BEGIN LOOPX_SKILLSBENCH_MAVEN_MIRROR" in staged_text, staged_text
        assert DEFAULT_DOCKER_MAVEN_MIRROR_URL in staged_text, staged_text
        assert (
            f"mvn --settings {DEFAULT_DOCKER_MAVEN_SETTINGS_PATH} "
            "dependency:resolve"
        ) in staged_text, staged_text
        assert "/etc/maven/settings.xml" not in staged_text, staged_text
        assert (
            "wget --tries=5 --timeout=120 --read-timeout=120 "
            "--retry-connrefused "
            "https://mirrors.huaweicloud.com/apache/druid/0.20.0/"
            "apache-druid-0.20.0-bin.tar.gz"
        ) in staged_text, staged_text
        assert (
            f"curl -fL --retry 5 {skillsbench_loop._dockerfile_curl_retry_all_errors_arg()} --retry-delay 2 "
            "--connect-timeout 60 --max-time 600 "
            "https://github.com/coursier/coursier/releases/download/"
            "v2.1.25-M23/cs-x86_64-pc-linux.gz"
        ) in staged_text, staged_text


def test_skillsbench_docker_task_staging_patches_dockerfile_uv_bootstrap() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-dockerfile-uv-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "pddl-tpp-planning"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM python:3.12-slim\n"
            "RUN python3 -m pip install --upgrade pip\n"
            "RUN curl -LsSf https://astral.sh/uv/0.9.22/install.sh | sh && \\\n"
            "    install -m 0755 ${HOME}/.local/bin/uv /usr/local/bin/uv && \\\n"
            "    install -m 0755 ${HOME}/.local/bin/uvx /usr/local/bin/uvx\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="pddl-tpp-planning-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_uv_bootstrap_risk_detected"] is True, metadata
        assert (
            metadata["dockerfile_uv_bootstrap_mirror_patch_required"] is True
        ), metadata
        assert (
            metadata["dockerfile_uv_bootstrap_mirror_patch_applied"] is True
        ), metadata
        assert (
            metadata["dockerfile_uv_bootstrap_pip_fallback_patch_applied"] is True
        ), metadata
        assert metadata["dockerfile_uv_bootstrap_version"] == "0.9.22", metadata
        assert metadata["dockerfile_uv_bootstrap_mirror_host"] == (
            DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
        ), metadata
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN in staged_text, staged_text
        assert "ARG LOOPX_SKILLSBENCH_UV_VERSION=0.9.22" in staged_text, staged_text
        assert "python3 -m pip install ${loopx_pip_break_system_packages}" in (
            staged_text
        ), staged_text
        assert "uv==${LOOPX_SKILLSBENCH_UV_VERSION}" in staged_text, staged_text
        assert "INSTALLER_DOWNLOAD_URL" in staged_text, staged_text
        assert skillsbench_loop._dockerfile_curl_retry_all_errors_arg() in staged_text, staged_text
        assert (
            "curl -LsSf https://astral.sh/uv/0.9.22/install.sh | sh &&"
            not in staged_text
        ), staged_text


def test_skillsbench_docker_task_staging_adds_pip_bootstrap_patch() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-pip-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "adaptive-cruise-control"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM ubuntu:24.04 AS builder\n"
            "RUN pip3 install numpy==1.26.4 pandas==2.2.2\n"
            "FROM python:3.12-slim\n"
            "RUN python3 -m pip install pyyaml==6.0.1\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="adaptive-cruise-control-goalstart",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["dockerfile_pip_install_risk_detected"] is True, metadata
        assert metadata["dockerfile_pip_bootstrap_patch_required"] is True, metadata
        assert metadata["dockerfile_pip_bootstrap_patch_applied"] is True, metadata
        assert metadata["dockerfile_pip_index_host"] == DEFAULT_DOCKER_PIP_INDEX_HOST, (
            metadata
        )
        assert metadata["original_task_mutated"] is False, metadata
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert staged_text.count(DOCKER_PIP_BOOTSTRAP_BEGIN) == 2, staged_text
        assert "PIP_INDEX_URL=${LOOPX_SKILLSBENCH_PIP_INDEX_URL}" in staged_text, (
            staged_text
        )
        assert "PIP_EXTRA_INDEX_URL=${LOOPX_SKILLSBENCH_PIP_EXTRA_INDEX_URL}" in (
            staged_text
        ), staged_text
        assert f"ARG LOOPX_SKILLSBENCH_PIP_INDEX_URL=https://{DEFAULT_DOCKER_PIP_INDEX_HOST}/simple" in (
            staged_text
        ), staged_text
        assert "PIP_RETRIES=10" in staged_text, staged_text
        assert staged_text.index(DOCKER_PIP_BOOTSTRAP_BEGIN) < staged_text.index(
            "pip3 install"
        ), staged_text


def test_skillsbench_docker_pip_bootstrap_skips_python_heredoc_imports() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-pip-heredoc-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "latex-formula-extraction"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM ubuntu:24.04\n"
            "RUN python3 - <<'PY'\n"
            "from huggingface_hub import snapshot_download\n"
            "snapshot_download(repo_id='example/model')\n"
            "PY\n"
            "RUN pip3 install marker-pdf==1.3.3\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="latex-formula-extraction-goalstart",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_pip_bootstrap_patch_applied"] is True, metadata
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert staged_text.count(DOCKER_PIP_BOOTSTRAP_BEGIN) == 1, staged_text
        heredoc_body = staged_text[
            staged_text.index("RUN python3 - <<'PY'") : staged_text.index(
                "PY\nRUN pip3 install"
            )
        ]
        assert DOCKER_PIP_BOOTSTRAP_BEGIN not in heredoc_body, staged_text
        assert staged_text.index(DOCKER_PIP_BOOTSTRAP_BEGIN) < staged_text.index(
            "RUN python3 - <<'PY'"
        ), staged_text


def test_skillsbench_runtime_tools_patch_has_own_apt_retry_defaults() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runtime-tools-apt-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "runtime-tools"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text("FROM ubuntu:20.04\n", encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="runtime-tools-apt",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["apt_retry_patch_required"] is False, metadata
        assert metadata["apt_retry_patch_applied"] is False, metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APT_RETRY_BEGIN not in staged_text, staged_text
        assert DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in staged_text, staged_text
        assert 'Acquire::Retries "5";' in staged_text, staged_text
        assert staged_text.index('Acquire::Retries "5";') < staged_text.index(
            "apt-get update -qq"
        ), staged_text
        assert "curl-minimal" in staged_text, staged_text
        assert "microdnf install -y ca-certificates tar xz" in staged_text, staged_text
        assert "dnf -y install ca-certificates tar xz" in staged_text, staged_text
        assert "dnf -y install ca-certificates curl tar xz" not in staged_text, (
            staged_text
        )


def test_skillsbench_docker_task_staging_patches_verifier_uv_bootstrap_mirror() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-uv-verifier-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "citation-check"
        dockerfile = task / "environment" / "Dockerfile"
        verifier = task / "tests" / "test.sh"
        dockerfile.parent.mkdir(parents=True)
        verifier.parent.mkdir(parents=True)
        dockerfile.write_text("FROM python:3.12-slim\n", encoding="utf-8")
        original_verifier = (
            "#!/bin/sh\n"
            "apt-get update\n"
            "curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\n"
            "source \"$HOME/.local/bin/env\"\n"
            "uvx --with pytest==8.4.1 pytest /tests/test_outputs.py\n"
        )
        verifier.write_text(original_verifier, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="citation-check-goalstart",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["verifier_bootstrap_risk_detected"] is True, metadata
        assert metadata["verifier_uv_bootstrap_risk_detected"] is True, metadata
        assert metadata["verifier_uv_bootstrap_mirror_patch_required"] is True, (
            metadata
        )
        assert metadata["verifier_uv_bootstrap_mirror_patch_applied"] is True, (
            metadata
        )
        assert metadata[
            "verifier_uv_bootstrap_pip_fallback_patch_applied"
        ] is True, metadata
        assert metadata["verifier_uv_env_source_guard_patch_applied"] is True, (
            metadata
        )
        assert metadata["verifier_uv_bootstrap_version"] == "0.9.7", metadata
        assert metadata["verifier_script_executable_required"] is True, metadata
        assert metadata["verifier_script_executable_ready"] is True, metadata
        assert metadata["verifier_uv_bootstrap_mirror_host"] == (
            DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
        ), metadata
        assert verifier.read_text(encoding="utf-8") == original_verifier
        assert not os.access(verifier, os.X_OK), verifier
        assert os.access(staged_path / "tests" / "test.sh", os.X_OK), staged_path
        staged_verifier = (staged_path / "tests" / "test.sh").read_text(
            encoding="utf-8"
        )
        assert VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN in staged_verifier, staged_verifier
        assert "INSTALLER_DOWNLOAD_URL" in staged_verifier, staged_verifier
        assert "python3 -m pip install" in staged_verifier, staged_verifier
        assert "--break-system-packages" in staged_verifier, staged_verifier
        assert "uv==${loopx_uv_version}" in staged_verifier, staged_verifier
        assert "loopx_uv_installer_timeout_sec" in staged_verifier, staged_verifier
        assert "timeout \"${loopx_uv_installer_timeout_sec}\" sh -c" in (
            staged_verifier
        )
        assert 'if [ -f "$HOME/.local/bin/env" ]; then' in staged_verifier, (
            staged_verifier
        )
        assert "source \"$HOME/.local/bin/env\"" not in staged_verifier, (
            staged_verifier
        )
        assert "releases.astral.sh/github/uv/releases/download" in staged_verifier, (
            staged_verifier
        )
        assert "uv-${loopx_uv_target}.tar.gz" not in staged_verifier, staged_verifier
        assert "if ! command -v uvx >/dev/null 2>&1; then" in staged_verifier, (
            staged_verifier
        )
        assert staged_verifier.index("INSTALLER_DOWNLOAD_URL") < staged_verifier.index(
            "astral.sh/uv/0.9.7/install.sh"
        ), staged_verifier


def test_skillsbench_docker_task_staging_forwards_proxy_to_verifier_bootstrap() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-verifier-proxy-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "citation-check"
        dockerfile = task / "environment" / "Dockerfile"
        verifier = task / "verifier" / "test.sh"
        dockerfile.parent.mkdir(parents=True)
        verifier.parent.mkdir(parents=True)
        original_dockerfile = (
            "FROM python:3.12-slim AS builder\n"
            "RUN wget https://example.invalid/model.tar.gz\n"
            "FROM python:3.12-slim\n"
            "RUN python3 - <<'PY'\n"
            "from urllib.request import urlopen\n"
            "urlopen('https://example.invalid/data.json')\n"
            "PY\n"
        )
        dockerfile.write_text(original_dockerfile, encoding="utf-8")
        original_verifier = (
            "#!/bin/sh\n"
            "set -x\n"
            "curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\n"
            "uvx --with pytest==8.4.1 pytest /tests/test_outputs.py\n"
        )
        verifier.write_text(original_verifier, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        proxy_url = "http://benchmark-proxy.example.invalid:18080"

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="citation-check-goalstart",
            sandbox="docker",
            include_task_skills=False,
            benchmark_egress_proxy_env={
                "LOOPX_SKILLSBENCH_EGRESS_PROXY": proxy_url,
                "HTTPS_PROXY": proxy_url,
                "HTTP_PROXY": proxy_url,
                "ALL_PROXY": proxy_url,
                "https_proxy": proxy_url,
                "http_proxy": proxy_url,
                "all_proxy": proxy_url,
                "NO_PROXY": "localhost,127.0.0.1,::1,hifis-storage.desy.de",
                "no_proxy": "localhost,127.0.0.1,::1,hifis-storage.desy.de",
            },
        )

        assert metadata["staged"] is True, metadata
        assert metadata["benchmark_egress_proxy_verifier_env_patch_required"] is True, (
            metadata
        )
        assert metadata["benchmark_egress_proxy_verifier_env_patch_applied"] is True, (
            metadata
        )
        assert metadata["benchmark_egress_proxy_verifier_env_key_count"] >= 8, metadata
        assert metadata[
            "benchmark_egress_proxy_verifier_env_raw_proxy_recorded"
        ] is False, metadata
        assert metadata[
            "benchmark_egress_proxy_dockerfile_env_patch_required"
        ] is True, metadata
        assert metadata[
            "benchmark_egress_proxy_dockerfile_env_patch_applied"
        ] is True, metadata
        assert metadata[
            "benchmark_egress_proxy_dockerfile_java_opts_patch_applied"
        ] is True, metadata
        assert metadata[
            "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded"
        ] is False, metadata
        assert proxy_url not in json.dumps(metadata, sort_keys=True), metadata
        assert dockerfile.read_text(encoding="utf-8") == original_dockerfile
        assert verifier.read_text(encoding="utf-8") == original_verifier

        staged_verifier = (staged_path / "verifier" / "test.sh").read_text(
            encoding="utf-8"
        )
        assert VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN in staged_verifier, (
            staged_verifier
        )
        assert staged_verifier.index(
            VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN
        ) < staged_verifier.index("set -x"), staged_verifier
        assert f"export HTTPS_PROXY={proxy_url}" in staged_verifier, staged_verifier
        assert f"export HTTP_PROXY={proxy_url}" in staged_verifier, staged_verifier
        assert "export NO_PROXY=localhost,127.0.0.1,::1,hifis-storage.desy.de" in (
            staged_verifier
        ), staged_verifier
        assert "case \"$-\" in *x*) loopx_restore_xtrace=1; set +x;; esac" in (
            staged_verifier
        )
        staged_dockerfile = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert staged_dockerfile.count(DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN) == 2, (
            staged_dockerfile
        )
        assert f"ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY={proxy_url}" in (
            staged_dockerfile
        ), staged_dockerfile
        assert (
            "ARG LOOPX_SKILLSBENCH_BENCHMARK_NO_PROXY="
            "localhost,127.0.0.1,::1,hifis-storage.desy.de"
        ) in staged_dockerfile, staged_dockerfile
        assert "ENV HTTPS_PROXY=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY}" in (
            staged_dockerfile
        ), staged_dockerfile
        assert (
            "ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_HOST="
            "benchmark-proxy.example.invalid"
        ) in staged_dockerfile, staged_dockerfile
        assert (
            "ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_PORT=18080"
            in staged_dockerfile
        ), staged_dockerfile
        assert "JAVA_TOOL_OPTIONS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS}" in (
            staged_dockerfile
        ), staged_dockerfile
        assert "COURSIER_OPTS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS}" in (
            staged_dockerfile
        ), staged_dockerfile
        heredoc_start = staged_dockerfile.index("RUN python3 - <<'PY'")
        heredoc_end = staged_dockerfile.index("\nPY\n", heredoc_start)
        heredoc_body = staged_dockerfile[heredoc_start:heredoc_end]
        assert DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN not in heredoc_body, (
            staged_dockerfile
        )


def test_skillsbench_docker_task_staging_keeps_empty_skills_build_context() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-empty-skills-context-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "radar-vital-signs"
        dockerfile = task / "environment" / "Dockerfile"
        skills_dir = task / "environment" / "skills"
        dockerfile.parent.mkdir(parents=True)
        skills_dir.mkdir(parents=True)
        dockerfile.write_text(
            "FROM python:3.11-slim\nCOPY skills /root/.codex/skills\n",
            encoding="utf-8",
        )
        (skills_dir / "private_task_skill.md").write_text(
            "task-local skill content should not be copied when disabled\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="radar-vital-signs-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        staged_skills_dir = staged_path / "environment" / "skills"
        assert metadata["task_skills_removed"] is True, metadata
        assert metadata["empty_skills_build_context_required"] is True, metadata
        assert metadata["empty_skills_build_context_created"] is True, metadata
        assert staged_skills_dir.is_dir(), metadata
        assert (staged_skills_dir / ".loopx_keep").exists(), metadata
        assert not (staged_skills_dir / "private_task_skill.md").exists(), metadata
        assert not skills_dir.joinpath(".loopx_keep").exists()


def test_skillsbench_apt_risk_preflight_blocks_full_run_without_benchflow() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-preflight-") as tmp:
        root = Path(tmp)
        task = root / "skillsbench" / "tasks" / "setup-fuzzing-py"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM ubuntu:20.04\n\nRUN apt-get update && apt-get install -y curl\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        jobs = root / "jobs"
        ledger = root / "benchmark-run-ledger.json"
        args = [
            "--task-id",
            "setup-fuzzing-py",
            "--route",
            "codex-acp-blind-loop-baseline",
            "--skillsbench-root",
            str(root / "skillsbench"),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "setup-fuzzing-py-apt-risk-preflight",
            "--run-group-id",
            "setup-fuzzing-py-apt-risk-preflight",
            "--ledger-path",
            str(ledger),
            "--fail-fast-on-apt-risk",
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        assert plan["task_setup_preflight"]["apt_setup_risk_detected"] is True, plan
        assert plan["task_setup_preflight"]["raw_task_text_read"] is False, plan

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "setup-fuzzing-py-apt-risk-preflight"
            / "setup-fuzzing-py__codex_acp_blind_loop"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["task_id"] == "setup-fuzzing-py", compact
        assert compact["case_id"] == "setup-fuzzing-py", compact
        assert compact["route"] == "codex-acp-blind-loop-baseline", compact
        assert compact["run_group_id"] == "setup-fuzzing-py-apt-risk-preflight", (
            compact
        )
        assert compact["job_name"] == "setup-fuzzing-py-apt-risk-preflight", compact
        assert compact["rollout_name"] == "setup-fuzzing-py__codex_acp_blind_loop", (
            compact
        )
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_apt_setup_risk_preflight_blocked"
        ), compact
        assert compact["task_staging"]["apt_setup_risk_detected"] is True, compact
        assert compact["task_staging"]["apt_retry_patch_required"] is True, compact
        assert compact["task_staging"]["apt_risk_preflight_blocked"] is True, compact
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"][
            "setup-fuzzing-py"
        ]
        assert case["latest_decision"]["decision"] == (
            "baseline_setup_preflight_selection_required"
        ), case
        entry = next(
            run
            for run in case["runs"]
            if run.get("run_group_id") == "setup-fuzzing-py-apt-risk-preflight"
            and run.get("job_name") == "setup-fuzzing-py-apt-risk-preflight"
        )
        assert entry["repair_class"] == "skillsbench_setup_preflight_selection", (
            entry
        )
        assert entry["task_staging"]["apt_risk_preflight_blocked"] is True, (
            entry
        )


def test_skillsbench_verifier_bootstrap_preflight_blocks_full_run_without_benchflow() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-verifier-preflight-") as tmp:
        root = Path(tmp)
        task = root / "skillsbench" / "tasks" / "organize-messy-files"
        dockerfile = task / "environment" / "Dockerfile"
        verifier = task / "verifier" / "test.sh"
        dockerfile.parent.mkdir(parents=True)
        verifier.parent.mkdir(parents=True)
        dockerfile.write_text("FROM python:3.12-slim\n", encoding="utf-8")
        verifier.write_text(
            "#!/bin/sh\n"
            "curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\n"
            "uv add polars==1.37.1\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        jobs = root / "jobs"
        ledger = root / "benchmark-run-ledger.json"
        args = [
            "--task-id",
            "organize-messy-files",
            "--route",
            "codex-acp-blind-loop-baseline",
            "--skillsbench-root",
            str(root / "skillsbench"),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "organize-messy-files-verifier-bootstrap-preflight",
            "--run-group-id",
            "organize-messy-files-verifier-bootstrap-preflight",
            "--ledger-path",
            str(ledger),
            "--fail-fast-on-verifier-bootstrap-risk",
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "verifier_bootstrap_risk_detected", preflight
        assert preflight["verifier_bootstrap_risk_detected"] is True, preflight
        assert preflight["verifier_uv_bootstrap_risk_detected"] is True, preflight
        assert preflight["verifier_uv_bootstrap_version"] == "0.9.7", preflight
        assert preflight["verifier_external_download_risk_detected"] is True, preflight
        assert preflight["verifier_package_install_risk_detected"] is True, preflight
        assert preflight["raw_task_text_read"] is False, preflight
        assert plan["task_staging"][
            "verifier_uv_bootstrap_mirror_patch_required"
        ] is True, plan
        assert plan["task_staging"][
            "verifier_uv_bootstrap_mirror_patch_applied"
        ] is False, plan

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "organize-messy-files-verifier-bootstrap-preflight"
            / "organize-messy-files__codex_acp_blind_loop"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["score_failure_attribution"] == (
            "skillsbench_verifier_bootstrap_risk_preflight_blocked"
        ), compact
        assert compact["task_setup_preflight"][
            "verifier_bootstrap_risk_detected"
        ] is True, compact
        assert compact["task_staging"][
            "verifier_bootstrap_risk_preflight_blocked"
        ] is True, compact
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"][
            "organize-messy-files"
        ]
        assert case["latest_decision"]["decision"] == (
            "baseline_verifier_bootstrap_preflight_selection_required"
        ), case
        entry = next(
            run
            for run in case["runs"]
            if run.get("run_group_id")
            == "organize-messy-files-verifier-bootstrap-preflight"
            and run.get("job_name")
            == "organize-messy-files-verifier-bootstrap-preflight"
        )
        assert entry["repair_class"] == (
            "skillsbench_verifier_bootstrap_preflight_selection"
        ), entry


def test_skillsbench_docker_task_staging_caps_local_cpu_request() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cpu-cap-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "debug-trl-grpo"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_dockerfile = "FROM python:3.11-slim\n"
        original_task_toml = (
            'version = "1.1"\n\n'
            "[environment]\n"
            "cpus = 4  # four project shards in the official task\n"
            "memory_mb = 2048\n"
        )
        dockerfile.write_text(original_dockerfile, encoding="utf-8")
        (task / "task.toml").write_text(original_task_toml, encoding="utf-8")

        previous = os.environ.get(DOCKER_HOST_CPU_ENV)
        os.environ[DOCKER_HOST_CPU_ENV] = "2"
        try:
            staged_path, metadata = stage_task_for_sandbox(
                task_path=task,
                jobs_dir=root / "jobs",
                job_name="debug-trl-grpo-baseline",
                sandbox="docker",
                include_task_skills=False,
            )
        finally:
            if previous is None:
                os.environ.pop(DOCKER_HOST_CPU_ENV, None)
            else:
                os.environ[DOCKER_HOST_CPU_ENV] = previous

        assert metadata["staged"] is True, metadata
        cap = metadata["resource_cap_patch"]
        assert cap["applied"] is True, metadata
        assert cap["requested_cpus"] == 4.0, metadata
        assert cap["effective_cpus"] == 2.0, metadata
        assert cap["original_task_mutated"] is False, metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        assert "cpus = 4  # four project shards" in (task / "task.toml").read_text(
            encoding="utf-8"
        )
        assert "cpus = 2  # four project shards" in (staged_path / "task.toml").read_text(
            encoding="utf-8"
        )
        assert dockerfile.read_text(encoding="utf-8") == original_dockerfile


def test_skillsbench_runner_plan_supports_baseline_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-plan-") as tmp:
        root = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "software-dependency-audit",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        plan = payload["launch_plan"]
        assert plan["schema_version"] == "skillsbench_runner_launch_plan_v0", plan
        assert plan["route"] == "codex-acp-blind-loop-baseline", plan
        assert plan["include_task_skills"] is False, plan
        observable = plan["observable_handle_registration"]
        assert observable["schema_version"] == "benchmark_launch_observable_handle_v0", (
            observable
        )
        assert observable["benchmark_id"] == "skillsbench-1.1", observable
        assert observable["launch_mode"] == "skillsbench_runner_launch_plan", observable
        handle = observable["observable_handle"]
        assert handle["kind"] == "job_basename", observable
        assert handle["state"] == "not_started", observable
        assert "/" not in handle["job_basename"], observable
        assert handle["raw_handle_payload_recorded"] is False, observable
        assert handle["private_handle_values_recorded"] is False, observable
        assert observable["allowed_poll_command"]["command_label"] == (
            "skillsbench_runner_status_snapshot"
        ), observable
        assert observable["allowed_poll_command"]["argv_recorded"] is False, observable
        assert observable["read_boundary"]["compact_only"] is True, observable
        assert observable["boundary"]["raw_task_text_recorded"] is False, observable
        assert observable["boundary"]["local_paths_recorded"] is False, observable
        assert plan["outer_timeout_sec"] == 7200, plan
        assert plan["sandbox_setup_timeout_sec"] == 7200, plan
        runner_prerequisites = plan["runner_prerequisites"]
        expected_runner_prerequisites = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "agent_execution_mode": "container_codex_acp",
            "codex_acp_runtime_container_bootstrap": True,
            "codex_acp_runtime_dependency_preflight": True,
            "codex_acp_runtime_launch_preflight": False,
            "codex_acp_runtime_launch_preflight_stage": (
                "after_agent_install_before_acp_connect"
            ),
            "codex_acp_runtime_launch_preflight_status": "pending",
            "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            "container_codex_acp_install_skipped": False,
            "benchflow_agent_install_skipped_by_runtime_layer": False,
            "host_local_acp_launch": False,
            "host_local_acp_launch_status": "not_requested",
            "remote_command_file_bridge_materialized": False,
        }
        assert_prerequisites_include(
            runner_prerequisites,
            expected_runner_prerequisites,
        )
        assert (
            runner_prerequisites["preinstalled_benchflow_agent_runtime_required"]
            is False
        ), plan
        assert (
            runner_prerequisites["benchflow_agent_runtime_layer_status"]
            == "not_requested"
        ), plan
        assert "curl" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "curl-minimal" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "microdnf install -y ca-certificates tar xz" in (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        )
        assert "dnf -y install ca-certificates curl tar xz" not in (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        )
        assert "xz-utils" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD.index("command -v curl")
            < CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD.index("apt-get")
        )
        assert "/tmp/loopx-apt-cache" not in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "/var/cache/apt/archives" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "libssl.so.3" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "microdnf install -y openssl-libs" in (
            CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        )
        assert "glibc >=2.34" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/tmp/loopx-apt-cache" not in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/var/cache/apt/archives" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/opt/benchflow/bin/codex-acp" in CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
        assert '"$agent_bin" --version' in CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
        assert plan["rollout_name"].endswith("__codex_acp_blind_loop"), plan
        assert plan["public_boundary"]["leaderboard_upload"] is False, plan


def test_skillsbench_codex_acp_model_control_warning() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-model-control-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root)
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                runner_warning_labels=["codex_acp_set_model_unsupported"],
            )
        )
        assert compact is not None
        assert compact["runner_warning_labels"] == [
            "codex_acp_set_model_unsupported"
        ], compact
        model_control = compact["model_control"]
        assert model_control["requested_model"] == "gpt-5.5", compact
        assert model_control["reported_model"] == "gpt-5.5", compact
        assert model_control["actual_model_verified"] is False, compact
        assert model_control["control_status"] == (
            "requested_model_not_enforced_by_acp"
        ), compact

        ledger_path = root / "benchmark-run-ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-model-control-warning",
            notes="compact runner model-control warning fixture",
            dry_run=False,
        )
        entry = update["entry"]
        assert entry["model_control_status"] == (
            "requested_model_not_enforced_by_acp"
        ), entry
        assert entry["actual_model_verified"] is False, entry
        assert entry["model_warning_labels"] == [
            "codex_acp_set_model_unsupported"
        ], entry


def test_skillsbench_runner_prerequisites_are_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-prereq-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=1.0)
        benchmark_run = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route="codex-acp-blind-loop-baseline",
        )
        benchmark_run["runner_prerequisites"] = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "codex_acp_runtime_container_bootstrap": True,
            "codex_acp_runtime_dependency_preflight": True,
            "codex_acp_runtime_launch_preflight": True,
            "codex_acp_runtime_launch_preflight_stage": (
                "preinstalled_benchflow_layer_after_sandbox_setup_before_acp_connect"
            ),
            "codex_acp_runtime_launch_preflight_status": "passed",
            "codex_acp_runtime_launch_preflight_rc": 0,
            "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            "container_codex_acp_install_skipped": True,
            "benchflow_agent_install_skipped_by_runtime_layer": True,
            "preinstalled_benchflow_agent_runtime_required": True,
            "benchflow_agent_runtime_layer_ready": True,
            "benchflow_agent_runtime_layer_status": "ready",
            "benchflow_agent_runtime_layer_mount_target": "/opt/benchflow",
            "benchflow_agent_runtime_mount_injected": True,
            "benchflow_agent_runtime_mount_read_only": True,
            "benchflow_agent_runtime_mount_source_recorded": False,
            "codex_acp_runtime_dependency_setup_skipped": True,
            "benchflow_intermediate_soft_verify_policy": "final-only",
            "benchflow_intermediate_soft_verify_final_only": True,
            "benchflow_intermediate_soft_verify_call_count": 0,
            "benchflow_intermediate_soft_verify_skipped_count": 3,
            "benchflow_intermediate_soft_verify_raw_output_recorded": False,
            "benchflow_verifier_prep_timeout_override_enabled": True,
            "benchflow_verifier_prep_timeout_sec": 120,
            "benchflow_verifier_prep_timeout_override_count": 2,
            "benchflow_verify_prep_timeout_override_count": 1,
            "benchflow_soft_verify_prep_timeout_override_count": 1,
            "benchflow_verifier_prep_timeout_raw_command_recorded": False,
            "benchflow_final_verifier_timeout_enabled": True,
            "benchflow_final_verifier_timeout_sec": 600,
            "benchflow_final_verifier_timeout_override_count": 1,
            "benchflow_final_verifier_timeout_triggered": True,
            "benchflow_final_verifier_timeout_raw_command_recorded": False,
            "benchflow_final_verifier_timeout_raw_output_recorded": False,
            "remote_command_file_bridge_agent_todo_closeout_count": 4,
            "remote_command_file_bridge_agent_refresh_state_count": 3,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 2,
            "benchflow_setup_stall_cleanup_requested": True,
            "benchflow_setup_stall_cleanup_raw_logs_read": False,
            "benchflow_setup_stall_cleanup_status": "terminated",
            "benchflow_setup_stall_cleanup_match_count": 2,
            "benchflow_setup_stall_cleanup_term_sent_count": 2,
            "benchflow_setup_stall_cleanup_kill_sent_count": 0,
            "benchflow_setup_stall_cleanup_alive_after_count": 0,
            "private_unlisted_detail": "must not compact",
        }
        compact = compact_benchmark_run(benchmark_run)
        assert compact is not None
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_stage": (
                    "preinstalled_benchflow_layer_after_sandbox_setup_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "passed",
                "codex_acp_runtime_launch_preflight_rc": 0,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                "container_codex_acp_install_skipped": True,
                "benchflow_agent_install_skipped_by_runtime_layer": True,
                "preinstalled_benchflow_agent_runtime_required": True,
                "benchflow_agent_runtime_layer_ready": True,
                "benchflow_agent_runtime_layer_status": "ready",
                "benchflow_agent_runtime_layer_mount_target": "/opt/benchflow",
                "benchflow_agent_runtime_mount_injected": True,
                "benchflow_agent_runtime_mount_read_only": True,
                "benchflow_agent_runtime_mount_source_recorded": False,
                "codex_acp_runtime_dependency_setup_skipped": True,
                "benchflow_intermediate_soft_verify_policy": "final-only",
                "benchflow_intermediate_soft_verify_final_only": True,
                "benchflow_intermediate_soft_verify_call_count": 0,
                "benchflow_intermediate_soft_verify_skipped_count": 3,
                "benchflow_intermediate_soft_verify_raw_output_recorded": False,
                "benchflow_verifier_prep_timeout_override_enabled": True,
                "benchflow_verifier_prep_timeout_sec": 120,
                "benchflow_verifier_prep_timeout_override_count": 2,
                "benchflow_verify_prep_timeout_override_count": 1,
                "benchflow_soft_verify_prep_timeout_override_count": 1,
                "benchflow_verifier_prep_timeout_raw_command_recorded": False,
                "benchflow_final_verifier_timeout_enabled": True,
                "benchflow_final_verifier_timeout_sec": 600,
                "benchflow_final_verifier_timeout_override_count": 1,
                "benchflow_final_verifier_timeout_triggered": True,
                "benchflow_final_verifier_timeout_raw_command_recorded": False,
                "benchflow_final_verifier_timeout_raw_output_recorded": False,
                "remote_command_file_bridge_agent_todo_closeout_count": 4,
                "remote_command_file_bridge_agent_refresh_state_count": 3,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 2,
                "benchflow_setup_stall_cleanup_requested": True,
                "benchflow_setup_stall_cleanup_raw_logs_read": False,
                "benchflow_setup_stall_cleanup_status": "terminated",
                "benchflow_setup_stall_cleanup_match_count": 2,
                "benchflow_setup_stall_cleanup_term_sent_count": 2,
                "benchflow_setup_stall_cleanup_kill_sent_count": 0,
                "benchflow_setup_stall_cleanup_alive_after_count": 0,
            },
        )
        assert "private_unlisted_detail" not in json.dumps(compact), compact


def test_skillsbench_case_event_timeline_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-case-timeline-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(
            root,
            reward=1.0,
            task_id="organize-messy-files",
        )
        args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "skillsbench-case-timeline-fixture",
                "--rollout-name",
                "organize-messy-files__loopx_product_mode",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "remote_command_file_bridge_consumed_by_solver": True,
                "remote_command_file_bridge_solver_operation_count": 2,
                "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
                "remote_command_file_bridge_agent_request_count": 3,
                "remote_command_file_bridge_agent_task_facing_operation_count": 2,
            "remote_command_file_bridge_agent_task_facing_success_count": 2,
                "remote_command_file_bridge_agent_todo_closeout_count": 1,
                "remote_command_file_bridge_agent_refresh_state_count": 1,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
            }
        )
        write_json(
            Path(plan["controller_trace_json"]),
            {
                "schema_version": "skillsbench_loopx_controller_trace_v0",
                "route": "loopx-product-mode",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "product_mode": True,
                "heartbeat_count": 2,
                "controller_action_decisions": 2,
                "initial_prompt_count": 1,
                "followup_prompt_count": 1,
                "stop_decision_count": 1,
                "official_success_observed": True,
                "official_success_observation_count": 1,
                "first_success_round": 2,
                "max_rounds_budget": 8,
                "case_goal_state_init_required": True,
                "case_goal_state_initialized_before_agent": True,
                "case_goal_state_init_status": "passed",
                "product_mode_lifecycle_checkpoint_required": True,
                "remote_command_file_bridge_consumed_by_solver": True,
                "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
                "remote_command_file_bridge_driver_lifecycle_execution_style": (
                    "orchestrated_agentloop_loopx_cli"
                ),
                "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
                "remote_command_file_bridge_driver_lifecycle_request_count": 4,
                "remote_command_file_bridge_driver_lifecycle_success_count": 4,
                "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
                "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": True,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_recorded"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 3,
                "remote_command_file_bridge_agent_task_facing_operation_count": 2,
            "remote_command_file_bridge_agent_task_facing_success_count": 2,
                "remote_command_file_bridge_agent_todo_closeout_count": 1,
                "remote_command_file_bridge_agent_refresh_state_count": 1,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
                "round_rewards": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                        "tool_calls": 4,
                    },
                    {
                        "agent_round": 2,
                        "reward_present": True,
                        "reward": 1.0,
                        "passed": True,
                        "tool_calls": 6,
                    },
                ],
                "last_decision": "stop_after_official_success_observed",
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
                "acp_trajectory_summary": {
                    "schema_version": "skillsbench_acp_trajectory_summary_v0",
                    "private_trajectory_present": True,
                    "raw_text_copied_to_public": False,
                    "event_count": 9,
                    "round_count": 2,
                    "user_message_count": 2,
                    "agent_message_count": 2,
                    "tool_call_count": 6,
                },
            },
        )

        compact = reduce_result(args, result_path, plan)
        timeline = compact["case_event_timeline"]
        assert timeline["schema_version"] == "skillsbench_case_event_timeline_v0"
        assert timeline["source"] == "compact_public_signals"
        assert timeline["raw_material_recorded"] is False
        events = {event["event"]: event for event in timeline["events"]}
        assert events["case_goal_state_init"]["status"] == "passed", compact
        assert events["orchestrated_loopx_lifecycle"]["checkpoint_count"] == 1
        assert events["remote_command_bridge_consumption"]["status"] == "consumed"
        assert events["task_facing_activity"]["status"] == "task_activity_observed"
        assert events["controller_decision_loop"]["status"] == (
            "official_success_observed"
        )
        assert events["official_score_closeout"]["status"] == "passed"
        assert events["agent_bridge_closeout"]["status"] == "satisfied"
        gate = compact["post_run_debug_gate"]
        assert gate["schema_version"] == "skillsbench_post_run_debug_gate_v0"
        assert gate["packet_complete"] is True, gate
        assert gate["case_closeout_complete"] is True, gate
        assert gate["next_case_gate"] == "open", gate
        assert gate["normal_progress_allowed"] is True, gate
        assert gate["scorer_verifier"]["official_score_passed"] is True, gate
        assert gate["loopx_lifecycle"]["todo_closeout_count"] == 1, gate
        assert gate["boundary"]["task_text_read"] is False, gate

        compact_again = compact_benchmark_run(compact)
        assert compact_again is not None
        assert compact_again["case_event_timeline"]["event_count"] == (
            timeline["event_count"]
        )
        assert compact_again["post_run_debug_gate"]["packet_complete"] is True
        compact_text = json.dumps(compact_again, sort_keys=True)
        assert "raw_task_text" not in compact_text
        assert "raw_trajectory" not in compact_text
        non_skillsbench = dict(compact_again)
        non_skillsbench["benchmark_id"] = "terminal-bench@2.0"
        non_skillsbench.pop("post_run_debug_gate", None)
        terminal_compact = compact_benchmark_run(non_skillsbench)
        assert terminal_compact is not None
        assert "case_event_timeline" in terminal_compact
        assert "post_run_debug_gate" not in terminal_compact


def test_skillsbench_runner_plan_supports_product_mode_routes() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-product-plan-") as tmp:
        root = Path(tmp)
        for route, suffix in (
            ("raw-codex-autonomous-max5", "raw_codex_autonomous_max5"),
            ("loopx-product-mode", "loopx_product_mode"),
        ):
            args = parse_args(
                [
                    "--task-id",
                    "software-dependency-audit",
                    "--route",
                    route,
                    "--jobs-dir",
                    str(root / "jobs"),
                ]
            )
            plan = build_plan(args)
            assert plan["route"] == route, plan
            assert plan["max_rounds"] == DEFAULT_MAX_ROUNDS, plan
            assert plan["rollout_name"] == (
                f"software-dependency-audit__{suffix}"
            ), plan


def test_loopx_product_mode_full_run_requires_canonical_driver() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--task-id",
            "software-dependency-audit",
            "--route",
            "loopx-product-mode",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2, result
    payload = json.loads(result.stderr)
    assert payload["error_type"] == "SkillsBenchProductModeCanonicalDriverRequired", (
        payload
    )
    assert payload["canonical_product_mode_lifecycle_driver_required"] is True, payload
    assert "--host-local-acp-launch" in payload["next_action"], payload
    assert payload["raw_trajectory_recorded"] is False, payload


def test_loopx_case_init_failure_blocker_is_public_safe() -> None:
    assert (
        _loopx_case_init_failure_blocker(
            "loopx_case_init_phase:ensure_cli\n"
            "LoopX local source install requested but python is missing"
        )
        == "loopx_case_python_missing"
    )
    assert (
        _loopx_case_init_failure_blocker(
            "loopx_case_init_phase:ensure_cli\n"
            "/usr/bin/env: 'bash': No such file or directory"
        )
        == "loopx_case_bash_missing"
    )
    assert (
        _loopx_case_init_failure_blocker("ModuleNotFoundError: No module named loopx")
        == "loopx_case_source_import_failed"
    )


def test_loopx_case_state_seed_runs_after_host_local_sandbox_install() -> None:
    source = (REPO_ROOT / "scripts" / "skillsbench_automation_loop.py").read_text(
        encoding="utf-8"
    )
    assert 'host_local_acp_install_stage"] = "seed_loopx_case_state"' in source
    assert '"loopx_source_upload_fallback"' in source
    assert "env.is_file(source_cli)" in source
    assert "await upload_dir(staged_source" in source
    assert "host_local_acp_after_sandbox_install" in source
    assert "host_local_acp_rollout_planes_available" in source
    assert "benchflow_rollout_module._snapshot_build_config" in source
    assert "benchflow_rollout_module.deploy_skills" in source
    assert (
        "if _is_case_loopx_route(args.route) and not args.host_local_acp_launch:"
        in source
    )


def test_loopx_source_mount_contract_uses_real_cli_source_not_local_installer() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-source-contract-") as tmp:
        source_dir = Path(tmp)
        (source_dir / "loopx").mkdir()
        (source_dir / "loopx" / "cli.py").write_text("# source fixture\n")
        args = parse_args(
            [
                "--route",
                "loopx-product-mode",
                "--loopx-source-dir",
                str(source_dir),
            ]
        )
        contract = _loopx_source_mount_contract(args)
        assert contract["requested"] is True
        assert contract["ready"] is True
        assert contract["status"] == "ready"


def test_host_local_product_mode_uses_source_upload_not_docker_bind_mount() -> None:
    args = parse_args(
        [
            "--route",
            "loopx-product-mode",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--loopx-source-dir",
            str(REPO_ROOT),
        ]
    )
    assert _loopx_source_mount_contract(args)["ready"] is True
    assert _loopx_source_mounts(args) == []
    assert _loopx_case_source_path_for_container(args) == "/app/.loopx-source"


def test_host_local_product_mode_auto_bridge_keeps_lifecycle_checkpoint_args() -> None:
    args = parse_args(
        [
            "--route",
            "loopx-product-mode",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--task-id",
            "3d-scan-calc",
            "--agent-idle-timeout",
            "1800",
        ]
    )
    command = _host_local_acp_launch_command(args, build_plan(args))
    assert "--loopx-workflow-lifecycle-checkpoint" in command
    assert "--loopx-case-goal-id" in command
    assert "--loopx-case-cli-path" in command
    assert "--remote-command-file-bridge-command" not in command
    assert command[command.index("--timeout-sec") + 1] == str(
        DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
        + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
    )
    assert command[command.index("--bridge-idle-timeout-sec") + 1] == str(
        DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
    )


def test_host_local_acp_connect_contract_matches_benchflow_runtime() -> None:
    source = (REPO_ROOT / "scripts" / "skillsbench_automation_loop.py").read_text(
        encoding="utf-8"
    )
    assert "def _benchflow_connect_acp_return_arity(target: Any) -> int:" in source
    assert "_benchflow_connect_acp_return_arity(" in source
    assert "return_arity = connect_as_return_arity or _benchflow_connect_acp_return_arity(" in source
    assert "if return_arity >= 4:" in source
    assert "from benchflow.agents.protocol import ACPSessionAdapter" in source
    assert ") -> tuple[Any, ...]:" in source
    assert "session_adapter = ACPSessionAdapter(client)" in source
    assert "return client, session, agent_name" in source
    assert "return client, session, session_adapter, agent_name" in source
    assert 'host_local_acp_connect_return_arity"] = return_arity' in source
    assert 'if "mcp_servers" in inspect.signature(client.session_new).parameters:' in source
    assert "client.session_new(cwd=agent_cwd, mcp_servers=mcp_servers)" not in source


def test_loopx_source_upload_subset_is_public_safe_and_minimal() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-source-subset-") as tmp:
        source_dir = Path(tmp) / "checkout"
        target_dir = Path(tmp) / "upload"
        (source_dir / "loopx").mkdir(parents=True)
        (source_dir / "loopx" / "cli.py").write_text("# source fixture\n")
        (source_dir / "scripts").mkdir()
        (source_dir / "scripts" / "install-local.sh").write_text("# old installer\n")
        target_dir.mkdir()
        file_count = _copy_loopx_source_subset(source_dir, target_dir)
        assert file_count == 1
        assert (target_dir / "loopx" / "cli.py").exists()
        assert not (target_dir / "scripts" / "install-local.sh").exists()


def test_remote_bridge_auto_wiring_pending_is_not_final_failure_attribution() -> None:
    prereqs = {
        "remote_command_file_bridge_agent_operation_trace_required": True,
        "remote_command_file_bridge_agent_operation_trace_satisfied": False,
        "remote_command_file_bridge_agent_operation_trace_status": (
            "relay_generated_wrapper_pending_prompt"
        ),
        "remote_command_file_bridge_consumption_status": (
            "sandbox_bridge_auto_wiring_pending"
        ),
        "remote_command_file_bridge_agent_operation_trace_count": 0,
        "remote_command_file_bridge_agent_request_count": 0,
    }
    assert _runner_prerequisite_failure_attribution(prereqs) is None


def test_skillsbench_task_staging_metadata_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-staging-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        args = parse_args(
            [
                "--task-id",
                "setup-fuzzing-py",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "setup-fuzzing-py-task-staging-fixture",
            ]
        )
        plan = build_plan(args)
        plan["task_staging"] = {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": True,
            "staged_task_path": "/private/path/must/not/compact",
            "include_task_skills": False,
            "apt_setup_risk_detected": True,
            "apt_retry_patch_required": True,
            "app_skills_mount_patch_applied": False,
            "apt_retry_patch_applied": True,
            "apt_risk_preflight_blocked": False,
            "codex_acp_runtime_tools_patch_applied": True,
            "verifier_uv_bootstrap_risk_detected": True,
            "verifier_uv_bootstrap_mirror_patch_required": True,
            "verifier_uv_bootstrap_mirror_patch_applied": True,
            "verifier_script_executable_required": True,
            "verifier_script_executable_ready": True,
            "verifier_uv_bootstrap_version": "0.9.7",
            "verifier_uv_bootstrap_mirror_host": (
                DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
            ),
            "dockerfile_apache_archive_mirror_patch_required": True,
            "dockerfile_apache_archive_mirror_patch_applied": True,
            "dockerfile_apache_archive_mirror_host": (
                DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
            ),
            "dockerfile_apache_archive_raw_url_recorded": False,
            "dockerfile_maven_mirror_patch_required": True,
            "dockerfile_maven_mirror_patch_applied": True,
            "dockerfile_maven_mirror_host": DEFAULT_DOCKER_MAVEN_MIRROR_HOST,
            "dockerfile_maven_mirror_raw_url_recorded": False,
            "task_skills_removed": False,
            "original_task_mutated": False,
            "resource_cap_patch": {
                "schema_version": "skillsbench_local_docker_resource_cap_v0",
                "applied": False,
                "host_cpus": 2.0,
                "requested_cpus": 1.0,
                "effective_cpus": 1.0,
                "private_detail": "must not compact",
            },
        }

        compact = reduce_result(args, result_path, plan)

        assert compact["task_staging"] == {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": True,
            "include_task_skills": False,
            "apt_setup_risk_detected": True,
            "apt_retry_patch_required": True,
            "app_skills_mount_patch_applied": False,
            "apt_retry_patch_applied": True,
            "apt_risk_preflight_blocked": False,
            "codex_acp_runtime_tools_patch_applied": True,
            "verifier_uv_bootstrap_risk_detected": True,
            "verifier_uv_bootstrap_mirror_patch_required": True,
            "verifier_uv_bootstrap_mirror_patch_applied": True,
            "verifier_script_executable_required": True,
            "verifier_script_executable_ready": True,
            "verifier_uv_bootstrap_version": "0.9.7",
            "verifier_uv_bootstrap_mirror_host": (
                DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
            ),
            "dockerfile_apache_archive_mirror_patch_required": True,
            "dockerfile_apache_archive_mirror_patch_applied": True,
            "dockerfile_apache_archive_mirror_host": (
                DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
            ),
            "dockerfile_apache_archive_raw_url_recorded": False,
            "dockerfile_maven_mirror_patch_required": True,
            "dockerfile_maven_mirror_patch_applied": True,
            "dockerfile_maven_mirror_host": DEFAULT_DOCKER_MAVEN_MIRROR_HOST,
            "dockerfile_maven_mirror_raw_url_recorded": False,
            "task_skills_removed": False,
            "original_task_mutated": False,
            "resource_cap_patch": {
                "schema_version": "skillsbench_local_docker_resource_cap_v0",
                "applied": False,
                "host_cpus": 2.0,
                "requested_cpus": 1.0,
                "effective_cpus": 1.0,
            },
        }, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "staged_task_path" not in compact_text, compact
        assert "/private/path" not in compact_text, compact
        assert "private_detail" not in compact_text, compact
        update = update_benchmark_run_ledger(
            ledger_path=root / "ledger.json",
            benchmark_run=compact,
            run_group_id="setup-fuzzing-py-task-staging-fixture",
            dry_run=False,
        )
        entry_staging = update["entry"]["task_staging"]
        assert entry_staging["apt_retry_patch_applied"] is True, update
        assert entry_staging["apt_setup_risk_detected"] is True, update
        assert entry_staging["codex_acp_runtime_tools_patch_applied"] is True, update
        assert entry_staging["verifier_uv_bootstrap_mirror_patch_applied"] is True, (
            update
        )
        assert (
            entry_staging["dockerfile_apache_archive_mirror_patch_applied"] is True
        ), update
        assert entry_staging["dockerfile_maven_mirror_patch_applied"] is True, update
        assert "staged_task_path" not in json.dumps(update, sort_keys=True), update


def test_skillsbench_reduce_only_recovers_prepared_task_staging_metadata() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-staging-recover-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        args = parse_args(
            [
                "--task-id",
                "setup-fuzzing-py",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "setup-fuzzing-py-task-staging-recover-fixture",
            ]
        )
        plan = build_plan(args)
        prepared = (
            root
            / "jobs"
            / "setup-fuzzing-py-task-staging-recover-fixture"
            / "prepared-tasks"
            / "setup-fuzzing-py"
        )
        dockerfile = prepared / "environment" / "Dockerfile"
        verifier = prepared / "verifier" / "test.sh"
        dockerfile.parent.mkdir(parents=True)
        verifier.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM ubuntu:20.04\n"
            f"{DOCKER_APT_RETRY_BEGIN}\n"
            "RUN true\n"
            "# END LOOPX_SKILLSBENCH_APT_RETRY\n"
            f"{DOCKER_MAVEN_MIRROR_BEGIN}\n"
            "RUN mkdir -p /opt/loopx-maven\n"
            f"{DOCKER_MAVEN_MIRROR_END}\n"
            "RUN wget https://mirrors.huaweicloud.com/apache/druid/0.20.0/"
            "apache-druid-0.20.0-bin.tar.gz\n",
            encoding="utf-8",
        )
        verifier.write_text(
            "#!/bin/sh\n"
            f"{VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN}\n"
            "export INSTALLER_DOWNLOAD_URL="
            "https://releases.astral.sh/github/uv/releases/download/0.9.7\n"
            "# END LOOPX_SKILLSBENCH_VERIFIER_UV_BOOTSTRAP_MIRROR\n"
            "curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\n",
            encoding="utf-8",
        )

        compact = reduce_result(args, result_path, plan)

        assert compact["task_staging"]["staged"] is True, compact
        assert compact["task_staging"]["apt_retry_patch_applied"] is True, compact
        assert compact["task_staging"][
            "codex_acp_runtime_tools_patch_applied"
        ] is False, compact
        assert compact["task_staging"][
            "verifier_uv_bootstrap_mirror_patch_applied"
        ] is True, compact
        assert compact["task_staging"][
            "verifier_uv_bootstrap_version"
        ] == "0.9.7", compact
        assert compact["task_staging"][
            "dockerfile_apache_archive_mirror_patch_applied"
        ] is True, compact
        assert compact["task_staging"]["dockerfile_apache_archive_mirror_host"] == (
            DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
        ), compact
        assert compact["task_staging"][
            "dockerfile_maven_mirror_patch_applied"
        ] is True, compact
        assert compact["task_staging"]["dockerfile_maven_mirror_host"] == (
            DEFAULT_DOCKER_MAVEN_MIRROR_HOST
        ), compact
        assert compact["task_staging"]["task_skills_removed"] is True, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "prepared-tasks" not in compact_text, compact
        assert "FROM ubuntu" not in compact_text, compact


def test_skillsbench_controller_trace_counts_are_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-controller-trace-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=1.0)
        blind_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-blind-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "verifier_feedback_observation_count": 0,
            "official_feedback_blinded_count": 2,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                    "tool_calls": 5,
                },
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 7,
                },
            ],
            "official_success_observed": True,
            "official_success_observation_count": 1,
            "first_success_round": 2,
            "official_feedback_forwarded": False,
            "blind_loop": True,
            "max_rounds_budget": 2,
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "last_decision": "stop_after_blind_loop_official_success_observed_without_feedback",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        blind_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-blind-loop-treatment",
                controller_trace=blind_trace,
            )
        )
        assert blind_compact is not None
        assert blind_compact["historical_route_read_only"] is True, blind_compact
        assert blind_compact["skillsbench_route_semantics"] == "historical_nonproduct_invalid_for_comparison", blind_compact
        assert blind_compact["official_score_comparable_to_loopx_treatment"] is False
        assert blind_compact["blind_loop"] is True, blind_compact
        assert blind_compact["official_feedback_blinded"] is True, blind_compact
        assert blind_compact["reward_feedback_forwarded"] is False, blind_compact
        blind_counters = blind_compact["interaction_counters"]
        assert blind_counters["controller_reward_observation_count"] == 2, blind_compact
        assert blind_counters["controller_round_reward_count"] == 2, blind_compact
        assert blind_counters["controller_official_success_observed"] is True, blind_compact
        assert blind_counters["controller_official_success_observation_count"] == 1, blind_compact
        assert blind_counters["controller_first_success_round"] == 2, blind_compact
        assert blind_counters["controller_verifier_feedback_observation_count"] == 0, blind_compact
        assert blind_counters["controller_official_feedback_blinded_count"] == 2, blind_compact
        assert blind_counters["controller_official_feedback_forwarded"] is False, blind_compact
        assert blind_counters["controller_blind_loop"] is True, blind_compact
        assert blind_counters["controller_max_rounds_budget"] == 2, blind_compact
        round_trace = blind_compact["round_reward_trace"]
        assert round_trace["first_success_round"] == 2, blind_compact
        assert round_trace["success_observed"] is True, blind_compact
        assert round_trace["official_feedback_blinded"] is True, blind_compact
        assert round_trace["reward_feedback_forwarded"] is False, blind_compact
        assert round_trace["final_round"] == 2, blind_compact
        assert round_trace["final_round_reward"] == 1.0, blind_compact
        assert round_trace["best_reward_round"] == 2, blind_compact
        assert round_trace["best_round_reward"] == 1.0, blind_compact
        assert round_trace["best_round_is_final"] is True, blind_compact
        assert round_trace["loop_score_policy"] == (
            "best_round_for_offline_controller_analysis"
        ), blind_compact
        assert round_trace["official_score_policy"] == (
            "final_workspace_official_result"
        ), blind_compact
        assert [item["reward"] for item in round_trace["records"]] == [0.0, 1.0], blind_compact
        assert round_trace["records"][1]["passed"] is True, blind_compact
        assert blind_compact["episode_policy"]["reward_feedback_forwarded"] is False
        assert blind_compact["episode_policy"]["official_feedback_blinded"] is True

        final_result_path = root / "final-result.json"
        write_json(
            final_result_path,
            {
                "rewards": {"reward": 1.0},
                "n_tool_calls": 9,
            },
        )
        partial_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-acp-blind-loop-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "blind_loop": True,
            "max_round_observed": 1,
            "last_decision": "send_blind_scheduled_continuation",
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                }
            ],
            "reward_observation_count": 1,
            "official_success_observed": False,
            "official_success_observation_count": 0,
            "first_success_round": None,
        }
        _merge_final_result_round_reward(partial_trace, final_result_path)
        assert partial_trace["reward_observation_count"] == 2, partial_trace
        assert partial_trace["official_feedback_blinded_count"] == 2, partial_trace
        assert partial_trace["official_success_observed"] is True, partial_trace
        assert partial_trace["official_success_observation_count"] == 1, partial_trace
        assert partial_trace["first_success_round"] == 2, partial_trace
        assert partial_trace["round_rewards"][1]["agent_round"] == 2, partial_trace
        assert partial_trace["round_rewards"][1]["reward"] == 1.0, partial_trace
        assert partial_trace["round_rewards"][1]["source"] == "benchflow_final_result", partial_trace

        depth_gate_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "max_round_observed": 4,
            "last_decision": "continue_after_declared_done_depth_gate_gap",
            "round_rewards": [
                {
                    "agent_round": index,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                }
                for index in range(1, 5)
            ],
            "reward_observation_count": 4,
            "official_success_observed": False,
            "official_success_observation_count": 0,
            "first_success_round": None,
        }
        _merge_final_result_round_reward(depth_gate_trace, final_result_path)
        assert depth_gate_trace["reward_observation_count"] == 5, depth_gate_trace
        assert depth_gate_trace["official_success_observed"] is True, depth_gate_trace
        assert depth_gate_trace["first_success_round"] == 5, depth_gate_trace
        assert depth_gate_trace["round_rewards"][4]["agent_round"] == 5, depth_gate_trace
        assert depth_gate_trace["round_rewards"][4]["reward"] == 1.0, depth_gate_trace


def test_skillsbench_round_trace_records_best_round_score() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-best-round-score-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-blind-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 5,
            "controller_action_decisions": 5,
            "initial_prompt_count": 1,
            "followup_prompt_count": 4,
            "reward_observation_count": 5,
            "official_feedback_blinded_count": 5,
            "round_rewards": [
                {"agent_round": 1, "reward_present": True, "reward": 0.25, "passed": False},
                {"agent_round": 2, "reward_present": True, "reward": 0.25, "passed": False},
                {"agent_round": 3, "reward_present": True, "reward": 0.0, "passed": False},
                {"agent_round": 4, "reward_present": True, "reward": 0.0, "passed": False},
                {"agent_round": 5, "reward_present": True, "reward": 0.0, "passed": False},
            ],
            "official_success_observed": False,
            "first_success_round": None,
            "official_feedback_forwarded": False,
            "blind_loop": True,
            "max_rounds_budget": 5,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-blind-loop-treatment",
                controller_trace=trace,
            )
        )
        assert compact is not None
        assert compact["historical_route_read_only"] is True, compact
        assert compact["skillsbench_route_semantics"] == "historical_nonproduct_invalid_for_comparison", compact
        assert compact["official_score_comparable_to_loopx_treatment"] is False
        round_trace = compact["round_reward_trace"]
        assert compact["official_score"] == 0.0, compact
        assert round_trace["final_round"] == 5, round_trace
        assert round_trace["final_round_reward"] == 0.0, round_trace
        assert round_trace["best_reward_round"] == 1, round_trace
        assert round_trace["best_round_reward"] == 0.25, round_trace
        assert round_trace["best_round_passed"] is False, round_trace
        assert round_trace["best_round_is_final"] is False, round_trace
        assert round_trace["loop_score_policy"] == (
            "best_round_for_offline_controller_analysis"
        ), round_trace

        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 0,
            "reward_observation_count": 1,
            "verifier_feedback_observation_count": 1,
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "last_decision": "send_followup_after_failed_reward",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["controller_trace_present"] is True, compact
        assert counters["heartbeat_count"] == 2, compact
        assert counters["controller_action_decisions"] == 2, compact
        assert counters["controller_initial_prompt_count"] == 1, compact
        assert counters["controller_followup_prompt_count"] == 1, compact
        assert counters["counter_trust_level"] == (
            "official_benchflow_compact_result_plus_loopx_controller_trace"
        ), compact
        assert "loopx:controller_trace.public.json" in compact["evidence_files"]
        assert compact["read_boundary"]["controller_trace_read"] is True, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "private_verifier_output" not in compact_text
        assert "TASK INSTRUCTION" not in compact_text

        worker_trace_dir = root / "native-worker-traces"
        worker_trace_dir.mkdir()
        write_json(
            worker_trace_dir / "worker-000001.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": True,
                "route": "codex-app-server-goal-baseline",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "turn": {
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "goal_status": "active",
                    "turn_id_present": True,
                    "turn_status": "completed",
                    "turn_completed_observed": True,
                    "assistant_message_present": True,
                    "assistant_message_chars": 42,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        write_json(
            worker_trace_dir / "bridge-agent-ops.compact.json",
            {
                "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
                "ok": True,
                "route": "codex-app-server-goal-baseline",
                "trace_kind": "remote_command_file_bridge_agent_operations",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "remote_command_file_bridge_agent_operations": {
                    "schema_version": (
                        "skillsbench_remote_command_file_bridge_agent_operations_v0"
                    ),
                    "request_count": 2,
                    "success_count": 2,
                    "failure_count": 0,
                    "operation_counts": {"exec": 2},
                    "returncode_counts": {"0": 2},
                    "failure_category_counts": {},
                    "loopx_cli_call_count": 0,
                    "loopx_cli_subcommand_counts": {},
                    "successful_loopx_cli_subcommand_counts": {},
                    "successful_loopx_cli_command_records": [],
                    "loopx_state_read_count": 0,
                    "loopx_state_write_count": 0,
                    "task_facing_operation_count": 2,
                    "preflight_success_count": 0,
                    "preflight_failure_count": 0,
                    "task_facing_success_count": 2,
                    "task_facing_failure_count": 0,
                    "probe_operation_count": 0,
                    "inflight_operation_count": 0,
                    "interrupted_operation_count": 0,
                    "task_facing_interrupted_count": 0,
                    "raw_material_recorded": False,
                },
                "boundary": {
                    "raw_command_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "upload_performed": False,
                    "submit_performed": False,
                },
            },
        )
        app_server_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(worker_trace_dir),
            },
            app_server_trace,
        )
        _merge_host_local_acp_relay_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(worker_trace_dir),
            },
            app_server_trace,
        )
        native_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=app_server_trace,
            )
        )
        assert native_compact is not None
        assert native_compact["case_id"] == "llm-prefix-cache-replay", native_compact
        assert native_compact["case_ids"] == ["llm-prefix-cache-replay"], native_compact
        assert native_compact["validation"]["loopx_controller_trace_present"] is True
        assert native_compact["validation"]["failed_checks"] == [], native_compact
        native_counters = native_compact["interaction_counters"]
        assert native_counters["controller_trace_present"] is True, native_compact
        assert native_counters["native_goal_worker_route"] is True, native_compact
        assert native_counters["native_goal_worker_trace_count"] == 1, native_compact
        assert native_counters["native_goal_worker_ok_count"] == 1, native_compact
        assert native_counters["native_goal_worker_goal_get_count"] == 1, native_compact
        assert native_counters["native_goal_worker_turn_start_count"] == 1, native_compact
        assert native_counters["native_goal_worker_turn_completed_observed_count"] == 1, native_compact
        assert native_counters["native_goal_worker_raw_material_recorded"] is False, native_compact
        assert native_counters["remote_command_file_bridge_agent_request_count"] == 2, native_compact
        assert native_counters[
            "remote_command_file_bridge_agent_task_facing_operation_count"
        ] == 2, native_compact
        assert native_counters[
            "remote_command_file_bridge_agent_task_facing_success_count"
        ] == 2, native_compact
        native_validation = native_compact["validation"]
        assert native_validation["native_goal_worker_trace_observed"] is True, native_compact
        assert native_validation["native_goal_worker_trace_count"] == 1, native_compact
        assert native_validation["native_goal_worker_trace_status"] == "public_trace_observed", native_compact

        connected_no_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        connected_no_trace_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-connected-no-trace",
                    reward=0.0,
                    task_id="tictoc-unnecessary-abort-detection",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=connected_no_trace,
            )
        )
        assert connected_no_trace_compact is not None
        no_trace_validation = connected_no_trace_compact["validation"]
        assert no_trace_validation["failed_checks"] == [
            "native_goal_worker_countable_baseline",
            "native_goal_worker_public_trace_missing"
        ], connected_no_trace_compact
        assert no_trace_validation["native_goal_worker_connected"] is True, connected_no_trace_compact
        assert no_trace_validation["native_goal_worker_trace_observed"] is False, connected_no_trace_compact
        assert no_trace_validation["native_goal_worker_trace_count"] == 0, connected_no_trace_compact
        assert (
            no_trace_validation["native_goal_worker_trace_status"]
            == "worker_connected_trace_dir_missing"
        ), connected_no_trace_compact

        lifecycle_trace_dir = root / "native-worker-lifecycle-traces"
        lifecycle_trace_dir.mkdir()
        write_json(
            lifecycle_trace_dir / "worker-lifecycle.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": False,
                "route": "codex-app-server-goal-baseline",
                "trace_kind": "relay_lifecycle",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "relay": {
                    "schema_version": "skillsbench_app_server_goal_worker_lifecycle_trace_v0",
                    "stage": "session_new",
                    "app_server_goal_worker": True,
                    "worker_public_trace_configured": True,
                    "raw_prompt_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "host_paths_recorded": False,
                },
                "turn": {
                    "thread_id_present": False,
                    "goal_get_present": False,
                    "turn_id_present": False,
                    "turn_completed_observed": False,
                    "assistant_message_present": False,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        connected_lifecycle_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(lifecycle_trace_dir),
            },
            connected_lifecycle_trace,
        )
        lifecycle_trace_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-connected-lifecycle-trace",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=connected_lifecycle_trace,
            )
        )
        assert lifecycle_trace_compact is not None
        lifecycle_validation = lifecycle_trace_compact["validation"]
        assert lifecycle_validation["failed_checks"] == [
            "native_goal_worker_countable_baseline",
            "native_goal_worker_public_trace_missing"
        ], lifecycle_trace_compact
        assert lifecycle_validation["native_goal_worker_trace_observed"] is True, lifecycle_trace_compact
        assert lifecycle_validation["native_goal_worker_trace_count"] == 1, lifecycle_trace_compact
        assert lifecycle_validation["native_goal_worker_lifecycle_trace_count"] == 1, lifecycle_trace_compact
        assert (
            lifecycle_validation["native_goal_worker_trace_status"]
            == "worker_connected_no_prompt_trace"
        ), lifecycle_trace_compact
        lifecycle_counters = lifecycle_trace_compact["interaction_counters"]
        assert lifecycle_counters["native_goal_worker_lifecycle_trace_count"] == 1, lifecycle_trace_compact
        assert lifecycle_counters["native_goal_worker_turn_start_count"] == 0, lifecycle_trace_compact

        worker_failure_trace_dir = root / "native-worker-first-action-timeout"
        worker_failure_trace_dir.mkdir()
        write_json(
            worker_failure_trace_dir / "worker-failure.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": False,
                "route": "codex-app-server-goal-baseline",
                "trace_kind": "host_worker_process_failure",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "worker_process": {
                    "schema_version": "skillsbench_host_worker_process_failure_v0",
                    "stage": "first_action_timeout",
                    "failure_category": "codex_exec_first_action_timeout",
                    "returncode": -15,
                    "stdout_bytes": 0,
                    "stderr_bytes": 32,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "host_paths_recorded": False,
                },
                "worker_contract": {
                    "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                    "route": "codex-app-server-goal-baseline",
                    "ready": False,
                    "runner_integration_ready": True,
                    "first_blocker": "first_action_timeout",
                },
                "turn": {
                    "thread_id_present": False,
                    "goal_get_present": False,
                    "turn_id_present": False,
                    "turn_completed_observed": False,
                    "assistant_message_present": False,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        first_action_timeout_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(worker_failure_trace_dir),
            },
            first_action_timeout_trace,
        )
        first_action_timeout_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-worker-first-action-timeout-result",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=first_action_timeout_trace,
            )
        )
        assert first_action_timeout_compact is not None
        expected_native_worker_failure = (
            "skillsbench_native_goal_worker_failed_codex_exec_first_action_timeout"
        )
        assert (
            first_action_timeout_compact["score_failure_attribution"]
            == expected_native_worker_failure
        ), first_action_timeout_compact
        assert first_action_timeout_compact[
            "official_score_comparable_to_native_codex"
        ] is False, first_action_timeout_compact
        assert first_action_timeout_compact[
            "official_score_comparable_to_loopx_treatment"
        ] is False, first_action_timeout_compact
        assert "official_verifier_solution_failure" not in first_action_timeout_compact[
            "failure_attribution_labels"
        ], first_action_timeout_compact
        assert first_action_timeout_compact["runner_failure"][
            "native_goal_worker"
        ]["failure_category"] == "codex_exec_first_action_timeout"
        assert first_action_timeout_compact["validation"][
            "native_goal_worker_failure_category"
        ] == "codex_exec_first_action_timeout"
        assert first_action_timeout_compact["native_goal_worker_contract"][
            "countable_baseline"
        ] is False
        assert first_action_timeout_compact["attempt_accounting"][
            "failure_class"
        ] == "job_materialization_failed", first_action_timeout_compact

        no_assistant_trace_dir = root / "native-worker-no-assistant-message"
        no_assistant_trace_dir.mkdir()
        write_json(
            no_assistant_trace_dir / "worker-no-assistant.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": False,
                "route": "codex-app-server-goal-baseline",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "worker_contract": {
                    "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                    "route": "codex-app-server-goal-baseline",
                    "ready": False,
                    "runner_integration_ready": True,
                    "first_blocker": "codex_app_server_no_assistant_message",
                },
                "turn": {
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "turn_id_present": True,
                    "turn_completed_observed": True,
                    "assistant_message_present": False,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        no_assistant_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(no_assistant_trace_dir),
            },
            no_assistant_trace,
        )
        no_assistant_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-worker-no-assistant-result",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=no_assistant_trace,
            )
        )
        assert no_assistant_compact is not None
        expected_no_assistant_failure = (
            "skillsbench_native_goal_worker_failed_codex_app_server_no_assistant_message"
        )
        assert (
            no_assistant_compact["score_failure_attribution"]
            == expected_no_assistant_failure
        ), no_assistant_compact
        assert no_assistant_compact["native_goal_worker_contract"][
            "countable_baseline"
        ] is False, no_assistant_compact
        assert no_assistant_compact["native_goal_worker_contract"][
            "failure_category"
        ] == "codex_app_server_no_assistant_message", no_assistant_compact
        assert no_assistant_compact["native_goal_worker_contract"][
            "assistant_message_present_count"
        ] == 0, no_assistant_compact
        assert no_assistant_compact[
            "official_score_comparable_to_native_codex"
        ] is False, no_assistant_compact
        assert "official_verifier_solution_failure" not in no_assistant_compact[
            "failure_attribution_labels"
        ], no_assistant_compact
        assert no_assistant_compact["attempt_accounting"][
            "failure_class"
        ] == "job_materialization_failed", no_assistant_compact

        context_only_trace_dir = root / "native-worker-context-only-message"
        context_only_trace_dir.mkdir()
        write_json(
            context_only_trace_dir / "worker-context-only.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": False,
                "route": "codex-app-server-goal-baseline",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "worker_adapter": {
                    "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                    "reasoning_effort": "xhigh",
                    "agent_execution_mode": "codex_app_server_goal",
                    "worker_surface": "native_codex_app_server_goal",
                },
                "worker_contract": {
                    "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                    "route": "codex-app-server-goal-baseline",
                    "ready": False,
                    "runner_integration_ready": True,
                    "first_blocker": "codex_app_server_context_only_assistant_message",
                },
                "turn": {
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "turn_id_present": True,
                    "turn_completed_observed": True,
                    "assistant_message_present": True,
                    "assistant_message_chars": 10339,
                    "agent_message_item_count": 1,
                    "agent_message_delta_count": 0,
                    "assistant_message_context_only": True,
                    "post_context_assistant_chars": 0,
                    "context_only_recovery_attempted": True,
                    "context_only_recovery_succeeded": False,
                    "context_only_followup_start_attempted": True,
                    "context_only_followup_start_succeeded": False,
                    "context_only_followup_start_error_type": (
                        "codex_app_server_context_only_followup_start_failed"
                    ),
                    "reasoning_effort": "xhigh",
                    "first_action_observed": False,
                    "effective_action_observed": False,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        context_only_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(context_only_trace_dir),
            },
            context_only_trace,
        )
        context_only_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-worker-context-only-result",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=context_only_trace,
            )
        )
        assert context_only_compact is not None
        expected_context_only_failure = (
            "skillsbench_native_goal_worker_failed_"
            "codex_app_server_context_only_assistant_message"
        )
        assert (
            context_only_compact["score_failure_attribution"]
            == expected_context_only_failure
        ), context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "countable_baseline"
        ] is False, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "assistant_context_only_count"
        ] == 1, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "context_only_recovery_attempted_count"
        ] == 1, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "context_only_recovery_succeeded_count"
        ] == 0, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "context_only_followup_start_attempted_count"
        ] == 1, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "context_only_followup_start_succeeded_count"
        ] == 0, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "post_context_assistant_chars_total"
        ] == 0, context_only_compact
        assert context_only_compact["native_goal_worker_contract"][
            "reasoning_effort"
        ] == "xhigh", context_only_compact
        context_only_counters = context_only_compact["interaction_counters"]
        assert (
            context_only_counters["native_goal_worker_assistant_context_only_count"]
            == 1
        ), context_only_compact
        assert (
            context_only_counters[
                "native_goal_worker_context_only_followup_start_attempted_count"
            ]
            == 1
        ), context_only_compact
        assert (
            context_only_counters["native_goal_worker_reasoning_effort"] == "xhigh"
        ), context_only_compact
        assert context_only_compact[
            "official_score_comparable_to_native_codex"
        ] is False, context_only_compact
        assert "official_verifier_solution_failure" not in context_only_compact[
            "failure_attribution_labels"
        ], context_only_compact
        assert context_only_compact["attempt_accounting"][
            "failure_class"
        ] == "job_materialization_failed", context_only_compact

        incomplete_no_activity_trace_dir = root / "native-worker-inprogress-no-activity"
        incomplete_no_activity_trace_dir.mkdir()
        write_json(
            incomplete_no_activity_trace_dir / "worker-inprogress.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": True,
                "route": "codex-app-server-goal-baseline",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "travel-planning",
                "worker_contract": {
                    "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                    "route": "codex-app-server-goal-baseline",
                    "ready": True,
                    "runner_integration_ready": True,
                    "first_blocker": "ready_for_skillsbench_app_server_goal_worker",
                },
                "turn": {
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "turn_id_present": True,
                    "turn_status": "inProgress",
                    "turn_completed_observed": True,
                    "assistant_message_present": True,
                    "assistant_message_chars": 4012,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        write_json(
            incomplete_no_activity_trace_dir / "bridge-agent-empty.compact.json",
            {
                "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
                "ok": True,
                "route": "codex-app-server-goal-baseline",
                "trace_kind": "remote_command_file_bridge_agent_operations",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "travel-planning",
                "remote_command_file_bridge_agent_operations": {
                    "schema_version": (
                        "skillsbench_remote_command_file_bridge_agent_operations_v0"
                    ),
                    "request_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "operation_counts": {},
                    "returncode_counts": {},
                    "failure_category_counts": {},
                    "task_facing_operation_count": 0,
                    "task_facing_success_count": 0,
                    "task_facing_failure_count": 0,
                    "raw_material_recorded": False,
                },
                "boundary": {
                    "raw_command_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "upload_performed": False,
                    "submit_performed": False,
                },
            },
        )
        incomplete_no_activity_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(incomplete_no_activity_trace_dir),
            },
            incomplete_no_activity_trace,
        )
        _merge_host_local_acp_relay_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(incomplete_no_activity_trace_dir),
            },
            incomplete_no_activity_trace,
        )
        incomplete_no_activity_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-worker-inprogress-no-activity-result",
                    reward=0.0,
                    task_id="travel-planning",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=incomplete_no_activity_trace,
            )
        )
        assert incomplete_no_activity_compact is not None
        _apply_native_goal_worker_finish_guard_attribution(
            incomplete_no_activity_compact
        )
        expected_finish_guard_failure = (
            "skillsbench_native_goal_worker_incomplete_turn_without_task_activity"
        )
        assert (
            incomplete_no_activity_compact["score_failure_attribution"]
            == expected_finish_guard_failure
        ), incomplete_no_activity_compact
        assert "official_verifier_solution_failure" not in (
            incomplete_no_activity_compact["failure_attribution_labels"]
        ), incomplete_no_activity_compact
        assert incomplete_no_activity_compact[
            "official_score_comparable_to_native_codex"
        ] is False, incomplete_no_activity_compact
        finish_guard_counters = incomplete_no_activity_compact["interaction_counters"]
        assert (
            finish_guard_counters[
                "native_goal_worker_incomplete_after_completion_event_count"
            ]
            == 1
        ), incomplete_no_activity_compact
        assert incomplete_no_activity_compact["native_goal_worker_contract"][
            "countable_baseline"
        ] is False, incomplete_no_activity_compact
        assert incomplete_no_activity_compact["attempt_accounting"][
            "case_attempt_countable"
        ] is False, incomplete_no_activity_compact

        bridge_quiet_result_path = write_official_skillsbench_result(
            root / "native-worker-bridge-quiet-result",
            reward=0.0,
            task_id="adaptive-cruise-control",
        )
        bridge_quiet_result = json.loads(
            bridge_quiet_result_path.read_text(encoding="utf-8")
        )
        bridge_quiet_result["error"] = "codex_exec_task_output_quiet_timeout"
        write_json(bridge_quiet_result_path, bridge_quiet_result)
        bridge_quiet_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "native_goal_worker_trace_dir_present": True,
            "native_goal_worker_public_trace_read": True,
            "native_goal_worker_trace_count": 4,
            "native_goal_worker_lifecycle_trace_count": 3,
            "native_goal_worker_prompt_received_count": 1,
            "native_goal_worker_failure_trace_count": 1,
            "native_goal_worker_failure_category": "codex_exec_task_output_quiet_timeout",
            "native_goal_worker_first_blocker": "task_output_quiet_timeout",
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 20,
            "remote_command_file_bridge_agent_task_facing_operation_count": 20,
            "remote_command_file_bridge_agent_task_facing_success_count": 20,
            "remote_command_file_bridge_agent_failure_count": 0,
            "host_local_acp_bridge_progress_status": (
                "bridge_task_facing_success_observed"
            ),
            "host_local_acp_bridge_progress_signal_source": (
                "remote_command_file_bridge_agent_operations"
            ),
            "host_local_acp_codex_exec_failure_trace_present": True,
            "host_local_acp_codex_exec_failure_trace_count": 1,
            "host_local_acp_codex_exec_failure_category": (
                "codex_exec_task_output_quiet_timeout"
            ),
            "host_local_acp_codex_exec_failure_categories": [
                "codex_exec_task_output_quiet_timeout"
            ],
            "host_local_acp_codex_exec_failure_raw_material_recorded": False,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        bridge_quiet_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                bridge_quiet_result_path,
                route="codex-app-server-goal-baseline",
                controller_trace=bridge_quiet_trace,
            )
        )
        assert bridge_quiet_compact is not None
        assert bridge_quiet_compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), bridge_quiet_compact
        assert "runner_failure" not in bridge_quiet_compact, bridge_quiet_compact
        assert "skillsbench_runner_setup_error" not in bridge_quiet_compact[
            "failure_attribution_labels"
        ], bridge_quiet_compact
        assert (
            "skillsbench_host_local_acp_task_output_quiet_after_bridge_attempt"
            in bridge_quiet_compact["runner_warning_labels"]
        ), bridge_quiet_compact
        bridge_quiet_worker = bridge_quiet_compact["native_goal_worker_contract"]
        assert bridge_quiet_worker["countable_baseline"] is True, bridge_quiet_compact
        assert bridge_quiet_worker["countability_source"] == (
            "remote_command_file_bridge_task_facing_success"
        ), bridge_quiet_compact
        assert bridge_quiet_worker["bridge_task_facing_success_count"] == 20, (
            bridge_quiet_compact
        )
        bridge_quiet_accounting = bridge_quiet_compact["attempt_accounting"]
        assert bridge_quiet_accounting["failure_class"] == "solver_failed", (
            bridge_quiet_accounting
        )
        assert bridge_quiet_accounting["case_attempt_countable"] is True, (
            bridge_quiet_accounting
        )
        assert bridge_quiet_accounting["solver_attempt_countable"] is True, (
            bridge_quiet_accounting
        )
        assert bridge_quiet_accounting["verifier_attempt_countable"] is True, (
            bridge_quiet_accounting
        )
        assert bridge_quiet_accounting["official_score_attempt_countable"] is True, (
            bridge_quiet_accounting
        )

        empty_worker_trace_dir = root / "native-worker-empty-traces"
        empty_worker_trace_dir.mkdir()
        connected_empty_trace_dir = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(empty_worker_trace_dir),
            },
            connected_empty_trace_dir,
        )
        empty_trace_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native-connected-empty-trace-dir",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=connected_empty_trace_dir,
            )
        )
        assert empty_trace_compact is not None
        empty_trace_validation = empty_trace_compact["validation"]
        assert empty_trace_validation["failed_checks"] == [
            "native_goal_worker_countable_baseline",
            "native_goal_worker_public_trace_missing"
        ], empty_trace_compact
        assert empty_trace_validation["native_goal_worker_connected"] is True, empty_trace_compact
        assert empty_trace_validation["native_goal_worker_trace_dir_present"] is True, empty_trace_compact
        assert empty_trace_validation["native_goal_worker_trace_observed"] is False, empty_trace_compact
        assert empty_trace_validation["native_goal_worker_trace_count"] == 0, empty_trace_compact
        assert (
            empty_trace_validation["native_goal_worker_trace_status"]
            == "worker_connected_no_public_trace"
        ), empty_trace_compact

        baseline = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(root / "baseline", reward=0.0),
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert baseline["native_goal_mode_requested"] is False, baseline
        assert baseline["native_goal_mode_invoked"] is False, baseline
        assert baseline["native_goal_mode_confirmation_status"] == (
            "not_requested"
        ), baseline
        assert baseline["codex_acp_protocol_used"] is True, baseline
        assert baseline["skillsbench_route_semantics"] == (
            "codex_acp_ordinary_agent_blind_loop_no_goal_no_reward_feedback"
        ), baseline
        comparison = {
            "schema_version": "benchmark_comparison_v0",
            "task_id": "skillsbench@1.1/sample-task",
            "comparison_id": "skillsbench-controller-trace-fixture",
            "official_task_score_delta": 1.0,
            "claim_boundary": {
                "leaderboard_claim_allowed": False,
                "official_score_uplift_claim_allowed": False,
                "assisted_collaboration_claim_allowed": False,
                "raw_trace_excluded": True,
            },
        }
        review = build_benchmark_claim_review(
            comparison,
            benchmark_runs=[baseline, compact],
        )
        assert "missing_treatment_worker_loopx_evidence" not in review[
            "decision"
        ]["blockers"], review
        assert review["treatment_worker_evidence"][
            "outer_loopx_controller_present"
        ] is True, review


def test_app_server_goal_round_semantics_survive_compact_and_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-rounds-") as tmp:
        root = Path(tmp)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "max_rounds_budget": 16,
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_trace_dir_present": True,
            "native_goal_worker_public_trace_read": True,
            "native_goal_worker_trace_count": 1,
            "native_goal_worker_ok_count": 1,
            "native_goal_worker_goal_get_count": 1,
            "native_goal_worker_turn_start_count": 1,
            "native_goal_worker_turn_completed_observed_count": 1,
            "native_goal_worker_assistant_message_present_count": 1,
            "native_goal_worker_session_policy": "single_thread_with_blinded_followups",
            "native_goal_worker_max_rounds_budget_applies_to": (
                "benchflow_outer_controller_budget_not_native_goal_attempts"
            ),
            "native_goal_worker_initial_goal_turn_budget": 1,
            "native_goal_worker_same_thread_followup_budget": 2,
            "native_goal_worker_independent_attempt_budget": 3,
            "native_goal_worker_fresh_goal_thread_per_independent_attempt": True,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "result",
                    reward=0.0,
                    task_id="bike-rebalance",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        round_semantics = compact["app_server_goal_round_semantics"]
        assert round_semantics["session_policy"] == (
            "single_thread_with_blinded_followups"
        ), compact
        assert round_semantics["benchflow_max_rounds_budget"] == 16, compact
        assert round_semantics["max_rounds_budget_applies_to"] == (
            "benchflow_outer_controller_budget_not_native_goal_attempts"
        ), compact
        assert round_semantics["initial_goal_turn_budget"] == 1, compact
        assert round_semantics["same_thread_followup_budget"] == 2, compact
        assert round_semantics["independent_attempt_budget"] == 3, compact
        assert (
            round_semantics["fresh_goal_thread_per_independent_attempt"] is True
        ), compact

        ledger_path = root / "ledger.json"
        update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            compact_artifact_ref="runs/public/compact-benchmark-run.json",
        )
        ledger = load_benchmark_run_ledger(ledger_path)
        [run] = ledger["benchmarks"]["skillsbench@1.1"]["cases"]["bike-rebalance"][
            "runs"
        ]
        assert run["max_rounds_budget"] == 16, run
        assert run["native_goal_session_policy"] == (
            "single_thread_with_blinded_followups"
        ), run
        assert run["max_rounds_budget_applies_to"] == (
            "benchflow_outer_controller_budget_not_native_goal_attempts"
        ), run
        assert run["native_goal_initial_turn_budget"] == 1, run
        assert run["native_goal_same_thread_followup_budget"] == 2, run
        assert run["native_goal_independent_attempt_budget"] == 3, run
        assert run["native_goal_fresh_thread_per_independent_attempt"] is True, run
        from loopx.benchmark_ledger import build_benchmark_run_ledger_current_aggregate

        current_aggregate = build_benchmark_run_ledger_current_aggregate(
            ledger,
            benchmark_id="skillsbench@1.1",
            canonical_case_ids=["bike-rebalance"],
        )
        current = current_aggregate["case_best"]["bike-rebalance"]
        assert current["max_rounds_budget_applies_to"] == (
            "benchflow_outer_controller_budget_not_native_goal_attempts"
        ), current


def test_app_server_goal_round_semantics_seed_controller_trace_from_plan() -> None:
    trace = _new_controller_trace(
        "codex-app-server-goal-baseline",
        max_rounds=16,
    )
    plan = {
        "route": "codex-app-server-goal-baseline",
        "app_server_goal_followup_max": 2,
        "app_server_goal_round_semantics": {
            "session_policy": "single_thread_with_blinded_followups",
            "same_thread_followup_budget": 2,
            "independent_attempt_budget": 3,
        },
        "independent_goal_retry": {"attempt_budget": 3},
    }

    _apply_app_server_goal_round_semantics_to_controller_trace(trace, plan)

    assert trace["native_goal_worker_route"] is True, trace
    assert trace["native_goal_worker_session_policy"] == (
        "single_thread_with_blinded_followups"
    ), trace
    assert trace["native_goal_worker_same_thread_followup_budget"] == 2, trace
    assert trace["native_goal_worker_independent_attempt_budget"] == 3, trace


def test_skillsbench_product_mode_declared_done_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-product-done-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.25)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "agent_declared_done": True,
            "declared_done_round": 1,
            "declared_done_score": 0.25,
            "heartbeat_count": 1,
            "controller_action_decisions": 1,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 1,
            "reward_observation_count": 1,
            "official_feedback_blinded_count": 1,
            "official_feedback_forwarded": False,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.25,
                    "passed": False,
                }
            ],
            "official_success_observed": False,
            "first_success_round": None,
            "blind_loop": False,
            "case_goal_state_packet_present": True,
            "case_goal_state_init_required": True,
            "case_goal_state_initialized_before_agent": True,
            "case_goal_state_init_status": "passed",
            "case_goal_state_path": PRODUCT_MODE_CASE_STATE_PATH,
            "case_goal_state_schema_version": PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION,
            "declared_done_requires_no_remaining_goals": True,
            "benchflow_intermediate_soft_verify_policy": "final-only",
            "benchflow_intermediate_soft_verify_final_only": True,
            "benchflow_intermediate_soft_verify_call_count": 0,
            "benchflow_intermediate_soft_verify_skipped_count": 1,
            "benchflow_intermediate_soft_verify_raw_output_recorded": False,
            "max_rounds_budget": 5,
            "loopx_state_reads": 1,
            "loopx_state_writes": 1,
            "loopx_case_state_reads": 1,
            "loopx_case_state_writes": 1,
            "last_decision": "stop_after_agent_declared_done_without_official_feedback",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["product_mode"] is True, compact
        assert compact["official_feedback_blinded"] is True, compact
        assert compact["reward_feedback_forwarded"] is False, compact
        counters = compact["interaction_counters"]
        assert counters["product_mode"] is True, compact
        assert counters["case_goal_state_packet_present"] is True, compact
        assert counters["case_goal_state_init_required"] is True, compact
        assert counters["case_goal_state_initialized_before_agent"] is True, compact
        assert counters["case_goal_state_init_status"] == "passed", compact
        assert (
            counters["case_goal_state_schema_version"]
            == PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION
        ), compact
        assert counters["case_goal_state_path"] == PRODUCT_MODE_CASE_STATE_PATH, compact
        assert counters["declared_done_requires_no_remaining_goals"] is True, compact
        assert counters["agent_declared_done"] is True, compact
        assert counters["declared_done_round"] == 1, compact
        assert counters["benchflow_intermediate_soft_verify_policy"] == "final-only"
        assert counters["benchflow_intermediate_soft_verify_final_only"] is True
        assert counters["benchflow_intermediate_soft_verify_call_count"] == 0
        assert counters["benchflow_intermediate_soft_verify_skipped_count"] == 1
        assert (
            counters["benchflow_intermediate_soft_verify_raw_output_recorded"]
            is False
        )
        assert counters["loopx_case_state_reads"] == 1, compact
        assert counters["loopx_case_state_writes"] == 1, compact
        round_trace = compact["round_reward_trace"]
        assert round_trace["agent_declared_done"] is True, compact
        assert round_trace["declared_done_round"] == 1, compact
        assert round_trace["declared_done_score"] == 0.25, compact
        assert round_trace["final_round"] == 1, compact
        assert round_trace["final_round_reward"] == 0.25, compact
        assert round_trace["best_reward_round"] == 1, compact
        assert round_trace["best_round_reward"] == 0.25, compact
        assert compact["episode_policy"]["product_mode"] is True, compact

        update = update_benchmark_run_ledger(
            ledger_path=root / "ledger.json",
            benchmark_run=compact,
            run_group_id="product-mode-declared-done-fixture",
            dry_run=False,
        )
        run = update["entry"]
        assert run["agent_declared_done"] is True, update
        assert run["declared_done_round"] == 1, update
        assert run["declared_done_score"] == 0.25, update
        assert run["final_round"] == 1, update
        assert run["final_round_reward"] == 0.25, update
        assert run["best_reward_round"] == 1, update
        assert run["best_round_reward"] == 0.25, update


def test_skillsbench_product_mode_lifecycle_checkpoint_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-lifecycle-compact-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 0,
            "product_mode_lifecycle_checkpoint_required": True,
            "product_mode_lifecycle_checkpoint_count": 1,
            "product_mode_lifecycle_checkpoint_round": 1,
            "product_mode_lifecycle_checkpoint_missing_reason": (
                "missing_case_local_loopx_state_read_or_write"
            ),
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "last_decision": "send_product_mode_lifecycle_checkpoint_continuation",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode"] is True, compact
        assert counters["product_mode_lifecycle_checkpoint_required"] is True
        assert counters["product_mode_lifecycle_checkpoint_count"] == 1
        assert counters["product_mode_lifecycle_checkpoint_round"] == 1
        assert counters["product_mode_lifecycle_checkpoint_missing_reason"] == (
            "missing_case_local_loopx_state_read_or_write"
        )
        assert compact["score_failure_attribution"] == (
            "skillsbench_product_mode_lifecycle_missing"
        ), compact
        assert compact["official_score_comparable_to_native_codex"] is False, compact
        assert compact["official_score_comparable_to_loopx_treatment"] is False, compact
        assert "skillsbench_product_mode_uncountable_treatment" in compact[
            "failure_attribution_labels"
        ], compact
        lifecycle_contract = compact["product_mode_lifecycle_contract"]
        assert lifecycle_contract == {
            "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
            "required": True,
            "satisfied": False,
            "countable_treatment": False,
            "state_read_count": 0,
            "state_write_count": 0,
            "checkpoint_required": True,
            "checkpoint_count": 1,
            "closeout_required": False,
            "closeout_satisfied": True,
            "agent_operation_trace_required": False,
            "agent_operation_trace_satisfied": False,
            "agent_operation_trace_missing": False,
            "orchestrated_driver_lifecycle_satisfied": False,
            "orchestrated_driver_counts_as_product_mode": False,
            "agent_bridge_state_read_count": 0,
            "agent_bridge_state_write_count": 0,
            "agent_bridge_todo_closeout_count": 0,
            "agent_bridge_refresh_state_count": 0,
            "agent_bridge_quota_spend_slot_count": 0,
            "driver_lifecycle_state_read_count": 0,
            "driver_lifecycle_state_write_count": 0,
            "checkpoint_round": 1,
            "missing_reason": "missing_case_local_loopx_state_read_or_write",
        }, compact
        compact_again = compact_benchmark_run(compact)
        assert compact_again is not None
        compact_counters = compact_again["interaction_counters"]
        assert compact_counters["product_mode_lifecycle_checkpoint_required"] is True
        assert compact_counters["product_mode_lifecycle_checkpoint_count"] == 1
        assert compact_again["score_failure_attribution"] == (
            "skillsbench_product_mode_lifecycle_missing"
        ), compact_again
        assert compact_again["product_mode_lifecycle_contract"] == (
            lifecycle_contract
        ), compact_again
        driver_controller_trace = dict(controller_trace)
        driver_controller_trace.update(
            {
                "product_mode_lifecycle_checkpoint_missing_reason": "",
                "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
                "remote_command_file_bridge_driver_lifecycle_execution_style": (
                    "orchestrated_agentloop_loopx_cli"
                ),
                "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
                "remote_command_file_bridge_driver_lifecycle_request_count": 4,
                "remote_command_file_bridge_driver_lifecycle_success_count": 4,
                "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
                "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            }
        )
        driver_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=driver_controller_trace,
            )
        )
        assert driver_compact is not None
        driver_contract = driver_compact["product_mode_lifecycle_contract"]
        assert driver_contract["satisfied"] is True, driver_compact
        assert driver_contract["countable_treatment"] is True, driver_compact
        assert (
            driver_contract["orchestrated_driver_counts_as_product_mode"] is True
        ), driver_contract
        assert driver_contract["state_read_count"] == 1, driver_compact
        assert driver_contract["state_write_count"] == 3, driver_compact
        assert driver_contract["execution_style"] == (
            "orchestrated_agentloop_loopx_cli"
        ), driver_compact
        driver_counters = driver_compact["interaction_counters"]
        assert (
            driver_counters[
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
            ]
            == 1
        ), driver_compact
        assert (
            driver_counters[
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
            ]
            == 3
        ), driver_compact
        assert "skillsbench_product_mode_lifecycle_missing" not in driver_compact[
            "failure_attribution_labels"
        ], driver_compact
        prompt_timeout_controller_trace = dict(driver_controller_trace)
        prompt_timeout_controller_trace.update(
            {
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_command_instrumented": False,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_missing"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 0,
                "remote_command_file_bridge_agent_request_count": 0,
                "remote_command_file_bridge_agent_loopx_cli_call_count": 0,
                "remote_command_file_bridge_agent_loopx_state_read_count": 0,
                "remote_command_file_bridge_agent_loopx_state_write_count": 0,
                "remote_command_file_bridge_agent_todo_closeout_count": 0,
                "remote_command_file_bridge_agent_refresh_state_count": 0,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 0,
            }
        )
        prompt_timeout_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=prompt_timeout_controller_trace,
            )
        )
        assert prompt_timeout_compact is not None
        prompt_timeout_contract = prompt_timeout_compact[
            "product_mode_lifecycle_contract"
        ]
        assert (
            prompt_timeout_contract["orchestrated_driver_lifecycle_satisfied"] is True
        )
        assert (
            prompt_timeout_contract["orchestrated_driver_counts_as_product_mode"]
            is False
        ), prompt_timeout_contract
        assert prompt_timeout_contract["agent_operation_trace_required"] is True
        assert prompt_timeout_contract["agent_operation_trace_missing"] is True
        assert prompt_timeout_contract["countable_treatment"] is False, (
            prompt_timeout_compact
        )
        assert prompt_timeout_contract["closeout_satisfied"] is False
        assert (
            "skillsbench_product_mode_uncountable_treatment"
            in prompt_timeout_compact["failure_attribution_labels"]
        ), prompt_timeout_compact
        assert (
            "skillsbench_remote_bridge_agent_operation_trace_missing"
            in prompt_timeout_compact["failure_attribution_labels"]
        ), prompt_timeout_compact
        failed_agent_controller_trace = dict(driver_controller_trace)
        failed_agent_controller_trace.update(
            {
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_command_instrumented": True,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_recorded_no_success"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 1,
                "remote_command_file_bridge_agent_success_count": 0,
                "remote_command_file_bridge_agent_failure_count": 1,
                "remote_command_file_bridge_agent_failure_category_counts": {
                    "bridge_client_permission_error": 1,
                },
                "remote_command_file_bridge_agent_loopx_cli_call_count": 0,
                "remote_command_file_bridge_agent_loopx_state_read_count": 0,
                "remote_command_file_bridge_agent_loopx_state_write_count": 0,
                "remote_command_file_bridge_agent_todo_closeout_count": 0,
                "remote_command_file_bridge_agent_refresh_state_count": 0,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 0,
            }
        )
        failed_agent_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=failed_agent_controller_trace,
            )
        )
        assert failed_agent_compact is not None
        expected_failed_agent_label = (
            "skillsbench_remote_bridge_agent_operation_failed_"
            "bridge_client_permission_error"
        )
        assert failed_agent_compact["score_failure_attribution"] == (
            expected_failed_agent_label
        ), failed_agent_compact
        assert expected_failed_agent_label in failed_agent_compact[
            "failure_attribution_labels"
        ], failed_agent_compact
        assert "skillsbench_runner_setup_error" in failed_agent_compact[
            "failure_attribution_labels"
        ], failed_agent_compact
        external_agent_controller_trace = dict(driver_controller_trace)
        external_agent_controller_trace.update(
            {
                "remote_command_file_bridge_driver_lifecycle_execution_style": (
                    "prompt_driven_loopx_cli"
                ),
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_command_instrumented": False,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_missing"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 0,
                "remote_command_file_bridge_agent_request_count": 0,
                "remote_command_file_bridge_agent_loopx_state_read_count": 0,
                "remote_command_file_bridge_agent_loopx_state_write_count": 0,
            }
        )
        external_agent_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=external_agent_controller_trace,
            )
        )
        assert external_agent_compact is not None
        external_agent_contract = external_agent_compact[
            "product_mode_lifecycle_contract"
        ]
        assert external_agent_contract["satisfied"] is False, external_agent_compact
        assert external_agent_contract["countable_treatment"] is False, (
            external_agent_compact
        )
        assert (
            external_agent_contract["agent_operation_trace_required"] is True
        ), external_agent_contract
        assert (
            external_agent_contract["agent_operation_trace_missing"] is True
        ), external_agent_contract
        assert external_agent_contract["state_read_count"] == 0, (
            external_agent_contract
        )
        assert external_agent_contract["state_write_count"] == 0, (
            external_agent_contract
        )
        assert external_agent_contract["driver_lifecycle_state_read_count"] == 1
        assert external_agent_contract["driver_lifecycle_state_write_count"] == 3
        assert external_agent_contract["missing_reason"] == (
            "remote_command_file_bridge_agent_operation_trace_missing"
        )
        assert (
            "skillsbench_remote_bridge_agent_operation_trace_missing"
            in external_agent_compact["failure_attribution_labels"]
        ), external_agent_compact
        orchestrated_no_request_controller_trace = dict(driver_controller_trace)
        orchestrated_no_request_controller_trace.update(
            {
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_command_instrumented": True,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_present_no_requests"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 0,
                "remote_command_file_bridge_agent_loopx_state_read_count": 0,
                "remote_command_file_bridge_agent_loopx_state_write_count": 0,
            }
        )
        orchestrated_no_request_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=orchestrated_no_request_controller_trace,
            )
        )
        assert orchestrated_no_request_compact is not None
        orchestrated_no_request_contract = orchestrated_no_request_compact[
            "product_mode_lifecycle_contract"
        ]
        assert orchestrated_no_request_contract["satisfied"] is False, (
            orchestrated_no_request_compact
        )
        assert orchestrated_no_request_contract["countable_treatment"] is False, (
            orchestrated_no_request_compact
        )
        assert (
            orchestrated_no_request_contract[
                "orchestrated_driver_lifecycle_satisfied"
            ]
            is True
        ), orchestrated_no_request_contract
        assert (
            orchestrated_no_request_contract[
                "orchestrated_driver_counts_as_product_mode"
            ]
            is False
        ), orchestrated_no_request_contract
        assert (
            orchestrated_no_request_contract["agent_operation_trace_required"]
            is True
        ), orchestrated_no_request_contract
        assert orchestrated_no_request_contract["missing_reason"] == (
            "remote_command_file_bridge_agent_no_requests"
        ), orchestrated_no_request_contract
        assert "skillsbench_remote_bridge_agent_no_requests" in (
            orchestrated_no_request_compact["failure_attribution_labels"]
        ), orchestrated_no_request_compact
        no_request_controller_trace = dict(external_agent_controller_trace)
        no_request_controller_trace.update(
            {
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_present_no_requests"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
            }
        )
        no_request_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=no_request_controller_trace,
            )
        )
        assert no_request_compact is not None
        no_request_contract = no_request_compact[
            "product_mode_lifecycle_contract"
        ]
        assert no_request_contract["satisfied"] is False, no_request_compact
        assert no_request_contract["countable_treatment"] is False, (
            no_request_compact
        )
        assert no_request_contract["missing_reason"] == (
            "remote_command_file_bridge_agent_no_requests"
        )
        assert (
            "skillsbench_remote_bridge_agent_no_requests"
            in no_request_compact["failure_attribution_labels"]
        ), no_request_compact
        assert (
            "skillsbench_remote_bridge_agent_operation_trace_missing"
            not in no_request_compact["failure_attribution_labels"]
        ), no_request_compact
        agent_bridge_no_closeout_controller_trace = dict(controller_trace)
        agent_bridge_no_closeout_controller_trace.update(
            {
                "followup_prompt_count": 0,
                "stop_decision_count": 1,
                "remote_command_file_bridge_agent_command_configured": True,
                "remote_command_file_bridge_agent_command_instrumented": True,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": True,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_recorded"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 4,
                "remote_command_file_bridge_agent_loopx_cli_call_count": 3,
                "remote_command_file_bridge_agent_loopx_state_read_count": 2,
                "remote_command_file_bridge_agent_loopx_state_write_count": 1,
                "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
                "remote_command_file_bridge_agent_loopx_subcommand_counts": {
                    "quota should-run": 2,
                    "todo claim": 1,
                },
                "product_mode_no_tool_call_lifecycle_abort": True,
                "product_mode_no_tool_call_lifecycle_abort_count": 1,
                "product_mode_no_tool_call_lifecycle_abort_round": 1,
            }
        )
        agent_bridge_no_closeout_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=agent_bridge_no_closeout_controller_trace,
            )
        )
        assert agent_bridge_no_closeout_compact is not None
        no_closeout_contract = agent_bridge_no_closeout_compact[
            "product_mode_lifecycle_contract"
        ]
        assert no_closeout_contract["satisfied"] is False, (
            agent_bridge_no_closeout_compact
        )
        assert no_closeout_contract["countable_treatment"] is False, (
            agent_bridge_no_closeout_compact
        )
        assert no_closeout_contract["state_read_count"] == 2
        assert no_closeout_contract["state_write_count"] == 1
        assert no_closeout_contract["closeout_required"] is True
        assert no_closeout_contract["closeout_satisfied"] is False
        assert no_closeout_contract["agent_bridge_todo_closeout_count"] == 0
        assert no_closeout_contract["agent_bridge_refresh_state_count"] == 0
        assert no_closeout_contract["agent_bridge_quota_spend_slot_count"] == 0
        assert no_closeout_contract["missing_reason"] == (
            "missing_case_local_loopx_closeout"
        )
        assert (
            "skillsbench_product_mode_lifecycle_missing"
            in agent_bridge_no_closeout_compact["failure_attribution_labels"]
        ), agent_bridge_no_closeout_compact
        agent_bridge_controller_trace = dict(agent_bridge_no_closeout_controller_trace)
        agent_bridge_controller_trace.update(
            {
                "remote_command_file_bridge_agent_loopx_state_write_count": 3,
                "remote_command_file_bridge_agent_loopx_subcommand_counts": {
                    "quota should-run": 2,
                    "todo claim": 1,
                    "todo complete": 1,
                    "refresh-state": 1,
                    "quota spend-slot": 1,
                },
            }
        )
        agent_bridge_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=agent_bridge_controller_trace,
            )
        )
        assert agent_bridge_compact is not None
        agent_bridge_contract = agent_bridge_compact[
            "product_mode_lifecycle_contract"
        ]
        assert agent_bridge_contract["satisfied"] is True, agent_bridge_compact
        assert agent_bridge_contract["countable_treatment"] is True, (
            agent_bridge_compact
        )
        assert agent_bridge_contract["state_read_count"] == 2, agent_bridge_compact
        assert agent_bridge_contract["state_write_count"] == 3, agent_bridge_compact
        assert agent_bridge_contract["closeout_required"] is True
        assert agent_bridge_contract["closeout_satisfied"] is True
        assert agent_bridge_contract["agent_bridge_todo_closeout_count"] == 1
        assert agent_bridge_contract["agent_bridge_refresh_state_count"] == 1
        assert agent_bridge_contract["agent_bridge_quota_spend_slot_count"] == 1
        assert agent_bridge_contract["agent_operation_trace_required"] is True
        assert agent_bridge_contract["agent_operation_trace_satisfied"] is True
        assert agent_bridge_contract.get("missing_reason", "") == "", (
            agent_bridge_contract
        )
        agent_bridge_counters = agent_bridge_compact["interaction_counters"]
        assert (
            agent_bridge_counters[
                "remote_command_file_bridge_agent_operation_trace_required"
            ]
            is True
        )
        assert (
            agent_bridge_counters[
                "remote_command_file_bridge_agent_operation_trace_satisfied"
            ]
            is True
        )
        assert (
            agent_bridge_counters[
                "remote_command_file_bridge_agent_operation_trace_status"
            ]
            == "agent_operation_trace_recorded"
        )
        assert (
            agent_bridge_counters.get(
                "product_mode_lifecycle_checkpoint_missing_reason", ""
            )
            == ""
        )
        assert (
            agent_bridge_counters["product_mode_no_tool_call_lifecycle_abort"]
            is False
        )
        assert (
            agent_bridge_counters["product_mode_no_tool_call_lifecycle_abort_count"]
            == 0
        )
        assert agent_bridge_counters[
            "remote_command_file_bridge_agent_todo_closeout_count"
        ] == 1
        assert (
            agent_bridge_counters[
                "remote_command_file_bridge_agent_refresh_state_count"
            ]
            == 1
        )
        assert (
            agent_bridge_counters[
                "remote_command_file_bridge_agent_quota_spend_slot_count"
            ]
            == 1
        )
        assert "skillsbench_product_mode_lifecycle_missing" not in (
            agent_bridge_compact["failure_attribution_labels"]
        ), agent_bridge_compact


def test_skillsbench_product_mode_recompact_normalizes_agent_bridge_closeout() -> None:
    compact = compact_benchmark_run(
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "official_skillsbench_benchflow_result",
            "benchmark_id": "skillsbench",
            "case_id": "sample-task",
            "case_ids": ["sample-task"],
            "mode": "single",
            "route": "loopx-product-mode",
            "official_score": 0.0,
            "score_failure_attribution": "skillsbench_product_mode_lifecycle_missing",
            "failure_attribution_labels": [
                "official_verifier_solution_failure",
                "skillsbench_product_mode_lifecycle_missing",
                "skillsbench_product_mode_uncountable_treatment",
                "skillsbench_case_local_loopx_state_not_observed",
            ],
            "interaction_counters": {
                "schema_version": "skillsbench_interaction_counters_v0",
                "product_mode": True,
                "product_mode_solver_activity_gap": True,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": True,
                "remote_command_file_bridge_agent_request_count": 11,
                "remote_command_file_bridge_agent_loopx_state_read_count": 3,
                "remote_command_file_bridge_agent_loopx_state_write_count": 4,
                "remote_command_file_bridge_agent_todo_closeout_count": 1,
                "remote_command_file_bridge_agent_refresh_state_count": 1,
                "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
                "remote_command_file_bridge_agent_task_facing_operation_count": 4,
            "remote_command_file_bridge_agent_task_facing_success_count": 4,
            },
            "product_mode_lifecycle_contract": {
                "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
                "required": True,
                "satisfied": False,
                "countable_treatment": False,
                "state_read_count": 3,
                "state_write_count": 4,
                "checkpoint_required": True,
                "checkpoint_count": 4,
                "closeout_required": True,
                "closeout_satisfied": True,
                "agent_operation_trace_required": True,
                "agent_operation_trace_satisfied": True,
                "agent_operation_trace_missing": False,
                "agent_bridge_state_read_count": 3,
                "agent_bridge_state_write_count": 4,
                "agent_bridge_todo_closeout_count": 1,
                "agent_bridge_refresh_state_count": 1,
                "agent_bridge_quota_spend_slot_count": 1,
                "missing_reason": "missing_case_local_loopx_closeout",
            },
        }
    )
    assert compact is not None
    contract = compact["product_mode_lifecycle_contract"]
    assert contract["satisfied"] is True, compact
    assert contract["countable_treatment"] is True, compact
    assert contract["closeout_satisfied"] is True, compact
    assert contract.get("missing_reason", "") == "", compact
    assert compact["score_failure_attribution"] == (
        "official_verifier_solution_failure"
    ), compact
    labels = compact["failure_attribution_labels"]
    assert "official_verifier_solution_failure" in labels, compact
    assert "skillsbench_product_mode_lifecycle_missing" not in labels, compact
    assert "skillsbench_product_mode_uncountable_treatment" not in labels, compact
    solution_quality = compact["solution_quality_signals"]
    assert solution_quality["outcome_class"] == "official_zero", compact
    assert "official_zero_after_public_worker_activity" in solution_quality[
        "solution_action_labels"
    ], compact
    assert solution_quality["rubric_miss_label_status"] == (
        "not_available_from_compact_public_signals"
    ), compact
    assert compact["post_run_debug_gate"]["solution_quality"]["outcome_class"] == (
        "official_zero"
    ), compact


def test_skillsbench_solution_quality_labels_partial_nonpass() -> None:
    compact = compact_benchmark_run(
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "official_skillsbench_benchflow_result",
            "benchmark_id": "skillsbench",
            "case_id": "sample-partial-task",
            "case_ids": ["sample-partial-task"],
            "mode": "single",
            "official_score": 0.5,
            "official_task_score": {
                "kind": "skillsbench_verifier_reward",
                "value": 0.5,
                "passed": False,
            },
            "score_failure_attribution": "official_score_partial_case_failure",
            "failure_attribution_labels": ["partial_trajectory"],
        }
    )
    assert compact is not None
    solution_quality = compact["solution_quality_signals"]
    assert solution_quality["outcome_class"] == "partial_nonpass", compact
    assert "partial_nonpass_official_score" in solution_quality[
        "solution_action_labels"
    ], compact
    assert "partial_trajectory_public_label_present" in solution_quality[
        "solution_action_labels"
    ], compact
    assert solution_quality["rubric_miss_labels"] == [], compact
    assert solution_quality["rubric_miss_label_status"] == (
        "not_available_from_compact_public_signals"
    ), compact
    assert compact["post_run_debug_gate"]["solution_quality"]["outcome_class"] == (
        "partial_nonpass"
    ), compact


def test_skillsbench_agent_bridge_closeout_requires_successful_commands() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-agent-closeout-") as tmp:
        trace_dir = Path(tmp)
        write_json(
            trace_dir / "worker-agent-ops.compact.json",
            {
                "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
                "ok": True,
                "route": "loopx-product-mode",
                "trace_kind": "remote_command_file_bridge_agent_operations",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "sample-task",
                "remote_command_file_bridge_agent_operations": {
                    "schema_version": (
                        "skillsbench_remote_command_file_bridge_agent_operations_v0"
                    ),
                    "request_count": 3,
                    "success_count": 1,
                    "failure_count": 2,
                    "operation_counts": {"exec": 3},
                    "returncode_counts": {"0": 1, "1": 2},
                    "loopx_cli_call_count": 3,
                    "loopx_cli_subcommand_counts": {
                        "todo complete": 1,
                        "refresh-state": 1,
                        "quota spend-slot": 1,
                    },
                    "successful_loopx_cli_subcommand_counts": {
                        "refresh-state": 1,
                    },
                    "loopx_state_read_count": 0,
                    "loopx_state_write_count": 3,
                    "task_facing_operation_count": 0,
                    "raw_material_recorded": False,
                },
                "boundary": {
                    "raw_command_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                },
            },
        )
        plan = {
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {
                "remote_command_file_bridge_agent_operation_trace_required": True,
            },
        }
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        }
        _merge_host_local_acp_relay_trace_summary(plan, trace)
        assert trace["remote_command_file_bridge_agent_request_count"] == 3, trace
        assert trace["remote_command_file_bridge_agent_success_count"] == 1, trace
        assert trace["remote_command_file_bridge_agent_failure_count"] == 2, trace
        assert (
            trace["remote_command_file_bridge_agent_todo_closeout_count"] == 0
        ), trace
        assert trace["remote_command_file_bridge_agent_refresh_state_count"] == 1, trace
        assert (
            trace["remote_command_file_bridge_agent_quota_spend_slot_count"] == 0
        ), trace

        compact = {
            "interaction_counters": {},
            "product_mode_lifecycle_contract": {
                "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
                "required": True,
                "state_read_count": 1,
                "state_write_count": 1,
                "agent_operation_trace_required": True,
                "agent_operation_trace_satisfied": True,
            },
        }
        _sync_relay_closeout_counts_into_compact(
            compact,
            plan["runner_prerequisites"],
        )
        contract = compact["product_mode_lifecycle_contract"]
        assert contract["agent_bridge_todo_closeout_count"] == 0, compact
        assert contract["agent_bridge_refresh_state_count"] == 1, compact
        assert contract["agent_bridge_quota_spend_slot_count"] == 0, compact
        assert contract.get("closeout_satisfied") is not True, compact


def test_skillsbench_goal_start_repeated_selected_todo_complete_is_diagnosed() -> None:
    selected_todo_id = BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID
    command_records = [
        {
            "subcommand": "todo claim",
            "todo_id": selected_todo_id,
            "goal_id": "skillsbench-case",
        },
        {
            "subcommand": "todo update",
            "todo_id": selected_todo_id,
            "goal_id": "skillsbench-case",
        },
    ]
    command_records.extend(
        {
            "subcommand": "todo complete",
            "todo_id": selected_todo_id,
            "goal_id": "skillsbench-case",
        }
        for _ in range(7)
    )
    command_records.extend({"subcommand": "refresh-state"} for _ in range(7))
    with tempfile.TemporaryDirectory(prefix="skillsbench-repeat-complete-") as tmp:
        trace_dir = Path(tmp)
        write_json(
            trace_dir / "worker-agent-ops.compact.json",
            {
                "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
                "ok": True,
                "route": "loopx-goal-start-product-mode",
                "trace_kind": "remote_command_file_bridge_agent_operations",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "paratransit-routing",
                "remote_command_file_bridge_agent_operations": {
                    "schema_version": (
                        "skillsbench_remote_command_file_bridge_agent_operations_v0"
                    ),
                    "request_count": len(command_records),
                    "success_count": len(command_records),
                    "failure_count": 0,
                    "operation_counts": {"exec": len(command_records)},
                    "returncode_counts": {"0": len(command_records)},
                    "loopx_cli_call_count": len(command_records),
                    "loopx_cli_subcommand_counts": {
                        "todo claim": 1,
                        "todo update": 1,
                        "todo complete": 7,
                        "refresh-state": 7,
                    },
                    "successful_loopx_cli_subcommand_counts": {
                        "todo claim": 1,
                        "todo update": 1,
                        "todo complete": 7,
                        "refresh-state": 7,
                    },
                    "successful_loopx_cli_command_records": command_records,
                    "loopx_state_read_count": 0,
                    "loopx_state_write_count": len(command_records),
                    "task_facing_operation_count": 0,
                    "raw_material_recorded": False,
                },
                "boundary": {
                    "raw_command_recorded": False,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                },
            },
        )
        plan = {
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {
                "goal_start_product_mode": True,
                "goal_start_plan_required": True,
                "goal_start_planned_todo_count_expected": 3,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "planned_todo_ids": list(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS),
                "planned_todo_texts_public_safe": list(
                    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS
                ),
            },
        }
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        }
        _merge_host_local_acp_relay_trace_summary(plan, trace)
        assert (
            trace[
                "remote_command_file_bridge_agent_successful_loopx_command_records"
            ][2]["todo_id"]
            == selected_todo_id
        ), trace

        compact = {
            "interaction_counters": {
                **trace,
                "goal_start_product_mode": True,
                "goal_start_plan_observed": True,
                "planner_before_todo_write": True,
                "same_priority_order_preserved": True,
                "planned_todo_count": 3,
                "planned_p0_count": 1,
                "selected_p0_todo_id": selected_todo_id,
                "planned_todo_ids": list(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS),
                "planned_todo_texts_public_safe": list(
                    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS
                ),
                "non_selected_todos_preserved_open_or_deferred": True,
            }
        }
        control = _build_goal_start_product_mode_control_score(compact, plan)
        assert control["satisfied"] is False, control
        assert control["agent_todo_complete_count"] == 7, control
        assert control["agent_todo_complete_unique_todo_count"] == 1, control
        assert control["selected_todo_complete_count"] == 7, control
        assert control["selected_todo_duplicate_complete_count"] == 6, control
        assert control["non_selected_todo_complete_count"] == 0, control
        assert control["quota_spend_missing_after_repeated_complete"] is True, control
        snapshot = control["goal_start_todo_snapshot"]
        assert len(snapshot["planned_todos"]) == 3, snapshot
        assert snapshot["planned_todos"][0]["status"] == "done_observed", snapshot
        assert snapshot["planned_todos"][1]["status"] == (
            "open_or_deferred_observed"
        ), snapshot
        assert snapshot["completed_todo_ids"] == [selected_todo_id], snapshot

        compact["goal_start_product_mode_control_score"] = control
        timeline = skillsbench_loop._build_case_event_timeline(compact, plan)
        goal_event = next(
            event
            for event in timeline["events"]
            if event["event"] == "ranked_todo_plan_selected_p0_lifecycle"
        )
        assert goal_event["selected_todo_duplicate_complete_count"] == 6, goal_event
        assert (
            goal_event["quota_spend_missing_after_repeated_complete"] is True
        ), goal_event

        recompacted = compact_benchmark_run(
            {
                "schema_version": "benchmark_run_v0",
                "source_runner": "official_skillsbench_benchflow_result",
                "benchmark_id": "skillsbench@1.1",
                "case_id": "paratransit-routing",
                "arm_id": "loopx",
                "goal_start_product_mode_control_score": control,
                "interaction_counters": compact["interaction_counters"],
                "case_event_timeline": timeline,
            }
        )
        recompacted_snapshot = recompacted["goal_start_product_mode_control_score"][
            "goal_start_todo_snapshot"
        ]
        assert recompacted_snapshot["planned_todos"][0]["complete_count"] == 7
        assert (
            recompacted["interaction_counters"][
                "remote_command_file_bridge_agent_successful_loopx_command_records"
            ][2]["todo_id"]
            == selected_todo_id
        )


def test_skillsbench_product_mode_recompact_prefers_corroborated_solver_gap() -> None:
    compact = compact_benchmark_run(
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "official_skillsbench_benchflow_result",
            "benchmark_id": "skillsbench",
            "case_id": "sample-task",
            "case_ids": ["sample-task"],
            "mode": "single",
            "route": "loopx-product-mode",
            "official_score": 0.0,
            "score_failure_attribution": "skillsbench_product_mode_lifecycle_missing",
            "failure_attribution_labels": [
                "official_verifier_solution_failure",
                "skillsbench_product_mode_lifecycle_missing",
            ],
            "interaction_counters": {
                "schema_version": "skillsbench_interaction_counters_v0",
                "product_mode": True,
                "product_mode_solver_activity_gap": True,
                "product_mode_solver_activity_gap_count": 1,
                "product_mode_solver_activity_gap_round": 1,
                "product_mode_solver_activity_missing_reason": (
                    "missing_task_facing_activity_or_agent_closeout_before_declared_done"
                ),
                "remote_command_file_bridge_agent_task_facing_operation_count": 0,
            "remote_command_file_bridge_agent_task_facing_success_count": 0,
                "remote_command_file_bridge_agent_todo_closeout_count": 0,
            },
            "product_mode_lifecycle_contract": {
                "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
                "required": True,
                "satisfied": True,
                "countable_treatment": True,
            },
        }
    )
    assert compact is not None
    assert compact["score_failure_attribution"] == (
        "skillsbench_product_mode_solver_activity_gap"
    ), compact
    labels = compact["failure_attribution_labels"]
    assert "skillsbench_product_mode_solver_activity_gap" in labels, compact
    assert "skillsbench_product_mode_lifecycle_missing" not in labels, compact
    assert "official_verifier_solution_failure" not in labels, compact


def test_skillsbench_product_mode_solver_activity_gap_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-solver-gap-compact-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 0,
            "product_mode_solver_activity_required": True,
            "product_mode_solver_activity_gap": True,
            "product_mode_solver_activity_gap_count": 1,
            "product_mode_solver_activity_gap_round": 1,
            "product_mode_solver_activity_missing_reason": (
                "missing_task_facing_activity_or_agent_closeout_before_declared_done"
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_request_count": 4,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 1,
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 2,
            "remote_command_file_bridge_agent_loopx_state_read_count": 2,
            "remote_command_file_bridge_agent_loopx_state_write_count": 0,
            "remote_command_file_bridge_agent_task_facing_operation_count": 0,
            "remote_command_file_bridge_agent_task_facing_success_count": 0,
            "last_decision": "send_product_mode_solver_activity_continuation",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode_solver_activity_required"] is True
        assert counters["product_mode_solver_activity_gap"] is True
        assert counters["product_mode_solver_activity_gap_count"] == 1
        assert counters["product_mode_solver_activity_gap_round"] == 1
        assert (
            counters["remote_command_file_bridge_agent_task_facing_operation_count"]
            == 0
        )
        assert counters["product_mode_solver_activity_missing_reason"] == (
            "missing_task_facing_activity_or_agent_closeout_before_declared_done"
        )
        lifecycle_contract = compact["product_mode_lifecycle_contract"]
        assert lifecycle_contract["satisfied"] is True, compact
        assert lifecycle_contract["countable_treatment"] is True, compact
        compact_again = compact_benchmark_run(compact)
        assert compact_again is not None
        compact_counters = compact_again["interaction_counters"]
        assert compact_counters["product_mode_solver_activity_gap"] is True
        assert compact_counters["product_mode_solver_activity_gap_count"] == 1


def test_skillsbench_product_mode_first_action_timeout_is_uncountable() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-first-action-timeout-") as tmp:
        root = Path(tmp)
        run_dir = root / "official" / "2026-06-25__20-49-07" / "sample-task__abc123"
        result_path = run_dir / "result.json"
        write_json(
            result_path,
            {
                "task_name": "sample-task",
                "rollout_name": "sample-task__abc123",
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 1,
                "error": "ACP error -32603: internal error",
                "error_category": "acp_error",
                "verifier_error": None,
                "partial_trajectory": True,
                "trajectory_source": "partial_acp",
                "trajectory_summary": {
                    "steps": 2,
                    "tool_call_steps": 0,
                    "partial_trajectory": True,
                },
            },
        )
        write_json(
            run_dir / "timing.json",
            {
                "environment_setup": 24.4,
                "agent_setup": 0.1,
                "total": 964.8,
            },
        )
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "max_rounds_budget": 32,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "remote_command_file_bridge_consumed_by_solver": True,
            "remote_command_file_bridge_solver_trace_count": 1,
            "remote_command_file_bridge_solver_probe_ready_count": 1,
            "remote_command_file_bridge_solver_operation_count": 4,
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_request_count": 4,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_present": False,
            "remote_command_file_bridge_agent_operation_trace_count": 0,
            "remote_command_file_bridge_agent_request_count": 0,
            "remote_command_file_bridge_agent_task_facing_operation_count": 0,
            "remote_command_file_bridge_agent_task_facing_success_count": 0,
            "host_local_acp_codex_exec_failure_trace_present": True,
            "host_local_acp_codex_exec_failure_trace_count": 1,
            "host_local_acp_codex_exec_failure_category": (
                "codex_exec_first_action_timeout"
            ),
            "host_local_acp_codex_exec_failure_categories": [
                "codex_exec_first_action_timeout"
            ],
            "host_local_acp_codex_exec_failure_raw_material_recorded": False,
            "last_decision": "remote_command_file_bridge_solver_trace_recorded",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        expected_label = (
            "skillsbench_host_local_acp_codex_exec_failed_"
            "codex_exec_first_action_timeout"
        )
        assert compact["score_failure_attribution"] == expected_label, compact
        assert expected_label in compact["failure_attribution_labels"], compact
        assert "skillsbench_product_mode_transport_failure" in (
            compact["failure_attribution_labels"]
        ), compact
        assert compact["official_score_status"] == "missing", compact
        assert compact["official_score_comparable_to_native_codex"] is False
        assert compact["official_score_comparable_to_loopx_treatment"] is False
        accounting = compact["attempt_accounting"]
        assert accounting["case_attempt_countable"] is False, accounting
        assert accounting["solver_attempt_countable"] is False, accounting
        assert accounting["verifier_attempt_countable"] is False, accounting
        assert accounting["official_score_attempt_countable"] is False, accounting
        assert accounting["failure_class"] == "job_materialization_failed", accounting
        counters = compact["interaction_counters"]
        assert counters["host_local_acp_codex_exec_failure_trace_present"] is True
        assert counters["host_local_acp_codex_exec_failure_trace_count"] == 1
        assert counters["host_local_acp_codex_exec_failure_category"] == (
            "codex_exec_first_action_timeout"
        )
        assert (
            counters["host_local_acp_codex_exec_failure_raw_material_recorded"]
            is False
        )
        assert counters["remote_command_file_bridge_agent_request_count"] == 0
        assert (
            counters["remote_command_file_bridge_agent_task_facing_operation_count"]
            == 0
        )
        failure = compact["runner_failure"]
        assert failure["exception_type"] == expected_label, failure
        assert failure["failure_class"] == expected_label, failure
        assert failure["raw_error_recorded"] is False


def test_skillsbench_host_local_idle_timeout_after_closeout_is_countable() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-host-acp-closeout-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        result = json.loads(result_path.read_text())
        result["error"] = "synthetic codex_exec_bridge_idle_timeout"
        write_json(result_path, result)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "reward_observation_count": 13,
            "round_rewards": [
                {"agent_round": 13, "reward_present": True, "reward": 0.0}
            ],
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "declared_done_round": 13,
            "product_mode_solver_activity_gap": True,
            "product_mode_solver_activity_gap_count": 1,
            "product_mode_solver_activity_gap_round": 7,
            "product_mode_solver_activity_missing_reason": (
                "missing_task_facing_activity_or_agent_closeout_before_declared_done"
            ),
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": 14,
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 14,
            "remote_command_file_bridge_driver_lifecycle_request_count": 56,
            "remote_command_file_bridge_driver_lifecycle_success_count": 56,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 56,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 14,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 42,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 14,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 47,
            "remote_command_file_bridge_agent_task_facing_operation_count": 34,
            "remote_command_file_bridge_agent_task_facing_success_count": 34,
            "remote_command_file_bridge_agent_loopx_state_read_count": 7,
            "remote_command_file_bridge_agent_loopx_state_write_count": 5,
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 2,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
            "host_local_acp_codex_exec_failure_trace_present": True,
            "host_local_acp_codex_exec_failure_trace_count": 1,
            "host_local_acp_codex_exec_failure_category": (
                "codex_exec_bridge_idle_timeout"
            ),
            "host_local_acp_codex_exec_failure_categories": [
                "codex_exec_bridge_idle_timeout"
            ],
            "host_local_acp_codex_exec_failure_raw_material_recorded": False,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["official_score"] == 0.0, compact
        assert compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), compact
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_product_mode_solver_activity_gap" not in labels, compact
        assert "skillsbench_runner_setup_error" not in labels, compact
        warnings = compact["runner_warning_labels"]
        assert (
            "skillsbench_host_local_acp_idle_timeout_after_countable_closeout"
            in warnings
        ), compact
        accounting = compact["attempt_accounting"]
        assert accounting["case_attempt_countable"] is True, accounting
        assert accounting["solver_attempt_countable"] is True, accounting
        assert accounting["verifier_attempt_countable"] is True, accounting
        assert accounting["official_score_attempt_countable"] is True, accounting
        assert accounting["failure_class"] == "solver_failed", accounting


def test_skillsbench_host_local_idle_no_output_progress_is_distinct() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-host-acp-idle-progress-") as tmp:
        root = Path(tmp)
        run_dir = root / "official" / "2026-06-15__00-00-00" / "sample-task__abc123"
        result_path = run_dir / "result.json"
        write_json(
            result_path,
            {
                "task_name": "sample-task",
                "rollout_name": "sample-task__abc123",
                "rewards": None,
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 2,
                "error": "ACP error -32002: local codex execution timeout",
                "verifier_error": None,
                "partial_trajectory": True,
                "trajectory_source": "partial_acp",
                "trajectory_summary": {
                    "steps": 2,
                    "round_count": 2,
                    "tool_call_count": 0,
                    "partial_trajectory": True,
                },
            },
        )
        write_json(
            run_dir / "timing.json",
            {
                "environment_setup": 2.0,
                "agent_setup": 1.0,
                "agent_execution": 30.0,
                "total": 33.0,
            },
        )
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "max_rounds_budget": 16,
            "initial_prompt_count": 1,
            "followup_prompt_count": 2,
            "stop_decision_count": 1,
            "controller_action_decisions": 3,
            "reward_observation_count": 2,
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": 2,
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 2,
            "remote_command_file_bridge_driver_lifecycle_request_count": 8,
            "remote_command_file_bridge_driver_lifecycle_success_count": 8,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 8,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 2,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 2,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 2,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 5,
            "remote_command_file_bridge_agent_task_facing_operation_count": 5,
            "remote_command_file_bridge_agent_task_facing_success_count": 5,
            "host_local_acp_bridge_progress_status": (
                "bridge_task_facing_success_observed"
            ),
            "host_local_acp_bridge_progress_signal_source": (
                "remote_command_file_bridge_agent_operations"
            ),
            "host_local_acp_codex_exec_failure_trace_present": True,
            "host_local_acp_codex_exec_failure_trace_count": 2,
            "host_local_acp_codex_exec_failure_category": (
                "codex_exec_bridge_idle_timeout"
            ),
            "host_local_acp_codex_exec_failure_categories": [
                "codex_exec_bridge_idle_timeout"
            ],
            "host_local_acp_codex_exec_failure_raw_material_recorded": False,
            "product_mode_host_local_idle_no_task_output_progress": True,
            "product_mode_host_local_idle_no_task_output_progress_stop": True,
            "product_mode_host_local_idle_no_task_output_progress_streak": 2,
            "product_mode_host_local_idle_no_task_output_progress_streak_threshold": 2,
            "product_mode_host_local_idle_no_task_output_progress_round": 4,
            "product_mode_host_local_idle_no_task_output_progress_stop_round": 4,
            "product_mode_host_local_idle_no_task_output_progress_stop_count": 1,
            "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls": 0,
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops": 5,
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes": 5,
            "product_mode_host_local_idle_no_task_output_progress_score_status": (
                "missing"
            ),
            "product_mode_host_local_idle_no_task_output_progress_category": (
                "codex_exec_bridge_idle_timeout"
            ),
            "product_mode_host_local_idle_no_task_output_progress_policy": (
                "stop_after_two_host_local_idle_rounds_without_task_output_or_closeout"
            ),
            "last_decision": (
                "stop_after_product_mode_host_local_idle_no_task_output_progress"
            ),
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        expected = "skillsbench_host_local_acp_idle_no_task_output_progress"
        assert compact["score_failure_attribution"] == expected, compact
        labels = compact["failure_attribution_labels"]
        assert expected in labels, compact
        assert "skillsbench_product_mode_transport_failure" in labels, compact
        assert "skillsbench_runner_setup_error" not in labels, compact
        assert "skillsbench_acp_agent_message_only_no_tool_calls" not in labels, compact
        assert "official_score_zero_case_failure" not in labels, compact
        accounting = compact["attempt_accounting"]
        assert accounting["failure_class"] == "official_score_failed", accounting

        counters = compact["interaction_counters"]
        assert counters["private_trajectory_tool_call_count"] == 0, counters
        assert counters["remote_command_file_bridge_agent_request_count"] == 5, counters
        assert (
            counters["remote_command_file_bridge_agent_task_facing_operation_count"]
            == 5
        ), counters
        assert counters["host_local_acp_bridge_progress_status"] == (
            "bridge_task_facing_success_observed"
        ), counters
        assert (
            counters["product_mode_host_local_idle_no_task_output_progress_stop"]
            is True
        ), counters

        timeline = skillsbench_loop._build_case_event_timeline(
            compact,
            {"runner_prerequisites": {}},
        )
        compact["case_event_timeline"] = timeline
        gate = build_skillsbench_post_run_debug_gate(compact)
        assert gate["todo_flow"]["task_facing_activity_status"] == (
            "task_activity_observed"
        ), gate
        assert gate["todo_flow"]["host_local_acp_bridge_progress_status"] == (
            "bridge_task_facing_success_observed"
        ), gate
        assert gate["todo_flow"]["acp_protocol_tool_call_count"] == 0, gate
        assert gate["todo_flow"]["agent_bridge_task_facing_operation_count"] == 5, gate
        assert gate["controller"]["status"] == (
            "host_local_idle_no_task_output_progress_stop"
        ), gate


def test_product_mode_host_local_idle_no_output_progress_requires_new_trace() -> None:
    trace: dict[str, Any] = {
        "host_local_acp_codex_exec_failure_category": (
            "codex_exec_bridge_idle_timeout"
        ),
        "host_local_acp_codex_exec_failure_trace_count": 1,
        "remote_command_file_bridge_agent_request_count": 2,
        "remote_command_file_bridge_agent_task_facing_operation_count": 2,
        "remote_command_file_bridge_agent_task_facing_success_count": 2,
    }
    round_result = types.SimpleNamespace(n_tool_calls=0)

    assert skillsbench_loop._product_mode_host_local_idle_no_task_output_progress_applicable(
        trace,
        round_result,
        reward=None,
    )
    stopped = skillsbench_loop._record_product_mode_host_local_idle_no_task_output_progress(
        trace,
        agent_round=2,
        reward=None,
        round_result=round_result,
    )
    assert stopped is False, trace
    assert (
        trace["product_mode_host_local_idle_no_task_output_progress_streak"] == 1
    ), trace
    assert not skillsbench_loop._product_mode_host_local_idle_no_task_output_progress_applicable(
        trace,
        round_result,
        reward=None,
    )

    trace["host_local_acp_codex_exec_failure_trace_count"] = 2
    assert skillsbench_loop._product_mode_host_local_idle_no_task_output_progress_applicable(
        trace,
        round_result,
        reward=0.0,
    )
    stopped = skillsbench_loop._record_product_mode_host_local_idle_no_task_output_progress(
        trace,
        agent_round=3,
        reward=0.0,
        round_result=round_result,
    )
    assert stopped is True, trace
    assert trace["product_mode_host_local_idle_no_task_output_progress_stop"] is True
    assert (
        trace["product_mode_host_local_idle_no_task_output_progress_streak"] == 2
    ), trace
    assert trace["product_mode_host_local_idle_no_task_output_progress_policy"] == (
        "stop_after_two_host_local_idle_rounds_without_task_output_or_closeout"
    )


def test_goal_start_host_local_defers_codex_exec_preflight_until_bridge_command() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-goal-start-preflight-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "loopx-goal-start-product-mode",
                "--host-local-acp-launch",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-goal-start-preflight-fixture",
            ]
        )
        plan = build_plan(args)
        prereqs = plan["runner_prerequisites"]
        assert (
            prereqs["host_local_acp_codex_exec_preflight_requested"] is False
        ), prereqs
        assert prereqs["host_local_acp_codex_exec_preflight_status"] == "not_requested", (
            prereqs
        )
        args_with_bridge = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "loopx-goal-start-product-mode",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--remote-command-file-bridge-solver-command",
                "/tmp/loopx-skillsbench-docker-bridge",
                "--jobs-dir",
                str(Path(tmp) / "jobs-with-bridge"),
                "--job-name",
                "skillsbench-goal-start-preflight-bridge-fixture",
            ]
        )
        bridge_plan = build_plan(args_with_bridge)
        bridge_prereqs = bridge_plan["runner_prerequisites"]
        assert (
            bridge_prereqs["host_local_acp_codex_exec_preflight_requested"] is True
        ), bridge_prereqs
        assert bridge_prereqs["host_local_acp_codex_exec_preflight_status"] == "pending", (
            bridge_prereqs
        )


def test_app_server_goal_worker_skips_plain_codex_exec_preflight() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-server-preflight-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "3d-scan-calc",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--host-local-acp-launch",
                "--host-local-acp-codex-exec-preflight",
                "--remote-command-file-bridge-ready",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-app-server-preflight-fixture",
            ]
        )
        plan = build_plan(args)
        prereqs = plan["runner_prerequisites"]
        assert prereqs["host_local_acp_codex_exec_preflight_requested"] is False, (
            prereqs
        )
        assert prereqs["host_local_acp_codex_exec_preflight_status"] == "not_requested", (
            prereqs
        )
        assert prereqs["codex_acp_runtime_launch_preflight_stage"] == (
            "not_applicable_app_server_goal_worker"
        ), prereqs


def test_codex_cli_goal_worker_skips_plain_codex_exec_preflight() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-goal-preflight-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "3d-scan-calc",
                "--route",
                "codex-cli-goal-baseline",
                "--host-local-acp-launch",
                "--host-local-acp-codex-exec-preflight",
                "--remote-command-file-bridge-ready",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-cli-goal-preflight-fixture",
            ]
        )
        plan = build_plan(args)
        prereqs = plan["runner_prerequisites"]
        assert prereqs["host_local_acp_codex_exec_preflight_requested"] is False, (
            prereqs
        )
        assert prereqs["host_local_acp_codex_exec_preflight_status"] == "not_requested", (
            prereqs
        )
        assert prereqs["container_codex_acp_install_skipped"] is True, prereqs


def test_codex_cli_goal_official_score_without_task_activity_is_uncountable() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-goal-countability-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        args = parse_args(
            [
                "--task-id",
                "azure-bgp-oscillation-route-leak",
                "--route",
                "codex-cli-goal-baseline",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--remote-command-file-bridge-solver-command",
                "/tmp/loopx-skillsbench-docker-bridge",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "skillsbench-cli-goal-countability-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_present_no_requests"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 0,
                "remote_command_file_bridge_agent_task_facing_operation_count": 0,
                "remote_command_file_bridge_agent_task_facing_success_count": 0,
                "codex_cli_goal_tui_trace_present": True,
                "codex_cli_goal_tui_ok_count": 1,
                "codex_cli_goal_tui_stage": "goal_achieved",
                "codex_cli_goal_tui_task_facing_success_count": 0,
                "codex_cli_goal_tui_raw_material_recorded": False,
            }
        )

        compact = reduce_result(args, result_path, plan)

        expected = "skillsbench_codex_cli_goal_uncountable_no_task_activity"
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 0.0, compact
        assert compact["score_failure_attribution"] == expected, compact
        assert compact["first_blocker"] == expected, compact
        assert "official_verifier_solution_failure" not in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_codex_cli_goal_uncountable_baseline" in compact[
            "failure_attribution_labels"
        ], compact
        contract = compact["codex_cli_goal_countability_contract"]
        assert contract["countable_baseline"] is False, contract
        assert contract["ok_count"] == 1, contract
        assert contract["request_count"] == 0, contract
        assert contract["task_facing_activity_count"] == 0, contract
        assert contract["raw_material_recorded"] is False, contract
        accounting = compact["attempt_accounting"]
        assert accounting["failure_class"] == "job_materialization_failed", accounting
        assert accounting["failure_label"] == expected, accounting
        assert accounting["case_attempt_countable"] is False, accounting
        assert accounting["solver_attempt_countable"] is False, accounting
        assert accounting["verifier_attempt_countable"] is False, accounting
        assert accounting["official_score_attempt_countable"] is False, accounting


def test_app_server_goal_first_action_timeout_respects_agent_idle_timeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-server-timeout-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "energy-ac-optimal-power-flow",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--host-local-acp-launch",
                "--agent-idle-timeout",
                "900",
                "--outer-timeout-sec",
                "3600",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-app-server-timeout-fixture",
            ]
        )
        assert _effective_local_codex_first_action_timeout_sec(args) == 900
        command = _host_local_acp_launch_command(args, build_plan(args))
        assert int(command[command.index("--timeout-sec") + 1]) >= 3600
        assert command[command.index("--first-action-timeout-sec") + 1] == "900"

        explicit_args = parse_args(
            [
                "--task-id",
                "energy-ac-optimal-power-flow",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--host-local-acp-launch",
                "--agent-idle-timeout",
                "900",
                "--local-codex-first-action-timeout-sec",
                "1200",
                "--jobs-dir",
                str(Path(tmp) / "explicit-jobs"),
                "--job-name",
                "skillsbench-app-server-explicit-timeout-fixture",
            ]
        )
        assert _effective_local_codex_first_action_timeout_sec(explicit_args) == 1200
        explicit_command = _host_local_acp_launch_command(
            explicit_args,
            build_plan(explicit_args),
        )
        assert (
            explicit_command[explicit_command.index("--first-action-timeout-sec") + 1]
            == "1200"
        )


def test_goal_start_host_exec_failure_overrides_zero_score_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-goal-start-host-failure-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "loopx-goal-start-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-goal-start-host-failure-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "agent_execution_mode": "host_local_acp",
                "host_local_acp_codex_exec_failure_trace_present": True,
                "host_local_acp_codex_exec_failure_trace_count": 1,
                "host_local_acp_codex_exec_failure_category": (
                    "codex_exec_bridge_idle_timeout"
                ),
            }
        )
        result_path = Path(plan["result_json"])
        write_json(
            result_path,
            {
                "task_name": "citation-check",
                "rollout_name": "citation-check__loopx_goal_start_product_mode",
                "rewards": None,
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 13,
                "error": "ACP error -32002: local codex execution timeout",
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        verifier_dir = result_path.with_name("verifier")
        verifier_dir.mkdir(parents=True, exist_ok=True)
        (verifier_dir / "reward.txt").write_text("0.0\n", encoding="utf-8")
        compact = reduce_result(args, result_path, plan)
        expected = (
            "skillsbench_host_local_acp_codex_exec_failed_"
            "codex_exec_bridge_idle_timeout"
        )
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 0.0, compact
        assert compact["score_failure_attribution"] == expected, compact
        assert compact["runner_failure"]["failure_class"] == expected, compact
        assert "official_score_zero_case_failure" not in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_product_mode_transport_failure" in compact[
            "failure_attribution_labels"
        ], compact
        accounting = compact["attempt_accounting"]
        assert accounting["failure_class"] == "job_materialization_failed", accounting
        assert accounting["failure_label"] == expected, accounting
        assert accounting["case_attempt_countable"] is False, accounting
        assert accounting["solver_attempt_countable"] is False, accounting
        assert accounting["verifier_attempt_countable"] is False, accounting
        assert accounting["official_score_attempt_countable"] is False, accounting


def test_skillsbench_product_mode_declared_done_below_passing_reward_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-declared-done-low-score-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "round_rewards": [
                {"agent_round": 1, "reward_present": True, "reward": 0.0},
                {"agent_round": 2, "reward_present": True, "reward": 0.0},
            ],
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "declared_done_round": 2,
            "declared_done_score": 0.0,
            "product_mode_declared_done_below_passing_reward": True,
            "product_mode_declared_done_below_passing_reward_count": 2,
            "product_mode_declared_done_below_passing_reward_round": 2,
            "product_mode_declared_done_below_passing_reward_score": 0.0,
            "product_mode_declared_done_below_passing_reward_score_status": (
                "observed_below_passing"
            ),
            "open_todo_count": 0,
            "product_mode_no_open_todo_below_passing_reward_stop": True,
            "product_mode_no_open_todo_below_passing_reward_streak": 2,
            "product_mode_no_open_todo_below_passing_reward_streak_threshold": 2,
            "product_mode_no_open_todo_below_passing_reward_round": 2,
            "product_mode_no_open_todo_below_passing_reward_stop_count": 1,
            "product_mode_no_open_todo_below_passing_reward_stop_round": 2,
            "product_mode_no_open_todo_below_passing_reward_open_todo_count_public": 0,
            "product_mode_no_open_todo_below_passing_reward_score": 0.0,
            "product_mode_no_open_todo_below_passing_reward_score_status": (
                "observed_below_passing"
            ),
            "product_mode_declared_done_policy": (
                "stop_after_two_no_open_todo_rounds_without_passing_reward"
            ),
            "last_decision": (
                "stop_after_product_mode_two_no_open_todo_rounds_without_passing_reward"
            ),
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode_declared_done_below_passing_reward"] is True
        assert (
            counters["product_mode_declared_done_below_passing_reward_count"] == 2
        )
        assert (
            counters["product_mode_declared_done_below_passing_reward_round"] == 2
        )
        assert (
            counters["product_mode_declared_done_below_passing_reward_score"] == 0.0
        )
        assert (
            counters[
                "product_mode_declared_done_below_passing_reward_score_status"
            ]
            == "observed_below_passing"
        )
        assert counters["product_mode_declared_done_policy"] == (
            "stop_after_two_no_open_todo_rounds_without_passing_reward"
        )
        assert (
            counters["product_mode_no_open_todo_below_passing_reward_stop"] is True
        )
        assert counters["product_mode_no_open_todo_below_passing_reward_streak"] == 2
        assert (
            counters[
                "product_mode_no_open_todo_below_passing_reward_streak_threshold"
            ]
            == 2
        )
        assert (
            counters[
                "product_mode_no_open_todo_below_passing_reward_open_todo_count_public"
            ]
            == 0
        )
        assert (
            counters["product_mode_no_open_todo_below_passing_reward_score"] == 0.0
        )
        round_trace = compact["round_reward_trace"]
        assert (
            round_trace["product_mode_no_open_todo_below_passing_reward_stop"]
            is True
        ), round_trace
        assert (
            round_trace["product_mode_no_open_todo_below_passing_reward_streak"] == 2
        ), round_trace
        post_run_gate = compact["post_run_debug_gate"]
        assert (
            post_run_gate["todo_flow"]["no_open_todo_below_passing_reward_stop"]
            is True
        ), post_run_gate
        assert (
            post_run_gate["todo_flow"]["no_open_todo_below_passing_reward_streak"]
            == 2
        ), post_run_gate
        labels = compact["failure_attribution_labels"]
        assert (
            "skillsbench_product_mode_declared_done_below_passing_reward" in labels
        )
        assert "skillsbench_agent_premature_done_signal" in labels
        assert (
            "skillsbench_product_mode_no_open_todo_below_passing_reward_stop"
            in labels
        )
        assert "skillsbench_solver_exhausted_no_open_todos" in labels


def test_skillsbench_declared_done_missing_reward_status_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-declared-done-missing-reward-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "reward_observation_count": 0,
            "round_rewards": [{"agent_round": 1, "tool_calls": 0}],
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "declared_done_round": 1,
            "product_mode_declared_done_below_passing_reward": True,
            "product_mode_declared_done_below_passing_reward_count": 1,
            "product_mode_declared_done_below_passing_reward_round": 1,
            "product_mode_declared_done_below_passing_reward_score_status": (
                "missing"
            ),
            "product_mode_declared_done_policy": (
                "continue_until_official_success_or_budget"
            ),
            "last_decision": (
                "send_product_mode_success_or_budget_continuation_after_declared_done"
            ),
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode_declared_done_below_passing_reward"] is True
        assert (
            "product_mode_declared_done_below_passing_reward_score"
            not in counters
        )
        assert (
            counters[
                "product_mode_declared_done_below_passing_reward_score_status"
            ]
            == "missing"
        )
        assert counters["product_mode_declared_done_policy"] == (
            "continue_until_official_success_or_budget"
        )


def test_skillsbench_product_mode_declared_done_without_closeout_overrides_verifier_error() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-declared-done-no-closeout-") as tmp:
        root = Path(tmp)
        run_dir = root / "official" / "2026-06-24__07-28-16" / "citation-check__abc123"
        result_path = run_dir / "result.json"
        write_json(
            result_path,
            {
                "task_name": "citation-check",
                "rollout_name": "citation-check__abc123",
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 1,
                "error": None,
                "verifier_error": "public verifier error marker",
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(run_dir / "timing.json", {"agent_execution": 5.0, "total": 65.0})
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 1,
            "controller_action_decisions": 1,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 1,
            "reward_observation_count": 0,
            "round_rewards": [{"agent_round": 1, "tool_calls": 0}],
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "declared_done_round": 1,
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_request_count": 4,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 1,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 3,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 1,
            "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
            "remote_command_file_bridge_agent_todo_closeout_count": 0,
            "remote_command_file_bridge_agent_refresh_state_count": 0,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 0,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_product_mode_solver_activity_gap"
        ), compact
        assert compact["attempt_accounting"]["failure_class"] == "solver_failed", compact
        counters = compact["interaction_counters"]
        assert counters["product_mode_solver_activity_gap"] is True, compact
        assert counters["product_mode_solver_activity_gap_count"] == 1, compact
        assert counters["product_mode_solver_activity_gap_round"] == 1, compact
        assert counters["product_mode_solver_activity_missing_reason"] == (
            "missing_task_facing_activity_or_agent_closeout_before_declared_done"
        )
        lifecycle_contract = compact["product_mode_lifecycle_contract"]
        assert lifecycle_contract["satisfied"] is True, compact
        assert lifecycle_contract["countable_treatment"] is True, compact
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_product_mode_solver_activity_gap" in labels, compact
        assert "skillsbench_agent_behavior_gap" in labels, compact
        assert "skillsbench_reward_artifact_missing" in labels, compact
        assert "skillsbench_verifier_error_subtype_unavailable_public" in labels, compact


def test_skillsbench_product_mode_solver_activity_gap_overrides_zero_score() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-solver-gap-zero-score-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "reward_observation_count": 1,
            "round_rewards": [
                {"agent_round": 1, "reward_present": True, "reward": 0.0}
            ],
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "declared_done_round": 1,
            "product_mode_solver_activity_gap": True,
            "product_mode_solver_activity_gap_count": 1,
            "product_mode_solver_activity_gap_round": 1,
            "product_mode_solver_activity_missing_reason": (
                "missing_task_facing_activity_or_agent_closeout_before_declared_done"
            ),
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 1,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_task_facing_operation_count": 0,
            "remote_command_file_bridge_agent_task_facing_success_count": 0,
            "remote_command_file_bridge_agent_todo_closeout_count": 0,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["official_score"] == 0.0, compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_product_mode_solver_activity_gap"
        ), compact
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_product_mode_solver_activity_gap" in labels, compact
        assert "skillsbench_agent_behavior_gap" in labels, compact
        assert "official_verifier_solution_failure" not in labels, compact
        assert "skillsbench_reward_artifact_missing" not in labels, compact


def test_skillsbench_product_mode_no_tool_lifecycle_abort_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-tool-compact-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 1,
            "product_mode_lifecycle_checkpoint_required": True,
            "product_mode_lifecycle_checkpoint_count": 1,
            "product_mode_lifecycle_checkpoint_round": 1,
            "product_mode_lifecycle_checkpoint_missing_reason": (
                "missing_case_local_loopx_state_read_or_write"
            ),
            "product_mode_no_tool_call_lifecycle_abort": True,
            "product_mode_no_tool_call_lifecycle_abort_count": 1,
            "product_mode_no_tool_call_lifecycle_abort_round": 1,
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "last_decision": "stop_after_product_mode_no_tool_calls_without_lifecycle",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode_no_tool_call_lifecycle_abort"] is True
        assert counters["product_mode_no_tool_call_lifecycle_abort_count"] == 1
        assert counters["product_mode_no_tool_call_lifecycle_abort_round"] == 1
        assert counters["controller_stop_decision_count"] == 1
        assert counters["controller_followup_prompt_count"] == 0
        assert (
            counters["last_decision"]
            == "stop_after_product_mode_no_tool_calls_without_lifecycle"
        )


def test_skillsbench_product_mode_case_state_usage_is_compacted() -> None:
    assert PRODUCT_MODE_CASE_STATE_PATH == (
        "/app/.codex/goals/skillsbench-case/ACTIVE_GOAL_STATE.md"
    )
    with tempfile.TemporaryDirectory(prefix="skillsbench-case-state-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_case_state_fixture"
        rollout_name = "case__loopx_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        events = [
            {
                "type": "user_message",
                "text": (
                    "LoopX product-mode treatment. Maintain "
                    f"{PRODUCT_MODE_CASE_STATE_PATH}."
                ),
            },
            {
                "type": "tool_call",
                "title": f"cat {PRODUCT_MODE_CASE_STATE_PATH}",
                "status": "success",
            },
            {
                "type": "tool_call",
                "title": (
                    "python - <<'PY'\n"
                    "from pathlib import Path\n"
                    f"Path('{PRODUCT_MODE_CASE_STATE_PATH}').write_text('ok')\n"
                    "PY"
                ),
                "status": "success",
            },
        ]
        with trajectory_path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["loopx_case_state_path_count"] == 1, summary
        assert summary["loopx_case_state_paths"] == [
            PRODUCT_MODE_CASE_STATE_PATH
        ], summary
        assert summary["loopx_case_state_read_count"] == 1, summary
        assert summary["loopx_case_state_write_count"] == 1, summary

        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
        }
        _merge_acp_trajectory_summary(
            {
                "jobs_dir": str(jobs_dir),
                "job_name": job_name,
                "rollout_name": rollout_name,
            },
            trace,
        )
        assert trace["loopx_case_state_reads"] == 1, trace
        assert trace["loopx_case_state_writes"] == 1, trace
        assert trace["loopx_state_reads"] == 1, trace
        assert trace["loopx_state_writes"] == 1, trace
        assert _product_mode_depth_gate_satisfied(trace) is True, trace
        cli_only_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-product-mode",
            "loopx_state_reads": 3,
            "loopx_state_writes": 2,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
        }
        assert _product_mode_depth_gate_satisfied(cli_only_trace) is True, cli_only_trace


def test_skillsbench_product_mode_legacy_case_state_path_is_not_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-legacy-case-state-") as tmp:
        root = Path(tmp)
        trajectory_path = root / "acp_trajectory.jsonl"
        legacy_path = "/app/.loopx-case-state.md"
        events = [
            {
                "type": "tool_call",
                "title": f"cat {legacy_path}",
                "status": "success",
            },
            {
                "type": "tool_call",
                "title": (
                    "python - <<'PY'\n"
                    "from pathlib import Path\n"
                    f"Path('{legacy_path}').write_text('ok')\n"
                    "PY"
                ),
                "status": "success",
            },
        ]
        with trajectory_path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["loopx_case_state_path_count"] == 0, summary
        assert summary["loopx_case_state_paths"] == [], summary
        assert summary["loopx_case_state_read_count"] == 0, summary
        assert summary["loopx_case_state_write_count"] == 0, summary


def test_skillsbench_acp_trajectory_summary_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-trace-summary-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "debug-trl-grpo-trace-summary"
        rollout_name = "debug-trl-grpo__loopx_blind_loop"
        run_dir = jobs_dir / job_name / rollout_name
        trajectory_path = run_dir / "agent" / "acp_trajectory.jsonl"
        trajectory_path.parent.mkdir(parents=True)
        events = [
            {
                "type": "user_message",
                "text": (
                    "Round 1. Do not modify /app/train_grpo.py or "
                    "/app/reward_fn.py. Inspect /app/trl instead."
                ),
            },
            {
                "type": "tool_call",
                "title": "loopx status",
                "status": "completed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "/app/.local/bin/loopx --registry /app/.loopx/registry.json "
                    "--runtime-root /app/.loopx/runtime --format json todo update "
                    "--goal-id demo --todo-id todo_demo --status open"
                ),
                "status": "failed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "/app/.local/bin/loopx --registry /app/.loopx/registry.json "
                    "--runtime-root /app/.loopx/runtime --format json quota spend-slot "
                    "--goal-id demo --agent-id codex-benchmark-agent --execute"
                ),
                "status": "completed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "perl -0pi -e 's/config=config,/args=config,/' "
                    "/app/train_grpo.py"
                ),
                "status": "completed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "python -m py_compile /app/train_grpo.py "
                    "/app/reward_fn.py /app/trl/trl/trainer/grpo_trainer.py"
                ),
                "status": "completed",
                "content": [],
            },
            {"type": "agent_message", "text": "Finished local validation."},
        ]
        trajectory_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        (run_dir / "agent" / "codex_acp.txt").write_text("", encoding="utf-8")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["event_count"] == 7, summary
        assert summary["round_count"] == 1, summary
        assert summary["tool_call_count"] == 5, summary
        assert summary["loopx_cli_call_count"] == 3, summary
        assert summary["loopx_cli_calls"] == [
            {
                "round": 1,
                "command": "loopx status",
                "subcommands": ["status"],
                "flags": [],
                "state_usage": "state_read",
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
            {
                "round": 1,
                "command": "loopx todo update",
                "subcommands": ["todo", "update"],
                "flags": ["--format", "--registry", "--runtime-root"],
                "state_usage": "state_write",
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
            {
                "round": 1,
                "command": "loopx quota spend-slot",
                "subcommands": ["quota", "spend-slot"],
                "flags": ["--format", "--registry", "--runtime-root"],
                "state_usage": "state_write",
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
        ], summary
        assert summary["action_category_counts"] == {
            "edit": 1,
            "loopx_cli": 3,
            "validation": 1,
        }, summary
        assert summary["loopx_cli_state_usage_counts"] == {
            "state_read": 1,
            "state_write": 2,
        }, summary
        assert summary["loopx_cli_state_read_count"] == 1, summary
        assert summary["loopx_cli_state_write_count"] == 2, summary
        assert summary["protected_path_mentions"] == [
            "/app/reward_fn.py",
            "/app/train_grpo.py",
        ], summary
        assert summary["protected_path_edit_signal_count"] == 1, summary
        assert summary["protected_path_edit_rounds"] == {"/app/train_grpo.py": [1]}, summary

        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                job_name,
                "--rollout-name",
                rollout_name,
            ]
        )
        plan = build_plan(args)
        trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "codex-acp-blind-loop-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "blind_loop": True,
            "official_feedback_forwarded": False,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_acp_trajectory_summary(plan, trace)
        assert trace["private_agent_trajectory_summary_recorded"] is True, trace
        assert trace["raw_agent_trajectory_recorded"] is False, trace
        assert trace["acp_trajectory_summary"]["codex_acp_text_bytes"] == 0, trace

        trace_path = jobs_dir / job_name / "loopx_controller_trace.public.json"
        write_json(trace_path, trace)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        compact = reduce_result(args, result_path, plan)
        counters = compact["interaction_counters"]
        assert counters["private_trajectory_summary_present"] is True, compact
        assert counters["private_trajectory_event_count"] == 7, compact
        assert counters["private_trajectory_tool_call_count"] == 5, compact
        assert counters["loopx_cli_call_count"] == 3, compact
        assert counters["loopx_cli_calls"] == [
            {
                "round": 1,
                "command": "loopx status",
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
            {
                "round": 1,
                "command": "loopx todo update",
                "flags": ["--format", "--registry", "--runtime-root"],
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
            {
                "round": 1,
                "command": "loopx quota spend-slot",
                "flags": ["--format", "--registry", "--runtime-root"],
                "raw_title_copied": False,
                "raw_output_copied": False,
            },
        ], compact
        assert counters["trajectory_action_category_counts"] == {
            "edit": 1,
            "loopx_cli": 3,
            "validation": 1,
        }, compact
        assert counters["loopx_cli_state_usage_counts"] == {
            "state_read": 1,
            "state_write": 2,
        }, compact
        assert counters["loopx_cli_state_read_count"] == 1, compact
        assert counters["loopx_cli_state_write_count"] == 2, compact
        assert counters["protected_path_mention_count"] == 2, compact
        assert counters["protected_path_edit_signal_count"] == 1, compact
        assert "loopx:acp_trajectory_summary" in compact["evidence_files"], compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "Do not modify" not in compact_text, compact
        assert "Finished local validation" not in compact_text, compact
        assert str(root) not in compact_text, compact


def test_cli_dry_run_skillsbench_skeleton() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-smoke-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "skillsbench",
                "--goal-id",
                GOAL_ID,
                "--skillsbench-route",
                "loopx-goal-start-product-mode",
                "--include-task-name",
                "citation-check",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["benchmark_run"]["benchmark_id"] == "skillsbench@1.1", payload
        assert payload["benchmark_cli"]["benchmark"] == "skillsbench", payload
        assert payload["benchmark_cli"]["skillsbench_route"] == (
            "loopx-goal-start-product-mode"
        ), payload
        assert payload["benchmark_cli"]["real_runner_invoked"] is False, payload
        assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload


def test_cli_dry_run_skillsbench_official_result() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-result-smoke-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        result_path = write_official_skillsbench_result(root)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "skillsbench",
                "--goal-id",
                GOAL_ID,
                "--skillsbench-route",
                "codex-acp-blind-loop-baseline",
                "--skillsbench-result-json",
                str(result_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["benchmark_run"]["source_runner"] == (
            "official_skillsbench_benchflow_result"
        ), payload
        assert payload["benchmark_run"]["official_task_score"]["value"] == 0.0
        assert payload["benchmark_cli"]["skillsbench_result_ingested"] is True, payload


def test_cli_skillsbench_result_root_discovers_nested_case_result_for_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-result-root-smoke-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        run_group_id = "skillsbench-goal-baseline-30case-r12-fixture"
        task_id = "citation-check"
        case_root = root / run_group_id / task_id
        nested_result = case_root / task_id / "result.json"
        write_json(
            nested_result,
            {
                "task_name": task_id,
                "rollout_name": f"{task_id}__nested_fixture",
                "rewards": {"reward": 0.0},
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 9,
                "n_prompts": 2,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(nested_result.with_name("timing.json"), {"total": 42.0})
        write_json(
            case_root / "other-task" / "result.json",
            {
                "task_name": "other-task",
                "rollout_name": "other-task__nested_fixture",
                "rewards": {"reward": 1.0},
            },
        )
        ledger_path = root / "visible-ledger.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "skillsbench",
                "--goal-id",
                GOAL_ID,
                "--skillsbench-route",
                "codex-acp-blind-loop-baseline",
                "--include-task-name",
                task_id,
                "--skillsbench-result-root",
                str(case_root),
                "--update-run-ledger",
                "--run-ledger-path",
                str(ledger_path),
                "--run-group-id",
                run_group_id,
                "--arm-id",
                "codex_acp_blind_loop_baseline",
                "--execute",
                "--no-global-sync",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["benchmark_cli"]["skillsbench_result_ingested"] is True, payload
        assert payload["benchmark_cli"]["skillsbench_result_root_ingested"] is True, payload
        discovery = payload["skillsbench_result_discovery"]
        assert discovery["status"] == "found", discovery
        assert discovery["selected_relative_to_root"] == f"{task_id}/result.json", discovery
        assert payload["benchmark_run"]["result_discovery"]["status"] == "found", payload
        ledger_payload = payload["benchmark_run_ledger"]
        assert ledger_payload["updated"] is True, ledger_payload
        entry = ledger_payload["entry"]
        assert entry["case_id"] == task_id, entry
        refs = entry["artifact_refs"]
        assert refs["artifact_ref"] == task_id, refs
        assert refs["result_ref"] == f"{task_id}/result.json", refs
        assert (root / "visible-ledger.md").exists(), "CLI should render markdown"


def test_skillsbench_runner_plan_supports_controller_trace_path() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-trace-plan-") as tmp:
        root = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "software-dependency-audit",
                "--route",
                "loopx-goal-start-product-mode",
                "--jobs-dir",
                str(root / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        plan = payload["launch_plan"]
        assert plan["route"] == "loopx-goal-start-product-mode", plan
        assert plan["controller_trace_json"].endswith(
            "loopx_controller_trace.public.json"
        ), plan
        assert plan["include_task_skills"] is False, plan


def test_skillsbench_parallel_batch_isolates_case_process_argv() -> None:
    args = parse_args(
        [
            "--task-ids",
            "3d-scan-calc,adaptive-cruise-control",
            "--parallel-cases",
            "2",
            "--route",
            "codex-app-server-goal-baseline",
            "--allow-deprecated-app-server-goal-route",
            "--run-group-id",
            "skillsbench-goal-baseline-30case-test",
            "--job-name",
            "skillsbench-goal-baseline-30case-test",
            "--rollout-name",
            "skillsbench-goal-baseline-30case-test",
            "--max-rounds",
            "16",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--app-server-reasoning-effort",
            "high",
            "--append-history",
        ]
    )
    assert parallel_batch_requires_subprocess_isolation(2) is True
    case_args = skillsbench_loop._clone_args_for_batch_case(
        args,
        task_id="adaptive-cruise-control",
        index=1,
        total=2,
        run_group_id="skillsbench-goal-baseline-30case-test",
    )
    child_argv = skillsbench_loop._batch_case_args_to_cli(case_args)
    assert "--task-ids" not in child_argv, child_argv
    assert "--apt-risk-fail-fast-defaulted" not in child_argv, child_argv
    assert "--bootstrap-light-fail-fast-defaulted" not in child_argv, child_argv
    assert "--verifier-bootstrap-fail-fast-defaulted" not in child_argv, child_argv
    assert "--fail-fast-on-apt-risk" not in child_argv, child_argv
    assert "--fail-fast-on-verifier-bootstrap-risk" not in child_argv, child_argv
    assert child_argv[child_argv.index("--task-id") + 1] == (
        "adaptive-cruise-control"
    ), child_argv
    assert child_argv[child_argv.index("--parallel-cases") + 1] == "1", child_argv
    assert child_argv[child_argv.index("--run-group-id") + 1] == (
        "skillsbench-goal-baseline-30case-test"
    ), child_argv
    assert child_argv[child_argv.index("--job-name") + 1].endswith(
        "-02-adaptive-cruise-control"
    ), child_argv
    assert "--host-local-acp-launch" in child_argv, child_argv
    assert "--remote-command-file-bridge-ready" in child_argv, child_argv
    assert "--append-history" in child_argv, child_argv
    reparsed_child = parse_args(child_argv)
    assert reparsed_child.task_id == "adaptive-cruise-control", reparsed_child
    assert reparsed_child.task_ids is None, reparsed_child
    assert reparsed_child.parallel_cases == 1, reparsed_child
    assert reparsed_child.bootstrap_light_fail_fast_defaulted is True, reparsed_child


def test_skillsbench_single_task_ids_replaces_default_task_id() -> None:
    args = parse_args(
        [
            "--task-ids",
            "bike-rebalance",
            "--route",
            "codex-app-server-goal-baseline",
            "--allow-deprecated-app-server-goal-route",
            "--plan-only",
        ]
    )
    assert args.task_id == "bike-rebalance", args
    assert skillsbench_loop._batch_task_ids(args) == ["bike-rebalance"], args


def test_skillsbench_parallel_batch_recovers_child_payload_from_mixed_stderr() -> None:
    args = parse_args(
        [
            "--task-id",
            "suricata-custom-exfil",
            "--route",
            "codex-app-server-goal-baseline",
            "--allow-deprecated-app-server-goal-route",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
        ]
    )
    payload = {
        "ok": False,
        "task_id": "suricata-custom-exfil",
        "route": "codex-app-server-goal-baseline",
        "score_failure_attribution": "skillsbench_verifier_bootstrap_risk_preflight_blocked",
        "compact_closeout_recorded": True,
    }
    recovered = skillsbench_loop._extract_batch_case_subprocess_payload(
        case_args=args,
        returncode=2,
        stdout=b"",
        stderr=(
            "usage warning that must not become the payload\n"
            + json.dumps(payload, sort_keys=True)
            + "\n"
        ).encode("utf-8"),
    )
    assert recovered["task_id"] == "suricata-custom-exfil", recovered
    assert recovered["score_failure_attribution"] == (
        "skillsbench_verifier_bootstrap_risk_preflight_blocked"
    ), recovered
    assert recovered["compact_closeout_recorded"] is True, recovered
    assert recovered["batch_case_subprocess_payload_source"] == "stderr", recovered
    assert recovered["batch_case_subprocess_payload_mixed_output"] is True, recovered
    assert recovered["runner_returncode"] == 2, recovered
    assert recovered.get("raw_stdout_recorded") is not True, recovered
    assert recovered.get("raw_stderr_recorded") is not True, recovered


def test_skillsbench_compact_runs_update_ledger_pair() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-ledger-smoke-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        baseline = compact_skillsbench_run(
            task_id="citation-check",
            mode="skillsbench_raw_codex_autonomous_max5",
            score=0.0,
            passed=False,
            exception_type="AgentRuntimeError",
            round_reward_trace={
                "schema_version": "benchmark_round_reward_trace_v0",
                "source": "loopx_controller_trace",
                "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
                "records": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                    }
                ],
                "success_observed": False,
                "max_rounds_budget": 5,
                "official_feedback_blinded": True,
                "reward_feedback_forwarded": False,
            },
            payload_overrides={
                "official_feedback_blinded": True,
                "reward_feedback_forwarded": False,
                "product_mode": True,
            },
        )
        treatment = compact_skillsbench_run(
            task_id="citation-check",
            mode="skillsbench_loopx_product_mode_treatment",
            score=1.0,
            passed=True,
            round_reward_trace={
                "schema_version": "benchmark_round_reward_trace_v0",
                "source": "loopx_controller_trace",
                "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
                "records": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                    },
                    {
                        "agent_round": 2,
                        "reward_present": True,
                        "reward": 1.0,
                        "passed": True,
                    },
                ],
                "first_success_round": 2,
                "success_observed": True,
                "max_rounds_budget": 5,
                "official_feedback_blinded": True,
                "reward_feedback_forwarded": False,
            },
            payload_overrides={
                "loopx_inside_case": True,
                "official_feedback_blinded": True,
                "reward_feedback_forwarded": False,
                "product_mode": True,
                "product_mode_lifecycle_contract": {
                    "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
                    "required": True,
                    "satisfied": True,
                    "countable_treatment": True,
                    "checkpoint_required": True,
                    "closeout_required": True,
                    "closeout_satisfied": True,
                    "state_read_count": 1,
                    "state_write_count": 1,
                    "agent_operation_trace_required": False,
                },
            },
        )
        baseline_update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            run_group_id="skillsbench-citation-check-pair",
            notes="compact baseline failure fixture; no raw task/log material",
            dry_run=False,
        )
        assert baseline_update["entry"]["arm_id"] == (
            "skillsbench_raw_codex_autonomous_max5"
        )
        assert baseline_update["case_decision"]["decision"] == (
            "baseline_failed_treatment_candidate"
        )
        treatment_update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            run_group_id="skillsbench-citation-check-pair",
            notes="compact product-mode treatment fixture; no raw task/log material",
            dry_run=False,
        )
        assert treatment_update["entry"]["arm_id"] == (
            "codex_loopx_treatment"
        )
        assert treatment_update["case_decision"]["decision"] == (
            "paired_treatment_improved"
        )
        assert treatment_update["entry"]["first_success_round"] == 2
        assert treatment_update["entry"]["round_rewards"][1]["passed"] is True
        assert treatment_update["entry"]["reward_feedback_forwarded"] is False
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"]["citation-check"]
        assert len(case["runs"]) == 2, case
        assert case["latest_decision"]["official_score_delta"] == 1.0, case
        rendered = (ledger_path.with_suffix(".md")).read_text(encoding="utf-8")
        assert "First Success Round" in rendered, rendered
        assert "`1:0,2:1*`" in rendered, rendered


def test_skillsbench_repeat_same_mode_collapses_active_ledger_run() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-ledger-repeat-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        compact = compact_skillsbench_run(
            task_id="software-dependency-audit",
            mode="skillsbench_loopx_product_mode_treatment",
            score=0.0,
            passed=False,
        )
        first = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture",
            compact_artifact_ref=root / "first" / "benchmark_run.compact.json",
            notes="first compact treatment fixture",
            cwd=root,
            dry_run=False,
        )
        second = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture",
            compact_artifact_ref=root / "second" / "benchmark_run.compact.json",
            notes="second compact treatment fixture",
            cwd=root,
            dry_run=False,
        )
        assert first["entry"]["run_id"] != second["entry"]["run_id"], second
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "software-dependency-audit"
        ]
        assert len(case["runs"]) == 1, case
        assert case["active_run_count"] == 1, case
        assert case["latest_decision"]["decision"] == "single_arm_recorded", case
        third = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture-no-artifact-a",
            notes="third compact treatment fixture without artifact ref",
            dry_run=False,
        )
        fourth = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture-no-artifact-b",
            notes="fourth compact treatment fixture without artifact ref",
            dry_run=False,
        )
        assert third["entry"]["run_id"] != fourth["entry"]["run_id"], fourth
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "software-dependency-audit"
        ]
        assert len(case["runs"]) == 3, case
        assert case["active_run_count"] == 3, case


def test_skillsbench_run_group_ledger_inherits_and_syncs_global_ledger() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-ledger-global-sync-") as tmp:
        root = Path(tmp)
        global_ledger = root / "global" / "benchmark-run-ledger.json"
        run_group_ledger = root / "run-group" / "benchmark-run-ledger.json"
        inherited_compact = compact_skillsbench_run(
            task_id="3d-scan-calc",
            mode="skillsbench_codex_app_server_goal_baseline",
            score=1.0,
            passed=True,
        )
        update_benchmark_run_ledger(
            ledger_path=global_ledger,
            benchmark_run=inherited_compact,
            run_group_id="skillsbench-global-existing",
            dry_run=False,
        )
        new_compact = compact_skillsbench_run(
            task_id="tictoc-unnecessary-abort-detection",
            mode="skillsbench_codex_app_server_goal_baseline",
            score=1.0,
            passed=True,
        )
        args = parse_args(
            [
                "--task-id",
                "tictoc-unnecessary-abort-detection",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--ledger-path",
                str(run_group_ledger),
                "--global-ledger-path",
                str(global_ledger),
                "--run-group-id",
                "skillsbench-revtunnel-appgoal-batch5-fixture",
                "--update-ledger",
            ]
        )
        compact_path = (
            root
            / "remote-public"
            / "tictoc-unnecessary-abort-detection"
            / "benchmark_run.compact.json"
        )
        update = update_skillsbench_ledger(args, new_compact, compact_path=compact_path)
        assert update["ledger_scope"] == "run_group_with_global_sync", update
        assert update["global_ledger_inheritance"]["status"] == "inherited", update
        assert update["global_ledger_inheritance"]["inherited"] is True, update
        assert update["primary_ledger_update"]["updated"] is True, update
        assert update["global_ledger_update"]["updated"] is True, update
        aggregate_update = update["current_aggregate_update"]
        assert aggregate_update["updated"] is True, aggregate_update
        assert aggregate_update["canonical_covered"] == 2, aggregate_update

        local_ledger = load_benchmark_run_ledger(run_group_ledger)
        global_payload = load_benchmark_run_ledger(global_ledger)
        local_cases = local_ledger["benchmarks"]["skillsbench@1.1"]["cases"]
        global_cases = global_payload["benchmarks"]["skillsbench@1.1"]["cases"]
        assert "3d-scan-calc" in local_cases, local_cases
        assert "tictoc-unnecessary-abort-detection" in local_cases, local_cases
        assert "tictoc-unnecessary-abort-detection" in global_cases, global_cases
        aggregate_path = global_ledger.parent / "current-aggregate-status.v3.json"
        assert aggregate_path.exists(), aggregate_path
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
        assert aggregate["distribution"]["pass"] == 2, aggregate
        assert aggregate["case_best"]["tictoc-unnecessary-abort-detection"][
            "bucket"
        ] == "pass", aggregate
        assert ".local" not in json.dumps(update, sort_keys=True), update


def test_skillsbench_runner_failure_compact_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-failure-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-debug-trl-grpo-failure-fixture",
            ]
        )
        plan = build_plan(args)
        compact = build_runner_failure_compact(
            args,
            plan,
            FileNotFoundError("BenchFlow result.json not found"),
        )
        assert compact["schema_version"] == "benchmark_run_v0", compact
        assert compact["benchmark_id"] == "skillsbench@1.1", compact
        assert compact["source_runner"] == (
            "official_skillsbench_benchflow_launch_failure"
        ), compact
        assert compact["task_id"] == "debug-trl-grpo", compact
        assert compact["case_id"] == "debug-trl-grpo", compact
        assert compact["route"] == "codex-acp-blind-loop-baseline", compact
        assert compact["job_name"] == "skillsbench-debug-trl-grpo-failure-fixture", (
            compact
        )
        assert compact["rollout_name"] == "debug-trl-grpo__codex_acp_blind_loop", (
            compact
        )
        assert compact["mode"] == "skillsbench_codex_acp_blind_loop_baseline", compact
        assert compact["real_run"] is True, compact
        assert compact["official_score_status"] == "missing", compact
        assert compact["first_blocker"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact
        assert "skillsbench_result_json_missing_after_runner_exit" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"] == {
            "exception_type": "FileNotFoundError",
            "failure_class": "skillsbench_result_json_missing_after_runner_exit",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_runner_failure_v0",
        }, compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_stage": (
                    "after_agent_install_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "pending",
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            },
        )
        assert "do_not_run_benchflow_from_skeleton" not in compact[
            "stop_conditions"
        ], compact
        assert "classify_compact_runner_failure_before_rerun" in compact[
            "stop_conditions"
        ], compact
        assert (
            "do_not_read_raw_task_prompt_solution_log_or_trajectory"
            in compact["stop_conditions"]
        ), compact
        assert "BenchFlow result.json not found" not in json.dumps(compact), compact


def test_skillsbench_runner_failure_case_event_timeline_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-failure-timeline-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-failure-timeline-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "remote_command_file_bridge_consumed_by_solver": True,
                "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_missing"
                ),
                "benchflow_user_loop_recovery_exception_type": (
                    "AgentPromptTimeoutError"
                ),
                "benchflow_user_loop_recovery_stage": "agent_execute",
                "benchflow_user_loop_recovery_delta_events": 3,
                "benchflow_user_loop_recovery_delta_tool_calls": 0,
                "benchflow_agent_timeout_effective_sec": 21660,
                "benchflow_agent_timeout_host_local_acp_exec_timeout_sec": 21600,
            }
        )

        compact = build_runner_failure_compact(
            args,
            plan,
            TimeoutError("PRIVATE_TIMEOUT_DETAIL_SHOULD_NOT_ESCAPE"),
        )
        timeline = compact["case_event_timeline"]
        events = {event["event"]: event for event in timeline["events"]}
        assert events["remote_command_bridge_consumption"]["status"] == "consumed"
        assert events["task_facing_activity"]["status"] == (
            "missing_agent_operation_trace"
        )
        recovery = events["timeout_or_failure_closeout"]
        assert recovery["status"] == "user_loop_recovery_triggered"
        assert recovery["recovery_exception_type"] == "AgentPromptTimeoutError"
        assert recovery["benchflow_agent_timeout_effective_sec"] == 21660
        assert recovery["local_codex_exec_timeout_sec"] == 21600
        assert events["official_score_closeout"]["status"] == "missing"
        gate = compact["post_run_debug_gate"]
        assert gate["schema_version"] == "skillsbench_post_run_debug_gate_v0"
        assert gate["packet_complete"] is True, gate
        assert gate["case_closeout_complete"] is False, gate
        assert gate["next_case_gate"] == "blocked_incomplete_case_closeout", gate
        assert gate["normal_progress_allowed"] is False, gate
        assert gate["attribution_layer"] == "loopx_lifecycle", gate
        assert gate["first_blocker"] in {
            "remote_command_file_bridge_agent_operation_trace_missing",
            "loopx_lifecycle_incomplete",
        }, gate
        assert gate["timeout_fairness"]["recovery_exception_type"] == (
            "AgentPromptTimeoutError"
        )

        compact_again = compact_benchmark_run(compact)
        assert compact_again is not None
        assert compact_again["case_event_timeline"]["raw_material_recorded"] is False
        assert compact_again["post_run_debug_gate"]["packet_complete"] is True
        assert "PRIVATE_TIMEOUT_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact_again
        ), compact_again


def test_skillsbench_runner_failure_recovers_zero_score_from_controller_trace() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-failure-score-recovery-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "paratransit-routing",
                "--route",
                "loopx-goal-start-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-paratransit-recovered-score-fixture",
            ]
        )
        plan = build_plan(args)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "product_mode": True,
            "goal_start_product_mode": True,
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "official_feedback_blinded_count": 2,
            "official_feedback_forwarded": False,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                    "tool_calls": 3,
                },
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                    "tool_calls": 1,
                },
            ],
            "max_rounds_budget": 16,
            "last_decision": (
                "stop_after_product_mode_two_no_open_todo_rounds_without_passing_reward"
            ),
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_request_count": 10,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 5,
            "remote_command_file_bridge_agent_task_facing_operation_count": 4,
            "remote_command_file_bridge_agent_task_facing_success_count": 4,
            "remote_command_file_bridge_agent_todo_closeout_count": 2,
            "remote_command_file_bridge_agent_refresh_state_count": 1,
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
            "product_mode_no_open_todo_below_passing_reward_stop": True,
            "product_mode_no_open_todo_below_passing_reward_streak": 2,
            "product_mode_no_open_todo_below_passing_reward_streak_threshold": 2,
            "product_mode_no_open_todo_below_passing_reward_round": 2,
            "product_mode_no_open_todo_below_passing_reward_stop_round": 2,
            "product_mode_no_open_todo_below_passing_reward_score": 0.0,
            "product_mode_no_open_todo_below_passing_reward_score_status": (
                "observed_below_passing"
            ),
            "product_mode_no_open_todo_below_passing_reward_open_todo_count_public": 0,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        write_json(Path(plan["controller_trace_json"]), controller_trace)

        compact = build_runner_failure_compact(
            args,
            plan,
            KeyboardInterrupt("PRIVATE_INTERRUPTION_DETAIL_SHOULD_NOT_ESCAPE"),
        )

        assert compact["runner_return_status"] == (
            "interrupted_after_controller_reward_observation"
        ), compact
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 0.0, compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_controller_trace",
            "passed": False,
            "value": 0.0,
        }, compact
        assert compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), compact
        assert "skillsbench_runner_interrupted_after_controller_reward_observation" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["round_reward_trace"]["final_round_reward"] == 0.0, compact
        assert compact["round_reward_trace"][
            "official_score_recovered_from_controller_trace"
        ] is True, compact
        assert compact["interaction_counters"][
            "product_mode_no_open_todo_below_passing_reward_stop"
        ] is True, compact
        assert compact["product_mode_lifecycle_contract"]["satisfied"] is True, (
            compact
        )
        assert compact["attempt_accounting"]["official_score_attempt_countable"] is True
        assert compact["attempt_accounting"]["failure_class"] == "solver_failed"
        events = {event["event"]: event for event in compact["case_event_timeline"]["events"]}
        assert events["timeout_or_failure_closeout"]["status"] == (
            "runner_failure_after_official_score"
        ), compact
        assert events["controller_decision_loop"]["max_rounds_budget"] == 16
        assert events["controller_decision_loop"]["initial_prompt_count"] == 1
        assert events["controller_decision_loop"]["followup_prompt_count"] == 1
        assert events["controller_decision_loop"]["stop_decision_count"] == 1
        assert events["official_score_closeout"]["status"] == "completed_nonpassing"
        gate = compact["post_run_debug_gate"]
        assert gate["packet_complete"] is True, gate
        assert gate["case_closeout_complete"] is True, gate
        assert gate["normal_progress_allowed"] is True, gate
        assert gate["attribution_layer"] == "solution_level_unknown", gate
        assert gate["first_blocker"] == "official_score_zero_case_failure", gate
        assert gate["scorer_verifier"]["official_score_status"] == (
            "completed_nonpassing"
        ), gate
        assert gate["scorer_verifier"]["official_score_value"] == 0.0, gate
        solution_quality = compact["solution_quality_signals"]
        assert solution_quality["outcome_class"] == "official_zero", compact
        assert "official_zero_after_public_worker_activity" in solution_quality[
            "solution_action_labels"
        ], compact
        assert "runner_recovery_noise_recorded" in solution_quality[
            "solution_action_labels"
        ], compact
        assert gate["solution_quality"]["outcome_class"] == "official_zero", gate
        assert "runner_recovery_noise_recorded" in gate["solution_quality"][
            "solution_action_labels"
        ], gate
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_runner_interrupted_after_controller_reward_observation"
        ), compact
        assert "PRIVATE_INTERRUPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_runner_failure_recovers_passing_score_from_verifier_artifact() -> None:
    with tempfile.TemporaryDirectory(
        prefix="skillsbench-verifier-artifact-recovery-"
    ) as tmp:
        args = parse_args(
            [
                "--task-id",
                "paratransit-routing",
                "--route",
                "loopx-goal-start-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-paratransit-verifier-artifact-fixture",
                "--max-rounds",
                "16",
                "--outer-timeout-sec",
                "3600",
                "--product-mode-soft-verify-policy",
                "every-round",
                "--soft-verifier-timeout-sec",
                "600",
            ]
        )
        plan = build_plan(args)
        run_dir = Path(plan["result_json"]).parent
        verifier_dir = run_dir / "verifier"
        verifier_dir.mkdir(parents=True, exist_ok=True)
        (verifier_dir / "reward.txt").write_text("1\n", encoding="utf-8")
        write_json(
            verifier_dir / "ctrf.json",
            {
                "summary": {
                    "tests": 7,
                    "passed": 7,
                    "failed": 0,
                    "pending": 0,
                    "skipped": 0,
                    "start": 1.0,
                    "stop": 2.0,
                }
            },
        )

        compact = build_runner_failure_compact(
            args,
            plan,
            TimeoutError("PRIVATE_TIMEOUT_DETAIL_SHOULD_NOT_ESCAPE"),
        )

        assert compact["runner_return_status"] == (
            "interrupted_after_verifier_reward_artifact"
        ), compact
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 1.0, compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_verifier_artifact",
            "passed": True,
            "value": 1.0,
        }, compact
        assert compact["score_failure_attribution"] == "none", compact
        assert compact["attempt_accounting"]["official_score_attempt_countable"] is True
        assert compact["attempt_accounting"]["failure_class"] == "none"
        assert compact["verifier_reward_artifact_recovery"]["passed"] is True
        assert compact["verifier_reward_artifact_recovery"][
            "official_result_json_materialized"
        ] is False
        assert compact["verifier_reward_artifact_discovery"]["status"] == "found"
        assert compact["verifier_ctrf_summary"]["tests"] == 7
        assert compact["verifier_ctrf_summary"]["passed"] == 7
        assert compact["validation"]["verifier_reward_artifact_recovered"] is True
        assert compact["validation"]["official_case_success"] is True
        assert "skillsbench_runner_interrupted_after_verifier_reward_artifact" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_result_json_missing_after_runner_exit" not in compact[
            "failure_attribution_labels"
        ], compact

        runner_config = compact["runner_config"]
        assert runner_config["route"] == "loopx-goal-start-product-mode"
        assert runner_config["max_rounds"] == 16
        assert runner_config["outer_timeout_sec"] == 3600
        assert runner_config["product_mode_soft_verify_policy"] == "every-round"
        assert runner_config["soft_verifier_timeout_sec"] == 600
        assert runner_config["raw_command_recorded"] is False
        assert runner_config["raw_env_recorded"] is False

        public_runner_config_path = (
            Path(plan["jobs_dir"]) / plan["job_name"] / RUNNER_CONFIG_PUBLIC_FILENAME
        )
        assert public_runner_config_path.exists(), public_runner_config_path
        persisted_runner_config = json.loads(
            public_runner_config_path.read_text(encoding="utf-8")
        )
        assert persisted_runner_config["max_rounds"] == 16
        rollout_config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        assert rollout_config["loopx_runner_config"]["outer_timeout_sec"] == 3600
        assert rollout_config["loopx_runner_config_public"] is True
        assert rollout_config["loopx_runner_config_raw_command_recorded"] is False
        assert rollout_config["loopx_runner_config_raw_env_recorded"] is False

        events = {event["event"]: event for event in compact["case_event_timeline"]["events"]}
        assert events["official_score_closeout"]["status"] == "passed"
        gate = compact["post_run_debug_gate"]
        assert gate["packet_complete"] is True, gate
        assert gate["case_closeout_complete"] is True, gate
        assert gate["normal_progress_allowed"] is True, gate
        assert "PRIVATE_TIMEOUT_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(compact)


def test_skillsbench_runner_failure_compact_attributes_agent_no_requests() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-agent-request-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-organize-messy-files-no-agent-request-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "remote_command_file_bridge_agent_operation_trace_required": True,
                "remote_command_file_bridge_agent_operation_trace_satisfied": False,
                "remote_command_file_bridge_agent_operation_trace_status": (
                    "agent_operation_trace_present_no_requests"
                ),
                "remote_command_file_bridge_agent_operation_trace_count": 1,
                "remote_command_file_bridge_agent_request_count": 0,
                "remote_command_file_bridge_agent_loopx_cli_call_count": 0,
                "remote_command_file_bridge_agent_loopx_state_read_count": 0,
                "remote_command_file_bridge_agent_loopx_state_write_count": 0,
            }
        )
        compact = build_runner_failure_compact(
            args,
            plan,
            SkillsBenchProductModeNoLifecycleRequests(
                "loopx-product-mode agent produced no tool or case-local "
                "LoopX lifecycle request before official verifier"
            ),
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["first_blocker"] == (
            "skillsbench_remote_bridge_agent_no_requests"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_remote_bridge_agent_no_requests"
        ), compact
        assert (
            compact["runner_failure"]["failure_class"]
            == "skillsbench_remote_bridge_agent_no_requests"
        ), compact
        assert (
            compact["runner_prerequisites"][
                "remote_command_file_bridge_agent_operation_trace_status"
            ]
            == "agent_operation_trace_present_no_requests"
        ), compact
        assert "skillsbench_remote_bridge_agent_no_requests" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_remote_bridge_agent_operation_trace_missing" not in compact[
            "failure_attribution_labels"
        ], compact
        assert "case-local LoopX lifecycle request" not in json.dumps(compact), compact


def test_skillsbench_product_mode_pass_clears_generic_runner_error() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-pass-runner-error-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=1.0)
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["error"] = "generic runner closeout noise after official scoring"
        write_json(result_path, payload)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "publicness": "public_counts_only_no_task_text_no_verifier_output",
            "loopx_automation_loop": True,
            "product_mode": True,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "remote_command_file_bridge_driver_lifecycle_trace_count": 1,
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                "orchestrated_agentloop_loopx_cli"
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 1,
            "remote_command_file_bridge_driver_lifecycle_success_count": 4,
            "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 4,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 1,
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 3,
            "remote_command_file_bridge_agent_command_instrumented": True,
            "remote_command_file_bridge_agent_operation_trace_required": True,
            "remote_command_file_bridge_agent_operation_trace_satisfied": True,
            "remote_command_file_bridge_agent_operation_trace_status": (
                "agent_operation_trace_recorded"
            ),
            "remote_command_file_bridge_agent_operation_trace_count": 1,
            "remote_command_file_bridge_agent_request_count": 2,
            "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
            "remote_command_file_bridge_agent_loopx_state_read_count": 1,
            "remote_command_file_bridge_agent_loopx_state_write_count": 1,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["official_score"] == 1.0, compact
        assert compact["score_failure_attribution"] == "none", compact
        assert compact.get("failure_attribution_labels", []) == [], compact
        assert compact.get("runner_failure") is None, compact
        assert (
            compact["product_mode_lifecycle_contract"]["countable_treatment"]
            is True
        ), compact
        assert (
            "skillsbench_runner_error_after_official_pass_ignored"
            in compact["model_control"]["warning_labels"]
        ), compact


def test_skillsbench_runner_failure_prefers_structured_preflight_blocker() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-preflight-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "raw-codex-autonomous-max5",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-debug-trl-grpo-preflight-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "failed",
                "codex_acp_runtime_launch_preflight_rc": 127,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            }
        )
        compact = build_runner_failure_compact(
            args,
            plan,
            RuntimeError("BenchFlow runner exited before official result"),
        )
        assert compact["first_blocker"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_status"
        ] == "failed", compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_raw_logs_read"
        ] is False, compact
        assert "BenchFlow runner exited before official result" not in json.dumps(
            compact
        ), compact


def test_skillsbench_runner_failure_marks_pre_agent_install_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-pre-agent-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "hello-world",
                "--route",
                "raw-codex-autonomous-max5",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-hello-world-pre-agent-fixture",
            ]
        )
        plan = build_plan(args)
        compact = build_runner_failure_compact(
            args,
            plan,
            RuntimeError("BenchFlow runner exited before official result"),
        )
        assert compact["first_blocker"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_container_bootstrap"
        ] is True, compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_dependency_preflight"
        ] is True, compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_status"
        ] == "pending", compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_stage"
        ] == "after_agent_install_before_acp_connect", compact
        assert "BenchFlow runner exited before official result" not in json.dumps(
            compact
        ), compact


def test_skillsbench_runner_failure_marks_final_verifier_timeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-final-verifier-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "powerlifting-coef-calc",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-powerlifting-final-verifier-timeout-fixture",
                "--final-verifier-timeout-sec",
                "600",
            ]
        )
        plan = build_plan(args)
        plan.setdefault("runner_prerequisites", {}).update(
            {
                "benchflow_final_verifier_timeout_enabled": True,
                "benchflow_final_verifier_timeout_sec": 600,
                "benchflow_final_verifier_timeout_override_count": 1,
                "benchflow_final_verifier_timeout_triggered": True,
                "benchflow_final_verifier_timeout_raw_command_recorded": False,
                "benchflow_final_verifier_timeout_raw_output_recorded": False,
            }
        )

        compact = build_runner_failure_compact(
            args,
            plan,
            asyncio.TimeoutError("final verifier timed out"),
        )

        assert compact["first_blocker"] == "skillsbench_final_verifier_timeout"
        assert compact["score_failure_attribution"] == (
            "skillsbench_final_verifier_timeout"
        )
        assert "skillsbench_verifier_timeout" in compact[
            "failure_attribution_labels"
        ], compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "benchflow_final_verifier_timeout_enabled": True,
                "benchflow_final_verifier_timeout_sec": 600,
                "benchflow_final_verifier_timeout_override_count": 1,
                "benchflow_final_verifier_timeout_triggered": True,
                "benchflow_final_verifier_timeout_raw_command_recorded": False,
                "benchflow_final_verifier_timeout_raw_output_recorded": False,
            },
        )
        compact_text = json.dumps(compact, sort_keys=True)
        assert "final verifier timed out" not in compact_text
        assert "/private/" not in compact_text


def test_skillsbench_runner_failure_backfills_generic_timeout_stall_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-generic-timeout-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-citation-check-generic-timeout-fixture",
                "--build-stall-timeout-sec",
                "180",
            ]
        )
        plan = build_plan(args)
        plan.setdefault("runner_prerequisites", {})[
            "codex_acp_runtime_launch_preflight_status"
        ] = "pending"
        cleanup_calls: list[str] = []
        original_cleanup = skillsbench_loop.cleanup_benchflow_setup_stall_children

        def fake_cleanup(plan_arg: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
            cleanup_calls.append(str(plan_arg.get("job_name") or ""))
            prereqs = plan_arg.setdefault("runner_prerequisites", {})
            prereqs.update(
                {
                    "benchflow_setup_stall_cleanup_requested": True,
                    "benchflow_setup_stall_cleanup_raw_logs_read": False,
                    "benchflow_setup_stall_cleanup_status": "no_matching_processes",
                    "benchflow_setup_stall_cleanup_match_count": 0,
                    "benchflow_setup_stall_cleanup_term_sent_count": 0,
                    "benchflow_setup_stall_cleanup_kill_sent_count": 0,
                    "benchflow_setup_stall_cleanup_alive_after_count": 0,
                }
            )
            return {
                "schema_version": "skillsbench_setup_stall_process_cleanup_v0",
                "requested": True,
                "raw_logs_read": False,
                "status": "no_matching_processes",
                "match_count": 0,
                "term_sent_count": 0,
                "kill_sent_count": 0,
                "alive_after_count": 0,
            }

        try:
            skillsbench_loop.cleanup_benchflow_setup_stall_children = fake_cleanup
            compact = build_runner_failure_compact(
                args,
                plan,
                asyncio.TimeoutError(),
            )
        finally:
            skillsbench_loop.cleanup_benchflow_setup_stall_children = (
                original_cleanup
            )

        assert cleanup_calls == [plan["job_name"]], cleanup_calls
        assert compact["first_blocker"] == (
            "skillsbench_docker_compose_build_stall_timeout"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_build_stall_timeout"
        ), compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "benchflow_run_stage": "build_or_setup_stall_before_agent",
                "benchflow_setup_stall_timeout_enabled": True,
                "benchflow_setup_stall_timeout_requested_sec": 180,
                "benchflow_setup_stall_timeout_sec": 180,
                "benchflow_setup_stall_timeout_triggered": True,
                "benchflow_setup_stall_before_agent_lifecycle": True,
                "benchflow_setup_stall_raw_logs_read": False,
                "benchflow_setup_stall_cleanup_requested": True,
                "benchflow_setup_stall_cleanup_raw_logs_read": False,
                "benchflow_setup_stall_cleanup_status": "no_matching_processes",
                "benchflow_setup_stall_cleanup_match_count": 0,
                "benchflow_setup_stall_cleanup_term_sent_count": 0,
                "benchflow_setup_stall_cleanup_kill_sent_count": 0,
                "benchflow_setup_stall_cleanup_alive_after_count": 0,
            },
        )
        assert compact["compose_setup_diagnostic"]["status"] == (
            "compose_setup_blocked_before_agent_rounds"
        ), compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "/private/" not in compact_text


def test_skillsbench_setup_stall_cleanup_targets_current_job_only() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cleanup-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-organize-messy-files-cleanup-fixture",
            ]
        )
        plan = build_plan(args)
        job_name = plan["job_name"]
        rollout_name = plan["rollout_name"]
        ps_stdout = "\n".join(
            [
                (
                    f"101 1 docker compose --project-name {rollout_name} "
                    f"--project-directory /tmp/{job_name}/prepared build"
                ),
                (
                    f"102 101 /usr/libexec/docker/cli-plugins/docker-buildx "
                    f"bake --allow fs.read=/tmp/{job_name}/prepared"
                ),
                (
                    "103 1 docker compose --project-name unrelated "
                    "--project-directory /tmp/other-job build"
                ),
            ]
        )
        alive = {101, 102, 103}
        sent: list[tuple[int, int]] = []
        original_run = skillsbench_loop.subprocess.run
        original_kill = skillsbench_loop.os.kill
        original_sleep = skillsbench_loop.time.sleep

        def fake_run(*_args: Any, **_kwargs: Any) -> Any:
            return types.SimpleNamespace(returncode=0, stdout=ps_stdout, stderr="")

        def fake_kill(pid: int, sig: int) -> None:
            if sig == 0:
                if pid in alive:
                    return
                raise ProcessLookupError(pid)
            sent.append((pid, sig))
            if sig == skillsbench_loop.signal.SIGTERM:
                alive.discard(pid)

        try:
            skillsbench_loop.subprocess.run = fake_run
            skillsbench_loop.os.kill = fake_kill
            skillsbench_loop.time.sleep = lambda _seconds: None
            cleanup = cleanup_benchflow_setup_stall_children(
                plan,
                grace_seconds=0,
            )
        finally:
            skillsbench_loop.subprocess.run = original_run
            skillsbench_loop.os.kill = original_kill
            skillsbench_loop.time.sleep = original_sleep

        assert cleanup["status"] == "terminated", cleanup
        assert cleanup["match_count"] == 2, cleanup
        assert set(sent) == {
            (101, skillsbench_loop.signal.SIGTERM),
            (102, skillsbench_loop.signal.SIGTERM),
        }, sent
        assert 103 in alive, alive
        prereqs = plan["runner_prerequisites"]
        assert_prerequisites_include(
            prereqs,
            {
                "benchflow_setup_stall_cleanup_requested": True,
                "benchflow_setup_stall_cleanup_raw_logs_read": False,
                "benchflow_setup_stall_cleanup_status": "terminated",
                "benchflow_setup_stall_cleanup_match_count": 2,
                "benchflow_setup_stall_cleanup_term_sent_count": 2,
                "benchflow_setup_stall_cleanup_kill_sent_count": 0,
                "benchflow_setup_stall_cleanup_alive_after_count": 0,
            },
        )
        assert job_name not in json.dumps(cleanup, sort_keys=True)


def test_skillsbench_host_local_attempt_cleanup_targets_current_attempt_only() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-host-acp-cleanup-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "bike-rebalance",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-bike-rebalance-cleanup-fixture-attempt-01",
                "--host-local-acp-launch",
            ]
        )
        plan = build_plan(args)
        job_name = plan["job_name"]
        rollout_name = plan["rollout_name"]
        ps_stdout = "\n".join(
            [
                (
                    "201 1 python scripts/skillsbench_local_acp_relay.py "
                    f"--worker-public-trace-dir /tmp/{job_name}/trace "
                    f"--project-name {rollout_name}"
                ),
                (
                    "202 201 python scripts/skillsbench_host_codex_goal_worker.py "
                    "--turn-timeout-sec 3600"
                ),
                "203 202 codex app-server --listen 127.0.0.1:0",
                (
                    "204 1 python scripts/skillsbench_local_acp_relay.py "
                    "--worker-public-trace-dir /tmp/unrelated/trace "
                    "--project-name unrelated"
                ),
            ]
        )
        alive = {201, 202, 203, 204}
        sent: list[tuple[int, int]] = []
        original_run = skillsbench_loop.subprocess.run
        original_kill = skillsbench_loop.os.kill
        original_sleep = skillsbench_loop.time.sleep

        def fake_run(*_args: Any, **_kwargs: Any) -> Any:
            return types.SimpleNamespace(returncode=0, stdout=ps_stdout, stderr="")

        def fake_kill(pid: int, sig: int) -> None:
            if sig == 0:
                if pid in alive:
                    return
                raise ProcessLookupError(pid)
            sent.append((pid, sig))
            if sig == skillsbench_loop.signal.SIGTERM:
                alive.discard(pid)

        try:
            skillsbench_loop.subprocess.run = fake_run
            skillsbench_loop.os.kill = fake_kill
            skillsbench_loop.time.sleep = lambda _seconds: None
            cleanup = cleanup_host_local_acp_attempt_children(
                plan,
                grace_seconds=0,
            )
        finally:
            skillsbench_loop.subprocess.run = original_run
            skillsbench_loop.os.kill = original_kill
            skillsbench_loop.time.sleep = original_sleep

        assert cleanup["status"] == "terminated", cleanup
        assert cleanup["match_count"] == 3, cleanup
        assert set(sent) == {
            (201, skillsbench_loop.signal.SIGTERM),
            (202, skillsbench_loop.signal.SIGTERM),
            (203, skillsbench_loop.signal.SIGTERM),
        }, sent
        assert 204 in alive, alive
        prereqs = plan["runner_prerequisites"]
        assert_prerequisites_include(
            prereqs,
            {
                "host_local_acp_attempt_cleanup_requested": True,
                "host_local_acp_attempt_cleanup_raw_logs_read": False,
                "host_local_acp_attempt_cleanup_raw_command_recorded": False,
                "host_local_acp_attempt_cleanup_status": "terminated",
                "host_local_acp_attempt_cleanup_match_count": 3,
                "host_local_acp_attempt_cleanup_term_sent_count": 3,
                "host_local_acp_attempt_cleanup_kill_sent_count": 0,
                "host_local_acp_attempt_cleanup_alive_after_count": 0,
            },
        )
        assert job_name not in json.dumps(cleanup, sort_keys=True)
        assert rollout_name not in json.dumps(cleanup, sort_keys=True)


def test_independent_goal_retry_records_attempt_cleanup_after_exception() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-retry-cleanup-summary-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "bike-rebalance",
                "--route",
                "codex-app-server-goal-baseline",
                "--allow-deprecated-app-server-goal-route",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-bike-rebalance-independent-cleanup",
                "--independent-goal-retries",
                "2",
                "--host-local-acp-launch",
            ]
        )
        cleanup_calls: list[str] = []
        original_async_main = skillsbench_loop.async_main
        original_cleanup = skillsbench_loop.cleanup_host_local_acp_attempt_children

        async def fake_async_main(
            _args: Any,
            *,
            plan: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            raise RuntimeError("fixture runner exception")

        def fake_cleanup(plan_arg: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
            cleanup_calls.append(str(plan_arg.get("job_name") or ""))
            prereqs = plan_arg.setdefault("runner_prerequisites", {})
            prereqs.update(
                {
                    "host_local_acp_attempt_cleanup_requested": True,
                    "host_local_acp_attempt_cleanup_raw_logs_read": False,
                    "host_local_acp_attempt_cleanup_raw_command_recorded": False,
                    "host_local_acp_attempt_cleanup_status": "no_matching_processes",
                    "host_local_acp_attempt_cleanup_match_count": 0,
                    "host_local_acp_attempt_cleanup_term_sent_count": 0,
                    "host_local_acp_attempt_cleanup_kill_sent_count": 0,
                    "host_local_acp_attempt_cleanup_alive_after_count": 0,
                }
            )
            return {
                "schema_version": "skillsbench_host_local_acp_attempt_cleanup_v0",
                "requested": True,
                "raw_logs_read": False,
                "raw_command_recorded": False,
                "status": "no_matching_processes",
                "match_count": 0,
                "term_sent_count": 0,
                "kill_sent_count": 0,
                "alive_after_count": 0,
            }

        try:
            skillsbench_loop.async_main = fake_async_main
            skillsbench_loop.cleanup_host_local_acp_attempt_children = fake_cleanup
            summary = asyncio.run(skillsbench_loop.async_independent_goal_retry_main(args))
        finally:
            skillsbench_loop.async_main = original_async_main
            skillsbench_loop.cleanup_host_local_acp_attempt_children = original_cleanup

        assert summary["success_observed"] is False, summary
        assert summary["attempts_started"] == 2, summary
        assert len(cleanup_calls) == 2, cleanup_calls
        for attempt in summary["attempts"]:
            cleanup = attempt["host_local_acp_attempt_cleanup"]
            assert cleanup["requested"] is True, cleanup
            assert cleanup["raw_logs_read"] is False, cleanup
            assert cleanup["raw_command_recorded"] is False, cleanup
            assert cleanup["status"] == "no_matching_processes", cleanup
        summary_text = json.dumps(summary, sort_keys=True)
        assert "fixture runner exception" not in summary_text
        assert "/private/" not in summary_text


def test_skillsbench_reduce_only_missing_result_records_closeout_exit_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-missing-result-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "pddl-airport-planning",
                    "--route",
                    "codex-acp-blind-loop-baseline",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    "skillsbench-pddl-missing-result-fixture",
                    "--rollout-name",
                    "pddl-airport-planning__missing_result_fixture",
                    "--run-group-id",
                    "skillsbench-pddl-missing-result-fixture",
                    "--reduce-only",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        assert payload["ok"] is False, payload
        assert payload["error_recorded"] is True, payload
        assert payload["compact_closeout_recorded"] is True, payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        assert compact_path.exists(), payload
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["score_failure_attribution"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact


def test_skillsbench_reduce_only_discovers_nested_official_result() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-nested-result-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-pddl-nested-result-fixture"
        nested_run_dir = (
            jobs_dir
            / job_name
            / "jobs"
            / "2026-06-15__04-24-04"
            / "pddl-airport-planning__69640c62"
        )
        write_json(
            nested_run_dir / "result.json",
            {
                "task_name": "pddl-airport-planning",
                "rollout_name": "pddl-airport-planning__69640c62",
                "rewards": {"reward": 0.0},
                "agent": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 5,
                "n_prompts": 1,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(nested_run_dir / "timing.json", {"total": 12.0})
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "pddl-airport-planning",
                    "--route",
                    "codex-acp-blind-loop-baseline",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    job_name,
                    "--rollout-name",
                    "pddl-airport-planning__requested_rollout_fixture",
                    "--run-group-id",
                    "skillsbench-pddl-nested-result-fixture",
                    "--reduce-only",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        assert payload["ok"] is True, payload
        assert payload["result_discovery"]["status"] == "found", payload
        assert payload["result_discovery"]["selection_policy"] == (
            "planned_path_then_job_root_scan_best_match"
        ), payload
        assert payload["result_discovery"]["tie_breaker"] == (
            "highest_match_score_then_newest_mtime"
        ), payload
        assert "jobs/2026-06-15__04-24-04/pddl-airport-planning__69640c62" in (
            payload["result_discovery"]["selected_relative_to_job"]
        ), payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        assert compact_path.exists(), payload
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"]["value"] == 0.0, compact
        assert compact["result_discovery"]["status"] == "found", compact


def test_skillsbench_main_failure_closeout_preserves_mutated_prerequisites() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-main-prereq-closeout-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "bike-rebalance").mkdir(parents=True)

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "passed",
                    "codex_acp_runtime_launch_preflight_rc": 0,
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            raise RuntimeError("BenchFlow result.json not found")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "bike-rebalance",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        "skillsbench-prereq-closeout-fixture",
                        "--rollout-name",
                        "bike-rebalance__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-prereq-closeout-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        assert payload["compact_closeout_recorded"] is True, payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        prereq_path = (
            jobs_dir
            / "skillsbench-prereq-closeout-fixture"
            / RUNNER_PREREQUISITES_PUBLIC_FILENAME
        )
        assert prereq_path.exists(), payload
        persisted_prereqs = json.loads(prereq_path.read_text(encoding="utf-8"))
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_stage": (
                    "after_agent_install_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "passed",
                "codex_acp_runtime_launch_preflight_rc": 0,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            },
        )
        assert_prerequisites_include(
            persisted_prereqs,
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_status": "passed",
                "codex_acp_runtime_launch_preflight_rc": 0,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            },
        )


def test_skillsbench_main_recovers_official_result_after_runner_exception() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-result-recovery-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "tictoc-unnecessary-abort-detection").mkdir(parents=True)
        job_name = "skillsbench-result-recovery-fixture"
        exception_message = "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__codex_acp_blind_loop",
                    "rewards": {"reward": 0.0},
                    "agent": "codex-acp",
                    "agent_name": "codex-acp",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "idle_timeout",
                    "verifier_error": None,
                    "partial_trajectory": False,
                    "trajectory_source": "acp",
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError(exception_message)

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-result-recovery-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        assert stderr.getvalue() == "", stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        assert payload["ok"] is True, payload
        assert payload["recovered_after_runner_exception"] is True, payload
        assert payload["runner_exception_type"] == "RuntimeError", payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"]["value"] == 0.0, compact
        assert compact["runner_return_status"] == (
            "official_result_recovered_after_runner_exception"
        ), compact
        assert compact["result_recovery"] == {
            "exception_type": "RuntimeError",
            "official_result_json_materialized": True,
            "raw_exception_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_result_recovery_v0",
            "status": "official_result_recovered_after_runner_exception",
        }, compact
        assert exception_message not in json.dumps(payload), payload
        assert exception_message not in json.dumps(compact), compact


def test_skillsbench_main_recovers_missing_reward_with_structured_prereq_blocker() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-missing-reward-prereq-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "tictoc-unnecessary-abort-detection").mkdir(parents=True)
        job_name = "skillsbench-missing-reward-prereq-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "host_local_acp",
                    "host_local_acp_launch": True,
                    "host_local_acp_launch_status": "sandbox_install_failed",
                    "host_local_acp_install_stage": "deploy_skills",
                    "host_local_acp_install_failed_stage": "deploy_skills",
                    "container_codex_acp_install_skipped": True,
                    "codex_acp_runtime_container_bootstrap": False,
                    "codex_acp_runtime_dependency_preflight": False,
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "skipped",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "setup",
                    "verifier_error": None,
                    "partial_trajectory": False,
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                        "--run-group-id",
                        "skillsbench-missing-reward-prereq-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_host_local_acp_sandbox_install_failed"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_host_local_acp_sandbox_install_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_prerequisites"]["host_local_acp_install_stage"] == (
            "deploy_skills"
        ), compact
        assert compact["runner_prerequisites"][
            "host_local_acp_install_failed_stage"
        ] == "deploy_skills", compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_result_timeout_after_loopx_lifecycle_is_attributed() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-result-timeout-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        args = parse_args(
            [
                "--task-id",
                "powerlifting-coef-calc",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "skillsbench-result-timeout-fixture",
                "--rollout-name",
                "powerlifting-coef-calc__loopx_product_mode",
            ]
        )
        plan = build_plan(args)
        write_json(
            Path(plan["controller_trace_json"]),
            {
                "schema_version": "skillsbench_loopx_controller_trace_v0",
                "route": "loopx-product-mode",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "product_mode": True,
                "heartbeat_count": 1,
                "controller_action_decisions": 1,
                "initial_prompt_count": 1,
                "max_rounds_budget": 8,
                "max_round_observed": 0,
                "loopx_canonical_product_mode_lifecycle_driver": True,
                "case_goal_state_init_status": "passed",
                "case_goal_state_initialized_before_agent": True,
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
                "acp_trajectory_summary": {
                    "schema_version": "skillsbench_acp_trajectory_summary_v0",
                    "private_trajectory_present": True,
                    "raw_text_copied_to_public": False,
                    "event_count": 42,
                    "round_count": 1,
                    "user_message_count": 1,
                    "agent_message_count": 16,
                    "tool_call_count": 25,
                    "loopx_cli_call_count": 9,
                    "loopx_cli_state_read_count": 6,
                    "loopx_cli_state_write_count": 4,
                },
            },
        )
        result_path = Path(plan["result_json"])
        write_json(
            result_path,
            {
                "task_name": "powerlifting-coef-calc",
                "rollout_name": "powerlifting-coef-calc__loopx_product_mode",
                "rewards": None,
                "agent": "codex-acp",
                "agent_name": "",
                "model": "gpt-5.5",
                "n_tool_calls": 25,
                "n_prompts": 1,
                "error": "Command timed out after 10 seconds",
                "verifier_error": None,
                "partial_trajectory": True,
            },
        )
        write_json(result_path.with_name("timing.json"), {"agent_execution": 240.0})

        compact = reduce_result(args, result_path, plan)
        assert compact["official_score_status"] == "missing", compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_result_timeout_after_agent_round_no_reward_artifact"
        ), compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_result_timeout_after_agent_round_no_reward_artifact"
        ), compact
        assert "skillsbench_result_error_after_agent_round" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_reward_artifact_missing" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_controller_budget_not_exercised" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_result_error_cut_off_followup_loop" in compact[
            "failure_attribution_labels"
        ], compact
        assert "timeout" in compact["runner_failure_fingerprint"][
            "matched_patterns"
        ], compact
        assert "subprocess_command_timeout" in compact["runner_failure_fingerprint"][
            "matched_patterns"
        ], compact
        assert compact["runner_failure"]["controller_cutoff"] == {
            "schema_version": "skillsbench_controller_cutoff_v0",
            "cutoff_before_followup": True,
            "reason": "result_error_after_agent_round_no_reward_artifact",
            "max_rounds_budget": 8,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
        }, compact
        assert compact["interaction_counters"]["loopx_cli_call_count"] == 9, compact
        assert compact["interaction_counters"]["loopx_cli_state_write_count"] == 4, compact
        assert compact["interaction_counters"][
            "controller_budget_cutoff_before_followup"
        ] is True, compact
        assert compact["interaction_counters"]["controller_budget_cutoff_reason"] == (
            "result_error_after_agent_round_no_reward_artifact"
        ), compact


def test_skillsbench_user_loop_soft_verify_exception_continues_to_next_round() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-user-loop-soft-verify-") as tmp:
        rollout_dir = Path(tmp)
        plan = {"runner_prerequisites": {}}
        trace: dict[str, Any] = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
        }
        seen_rounds: list[tuple[int, str | None]] = []

        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user_module = types.ModuleType("benchflow.sandbox.user")

        class FakeRoundResult:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

        fake_user_module.RoundResult = FakeRoundResult
        old_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user_module

        class FakeUser:
            async def setup(self, instruction: str, solution: str | None) -> None:
                assert instruction == "fixture instruction"
                assert solution is None

            async def run(
                self,
                round: int,
                instruction: str,
                round_result: Any | None = None,
            ) -> str | None:
                assert instruction == "fixture instruction"
                seen_rounds.append(
                    (
                        round,
                        getattr(round_result, "verifier_error", None)
                        if round_result is not None
                        else None,
                    )
                )
                if round == 0:
                    return "continue without verifier feedback"
                return None

        class FakeRole:
            pass

        class FakeScene:
            roles = [FakeRole()]

        class FakeConfig:
            user = FakeUser()
            effective_scenes = [FakeScene()]
            oracle_access = False
            max_user_rounds = 3

        class FakeRollout:
            async def _run_user_loop(self) -> None:
                raise AssertionError("original user loop should be patched")

            def __init__(self) -> None:
                self._config = FakeConfig()
                self._resolved_prompts = ["fixture instruction"]
                self._trajectory: list[dict[str, Any]] = []
                self._rollout_dir = rollout_dir
                self.connected = False
                self.disconnected = False

            async def connect_as(self, role: Any) -> None:
                self.connected = True

            async def execute(self, prompts: list[str] | None = None) -> None:
                assert prompts == ["continue without verifier feedback"]
                self._trajectory.extend(
                    [
                        {"type": "agent_message"},
                        {"type": "tool_call"},
                    ]
                )

            async def disconnect(self) -> None:
                self.disconnected = True

            async def soft_verify(self) -> tuple[dict | None, str | None, str | None]:
                raise TimeoutError("PRIVATE_PATH_SHOULD_NOT_ESCAPE")

        try:
            original = install_benchflow_user_loop_final_verify_recovery(
                FakeRollout,
                plan=plan,
                trace=trace,
            )
            fake_rollout = FakeRollout()
            asyncio.run(FakeRollout._run_user_loop(fake_rollout))
            FakeRollout._run_user_loop = original
        finally:
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        prerequisites = plan["runner_prerequisites"]
        assert fake_rollout.connected is True
        assert fake_rollout.disconnected is True
        assert prerequisites["benchflow_user_loop_final_verify_recovery_enabled"] is True
        assert (
            prerequisites.get("benchflow_user_loop_final_verify_recovery_triggered")
            is not True
        )
        assert (
            prerequisites["benchflow_user_loop_soft_verify_exception_continued"]
            is True
        )
        assert prerequisites["benchflow_user_loop_soft_verify_exception_stage"] == (
            "soft_verify"
        )
        assert prerequisites["benchflow_user_loop_soft_verify_exception_type"] == (
            "TimeoutError"
        )
        assert prerequisites["benchflow_user_loop_soft_verify_exception_count"] == 1
        assert prerequisites["benchflow_user_loop_soft_verify_exception_round"] == 0
        assert (
            prerequisites["benchflow_user_loop_soft_verify_exception_delta_events"]
            == 2
        )
        assert (
            prerequisites[
                "benchflow_user_loop_soft_verify_exception_delta_tool_calls"
            ]
            == 1
        )
        assert (
            prerequisites[
                "benchflow_user_loop_soft_verify_exception_raw_error_recorded"
            ]
            is False
        )
        assert seen_rounds == [
            (0, None),
            (1, "public_safe_soft_verify_exception_after_agent_round"),
        ]
        rounds_log = (rollout_dir / "user_rounds.jsonl").read_text(encoding="utf-8")
        assert "public_safe_soft_verify_exception_after_agent_round" in rounds_log
        assert "PRIVATE_PATH_SHOULD_NOT_ESCAPE" not in rounds_log


def test_skillsbench_user_loop_no_tool_execute_exception_continues_to_next_round() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-user-loop-no-tool-") as tmp:
        rollout_dir = Path(tmp)
        plan = {"runner_prerequisites": {}}
        trace: dict[str, Any] = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
        }
        seen_rounds: list[tuple[int, str | None]] = []

        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user_module = types.ModuleType("benchflow.sandbox.user")

        class FakeRoundResult:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

        fake_user_module.RoundResult = FakeRoundResult
        old_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user_module

        class FakeUser:
            async def setup(self, instruction: str, solution: str | None) -> None:
                assert instruction == "fixture instruction"
                assert solution is None

            async def run(
                self,
                round: int,
                instruction: str,
                round_result: Any | None = None,
            ) -> str | None:
                seen_rounds.append(
                    (
                        round,
                        getattr(round_result, "verifier_error", None)
                        if round_result is not None
                        else None,
                    )
                )
                if round == 0:
                    return "first attempt"
                return None

        class FakeRole:
            pass

        class FakeScene:
            roles = [FakeRole()]

        class FakeConfig:
            user = FakeUser()
            effective_scenes = [FakeScene()]
            oracle_access = False
            max_user_rounds = 3

        class FakeRollout:
            async def _run_user_loop(self) -> None:
                raise AssertionError("original user loop should be patched")

            def __init__(self) -> None:
                self._config = FakeConfig()
                self._resolved_prompts = ["fixture instruction"]
                self._trajectory: list[dict[str, Any]] = []
                self._rollout_dir = rollout_dir
                self.connected = False
                self.disconnected = False
                self.soft_verify_called = 0

            async def connect_as(self, role: Any) -> None:
                self.connected = True

            async def execute(self, prompts: list[str] | None = None) -> None:
                assert prompts == ["first attempt"]
                self._trajectory.extend(
                    [
                        {"type": "user_message"},
                        {"type": "agent_message"},
                    ]
                )
                raise TimeoutError("PRIVATE_PATH_SHOULD_NOT_ESCAPE")

            async def disconnect(self) -> None:
                self.disconnected = True

            async def soft_verify(self) -> tuple[dict | None, str | None, str | None]:
                self.soft_verify_called += 1
                raise AssertionError("soft verify must not run after no-tool execute exception")

        try:
            original = install_benchflow_user_loop_final_verify_recovery(
                FakeRollout,
                plan=plan,
                trace=trace,
            )
            fake_rollout = FakeRollout()
            asyncio.run(FakeRollout._run_user_loop(fake_rollout))
            FakeRollout._run_user_loop = original
        finally:
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        prerequisites = plan["runner_prerequisites"]
        assert fake_rollout.connected is True
        assert fake_rollout.disconnected is True
        assert fake_rollout.soft_verify_called == 0
        assert (
            prerequisites.get("benchflow_user_loop_final_verify_recovery_triggered")
            is not True
        )
        assert prerequisites["benchflow_user_loop_no_tool_exception_continued"] is True
        assert prerequisites["benchflow_user_loop_no_tool_exception_stage"] == (
            "agent_execute"
        )
        assert prerequisites["benchflow_user_loop_no_tool_exception_type"] == (
            "TimeoutError"
        )
        assert prerequisites["benchflow_user_loop_no_tool_exception_count"] == 1
        assert prerequisites["benchflow_user_loop_no_tool_exception_round"] == 0
        assert prerequisites["benchflow_user_loop_no_tool_exception_delta_events"] == 2
        assert prerequisites["benchflow_user_loop_no_tool_exception_delta_tool_calls"] == 0
        assert (
            prerequisites["benchflow_user_loop_no_tool_exception_raw_error_recorded"]
            is False
        )
        assert seen_rounds == [
            (0, None),
            (1, "public_safe_agent_execute_exception_before_tool_activity"),
        ]
        rounds_log = (rollout_dir / "user_rounds.jsonl").read_text(encoding="utf-8")
        assert "public_safe_agent_execute_exception_before_tool_activity" in rounds_log
        assert "PRIVATE_PATH_SHOULD_NOT_ESCAPE" not in rounds_log


def test_skillsbench_product_mode_can_skip_intermediate_soft_verify() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-soft-verify-policy-") as tmp:
        rollout_dir = Path(tmp)
        plan = {"runner_prerequisites": {}}
        trace: dict[str, Any] = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
        }

        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user_module = types.ModuleType("benchflow.sandbox.user")

        class FakeRoundResult:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

        fake_user_module.RoundResult = FakeRoundResult
        old_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user_module

        class FakeUser:
            async def setup(self, instruction: str, solution: str | None) -> None:
                assert instruction == "fixture instruction"
                assert solution is None

            async def run(
                self,
                round: int,
                instruction: str,
                round_result: Any | None = None,
            ) -> str | None:
                if round == 0:
                    assert round_result is None
                    return "continue without verifier feedback"
                assert round_result is not None
                assert round_result.rewards is None
                assert round_result.verifier_output is None
                assert round_result.verifier_error is None
                return None

        class FakeRole:
            pass

        class FakeScene:
            roles = [FakeRole()]

        class FakeConfig:
            user = FakeUser()
            effective_scenes = [FakeScene()]
            oracle_access = False
            max_user_rounds = 2

        class FakeRollout:
            async def _run_user_loop(self) -> None:
                raise AssertionError("original user loop should be patched")

            def __init__(self) -> None:
                self._config = FakeConfig()
                self._resolved_prompts = ["fixture instruction"]
                self._trajectory: list[dict[str, Any]] = []
                self._rollout_dir = rollout_dir
                self.soft_verify_called = 0

            async def connect_as(self, role: Any) -> None:
                return None

            async def execute(self, prompts: list[str] | None = None) -> None:
                assert prompts == ["continue without verifier feedback"]
                self._trajectory.append({"type": "tool_call"})

            async def disconnect(self) -> None:
                return None

            async def soft_verify(self) -> tuple[dict | None, str | None, str | None]:
                self.soft_verify_called += 1
                raise AssertionError("intermediate soft_verify must be skipped")

        try:
            original = install_benchflow_user_loop_final_verify_recovery(
                FakeRollout,
                plan=plan,
                trace=trace,
                intermediate_soft_verify_policy="final-only",
            )
            fake_rollout = FakeRollout()
            asyncio.run(FakeRollout._run_user_loop(fake_rollout))
            FakeRollout._run_user_loop = original
        finally:
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        prerequisites = plan["runner_prerequisites"]
        assert fake_rollout.soft_verify_called == 0
        assert prerequisites["benchflow_intermediate_soft_verify_policy"] == (
            "final-only"
        )
        assert prerequisites["benchflow_intermediate_soft_verify_final_only"] is True
        assert prerequisites["benchflow_intermediate_soft_verify_call_count"] == 0
        assert prerequisites["benchflow_intermediate_soft_verify_skipped_count"] == 1
        assert (
            prerequisites["benchflow_intermediate_soft_verify_raw_output_recorded"]
            is False
        )
        assert trace["benchflow_intermediate_soft_verify_skipped_count"] == 1
        rounds = [
            json.loads(line)
            for line in (rollout_dir / "user_rounds.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert rounds[0]["soft_verify_policy"] == "final-only"
        assert rounds[0]["soft_verify_skipped"] is True
        assert "intermediate soft_verify must be skipped" not in json.dumps(rounds)


def test_skillsbench_final_verify_timeout_after_user_loop_recovery_is_attributed() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-final-verify-timeout-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        args = parse_args(
            [
                "--task-id",
                "citation-check",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "skillsbench-final-verify-timeout-fixture",
                "--rollout-name",
                "citation-check__loopx_product_mode",
            ]
        )
        plan = build_plan(args)
        write_json(
            Path(plan["controller_trace_json"]),
            {
                "schema_version": "skillsbench_loopx_controller_trace_v0",
                "route": "loopx-product-mode",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "product_mode": True,
                "heartbeat_count": 1,
                "controller_action_decisions": 1,
                "initial_prompt_count": 1,
                "max_rounds_budget": 8,
                "max_round_observed": 0,
                "benchflow_user_loop_final_verify_recovery_triggered": True,
                "benchflow_user_loop_recovery_after_agent_activity": True,
                "benchflow_user_loop_recovery_preserved_final_verify": True,
                "benchflow_user_loop_recovery_raw_error_recorded": False,
                "benchflow_user_loop_recovery_stage": "soft_verify",
                "benchflow_user_loop_recovery_exception_type": "RuntimeError",
                "benchflow_user_loop_recovery_round": 0,
                "benchflow_user_loop_recovery_delta_events": 40,
                "benchflow_user_loop_recovery_delta_tool_calls": 27,
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
                "acp_trajectory_summary": {
                    "schema_version": "skillsbench_acp_trajectory_summary_v0",
                    "private_trajectory_present": True,
                    "raw_text_copied_to_public": False,
                    "event_count": 40,
                    "round_count": 1,
                    "user_message_count": 1,
                    "agent_message_count": 12,
                    "tool_call_count": 27,
                    "loopx_cli_call_count": 8,
                    "loopx_cli_state_read_count": 3,
                    "loopx_cli_state_write_count": 5,
                },
            },
        )
        result_path = Path(plan["result_json"])
        write_json(
            result_path,
            {
                "task_name": "citation-check",
                "rollout_name": "citation-check__loopx_product_mode",
                "rewards": None,
                "agent": "codex-acp",
                "agent_name": "",
                "model": "gpt-5.5",
                "n_tool_calls": 27,
                "n_prompts": 1,
                "error": "Command timed out after 10 seconds",
                "verifier_error": None,
                "partial_trajectory": False,
            },
        )
        write_json(result_path.with_name("timing.json"), {"agent_execution": 240.0})

        compact = reduce_result(args, result_path, plan)
        expected = (
            "skillsbench_final_verify_timeout_after_user_loop_recovery_no_reward_artifact"
        )
        assert compact["score_failure_attribution"] == expected, compact
        assert compact["runner_failure"]["failure_class"] == expected, compact
        assert expected in compact["failure_attribution_labels"], compact
        assert "skillsbench_controller_budget_not_exercised" not in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["user_loop_recovery"] == {
            "schema_version": "skillsbench_user_loop_recovery_v0",
            "preserved_final_verify": True,
            "stage": "soft_verify",
            "exception_type": "runtimeerror",
            "round": 0,
            "delta_events": 40,
            "delta_tool_calls": 27,
            "raw_error_recorded": False,
        }, compact
        assert compact["interaction_counters"][
            "benchflow_user_loop_final_verify_recovery_triggered"
        ] is True
        assert compact["interaction_counters"][
            "benchflow_user_loop_recovery_raw_error_recorded"
        ] is False


def test_skillsbench_verifier_prep_timeout_override_is_public_safe() -> None:
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}

    class ExecResult:
        stdout = ""
        stderr = ""
        return_code = 0

    class FakeEnv:
        def __init__(self) -> None:
            self.timeouts: list[int | None] = []

        async def exec(self, _command: str, **kwargs: Any) -> ExecResult:
            self.timeouts.append(kwargs.get("timeout_sec"))
            return ExecResult()

    class FakeRollout:
        def __init__(self) -> None:
            self._env = FakeEnv()

        async def verify(self) -> dict[str, float]:
            await self._env.exec("mkdir -p /logs/agent", timeout_sec=10)
            await self._env.exec("official verifier body", timeout_sec=99)
            return {"score": 1.0}

        async def soft_verify(self) -> tuple[None, None, None]:
            await self._env.exec("rm -rf /logs/verifier", timeout_sec=10)
            return None, None, None

    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        plan=plan,
        trace=trace,
    )
    try:
        fake_rollout = FakeRollout()
        assert asyncio.run(FakeRollout.verify(fake_rollout)) == {"score": 1.0}
        assert asyncio.run(FakeRollout.soft_verify(fake_rollout)) == (
            None,
            None,
            None,
        )
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert fake_rollout._env.timeouts == [120, 99, 120]
    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["benchflow_verifier_prep_timeout_override_enabled"] is True
    assert prerequisites["benchflow_verifier_prep_timeout_sec"] == 120
    assert prerequisites["benchflow_verifier_prep_timeout_override_count"] == 2
    assert prerequisites["benchflow_verify_prep_timeout_override_count"] == 1
    assert prerequisites["benchflow_soft_verify_prep_timeout_override_count"] == 1
    assert prerequisites["benchflow_verifier_prep_timeout_raw_command_recorded"] is False
    assert "mkdir -p" not in json.dumps(prerequisites)
    assert trace["benchflow_verifier_prep_timeout_override_count"] == 2


def test_skillsbench_main_marks_empty_acp_trajectory_after_host_install() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-empty-acp-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "tictoc-unnecessary-abort-detection").mkdir(parents=True)
        job_name = "skillsbench-empty-acp-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "host_local_acp",
                    "host_local_acp_launch": True,
                    "host_local_acp_launch_status": "sandbox_installed",
                    "host_local_acp_install_stage": "sandbox_installed",
                    "container_codex_acp_install_skipped": True,
                    "codex_acp_runtime_container_bootstrap": False,
                    "codex_acp_runtime_dependency_preflight": False,
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "skipped",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            write_json(
                Path(plan["controller_trace_json"]),
                {
                    "schema_version": "skillsbench_loopx_controller_trace_v0",
                    "route": "codex-acp-blind-loop-baseline",
                    "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                    "heartbeat_count": 1,
                    "controller_action_decisions": 1,
                    "initial_prompt_count": 1,
                    "round_rewards": [
                        {
                            "agent_round": 1,
                            "reward_present": False,
                            "passed": False,
                        }
                    ],
                    "official_success_observed": False,
                    "raw_task_text_recorded": False,
                    "raw_verifier_output_recorded": False,
                    "raw_agent_trajectory_recorded": False,
                    "acp_trajectory_summary": {
                        "schema_version": "skillsbench_acp_trajectory_summary_v0",
                        "private_trajectory_present": True,
                        "raw_text_copied_to_public": False,
                        "event_count": 0,
                        "round_count": 0,
                        "user_message_count": 0,
                        "agent_message_count": 0,
                        "tool_call_count": 0,
                        "codex_acp_text_present": False,
                        "codex_acp_text_bytes": 0,
                    },
                },
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "setup",
                    "verifier_error": None,
                    "partial_trajectory": False,
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                        "--run-group-id",
                        "skillsbench-empty-acp-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["runner_prerequisites"]["host_local_acp_launch_status"] == (
            "sandbox_installed"
        ), compact
        assert compact["interaction_counters"]["private_trajectory_event_count"] == 0
        assert compact["score_failure_attribution"] == (
            "skillsbench_host_local_acp_empty_trajectory_after_install"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_host_local_acp_empty_trajectory_after_install"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_main_marks_agent_message_only_no_tool_calls() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-agent-message-only-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "tictoc-unnecessary-abort-detection").mkdir(parents=True)
        job_name = "skillsbench-agent-message-only-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "container_local_acp",
                    "container_codex_acp_install_skipped": False,
                    "codex_acp_runtime_container_bootstrap": True,
                    "codex_acp_runtime_dependency_preflight": True,
                    "codex_acp_runtime_launch_preflight": False,
                    "codex_acp_runtime_launch_preflight_stage": (
                        "after_agent_install_before_acp_connect"
                    ),
                    "codex_acp_runtime_launch_preflight_status": "pending",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            write_json(
                Path(plan["controller_trace_json"]),
                {
                    "schema_version": "skillsbench_loopx_controller_trace_v0",
                    "route": "codex-acp-blind-loop-baseline",
                    "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                    "heartbeat_count": 2,
                    "controller_action_decisions": 2,
                    "initial_prompt_count": 1,
                    "followup_prompt_count": 1,
                    "round_rewards": [
                        {
                            "agent_round": 1,
                            "reward_present": False,
                            "passed": False,
                        },
                        {
                            "agent_round": 2,
                            "reward_present": False,
                            "passed": False,
                        },
                    ],
                    "official_success_observed": False,
                    "raw_task_text_recorded": False,
                    "raw_verifier_output_recorded": False,
                    "raw_agent_trajectory_recorded": False,
                    "acp_trajectory_summary": {
                        "schema_version": "skillsbench_acp_trajectory_summary_v0",
                        "private_trajectory_present": True,
                        "raw_text_copied_to_public": False,
                        "event_count": 4,
                        "round_count": 2,
                        "user_message_count": 2,
                        "agent_message_count": 2,
                        "tool_call_count": 0,
                        "codex_acp_text_present": False,
                        "codex_acp_text_bytes": 0,
                    },
                },
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "codex-acp",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 2,
                    "error": "compact-safe official runner error",
                    "error_category": "agent_behavior",
                    "verifier_error": None,
                    "partial_trajectory": False,
                    "trajectory_source": "acp",
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__loopx_blind_loop",
                        "--run-group-id",
                        "skillsbench-agent-message-only-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["interaction_counters"]["private_trajectory_event_count"] == 4
        assert compact["interaction_counters"]["private_trajectory_tool_call_count"] == 0
        assert compact["score_failure_attribution"] == (
            "skillsbench_acp_agent_message_only_no_tool_calls"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_acp_agent_message_only_no_tool_calls"
        ), compact
        assert "skillsbench_agent_behavior_gap" in compact[
            "failure_attribution_labels"
        ], compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_main_redirects_runner_output_to_private_log() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-private-runner-output-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        skillsbench_root = Path(tmp) / "skillsbench"
        (skillsbench_root / "tasks" / "private-output-fixture").mkdir(parents=True)
        job_name = "skillsbench-private-output-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, _plan: dict[str, Any]) -> Path:
            print("PRIVATE_BENCHFLOW_STDOUT_MARKER")
            print("PRIVATE_BENCHFLOW_STDERR_MARKER", file=sys.stderr)
            raise RuntimeError("Docker compose command failed for environment fixture")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "private-output-fixture",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "private-output-fixture__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-private-output-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in stdout.getvalue()
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in stderr.getvalue()
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in stdout.getvalue()
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["runner_output_capture"] == {
            "schema_version": "skillsbench_runner_output_capture_v0",
            "enabled": True,
            "stdout_stderr_redirected": True,
            "raw_output_public": False,
            "private_log_path_public": False,
        }, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "runner-output.private.log" not in compact_text, compact
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in compact_text, compact
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in compact_text, compact
        private_log = jobs_dir / job_name / "runner-output.private.log"
        private_log_text = private_log.read_text(encoding="utf-8")
        assert "begin private BenchFlow stdout/stderr capture" in private_log_text
        assert "end private BenchFlow stdout/stderr capture" in private_log_text
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" in private_log_text
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" in private_log_text


def test_skillsbench_reduce_only_preserves_round_reward_trace() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-round-reward-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-round-trace-fixture"
        rollout_name = "sample-task__loopx_blind_loop"
        run_dir = jobs_dir / job_name / rollout_name
        write_json(
            run_dir / "result.json",
            {
                "task_name": "sample-task",
                "rollout_name": rollout_name,
                "rewards": {"reward": 1.0},
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 9,
                "n_prompts": 2,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(run_dir / "timing.json", {"total": 3.0})
        write_json(
            jobs_dir / job_name / "loopx_controller_trace.public.json",
            {
                "schema_version": "skillsbench_loopx_controller_trace_v0",
                "route": "loopx-blind-loop-treatment",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "heartbeat_count": 3,
                "controller_action_decisions": 3,
                "initial_prompt_count": 1,
                "followup_prompt_count": 1,
                "stop_decision_count": 1,
                "reward_observation_count": 2,
                "verifier_feedback_observation_count": 0,
                "official_feedback_blinded_count": 2,
                "round_rewards": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                    },
                    {
                        "agent_round": 2,
                        "reward_present": True,
                        "reward": 1.0,
                        "passed": True,
                    },
                ],
                "official_success_observed": True,
                "official_success_observation_count": 1,
                "first_success_round": 2,
                "official_feedback_forwarded": False,
                "blind_loop": True,
                "max_rounds_budget": 2,
                "last_decision": (
                    "stop_after_blind_loop_official_success_observed_without_feedback"
                ),
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "sample-task",
                    "--route",
                    "loopx-blind-loop-treatment",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    job_name,
                    "--rollout-name",
                    rollout_name,
                    "--ledger-path",
                    str(Path(tmp) / "ledger.json"),
                    "--skip-ledger-inherit",
                    "--skip-global-ledger-sync",
                    "--reduce-only",
                    "--update-ledger",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["historical_route_read_only"] is True, compact
        assert compact["skillsbench_route_semantics"] == "historical_nonproduct_invalid_for_comparison", compact
        assert compact["official_score_comparable_to_loopx_treatment"] is False
        round_trace = compact["round_reward_trace"]
        assert round_trace["first_success_round"] == 2, compact
        assert [item["reward"] for item in round_trace["records"]] == [0.0, 1.0], compact
        assert round_trace["records"][1]["passed"] is True, compact
        entry = payload["ledger_update"]["primary_ledger_update"]["entry"]
        ledger = load_benchmark_run_ledger(Path(tmp) / "ledger.json")
        runs = ledger["benchmarks"]["skillsbench@1.1"]["cases"]["sample-task"]["runs"]
        run = next(item for item in runs if item["run_id"] == entry["run_id"])
        assert run["round_reward_count"] == 2, run
        assert run["round_success_observed"] is True, run
        assert [item["reward"] for item in run["round_rewards"]] == [0.0, 1.0], run
        assert run["first_success_round"] == 2, run


def test_skillsbench_reduce_only_preserves_persisted_public_prerequisites() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-prereq-reduce-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-prereq-reduce-fixture"
        rollout_name = "sample-task__loopx_product_mode"
        run_dir = jobs_dir / job_name / rollout_name
        write_json(
            run_dir / "result.json",
            {
                "task_name": "sample-task",
                "rollout_name": rollout_name,
                "rewards": {"reward": 0.0},
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 0,
                "n_prompts": 1,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(run_dir / "timing.json", {"total": 4.0})
        write_json(
            jobs_dir / job_name / RUNNER_PREREQUISITES_PUBLIC_FILENAME,
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "agent_execution_mode": "host_local_acp",
                "host_local_acp_launch": True,
                "host_local_acp_launch_status": "sandbox_installed",
                "codex_acp_runtime_container_bootstrap": False,
                "codex_acp_runtime_dependency_preflight": False,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_status": "skipped",
                "remote_command_file_bridge_consumed_by_solver": True,
                "remote_command_file_bridge_agent_request_count": 2,
                "remote_command_file_bridge_agent_loopx_cli_call_count": 6,
                "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
                "filtered_extra_marker": "FILTERED_PREREQ_MARKER_MUST_NOT_ESCAPE",
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "sample-task",
                    "--route",
                    "loopx-product-mode",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    job_name,
                    "--rollout-name",
                    rollout_name,
                    "--ledger-path",
                    str(Path(tmp) / "ledger.json"),
                    "--skip-ledger-inherit",
                    "--skip-global-ledger-sync",
                    "--reduce-only",
                    "--update-ledger",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        prereqs = compact["runner_prerequisites"]
        assert_prerequisites_include(
            prereqs,
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "agent_execution_mode": "host_local_acp",
                "host_local_acp_launch": True,
                "host_local_acp_launch_status": "sandbox_installed",
                "codex_acp_runtime_container_bootstrap": False,
                "codex_acp_runtime_dependency_preflight": False,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_status": "skipped",
                "remote_command_file_bridge_consumed_by_solver": True,
                "remote_command_file_bridge_agent_request_count": 2,
                "remote_command_file_bridge_agent_loopx_cli_call_count": 6,
                "remote_command_file_bridge_agent_task_facing_operation_count": 1,
            "remote_command_file_bridge_agent_task_facing_success_count": 1,
                "reduce_only_prerequisites_source": "persisted_public_job_artifact",
                "reduce_only_prerequisites_artifact_read": True,
            },
        )
        compact_text = json.dumps(compact, sort_keys=True)
        assert "container_codex_acp" not in compact_text, compact
        assert "FILTERED_PREREQ_MARKER_MUST_NOT_ESCAPE" not in compact_text, compact


if __name__ == "__main__":
    test_skillsbench_default_route_is_goal_baseline()
    test_codex_app_server_goal_requires_public_safe_codex_api_tunnel_contract()
    test_generic_reasoning_effort_reaches_codex_exec_route()
    test_codex_exec_relay_maps_reasoning_effort_to_cli_config()
    test_codex_app_server_goal_rejects_non_http_codex_api_proxy_scheme()
    test_codex_app_server_goal_blocks_without_codex_api_egress()
    test_benchmark_egress_proxy_env_is_public_safe_and_forwarded()
    test_benchmark_egress_proxy_require_mode_blocks_without_proxy()
    test_benchmark_egress_proxy_auto_falls_back_to_direct_without_leaking_proxy()
    test_benchmark_egress_proxy_auto_ignores_shell_placeholder()
    test_benchmark_egress_proxy_require_blocks_shell_placeholder()
    test_skillsbench_plan_only_batch_parallel_case_contract()
    test_skillsbench_batch_case_cli_filters_internal_aggregate_flag()
    test_skillsbench_formal_product_mode_rejects_tiny_round_budget()
    test_skillsbench_product_mode_soft_verify_default_is_every_round()
    test_skillsbench_turn_uses_final_only_soft_verify()
    test_reverse_channel_first_action_timeout_stops_codex_process()
    test_reverse_channel_timeout_survives_blocked_stdin_write()
    test_reverse_channel_raw_prompt_does_not_require_bridge_first_action()
    test_reverse_channel_bridge_idle_waits_for_bridge_activity()
    test_reverse_channel_bridge_operation_failure_is_categorized()
    test_host_local_codex_exec_preflight_requires_successful_bridge_action()
    test_reverse_channel_product_mode_checkpoint_requires_bridge_first_action()
    test_reverse_channel_bridge_idle_timeout_stops_codex_process()
    test_product_mode_initial_prompt_keeps_task_visible_after_lifecycle_gate()
    test_skillsbench_final_verifier_timeout_override_records_public_state()
    test_skillsbench_final_verifier_timeout_override_can_extend_timeout()
    test_skillsbench_intermediate_soft_verifier_timeout_override_records_public_state()
    test_skillsbench_intermediate_soft_verifier_timeout_is_independent()
    test_skillsbench_intermediate_soft_verifier_timeout_triggers_cleanup()
    test_skillsbench_intermediate_soft_verifier_phase_timeout_bounds_hung_exec()
    test_skillsbench_final_verifier_phase_timeout_bounds_hung_exec()
    test_skillsbench_intermediate_soft_verifier_return_cleans_orphan_processes()
    test_skillsbench_host_local_attempt_cleanup_targets_current_attempt_only()
    test_independent_goal_retry_records_attempt_cleanup_after_exception()
    test_skillsbench_local_driver_a2a_contract_keeps_codex_local()
    test_skillsbench_local_driver_a2a_contract_ready_only_after_both_sides()
    test_skillsbench_local_driver_a2a_contract_distinguishes_cli_from_handshake()
    test_skillsbench_worker_handshake_preflight_exposes_acp_relay_gap()
    test_skillsbench_worker_handshake_preflight_distinguishes_host_transport()
    test_skillsbench_worker_handshake_preflight_distinguishes_remote_bridge()
    test_skillsbench_remote_command_file_bridge_probe_requires_command()
    test_skillsbench_remote_command_file_bridge_probe_fake_bridge_ready()
    test_skillsbench_remote_command_file_bridge_probe_preserves_response_blocker()
    test_skillsbench_worker_handshake_preflight_accepts_bridge_probe()
    test_skillsbench_local_acp_relay_probe_completes_stdio_handshake()
    test_skillsbench_host_local_acp_transport_probe_uses_benchflow_client()
    test_skillsbench_worker_handshake_preflight_probe_clears_relay_gap()
    test_skillsbench_worker_handshake_preflight_missing_runtime_is_compact()
    test_local_codex_participant_ping_missing_binary_is_compact()
    test_blind_loop_continuation_reprojects_round_one_constraints()
    test_product_mode_declared_done_marker_detection()
    test_product_mode_declared_done_ignores_user_prompt_marker()
    test_skillsbench_codex_exec_failure_category_is_actionable()
    test_host_local_relay_timeout_returns_recoverable_turn_message()
    test_product_mode_case_state_seed_uses_active_goal_shape()
    test_product_mode_declared_done_requires_case_state_depth()
    test_product_mode_declared_done_requires_solver_activity_after_driver_lifecycle()
    test_product_mode_declared_done_runs_one_typed_repair_then_stops_without_delta()
    test_app_server_goal_round_semantics_survive_compact_and_ledger()
    test_product_mode_closeout_without_done_does_not_trigger_typed_repair()
    test_product_mode_declared_done_missing_reward_continues()
    test_product_mode_missing_lifecycle_prompts_exact_checkpoint()
    test_product_mode_no_tool_call_continues_before_checkpoint_loop()
    test_product_mode_workflow_driver_task_bridge_activity_avoids_no_tool_abort()
    test_product_mode_official_success_stops_without_final_closeout_checkpoint()
    test_skillsbench_skeleton_builder()
    test_skillsbench_official_result_builder()
    test_skillsbench_result_reward_artifact_recovery()
    test_skillsbench_oracle_result_reward_artifact_recovery()
    test_skillsbench_app_mount_failure_attribution()
    test_skillsbench_app_skills_failure_attribution()
    test_skillsbench_app_skills_permission_failure_not_overridden_by_worker_route()
    test_skillsbench_docker_port_conflict_attribution()
    test_skillsbench_docker_apt_failure_attribution()
    test_skillsbench_docker_daemon_unavailable_attribution()
    test_skillsbench_unclassified_compose_failure_fingerprint()
    test_skillsbench_codex_acp_libssl_failure_attribution()
    test_skillsbench_codex_acp_glibc_failure_attribution()
    test_skillsbench_codex_acp_launch_preflight_attribution()
    test_skillsbench_codex_acp_internal_error_attribution()
    test_skillsbench_codex_acp_provider_zero_activity_attribution()
    test_skillsbench_no_tool_postprocess_preserves_provider_zero_activity()
    test_skillsbench_no_tool_postprocess_preserves_agent_bridge_activity()
    test_skillsbench_codex_acp_post_success_trace_recovers_score()
    test_skillsbench_codex_acp_post_success_finalization_route()
    test_skillsbench_docker_task_staging_adds_app_skills_mount()
    test_skillsbench_no_skill_route_removes_staged_task_skills()
    test_skillsbench_docker_task_staging_adds_apt_retry_patch()
    test_skillsbench_docker_task_staging_apt_retry_is_nonroot_safe()
    test_skillsbench_docker_task_staging_rewrites_gcr_oss_fuzz_base()
    test_skillsbench_docker_task_staging_hardens_elan_toolchain_install()
    test_skillsbench_docker_task_staging_rewrites_wget_gpg_key_download()
    test_skillsbench_docker_task_staging_hardens_build_downloads()
    test_skillsbench_docker_task_staging_patches_dockerfile_uv_bootstrap()
    test_skillsbench_runtime_tools_patch_has_own_apt_retry_defaults()
    test_skillsbench_docker_task_staging_patches_verifier_uv_bootstrap_mirror()
    test_skillsbench_docker_task_staging_forwards_proxy_to_verifier_bootstrap()
    test_skillsbench_apt_risk_preflight_blocks_full_run_without_benchflow()
    test_skillsbench_verifier_bootstrap_preflight_blocks_full_run_without_benchflow()
    test_skillsbench_docker_task_staging_caps_local_cpu_request()
    test_skillsbench_volume_mount_failure_attribution()
    test_skillsbench_runner_plan_supports_baseline_route()
    test_skillsbench_runner_plan_supports_product_mode_routes()
    test_loopx_product_mode_full_run_requires_canonical_driver()
    test_loopx_case_init_failure_blocker_is_public_safe()
    test_loopx_case_state_seed_runs_after_host_local_sandbox_install()
    test_loopx_source_mount_contract_uses_real_cli_source_not_local_installer()
    test_host_local_product_mode_uses_source_upload_not_docker_bind_mount()
    test_host_local_product_mode_auto_bridge_keeps_lifecycle_checkpoint_args()
    test_host_local_acp_connect_contract_matches_benchflow_runtime()
    test_loopx_source_upload_subset_is_public_safe_and_minimal()
    test_remote_bridge_auto_wiring_pending_is_not_final_failure_attribution()
    test_skillsbench_codex_acp_model_control_warning()
    test_skillsbench_runner_prerequisites_are_compacted()
    test_skillsbench_case_event_timeline_is_compacted()
    test_skillsbench_task_staging_metadata_is_compacted()
    test_skillsbench_reduce_only_recovers_prepared_task_staging_metadata()
    test_skillsbench_controller_trace_counts_are_compacted()
    test_skillsbench_product_mode_declared_done_is_compacted()
    test_skillsbench_product_mode_lifecycle_checkpoint_is_compacted()
    test_skillsbench_product_mode_recompact_normalizes_agent_bridge_closeout()
    test_skillsbench_solution_quality_labels_partial_nonpass()
    test_skillsbench_agent_bridge_closeout_requires_successful_commands()
    test_skillsbench_product_mode_recompact_prefers_corroborated_solver_gap()
    test_skillsbench_product_mode_solver_activity_gap_is_compacted()
    test_skillsbench_product_mode_solver_activity_gap_overrides_zero_score()
    test_skillsbench_product_mode_first_action_timeout_is_uncountable()
    test_skillsbench_host_local_idle_timeout_after_closeout_is_countable()
    test_skillsbench_host_local_idle_no_output_progress_is_distinct()
    test_product_mode_host_local_idle_no_output_progress_requires_new_trace()
    test_goal_start_host_local_defers_codex_exec_preflight_until_bridge_command()
    test_app_server_goal_worker_skips_plain_codex_exec_preflight()
    test_codex_cli_goal_worker_skips_plain_codex_exec_preflight()
    test_codex_cli_goal_official_score_without_task_activity_is_uncountable()
    test_app_server_goal_first_action_timeout_respects_agent_idle_timeout()
    test_goal_start_host_exec_failure_overrides_zero_score_recovery()
    test_skillsbench_product_mode_declared_done_below_passing_reward_is_compacted()
    test_skillsbench_declared_done_missing_reward_status_is_compacted()
    test_skillsbench_product_mode_declared_done_without_closeout_overrides_verifier_error()
    test_skillsbench_product_mode_no_tool_lifecycle_abort_is_compacted()
    test_skillsbench_product_mode_pass_clears_generic_runner_error()
    test_skillsbench_product_mode_case_state_usage_is_compacted()
    test_skillsbench_product_mode_legacy_case_state_path_is_not_compacted()
    test_skillsbench_round_trace_records_best_round_score()
    test_skillsbench_acp_trajectory_summary_is_compacted()
    test_cli_dry_run_skillsbench_skeleton()
    test_cli_dry_run_skillsbench_official_result()
    test_cli_skillsbench_result_root_discovers_nested_case_result_for_ledger()
    test_skillsbench_runner_plan_supports_controller_trace_path()
    test_skillsbench_parallel_batch_isolates_case_process_argv()
    test_skillsbench_single_task_ids_replaces_default_task_id()
    test_skillsbench_parallel_batch_recovers_child_payload_from_mixed_stderr()
    test_skillsbench_compact_runs_update_ledger_pair()
    test_skillsbench_repeat_same_mode_collapses_active_ledger_run()
    test_skillsbench_run_group_ledger_inherits_and_syncs_global_ledger()
    test_skillsbench_runner_failure_compact_closeout()
    test_skillsbench_runner_failure_case_event_timeline_is_compacted()
    test_skillsbench_runner_failure_recovers_zero_score_from_controller_trace()
    test_skillsbench_runner_failure_recovers_passing_score_from_verifier_artifact()
    test_skillsbench_runner_failure_prefers_structured_preflight_blocker()
    test_skillsbench_runner_failure_marks_pre_agent_install_stage()
    test_skillsbench_runner_failure_backfills_generic_timeout_stall_cleanup()
    test_skillsbench_setup_stall_cleanup_targets_current_job_only()
    test_skillsbench_reduce_only_missing_result_records_closeout_exit_zero()
    test_skillsbench_main_failure_closeout_preserves_mutated_prerequisites()
    test_skillsbench_main_recovers_official_result_after_runner_exception()
    test_skillsbench_main_recovers_missing_reward_with_structured_prereq_blocker()
    test_skillsbench_result_timeout_after_loopx_lifecycle_is_attributed()
    test_skillsbench_user_loop_soft_verify_exception_continues_to_next_round()
    test_skillsbench_user_loop_no_tool_execute_exception_continues_to_next_round()
    test_skillsbench_final_verify_timeout_after_user_loop_recovery_is_attributed()
    test_skillsbench_verifier_prep_timeout_override_is_public_safe()
    test_skillsbench_main_marks_empty_acp_trajectory_after_host_install()
    test_skillsbench_main_marks_agent_message_only_no_tool_calls()
    test_skillsbench_main_redirects_runner_output_to_private_log()
    test_skillsbench_reduce_only_discovers_nested_official_result()
    test_skillsbench_reduce_only_preserves_round_reward_trace()
    test_skillsbench_reduce_only_preserves_persisted_public_prerequisites()
    print("skillsbench-benchmark-run-smoke: ok")
