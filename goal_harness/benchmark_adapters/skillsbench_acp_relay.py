from __future__ import annotations

import asyncio
import json
import os
import selectors
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


SKILLSBENCH_LOCAL_ACP_RELAY_SCHEMA_VERSION = "skillsbench_local_acp_relay_v0"
SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION = (
    "skillsbench_local_acp_relay_probe_v0"
)
SKILLSBENCH_HOST_LOCAL_ACP_TRANSPORT_PROBE_SCHEMA_VERSION = (
    "skillsbench_host_local_acp_transport_probe_v0"
)
SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER = (
    "GOAL_HARNESS_SKILLSBENCH_LOCAL_ACP_RELAY_READY"
)


def _json_rpc_result(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _json_rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message},
    }


def _text_blocks_to_prompt(prompt: Any) -> str:
    if not isinstance(prompt, list):
        return ""
    parts: list[str] = []
    for block in prompt:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _safe_cwd(value: Any, *, default: str) -> str:
    text = str(value or "").strip()
    return text or default


@dataclass(frozen=True)
class CodexExecConfig:
    codex_bin: str = "codex"
    sandbox: str = "workspace-write"
    model: str | None = None
    timeout_sec: int = 7200
    dry_run_response: str | None = None
    app_server_goal_worker: bool = False
    dataset: str = "skillsbench-v1.1"
    task_id: str = "llm-prefix-cache-replay"
    approval_policy: str = "never"
    response_timeout_sec: float = 30.0
    worker_script: str | None = None
    stream_heartbeat_interval_sec: float = 120.0
    reasoning_effort: str | None = "high"


