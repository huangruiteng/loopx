#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_runner_profile import (
    SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
    SkillsBenchRunnerProfileError,
    capture_skillsbench_runner_profile,
    default_skillsbench_runner_profile_path,
    load_skillsbench_runner_profile,
    skillsbench_runner_profile_shell_exports,
    skillsbench_runner_profile_summary,
)


LAUNCHER = REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"
PROFILE_MODULE = (
    REPO_ROOT
    / "loopx"
    / "benchmark_adapters"
    / "skillsbench_runner_profile.py"
)


def _environment() -> dict[str, str]:
    return {
        "SKILLSBENCH_SSH_DESTINATION": "runner.example.invalid",
        "SKILLSBENCH_REMOTE_ROOT": "/opaque/source-7d2d9f4a",
        "SKILLSBENCH_ROOT": "/opaque/benchmark-351d9b72",
        "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "a" * 40,
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_COMMAND": (
            "private-probe-marker"
        ),
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_SOLVER_COMMAND": (
            "private-solver-marker"
        ),
        "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND": (
            "private-validator-marker"
        ),
    }


def _expect_error(code: str, callback: object) -> None:
    try:
        callback()  # type: ignore[operator]
    except SkillsBenchRunnerProfileError as error:
        assert error.code == code, error.code
    else:
        raise AssertionError(f"expected runner profile error: {code}")


def _copy_launcher_fixture(root: Path) -> Path:
    launcher = root / "scripts" / LAUNCHER.name
    launcher.parent.mkdir(parents=True)
    shutil.copy2(LAUNCHER, launcher)
    package = root / "loopx" / "benchmark_adapters"
    package.mkdir(parents=True)
    (root / "loopx" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(PROFILE_MODULE, package / PROFILE_MODULE.name)
    return launcher


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-profile-") as value:
        root = Path(value)
        profile_path = root / "private" / "runner-profile.json"
        default_profile_path = default_skillsbench_runner_profile_path(
            {"XDG_STATE_HOME": str(root / "state")}
        )
        assert default_profile_path == (
            root / "state" / "loopx" / "skillsbench" / "runner-profile.json"
        )
        source_environment = _environment()
        _expect_error(
            "required_runner_environment_missing",
            lambda: capture_skillsbench_runner_profile(
                root / "private" / "incomplete.json",
                environment={},
            ),
        )
        summary = capture_skillsbench_runner_profile(
            profile_path,
            environment=source_environment,
        )
        assert stat.S_IMODE(profile_path.stat().st_mode) == 0o600
        assert summary == {
            "ok": True,
            "schema_version": SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
            "environment_key_count": len(source_environment),
            "required_environment_complete": True,
            "profile_path_recorded": False,
            "profile_values_recorded": False,
            "owner_only_permissions_required": True,
        }
        loaded = load_skillsbench_runner_profile(profile_path)
        assert loaded == source_environment
        assert not set(source_environment.values()) & set(
            skillsbench_runner_profile_summary(loaded).values()
        )
        symlink_path = root / "private" / "runner-profile-link.json"
        symlink_path.symlink_to(profile_path)
        _expect_error(
            "profile_not_regular_file",
            lambda: load_skillsbench_runner_profile(symlink_path),
        )

        exports = skillsbench_runner_profile_shell_exports(
            loaded,
            current_environment={
                "SKILLSBENCH_REMOTE_ROOT": "/explicit/source-override"
            },
        )
        assert "SKILLSBENCH_REMOTE_ROOT" not in exports
        assert "SKILLSBENCH_SSH_DESTINATION" in exports

        profile_path.chmod(0o644)
        _expect_error(
            "profile_permissions_not_owner_only",
            lambda: load_skillsbench_runner_profile(profile_path),
        )
        profile_path.chmod(0o600)

        profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        profile_payload["environment"]["SKILLSBENCH_UNKNOWN_PRIVATE_VALUE"] = "x"
        profile_path.write_text(
            json.dumps(profile_payload),
            encoding="utf-8",
        )
        profile_path.chmod(0o600)
        _expect_error(
            "profile_environment_key_unknown",
            lambda: load_skillsbench_runner_profile(profile_path),
        )

        capture_skillsbench_runner_profile(
            profile_path,
            environment=source_environment,
            force=True,
        )
        launcher = _copy_launcher_fixture(root / "fixture-repo")
        launch_environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SKILLSBENCH_")
        }
        launch_environment.update(
            {
                "SKILLSBENCH_ROUTE": "loopx-turn-agent-cli",
                "SKILLSBENCH_RUN_STAMP": "runnerprofile-smoke",
                "SKILLSBENCH_DOCKER_PROXY_HOST": "docker-proxy.example.invalid",
                "SKILLSBENCH_DOCKER_API_VERSION": "1.43",
                "XDG_STATE_HOME": str(root / "state"),
            }
        )
        default_profile_path.parent.mkdir(parents=True)
        shutil.copy2(profile_path, default_profile_path)
        completed = subprocess.run(
            [
                "bash",
                str(launcher),
                "--dry-run",
                "fixture-task",
                "runner-profile-smoke",
                "18181",
            ],
            cwd=launcher.parents[1],
            env=launch_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        output = completed.stdout
        assert "runner_profile_loaded=true" in output
        assert "runner_profile_path_recorded=false" in output
        assert "runner_profile_values_recorded=false" in output
        assert "docker_proxy_host_recorded=false" in output
        assert launch_environment["SKILLSBENCH_DOCKER_PROXY_HOST"] not in output
        assert (
            launch_environment["SKILLSBENCH_DOCKER_PROXY_HOST"]
            not in completed.stderr
        )
        assert "private_runner_command_values_redacted=true" in output
        assert "loopx_turn_validation_command_configured=1" in output
        for key, private_value in source_environment.items():
            assert private_value not in output, key
            assert private_value not in completed.stderr, key

    print("skillsbench-runner-profile-smoke: ok")


if __name__ == "__main__":
    main()
