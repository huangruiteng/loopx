#!/usr/bin/env python3
"""Hold a reverse-tunnel session while running a remote SkillsBench command.

This helper is intentionally local-side: the remote benchmark host cannot
create an ``ssh -R`` tunnel back to itself. The launcher owns the tunnel process,
probes the remote loopback proxy through SSH, runs one remote command, and then
cleans the tunnel up. Public output records only lifecycle status and compact
counts; raw SSH destinations, remote commands, proxy URLs, and command output
are private.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core.remote_closeout import (
    build_remote_benchmark_closeout_contract,
    closeout_remote_benchmark_batch,
)


SCHEMA_VERSION = "skillsbench_reverse_tunnel_supervisor_v0"
DEFAULT_REMOTE_FORWARD = "127.0.0.1:18180:127.0.0.1:18180"
DEFAULT_TEST_HOST = "chatgpt.com"
DEFAULT_TEST_PORT = 443
BRIDGE_HELPER = (
    Path(__file__).resolve().with_name("skillsbench_reverse_channel_bridge.py")
)


def _host_kind(value: str) -> str:
    normalized = value.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return "loopback"
    if normalized.startswith("10.") or normalized.startswith("192.168."):
        return "private"
    if normalized.startswith("172."):
        try:
            second_octet = int(normalized.split(".", 2)[1])
        except (IndexError, ValueError):
            second_octet = -1
        if 16 <= second_octet <= 31:
            return "private"
    return "public_or_unknown"


def _parse_remote_forward(value: str) -> dict[str, Any]:
    parts = value.split(":")
    if len(parts) != 4:
        raise ValueError(
            "--remote-forward must use host:port:host:port form, "
            "for example 127.0.0.1:18180:127.0.0.1:18180"
        )
    remote_host, remote_port, local_host, local_port = parts
    return {
        "remote_host": remote_host,
        "remote_port": int(remote_port),
        "local_host": local_host,
        "local_port": int(local_port),
    }


def _forward_public_contract(remote_forward: str) -> dict[str, Any]:
    parsed = _parse_remote_forward(remote_forward)
    return {
        "remote_host_kind": _host_kind(parsed["remote_host"]),
        "remote_port": parsed["remote_port"],
        "local_host_kind": _host_kind(parsed["local_host"]),
        "local_port": parsed["local_port"],
        "raw_forward_recorded": False,
    }


def _ssh_base_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.ssh_bin,
        "-x",
        "-T",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "ControlPersist=no",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ServerAliveInterval={max(1, int(args.server_alive_interval_sec))}",
        "-o",
        f"ServerAliveCountMax={max(1, int(args.server_alive_count_max))}",
    ]
    for option in args.ssh_option or []:
        command.extend(["-o", option])
    return command


def _json_bridge_requested(args: argparse.Namespace) -> bool:
    return bool(
        args.json_bridge
        or args.json_bridge_command
        or args.json_remote_socket
        or args.json_remote_client_path
    )


def _json_bridge_public_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "enabled": _json_bridge_requested(args),
        "server_started": False,
        "local_socket_ready": False,
        "reverse_socket_forward_requested": bool(args.json_remote_socket),
        "remote_socket_ready": False,
        "remote_client_materialized": False,
        "probe_policy": args.json_bridge_probe_policy,
        "sandbox_env_probe_deferred": (
            args.json_bridge_probe_policy == "sandbox-env-deferred"
        ),
        "sandbox_env_probe_defer_reason": (
            "benchflow_ai_addr_ai_port_available_only_inside_task_sandbox"
            if args.json_bridge_probe_policy == "sandbox-env-deferred"
            else ""
        ),
        "raw_bridge_command_recorded": False,
        "raw_socket_paths_recorded": False,
        "raw_client_path_recorded": False,
        "raw_probe_output_recorded": False,
        "remote_socket_cleanup": _remote_json_socket_cleanup_public_contract(args),
    }


def _resolved_json_local_socket(
    args: argparse.Namespace,
    runtime_dir: Path,
) -> Path:
    if args.json_local_socket:
        return Path(args.json_local_socket).expanduser()
    return runtime_dir / "json-bridge.sock"


def _cleanup_stale_local_forward(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requested": bool(args.cleanup_stale_local_forward),
        "matched_count": 0,
        "terminated_count": 0,
        "raw_process_args_recorded": False,
    }
    if not args.cleanup_stale_local_forward:
        return payload
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        payload["first_blocker"] = "stale_forward_scan_failed"
        return payload

    current_pid = os.getpid()
    candidates: list[int] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if (
            args.ssh_destination in command
            and args.remote_forward in command
            and " -R " in f" {command} "
        ):
            candidates.append(pid)
    payload["matched_count"] = len(candidates)
    for pid in candidates:
        try:
            os.kill(pid, signal.SIGTERM)
            payload["terminated_count"] = int(payload["terminated_count"]) + 1
        except (OSError, ProcessLookupError):
            continue
    if candidates:
        time.sleep(0.2)
    return payload


def _start_json_bridge_server(
    args: argparse.Namespace,
    *,
    socket_path: Path,
) -> subprocess.Popen[Any]:
    return subprocess.Popen(
        [
            sys.executable,
            str(BRIDGE_HELPER),
            "serve-json",
            "--socket",
            str(socket_path),
            "--bridge-command",
            args.json_bridge_command,
            "--timeout-sec",
            str(max(1.0, float(args.json_server_timeout_sec))),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _probe_local_json_socket(args: argparse.Namespace, socket_path: Path) -> bool:
    deadline = time.monotonic() + max(1.0, float(args.json_socket_ready_timeout_sec))
    while time.monotonic() < deadline:
        if socket_path.exists():
            return True
        time.sleep(max(0.05, float(args.probe_interval_sec)))
    return False


def _run_remote_shell_command(
    args: argparse.Namespace,
    command: str,
    *,
    timeout_sec: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_ssh_base_command(args), args.ssh_destination, command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(1.0, float(timeout_sec)),
        check=False,
    )


def _probe_remote_json_socket(args: argparse.Namespace) -> bool:
    command = "test -S " + shlex.quote(args.json_remote_socket)
    try:
        proc = _run_remote_shell_command(
            args,
            command,
            timeout_sec=args.json_socket_ready_timeout_sec,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _remote_json_socket_cleanup_public_contract(
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "requested": bool(_json_bridge_requested(args) and args.json_remote_socket),
        "attempted": False,
        "ok": False,
        "raw_socket_paths_recorded": False,
        "raw_output_recorded": False,
    }


def _cleanup_remote_json_socket(args: argparse.Namespace) -> dict[str, Any]:
    payload = _remote_json_socket_cleanup_public_contract(args)
    if not payload["requested"]:
        return payload
    payload["attempted"] = True
    command = "rm -f -- " + shlex.quote(args.json_remote_socket)
    try:
        proc = _run_remote_shell_command(
            args,
            command,
            timeout_sec=args.remote_setup_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        payload["first_blocker"] = "json_bridge_remote_socket_cleanup_timeout"
        return payload
    except OSError:
        payload["first_blocker"] = "json_bridge_remote_socket_cleanup_launch_failed"
        return payload
    payload["exit_code"] = proc.returncode
    payload["stdout_size_bucket"] = _size_bucket(proc.stdout or "")
    payload["stderr_size_bucket"] = _size_bucket(proc.stderr or "")
    payload["ok"] = proc.returncode == 0
    if proc.returncode != 0:
        payload["first_blocker"] = "json_bridge_remote_socket_cleanup_exit_nonzero"
    return payload


def _materialize_remote_json_client(
    args: argparse.Namespace, runtime_dir: Path
) -> bool:
    local_client = runtime_dir / "json-bridge-client"
    try:
        subprocess.run(
            [
                sys.executable,
                str(BRIDGE_HELPER),
                "write-client",
                "--kind",
                "json",
                "--socket",
                args.json_remote_socket,
                "--output",
                str(local_client),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=max(1.0, float(args.remote_setup_timeout_sec)),
            check=True,
        )
        client_text = local_client.read_text(encoding="utf-8")
        remote_path = args.json_remote_client_path
        remote_parent = os.path.dirname(remote_path) or "."
        remote_command = (
            "umask 077; mkdir -p "
            + shlex.quote(remote_parent)
            + "; cat > "
            + shlex.quote(remote_path)
            + "; chmod 700 "
            + shlex.quote(remote_path)
        )
        proc = subprocess.run(
            [*_ssh_base_command(args), args.ssh_destination, remote_command],
            input=client_text,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=max(1.0, float(args.remote_setup_timeout_sec)),
            check=False,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _render_remote_command(args: argparse.Namespace) -> str:
    command = args.remote_command
    if _json_bridge_requested(args):
        command = command.replace(
            "{json_bridge_client}",
            shlex.quote(args.json_remote_client_path),
        )
    return command


def _remote_json_bridge_env_prefix(args: argparse.Namespace) -> str:
    if not _json_bridge_requested(args):
        return ""
    assignments = {
        "LOOPX_SKILLSBENCH_JSON_BRIDGE_CLIENT": args.json_remote_client_path,
        "LOOPX_REVERSE_JSON_TIMEOUT_SEC": str(int(args.json_server_timeout_sec)),
    }
    return " ".join(
        f"{name}={shlex.quote(value)}" for name, value in assignments.items()
    )


def _remote_command_with_bridge_env(args: argparse.Namespace) -> str:
    rendered = _render_remote_command(args)
    prefix = _remote_json_bridge_env_prefix(args)
    if not prefix:
        return rendered
    return prefix + " " + rendered


def _tunnel_command(
    args: argparse.Namespace,
    *,
    json_local_socket: Path | None = None,
) -> list[str]:
    keepalive = max(1, int(args.keepalive_interval_sec))
    remote_keepalive = (
        f"while true; do sleep {keepalive}; "
        "echo loopx_reverse_tunnel_keepalive >&2; done"
    )
    command = [
        *_ssh_base_command(args),
        "-o",
        "ExitOnForwardFailure=yes",
    ]
    if _json_bridge_requested(args) and json_local_socket is not None:
        command.extend(
            [
                "-o",
                "StreamLocalBindUnlink=yes",
                "-R",
                f"{args.json_remote_socket}:{json_local_socket}",
            ]
        )
    command.extend(
        [
            "-R",
            args.remote_forward,
            args.ssh_destination,
            remote_keepalive,
        ]
    )
    return command


def _probe_command(args: argparse.Namespace) -> str:
    parsed = _parse_remote_forward(args.remote_forward)
    timeout = max(1.0, float(args.probe_timeout_sec))
    code = (
        "# LOOPX_REVERSE_TUNNEL_PROBE\n"
        "import socket, sys\n"
        f"proxy_host = {parsed['remote_host']!r}\n"
        f"proxy_port = {parsed['remote_port']!r}\n"
        f"test_host = {args.test_host!r}\n"
        f"test_port = {int(args.test_port)!r}\n"
        f"timeout = {timeout!r}\n"
        "sock = socket.create_connection((proxy_host, proxy_port), timeout)\n"
        "sock.settimeout(timeout)\n"
        "request = (\n"
        "    f'CONNECT {test_host}:{test_port} HTTP/1.1\\r\\n'\n"
        "    f'Host: {test_host}:{test_port}\\r\\n'\n"
        "    'Proxy-Connection: close\\r\\n\\r\\n'\n"
        ")\n"
        "sock.sendall(request.encode('ascii'))\n"
        "response = sock.recv(256).decode('iso-8859-1', errors='replace')\n"
        "sock.close()\n"
        "print(response.splitlines()[0] if response.splitlines() else '')\n"
    )
    return "python3 -c " + shlex.quote(code)


def _run_remote_probe(args: argparse.Namespace) -> tuple[bool, str]:
    command = [*_ssh_base_command(args), args.ssh_destination, _probe_command(args)]
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, float(args.probe_timeout_sec) + 5.0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "probe_timeout"
    except OSError:
        return False, "probe_launch_failed"
    output = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    if proc.returncode == 0 and " 200 " in f" {output} ":
        return True, "http_connect_ready"
    if " 407 " in f" {output} ":
        return False, "proxy_auth_required"
    if proc.returncode != 0:
        return False, "probe_exit_nonzero"
    return False, "proxy_connect_rejected"


def _start_tunnel_process(
    args: argparse.Namespace,
    *,
    json_local_socket: Path | None = None,
) -> subprocess.Popen[Any]:
    return subprocess.Popen(
        _tunnel_command(args, json_local_socket=json_local_socket),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _wait_for_tunnel_ready(
    args: argparse.Namespace,
    tunnel_proc: subprocess.Popen[Any],
    *,
    timeout_sec: float,
    remote_proc: subprocess.Popen[Any] | None = None,
    run_deadline: float | None = None,
) -> tuple[bool, str, int]:
    deadline = time.monotonic() + max(1.0, float(timeout_sec))
    status = "not_started"
    attempts = 0
    while time.monotonic() < deadline:
        if remote_proc is not None and remote_proc.poll() is not None:
            return False, "remote_command_completed", attempts
        if run_deadline is not None and time.monotonic() >= run_deadline:
            return False, "run_deadline_exceeded", attempts
        if tunnel_proc.poll() is not None:
            return False, "tunnel_process_exited", attempts
        ready, status = _run_remote_probe(args)
        attempts += 1
        if ready:
            return True, status, attempts
        time.sleep(max(0.1, float(args.probe_interval_sec)))
    return False, status, attempts


def _tunnel_liveness_public_contract(args: argparse.Namespace) -> dict[str, Any]:
    interval_sec = max(0.0, float(args.tunnel_health_interval_sec))
    enabled = bool(interval_sec > 0 and args.remote_command)
    return {
        "schema_version": "skillsbench_reverse_tunnel_liveness_v0",
        "enabled": enabled,
        "state": "not_started" if enabled else "disabled",
        "health_interval_sec": interval_sec,
        "failure_threshold": max(1, int(args.tunnel_health_failure_threshold)),
        "reconnect_attempt_limit": max(0, int(args.tunnel_reconnect_attempts)),
        "health_probe_attempt_count": 0,
        "health_probe_success_count": 0,
        "health_probe_failure_count": 0,
        "max_consecutive_failure_count": 0,
        "reconnect_attempt_count": 0,
        "reconnect_success_count": 0,
        "reconnect_failure_count": 0,
        "last_probe_status": "not_started",
        "raw_probe_output_recorded": False,
    }


def _stop_process_group(proc: subprocess.Popen[Any], *, grace_sec: float = 5.0) -> str:
    if proc.poll() is not None:
        return "already_exited"
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return "already_exited"
    except OSError:
        try:
            proc.terminate()
        except OSError:
            pass
    deadline = time.monotonic() + max(0.0, grace_sec)
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        return "killed"
    return "terminated"


def _write_private_log(
    path: str | None,
    *,
    stdout_text: str,
    stderr_text: str,
) -> bool:
    if not path:
        return False
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (f"# stdout\n{stdout_text}\n# stderr\n{stderr_text}\n"),
        encoding="utf-8",
    )
    return True


def _public_artifact_sync_requested(args: argparse.Namespace) -> bool:
    return bool(
        args.remote_public_artifact_root
        or args.remote_public_artifact_glob
        or args.local_public_artifact_dir
    )


def _public_artifact_sync_contract(args: argparse.Namespace) -> dict[str, Any]:
    return build_remote_benchmark_closeout_contract(
        requested=_public_artifact_sync_requested(args),
        ledger_requested=bool(args.local_run_ledger_path),
        aggregate_requested=bool(args.local_current_aggregate_path),
        ledger_catchup_requested=bool(args.local_ledger_catchup_root),
    )


def _sync_remote_public_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    return closeout_remote_benchmark_batch(
        run_remote_command=lambda command, timeout: _run_remote_shell_command(
            args,
            command,
            timeout_sec=timeout,
        ),
        remote_root=args.remote_public_artifact_root,
        artifact_globs=list(args.remote_public_artifact_glob or []),
        local_public_artifact_dir=args.local_public_artifact_dir,
        adapter_kind=args.public_artifact_adapter_kind,
        max_bytes=args.public_artifact_max_bytes,
        sync_timeout_sec=args.public_artifact_sync_timeout_sec,
        ledger_path=args.local_run_ledger_path,
        run_group_id=args.local_run_group_id,
        aggregate_path=args.local_current_aggregate_path,
        canonical_case_ids_file=args.local_canonical_case_ids_file,
        benchmark_id=args.local_benchmark_id,
        target_lane_id=args.local_target_lane_id,
        target_run_group_contains=list(args.local_target_run_group_contains or []),
        target_backfill_run_group_contains=list(
            args.local_target_backfill_run_group_contains or []
        ),
        ledger_catchup_root=args.local_ledger_catchup_root,
        ledger_catchup_run_group_contains=list(
            args.local_ledger_catchup_run_group_contains or []
        ),
        repo_root=REPO_ROOT,
    )


def _size_bucket(value: str) -> str:
    size = len(value.encode("utf-8", errors="replace"))
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 1000:
        return "200_999"
    if size < 5000:
        return "1000_4999"
    return "5000_plus"


def _remote_failure_cleanup_public_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "requested": bool(args.remote_failure_cleanup_pattern),
        "attempted": False,
        "trigger": "not_run",
        "include_docker": bool(args.remote_failure_cleanup_include_docker),
        "raw_pattern_recorded": False,
        "raw_output_recorded": False,
    }


def _remote_failure_cleanup_command(args: argparse.Namespace) -> str:
    code = r"""