class SkillsBenchLocalAcpRelay:
    """Minimal ACP stdio server for the SkillsBench local-driver route.

    The relay is intentionally a local ACP adapter, not a remote Codex runtime.
    In dry-run mode it proves the BenchFlow JSON-RPC handshake without invoking
    Codex. In normal mode it delegates each prompt to the local Codex CLI and
    sends only the final assistant message back over ACP stdout.
    """

    def __init__(self, config: CodexExecConfig):
        self._config = config
        self._sessions: dict[str, dict[str, Any]] = {}

    def serve(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                continue
            response = self.handle_message(message, stdout=stdout)
            if response is not None:
                self._write(stdout, response)
        return 0

    def handle_message(
        self, message: dict[str, Any], *, stdout: TextIO
    ) -> dict[str, Any] | None:
        method = str(message.get("method") or "")
        message_id = message.get("id")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if "id" not in message:
            if method == "session/cancel":
                return None
            return None
        if method == "initialize":
            return _json_rpc_result(
                message_id,
                {
                    "protocolVersion": int(params.get("protocolVersion") or 0),
                    "agentCapabilities": {
                        "promptCapabilities": {
                            "image": False,
                            "audio": False,
                            "embeddedContext": False,
                        },
                        "mcpCapabilities": {"sse": False, "http": False},
                        "loadSession": True,
                    },
                    "agentInfo": {
                        "name": "goal-harness-skillsbench-local-acp-relay",
                        "version": SKILLSBENCH_LOCAL_ACP_RELAY_SCHEMA_VERSION,
                    },
                },
            )
        if method in {"session/new", "session/load"}:
            session_id = str(params.get("sessionId") or f"gh-sb-{uuid.uuid4().hex[:12]}")
            self._sessions[session_id] = {
                "cwd": _safe_cwd(params.get("cwd"), default=os.getcwd()),
                "model": None,
                "cancelled": False,
            }
            return _json_rpc_result(message_id, {"sessionId": session_id})
        if method == "session/set_model":
            session = self._sessions.get(str(params.get("sessionId") or ""))
            if session is None:
                return _json_rpc_error(message_id, -32001, "unknown session")
            session["model"] = str(params.get("modelId") or "")
            return _json_rpc_result(message_id, {})
        if method == "session/prompt":
            return self._handle_prompt(message_id, params, stdout=stdout)
        return _json_rpc_error(message_id, -32601, f"method not found: {method}")

    def _handle_prompt(
        self, message_id: Any, params: dict[str, Any], *, stdout: TextIO
    ) -> dict[str, Any]:
        session_id = str(params.get("sessionId") or "")
        session = self._sessions.get(session_id)
        if session is None:
            return _json_rpc_error(message_id, -32001, "unknown session")
        prompt_text = _text_blocks_to_prompt(params.get("prompt"))
        if not prompt_text:
            return _json_rpc_error(message_id, -32602, "prompt text missing")
        try:
            response_text = self._run_codex(
                prompt_text,
                session=session,
                session_id=session_id,
                stdout=stdout,
            )
        except TimeoutError:
            return _json_rpc_error(message_id, -32002, "local codex execution timeout")
        except RuntimeError as exc:
            return _json_rpc_error(message_id, -32003, str(exc))
        self._write(
            stdout,
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": response_text},
                    },
                },
            },
        )
        return _json_rpc_result(message_id, {"stopReason": "end_turn"})

    def _run_codex(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
    ) -> str:
        if self._config.dry_run_response is not None:
            return self._config.dry_run_response
        if self._config.app_server_goal_worker:
            return self._run_app_server_goal_worker(
                prompt_text,
                session=session,
                session_id=session_id,
                stdout=stdout,
            )
        cwd = _safe_cwd(session.get("cwd"), default=os.getcwd())
        with tempfile.TemporaryDirectory(prefix="gh-skillsbench-acp-") as tmp:
            output_path = Path(tmp) / "last-message.txt"
            cmd = [
                self._config.codex_bin,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                self._config.sandbox,
                "-C",
                cwd,
                "--output-last-message",
                str(output_path),
                "--json",
            ]
            model = self._config.model or session.get("model")
            if model:
                cmd.extend(["--model", str(model)])
            cmd.append(prompt_text)
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self._config.timeout_sec,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError from exc
            if proc.returncode != 0:
                raise RuntimeError("local codex execution failed")
            try:
                response = output_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RuntimeError("local codex final message missing") from exc
            return response or "local codex returned an empty final message"

    def _run_app_server_goal_worker(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
    ) -> str:
        cwd = _safe_cwd(session.get("cwd"), default=os.getcwd())
        with tempfile.TemporaryDirectory(prefix="gh-skillsbench-goal-worker-") as tmp:
            tmp_path = Path(tmp)
            prompt_path = tmp_path / "prompt.txt"
            output_json = tmp_path / "worker.compact.json"
            response_path = tmp_path / "response.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")
            worker_script = (
                Path(self._config.worker_script).expanduser()
                if self._config.worker_script
                else Path(__file__).resolve().parents[2]
                / "scripts"
                / "skillsbench_host_codex_goal_worker.py"
            )
            cmd = [
                sys.executable,
                str(worker_script),
                "--dataset",
                self._config.dataset,
                "--task-id",
                self._config.task_id,
                "--codex-bin",
                self._config.codex_bin,
                "--sandbox",
                self._config.sandbox,
                "--approval-policy",
                self._config.approval_policy,
                "--work-dir",
                cwd,
                "--prompt-file",
                str(prompt_path),
                "--output-json",
                str(output_json),
                "--response-text-file",
                str(response_path),
                "--response-timeout-sec",
                str(self._config.response_timeout_sec),
                "--turn-timeout-sec",
                str(self._config.timeout_sec),
                "--reasoning-effort",
                str(self._config.reasoning_effort or "high"),
                "--runner-integration-ready",
            ]
            model = self._config.model or session.get("model")
            if model:
                cmd.extend(["--model", str(model)])
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self._write_worker_heartbeat(
                    stdout,
                    session_id=session_id,
                    text="host app-server goal worker started",
                )
                deadline = time.monotonic() + self._config.timeout_sec + 60
                next_heartbeat = (
                    time.monotonic()
                    + max(1.0, self._config.stream_heartbeat_interval_sec)
                )
                while proc.poll() is None:
                    now = time.monotonic()
                    if now >= deadline:
                        proc.kill()
                        proc.communicate(timeout=2)
                        raise TimeoutError
                    if now >= next_heartbeat:
                        self._write_worker_heartbeat(
                            stdout,
                            session_id=session_id,
                            text="host app-server goal worker still running",
                        )
                        next_heartbeat = (
                            now + max(1.0, self._config.stream_heartbeat_interval_sec)
                        )
                    time.sleep(0.2)
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError from exc
            if proc.returncode != 0:
                raise RuntimeError("host app-server goal worker failed")
            try:
                response = response_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RuntimeError("host app-server goal worker response missing") from exc
            return response or "host app-server goal worker returned an empty final message"

    def _write_worker_heartbeat(
        self,
        stdout: TextIO,
        *,
        session_id: str,
        text: str,
    ) -> None:
        """Emit a public-safe ACP activity heartbeat while the host worker runs."""

        self._write(
            stdout,
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "agent_thought_chunk",
                        "content": {"type": "text", "text": text},
                    },
                },
            },
        )

    @staticmethod
    def _write(stdout: TextIO, message: dict[str, Any]) -> None:
        stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        stdout.flush()


