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
from loopx.benchmark_adapters import skillsbench_dockerfile_runtime as dockerfile_runtime
from loopx.benchmark_adapters import skillsbench_proxy_runtime as proxy_runtime


def _launcher_env_without_profile() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("SKILLSBENCH_RUNNER_PROFILE", None)
    env["XDG_STATE_HOME"] = str(
        Path(tempfile.gettempdir()) / f"loopx-skillsbench-smoke-{os.getpid()}"
    )
    return env


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
    env = _launcher_env_without_profile()
    env.update(
        {
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_DOCKER_PROXY_HOST": "host.docker.internal",
            "SKILLSBENCH_DOCKER_API_VERSION": "1.43",
            "SKILLSBENCH_REMOTE_CODEX_BIN": "/remote/bin/codex",
            "SKILLSBENCH_LOCAL_CODEX_SANDBOX": "danger-full-access",
            "SKILLSBENCH_CLI_GOAL_THREAD_PREWARM": "1",
            "SKILLSBENCH_ALLOW_STAGED_BOOTSTRAP_REPAIR_RUN": "1",
            "SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY": "final-only",
            "SKILLSBENCH_RUN_STAMP": "20260709T000000CST",
            "SKILLSBENCH_TUNNEL_PROBE_TIMEOUT_SEC": "19",
            "SKILLSBENCH_TUNNEL_READY_TIMEOUT_SEC": "71",
            "SKILLSBENCH_TUNNEL_HEALTH_INTERVAL_SEC": "29",
            "SKILLSBENCH_TUNNEL_HEALTH_FAILURE_THRESHOLD": "3",
            "SKILLSBENCH_TUNNEL_RECONNECT_ATTEMPTS": "4",
            "SKILLSBENCH_SKIP_GLOBAL_LEDGER_SYNC": "1",
            "SKILLSBENCH_SKIP_CURRENT_AGGREGATE_UPDATE": "1",
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
    assert "docker_proxy_host_recorded=false" in output, output
    assert (
        "LOOPX_SKILLSBENCH_EGRESS_PROXY=http://host.docker.internal:18186"
        in output
    ), output
    assert "DOCKER_API_VERSION=1.43" in output, output
    assert "--codex-api-reverse-tunnel-proxy http://127.0.0.1:18186" in output, output
    assert "--benchmark-egress-proxy-mode require" in output, output
    assert "--local-codex-bin /remote/bin/codex" in output, output
    assert "--local-codex-sandbox danger-full-access" in output, output
    assert "local_codex_sandbox=danger-full-access" in output, output
    assert "codex_cli_goal_thread_prewarm=1" in output, output
    assert "--codex-cli-goal-thread-prewarm" in output, output
    assert "allow_staged_bootstrap_repair_run=1" in output, output
    assert "--allow-staged-bootstrap-repair-run" in output, output
    assert "product_mode_soft_verify_policy=final-only" in output, output
    assert "--product-mode-soft-verify-policy final-only" in output, output
    assert "remote_codex_bin_mode=explicit" in output, output
    assert "--probe-timeout-sec 19" in output, output
    assert "--tunnel-ready-timeout-sec 71" in output, output
    assert "--tunnel-health-interval-sec 29" in output, output
    assert "--tunnel-health-failure-threshold 3" in output, output
    assert "--tunnel-reconnect-attempts 4" in output, output
    assert "--tunnel-reconnect-ready-timeout-sec 71" in output, output
    assert (
        "--local-ledger-catchup-run-group-contains "
        "skillsbench-codex-cli-goal-xhigh-citation-check-egress-smoke-"
        "20260709T000000CST" in output
    ), output
    assert "--append-history" not in output, output
    assert "skip_global_ledger_sync=1" in output, output
    assert "skip_current_aggregate_update=1" in output, output
    assert "--skip-global-ledger-sync" in output, output
    assert "--skip-current-aggregate-update" in output, output


def test_public_launcher_rejects_invalid_product_mode_soft_verify_policy() -> None:
    env = _launcher_env_without_profile()
    env.update(
        {
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY": "sometimes",
        }
    )
    proc = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"),
            "--dry-run",
            "citation-check",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc
    assert (
        "SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY must be "
        "every-round or final-only" in proc.stderr
    ), proc.stderr


def test_public_launcher_batches_three_cases_with_closeout_sync() -> None:
    env = _launcher_env_without_profile()
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
    assert "--probe-timeout-sec 20" in output, output
    assert "--tunnel-ready-timeout-sec 60" in output, output
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
    assert "--codex-cli-goal-thread-prewarm" not in output, output
    assert "--allow-staged-bootstrap-repair-run" not in output, output
    assert "product_mode_soft_verify_policy=runner-default" in output, output
    assert "--product-mode-soft-verify-policy" not in output, output
    assert "--local-target-lane-id codex-cli-goal-xhigh" in output, output
    assert "--local-target-run-group-contains" not in output, output
    assert "--local-target-backfill-run-group-contains" not in output, output
    assert (
        "local_run_ledger=.local/goals/loopx-meta/skillsbench-ledgers/"
        "live-standard-run-ledger.json" in output
    ), output
    assert (
        "standard_aggregate=.local/goals/loopx-meta/skillsbench-ledgers/"
        "standard-current-aggregate.json" in output
    ), output


def test_public_launcher_rejects_aggregate_without_explicit_ledger() -> None:
    env = _launcher_env_without_profile()
    env.update(
        {
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_STANDARD_AGGREGATE_PATH": "/other/standard.json",
        }
    )
    env.pop("SKILLSBENCH_LOCAL_RUN_LEDGER_PATH", None)
    proc = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"),
            "--dry-run",
            "citation-check",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc
    assert (
        "SKILLSBENCH_STANDARD_AGGREGATE_PATH requires "
        "SKILLSBENCH_LOCAL_RUN_LEDGER_PATH" in proc.stderr
    ), proc.stderr


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
        env = _launcher_env_without_profile()
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
        assert "docker_proxy_host_recorded=false" in proc.stdout, proc.stdout
        assert "docker_proxy_endpoint_mode=rootless_host_interface" in proc.stdout
        assert "docker_api_version=1.43" in proc.stdout, proc.stdout
        assert "DOCKER_API_VERSION=1.43" in proc.stdout, proc.stdout


def test_docker_staging_keeps_pip_installs_inside_explicit_venv() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-venv-pip-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "venv-pip"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original = (
            "FROM ubuntu:24.04\n"
            "RUN python3 -m venv /opt/venv\n"
            'ENV PATH="/opt/venv/bin:$PATH"\n'
            "RUN pip install -U pip setuptools wheel\n"
            "RUN pip3 install numpy && \\\n"
            "    python3 -m pip install cython\n"
            "RUN uv pip install pandas\n"
            "RUN echo 'pip install is documentation'\n"
            "RUN python3 - <<'PY'\n"
            "print('pip install remains text')\n"
            "PY\n"
            "FROM ubuntu:24.04 AS system-stage\n"
            "RUN pip install system-package\n"
        )
        dockerfile.write_text(original, encoding="utf-8")
        (task / "task.toml").write_text('version = "1.1"\n', encoding="utf-8")

        staged, metadata = skillsbench_loop.stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="venv-pip-goal",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["dockerfile_venv_pip_invocation_patch_required"] is True
        assert metadata["dockerfile_venv_pip_invocation_patch_applied"] is True
        assert dockerfile.read_text(encoding="utf-8") == original
        staged_text = (staged / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert dockerfile_runtime.VENV_PIP_INVOCATION_MARKER in staged_text
        assert "RUN python3 -m pip install -U pip setuptools wheel" in staged_text
        assert "RUN python3 -m pip install numpy" in staged_text
        assert "python3 -m pip install cython" in staged_text
        assert "RUN uv pip install pandas" in staged_text
        assert "RUN echo 'pip install is documentation'" in staged_text
        assert "print('pip install remains text')" in staged_text
        assert "RUN pip install system-package" in staged_text
        public = skillsbench_loop._public_task_staging(metadata)
        assert public["dockerfile_venv_pip_invocation_patch_required"] is True
        assert public["dockerfile_venv_pip_invocation_patch_applied"] is True


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
    test_public_launcher_rejects_aggregate_without_explicit_ledger()
    test_public_launcher_applies_ssh_options_to_remote_discovery()
    test_docker_staging_keeps_pip_installs_inside_explicit_venv()
    test_proxy_runtime_preserves_docker_cli_plugins()
    test_verifier_proxy_patch_is_required_only_for_existing_verifier()
    test_verifier_proxy_patch_failure_blocks_task_staging()
    test_proxy_runtime_prewarms_external_base_images_without_public_refs()
    print("skillsbench-benchmark-egress-policy-smoke: ok")
