#!/usr/bin/env python3
"""Smoke-test the SkillsBench reverse-channel bridge helper."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = REPO_ROOT / "scripts" / "skillsbench_reverse_channel_bridge.py"


def wait_for_socket(path: Path, proc: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"server exited early: {proc.returncode}")
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"socket did not appear: {path}")


def connect_only_probe(path: Path) -> None:
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.settimeout(1)
        sock.connect(str(path))
    finally:
        sock.close()


def test_codex_client_writes_last_message_and_rewrites_bridge() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-bridge-smoke-") as tmp:
        root = Path(tmp)
        fake_codex = root / "fake-codex"
        prompt_dump = root / "prompt.txt"
        fake_codex.write_text(
            f"""#!/usr/bin/env python3
import os, sys, time
from pathlib import Path

args = sys.argv[1:]
stdin_text = sys.stdin.read()
if stdin_text:
    raise SystemExit(41)
prompt = args[-1]
Path({str(prompt_dump)!r}).write_text(prompt, encoding='utf-8')
out = Path(args[args.index('--output-last-message') + 1])
time.sleep(0.35)
out.write_text('LOOPX_REVERSE_READY\\n', encoding='utf-8')
print('codex stdout ok')
print('codex stderr ok', file=sys.stderr)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        socket_path = root / "codex.sock"
        local_bridge = root / "local-json-bridge"
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-codex",
                "--socket",
                str(socket_path),
                "--codex-bin",
                str(fake_codex),
                "--prompt-bridge-command",
                str(local_bridge),
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
            connect_only_probe(socket_path)
            assert server.poll() is None
            client = root / "codex-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    "codex",
                    "--socket",
                    str(socket_path),
                    "--output",
                    str(client),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            remote_last = root / "remote-last-message.txt"
            prompt = "Private bridge command:\n/remote/tmp/bridge\n\nTask"
            env = os.environ.copy()
            env["LOOPX_REVERSE_CONNECT_TIMEOUT_SEC"] = "0.1"
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            proc = subprocess.run(
                [
                    str(client),
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "-C",
                    "/remote/tmp/does-not-exist-on-local-host",
                    "--output-last-message",
                    str(remote_last),
                    "--json",
                    prompt,
                ],
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            assert "codex stdout ok" in proc.stdout
            assert "codex stderr ok" in proc.stderr
            assert remote_last.read_text(encoding="utf-8") == "LOOPX_REVERSE_READY\n"
            rewritten = prompt_dump.read_text(encoding="utf-8")
            assert str(local_bridge) in rewritten
            assert "/remote/tmp/bridge" not in rewritten
        finally:
            server.wait(timeout=5)


def test_json_client_forwards_stdin_to_bridge_command() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-json-smoke-") as tmp:
        root = Path(tmp)
        fake_bridge = root / "fake-json-bridge"
        fake_bridge.write_text(
            """#!/usr/bin/env python3
import json, os, sys, time
payload = json.loads(sys.stdin.read() or '{}')
time.sleep(0.35)
print(json.dumps({
    'ok': True,
    'operation': payload.get('operation'),
    'ai_addr_present': bool(os.environ.get('AI_ADDR')),
    'ai_port_present': bool(os.environ.get('AI_PORT')),
    'raw_task_text_recorded': False,
    'credential_values_recorded': False,
}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        socket_path = root / "json.sock"
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-json",
                "--socket",
                str(socket_path),
                "--bridge-command",
                str(fake_bridge),
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
            connect_only_probe(socket_path)
            assert server.poll() is None
            client = root / "json-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    "json",
                    "--socket",
                    str(socket_path),
                    "--output",
                    str(client),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            env = os.environ.copy()
            env["LOOPX_REVERSE_CONNECT_TIMEOUT_SEC"] = "0.1"
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            env["AI_ADDR"] = "127.0.0.1"
            env["AI_PORT"] = "2022"
            proc = subprocess.run(
                [str(client)],
                input=json.dumps({"operation": "exec", "cwd": "/app"}),
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            response = json.loads(proc.stdout)
            assert response["ok"] is True
            assert response["operation"] == "exec"
            assert response["ai_addr_present"] is True
            assert response["ai_port_present"] is True
            assert response["raw_task_text_recorded"] is False
            assert response["credential_values_recorded"] is False
        finally:
            server.wait(timeout=5)


def test_json_client_expands_allowed_env_template_for_nested_bridge() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-json-env-smoke-") as tmp:
        root = Path(tmp)
        fake_bridge = root / "fake-nested-json-bridge"
        fake_bridge.write_text(
            """#!/usr/bin/env python3
import json, os, sys

assignments = sys.argv[1:]
payload = json.loads(sys.stdin.read() or '{}')
print(json.dumps({
    'ok': True,
    'operation': payload.get('operation'),
    'argv_has_ai_addr': any(item.startswith('AI_ADDR=') for item in assignments),
    'argv_has_ai_port': any(item.startswith('AI_PORT=') for item in assignments),
    'argv_has_runtime_root': any(item.startswith('GOAL_HARNESS_REMOTE_BENCH_ROOT=') for item in assignments),
    'raw_task_text_recorded': False,
    'credential_values_recorded': False,
}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        socket_path = root / "json-env.sock"
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-json",
                "--socket",
                str(socket_path),
                "--bridge-command",
                f"{fake_bridge} {{loopx_allowed_env}}",
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
            client = root / "json-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    "json",
                    "--socket",
                    str(socket_path),
                    "--output",
                    str(client),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            env = os.environ.copy()
            env["LOOPX_REVERSE_CONNECT_TIMEOUT_SEC"] = "0.1"
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            env["AI_ADDR"] = "127.0.0.1"
            env["AI_PORT"] = "2022"
            env["GOAL_HARNESS_REMOTE_BENCH_ROOT"] = "/tmp/loopx-bench"
            proc = subprocess.run(
                [str(client)],
                input=json.dumps({"operation": "exec", "cwd": "/app"}),
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            response = json.loads(proc.stdout)
            assert response["ok"] is True
            assert response["operation"] == "exec"
            assert response["argv_has_ai_addr"] is True
            assert response["argv_has_ai_port"] is True
            assert response["argv_has_runtime_root"] is True
            assert response["raw_task_text_recorded"] is False
            assert response["credential_values_recorded"] is False
        finally:
            server.wait(timeout=5)


def test_socket_probe_reports_missing_or_orphaned() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-probe-smoke-") as tmp:
        missing = Path(tmp) / "missing.sock"
        proc = subprocess.run(
            [
                sys.executable,
                str(BRIDGE),
                "probe-socket",
                "--socket",
                str(missing),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["ready"] is False
        assert payload["first_blocker"] == "skillsbench_reverse_channel_socket_missing"


def main() -> int:
    test_codex_client_writes_last_message_and_rewrites_bridge()
    test_json_client_forwards_stdin_to_bridge_command()
    test_json_client_expands_allowed_env_template_for_nested_bridge()
    test_socket_probe_reports_missing_or_orphaned()
    print("skillsbench reverse-channel bridge smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
