#!/usr/bin/env python3
"""Smoke-test the SkillsBench reverse-tunnel supervisor wrapper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "skillsbench_reverse_tunnel_supervisor.py"


def _fake_ssh(path: Path, log_path: Path) -> None:
    path.write_text(
        f"""#!/usr/bin/env python3
import os
import signal
import sys
import time

log_path = {str(log_path)!r}
args = sys.argv[1:]
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(repr(args) + "\\n")

if "-R" in args:
    running = True
    def stop(_sig, _frame):
        global running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        time.sleep(0.05)
    sys.exit(0)

remote_command = args[-1] if args else ""
if "LOOPX_REVERSE_TUNNEL_PROBE" in remote_command:
    print("HTTP/1.1 200 Connection Established")
    sys.exit(0)

print('{{"ok": true, "source": "fake_remote_command"}}')
sys.exit(0)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_supervisor_holds_tunnel_and_redacts_private_command() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-tunnel-supervisor-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        ssh_log = root / "ssh.log"
        public_output = root / "public.json"
        private_log = root / "private.log"
        _fake_ssh(fake_ssh, ssh_log)

        opaque_destination = "opaque-benchmark-host.example"
        opaque_command = "cd /opaque/workdir && run-skillsbench --task bike-rebalance"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ssh-bin",
                str(fake_ssh),
                "--ssh-destination",
                opaque_destination,
                "--remote-forward",
                "127.0.0.1:18180:127.0.0.1:18180",
                "--remote-command",
                opaque_command,
                "--public-output-path",
                str(public_output),
                "--private-log-path",
                str(private_log),
                "--tunnel-ready-timeout-sec",
                "5",
                "--probe-interval-sec",
                "0.1",
                "--run-timeout-sec",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        persisted = json.loads(public_output.read_text(encoding="utf-8"))
        assert payload == persisted
        assert payload["ok"] is True, payload
        assert payload["tunnel_started"] is True, payload
        assert payload["tunnel_ready"] is True, payload
        assert payload["probe_status"] == "http_connect_ready", payload
        assert payload["remote_command_exit_code"] == 0, payload
        assert payload["raw_ssh_destination_recorded"] is False, payload
        assert payload["raw_remote_command_recorded"] is False, payload
        assert payload["raw_remote_output_recorded"] is False, payload
        assert payload["private_log_written"] is True, payload
        assert payload["remote_forward"]["raw_forward_recorded"] is False, payload
        public_text = json.dumps(payload, sort_keys=True)
        assert opaque_destination not in public_text
        assert opaque_command not in public_text
        assert opaque_command in ssh_log.read_text(encoding="utf-8")
        assert private_log.exists()


if __name__ == "__main__":
    test_supervisor_holds_tunnel_and_redacts_private_command()
    print("skillsbench-reverse-tunnel-supervisor smoke ok")
