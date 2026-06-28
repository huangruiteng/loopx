#!/usr/bin/env python3
"""Smoke-test the SkillsBench reverse-channel bridge helper."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
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


def wait_for_path(path: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"path did not appear: {path}")


def run_empty_response_server(path: Path) -> threading.Thread:
    def serve() -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX)
        try:
            server.bind(str(path))
            path.chmod(0o600)
            server.listen(1)
            conn, _ = server.accept()
            with conn:
                conn.recv(65536)
        finally:
            server.close()
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    thread = threading.Thread(target=serve)
    thread.start()
    wait_for_path(path)
    return thread


def test_reverse_channel_clients_fail_closed_on_empty_response() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-empty-response-") as tmp:
        root = Path(tmp)
        for kind in ("codex", "json"):
            socket_path = root / f"{kind}.sock"
            server = run_empty_response_server(socket_path)
            client = root / f"{kind}-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    kind,
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
            args = [str(client), "exec"] if kind == "codex" else [str(client)]
            proc = subprocess.run(
                args,
                input="{}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            assert proc.returncode == 125, (kind, proc.returncode, proc.stderr)
            assert "reverse channel response missing" in proc.stderr
            server.join(timeout=5)
            assert not server.is_alive()


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
if not stdin_text:
    raise SystemExit(41)
if any('Private bridge command:' in item or 'Task' in item for item in args):
    raise SystemExit(42)
prompt = stdin_text
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
            assert "loopx-local-prompt-bridge" in rewritten
            assert str(local_bridge) not in rewritten
            assert "/remote/tmp/bridge" not in rewritten
        finally:
            server.wait(timeout=5)


def test_codex_bridge_template_preserves_dynamic_private_command() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-bridge-template-") as tmp:
        root = Path(tmp)
        fake_codex = root / "fake-codex"
        fake_bridge = root / "fake-json-bridge"
        bridge_args = root / "bridge-args.json"
        fake_bridge.write_text(
            f"""#!/usr/bin/env python3