import json
import os
import signal
import subprocess
import sys
import time

pattern = sys.argv[1]
include_docker = sys.argv[2] == "1"
self_pid = os.getpid()
self_pgid = os.getpgrp()
parent_pid = os.getppid()
ancestors = {parent_pid}
cursor = parent_pid
while cursor > 1:
    try:
        with open(f"/proc/{cursor}/stat", "r", encoding="utf-8", errors="replace") as handle:
            parts = handle.read().split()
        cursor = int(parts[3])
    except Exception:
        break
    ancestors.add(cursor)


def matching_pids():
    matches = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == self_pid or pid in ancestors:
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                raw = handle.read()
        except OSError:
            continue
        command = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        if pattern not in command:
            continue
        try:
            if os.getpgid(pid) == self_pgid:
                continue
        except OSError:
            pass
        matches.append(pid)
    return sorted(set(matches))


term_targets = matching_pids()
term_sent = 0
for pid in term_targets:
    try:
        os.kill(pid, signal.SIGTERM)
        term_sent += 1
    except OSError:
        pass

time.sleep(1.0)
kill_targets = matching_pids()
kill_sent = 0
for pid in kill_targets:
    try:
        os.kill(pid, signal.SIGKILL)
        kill_sent += 1
    except OSError:
        pass