def default_skillsbench_local_acp_relay_command() -> list[str]:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "skillsbench_local_acp_relay.py"
    )
    return [
        sys.executable,
        str(script),
        "--dry-run-response",
        SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER,
    ]


def run_skillsbench_local_acp_relay_probe(
    command: str | list[str] | tuple[str, ...] | None = None,
    *,
    timeout_sec: float = 10.0,
) -> dict[str, Any]:
    argv = (
        _command_to_argv(command)
        if command
        else default_skillsbench_local_acp_relay_command()
    )
    started = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
    stage = "spawn"
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stage = "initialize"
        initialize = _probe_request(
            proc,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            timeout_at=started + timeout_sec,
        )
        stage = "session_new"
        session = _probe_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/new",
                "params": {"cwd": os.getcwd(), "mcpServers": []},
            },
            timeout_at=started + timeout_sec,
        )
        session_id = str(session.get("result", {}).get("sessionId") or "")
        stage = "set_model"
        _probe_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "session/set_model",
                "params": {"sessionId": session_id, "modelId": "probe-model"},
            },
            timeout_at=started + timeout_sec,
        )
        stage = "prompt"
        prompt = _probe_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": "relay handshake probe"}],
                },
            },
            timeout_at=started + timeout_sec,
        )
        ready = (
            initialize.get("result", {}).get("agentInfo", {}).get("name")
            == "goal-harness-skillsbench-local-acp-relay"
            and bool(session_id)
            and prompt.get("result", {}).get("stopReason") == "end_turn"
        )
        return _relay_probe_payload(
            ready=ready,
            first_blocker=(
                "skillsbench_local_acp_relay_ready"
                if ready
                else "skillsbench_local_acp_relay_probe_failed"
            ),
            stage="complete",
            request_count=4,
        )
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError):
        return _relay_probe_payload(
            ready=False,
            first_blocker=f"skillsbench_local_acp_relay_{stage}_failed",
            stage=stage,
            request_count=0,
        )
    finally:
        if proc is not None:
            _terminate_probe_process(proc)


