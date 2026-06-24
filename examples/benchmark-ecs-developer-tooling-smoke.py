#!/usr/bin/env python3
"""Smoke-test public ECS benchmark workflow developer tooling."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_json(args: list[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bootstrap = run_json(
            [
                "scripts/benchmark_ecs_bootstrap.py",
                "--workspace",
                str(tmp_path / "loopx-bench"),
                "--min-free-gib",
                "0",
                "--require",
                "python3",
                "--require",
                "git",
                "--optional",
                "docker",
                "--create-dirs",
            ]
        )
        assert bootstrap["schema_version"] == "benchmark_ecs_bootstrap_probe_v0"
        assert bootstrap["ready"] is True, bootstrap
        assert bootstrap["workspace"]["path_recorded"] is False
        assert bootstrap["boundary"]["raw_logs_read"] is False
        assert (tmp_path / "loopx-bench" / "sources").is_dir()

        runtime_layer = run_json(
            [
                "scripts/benchmark_agent_runtime_layer.py",
                "--benchmark",
                "all",
                "--workspace",
                str(tmp_path / "loopx-bench"),
            ]
        )
        assert (
            runtime_layer["schema_version"]
            == "benchmark_agent_runtime_layer_plan_v0"
        )
        assert runtime_layer["ready"] is True
        assert runtime_layer["boundary"]["private_paths_recorded"] is False
        runtime_profiles = {
            profile["benchmark_id"]: profile
            for profile in runtime_layer["profiles"]
        }
        assert (
            runtime_profiles["terminal-bench"]["layer_id"]
            == "harbor_codex_cli_tools"
        )
        assert (
            runtime_profiles["swe-marathon"]["layer_id"]
            == "harbor_codex_cli_tools"
        )
        assert (
            runtime_profiles["skillsbench"]["layer_id"]
            == "benchflow_js_agent_runtime"
        )

        node_root = tmp_path / "node-v22.test-linux-x64"
        (node_root / "bin").mkdir(parents=True)
        for name, output in (
            ("node", "v22.20.0"),
            ("npm", "10.9.0"),
        ):
            executable = node_root / "bin" / name
            executable.write_text(
                f"#!/usr/bin/env sh\necho {output!r}\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
        codex_acp = tmp_path / "codex-acp"
        codex_acp.write_text(
            "#!/usr/bin/env sh\necho 'codex-acp 0.test'\n",
            encoding="utf-8",
        )
        codex_acp.chmod(0o755)
        skillsbench_agent_layer = run_json(
            [
                "scripts/skillsbench_agent_runtime_layer.py",
                "--output",
                str(tmp_path / "benchflow-agent-runtime"),
                "--node-root",
                str(node_root),
                "--codex-acp-bin",
                str(codex_acp),
            ]
        )
        assert (
            skillsbench_agent_layer["schema_version"]
            == "skillsbench_agent_runtime_layer_v0"
        )
        assert skillsbench_agent_layer["ready"] is True
        assert (
            skillsbench_agent_layer["output"]["mount_target"]
            == "/opt/benchflow"
        )
        assert skillsbench_agent_layer["boundary"]["raw_logs_read"] is False

        launch = run_json(
            [
                "scripts/terminal_bench_no_upload_smoke.py",
                "--task-id",
                "hello-world",
                "--jobs-dir",
                str(tmp_path / "jobs"),
                "--run-root",
                str(tmp_path / "run"),
            ]
        )
        assert launch["schema_version"] == "terminal_bench_worker_materialization_probe_launch_v0"
        assert launch["dry_run"] is True
        assert launch["boundary"]["no_upload"] is True
        assert launch["boundary"]["raw_logs_read"] is False
        assert launch["developer_entrypoint"]["public_safe"] is True

        post_launch_path = tmp_path / "post_launch.public.json"
        post_launch_path.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_post_launch_materialization_v0",
                    "ready_for_compact_result_ingest": False,
                    "ready_for_compact_failure_marker": True,
                    "compact_failure_class": "detached_worker_ended_without_jobs_dir",
                    "first_blocker": "detached_worker_ended_without_jobs_dir",
                    "trial_result_present_count": 0,
                    "raw_logs_read": False,
                    "raw_task_text_read": False,
                    "trajectory_read": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        reduced = run_json(
            [
                "scripts/terminal_bench_compose_startup_reducer.py",
                "--post-launch-json",
                str(post_launch_path),
            ]
        )
        assert reduced["schema_version"] == "terminal_bench_compose_startup_reducer_v0"
        assert reduced["compose_startup_blocker"] is True
        assert reduced["next_action"] == "repair_terminal_bench_compose_startup"
        assert reduced["boundary"]["raw_logs_read"] is False
        assert reduced["boundary"]["private_paths_recorded"] is False

        compose_setup_path = tmp_path / "compose_setup.public.json"
        compose_setup_path.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_compose_setup_diagnostic_v0",
                    "status": "blocked",
                    "failure_class": "environment_setup_failure",
                    "runner_error_len_bucket": "compact",
                    "next_diagnostic_action": "repair_terminal_bench_compose_setup",
                    "compose_setup_failure": True,
                    "apt_setup_risk_detected": True,
                    "apt_retry_patch_required": True,
                    "raw_error_recorded": False,
                    "raw_logs_read": False,
                    "raw_task_text_read": False,
                    "raw_trajectory_read": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        no_rebuild_guard_path = tmp_path / "no_rebuild_guard.public.json"
        no_rebuild_guard_path.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_no_rebuild_guard_v0",
                    "ok": False,
                    "first_blocker": "terminal_bench_no_rebuild_guard_not_applied",
                    "private_root_recorded": False,
                    "apply": False,
                    "manager_file_count": 1,
                    "patched_file_count": 0,
                    "files": [
                        {
                            "relative_path": "terminal_bench/terminal/docker_compose_manager.py",
                            "status": "needs_guard_patch",
                            "patchable": True,
                            "patched": False,
                        }
                    ],
                    "contract": {
                        "no_rebuild_implies_compose_no_build": True,
                        "score_or_task_behavior_changed": False,
                        "runner_surface_changed": "docker_compose_startup_only",
                    },
                    "boundary": {
                        "raw_logs_read": False,
                        "raw_task_text_read": False,
                        "trajectory_read": False,
                        "private_paths_recorded": False,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        task_image_bootstrap_path = tmp_path / "task_image_bootstrap.public.json"
        task_image_bootstrap_path.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_task_image_bootstrap_v0",
                    "ok": True,
                    "first_blocker": "",
                    "execute": False,
                    "private_work_dir_recorded": False,
                    "apt_packages": ["tmux", "asciinema"],
                    "required_commands": ["tmux", "asciinema"],
                    "apt_mirror_host": "mirrors.tuna.tsinghua.edu.cn",
                    "security_mirror_host": "mirrors.tuna.tsinghua.edu.cn",
                    "use_host_network": True,
                    "timeout_sec": 600,
                    "build_returncode": None,
                    "command_checks": {},
                    "contract": {
                        "score_or_task_behavior_changed": False,
                        "runner_surface_changed": "task_image_startup_prerequisites_only",
                        "case_runtime_agent_install_forbidden": True,
                    },
                    "boundary": {
                        "raw_logs_read": False,
                        "raw_task_text_read": False,
                        "trajectory_read": False,
                        "private_paths_recorded": False,
                        "credential_values_read": False,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        attributed = run_json(
            [
                "scripts/terminal_bench_compose_startup_reducer.py",
                "--post-launch-json",
                str(post_launch_path),
                "--compose-setup-json",
                str(compose_setup_path),
                "--no-rebuild-guard-json",
                str(no_rebuild_guard_path),
                "--task-image-bootstrap-json",
                str(task_image_bootstrap_path),
            ]
        )
        decision = attributed["cause_fix_decision"]
        assert (
            decision["schema_version"]
            == "terminal_bench_compose_cause_fix_decision_v0"
        )
        assert decision["classification"] == "no_rebuild_guard_blocker"
        assert decision["next_action"] == "apply_terminal_bench_no_rebuild_guard"
        assert attributed["next_action"] == "apply_terminal_bench_no_rebuild_guard"
        assert "compose_setup_diagnostic_present" in decision["reason_codes"]
        assert (
            "terminal_bench_no_rebuild_guard_not_applied"
            in decision["reason_codes"]
        )
        assert (
            "fast_mirror_bootstrap_fallback_available"
            in decision["reason_codes"]
        )
        assert (
            attributed["compose_setup_diagnostic"]["boundary"]["raw_logs_read"]
            is False
        )
        assert (
            attributed["no_rebuild_guard"]["file_statuses"][0]["patchable"]
            is True
        )
        assert (
            attributed["task_image_bootstrap"]["contract"][
                "case_runtime_agent_install_forbidden"
            ]
            is True
        )
        assert attributed["boundary"]["raw_task_text_read"] is False

        skillsbench_prewarm = run_json(
            [
                "scripts/skillsbench_verifier_prewarm_plan.py",
                "--task-id",
                "hello-world",
            ]
        )
        assert (
            skillsbench_prewarm["schema_version"]
            == "skillsbench_verifier_dependency_prewarm_plan_v0"
        )
        assert skillsbench_prewarm["ready"] is True
        assert (
            skillsbench_prewarm["prewarm_blocker_label"]
            == "skillsbench_verifier_dependency_prewarm_required"
        )
        assert skillsbench_prewarm["oracle_sanity_contract"]["no_upload"] is True
        assert skillsbench_prewarm["oracle_sanity_contract"]["expected_reward"] == 1.0
        assert (
            "upstream_task_truth"
            in skillsbench_prewarm["prewarm_scope"]["forbidden"]
        )
        assert "uvx" in skillsbench_prewarm["dependency_contract"]["required_tools"]
        assert skillsbench_prewarm["boundary"]["raw_logs_recorded"] is False
        assert skillsbench_prewarm["boundary"]["remote_paths_recorded"] is False

    print("benchmark-ecs-developer-tooling-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
