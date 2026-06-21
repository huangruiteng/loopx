#!/usr/bin/env python3
"""Smoke-test the ALE host Codex CLI route gate."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment,
    build_agents_last_exam_host_codex_cli_route,
)


def make_cua_assets(root: Path) -> Path:
    assets = root / "cua_mcp_server"
    (assets / "src").mkdir(parents=True)
    (assets / "node_modules").mkdir()
    (assets / "package.json").write_text('{"name":"cua-desktop"}\n', encoding="utf-8")
    (assets / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    (assets / "src" / "index.js").write_text("console.log('ok')\n", encoding="utf-8")
    return assets


def make_fake_codex(root: Path) -> Path:
    bin_dir = root / "bin"
    bin_dir.mkdir()
    binary = bin_dir / "codex-fixture"
    binary.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "args = sys.argv[1:]",
                "if args == ['--version']:",
                "    print('codex-cli 0.128.0')",
                "    raise SystemExit(0)",
                "if args == ['exec', '--help']:",
                "    print('usage: codex exec [OPTIONS]')",
                "    raise SystemExit(0)",
                "if args == ['mcp', 'list', '--json']:",
                "    print(json.dumps([{'name': 'cua', 'enabled': True, 'transport': {'type': 'stdio'}}]))",
                "    raise SystemExit(0)",
                "raise SystemExit(2)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return bin_dir


def assert_no_execution(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["hidden_references_allowed"] is False
    assert boundary["production_actions_allowed"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False
    host_auth = payload["host_auth"]
    assert isinstance(host_auth, dict)
    assert host_auth["auth_values_read"] is False
    assert host_auth["config_content_read"] is False
    assert host_auth["credential_values_recorded"] is False
    assert host_auth["auth_material_copied_to_sandbox"] is False
    assert host_auth["whole_codex_dir_copied"] is False
    assert host_auth["paths_recorded"] is False


def assert_no_task_e2e_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["codex_prompt_sent"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["hidden_references_allowed"] is False
    assert boundary["production_actions_allowed"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False
    assert boundary["raw_output_recorded"] is False
    route_gate = payload["route_gate"]
    assert isinstance(route_gate, dict)
    assert_no_execution(route_gate)


def assert_public_safe(payload: dict[str, object], temp_root: Path) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        str(temp_root),
        ".codex/auth.json",
        ".codex/config.toml",
        "CODEX_ACCESS_TOKEN",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "refresh_token",
        "access_token",
        "instruction.md",
        "trajectory.json",
        "screenshot.png",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked


def run_fixture_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-host-codex-route-") as tmp:
        temp_root = Path(tmp)
        assets = make_cua_assets(temp_root)
        payload = build_agents_last_exam_host_codex_cli_route(
            codex_binary="codex",
            codex_binary_available=True,
            codex_version_text="codex-cli 0.128.0",
            host_auth_cache_present=True,
            host_config_present=True,
            require_host_config=True,
            cua_mcp_assets_root=str(assets),
            ale_sandbox_cua_smoke_ready=True,
            operator_authorized_host_codex_auth=True,
        )
        assert payload["schema_version"] == "agents_last_exam_host_codex_cli_route_v0", payload
        assert payload["ready"] is True, payload
        assert payload["first_blocker"] == "ready_for_no_task_host_codex_cua_smoke", payload
        assert payload["route"]["mode"] == "host_codex_cli_local_executor", payload
        assert payload["route"]["upstream_provider_key_path_required"] is False, payload
        assert payload["host_codex_cli"]["binary_path_recorded"] is False, payload
        assert payload["cua_mcp_assets"]["path_recorded"] is False, payload
        assert_no_execution(payload)
        assert_public_safe(payload, temp_root)

        missing_auth = build_agents_last_exam_host_codex_cli_route(
            codex_binary="codex",
            codex_binary_available=True,
            codex_version_text="codex-cli 0.128.0",
            host_auth_cache_present=False,
            cua_mcp_assets_root=str(assets),
            ale_sandbox_cua_smoke_ready=True,
            operator_authorized_host_codex_auth=True,
        )
        assert missing_auth["ready"] is False, missing_auth
        assert missing_auth["first_blocker"] == "host_codex_auth_cache_missing", missing_auth
        assert_no_execution(missing_auth)
        assert_public_safe(missing_auth, temp_root)

        unsafe_binary = build_agents_last_exam_host_codex_cli_route(
            codex_binary="/tmp/codex",
            codex_binary_available=True,
            codex_version_text="codex-cli 0.128.0",
            host_auth_cache_present=True,
            cua_mcp_assets_root=str(assets),
            ale_sandbox_cua_smoke_ready=True,
            operator_authorized_host_codex_auth=True,
        )
        assert unsafe_binary["ready"] is False, unsafe_binary
        assert unsafe_binary["first_blocker"] in {
            "runner_binary_not_public_safe",
            "runner_binary_must_be_name_not_path",
        }, unsafe_binary
        assert_no_execution(unsafe_binary)
        assert_public_safe(unsafe_binary, temp_root)


def run_no_task_e2e_fixture_smoke() -> None:
    if shutil.which("node") is None:
        return
    with tempfile.TemporaryDirectory(prefix="ale-host-codex-no-task-e2e-") as tmp:
        temp_root = Path(tmp)
        assets = make_cua_assets(temp_root)
        bin_dir = make_fake_codex(temp_root)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        try:
            payload = build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
                codex_binary="codex-fixture",
                host_auth_cache_present=True,
                host_config_present=True,
                require_host_config=True,
                cua_mcp_assets_root=str(assets),
                ale_sandbox_cua_smoke_ready=True,
                operator_authorized_host_codex_auth=True,
            )
        finally:
            os.environ["PATH"] = old_path
        assert (
            payload["schema_version"]
            == "agents_last_exam_host_codex_cua_no_task_smoke_v0"
        ), payload
        assert payload["ready"] is True, payload
        assert payload["first_blocker"] == "ready_for_task_level_ale_codex_dry_run_gate", payload
        assert payload["codex_exec_surface"]["available"] is True, payload
        assert payload["codex_mcp_config"]["available"] is True, payload
        assert payload["cua_mcp_bridge"]["available"] is True, payload
        assert_no_task_e2e_boundary(payload)
        assert_public_safe(payload, temp_root)


def run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-host-codex-route-cli-") as tmp:
        temp_root = Path(tmp)
        assets = make_cua_assets(temp_root)
        base_cmd = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "ale-host-codex-cli-route",
            "--codex-binary",
            "codex",
            "--assume-codex-binary-available",
            "--codex-version-text",
            "codex-cli 0.128.0",
            "--host-auth-cache-present",
            "--host-config-present",
            "--require-host-config",
            "--cua-mcp-assets-root",
            str(assets),
            "--ale-sandbox-cua-smoke-ready",
            "--operator-authorized-host-codex-auth",
        ]
        result = subprocess.run(
            [*base_cmd, "--require-ready"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["ready"] is True, payload
        assert_no_execution(payload)
        assert_public_safe(payload, temp_root)

        blocked = subprocess.run(
            base_cmd[:-1],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        # The truncated command intentionally omits the operator auth flag value
        # only by removing the flag itself; argparse still succeeds and the
        # route gate reports the missing authorization blocker.
        blocked_payload = json.loads(blocked.stdout)
        assert blocked.returncode == 0, blocked.stderr
        assert blocked_payload["ready"] is False, blocked_payload
        assert blocked_payload["first_blocker"] == "operator_authorization_missing", blocked_payload
        assert_no_execution(blocked_payload)
        assert_public_safe(blocked_payload, temp_root)


def run_cli_no_task_e2e_smoke() -> None:
    if shutil.which("node") is None:
        return
    with tempfile.TemporaryDirectory(prefix="ale-host-codex-no-task-e2e-cli-") as tmp:
        temp_root = Path(tmp)
        assets = make_cua_assets(temp_root)
        bin_dir = make_fake_codex(temp_root)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        cmd = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "ale-host-codex-cua-no-task-e2e",
            "--codex-binary",
            "codex-fixture",
            "--host-auth-cache-present",
            "--host-config-present",
            "--require-host-config",
            "--cua-mcp-assets-root",
            str(assets),
            "--ale-sandbox-cua-smoke-ready",
            "--operator-authorized-host-codex-auth",
            "--require-ready",
        ]
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["ready"] is True, payload
        assert_no_task_e2e_boundary(payload)
        assert_public_safe(payload, temp_root)


if __name__ == "__main__":
    run_fixture_smoke()
    run_no_task_e2e_fixture_smoke()
    run_cli_smoke()
    run_cli_no_task_e2e_smoke()
    print("agents-last-exam-host-codex-cli-route-smoke ok")