alive_after = matching_pids()
docker_status = "not_requested"
docker_matched = 0
docker_removed = 0
if include_docker:
    docker_status = "ok"
    try:
        ps = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
        names = [
            line.strip()
            for line in (ps.stdout or "").splitlines()
            if line.strip() and pattern in line.strip()
        ]
        docker_matched = len(names)
        for name in names:
            rm = subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
                check=False,
            )
            if rm.returncode == 0:
                docker_removed += 1
    except FileNotFoundError:
        docker_status = "docker_unavailable"
    except Exception:
        docker_status = "docker_cleanup_failed"

print(json.dumps({
    "matched_count": len(term_targets),
    "term_sent_count": term_sent,
    "kill_sent_count": kill_sent,
    "alive_after_count": len(alive_after),
    "docker_status": docker_status,
    "docker_matched_count": docker_matched,
    "docker_removed_count": docker_removed,
}, sort_keys=True))
"""
    include_docker = "1" if args.remote_failure_cleanup_include_docker else "0"
    return (
        "# LOOPX_REMOTE_FAILURE_CLEANUP\n"
        + "python3 - "
        + shlex.quote(args.remote_failure_cleanup_pattern)
        + " "
        + include_docker
        + " <<'PY'\n"
        + code.strip()
        + "\nPY"
    )


def _run_remote_failure_cleanup(
    args: argparse.Namespace,
    *,
    trigger: str,
) -> dict[str, Any]:
    payload = _remote_failure_cleanup_public_contract(args)
    payload["trigger"] = trigger
    if not args.remote_failure_cleanup_pattern:
        return payload
    payload["attempted"] = True
    try:
        proc = _run_remote_shell_command(
            args,
            _remote_failure_cleanup_command(args),
            timeout_sec=args.remote_failure_cleanup_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        payload["first_blocker"] = "remote_failure_cleanup_timeout"
        return payload
    except OSError:
        payload["first_blocker"] = "remote_failure_cleanup_launch_failed"
        return payload

    stdout_text = proc.stdout or ""
    stderr_text = proc.stderr or ""
    payload["exit_code"] = proc.returncode
    payload["stdout_size_bucket"] = _size_bucket(stdout_text)
    payload["stderr_size_bucket"] = _size_bucket(stderr_text)
    if proc.returncode != 0:
        payload["first_blocker"] = "remote_failure_cleanup_exit_nonzero"
        return payload
    try:
        parsed = json.loads(stdout_text.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload["first_blocker"] = "remote_failure_cleanup_result_missing"
        return payload
    if not isinstance(parsed, dict):
        payload["first_blocker"] = "remote_failure_cleanup_result_invalid"
        return payload
    for key in (
        "matched_count",
        "term_sent_count",
        "kill_sent_count",
        "alive_after_count",
        "docker_matched_count",
        "docker_removed_count",
    ):
        try:
            payload[key] = int(parsed.get(key, 0))
        except (TypeError, ValueError):
            payload[key] = 0
    payload["docker_status"] = str(parsed.get("docker_status", "unknown"))[:80]
    return payload


def run_supervisor(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started_at = time.time()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "tunnel_started": False,
        "tunnel_ready": False,
        "probe_attempt_count": 0,
        "probe_status": "not_started",
        "remote_command_requested": bool(args.remote_command),
        "raw_ssh_destination_recorded": False,
        "raw_remote_command_recorded": False,
        "raw_probe_output_recorded": False,
        "raw_remote_output_recorded": False,
        "private_log_written": False,
        "remote_forward": _forward_public_contract(args.remote_forward),
        "json_bridge": _json_bridge_public_contract(args),
        "remote_failure_cleanup": _remote_failure_cleanup_public_contract(args),
        "public_artifact_sync": _public_artifact_sync_contract(args),
        "tunnel_liveness": _tunnel_liveness_public_contract(args),
    }

    tunnel_proc: subprocess.Popen[Any] | None = None
    json_bridge_proc: subprocess.Popen[Any] | None = None
    runtime_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    json_local_socket: Path | None = None

    def finish(returncode: int) -> tuple[int, dict[str, Any]]:
        payload["duration_sec"] = round(max(0.0, time.time() - started_at), 3)
        if tunnel_proc is not None:
            payload["tunnel_cleanup_status"] = _stop_process_group(
                tunnel_proc,
                grace_sec=1.0,
            )
            if tunnel_proc.returncode is not None:
                payload["tunnel_exit_code"] = tunnel_proc.returncode
        if json_bridge_proc is not None:
            payload["json_bridge"]["server_cleanup_status"] = _stop_process_group(
                json_bridge_proc,
                grace_sec=1.0,
            )
            if json_bridge_proc.returncode is not None:
                payload["json_bridge"]["server_exit_code"] = json_bridge_proc.returncode
        if runtime_dir_obj is not None:
            runtime_dir_obj.cleanup()
        return returncode, payload

    try:
        payload["stale_forward_cleanup"] = _cleanup_stale_local_forward(args)
        runtime_dir_obj = tempfile.TemporaryDirectory(
            prefix="loopx-rt-",
            dir="/tmp",
        )
        runtime_dir = Path(runtime_dir_obj.name)
        if _json_bridge_requested(args):
            json_bridge_payload = payload["json_bridge"]
            json_local_socket = _resolved_json_local_socket(args, runtime_dir)
            try:
                json_bridge_proc = _start_json_bridge_server(
                    args,
                    socket_path=json_local_socket,
                )
                json_bridge_payload["server_started"] = True
            except OSError as exc:
                payload["first_blocker"] = "json_bridge_server_launch_failed"
                json_bridge_payload["server_error_type"] = type(exc).__name__[:80]
                return finish(2)

            if not _probe_local_json_socket(args, json_local_socket):
                payload["first_blocker"] = "json_bridge_local_socket_not_ready"
                return finish(2)
            if json_bridge_proc.poll() is not None:
                payload["first_blocker"] = "json_bridge_server_exited_before_ready"
                json_bridge_payload["server_exit_code"] = json_bridge_proc.returncode
                return finish(2)
            json_bridge_payload["local_socket_ready"] = True
            json_bridge_payload["remote_socket_cleanup"] = _cleanup_remote_json_socket(
                args
            )
            if not json_bridge_payload["remote_socket_cleanup"].get("ok"):
                payload["first_blocker"] = json_bridge_payload[
                    "remote_socket_cleanup"
                ].get(
                    "first_blocker",
                    "json_bridge_remote_socket_cleanup_failed",
                )
                return finish(2)

        tunnel_proc = _start_tunnel_process(
            args,
            json_local_socket=json_local_socket,
        )
        payload["tunnel_started"] = True
    except OSError as exc:
        payload["first_blocker"] = "reverse_tunnel_launch_failed"
        payload["tunnel_error_type"] = type(exc).__name__[:80]
        return finish(2)

    ready, status, probe_attempts = _wait_for_tunnel_ready(
        args,
        tunnel_proc,
        timeout_sec=args.tunnel_ready_timeout_sec,
    )
    payload["probe_attempt_count"] = probe_attempts
    payload["probe_status"] = status
    payload["tunnel_ready"] = ready
    if status == "tunnel_process_exited":
        payload["first_blocker"] = "reverse_tunnel_process_exited_before_ready"
        payload["tunnel_exit_code"] = tunnel_proc.returncode
        return finish(2)

    if payload["tunnel_ready"] is not True:
        payload["first_blocker"] = "reverse_tunnel_probe_not_ready"
        return finish(2)

    if _json_bridge_requested(args):
        json_bridge_payload = payload["json_bridge"]
        if not _probe_remote_json_socket(args):
            payload["first_blocker"] = "json_bridge_remote_socket_not_ready"
            return finish(2)
        json_bridge_payload["remote_socket_ready"] = True
        assert runtime_dir_obj is not None
        if not _materialize_remote_json_client(args, Path(runtime_dir_obj.name)):
            payload["first_blocker"] = "json_bridge_remote_client_materialize_failed"
            return finish(2)
        json_bridge_payload["remote_client_materialized"] = True
        json_bridge_payload["remote_command_placeholder_supported"] = (
            "{json_bridge_client}" in args.remote_command
        )

    if args.preflight_only or not args.remote_command:
        payload["ok"] = True
        return finish(0)

    command = [
        *_ssh_base_command(args),
        args.ssh_destination,
        _remote_command_with_bridge_env(args),
    ]
    assert runtime_dir_obj is not None
    runtime_dir = Path(runtime_dir_obj.name)
    stdout_path = runtime_dir / "remote-command.stdout"
    stderr_path = runtime_dir / "remote-command.stderr"
    remote_proc: subprocess.Popen[Any] | None = None
    remote_command_timed_out = False
    tunnel_liveness_failed = False
    liveness = payload["tunnel_liveness"]
    try:
        with (
            stdout_path.open("w", encoding="utf-8") as stdout_handle,
            stderr_path.open("w", encoding="utf-8") as stderr_handle,
        ):
            remote_proc = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                start_new_session=True,
            )
            run_deadline = time.monotonic() + max(1.0, float(args.run_timeout_sec))
            health_interval = max(0.0, float(args.tunnel_health_interval_sec))
            next_health_probe = time.monotonic() + health_interval
            consecutive_failures = 0
            if liveness["enabled"]:
                liveness["state"] = "healthy"

            while remote_proc.poll() is None:
                now = time.monotonic()
                if now >= run_deadline:
                    remote_command_timed_out = True
                    _stop_process_group(remote_proc, grace_sec=1.0)
                    break
                if not liveness["enabled"] or now < next_health_probe:
                    time.sleep(0.1)
                    continue

                if tunnel_proc.poll() is not None:
                    health_ready = False
                    health_status = "tunnel_process_exited"
                else:
                    health_ready, health_status = _run_remote_probe(args)
                    payload["probe_attempt_count"] = (
                        int(payload["probe_attempt_count"]) + 1
                    )
                liveness["health_probe_attempt_count"] = (
                    int(liveness["health_probe_attempt_count"]) + 1
                )
                liveness["last_probe_status"] = health_status
                if health_ready:
                    liveness["health_probe_success_count"] = (
                        int(liveness["health_probe_success_count"]) + 1
                    )
                    consecutive_failures = 0
                    if liveness["state"] != "reconnected":
                        liveness["state"] = "healthy"
                    next_health_probe = time.monotonic() + health_interval
                    continue

                liveness["health_probe_failure_count"] = (
                    int(liveness["health_probe_failure_count"]) + 1
                )
                consecutive_failures += 1
                if health_status == "tunnel_process_exited":
                    consecutive_failures = max(
                        consecutive_failures,
                        int(liveness["failure_threshold"]),
                    )
                liveness["max_consecutive_failure_count"] = max(
                    int(liveness["max_consecutive_failure_count"]),
                    consecutive_failures,
                )
                if consecutive_failures < int(liveness["failure_threshold"]):
                    liveness["state"] = "degraded"
                    next_health_probe = time.monotonic() + health_interval
                    continue

                if tunnel_proc.poll() is None:
                    liveness["state"] = "failed"
                    liveness["last_probe_status"] = (
                        "new_connect_admission_failed_tunnel_preserved"
                    )
                    tunnel_liveness_failed = True
                    _stop_process_group(remote_proc, grace_sec=1.0)
                    break

                recovered = False
                for _attempt in range(int(liveness["reconnect_attempt_limit"])):
                    liveness["reconnect_attempt_count"] = (
                        int(liveness["reconnect_attempt_count"]) + 1
                    )
                    try:
                        tunnel_proc = _start_tunnel_process(
                            args,
                            json_local_socket=json_local_socket,
                        )
                    except OSError as exc:
                        liveness["last_probe_status"] = (
                            f"reconnect_launch_failed_{type(exc).__name__[:40]}"
                        )
                        liveness["reconnect_failure_count"] = (
                            int(liveness["reconnect_failure_count"]) + 1
                        )
                        continue
                    reconnect_ready, reconnect_status, reconnect_probes = (
                        _wait_for_tunnel_ready(
                            args,
                            tunnel_proc,
                            timeout_sec=args.tunnel_reconnect_ready_timeout_sec,
                            remote_proc=remote_proc,
                            run_deadline=run_deadline,
                        )
                    )
                    payload["probe_attempt_count"] = (
                        int(payload["probe_attempt_count"]) + reconnect_probes
                    )
                    liveness["last_probe_status"] = reconnect_status
                    if reconnect_status == "remote_command_completed":
                        recovered = True
                        break
                    if reconnect_status == "run_deadline_exceeded":
                        remote_command_timed_out = True
                        _stop_process_group(remote_proc, grace_sec=1.0)
                        break
                    if reconnect_ready:
                        liveness["reconnect_success_count"] = (
                            int(liveness["reconnect_success_count"]) + 1
                        )
                        liveness["state"] = "reconnected"
                        consecutive_failures = 0
                        recovered = True
                        break
                    liveness["reconnect_failure_count"] = (
                        int(liveness["reconnect_failure_count"]) + 1
                    )
                if remote_command_timed_out:
                    break
                if not recovered:
                    liveness["state"] = "failed"
                    tunnel_liveness_failed = True
                    _stop_process_group(remote_proc, grace_sec=1.0)
                    break
                next_health_probe = time.monotonic() + health_interval

            remote_proc.wait(timeout=2.0)

        stdout_text = stdout_path.read_text(encoding="utf-8")
        stderr_text = stderr_path.read_text(encoding="utf-8")
        payload["remote_command_exit_code"] = remote_proc.returncode
        payload["remote_stdout_size_bucket"] = _size_bucket(stdout_text)
        payload["remote_stderr_size_bucket"] = _size_bucket(stderr_text)
        payload["private_log_written"] = _write_private_log(
            args.private_log_path,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        if remote_command_timed_out:
            payload["remote_command_timeout"] = True
            payload["first_blocker"] = "remote_command_timeout"
            payload["remote_failure_cleanup"] = _run_remote_failure_cleanup(
                args,
                trigger="remote_command_timeout",
            )
            return finish(124)
        if tunnel_liveness_failed:
            payload["tunnel_ready"] = False
            payload["first_blocker"] = "reverse_tunnel_liveness_unrecoverable"
            payload["remote_failure_cleanup"] = _run_remote_failure_cleanup(
                args,
                trigger="reverse_tunnel_liveness_unrecoverable",
            )
            return finish(75)
        payload["public_artifact_sync"] = _sync_remote_public_artifacts(args)
        sync_ok = (
            not _public_artifact_sync_requested(args)
            or payload["public_artifact_sync"].get("ok") is True
        )
        payload["ok"] = remote_proc.returncode == 0 and sync_ok
        if remote_proc.returncode != 0:
            payload["first_blocker"] = "remote_command_exit_nonzero"
            payload["remote_failure_cleanup"] = _run_remote_failure_cleanup(
                args,
                trigger="remote_command_exit_nonzero",
            )
        elif not sync_ok:
            payload["first_blocker"] = str(
                payload["public_artifact_sync"].get("first_blocker")
                or "public_artifact_sync_failed"
            )
        return finish(
            0
            if remote_proc.returncode == 0 and sync_ok
            else remote_proc.returncode or 3
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if remote_proc is not None:
            _stop_process_group(remote_proc, grace_sec=1.0)
        payload["first_blocker"] = "remote_command_monitor_failed"
        payload["remote_command_monitor_error_type"] = type(exc).__name__[:80]
        payload["remote_failure_cleanup"] = _run_remote_failure_cleanup(
            args,
            trigger="remote_command_monitor_failed",
        )
        return finish(3)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-bin", default="ssh")
    parser.add_argument("--ssh-destination", required=True)
    parser.add_argument(
        "--ssh-option",
        action="append",
        default=[],
        help="Additional -o option for every ssh invocation, e.g. ConnectTimeout=10.",
    )
    parser.add_argument("--server-alive-interval-sec", type=int, default=30)
    parser.add_argument("--server-alive-count-max", type=int, default=3)
    parser.add_argument("--remote-forward", default=DEFAULT_REMOTE_FORWARD)
    parser.add_argument("--test-host", default=DEFAULT_TEST_HOST)
    parser.add_argument("--test-port", type=int, default=DEFAULT_TEST_PORT)
    parser.add_argument("--probe-timeout-sec", type=float, default=8.0)
    parser.add_argument("--probe-interval-sec", type=float, default=1.0)
    parser.add_argument("--tunnel-ready-timeout-sec", type=float, default=30.0)
    parser.add_argument("--keepalive-interval-sec", type=int, default=20)
    parser.add_argument(
        "--tunnel-health-interval-sec",
        type=float,
        default=30.0,
        help=(
            "Interval for CONNECT probes while the remote command is running; "
            "set to 0 to disable ongoing liveness checks."
        ),
    )
    parser.add_argument(
        "--tunnel-health-failure-threshold",
        type=int,
        default=2,
        help="Consecutive failed health probes before bounded tunnel reconnect.",
    )
    parser.add_argument(
        "--tunnel-reconnect-attempts",
        type=int,
        default=2,
        help="Maximum tunnel restart attempts after sustained liveness failure.",
    )
    parser.add_argument(
        "--tunnel-reconnect-ready-timeout-sec",
        type=float,
        default=30.0,
        help="Readiness budget for each restarted tunnel.",
    )
    parser.add_argument("--run-timeout-sec", type=float, default=7200.0)
    parser.add_argument(
        "--remote-failure-cleanup-pattern",
        default="",
        help=(
            "Private remote process/container name substring to clean up after "
            "a nonzero or timed-out remote command. Public output records "
            "counts only, never the pattern."
        ),
    )
    parser.add_argument(
        "--remote-failure-cleanup-include-docker",
        action="store_true",
        help=(
            "Also remove running Docker containers whose names contain the "
            "private cleanup pattern. Public output records counts only."
        ),
    )
    parser.add_argument(
        "--remote-failure-cleanup-timeout-sec",
        type=float,
        default=60.0,
        help="Timeout for the private remote failure cleanup command.",
    )
    parser.add_argument(
        "--cleanup-stale-local-forward",
        action="store_true",
        help=(
            "Before launching, terminate matching local ssh -R processes for "
            "the same destination and remote-forward. Public output records "
            "counts only."
        ),
    )
    parser.add_argument(
        "--json-bridge",
        action="store_true",
        help=(
            "Hold a per-run JSON reverse-channel bridge alongside the TCP "
            "reverse tunnel."
        ),
    )
    parser.add_argument(
        "--json-bridge-command",
        default="",
        help=(
            "Private local command executed by the JSON bridge server for "
            "sandbox command/file requests. Not written to public output."
        ),
    )
    parser.add_argument(
        "--json-local-socket",
        default="",
        help=(
            "Optional local Unix socket path for the JSON bridge server. "
            "Omit to use a per-run temporary socket."
        ),
    )
    parser.add_argument(
        "--json-remote-socket",
        default="",
        help=(
            "Remote Unix socket path exposed through ssh -R for the JSON "
            "bridge. The raw path is not written to public output."
        ),
    )
    parser.add_argument(
        "--json-remote-client-path",
        default="",
        help=(
            "Remote path where the JSON bridge client script is materialized. "
            "Use {json_bridge_client} inside --remote-command to inject it."
        ),
    )
    parser.add_argument("--json-server-timeout-sec", type=float, default=7200.0)
    parser.add_argument("--json-socket-ready-timeout-sec", type=float, default=15.0)
    parser.add_argument("--remote-setup-timeout-sec", type=float, default=30.0)
    parser.add_argument(
        "--json-bridge-probe-policy",
        choices=("sandbox-env-deferred", "socket-only"),
        default="sandbox-env-deferred",
        help=(
            "Pre-case readiness policy. sandbox-env-deferred avoids probing "
            "AI_ADDR/AI_PORT before the BenchFlow task sandbox exists; socket-only "
            "checks only the local/remote bridge socket and client lifecycle."
        ),
    )
    parser.add_argument("--remote-command", default="")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--remote-public-artifact-root",
        default="",
        help=(
            "Private remote root for post-run compact/public artifact collection. "
            "The path is never written to public output."
        ),
    )
    parser.add_argument(
        "--remote-public-artifact-glob",
        action="append",
        default=[],
        help=(
            "Relative compact/public artifact glob below the private remote root. "
            "May be repeated; raw artifacts are rejected before transport."
        ),
    )
    parser.add_argument(
        "--local-public-artifact-dir",
        default="",
        help=(
            "Private local destination for synchronized compact/public artifacts. "
            "The path is never written to public output."
        ),
    )
    parser.add_argument(
        "--public-artifact-adapter-kind",
        default="skillsbench",
    )
    parser.add_argument(
        "--public-artifact-max-bytes",
        type=int,
        default=2 * 1024 * 1024,
    )
    parser.add_argument(
        "--public-artifact-sync-timeout-sec",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--local-run-ledger-path",
        default="",
        help=(
            "Optional private local ledger updated from synchronized compact runs. "
            "The path is never written to public output."
        ),
    )
    parser.add_argument("--local-run-group-id", default="")
    parser.add_argument(
        "--local-ledger-catchup-root",
        default="",
        help=(
            "Optional local public artifact root laid out as "
            "<run-group-id>/**/benchmark_run.compact.json. Missing terminal rows "
            "are upserted before aggregation; raw artifacts are never read."
        ),
    )
    parser.add_argument(
        "--local-ledger-catchup-run-group-contains",
        action="append",
        default=[],
        help=(
            "Optional substring filter for catch-up run-group directories. "
            "May be repeated."
        ),
    )
    parser.add_argument("--local-current-aggregate-path", default="")
    parser.add_argument("--local-canonical-case-ids-file", default="")
    parser.add_argument("--local-benchmark-id", default="skillsbench@1.1")
    parser.add_argument("--local-target-lane-id", default="")
    parser.add_argument(
        "--local-target-run-group-contains",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--local-target-backfill-run-group-contains",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--private-log-path",
        default=None,
        help="Optional private stdout/stderr capture for the remote command.",
    )
    parser.add_argument(
        "--public-output-path",
        default=None,
        help="Optional path for compact public-safe supervisor JSON.",
    )
    args = parser.parse_args(argv)
    if _json_bridge_requested(args):
        args.json_bridge = True
        missing = [
            name
            for name in (
                "json_bridge_command",
                "json_remote_socket",
                "json_remote_client_path",
            )
            if not getattr(args, name)
        ]
        if missing:
            parser.error(
                "--json-bridge requires "
                + ", ".join("--" + item.replace("_", "-") for item in missing)
            )
    if _public_artifact_sync_requested(args):
        missing = []
        if not args.remote_public_artifact_root:
            missing.append("--remote-public-artifact-root")
        if not args.remote_public_artifact_glob:
            missing.append("--remote-public-artifact-glob")
        if not args.local_public_artifact_dir:
            missing.append("--local-public-artifact-dir")
        if missing:
            parser.error("artifact sync requires " + ", ".join(missing))
        for pattern in args.remote_public_artifact_glob:
            parts = Path(pattern).parts
            if Path(pattern).is_absolute() or ".." in parts:
                parser.error(
                    "--remote-public-artifact-glob must be relative and bounded"
                )
    if args.local_run_ledger_path and not _public_artifact_sync_requested(args):
        parser.error("--local-run-ledger-path requires artifact sync")
    if args.local_ledger_catchup_root and not args.local_run_ledger_path:
        parser.error("--local-ledger-catchup-root requires --local-run-ledger-path")
    if args.local_current_aggregate_path:
        if not args.local_run_ledger_path or not args.local_canonical_case_ids_file:
            parser.error(
                "--local-current-aggregate-path requires --local-run-ledger-path "
                "and --local-canonical-case-ids-file"
            )
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rc, payload = run_supervisor(args)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.public_output_path:
        path = Path(args.public_output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