import json, sys
Path = __import__('pathlib').Path
Path({str(bridge_args)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')
payload = json.loads(sys.stdin.read() or '{{}}')
print(json.dumps({{
    'ok': True,
    'operation': payload.get('operation'),
    'raw_task_text_recorded': False,
    'credential_values_recorded': False,
}}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
if not prompt:
    raise SystemExit(41)
if any('Private bridge command:' in item for item in args):
    raise SystemExit(42)
bridge = prompt.split('Private bridge command:\\n', 1)[1].split('\\n', 1)[0]
env = os.environ.copy()
env['AI_ADDR'] = '127.0.0.1'
env['AI_PORT'] = '2022'
proc = subprocess.run(
    [bridge],
    input=json.dumps({'operation': 'exec', 'cwd': '/app', 'command': 'pwd'}),
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    check=False,
)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
out = Path(args[args.index('--output-last-message') + 1])
out.write_text('LOOPX_REVERSE_TEMPLATE_READY\\n', encoding='utf-8')
raise SystemExit(proc.returncode)
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        socket_path = root / "codex.sock"
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
                f"{fake_bridge} {{private_bridge_command_sh}} {{loopx_allowed_env}}",
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
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
            dynamic_bridge = "/remote/tmp/dynamic bridge --compose-file /tmp/c.yml"
            prompt = f"Private bridge command:\n{dynamic_bridge}\n\nTask"
            proc = subprocess.run(
                [
                    str(client),
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "-C",
                    "/remote/tmp/workspace",
                    "--output-last-message",
                    str(remote_last),
                    "--json",
                    prompt,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            response = json.loads(proc.stdout)
            assert response["ok"] is True
            argv = json.loads(bridge_args.read_text(encoding="utf-8"))
            assert dynamic_bridge in argv
            assert any(item.startswith("AI_ADDR=") for item in argv), argv
            assert any(item.startswith("AI_PORT=") for item in argv), argv
            assert remote_last.read_text(encoding="utf-8") == (
                "LOOPX_REVERSE_TEMPLATE_READY\n"
            )
        finally:
            server.wait(timeout=5)


def test_codex_bridge_template_classifies_ssh_unavailable() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-bridge-ssh-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        fake_ssh.write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
        fake_ssh.chmod(0o700)
        fake_codex = root / "fake-codex"
        fake_codex.write_text(
            f"""#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path

os.environ["PATH"] = {str(root)!r} + os.pathsep + os.environ.get("PATH", "")
args = sys.argv[1:]
prompt = sys.stdin.read()
bridge = prompt.split('Private bridge command:\\n', 1)[1].split('\\n', 1)[0]
subprocess.run(
    [bridge],
    input=json.dumps({{'operation': 'exec', 'cwd': '/app', 'command': 'true'}}),
    text=True,
    check=False,
)
out = Path(args[args.index('--output-last-message') + 1])
out.write_text('LOOPX_REVERSE_SSH_CLASSIFIED\\n', encoding='utf-8')
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        socket_path = root / "codex.sock"
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
                "ssh loopx-unavailable.example",
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
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
            agent_ops = root / "agent-ops.jsonl"
            env = os.environ.copy()
            env["LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH"] = str(agent_ops)
            proc = subprocess.run(
                [
                    str(client),
                    "exec",
                    "--output-last-message",
                    str(root / "remote-last-message.txt"),
                    "Private bridge command:\n/not-recorded\n\nTask",
                ],
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            records = [
                json.loads(line)
                for line in agent_ops.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert records[-1]["record_phase"] == "complete", records
            assert records[-1]["failure_category"] == "bridge_ssh_unavailable"
        finally:
            server.wait(timeout=5)


def test_codex_client_plain_prompt_does_not_require_bridge_action() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-plain-prompt-") as tmp:
        root = Path(tmp)
        fake_codex = root / "fake-codex"
        prompt_dump = root / "plain-prompt.txt"
        fake_codex.write_text(
            f"""#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
if not prompt:
    raise SystemExit(41)
if any('plain health prompt' in item for item in args):
    raise SystemExit(42)
Path({str(prompt_dump)!r}).write_text(prompt, encoding='utf-8')
out = Path(args[args.index('--output-last-message') + 1])
out.write_text('LOOPX_REVERSE_PLAIN_READY\\n', encoding='utf-8')
print('plain codex stdout ok')
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        socket_path = root / "codex.sock"
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
                "false",
                "--first-action-timeout-sec",
                "1",
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_socket(socket_path, server)
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
            proc = subprocess.run(
                [
                    str(client),
                    "exec",
                    "--output-last-message",
                    str(remote_last),
                    "--json",
                ],
                check=False,
                input="plain health prompt",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            assert "plain codex stdout ok" in proc.stdout
            assert prompt_dump.read_text(encoding="utf-8") == "plain health prompt"
            assert remote_last.read_text(encoding="utf-8") == (
                "LOOPX_REVERSE_PLAIN_READY\n"
            )
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


def test_json_client_forwards_private_bridge_command_template() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-json-private-") as tmp:
        root = Path(tmp)
        fake_bridge = root / "fake-private-json-bridge"
        marker = root / "private-command-marker"
        fake_bridge.write_text(
            """#!/usr/bin/env python3
import json
import subprocess
import sys

private_command = sys.argv[1]
payload = json.loads(sys.stdin.read() or '{}')
proc = subprocess.run(
    private_command,
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    check=False,
)
print(json.dumps({
    'ok': proc.returncode == 0,
    'operation': payload.get('operation'),
    'private_command_seen': bool(private_command),
    'raw_task_text_recorded': False,
    'credential_values_recorded': False,
}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        socket_path = root / "json-private.sock"
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-json",
                "--socket",
                str(socket_path),
                "--bridge-command",
                f"{fake_bridge} {{private_bridge_command_sh}}",
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
            env["LOOPX_PRIVATE_BRIDGE_COMMAND"] = (
                f"{sys.executable} -c \"from pathlib import Path; "
                f"Path({str(marker)!r}).write_text('ok', encoding='utf-8'); "
                "print('private-ok')\""
            )
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
            assert response["private_command_seen"] is True
            assert marker.read_text(encoding="utf-8") == "ok"
            assert response["raw_task_text_recorded"] is False
            assert response["credential_values_recorded"] is False
        finally:
            server.wait(timeout=5)


def test_json_preflight_does_not_require_target_env_or_bridge_command() -> None:
    with tempfile.TemporaryDirectory(prefix="lrjp-") as tmp:
        root = Path(tmp)
        fake_bridge = root / "fake-json-bridge"
        marker = root / "bridge-invoked"
        fake_bridge.write_text(
            f"""#!/usr/bin/env python3
from pathlib import Path
Path({str(marker)!r}).write_text('unexpected', encoding='utf-8')
raise SystemExit(42)
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        socket_path = root / "json-preflight.sock"
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
            env.pop("AI_ADDR", None)
            env.pop("AI_PORT", None)
            env["LOOPX_REVERSE_CONNECT_TIMEOUT_SEC"] = "0.1"
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            proc = subprocess.run(
                [str(client)],
                input=json.dumps({"operation": "preflight"}),
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            response = json.loads(proc.stdout)
            assert response["ok"] is True
            assert response["operation"] == "preflight"
            assert response["raw_task_text_recorded"] is False
            assert response["credential_values_recorded"] is False
            assert marker.exists() is False
        finally:
            server.wait(timeout=5)


def test_json_file_queue_client_forwards_without_socket_access() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-json-file-") as tmp:
        root = Path(tmp)
        queue_dir = root / "queue"
        fake_bridge = root / "fake-json-bridge"
        fake_bridge.write_text(
            """#!/usr/bin/env python3
import json, os, sys

payload = json.loads(sys.stdin.read() or '{}')
print(json.dumps({
    'ok': True,
    'operation': payload.get('operation'),
    'ai_addr_present': bool(os.environ.get('AI_ADDR')),
    'raw_task_text_recorded': False,
    'credential_values_recorded': False,
}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-json-file",
                "--queue-dir",
                str(queue_dir),
                "--bridge-command",
                str(fake_bridge),
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_path(queue_dir / "requests")
            client = root / "json-file-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    "json-file",
                    "--queue-dir",
                    str(queue_dir),
                    "--output",
                    str(client),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            env = os.environ.copy()
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            env["AI_ADDR"] = "127.0.0.1"
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
            assert response["raw_task_text_recorded"] is False
            assert response["credential_values_recorded"] is False
        finally:
            server.wait(timeout=5)


def test_json_file_preflight_does_not_invoke_bridge_command() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-json-file-preflight-") as tmp:
        root = Path(tmp)
        queue_dir = root / "queue"
        fake_bridge = root / "fake-json-bridge"
        marker = root / "bridge-invoked"
        fake_bridge.write_text(
            f"""#!/usr/bin/env python3
from pathlib import Path
Path({str(marker)!r}).write_text('unexpected', encoding='utf-8')
raise SystemExit(42)
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o700)
        server = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "serve-json-file",
                "--queue-dir",
                str(queue_dir),
                "--bridge-command",
                str(fake_bridge),
                "--once",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_path(queue_dir / "requests")
            client = root / "json-file-client"
            subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE),
                    "write-client",
                    "--kind",
                    "json-file",
                    "--queue-dir",
                    str(queue_dir),
                    "--output",
                    str(client),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            env = os.environ.copy()
            env["LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC"] = "5"
            proc = subprocess.run(
                [str(client)],
                input=json.dumps({"operation": "preflight"}),
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            response = json.loads(proc.stdout)
            assert response["ok"] is True
            assert response["operation"] == "preflight"
            assert marker.exists() is False
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
    test_codex_bridge_template_preserves_dynamic_private_command()
    test_codex_client_plain_prompt_does_not_require_bridge_action()
    test_json_client_forwards_stdin_to_bridge_command()
    test_json_client_expands_allowed_env_template_for_nested_bridge()
    test_json_client_forwards_private_bridge_command_template()
    test_json_preflight_does_not_require_target_env_or_bridge_command()
    test_json_file_queue_client_forwards_without_socket_access()
    test_json_file_preflight_does_not_invoke_bridge_command()
    test_socket_probe_reports_missing_or_orphaned()
    print("skillsbench reverse-channel bridge smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
