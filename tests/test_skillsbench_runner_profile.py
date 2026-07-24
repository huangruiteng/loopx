from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from loopx.benchmark_adapters.skillsbench_runner_profile import (
    SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
    capture_skillsbench_runner_profile,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_probe_ssh_reuses_launcher_option_semantics_without_output(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "runner-profile.json"
    capture_skillsbench_runner_profile(
        profile_path,
        environment={
            "SKILLSBENCH_SSH_DESTINATION": "runner.example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_SSH_OPTIONS": (
                "GSSAPIAuthentication=yes ServerAliveInterval=30"
            ),
        },
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_path = tmp_path / "ssh-argv.json"
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        "#!/bin/sh\n"
        "python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['SSH_ARGV_PATH']).write_text(json.dumps(sys.argv[1:]))\n"
        "PY\n",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            "SSH_ARGV_PATH": str(argv_path),
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.benchmark_adapters.skillsbench_runner_profile",
            "probe-ssh",
            "--profile",
            str(profile_path),
        ],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "benchmark_job_launched": False,
        "ok": True,
        "profile_values_recorded": False,
        "raw_output_recorded": False,
        "reachable": True,
        "result": "reachable",
        "schema_version": "skillsbench_runner_connectivity_probe_v0",
        "task_material_read": False,
    }
    assert json.loads(argv_path.read_text(encoding="utf-8")) == [
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "GSSAPIAuthentication=yes",
        "-o",
        "ServerAliveInterval=30",
        "runner.example.invalid",
        "true",
    ]
    assert SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION == "skillsbench_runner_profile_v0"


def test_probe_ssh_reports_transport_failure_without_raw_output(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "runner-profile.json"
    capture_skillsbench_runner_profile(
        profile_path,
        environment={
            "SKILLSBENCH_SSH_DESTINATION": "runner.example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
        },
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text("#!/bin/sh\nexit 255\n", encoding="utf-8")
    fake_ssh.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.benchmark_adapters.skillsbench_runner_profile",
            "probe-ssh",
            "--profile",
            str(profile_path),
        ],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 3
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "benchmark_job_launched": False,
        "ok": True,
        "profile_values_recorded": False,
        "raw_output_recorded": False,
        "reachable": False,
        "result": "transport_unavailable",
        "schema_version": "skillsbench_runner_connectivity_probe_v0",
        "task_material_read": False,
    }
