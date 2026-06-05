#!/usr/bin/env python3
"""Smoke-test LaunchAgent status output without touching real launchctl."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHAGENT_SCRIPT = REPO_ROOT / "scripts" / "macos-dashboard-launchagent.sh"


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run_status(fake_bin: Path, home: Path, *, schema_version: int) -> str:
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "FAKE_STATUS_CONTRACT_SCHEMA_VERSION": str(schema_version),
        "GOAL_HARNESS_STATUS_CONTRACT_MIN_VERSION": "2",
    }
    result = subprocess.run(
        [str(LAUNCHAGENT_SCRIPT), "status"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-launchagent-status-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        fake_bin = tmp / "bin"
        home = tmp / "home"
        fake_bin.mkdir()
        home.mkdir()

        write_executable(
            fake_bin / "uname",
            "#!/usr/bin/env bash\nprintf 'Darwin\\n'\n",
        )
        write_executable(
            fake_bin / "launchctl",
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == \"print\" ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "echo \"unexpected launchctl args: $*\" >&2\n"
            "exit 2\n",
        )
        write_executable(
            fake_bin / "curl",
            "#!/usr/bin/env bash\n"
            "version=\"${FAKE_STATUS_CONTRACT_SCHEMA_VERSION:-0}\"\n"
            "cat <<EOF\n"
            "{\"ok\":true,\"status_contract\":{\"schema_version\":${version},\"producer\":\"goal-harness status\"}}\n"
            "EOF\n",
        )

        old_output = run_status(fake_bin, home, schema_version=1)
        assert "- com.goal-harness.status: loaded" in old_output, old_output
        assert "- com.goal-harness.dashboard: loaded" in old_output, old_output
        assert "- status_contract: schema_version=1 producer=goal-harness status expected>=2" in old_output, old_output
        assert "warning: status feed is using an old contract; run:" in old_output, old_output
        assert "macos-dashboard-launchagent.sh restart" in old_output, old_output

        current_output = run_status(fake_bin, home, schema_version=2)
        assert "- status_contract: schema_version=2 producer=goal-harness status expected>=2" in current_output, current_output
        assert "warning: status feed is using an old contract" not in current_output, current_output
        assert "LaunchAgents:" in current_output, current_output
        assert "URLs:" in current_output, current_output
        assert "Logs:" in current_output, current_output

    print("macos-dashboard-launchagent-status-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
