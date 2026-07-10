#!/usr/bin/env python3
"""Smoke SkillsBench benchmark egress proxy policy for formal Goal routes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import skillsbench_automation_loop as skillsbench_loop
from loopx.benchmark_adapters import skillsbench_proxy_runtime as proxy_runtime


def _make_skillsbench_root(root: Path) -> Path:
    skillsbench_root = root / "skillsbench"
    task_dir = skillsbench_root / "tasks" / "citation-check"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
    return skillsbench_root


def _formal_cli_goal_args(root: Path) -> object:
    return skillsbench_loop.parse_args(
        [
            "--task-id",
            "citation-check",
            "--route",
            "codex-cli-goal-baseline",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--skillsbench-root",
            str(_make_skillsbench_root(root)),
            "--jobs-dir",
            str(root / "jobs"),
        ]
    )


def test_formal_cli_goal_auto_requires_benchmark_egress_proxy() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-egress-policy-missing-") as tmp:
        root = Path(tmp)
        previous = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY")
        previous_mode = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE")
        os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
        os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE", None)
        try:
            args = _formal_cli_goal_args(root)
            plan = skillsbench_loop.build_plan(args)
            egress = plan["benchmark_egress_proxy"]
            assert egress["requested_mode"] == "require", egress
            assert egress["proxy_required"] is True, egress
            assert egress["proxy_configured"] is False, egress
            assert egress["proxy_url_recorded"] is False, egress
            assert egress["raw_proxy_url_recorded"] is False, egress

            try:
                skillsbench_loop._run_benchmark_egress_proxy_preflight(args, plan)
            except skillsbench_loop.SkillsBenchSetupPreflightBlocked:
                pass
            else:  # pragma: no cover - assertion path for script-style smoke
                raise AssertionError("formal CLI Goal run should require benchmark egress proxy")

            blocked = plan["benchmark_egress_proxy"]
            assert blocked["status"] == "missing_required_proxy", blocked
            assert blocked["ready"] is False, blocked
            prereqs = plan["runner_prerequisites"]
            assert prereqs["benchmark_egress_proxy_required"] is True, prereqs
            assert prereqs["benchmark_egress_proxy_configured"] is False, prereqs
            assert prereqs["benchmark_egress_proxy_mode_requested"] == "require", prereqs
            assert prereqs["benchmark_egress_proxy_status"] == "missing_required_proxy", prereqs
        finally:
            if previous is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = previous
            if previous_mode is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE"] = previous_mode


def test_formal_cli_goal_proxy_env_is_forwarded_without_public_url() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-egress-policy-forward-") as tmp:
        root = Path(tmp)
        proxy_url = "http://benchmark-proxy.example.invalid:18080"
        previous = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY")
        previous_mode = os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE")
        os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = proxy_url
        os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE", None)
        try:
            args = _formal_cli_goal_args(root)
            plan = skillsbench_loop.build_plan(args)
            egress = plan["benchmark_egress_proxy"]
            assert egress["requested_mode"] == "require", egress
            assert egress["proxy_required"] is True, egress
            assert egress["proxy_configured"] is True, egress
            assert egress["proxy_env_key"] == "LOOPX_SKILLSBENCH_EGRESS_PROXY", egress
            assert proxy_url not in json.dumps(plan, sort_keys=True), plan

            private_env = skillsbench_loop._benchmark_egress_proxy_env(args)
            assert private_env["LOOPX_SKILLSBENCH_EGRESS_PROXY"] == proxy_url, private_env
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                assert private_env[key] == proxy_url, private_env
            assert "127.0.0.1" in private_env["NO_PROXY"], private_env

            target_env = skillsbench_loop._host_local_acp_target_env({}, args=args)
            assert target_env["LOOPX_SKILLSBENCH_EGRESS_PROXY"] == proxy_url, target_env
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                assert target_env[key] == proxy_url, target_env
        finally:
            if previous is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = previous
            if previous_mode is None:
                os.environ.pop("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE", None)
            else:
                os.environ["LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE"] = previous_mode


def test_public_launcher_uses_container_reachable_benchmark_proxy() -> None:
    env = os.environ.copy()
    env.update(
        {
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_DOCKER_PROXY_HOST": "host.docker.internal",
            "SKILLSBENCH_DOCKER_API_VERSION": "1.43",
            "SKILLSBENCH_RUN_STAMP": "20260709T000000CST",
        }
    )
    env.pop("SKILLSBENCH_APPEND_HISTORY", None)
    proc = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"),
            "--dry-run",
            "citation-check",
            "egress-smoke",
            "18186",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    output = proc.stdout
    assert "docker_proxy_host=host.docker.internal" in output, output
    assert (
        "LOOPX_SKILLSBENCH_EGRESS_PROXY=http://host.docker.internal:18186"
        in output
    ), output
    assert "DOCKER_API_VERSION=1.43" in output, output
    assert "--codex-api-reverse-tunnel-proxy http://127.0.0.1:18186" in output, output
    assert "--benchmark-egress-proxy-mode require" in output, output
    assert "--append-history" not in output, output


def test_public_launcher_batches_three_cases_with_closeout_sync() -> None:
    env = os.environ.copy()
    env.update(
        {
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_DOCKER_PROXY_HOST": "host.docker.internal",
            "SKILLSBENCH_DOCKER_API_VERSION": "1.43",
            "SKILLSBENCH_RUN_STAMP": "20260710T000000CST",
            "SKILLSBENCH_CANONICAL_CASE_IDS_FILE": "/opaque/canonical-ids.txt",
        }
    )
    proc = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"),
            "--dry-run",
            "case-a,case-b,case-c",
            "batch-smoke",
            "18186",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    output = proc.stdout
    assert "task_ids=case-a,case-b,case-c" in output, output
    assert "parallel_cases=3" in output, output
    assert "--task-ids case-a\\,case-b\\,case-c" in output or (
        "--task-ids case-a,case-b,case-c" in output
    ), output
    assert "--parallel-cases 3" in output, output
    assert "--remote-public-artifact-root" in output, output
    assert "benchmark_run.compact.json" in output, output
    assert "--local-run-ledger-path" in output, output
    assert "--local-ledger-catchup-root" in output, output
    assert (
        "--local-ledger-catchup-run-group-contains "
        "skillsbench-codex-cli-goal-xhigh-" in output
    ), output
    assert "--remote-failure-cleanup-pattern" in output, output
    assert "--remote-failure-cleanup-include-docker" in output, output
    assert "--update-ledger" not in output, output
    assert "--local-target-lane-id codex-cli-goal-xhigh" in output, output
    assert "--local-target-run-group-contains" not in output, output
    assert "--local-target-backfill-run-group-contains" not in output, output


def test_public_launcher_applies_ssh_options_to_remote_discovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-launch-ssh-options-") as tmp:
        root = Path(tmp)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        ssh_log = root / "ssh.log"
        fake_ssh = fake_bin / "ssh"
        fake_ssh.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"$SKILLSBENCH_TEST_SSH_LOG\"\n"
            "if [[ \"$*\" == *'/version'* ]]; then\n"
            "  printf '1.43\\n'\n"
            "elif [[ \"$*\" == *'docker info'* ]]; then\n"
            "  printf '[\"name=rootless\"]\\n'\n"
            "elif [[ \"$*\" == *'hostname -I'* ]]; then\n"
            "  printf 'runner-host.example.invalid\\n'\n"
            "else\n"
            "  exit 99\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_ssh.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "SKILLSBENCH_TEST_SSH_LOG": str(ssh_log),
                "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
                "SKILLSBENCH_SSH_OPTIONS": "Port=2222",
                "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
                "SKILLSBENCH_ROOT": "/remote/skillsbench",
                "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
                "SKILLSBENCH_RUN_STAMP": "20260710T010000CST",
            }
        )
        env.pop("SKILLSBENCH_DOCKER_PROXY_HOST", None)
        env.pop("SKILLSBENCH_DOCKER_API_VERSION", None)
        proc = subprocess.run(
            [
                str(REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"),
                "--dry-run",
                "citation-check",
                "ssh-options-smoke",
                "18186",
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        discovery_calls = ssh_log.read_text(encoding="utf-8").splitlines()
        assert len(discovery_calls) == 3, discovery_calls
        assert all("-o Port=2222" in call for call in discovery_calls), discovery_calls
        assert "docker_proxy_host=runner-host.example.invalid" in proc.stdout, proc.stdout
        assert "docker_proxy_endpoint_mode=rootless_host_interface" in proc.stdout
        assert "docker_api_version=1.43" in proc.stdout, proc.stdout
        assert "DOCKER_API_VERSION=1.43" in proc.stdout, proc.stdout


def test_proxy_runtime_preserves_docker_cli_plugins() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-config-") as tmp:
        root = Path(tmp)
        source_config = root / "source"
        source_plugins = source_config / "cli-plugins"
        source_plugins.mkdir(parents=True)
        (source_plugins / "docker-compose").write_text("fixture\n", encoding="utf-8")
        (source_config / "config.json").write_text("{}\n", encoding="utf-8")
        previous = os.environ.get("DOCKER_CONFIG")
        os.environ["DOCKER_CONFIG"] = str(source_config)
        plan: dict[str, object] = {}
        active_config: Path | None = None
        try:
            with proxy_runtime.proxy_runtime_env_applied(
                {
                    "LOOPX_SKILLSBENCH_EGRESS_PROXY": (
                        "http://benchmark-proxy.example.invalid:18080"
                    ),
                    "NO_PROXY": "localhost",
                },
                plan=plan,
            ):
                active_config = Path(os.environ["DOCKER_CONFIG"])
                linked_plugins = active_config / "cli-plugins"
                assert linked_plugins.is_symlink(), linked_plugins
                assert linked_plugins.resolve() == source_plugins.resolve()
                prerequisites = plan["runner_prerequisites"]
                assert isinstance(prerequisites, dict)
                assert prerequisites[
                    "benchmark_egress_proxy_docker_cli_plugins_preserved"
                ] is True
                assert prerequisites[
                    "benchmark_egress_proxy_docker_cli_plugin_paths_recorded"
                ] is False
        finally:
            if previous is None:
                os.environ.pop("DOCKER_CONFIG", None)
            else:
                os.environ["DOCKER_CONFIG"] = previous
        assert active_config is not None and not active_config.exists()


def test_verifier_proxy_patch_is_required_only_for_existing_verifier() -> None:
    proxy_env = {
        "LOOPX_SKILLSBENCH_EGRESS_PROXY": "http://benchmark-proxy.example.invalid:18080",
        "NO_PROXY": "localhost,127.0.0.1,::1",
    }
    with tempfile.TemporaryDirectory(prefix="skillsbench-verifier-proxy-") as tmp:
        root = Path(tmp)
        missing = skillsbench_loop.patch_verifier_benchmark_egress_proxy_env(
            root / "missing-test.sh",
            proxy_env=proxy_env,
        )
        assert missing["benchmark_egress_proxy_verifier_env_patch_required"] is False
        assert missing["benchmark_egress_proxy_verifier_env_patch_applied"] is False
        assert missing["benchmark_egress_proxy_verifier_env_key_count"] == 0

        verifier = root / "test.sh"
        verifier.write_text("#!/usr/bin/env bash\npytest -q\n", encoding="utf-8")
        patched = skillsbench_loop.patch_verifier_benchmark_egress_proxy_env(
            verifier,
            proxy_env=proxy_env,
        )
        assert patched["benchmark_egress_proxy_verifier_env_patch_required"] is True
        assert patched["benchmark_egress_proxy_verifier_env_patch_applied"] is True
        assert patched["benchmark_egress_proxy_verifier_env_key_count"] > 0


def test_verifier_proxy_patch_failure_blocks_task_staging() -> None:
    proxy_url = "http://benchmark-proxy.example.invalid:18080"
    with tempfile.TemporaryDirectory(prefix="skillsbench-verifier-proxy-block-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "citation-check"
        dockerfile = task / "environment" / "Dockerfile"
        verifier = task / "tests" / "test.sh"
        dockerfile.parent.mkdir(parents=True)
        verifier.parent.mkdir(parents=True)
        dockerfile.write_text("FROM python:3.12-slim\n", encoding="utf-8")
        verifier.write_text("#!/bin/sh\npytest -q\n", encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        failed_patch = {
            "benchmark_egress_proxy_verifier_env_patch_required": True,
            "benchmark_egress_proxy_verifier_env_patch_applied": False,
            "benchmark_egress_proxy_verifier_env_key_count": 1,
            "benchmark_egress_proxy_verifier_env_raw_proxy_recorded": False,
        }
        with mock.patch.object(
            skillsbench_loop,
            "patch_verifier_benchmark_egress_proxy_env",
            return_value=failed_patch,
        ):
            try:
                skillsbench_loop.stage_task_for_sandbox(
                    task_path=task,
                    jobs_dir=root / "jobs",
                    job_name="citation-check-goal",
                    sandbox="docker",
                    benchmark_egress_proxy_env={
                        "LOOPX_SKILLSBENCH_EGRESS_PROXY": proxy_url,
                    },
                )
            except skillsbench_loop.SkillsBenchSetupPreflightBlocked as exc:
                assert "verifier egress proxy patch required" in str(exc), exc
            else:  # pragma: no cover - script-style assertion path
                raise AssertionError("missing verifier proxy patch must block staging")


def test_proxy_runtime_prewarms_external_base_images_without_public_refs() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-base-image-prewarm-") as tmp:
        dockerfile = Path(tmp) / "Dockerfile"
        image = "gcr.io/oss-fuzz-base/base-builder-python"
        dockerfile.write_text(
            f"FROM {image} AS builder\n"
            "FROM builder AS final\n",
            encoding="utf-8",
        )
        calls: list[list[str]] = []

        def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
            calls.append(argv)
            cached = argv[1:3] == ["image", "inspect"]
            return SimpleNamespace(returncode=1 if cached else 0)

        with mock.patch.object(
            proxy_runtime.shutil,
            "which",
            side_effect=lambda name: f"/usr/bin/{name}",
        ), mock.patch.object(proxy_runtime.subprocess, "run", side_effect=fake_run):
            metadata = proxy_runtime.prewarm_dockerfile_base_images(
                dockerfile,
                enabled=True,
            )

        assert metadata["benchmark_egress_proxy_base_image_prewarm_status"] == "completed"
        assert metadata["benchmark_egress_proxy_base_image_prewarm_candidate_count"] == 1
        assert metadata["benchmark_egress_proxy_base_image_prewarm_attempted_count"] == 1
        assert metadata["benchmark_egress_proxy_base_image_prewarm_loaded_count"] == 1
        assert metadata["benchmark_egress_proxy_base_image_prewarm_failed_count"] == 0
        assert metadata["benchmark_egress_proxy_base_image_prewarm_raw_image_refs_recorded"] is False
        assert metadata["benchmark_egress_proxy_base_image_prewarm_raw_output_recorded"] is False
        assert image not in json.dumps(metadata, sort_keys=True), metadata
        public_prerequisites = skillsbench_loop._public_runner_prerequisites(metadata)
        public_config = skillsbench_loop._public_runner_config(
            {"runner_prerequisites": metadata}
        )
        assert public_prerequisites == metadata, public_prerequisites
        for key, value in metadata.items():
            assert public_config[key] == value, public_config
        assert image not in json.dumps(public_prerequisites, sort_keys=True)
        skopeo_calls = [call for call in calls if call[0] == "/usr/bin/skopeo"]
        assert len(skopeo_calls) == 1, calls
        assert skopeo_calls[0][-2:] == [
            f"docker://{image}",
            f"docker-daemon:{image}:latest",
        ]


if __name__ == "__main__":
    test_formal_cli_goal_auto_requires_benchmark_egress_proxy()
    test_formal_cli_goal_proxy_env_is_forwarded_without_public_url()
    test_public_launcher_uses_container_reachable_benchmark_proxy()
    test_public_launcher_batches_three_cases_with_closeout_sync()
    test_public_launcher_applies_ssh_options_to_remote_discovery()
    test_proxy_runtime_preserves_docker_cli_plugins()
    test_verifier_proxy_patch_is_required_only_for_existing_verifier()
    test_verifier_proxy_patch_failure_blocks_task_staging()
    test_proxy_runtime_prewarms_external_base_images_without_public_refs()
    print("skillsbench-benchmark-egress-policy-smoke: ok")
