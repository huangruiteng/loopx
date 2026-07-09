#!/usr/bin/env python3
"""Smoke SkillsBench benchmark egress proxy policy for formal Goal routes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import skillsbench_automation_loop as skillsbench_loop


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
    assert "--local-target-lane-id codex-cli-goal-xhigh" in output, output
    assert "--local-target-run-group-contains" not in output, output
    assert "--local-target-backfill-run-group-contains" not in output, output


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


if __name__ == "__main__":
    test_formal_cli_goal_auto_requires_benchmark_egress_proxy()
    test_formal_cli_goal_proxy_env_is_forwarded_without_public_url()
    test_public_launcher_uses_container_reachable_benchmark_proxy()
    test_public_launcher_batches_three_cases_with_closeout_sync()
    test_verifier_proxy_patch_is_required_only_for_existing_verifier()
    print("skillsbench-benchmark-egress-policy-smoke: ok")