def run_skillsbench_host_local_acp_transport_probe(
    command: str | list[str] | tuple[str, ...] | None = None,
    *,
    skillsbench_root: str | Path | None = None,
    timeout_sec: float = 10.0,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Probe the real BenchFlow ACPClient against a host-local ACP relay.

    This proves the host-local stdio transport route without invoking Codex,
    reading task text, launching a task sandbox, or recording raw ACP traffic.
    """

    argv = (
        _command_to_argv(command)
        if command
        else default_skillsbench_local_acp_relay_command()
    )
    stage = {"value": "import"}
    try:
        _prepend_optional_skillsbench_site_packages(skillsbench_root)
        from benchflow.acp.client import ACPClient
        from benchflow.acp.transport import StdioTransport

        async def probe() -> dict[str, Any]:
            client = ACPClient(
                StdioTransport(
                    command=argv[0],
                    args=argv[1:],
                    cwd=str(cwd) if cwd is not None else None,
                )
            )

            async def step(name: str, awaitable: Any) -> Any:
                stage["value"] = name
                return await asyncio.wait_for(awaitable, timeout=timeout_sec)

            request_count = 0
            try:
                await step("connect", client.connect())
                initialize = await step("initialize", client.initialize())
                request_count += 1
                session = await step(
                    "session_new",
                    client.session_new(
                        cwd=str(cwd) if cwd is not None else os.getcwd()
                    ),
                )
                request_count += 1
                await step("set_model", client.set_model("probe-model"))
                request_count += 1
                prompt = await step("prompt", client.prompt("relay handshake probe"))
                request_count += 1
                agent_name = str(getattr(initialize.agent_info, "name", "") or "")
                session_id = str(getattr(session, "session_id", "") or "")
                stop_reason = str(getattr(prompt, "stop_reason", "") or "")
                ready = (
                    agent_name == "goal-harness-skillsbench-local-acp-relay"
                    and bool(session_id)
                    and stop_reason == "end_turn"
                )
                return _host_local_transport_probe_payload(
                    ready=ready,
                    first_blocker=(
                        "skillsbench_host_local_acp_transport_ready"
                        if ready
                        else "skillsbench_host_local_acp_transport_probe_failed"
                    ),
                    stage="complete",
                    request_count=request_count,
                    benchflow_acp_client_used=True,
                )
            finally:
                await client.close()

        return asyncio.run(probe())
    except Exception:
        return _host_local_transport_probe_payload(
            ready=False,
            first_blocker=(
                f"skillsbench_host_local_acp_transport_{stage['value']}_failed"
            ),
            stage=stage["value"],
            request_count=0,
            benchflow_acp_client_used=stage["value"] != "import",
        )


def _command_to_argv(command: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def _prepend_optional_skillsbench_site_packages(
    skillsbench_root: str | Path | None,
) -> None:
    if skillsbench_root is None:
        return
    root = Path(skillsbench_root).expanduser()
    venv = root / ".venv"
    if not venv.exists():
        return
    for candidate in sorted((venv / "lib").glob("python*/site-packages")):
        if candidate.exists():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
            return


def _probe_request(
    proc: subprocess.Popen[bytes],
    message: dict[str, Any],
    *,
    timeout_at: float,
) -> dict[str, Any]:
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("probe process pipes missing")
    proc.stdin.write((json.dumps(message) + "\n").encode())
    proc.stdin.flush()
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    pending = b""
    try:
        while True:
            remaining = timeout_at - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ACP relay probe timed out")
            events = selector.select(timeout=remaining)
            if not events:
                raise TimeoutError("ACP relay probe timed out")
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("ACP relay closed stdout")
            pending += chunk
            while b"\n" in pending:
                raw_line, pending = pending.split(b"\n", 1)
                if not raw_line.strip():
                    continue
                decoded = json.loads(raw_line.decode())
                if (
                    isinstance(decoded, dict)
                    and decoded.get("jsonrpc") == "2.0"
                    and decoded.get("id") == message.get("id")
                ):
                    if decoded.get("error"):
                        raise RuntimeError(
                            str(decoded["error"].get("message") or "error")
                        )
                    return decoded
    finally:
        selector.close()


def _terminate_probe_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.stdin:
        try:
            proc.stdin.close()
        except OSError:
            pass
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
            proc.wait(timeout=2)
        except OSError:
            pass


def _relay_probe_payload(
    *,
    ready: bool,
    first_blocker: str,
    stage: str,
    request_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION,
        "ready": ready,
        "first_blocker": first_blocker,
        "stage": stage,
        "request_count": request_count,
        "worker_protocol": "acp_stdio",
        "codex_cli_invoked": False,
        "raw_output_recorded": False,
        "raw_event_jsonl_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
    }


def _host_local_transport_probe_payload(
    *,
    ready: bool,
    first_blocker: str,
    stage: str,
    request_count: int,
    benchflow_acp_client_used: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SKILLSBENCH_HOST_LOCAL_ACP_TRANSPORT_PROBE_SCHEMA_VERSION,
        "ready": ready,
        "first_blocker": first_blocker,
        "stage": stage,
        "request_count": request_count,
        "benchflow_acp_client_used": benchflow_acp_client_used,
        "transport": "host_local_stdio",
        "container_transport_used": False,
        "codex_cli_invoked": False,
        "raw_output_recorded": False,
        "raw_event_jsonl_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
    }
