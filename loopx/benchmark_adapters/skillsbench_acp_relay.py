from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from loopx.benchmark_case_state import (
    BENCHMARK_CASE_LOOPX_AGENT_ID,
    BENCHMARK_CASE_LOOPX_CLI_PATH,
    BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
    BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    benchmark_case_goal_id,
    benchmark_case_loopx_command_prefix,
)
from loopx.benchmark_adapters.skillsbench_remote_bridge import (
    run_skillsbench_remote_command_file_bridge_probe,
)
from loopx.benchmark_adapters.skillsbench_turn_runtime import (
    SkillsBenchTurnAgentResult,
    run_skillsbench_loopx_turn_relay,
)
from loopx.benchmark_adapters.skillsbench_bridge_summary import (
    bridge_summary_has_inflight_operation as _bridge_summary_has_inflight_operation,
    bridge_summary_has_meaningful_agent_progress as _bridge_summary_has_meaningful_agent_progress,
    bridge_summary_has_successful_task_operation as _bridge_summary_has_successful_task_operation,
    bridge_summary_task_progress_receipt as _bridge_summary_task_progress_receipt,
    bridge_operation_record_interrupted as _bridge_operation_record_interrupted,
    prompt_requires_meaningful_bridge_progress as _prompt_requires_meaningful_bridge_progress,
)
from loopx.benchmark_adapters.skillsbench_bridge_guard import (
    LOOPX_COMMAND_INSTRUMENTATION_SOURCE,
    LOOPX_TODO_OUTPUT_INSTRUMENTATION_SOURCE,
)
from loopx.benchmark_adapters.skillsbench_acp_failure_policy import (
    RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES,
    RECOVERABLE_CODEX_TURN_FAILURE_PREFIX,
    recoverable_codex_turn_failure_message as _recoverable_codex_turn_failure_message,
)
from loopx.benchmark_adapters.skillsbench_acp_process import (
    write_process_stdin_async as _write_process_stdin_async,
)
from loopx.benchmark_adapters.skillsbench_codex_goal_recovery import (
    CODEX_CLI_GOAL_POST_BRIDGE_CONTINUE_PROMPT,
    POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
    PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
    codex_cli_tui_post_bridge_blocker_stage,
    codex_cli_tui_post_bridge_recovery_action,
    codex_cli_tui_post_bridge_recovery_skip_reason,
    codex_cli_tui_pre_bridge_blocker_stage,
    codex_cli_tui_pre_bridge_recovery_action,
    codex_cli_tui_pre_bridge_recovery_skip_reason,
    codex_cli_tui_pre_bridge_terminal_stage,
    codex_cli_tui_pre_bridge_terminal_skip_reason,
    write_private_codex_cli_goal_tui_tail,
)
from loopx.codex_cli_goal_tui import (
    CODEX_CLI_GOAL_KICKOFF_PROMPT,
    CODEX_CLI_GOAL_TASK_PROMPT_FILENAME,
    build_codex_cli_goal_file_objective,
    build_codex_cli_goal_tui_input,
    build_codex_cli_tui_command,
    CodexCliGoalLifecycleGeneration,
    codex_cli_goal_watchdog_expired,
    codex_cli_goal_reset_pre_bridge_deadlines,
    codex_cli_goal_should_ignore_stale_terminal,
    codex_cli_goal_should_submit_kickoff,
    codex_cli_tui_environment,
    codex_cli_tui_shell_command,
    codex_cli_tui_input_prompt_visible,
    codex_cli_tui_retryable_startup_blocker_stage,
    codex_cli_tui_turn_active,
    resolve_codex_cli_binary,
    start_codex_cli_goal_tui_session,
    tmux_capture,
    tmux_kill_session,
    tmux_paste_file_and_submit,
    tmux_submit_enter,
    tmux_type_text_and_submit,
)
from loopx.control_plane.turn_driver import codex_cli_session_id_from_jsonl

SAFE_LOOPX_TODO_ID_RE = re.compile(r"^todo_[A-Za-z0-9_-]{6,80}$")
SAFE_LOOPX_GOAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}$")
CODEX_EXEC_TRANSPORT_RETRY_LIMIT = 1
CODEX_EXEC_SESSION_ROLLOVER_LIMIT = 1


def _loopx_turn_local_session_root(
    worker_public_trace_dir: str | None,
    session_id: str,
) -> Path | None:
    if not worker_public_trace_dir:
        return None
    session_digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    return (
        Path(worker_public_trace_dir).parent
        / ".loopx-turn-codex-sessions"
        / session_digest
    )


def _safe_loopx_todo_id(value: object) -> str:
    text = str(value or "")
    return text if SAFE_LOOPX_TODO_ID_RE.match(text) else ""


def _safe_loopx_goal_id(value: object) -> str:
    text = str(value or "")
    return text if SAFE_LOOPX_GOAL_ID_RE.match(text) else ""


REPO_ROOT = Path(__file__).resolve().parents[2]
REVERSE_CHANNEL_BRIDGE_SCRIPT = (
    REPO_ROOT / "scripts" / "skillsbench_reverse_channel_bridge.py"
)
SKILLSBENCH_LOCAL_ACP_RELAY_SCHEMA_VERSION = "skillsbench_local_acp_relay_v0"
SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION = (
    "skillsbench_local_acp_relay_probe_v0"
)
SKILLSBENCH_HOST_LOCAL_ACP_TRANSPORT_PROBE_SCHEMA_VERSION = (
    "skillsbench_host_local_acp_transport_probe_v0"
)
SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER = "LOOPX_SKILLSBENCH_LOCAL_ACP_RELAY_READY"
SKILLSBENCH_LOCAL_ACP_RELAY_HEALTH_PROMPT = (
    "LoopX relay health check. Reply exactly "
    f"{SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER} and end the turn."
)
SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER = "LOOPX_SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_READY"
SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_PROMPT = (
    "LoopX bridge action preflight. First use the private bridge command from "
    "the relay packet to run one JSON preflight request that does not require "
    "scored sandbox target environment variables. Do not plan, explain, inspect "
    "files, or reply before that bridge request returns. Your first tool action "
    "should be a shell "
    "pipeline that sends the JSON request to the private bridge command shown "
    "in the packet, for example: "
    "`printf '%s\\n' '{\"operation\":\"preflight\"}' | <private bridge command>`. "
    "After the bridge response returns, reply exactly "
    f"{SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER} and end the turn."
)
CODEX_CLI_GOAL_THREAD_PREWARM_TIMEOUT_SEC = 120
SKILLSBENCH_OUTPUT_PATH_CONTRACT = (
    "- Honor every task input and output path exactly as explicit task "
    "instructions or visible task metadata declare it. Keep absolute paths "
    "unchanged. Resolve a relative path from the directory containing the "
    "metadata file that declares it, or otherwise from the sandbox task "
    "working directory. Do not force relative paths into `/root` or `/app` "
    "merely because those roots are available."
)


@contextlib.contextmanager
def _temporary_directory_ignore_cleanup_errors(*, prefix: str):
    path = tempfile.mkdtemp(prefix=prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

def _prompt_requires_bridge_first_action(prompt: str) -> bool:
    text = prompt or ""
    if "Private bridge command:" not in text:
        return False
    lowered = text.lower()
    required_markers = (
        SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER.lower(),
        "mandatory product-mode solver checkpoint",
        "mandatory product-mode closeout checkpoint",
        "must start with either a task-facing sandbox bridge operation",
        "first action required",
        "your first tool action should be a shell",
        "your first agent action must be a shell/tool call",
        "your first agent action must be a task-facing shell/tool call",
        "first run the case-local quota/todo commands",
        "first loopx cli action must invoke `start-goal",
        "this benchmark treatment executes the actual agent contract for `/loopx",
        "compact ranked",
        "selected runnable p0",
    )
    return any(marker in lowered for marker in required_markers)


def _is_bridge_action_preflight_prompt(prompt: str) -> bool:
    text = prompt or ""
    return (
        SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER in text
        and "LoopX bridge action preflight" in text
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


def _public_bridge_label(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("/", "_").replace("\\", "_")
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("._:-")
    return text[:limit]


def _public_bridge_label_list(value: Any, *, limit: int = 80) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value[:12]:
        label = _public_bridge_label(item, limit=limit)
        if label:
            labels.append(label)
    return labels


def _public_bridge_operations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    operations: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        operation: dict[str, Any] = {}
        for field in ("kind", "label", "status"):
            label = _public_bridge_label(item.get(field), limit=80)
            if label:
                operation[field] = label
        for field in ("exit_code_zero", "content_match"):
            flag = item.get(field)
            if isinstance(flag, bool):
                operation[field] = flag
        if operation:
            operations.append(operation)
    return operations


def _codex_exec_failure_category(
    *,
    returncode: int | None,
    stderr_text: str,
    stdout_text: str = "",
) -> str:
    text = "\n".join(
        value
        for value in (
            stderr_text or "",
            _codex_exec_jsonl_error_text(stdout_text),
        )
        if value
    ).lower()
    if any(
        token in text
        for token in (
            "not authenticated",
            "authentication",
            "unauthorized",
            "api key",
            "login required",
            "please login",
            "401",
        )
    ):
        return "codex_auth_or_login_required"
    if "model" in text and any(
        token in text
        for token in (
            "not found",
            "unknown",
            "unsupported",
            "invalid",
            "does not exist",
            "unavailable",
            "not supported",
        )
    ):
        return "codex_model_unavailable"
    if "codex/responses" in text and any(
        token in text
        for token in (
            "failed to connect to websocket",
            "stream disconnected before completion",
            "error sending request",
            "connection refused",
        )
    ):
        return "codex_responses_stream_unavailable"
    if any(
        token in text
        for token in (
            "failed to refresh available models",
            "stream disconnected before completion",
            "error sending request",
            "request error",
            "connection refused",
            "connection timed out",
        )
    ) and any(
        token in text
        for token in (
            "chatgpt.com",
            "api.openai.com",
            "backend-api",
            "available models",
        )
    ):
        return "codex_network_or_api_unreachable"
    if (
        "connectionrefusederror" in text
        or "connection refused" in text
        or "failed to establish a new connection" in text
        or ("create_connection" in text and "socket" in text)
    ):
        return "codex_reverse_channel_unavailable"
    if "hit your usage limit" in text or "usage limit" in text:
        return "codex_usage_limit"
    if "codex_exec_first_action_timeout" in text:
        return "codex_exec_first_action_timeout"
    if "codex_exec_task_output_quiet_timeout" in text:
        return "codex_exec_task_output_quiet_timeout"
    if "codex_exec_bridge_idle_timeout" in text:
        return "codex_exec_bridge_idle_timeout"
    if "unexpected argument" in text or "unrecognized option" in text:
        return "codex_cli_argument_incompatible"
    if any(
        token in text
        for token in (
            "command not found",
            "no such file or directory",
            "modulenotfounderror",
            "importerror",
            "failed to spawn",
        )
    ):
        return "codex_cli_or_environment_missing"
    if "api.openai.com" in text or "chatgpt.com" in text:
        if any(token in text for token in ("timed out", "timeout", "connection")):
            return "codex_network_or_api_unreachable"
    if returncode == 124:
        return "codex_exec_timeout"
    if returncode is not None and 0 < returncode <= 255:
        return f"codex_exec_exit_{returncode}"
    if returncode is not None:
        return "codex_exec_exit_nonzero"
    return "codex_exec_failed"


def _codex_exec_jsonl_error_text(stdout_text: str) -> str:
    """Extract only typed Codex error messages from private JSONL output."""

    messages: list[str] = []
    for line in (stdout_text or "").splitlines():
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "").strip().lower()
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type") or "").strip().lower()
        if event_type not in {"error", "turn.failed"} and item_type != "error":
            continue
        error = event.get("error")
        candidates = [event.get("message")]
        if isinstance(error, dict):
            candidates.append(error.get("message"))
        elif isinstance(error, str):
            candidates.append(error)
        if item_type == "error":
            candidates.extend((item.get("message"), item.get("text")))
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            message = candidate.strip()
            if message:
                messages.append(message[:4_000])
        if sum(len(message) for message in messages) >= 16_000:
            break
    return "\n".join(messages)[:16_000]


def _codex_exec_side_effect_free_recovery_allowed(
    *,
    category: str,
    bridge_summary_path: Path | None,
    final_message_present: bool,
    turn_deadline: float | None,
) -> bool:
    if (
        category not in RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES
        or final_message_present
        or bridge_summary_path is None
        or turn_deadline is not None
        and time.monotonic() >= turn_deadline
        or _bridge_summary_has_inflight_operation(bridge_summary_path)
        or _bridge_summary_has_meaningful_agent_progress(
            bridge_summary_path,
            allow_loopx_closeout=True,
        )
    ):
        return False
    receipt = _bridge_summary_task_progress_receipt(bridge_summary_path)
    return bool(
        receipt.get("task_facing_operation_count") == 0
        and receipt.get("task_facing_success_count") == 0
        and receipt.get("raw_material_recorded") is False
    )


def _codex_exec_transport_retry_allowed(
    *,
    category: str,
    bridge_summary_path: Path | None,
    retry_count: int,
    final_message_present: bool,
    turn_deadline: float | None,
) -> bool:
    return bool(
        retry_count < CODEX_EXEC_TRANSPORT_RETRY_LIMIT
        and _codex_exec_side_effect_free_recovery_allowed(
            category=category,
            bridge_summary_path=bridge_summary_path,
            final_message_present=final_message_present,
            turn_deadline=turn_deadline,
        )
    )


def _codex_exec_session_rollover_allowed(
    *,
    category: str,
    bridge_summary_path: Path | None,
    retry_count: int,
    rollover_count: int,
    final_message_present: bool,
    turn_deadline: float | None,
) -> bool:
    return bool(
        retry_count == CODEX_EXEC_TRANSPORT_RETRY_LIMIT
        and rollover_count < CODEX_EXEC_SESSION_ROLLOVER_LIMIT
        and _codex_exec_side_effect_free_recovery_allowed(
            category=category,
            bridge_summary_path=bridge_summary_path,
            final_message_present=final_message_present,
            turn_deadline=turn_deadline,
        )
    )


def _codex_exec_session_rollover_prompt(
    *, original_prompt: str, continuation_prompt: str
) -> str:
    return (
        original_prompt.rstrip()
        + "\n\n"
        + "LoopX Turn fresh-session recovery contract:\n"
        + "- Continue the same task after a native resume transport failure.\n"
        + "- Rebuild context from the current durable workspace and case-local "
        + "LoopX state; prior task-facing progress is already present there.\n"
        + "- Perform only the next bounded task-facing step, then stop.\n"
        + "- Do not use or request official verifier, reward, pass/fail, hidden-test, "
        + "or gold-answer feedback.\n\n"
        + continuation_prompt.strip()
    )


def _prompt_with_app_server_closeout_instruction(prompt_text: str) -> str:
    """Ask native Goal workers to end promptly after scored output exists."""

    return (
        prompt_text.rstrip()
        + "\n\n"
        + "Native Codex Goal worker closeout contract:\n"
        + "- Solve the task using only the available benchmark workspace or the "
        + "private bridge packet above.\n"
        + SKILLSBENCH_OUTPUT_PATH_CONTRACT
        + "\n"
        + "- Before writing the final scored output for optimization, "
        + "scheduling, allocation, routing, planning, or data-processing "
        + "tasks, run a task-derived quality self-check using only visible "
        + "task instructions and workspace data: validate hard constraints, "
        + "compute or estimate the visible objective when the task defines "
        + "one, compare at least one simple alternative or repair pass when "
        + "feasible, and only then write the final task-specified output. Do not "
        + "use official verifier/reward/pass-fail output, hidden tests, "
        + "gold answers, or external benchmark feedback for this self-check.\n"
        + "- After the task-required scored output file is written, immediately "
        + "end the turn with one short confirmation.\n"
        + "- Do not keep optimizing, narrating, or rechecking after the scored "
        + "output exists unless the task explicitly requires more work.\n"
    )


def _normalized_app_server_goal_prompt_style(style: str | None) -> str:
    text = str(style or "").strip().lower()
    if text in {"bridge-only", "native-goal", "cli-exec-like"}:
        return text
    return "bridge-only"


@dataclass(frozen=True)
class CodexExecConfig:
    codex_bin: str = "codex"
    sandbox: str = "workspace-write"
    model: str | None = None
    route: str = "unknown"
    timeout_sec: int = 7200
    dry_run_response: str | None = None
    app_server_goal_worker: bool = False
    codex_cli_goal_worker: bool = False
    dataset: str = "skillsbench-v1.1"
    task_id: str = "llm-prefix-cache-replay"
    run_group_id: str = ""
    job_name: str = ""
    rollout_name: str = ""
    approval_policy: str = "never"
    response_timeout_sec: float = 30.0
    worker_script: str | None = None
    stream_heartbeat_interval_sec: float = 120.0
    first_action_timeout_sec: float = 0.0
    goal_active_timeout_sec: float = 180.0
    app_server_goal_followup_max: int = 0
    app_server_goal_prompt_style: str = "bridge-only"
    bridge_idle_timeout_sec: float = 0.0
    task_output_quiet_timeout_sec: float = 0.0
    reasoning_effort: str | None = None
    codex_api_proxy: str | None = None
    codex_cli_goal_thread_prewarm: bool = False
    worker_public_trace_dir: str | None = None
    remote_command_file_bridge_command: str | None = None
    remote_command_file_bridge_agent_command: str | None = None
    remote_command_file_bridge_timeout_sec: float = 10.0
    loopx_workflow_lifecycle_checkpoint: bool = False
    loopx_turn_agent_cli: bool = False
    loopx_turn_validation_command: str | None = None
    loopx_turn_max_turns: int = 1
    loopx_turn_progress_exit_code: int = 10
    loopx_turn_terminal_policy: str = "validator"
    loopx_case_goal_id: str = "skillsbench-case"
    loopx_case_agent_id: str = BENCHMARK_CASE_LOOPX_AGENT_ID
    loopx_case_todo_id: str = BENCHMARK_CASE_LOOPX_TODO_ID
    loopx_case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH
    loopx_case_registry_path: str = BENCHMARK_CASE_LOOPX_REGISTRY_PATH
    loopx_case_runtime_root: str = BENCHMARK_CASE_LOOPX_RUNTIME_ROOT


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
        self._published_lifecycle_stages: set[str] = set()
        self._workflow_checkpoint_count = 0
        self._bridge_summary_snapshot_ids: dict[str, str] = {}
        self._bridge_summary_snapshot_indexes: dict[str, int] = {}
        self._latest_loopx_turn_agent_progress_receipt: dict[str, Any] = {}

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
            self._publish_worker_lifecycle_trace("initialize")
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
                        "name": "loopx-skillsbench-local-acp-relay",
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
            self._publish_worker_lifecycle_trace("session_new")
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
        output_tokens = max(1, len(response_text.encode("utf-8")) // 4)
        input_tokens = max(1, len(prompt_text.encode("utf-8")) // 4)
        return _json_rpc_result(
            message_id,
            {
                "stopReason": "end_turn",
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
            },
        )

    def _run_codex(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
        _bypass_loopx_turn: bool = False,
        _turn_deadline: float | None = None,
        _transport_retry_count: int = 0,
        _session_rollover_index: int = 0,
    ) -> str:
        if self._config.dry_run_response is not None:
            return self._config.dry_run_response
        if self._config.loopx_turn_agent_cli and not _bypass_loopx_turn:
            sequence_deadline = time.monotonic() + max(
                1.0, float(self._config.timeout_sec)
            )
            session["_loopx_turn_original_prompt"] = prompt_text
            session["_loopx_turn_codex_rollover_count"] = 0
            try:
                return run_skillsbench_loopx_turn_relay(
                    prompt=prompt_text,
                    session_id=session_id,
                    relay_config=self._config,
                    agent_runner=lambda turn_prompt: self._run_loopx_turn_agent_prompt(
                        turn_prompt,
                        session=session,
                        session_id=session_id,
                        stdout=stdout,
                        turn_deadline=sequence_deadline,
                    ),
                    trace_writer=self._write_worker_public_trace,
                )
            finally:
                session.pop("_loopx_turn_codex_thread_id", None)
                session.pop("_loopx_turn_codex_rollover_count", None)
                session.pop("_loopx_turn_original_prompt", None)
                session_root = _loopx_turn_local_session_root(
                    self._config.worker_public_trace_dir,
                    session_id,
                )
                if session_root is not None:
                    shutil.rmtree(session_root, ignore_errors=True)
                    with contextlib.suppress(OSError):
                        session_root.parent.rmdir()
        if self._config.app_server_goal_worker:
            return self._run_app_server_goal_worker(
                prompt_text,
                session=session,
                session_id=session_id,
                stdout=stdout,
            )
        if self._config.codex_cli_goal_worker:
            return self._run_codex_cli_goal_worker(
                prompt_text,
                session=session,
                session_id=session_id,
                stdout=stdout,
            )
        with tempfile.TemporaryDirectory(prefix="gh-skillsbench-acp-") as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "last-message.txt"
            stdout_path = tmp_path / "codex-stdout.txt"
            stderr_path = tmp_path / "codex-stderr.txt"
            prompt_for_codex = prompt_text
            cwd = _safe_cwd(session.get("cwd"), default=os.getcwd())
            resumable_loopx_turn = bool(
                _bypass_loopx_turn
                and self._config.loopx_turn_agent_cli
                and self._config.loopx_turn_max_turns > 1
            )
            resume_session_id = (
                str(session.get("_loopx_turn_codex_thread_id") or "")
                if resumable_loopx_turn
                else ""
            )
            bridge_server_proc: subprocess.Popen[str] | None = None
            if self._config.remote_command_file_bridge_command:
                if _is_bridge_action_preflight_prompt(prompt_text):
                    bridge_probe = self._reverse_channel_json_preflight_probe()
                else:
                    bridge_probe = self._consume_remote_bridge_for_solver()
                self._publish_remote_bridge_consumption_trace(bridge_probe)
                if bridge_probe.get("ready") is not True:
                    raise RuntimeError("remote command/file bridge probe failed")
                if resumable_loopx_turn:
                    session_root = _loopx_turn_local_session_root(
                        self._config.worker_public_trace_dir,
                        session_id,
                    )
                    if session_root is None:
                        raise RuntimeError(
                            "resumable LoopX Turn requires a public trace directory"
                        )
                    local_cwd = session_root / "cwd"
                else:
                    local_cwd = tmp_path / "local-codex-cwd"
                local_cwd.mkdir(parents=True, exist_ok=True)
                cwd = str(local_cwd)
                bridge_summary_path = tmp_path / "remote-bridge-agent-ops.jsonl"
                agent_bridge_command = (
                    self._config.remote_command_file_bridge_agent_command
                    or self._config.remote_command_file_bridge_command
                    or ""
                )
                agent_bridge_command, bridge_server_proc = (
                    self._start_json_file_bridge_server(
                        tmp_path=tmp_path,
                        local_cwd=local_cwd,
                        bridge_command=agent_bridge_command,
                    )
                )
                instrumented_bridge = self._write_instrumented_bridge_wrapper(
                    tmp_path=tmp_path,
                    summary_path=bridge_summary_path,
                    bridge_command=agent_bridge_command,
                )
                bridge_command_for_agent = str(instrumented_bridge)
                if self._config.loopx_workflow_lifecycle_checkpoint:
                    self._workflow_checkpoint_count += 1
                    self._run_loopx_workflow_lifecycle_checkpoint(
                        checkpoint_index=self._workflow_checkpoint_count,
                    )
                prompt_for_codex = self._prompt_with_remote_bridge_packet(
                    prompt_text,
                    bridge_probe=bridge_probe,
                    bridge_command_for_agent=bridge_command_for_agent,
                )
            else:
                bridge_summary_path = None
            if resume_session_id:
                cmd = [
                    self._config.codex_bin,
                    "exec",
                    "resume",
                    "--skip-git-repo-check",
                    "--output-last-message",
                    str(output_path),
                    "--json",
                ]
            else:
                cmd = [self._config.codex_bin, "exec"]
                if not resumable_loopx_turn:
                    cmd.append("--ephemeral")
                cmd.extend(
                    [
                        "--skip-git-repo-check",
                        "--sandbox",
                        self._config.sandbox,
                        "-C",
                        cwd,
                        "--output-last-message",
                        str(output_path),
                        "--json",
                    ]
                )
            if self._config.reasoning_effort:
                cmd.extend(
                    [
                        "-c",
                        "model_reasoning_effort="
                        + json.dumps(str(self._config.reasoning_effort)),
                    ]
                )
            model = self._config.model or session.get("model")
            if model:
                cmd.extend(["--model", str(model)])
            if resume_session_id:
                cmd.extend([resume_session_id, "-"])
            elif resumable_loopx_turn:
                cmd.append("-")
            codex_stdin_prompt = prompt_for_codex
            stdout_text = ""
            stderr_text = ""
            try:
                with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
                    "w", encoding="utf-8"
                ) as stderr_file:
                    codex_env = os.environ.copy()
                    if bridge_summary_path is not None:
                        codex_env["LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH"] = str(
                            bridge_summary_path
                        )
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        text=True,
                        env=codex_env,
                        start_new_session=True,
                    )
                    _write_process_stdin_async(proc, codex_stdin_prompt)
                    remaining_turn_seconds = (
                        _turn_deadline - time.monotonic()
                        if _turn_deadline is not None
                        else float(self._config.timeout_sec)
                    )
                    if remaining_turn_seconds <= 0:
                        self._terminate_codex_process(proc)
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_turn_time_budget_exhausted"
                        )
                    effective_timeout_sec = remaining_turn_seconds
                    deadline = time.monotonic() + effective_timeout_sec
                    first_action_deadline = 0.0
                    if (
                        bridge_summary_path is not None
                        and self._config.first_action_timeout_sec > 0
                        and _prompt_requires_bridge_first_action(prompt_for_codex)
                    ):
                        first_action_deadline = (
                            time.monotonic()
                            + max(1.0, self._config.first_action_timeout_sec)
                        )
                    meaningful_progress_deadline = 0.0
                    meaningful_progress_seen = False
                    meaningful_progress_required = (
                        bridge_summary_path is not None
                        and self._config.first_action_timeout_sec > 0
                        and _prompt_requires_meaningful_bridge_progress(
                            prompt_for_codex,
                            route=self._config.route,
                        )
                    )
                    allow_loopx_closeout_progress = self._config.route.startswith(
                        "loopx-"
                    )
                    if meaningful_progress_required:
                        meaningful_progress_deadline = (
                            time.monotonic()
                            + max(1.0, self._config.first_action_timeout_sec)
                        )
                    first_action_seen = not bool(first_action_deadline)
                    bridge_idle_timeout_sec = max(
                        0.0,
                        float(self._config.bridge_idle_timeout_sec or 0.0),
                    )
                    bridge_activity_seen = False
                    last_bridge_summary_size = 0
                    last_bridge_activity_at = time.monotonic()
                    next_heartbeat = (
                        time.monotonic()
                        + max(1.0, self._config.stream_heartbeat_interval_sec)
                    )
                    while proc.poll() is None:
                        now = time.monotonic()
                        if bridge_summary_path is not None:
                            try:
                                current_bridge_summary_size = (
                                    bridge_summary_path.stat().st_size
                                )
                            except OSError:
                                current_bridge_summary_size = 0
                            if current_bridge_summary_size > last_bridge_summary_size:
                                last_bridge_summary_size = current_bridge_summary_size
                                last_bridge_activity_at = now
                                bridge_activity_seen = True
                                first_action_seen = True
                            elif (
                                not first_action_seen
                                and current_bridge_summary_size > 0
                            ):
                                first_action_seen = True
                            if not meaningful_progress_seen:
                                meaningful_progress_seen = (
                                    _bridge_summary_has_meaningful_agent_progress(
                                        bridge_summary_path,
                                        allow_loopx_closeout=(
                                            allow_loopx_closeout_progress
                                        ),
                                    )
                                )
                        if (
                            not first_action_seen
                            and first_action_deadline
                            and now >= first_action_deadline
                        ):
                            self._terminate_codex_process(proc)
                            if bridge_summary_path is not None:
                                self._publish_remote_bridge_agent_operations_trace(
                                    bridge_summary_path=bridge_summary_path,
                                )
                            self._publish_codex_exec_failure_trace(
                                stage="first_action_timeout",
                                returncode=124,
                                stdout_text="",
                                stderr_text="codex_exec_first_action_timeout\n",
                                final_message_present=output_path.exists(),
                                final_message_bytes=(
                                    output_path.stat().st_size
                                    if output_path.exists()
                                    else 0
                                ),
                                failure_category="codex_exec_first_action_timeout",
                            )
                            return _recoverable_codex_turn_failure_message(
                                "codex_exec_first_action_timeout"
                            )
                        if (
                            meaningful_progress_required
                            and not meaningful_progress_seen
                            and meaningful_progress_deadline
                            and now >= meaningful_progress_deadline
                        ):
                            self._terminate_codex_process(proc)
                            if bridge_summary_path is not None:
                                self._publish_remote_bridge_agent_operations_trace(
                                    bridge_summary_path=bridge_summary_path,
                                )
                            self._publish_codex_exec_failure_trace(
                                stage="meaningful_bridge_progress_timeout",
                                returncode=124,
                                stdout_text="",
                                stderr_text="codex_exec_first_action_timeout\n",
                                final_message_present=output_path.exists(),
                                final_message_bytes=(
                                    output_path.stat().st_size
                                    if output_path.exists()
                                    else 0
                                ),
                                failure_category="codex_exec_first_action_timeout",
                            )
                            return _recoverable_codex_turn_failure_message(
                                "codex_exec_first_action_timeout"
                            )
                        if (
                            bridge_activity_seen
                            and bridge_summary_path is not None
                            and bridge_idle_timeout_sec > 0
                            and not _bridge_summary_has_inflight_operation(
                                bridge_summary_path
                            )
                            and now - last_bridge_activity_at >= bridge_idle_timeout_sec
                        ):
                            self._terminate_codex_process(proc)
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                            self._publish_codex_exec_failure_trace(
                                stage="bridge_idle_timeout",
                                returncode=124,
                                stdout_text="",
                                stderr_text="codex_exec_bridge_idle_timeout\n",
                                final_message_present=output_path.exists(),
                                final_message_bytes=(
                                    output_path.stat().st_size
                                    if output_path.exists()
                                    else 0
                                ),
                                failure_category="codex_exec_bridge_idle_timeout",
                            )
                            return _recoverable_codex_turn_failure_message(
                                "codex_exec_bridge_idle_timeout"
                            )
                        if now >= deadline:
                            self._terminate_codex_process(proc)
                            raise subprocess.TimeoutExpired(
                                cmd,
                                effective_timeout_sec,
                            )
                        if now >= next_heartbeat:
                            self._write_worker_heartbeat(
                                stdout,
                                session_id=session_id,
                                text="local codex exec still running",
                            )
                            next_heartbeat = (
                                now
                                + max(
                                    1.0,
                                    self._config.stream_heartbeat_interval_sec,
                                )
                            )
                        time.sleep(0.2)
            except subprocess.TimeoutExpired:
                stdout_text = (
                    stdout_path.read_text(encoding="utf-8", errors="replace")
                    if stdout_path.exists()
                    else ""
                )
                stderr_text = (
                    stderr_path.read_text(encoding="utf-8", errors="replace")
                    if stderr_path.exists()
                    else ""
                )
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                self._publish_codex_exec_failure_trace(
                    stage="timeout",
                    returncode=124,
                    stdout_text=stdout_text,
                    stderr_text=stderr_text,
                    final_message_present=output_path.exists(),
                    final_message_bytes=(
                        output_path.stat().st_size if output_path.exists() else 0
                    ),
                )
                return _recoverable_codex_turn_failure_message("codex_exec_timeout")
            finally:
                self._terminate_bridge_server_process(bridge_server_proc)
            stdout_text = (
                stdout_path.read_text(encoding="utf-8", errors="replace")
                if stdout_path.exists()
                else ""
            )
            stderr_text = (
                stderr_path.read_text(encoding="utf-8", errors="replace")
                if stderr_path.exists()
                else ""
            )
            if proc.returncode != 0:
                category = _codex_exec_failure_category(
                    returncode=proc.returncode,
                    stderr_text=stderr_text,
                    stdout_text=stdout_text,
                )
                recoverable_turn_failure = bool(
                    category in RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES
                    and prompt_text.strip()
                    != SKILLSBENCH_LOCAL_ACP_RELAY_HEALTH_PROMPT
                    and not _is_bridge_action_preflight_prompt(prompt_text)
                )
                retry_scheduled = bool(
                    recoverable_turn_failure
                    and resumable_loopx_turn
                    and _codex_exec_transport_retry_allowed(
                        category=category,
                        bridge_summary_path=bridge_summary_path,
                        retry_count=_transport_retry_count,
                        final_message_present=output_path.exists(),
                        turn_deadline=_turn_deadline,
                    )
                )
                rollover_count = int(
                    session.get("_loopx_turn_codex_rollover_count") or 0
                )
                session_rollover_scheduled = bool(
                    recoverable_turn_failure
                    and resumable_loopx_turn
                    and bool(resume_session_id)
                    and _codex_exec_session_rollover_allowed(
                        category=category,
                        bridge_summary_path=bridge_summary_path,
                        retry_count=_transport_retry_count,
                        rollover_count=rollover_count,
                        final_message_present=output_path.exists(),
                        turn_deadline=_turn_deadline,
                    )
                )
                self._publish_codex_exec_failure_trace(
                    stage="exit_nonzero",
                    returncode=proc.returncode,
                    stdout_text=stdout_text,
                    stderr_text=stderr_text,
                    final_message_present=output_path.exists(),
                    final_message_bytes=(
                        output_path.stat().st_size if output_path.exists() else 0
                    ),
                    failure_category=category,
                    recoverable_turn_failure=recoverable_turn_failure,
                    transport_retry_index=_transport_retry_count,
                    retry_scheduled=retry_scheduled,
                    session_rollover_index=_session_rollover_index,
                    session_rollover_scheduled=session_rollover_scheduled,
                )
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                if retry_scheduled:
                    return self._run_codex(
                        prompt_text,
                        session=session,
                        session_id=session_id,
                        stdout=stdout,
                        _bypass_loopx_turn=_bypass_loopx_turn,
                        _turn_deadline=_turn_deadline,
                        _transport_retry_count=_transport_retry_count + 1,
                        _session_rollover_index=_session_rollover_index,
                    )
                if session_rollover_scheduled:
                    original_prompt = str(
                        session.get("_loopx_turn_original_prompt") or ""
                    ).strip()
                    if not original_prompt:
                        return _recoverable_codex_turn_failure_message(category)
                    next_rollover_index = rollover_count + 1
                    session["_loopx_turn_codex_rollover_count"] = next_rollover_index
                    previous_thread_present = bool(
                        session.pop("_loopx_turn_codex_thread_id", None)
                    )
                    rollover_prompt = _codex_exec_session_rollover_prompt(
                        original_prompt=original_prompt,
                        continuation_prompt=prompt_text,
                    )
                    try:
                        response = self._run_codex(
                            rollover_prompt,
                            session=session,
                            session_id=session_id,
                            stdout=stdout,
                            _bypass_loopx_turn=_bypass_loopx_turn,
                            _turn_deadline=_turn_deadline,
                            _transport_retry_count=(
                                CODEX_EXEC_TRANSPORT_RETRY_LIMIT
                            ),
                            _session_rollover_index=next_rollover_index,
                        )
                    except (RuntimeError, TimeoutError):
                        self._publish_codex_exec_session_rollover_trace(
                            stage="failed",
                            rollover_index=next_rollover_index,
                            resume_failure_count=_transport_retry_count + 1,
                            previous_thread_present=previous_thread_present,
                            fresh_thread_present=bool(
                                session.get("_loopx_turn_codex_thread_id")
                            ),
                        )
                        raise
                    rollover_succeeded = not response.startswith(
                        RECOVERABLE_CODEX_TURN_FAILURE_PREFIX
                    )
                    self._publish_codex_exec_session_rollover_trace(
                        stage="completed" if rollover_succeeded else "failed",
                        rollover_index=next_rollover_index,
                        resume_failure_count=_transport_retry_count + 1,
                        previous_thread_present=previous_thread_present,
                        fresh_thread_present=bool(
                            session.get("_loopx_turn_codex_thread_id")
                        ),
                    )
                    return response
                if recoverable_turn_failure:
                    return _recoverable_codex_turn_failure_message(category)
                raise RuntimeError(f"local codex execution failed: {category}")
            if resumable_loopx_turn and not resume_session_id:
                observed_session_id = codex_cli_session_id_from_jsonl(stdout_text)
                if not observed_session_id:
                    self._publish_codex_exec_failure_trace(
                        stage="session_start_missing",
                        returncode=0,
                        stdout_text=stdout_text,
                        stderr_text=stderr_text,
                        final_message_present=output_path.exists(),
                        final_message_bytes=(
                            output_path.stat().st_size if output_path.exists() else 0
                        ),
                        failure_category="codex_exec_session_missing",
                        recoverable_turn_failure=True,
                    )
                    return _recoverable_codex_turn_failure_message(
                        "codex_exec_session_missing"
                    )
                session["_loopx_turn_codex_thread_id"] = observed_session_id
            try:
                response = output_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                self._publish_codex_exec_failure_trace(
                    stage="final_message_missing",
                    returncode=proc.returncode,
                    stdout_text=stdout_text,
                    stderr_text=stderr_text,
                    final_message_present=False,
                    final_message_bytes=0,
                    failure_category="codex_final_message_missing",
                )
                raise RuntimeError("local codex final message missing") from exc
            if bridge_summary_path is not None:
                self._publish_remote_bridge_agent_operations_trace(
                    bridge_summary_path=bridge_summary_path,
                )
                if _bypass_loopx_turn and self._config.loopx_turn_agent_cli:
                    self._latest_loopx_turn_agent_progress_receipt = (
                        _bridge_summary_task_progress_receipt(bridge_summary_path)
                    )
            return response or "local codex returned an empty final message"

    def _run_loopx_turn_agent_prompt(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
        turn_deadline: float,
    ) -> SkillsBenchTurnAgentResult:
        self._latest_loopx_turn_agent_progress_receipt = {}
        response = self._run_codex(
            prompt_text,
            session=session,
            session_id=session_id,
            stdout=stdout,
            _bypass_loopx_turn=True,
            _turn_deadline=turn_deadline,
        )
        return SkillsBenchTurnAgentResult(
            response_text=response,
            progress_evidence=dict(self._latest_loopx_turn_agent_progress_receipt),
        )

    def _run_codex_cli_goal_worker(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
    ) -> str:
        """Run one ACP prompt through the real Codex CLI TUI /goal surface."""

        resolved_codex_bin = resolve_codex_cli_binary(self._config.codex_bin)
        if not resolved_codex_bin:
            self._publish_codex_cli_goal_trace(
                ok=False,
                stage="codex_cli_unavailable",
                goal_active_observed=False,
                goal_terminal_observed=False,
                first_action_observed=False,
                bridge_summary_path=None,
                goal_slash_command_submitted=False,
            )
            raise RuntimeError("codex cli goal worker requires Codex CLI")
        if shutil.which("tmux") is None:
            self._publish_codex_cli_goal_trace(
                ok=False,
                stage="tmux_missing",
                goal_active_observed=False,
                goal_terminal_observed=False,
                first_action_observed=False,
                bridge_summary_path=None,
                goal_slash_command_submitted=False,
            )
            raise RuntimeError("codex cli goal worker requires tmux")
        with tempfile.TemporaryDirectory(prefix="gh-skillsbench-cli-goal-") as tmp:
            tmp_path = Path(tmp)
            prompt_for_codex = prompt_text
            cwd = _safe_cwd(session.get("cwd"), default=os.getcwd())
            bridge_server_proc: subprocess.Popen[str] | None = None
            bridge_summary_path: Path | None = None
            goal_prompt_file_used = False
            goal_command_submission_method = "paste-buffer"
            if self._config.remote_command_file_bridge_command:
                if _is_bridge_action_preflight_prompt(prompt_text):
                    bridge_probe = self._reverse_channel_json_preflight_probe()
                else:
                    bridge_probe = self._consume_remote_bridge_for_solver()
                self._publish_remote_bridge_consumption_trace(bridge_probe)
                if bridge_probe.get("ready") is not True:
                    self._publish_codex_cli_goal_trace(
                        ok=False,
                        stage="bridge_probe_failed",
                        goal_active_observed=False,
                        goal_terminal_observed=False,
                        first_action_observed=False,
                        bridge_summary_path=None,
                        goal_slash_command_submitted=False,
                    )
                    raise RuntimeError("remote command/file bridge probe failed")
                local_cwd = tmp_path / "local-codex-cli-goal-cwd"
                local_cwd.mkdir(parents=True, exist_ok=True)
                cwd = str(local_cwd)
                bridge_summary_path = tmp_path / "remote-bridge-agent-ops.jsonl"
                agent_bridge_command = (
                    self._config.remote_command_file_bridge_agent_command
                    or self._config.remote_command_file_bridge_command
                    or ""
                )
                agent_bridge_command, bridge_server_proc = (
                    self._start_json_file_bridge_server(
                        tmp_path=tmp_path,
                        local_cwd=local_cwd,
                        bridge_command=agent_bridge_command,
                    )
                )
                instrumented_bridge = self._write_instrumented_bridge_wrapper(
                    tmp_path=tmp_path,
                    summary_path=bridge_summary_path,
                    bridge_command=agent_bridge_command,
                )
                prompt_for_codex = self._prompt_with_remote_bridge_packet(
                    prompt_text,
                    bridge_probe=bridge_probe,
                    bridge_command_for_agent=str(instrumented_bridge),
                )
                prompt_instruction_path = (
                    Path(cwd) / CODEX_CLI_GOAL_TASK_PROMPT_FILENAME
                )
                prompt_instruction_path.write_text(
                    prompt_for_codex,
                    encoding="utf-8",
                )
                prompt_for_goal = build_codex_cli_goal_file_objective(
                    CODEX_CLI_GOAL_TASK_PROMPT_FILENAME
                )
                goal_prompt_file_used = True
                goal_command_submission_method = "typed"
            else:
                prompt_for_goal = prompt_for_codex
            goal_command_text = build_codex_cli_goal_tui_input(prompt_for_goal)
            prompt_path = tmp_path / "goal-prompt.txt"
            prompt_path.write_text(
                goal_command_text,
                encoding="utf-8",
            )
            tmux_name = f"gh-sb-cli-goal-{uuid.uuid4().hex[:10]}"
            cmd = build_codex_cli_tui_command(
                codex_bin=resolved_codex_bin,
                sandbox=self._config.sandbox,
                approval_policy=self._config.approval_policy,
                cwd=cwd,
                reasoning_effort=self._config.reasoning_effort,
                model=self._config.model or session.get("model"),
            )
            shell_command = codex_cli_tui_shell_command(
                cmd,
                env=codex_cli_tui_environment(self._config.codex_api_proxy),
            )
            goal_active_observed = False
            goal_terminal_observed = False
            goal_failed_observed = False
            goal_slash_command_submitted = False
            goal_kickoff_prompt_submitted = False
            post_bridge_terminal_stage = ""
            first_action_seen = False
            bridge_activity_seen = False
            last_bridge_summary_size = 0
            last_bridge_activity_at = time.monotonic()
            meaningful_progress_seen = False
            pre_bridge_recovery_attempt_count = 0
            pre_bridge_recovery_action = ""
            pre_bridge_recovery_skip_reason = ""
            post_bridge_recovery_attempt_count = 0
            post_bridge_recovery_action = ""
            post_bridge_recovery_skip_reason = ""
            pre_bridge_terminal_stage = ""
            thread_prewarm = self._config.codex_cli_goal_thread_prewarm
            self._last_codex_cli_goal_lifecycle = goal_lifecycle = CodexCliGoalLifecycleGeneration()
            try:
                startup_stage, thread_prewarm_observed = start_codex_cli_goal_tui_session(
                    tmux_name=tmux_name,
                    cwd=cwd,
                    shell_command=shell_command,
                    thread_prewarm=thread_prewarm,
                    thread_prewarm_timeout_sec=CODEX_CLI_GOAL_THREAD_PREWARM_TIMEOUT_SEC,
                )
                if startup_stage:
                    self._publish_codex_cli_goal_trace(
                        ok=False,
                        stage=startup_stage,
                        goal_active_observed=False,
                        goal_terminal_observed=False,
                        first_action_observed=False,
                        bridge_summary_path=bridge_summary_path,
                        thread_prewarm_observed=thread_prewarm_observed,
                        goal_prompt_file_used=goal_prompt_file_used,
                        goal_command_submission_method=goal_command_submission_method,
                        goal_slash_command_submitted=False,
                    )
                    return _recoverable_codex_turn_failure_message(
                        "codex_exec_first_action_timeout"
                    )
                goal_lifecycle.begin(tmux_capture(tmux_name))
                if goal_prompt_file_used:
                    tmux_type_text_and_submit(
                        tmux_name=tmux_name,
                        text=goal_command_text,
                    )
                else:
                    tmux_paste_file_and_submit(
                        tmux_name=tmux_name,
                        prompt_path=prompt_path,
                        buffer_suffix="prompt",
                    )
                goal_slash_command_submitted = True
                deadline = time.monotonic() + self._config.timeout_sec
                goal_active_deadline = 0.0
                if (
                    bridge_summary_path is not None
                    and self._config.goal_active_timeout_sec > 0
                    and _prompt_requires_bridge_first_action(prompt_for_codex)
                ):
                    goal_active_timeout_sec = max(
                        1.0,
                        float(self._config.goal_active_timeout_sec or 0.0),
                    )
                    goal_active_deadline = (
                        time.monotonic() + goal_active_timeout_sec
                    )
                first_action_deadline = 0.0
                if (
                    bridge_summary_path is not None
                    and self._config.first_action_timeout_sec > 0
                    and _prompt_requires_bridge_first_action(prompt_for_codex)
                ):
                    first_action_deadline = (
                        time.monotonic()
                        + max(1.0, self._config.first_action_timeout_sec)
                    )
                meaningful_progress_required = (
                    bridge_summary_path is not None
                    and self._config.first_action_timeout_sec > 0
                    and _prompt_requires_meaningful_bridge_progress(
                        prompt_for_codex,
                        route=self._config.route,
                    )
                )
                meaningful_progress_deadline = (
                    time.monotonic()
                    + max(1.0, self._config.first_action_timeout_sec)
                    if meaningful_progress_required
                    else 0.0
                )
                first_action_seen = not bool(first_action_deadline)
                bridge_idle_timeout_sec = max(
                    0.0,
                    float(self._config.bridge_idle_timeout_sec or 0.0),
                )
                task_output_quiet_timeout_sec = max(
                    0.0,
                    float(self._config.task_output_quiet_timeout_sec or 0.0),
                )
                next_heartbeat = (
                    time.monotonic()
                    + max(1.0, self._config.stream_heartbeat_interval_sec)
                )
                task_output_progress_seen = False
                last_task_output_activity_at = last_bridge_activity_at
                while time.monotonic() < deadline:
                    now = time.monotonic()
                    capture = self._last_codex_cli_goal_tui_capture = tmux_capture(tmux_name)
                    turn_active = codex_cli_tui_turn_active(capture)
                    goal_lifecycle.observe(capture, turn_active=turn_active)
                    if turn_active:
                        last_task_output_activity_at = now
                    if goal_lifecycle.active_observed:
                        goal_active_observed = True
                    goal_failed_now = goal_lifecycle.failed_advanced
                    if bridge_summary_path is not None:
                        try:
                            current_bridge_summary_size = bridge_summary_path.stat().st_size
                        except OSError:
                            current_bridge_summary_size = 0
                        if current_bridge_summary_size > last_bridge_summary_size:
                            last_bridge_summary_size = current_bridge_summary_size
                            last_bridge_activity_at = now
                            last_task_output_activity_at = now
                            bridge_activity_seen = True
                            first_action_seen = True
                        elif (
                            not first_action_seen
                            and current_bridge_summary_size > 0
                        ):
                            first_action_seen = True
                        if not meaningful_progress_seen:
                            meaningful_progress_seen = (
                                _bridge_summary_has_meaningful_agent_progress(
                                    bridge_summary_path,
                                    allow_loopx_closeout=False,
                                )
                            )
                        if (
                            not task_output_progress_seen
                            and task_output_quiet_timeout_sec > 0
                        ):
                            task_output_progress_seen = (
                                _bridge_summary_has_successful_task_operation(
                                    bridge_summary_path
                                )
                            )
                    if codex_cli_goal_should_submit_kickoff(
                        bridge_enabled=bridge_summary_path is not None,
                        goal_active_observed=goal_active_observed,
                        kickoff_submitted=goal_kickoff_prompt_submitted,
                        turn_active=turn_active,
                        first_action_seen=first_action_seen,
                        capture=capture,
                    ):
                        goal_kickoff_prompt_submitted = True
                        tmux_type_text_and_submit(
                            tmux_name=tmux_name,
                            text=CODEX_CLI_GOAL_KICKOFF_PROMPT,
                        )
                        (
                            goal_active_deadline,
                            first_action_deadline,
                            meaningful_progress_deadline,
                        ) = codex_cli_goal_reset_pre_bridge_deadlines(
                            now=now,
                            first_action_timeout_sec=self._config.first_action_timeout_sec,
                            goal_active_deadline=goal_active_deadline,
                            goal_active_timeout_sec=self._config.goal_active_timeout_sec,
                            first_action_deadline=first_action_deadline,
                            meaningful_progress_deadline=meaningful_progress_deadline,
                        )
                        next_heartbeat = now + max(
                            1.0,
                            self._config.stream_heartbeat_interval_sec,
                        )
                        continue
                    if codex_cli_goal_should_ignore_stale_terminal(
                        goal_failed_now=goal_failed_now,
                        kickoff_submitted=goal_kickoff_prompt_submitted,
                        first_action_seen=first_action_seen,
                        turn_active=turn_active,
                        first_action_deadline=first_action_deadline,
                        now=now,
                    ):
                        goal_failed_now = False
                    if goal_lifecycle.achieved_advanced:
                        goal_terminal_observed = True
                        break
                    retryable_startup_blocker_stage = ""
                    if not goal_active_observed and not first_action_seen:
                        retryable_startup_blocker_stage = codex_cli_tui_retryable_startup_blocker_stage(capture)
                    if retryable_startup_blocker_stage:
                        tmux_kill_session(tmux_name)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage=retryable_startup_blocker_stage,
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=goal_command_submission_method,
                            goal_kickoff_prompt_submitted=goal_kickoff_prompt_submitted,
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_cli_goal_" + retryable_startup_blocker_stage
                        )
                    pre_bridge_blocker_stage = ""
                    if bridge_summary_path is not None and not first_action_seen:
                        pre_bridge_blocker_stage = (
                            codex_cli_tui_pre_bridge_blocker_stage(
                                capture,
                                prompt_visible=(
                                    codex_cli_tui_input_prompt_visible(capture)
                                ),
                                terminal_observed=goal_failed_now,
                            )
                        )
                    if pre_bridge_blocker_stage:
                        recovery_action = codex_cli_tui_pre_bridge_recovery_action(
                            capture,
                            stage=pre_bridge_blocker_stage,
                        )
                        if recovery_action in {
                            "press_enter",
                            "restart_tui_goal",
                            "typed_goal_resubmit",
                        } and (
                            pre_bridge_recovery_attempt_count
                            < PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT
                        ):
                            pre_bridge_recovery_attempt_count += 1
                            pre_bridge_recovery_action = recovery_action
                            restart_stage = ""
                            if recovery_action == "press_enter":
                                tmux_submit_enter(tmux_name)
                            else:
                                if recovery_action == "restart_tui_goal":
                                    tmux_kill_session(tmux_name)
                                    (
                                        restart_stage,
                                        thread_prewarm_observed,
                                    ) = start_codex_cli_goal_tui_session(
                                        tmux_name=tmux_name,
                                        cwd=cwd,
                                        shell_command=shell_command,
                                        thread_prewarm=thread_prewarm,
                                        thread_prewarm_timeout_sec=CODEX_CLI_GOAL_THREAD_PREWARM_TIMEOUT_SEC,
                                    )
                                    if not restart_stage:
                                        capture = tmux_capture(tmux_name)
                                        goal_terminal_observed = False
                                        goal_failed_observed = False
                                if not restart_stage:
                                    goal_lifecycle.begin(capture)
                                    goal_active_observed = False
                                    goal_kickoff_prompt_submitted = False
                                    tmux_type_text_and_submit(
                                        tmux_name=tmux_name,
                                        text=goal_command_text,
                                    )
                            if restart_stage:
                                pre_bridge_blocker_stage = restart_stage
                                pre_bridge_recovery_skip_reason = "restart_failed"
                            else:
                                deadlines = codex_cli_goal_reset_pre_bridge_deadlines(
                                    now=now,
                                    first_action_timeout_sec=self._config.first_action_timeout_sec,
                                    goal_active_deadline=goal_active_deadline,
                                    goal_active_timeout_sec=self._config.goal_active_timeout_sec,
                                    first_action_deadline=first_action_deadline,
                                    meaningful_progress_deadline=meaningful_progress_deadline,
                                )
                                goal_active_deadline, first_action_deadline, meaningful_progress_deadline = deadlines
                                if recovery_action in {
                                    "restart_tui_goal",
                                    "typed_goal_resubmit",
                                }:
                                    next_heartbeat = now + max(
                                        1.0,
                                        self._config.stream_heartbeat_interval_sec,
                                    )
                                else:
                                    time.sleep(1.0)
                                continue
                        pre_bridge_recovery_skip_reason = pre_bridge_recovery_skip_reason or (
                            codex_cli_tui_pre_bridge_recovery_skip_reason(
                                capture,
                                stage=pre_bridge_blocker_stage,
                                recovery_action=recovery_action,
                            )
                        )
                        if (
                            not pre_bridge_recovery_skip_reason
                            and recovery_action
                            in {
                                "press_enter",
                                "restart_tui_goal",
                                "typed_goal_resubmit",
                            }
                        ):
                            pre_bridge_recovery_skip_reason = "retry_limit_reached"
                        tmux_kill_session(tmux_name)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage=pre_bridge_blocker_stage,
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            goal_kickoff_prompt_submitted=goal_kickoff_prompt_submitted,
                            post_bridge_recovery_attempt_count=pre_bridge_recovery_attempt_count,
                            post_bridge_recovery_action=pre_bridge_recovery_action,
                            post_bridge_recovery_skip_reason=pre_bridge_recovery_skip_reason,
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_cli_goal_" + pre_bridge_blocker_stage
                        )
                    if goal_failed_now:
                        if bridge_summary_path is not None and not first_action_seen:
                            prompt_visible = codex_cli_tui_input_prompt_visible(capture)
                            pre_bridge_recovery_skip_reason = codex_cli_tui_pre_bridge_terminal_skip_reason(capture, prompt_visible=prompt_visible)
                            pre_bridge_terminal_stage = codex_cli_tui_pre_bridge_terminal_stage(capture, prompt_visible=prompt_visible)
                        elif bridge_summary_path is not None:
                            post_bridge_terminal_stage = (
                                codex_cli_tui_post_bridge_blocker_stage(
                                    capture,
                                    prompt_visible=(
                                        codex_cli_tui_input_prompt_visible(capture)
                                    ),
                                )
                            )
                        goal_terminal_observed = True
                        goal_failed_observed = True
                        break
                    if (
                        not goal_active_observed
                        and not first_action_seen
                        and goal_active_deadline
                        and now >= goal_active_deadline
                    ):
                        tmux_kill_session(tmux_name)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage="goal_active_timeout",
                            goal_active_observed=False,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=False,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            post_bridge_recovery_attempt_count=pre_bridge_recovery_attempt_count,
                            post_bridge_recovery_action=pre_bridge_recovery_action,
                            post_bridge_recovery_skip_reason=pre_bridge_recovery_skip_reason,
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_cli_goal_goal_active_timeout"
                        )
                    if (
                        not first_action_seen
                        and codex_cli_goal_watchdog_expired(
                            deadline=first_action_deadline,
                            now=now,
                            turn_active=turn_active,
                        )
                    ):
                        tmux_kill_session(tmux_name)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage="first_action_timeout",
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=False,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            goal_kickoff_prompt_submitted=(
                                goal_kickoff_prompt_submitted
                            ),
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_first_action_timeout"
                        )
                    if (
                        meaningful_progress_required
                        and not meaningful_progress_seen
                        and codex_cli_goal_watchdog_expired(
                            deadline=meaningful_progress_deadline,
                            now=now,
                            turn_active=turn_active,
                        )
                    ):
                        tmux_kill_session(tmux_name)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage="meaningful_bridge_progress_timeout",
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_first_action_timeout"
                        )
                    post_bridge_blocker_stage = ""
                    if (
                        bridge_activity_seen
                        and bridge_summary_path is not None
                        and not _bridge_summary_has_inflight_operation(
                            bridge_summary_path
                        ) and (not post_bridge_recovery_attempt_count or now - last_bridge_activity_at >= 30.0)
                    ):
                        post_bridge_blocker_stage = (
                            codex_cli_tui_post_bridge_blocker_stage(
                                capture,
                                prompt_visible=(
                                    codex_cli_tui_input_prompt_visible(capture)
                                ),
                            )
                        )
                    if post_bridge_blocker_stage:
                        recovery_action = codex_cli_tui_post_bridge_recovery_action(
                            capture,
                            stage=post_bridge_blocker_stage,
                        )
                        if recovery_action == "press_enter" and post_bridge_recovery_attempt_count < POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT:
                            post_bridge_recovery_attempt_count += 1
                            post_bridge_recovery_action = recovery_action
                            tmux_submit_enter(tmux_name)
                            last_bridge_activity_at = now
                            next_heartbeat = (
                                now
                                + max(1.0, self._config.stream_heartbeat_interval_sec)
                            )
                            time.sleep(1.0)
                            continue
                        if recovery_action == "typed_continue" and post_bridge_recovery_attempt_count < POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT:
                            post_bridge_recovery_attempt_count += 1
                            post_bridge_recovery_action = recovery_action
                            tmux_type_text_and_submit(
                                tmux_name=tmux_name,
                                text=CODEX_CLI_GOAL_POST_BRIDGE_CONTINUE_PROMPT,
                            )
                            last_bridge_activity_at = now
                            next_heartbeat = (
                                now
                                + max(1.0, self._config.stream_heartbeat_interval_sec)
                            )
                            continue
                        post_bridge_recovery_skip_reason = (
                            codex_cli_tui_post_bridge_recovery_skip_reason(
                                capture,
                                stage=post_bridge_blocker_stage,
                                recovery_action=recovery_action,
                            )
                        )
                        if (
                            not post_bridge_recovery_skip_reason
                            and recovery_action in {"press_enter", "typed_continue"}
                        ):
                            post_bridge_recovery_skip_reason = "retry_limit_reached"
                        tmux_kill_session(tmux_name)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage=post_bridge_blocker_stage,
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            post_bridge_recovery_attempt_count=(
                                pre_bridge_recovery_attempt_count
                                + post_bridge_recovery_attempt_count
                            ),
                            post_bridge_recovery_action=(
                                post_bridge_recovery_action
                                or pre_bridge_recovery_action
                            ),
                            post_bridge_recovery_skip_reason=(
                                post_bridge_recovery_skip_reason
                                or pre_bridge_recovery_skip_reason
                            ),
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_cli_goal_" + post_bridge_blocker_stage
                        )
                    if (
                        task_output_progress_seen
                        and bridge_summary_path is not None
                        and task_output_quiet_timeout_sec > 0
                        and not turn_active
                        and not _bridge_summary_has_inflight_operation(
                            bridge_summary_path
                        )
                        and now - last_task_output_activity_at
                        >= task_output_quiet_timeout_sec
                    ):
                        tmux_kill_session(tmux_name)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage="task_output_quiet_timeout",
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            post_bridge_recovery_attempt_count=(
                                pre_bridge_recovery_attempt_count
                                + post_bridge_recovery_attempt_count
                            ),
                            post_bridge_recovery_action=(
                                post_bridge_recovery_action
                                or pre_bridge_recovery_action
                            ),
                            post_bridge_recovery_skip_reason=(
                                post_bridge_recovery_skip_reason
                                or pre_bridge_recovery_skip_reason
                            ),
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_task_output_quiet_timeout"
                        )
                    if (
                        bridge_activity_seen
                        and bridge_summary_path is not None
                        and bridge_idle_timeout_sec > 0
                        and not _bridge_summary_has_inflight_operation(
                            bridge_summary_path
                        )
                        and now - last_bridge_activity_at >= bridge_idle_timeout_sec
                    ):
                        tmux_kill_session(tmux_name)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        self._publish_codex_cli_goal_trace(
                            ok=False,
                            stage="bridge_idle_timeout",
                            goal_active_observed=goal_active_observed,
                            goal_terminal_observed=goal_terminal_observed,
                            first_action_observed=first_action_seen,
                            bridge_summary_path=bridge_summary_path,
                            thread_prewarm_observed=thread_prewarm_observed,
                            goal_prompt_file_used=goal_prompt_file_used,
                            goal_command_submission_method=(
                                goal_command_submission_method
                            ),
                            post_bridge_recovery_attempt_count=(
                                pre_bridge_recovery_attempt_count
                                + post_bridge_recovery_attempt_count
                            ),
                            post_bridge_recovery_action=(
                                post_bridge_recovery_action
                                or pre_bridge_recovery_action
                            ),
                            post_bridge_recovery_skip_reason=(
                                post_bridge_recovery_skip_reason
                                or pre_bridge_recovery_skip_reason
                            ),
                        )
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_bridge_idle_timeout"
                        )
                    if now >= next_heartbeat:
                        self._write_worker_heartbeat(
                            stdout,
                            session_id=session_id,
                            text="local codex cli /goal still running",
                        )
                        next_heartbeat = (
                            now
                            + max(1.0, self._config.stream_heartbeat_interval_sec)
                        )
                    time.sleep(0.5)
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                self._publish_codex_cli_goal_trace(
                    ok=bool(goal_terminal_observed and not goal_failed_observed),
                    stage=(
                        pre_bridge_terminal_stage
                        or post_bridge_terminal_stage
                        or (
                            "goal_achieved"
                            if goal_terminal_observed and not goal_failed_observed
                            else "goal_failed"
                            if goal_failed_observed
                            else "timeout"
                        )
                    ),
                    goal_active_observed=goal_active_observed,
                    goal_terminal_observed=goal_terminal_observed,
                    first_action_observed=first_action_seen,
                    bridge_summary_path=bridge_summary_path,
                    thread_prewarm_observed=thread_prewarm_observed,
                    goal_prompt_file_used=goal_prompt_file_used,
                    goal_command_submission_method=goal_command_submission_method,
                    goal_kickoff_prompt_submitted=goal_kickoff_prompt_submitted,
                    post_bridge_recovery_attempt_count=(
                        pre_bridge_recovery_attempt_count
                        + post_bridge_recovery_attempt_count
                    ),
                    post_bridge_recovery_action=(
                        post_bridge_recovery_action or pre_bridge_recovery_action
                    ),
                    post_bridge_recovery_skip_reason=(
                        post_bridge_recovery_skip_reason
                        or pre_bridge_recovery_skip_reason
                    ),
                )
                if goal_terminal_observed and not goal_failed_observed:
                    return "codex cli /goal completed"
                if pre_bridge_terminal_stage:
                    return _recoverable_codex_turn_failure_message("codex_cli_goal_" + pre_bridge_terminal_stage)
                if post_bridge_terminal_stage:
                    return _recoverable_codex_turn_failure_message(
                        "codex_cli_goal_" + post_bridge_terminal_stage
                    )
                if goal_failed_observed:
                    return _recoverable_codex_turn_failure_message(
                        "codex_exec_failed"
                    )
                return _recoverable_codex_turn_failure_message("codex_exec_timeout")
            except subprocess.SubprocessError as exc:
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                self._publish_codex_cli_goal_trace(
                    ok=False,
                    stage="tmux_or_input_failed",
                    goal_active_observed=goal_active_observed,
                    goal_terminal_observed=goal_terminal_observed,
                    first_action_observed=first_action_seen,
                    bridge_summary_path=bridge_summary_path,
                    thread_prewarm_observed=False,
                    goal_prompt_file_used=goal_prompt_file_used,
                    goal_command_submission_method=goal_command_submission_method,
                    goal_slash_command_submitted=goal_slash_command_submitted,
                )
                raise RuntimeError("codex cli goal worker failed before run") from exc
            finally:
                tmux_kill_session(tmux_name)
                self._terminate_bridge_server_process(bridge_server_proc)

    def _publish_codex_cli_goal_trace(
        self,
        *,
        ok: bool,
        stage: str,
        goal_active_observed: bool,
        goal_terminal_observed: bool,
        first_action_observed: bool,
        bridge_summary_path: Path | None,
        thread_prewarm_observed: bool = False,
        goal_prompt_file_used: bool = False,
        goal_command_submission_method: str = "",
        goal_slash_command_submitted: bool = True,
        goal_kickoff_prompt_submitted: bool = False,
        post_bridge_recovery_attempt_count: int = 0,
        post_bridge_recovery_action: str = "",
        post_bridge_recovery_skip_reason: str = "",
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        safe_stage = "".join(
            ch if ch.isalnum() or ch == "_" else "_"
            for ch in str(stage or "").strip().lower()
        ) or "unknown"
        private_tui_tail = write_private_codex_cli_goal_tui_tail(self._config.worker_public_trace_dir, safe_stage, getattr(self, "_last_codex_cli_goal_tui_capture", ""))
        bridge_request_count = 0
        task_facing_success_count = 0
        if bridge_summary_path is not None and bridge_summary_path.exists():
            try:
                lines = bridge_summary_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                lines = []
            for line in lines:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if str(record.get("record_phase") or "").lower() == "start":
                    bridge_request_count += 1
                if (
                    str(record.get("record_phase") or "").lower() == "complete"
                    and record.get("task_facing_operation") is True
                    and (record.get("success") is True or record.get("returncode") == 0)
                ):
                    task_facing_success_count += 1
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": bool(ok),
            "route": self._config.route,
            "trace_kind": "codex_cli_goal_tui",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "codex_cli_goal": {
                "schema_version": "skillsbench_codex_cli_goal_tui_v0",
                "stage": safe_stage,
                "goal_slash_command_submitted": bool(goal_slash_command_submitted),
                "goal_thread_prewarm_observed": bool(thread_prewarm_observed),
                "goal_thread_prewarm_timeout_sec": CODEX_CLI_GOAL_THREAD_PREWARM_TIMEOUT_SEC if self._config.codex_cli_goal_thread_prewarm else 0,
                "goal_prompt_file_used": bool(goal_prompt_file_used),
                "goal_prompt_file_raw_path_recorded": False,
                "goal_command_submission_method": str(
                    goal_command_submission_method or ""
                )[:40],
                "goal_active_observed": bool(goal_active_observed),
                "goal_terminal_observed": bool(goal_terminal_observed),
                "goal_kickoff_prompt_submitted": bool(
                    goal_kickoff_prompt_submitted
                ),
                "goal_kickoff_prompt_raw_text_recorded": False,
                **getattr(self, "_last_codex_cli_goal_lifecycle", CodexCliGoalLifecycleGeneration()).trace_fields(),
                "first_action_observed": bool(first_action_observed),
                "bridge_request_count": bridge_request_count,
                "task_facing_success_count": task_facing_success_count,
                "post_bridge_recovery_attempt_count": max(
                    0,
                    int(post_bridge_recovery_attempt_count or 0),
                ),
                "post_bridge_recovery_action": str(
                    post_bridge_recovery_action or ""
                )[:40],
                "post_bridge_recovery_skip_reason": str(
                    post_bridge_recovery_skip_reason or ""
                )[:80],
                "reasoning_effort": str(self._config.reasoning_effort or "")[:40],
                "codex_api_proxy_env_injected": bool(
                    codex_cli_tui_environment(self._config.codex_api_proxy)
                ),
                "codex_api_proxy_raw_url_recorded": False,
                **private_tui_tail,
                "raw_tui_capture_recorded": False,
                "raw_task_text_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "credential_values_recorded": False,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "remote_paths_recorded": False,
                "upload_performed": False,
                "submit_performed": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _terminate_codex_process(
        self,
        proc: subprocess.Popen[str],
        *,
        grace_sec: float = 5.0,
    ) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            try:
                proc.terminate()
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            proc.wait(timeout=grace_sec)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            proc.wait(timeout=grace_sec)
        except subprocess.TimeoutExpired:
            pass

    def _terminate_bridge_server_process(
        self,
        proc: subprocess.Popen[str] | None,
        *,
        grace_sec: float = 2.0,
    ) -> None:
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
        except (ProcessLookupError, PermissionError, OSError):
            return
        try:
            proc.wait(timeout=grace_sec)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            proc.kill()
        except (ProcessLookupError, PermissionError, OSError):
            return
        try:
            proc.wait(timeout=grace_sec)
        except subprocess.TimeoutExpired:
            pass

    def _start_json_file_bridge_server(
        self,
        *,
        tmp_path: Path,
        local_cwd: Path,
        bridge_command: str,
    ) -> tuple[str, subprocess.Popen[str] | None]:
        if not bridge_command or not REVERSE_CHANNEL_BRIDGE_SCRIPT.exists():
            return bridge_command, None
        queue_dir = local_cwd / "loopx-reverse-channel-queue"
        client_path = local_cwd / "loopx-json-file-bridge"
        subprocess.run(
            [
                sys.executable,
                str(REVERSE_CHANNEL_BRIDGE_SCRIPT),
                "write-client",
                "--kind",
                "json-file",
                "--queue-dir",
                str(queue_dir),
                "--output",
                str(client_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        proc = subprocess.Popen(
            [
                sys.executable,
                str(REVERSE_CHANNEL_BRIDGE_SCRIPT),
                "serve-json-file",
                "--queue-dir",
                str(queue_dir),
                "--bridge-command",
                bridge_command,
                "--timeout-sec",
                str(max(1.0, float(self._config.remote_command_file_bridge_timeout_sec))),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(tmp_path),
        )
        return shlex.quote(str(client_path)), proc

    def _consume_remote_bridge_for_solver(self) -> dict[str, Any]:
        return run_skillsbench_remote_command_file_bridge_probe(
            self._config.remote_command_file_bridge_command,
            timeout_sec=self._config.remote_command_file_bridge_timeout_sec,
        )

    def _reverse_channel_json_preflight_probe(self) -> dict[str, Any]:
        return {
            "schema_version": "skillsbench_remote_command_file_bridge_probe_v0",
            "ready": True,
            "first_blocker": "skillsbench_reverse_channel_json_preflight_ready",
            "stage": "pre_sandbox_reverse_channel_json",
            "elapsed_ms": 0,
            "bridge_command_invoked": False,
            "response_schema_version": (
                "skillsbench_reverse_channel_json_preflight_response_v0"
            ),
            "required_operations": ["preflight"],
            "operation_count": 1,
            "operations": [
                {
                    "kind": "preflight",
                    "label": "reverse_channel_json_bridge",
                    "status": "ok",
                }
            ],
            "missing_operations": [],
            "failed_operations": [],
            "boundary_violations": [],
            "raw_command_recorded": False,
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "raw_task_text_recorded": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "remote_paths_recorded": False,
            "upload_performed": False,
            "submit_performed": False,
        }

    def _run_remote_bridge_exec(self, command: str) -> dict[str, Any]:
        bridge_command = self._config.remote_command_file_bridge_command or ""
        request = {
            "operation": "exec",
            "cwd": "/app",
            "command": command,
            "timeout_sec": max(10.0, self._config.remote_command_file_bridge_timeout_sec),
        }
        started = time.monotonic()
        proc = subprocess.run(
            bridge_command,
            input=json.dumps(request),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            timeout=max(10.0, self._config.remote_command_file_bridge_timeout_sec + 5),
            check=False,
        )
        return {
            "returncode": int(proc.returncode),
            "stdout_bytes": len((proc.stdout or "").encode("utf-8")),
            "stderr_bytes": len((proc.stderr or "").encode("utf-8")),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "raw_command_recorded": False,
        }

    def _run_loopx_workflow_lifecycle_checkpoint(
        self,
        *,
        checkpoint_index: int,
    ) -> None:
        case_goal_id = self._config.loopx_case_goal_id or benchmark_case_goal_id(
            self._config.task_id
        )
        case_agent_id = self._config.loopx_case_agent_id or BENCHMARK_CASE_LOOPX_AGENT_ID
        case_todo_id = self._config.loopx_case_todo_id or BENCHMARK_CASE_LOOPX_TODO_ID
        cli_prefix = benchmark_case_loopx_command_prefix(
            case_cli_path=self._config.loopx_case_cli_path,
            case_registry_path=self._config.loopx_case_registry_path,
            case_runtime_root=self._config.loopx_case_runtime_root,
        )
        note = shlex.quote(
            f"workflow driver lifecycle checkpoint {checkpoint_index}"
        )
        evidence = shlex.quote(
            "public-safe orchestrated checkpoint: case-local LoopX state touched"
        )
        commands = [
            (
                "quota should-run",
                "read",
                f"{cli_prefix} quota should-run --goal-id {shlex.quote(case_goal_id)} "
                f"--agent-id {shlex.quote(case_agent_id)} "
                "--runtime-profile outer_controller",
            ),
            (
                "todo claim",
                "write",
                f"{cli_prefix} todo claim --goal-id {shlex.quote(case_goal_id)} "
                f"--todo-id {shlex.quote(case_todo_id)} "
                f"--claimed-by {shlex.quote(case_agent_id)} "
                f"--agent-id {shlex.quote(case_agent_id)}",
            ),
            (
                "todo update",
                "write",
                f"{cli_prefix} todo update --goal-id {shlex.quote(case_goal_id)} "
                f"--todo-id {shlex.quote(case_todo_id)} --status open "
                f"--note {note} --evidence {evidence} "
                f"--claimed-by {shlex.quote(case_agent_id)} "
                f"--agent-id {shlex.quote(case_agent_id)}",
            ),
            (
                "refresh-state",
                "write",
                f"{cli_prefix} refresh-state --goal-id {shlex.quote(case_goal_id)} "
                "--classification benchmark_case_lifecycle_checkpoint "
                "--delivery-batch-scale single_surface "
                "--delivery-outcome surface_only "
                f"--agent-id {shlex.quote(case_agent_id)} "
                "--agent-lane benchmark_case --no-global-sync",
            ),
        ]
        command_results: list[dict[str, Any]] = []
        failures = 0
        for command_name, io_kind, command in commands:
            try:
                result = self._run_remote_bridge_exec(command)
            except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
                result = {
                    "returncode": 124 if isinstance(exc, TimeoutError) else 1,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0,
                    "elapsed_ms": 0,
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_command_recorded": False,
                }
            result["command_name"] = command_name
            result["io_kind"] = io_kind
            command_results.append(result)
            if result.get("returncode") != 0:
                failures += 1
                break
        self._publish_loopx_workflow_lifecycle_checkpoint_trace(
            checkpoint_index=checkpoint_index,
            command_results=command_results,
            failure_count=failures,
        )
        if failures:
            raise RuntimeError("LoopX workflow lifecycle checkpoint failed")

    def _publish_loopx_workflow_lifecycle_checkpoint_trace(
        self,
        *,
        checkpoint_index: int,
        command_results: list[dict[str, Any]],
        failure_count: int,
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        command_counts: dict[str, int] = {}
        returncode_counts: dict[str, int] = {}
        state_read_count = 0
        state_write_count = 0
        for result in command_results:
            name = str(result.get("command_name") or "unknown")[:80]
            command_counts[name] = command_counts.get(name, 0) + 1
            rc = result.get("returncode")
            if isinstance(rc, int) and not isinstance(rc, bool):
                key = str(rc)
            else:
                key = "unknown"
            returncode_counts[key] = returncode_counts.get(key, 0) + 1
            io_kind = result.get("io_kind")
            if io_kind == "read":
                state_read_count += 1
            elif io_kind == "write":
                state_write_count += 1
        raw_material_recorded = any(
            result.get(field) is True
            for result in command_results
            for field in (
                "raw_command_recorded",
                "raw_stdout_recorded",
                "raw_stderr_recorded",
            )
        )
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": failure_count == 0,
            "route": self._config.route,
            "trace_kind": "remote_command_file_bridge_driver_lifecycle_checkpoint",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "remote_command_file_bridge_driver_lifecycle_checkpoint": {
                "schema_version": (
                    "skillsbench_remote_command_file_bridge_driver_lifecycle_v0"
                ),
                "execution_style": "orchestrated_agentloop_loopx_cli",
                "checkpoint_index": checkpoint_index,
                "checkpoint_count": 1,
                "request_count": len(command_results),
                "success_count": len(command_results) - max(0, failure_count),
                "failure_count": max(0, failure_count),
                "loopx_cli_call_count": len(command_results),
                "loopx_state_read_count": state_read_count,
                "loopx_state_write_count": state_write_count,
                "command_counts": dict(sorted(command_counts.items())),
                "returncode_counts": dict(sorted(returncode_counts.items())),
                "raw_material_recorded": raw_material_recorded,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "remote_paths_recorded": False,
                "upload_performed": False,
                "submit_performed": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _prompt_with_remote_bridge_packet(
        self,
        prompt_text: str,
        *,
        bridge_probe: dict[str, Any],
        bridge_command_for_agent: str | None = None,
    ) -> str:
        operation_count = bridge_probe.get("operation_count")
        if not isinstance(operation_count, int) or isinstance(operation_count, bool):
            operation_count = 0
        bridge_command = (
            bridge_command_for_agent
            or self._config.remote_command_file_bridge_command
            or ""
        )
        first_exec_request = json.dumps(
            {
                "operation": "exec",
                "cwd": "/app",
                "command": "pwd && ls -la",
                "timeout_sec": 10,
            },
            separators=(",", ":"),
        )
        first_exec_command = (
            f"printf '%s\\n' {shlex.quote(first_exec_request)} | {bridge_command}"
            if bridge_command
            else (
                "printf '%s\\n' "
                f"{shlex.quote(first_exec_request)} | <private bridge command>"
            )
        )
        packet = f"""

LoopX SkillsBench remote workspace bridge:
- This local Codex process is outside the scored SkillsBench sandbox.
- Use the command below as a private JSON bridge for sandbox exec, file write, file read, and cleanup operations.
- Send one JSON request on stdin and read one private JSON response on stdout.
- FIRST ACTION REQUIRED: before prose planning or final answer, run this exact
  shell command without Markdown backticks; JSON must be piped on stdin:
  ```sh
  {first_exec_command}
  ```
- Invoke additional operations by piping JSON to the bridge; never pass JSON as argv.
- Request examples:
  - {{"operation":"exec","cwd":"/app","command":"pwd","timeout_sec":10}}
  - {{"operation":"read_file","path":"/app/path/to/file","max_bytes":20000}}
  - {{"operation":"write_file","path":"/app/path/to/task-specified-output","content":"..."}}
  - {{"operation":"read_file","path":"/root/task-input-or-data","max_bytes":20000}}
  - {{"operation":"cleanup","path":"/tmp/path/to/temp"}}
- Allowed sandbox path roots are `/app`, `/tmp`, and `/root`; use an absolute
  root only when the task instruction or visible task metadata names it.
{SKILLSBENCH_OUTPUT_PATH_CONTRACT}
- Do not upload, submit, expose credentials, quote the bridge command in final output, or record raw stdout/stderr/task text in public artifacts.
- The bridge readiness probe completed with ready=true and operation_count={operation_count}.
- If a LoopX product-mode lifecycle contract is present later in this prompt,
  execute its case-local LoopX CLI commands through this JSON bridge
  (`operation=exec`, `cwd=/app`) before prose planning or final answer. A
  prose-only response without bridge requests is not a valid product-mode turn.

Private bridge command:
{bridge_command}
""".strip()
        return f"{packet}\n\n{prompt_text}"

    def _write_instrumented_bridge_wrapper(
        self,
        *,
        tmp_path: Path,
        summary_path: Path,
        bridge_command: str | None = None,
    ) -> Path:
        wrapper_path = tmp_path / "loopx-remote-bridge"
        command = bridge_command or self._config.remote_command_file_bridge_command or ""
        script = f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

SUMMARY_PATH = Path({str(summary_path)!r})
BRIDGE_COMMAND = {command!r}
PROBE_REQUEST_SCHEMA_VERSION = "skillsbench_remote_command_file_bridge_probe_request_v0"
PROBE_OPERATION_LABELS = {{
    "bounded_noop_command",
    "probe_marker_write",
    "probe_marker_read",
    "probe_marker_cleanup",
}}
PROBE_PATH_LABELS = {{"bridge_probe_marker"}}
CONTENT_COMPARE_MAX_BYTES = 200_000

{LOOPX_COMMAND_INSTRUMENTATION_SOURCE}
{LOOPX_TODO_OUTPUT_INSTRUMENTATION_SOURCE}

SAFE_LOOPX_TODO_ID_RE = re.compile(r"^todo_[A-Za-z0-9_-]{{6,80}}$")
SAFE_LOOPX_GOAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{{0,120}}$")

def loopx_public_fields(command: str) -> dict[str, str]:
    invocations = loopx_invocation_argvs(command)
    tokens = invocations[0] if invocations else []
    fields: dict[str, str] = {{}}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name = token
        value = ""
        if token.startswith("--") and "=" in token:
            name, value = token.split("=", 1)
        elif token in {{"--goal-id", "--todo-id"}} and i + 1 < len(tokens):
            value = tokens[i + 1]
            i += 1
        if name == "--todo-id" and SAFE_LOOPX_TODO_ID_RE.match(value or ""):
            fields["loopx_todo_id"] = value
        elif name == "--goal-id" and SAFE_LOOPX_GOAL_ID_RE.match(value or ""):
            fields["loopx_goal_id"] = value
        i += 1
    return fields

def private_bridge_probe(request):
    try:
        proc = subprocess.run(
            BRIDGE_COMMAND,
            input=json.dumps(request, separators=(",", ":")),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    try:
        response = json.loads(proc.stdout or "")
    except Exception:
        return None
    return response if isinstance(response, dict) else None

def durable_write_changes_content(payload, request_path):
    content = payload.get("content")
    if not isinstance(content, str):
        return False
    existence = private_bridge_probe({{
        "operation": "exec",
        "cwd": "/app",
        "command": "test -e " + shlex.quote(request_path),
        "timeout_sec": 10,
    }})
    if existence is None:
        return False
    if existence.get("ok") is not True:
        return existence.get("exit_code") == 1
    current = private_bridge_probe({{
        "operation": "read_file",
        "path": request_path,
        "max_bytes": CONTENT_COMPARE_MAX_BYTES,
        "timeout_sec": 30,
    }})
    if current is None or current.get("ok") is not True:
        return False
    current_content = current.get("content")
    if not isinstance(current_content, str):
        return False
    if current.get("content_truncated") is True:
        return not content.startswith(current_content)
    return current_content != content

raw = sys.stdin.read()
record: dict[str, object] = {{
    "schema_version": "skillsbench_remote_bridge_agent_operation_v0",
    "raw_request_recorded": False,
    "raw_stdout_recorded": False,
    "raw_stderr_recorded": False,
    "raw_task_text_recorded": False,
    "credential_values_recorded": False,
    "host_paths_recorded": False,
    "remote_paths_recorded": False,
}}
try:
    payload = json.loads(raw)
except Exception:
    payload = {{}}
operation = payload.get("operation") if isinstance(payload, dict) else ""
record["operation"] = operation if isinstance(operation, str) else "unknown"
operation_label = payload.get("label") if isinstance(payload, dict) else ""
path_label = payload.get("path_label") if isinstance(payload, dict) else ""
if isinstance(operation_label, str) and operation_label:
    record["operation_label"] = operation_label[:80]
if isinstance(path_label, str) and path_label:
    record["path_label"] = path_label[:80]
bridge_probe_operation = bool(
    isinstance(payload, dict)
    and (
        payload.get("schema_version") == PROBE_REQUEST_SCHEMA_VERSION
        or payload.get("probe_id") == "skillsbench_remote_command_file_bridge_probe"
        or (
            isinstance(operation_label, str)
            and operation_label in PROBE_OPERATION_LABELS
        )
        or (isinstance(path_label, str) and path_label in PROBE_PATH_LABELS)
    )
)
subcommands: list[str] = []
loopx_fields: dict[str, str] = {{}}
loopx_invocations = 0
if isinstance(payload, dict) and payload.get("operation") == "exec":
    command_text = payload.get("command")
    if isinstance(command_text, str):
        loopx_invocations = loopx_invocation_count(command_text)
        subcommands = loopx_subcommands(command_text)
        loopx_fields = loopx_public_fields(command_text)
record["loopx_invocation_count"] = loopx_invocations
record["loopx_cli_call"] = loopx_invocations > 0
record["loopx_subcommands"] = subcommands[:2]
record.update(loopx_fields)
record["loopx_state_read"] = subcommands[:2] in (["start-goal"], ["quota", "should-run"], ["status"], ["diagnose"])
record["loopx_state_write"] = bool(subcommands and (
    subcommands[0] in {{"todo", "refresh-state"}}
    or subcommands[:2] == ["quota", "spend-slot"]
))
record["task_facing_operation"] = bool(
    not bridge_probe_operation
    and (
        operation in {{"read_file", "write_file", "cleanup"}}
        or (operation == "exec" and loopx_invocations == 0)
    )
)
request_path = payload.get("path") if isinstance(payload, dict) else ""
durable_task_write = bool(
    operation == "write_file"
    and isinstance(request_path, str)
    and request_path.startswith(("/app/", "/root/"))
    and not request_path.startswith(
        (
            "/app/.loopx/",
            "/app/.codex/",
            "/app/.git/",
            "/app/.cache/",
            "/app/node_modules/",
            "/root/.loopx/",
            "/root/.codex/",
            "/root/.cache/",
            "/root/.local/",
        )
    )
)
record["durable_task_write"] = durable_task_write
record["durable_task_content_changed"] = bool(
    durable_task_write
    and isinstance(payload, dict)
    and durable_write_changes_content(payload, request_path)
)
if durable_task_write:
    record["durable_task_write_root"] = (
        "app" if request_path.startswith("/app/") else "root"
    )
record["bridge_probe_operation"] = bridge_probe_operation
record["operation_observed"] = True

def append_record(item: dict[str, object]) -> None:
    try:
        SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SUMMARY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, sort_keys=True) + "\\n")
    except OSError:
        pass

record["record_phase"] = "start"
append_record(record)
enforce_single_loopx_invocation(loopx_invocations, record, append_record)
proc = subprocess.run(
    BRIDGE_COMMAND,
    input=raw,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=True,
)
complete_record = dict(record)
complete_record["record_phase"] = "complete"
try:
    bridge_response = json.loads(proc.stdout or "")
except Exception:
    bridge_response = {{}}
response_ok = bridge_response.get("ok") if isinstance(bridge_response, dict) else None
response_exit_code = (
    bridge_response.get("exit_code") if isinstance(bridge_response, dict) else None
)
if isinstance(response_ok, bool):
    operation_returncode = (
        response_exit_code
        if isinstance(response_exit_code, int) and not isinstance(response_exit_code, bool)
        else 0 if response_ok else 1
    )
    operation_success = bool(response_ok and operation_returncode == 0)
else:
    operation_returncode = int(proc.returncode)
    operation_success = proc.returncode == 0
complete_record["returncode"] = operation_returncode
complete_record["success"] = operation_success
complete_record["stdout_bytes"] = len((proc.stdout or "").encode("utf-8"))
complete_record["stderr_bytes"] = len((proc.stderr or "").encode("utf-8"))
attach_successful_todo_add_id(complete_record, subcommands, proc.stdout or "")
if proc.returncode != 0:
    stderr_text = proc.stderr or ""
    if int(proc.returncode) < 0:
        complete_record["failure_category"] = "bridge_operation_interrupted"
        complete_record["interrupted"] = True
        complete_record["controller_interrupted"] = True
    elif "PermissionError" in stderr_text or "Operation not permitted" in stderr_text:
        complete_record["failure_category"] = "bridge_client_permission_error"
    elif "No such file or directory" in stderr_text:
        complete_record["failure_category"] = "bridge_command_not_found"
    elif proc.returncode == 255 and BRIDGE_COMMAND.lstrip().startswith("ssh "):
        complete_record["failure_category"] = "bridge_ssh_unavailable"
    else:
        complete_record["failure_category"] = "bridge_command_failed"
elif not operation_success:
    complete_record["failure_category"] = "bridge_operation_failed"
append_record(complete_record)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
raise SystemExit(proc.returncode)
"""
        wrapper_path.write_text(script, encoding="utf-8")
        wrapper_path.chmod(0o700)
        return wrapper_path

    def _publish_remote_bridge_agent_operations_trace(
        self,
        *,
        bridge_summary_path: Path,
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        operation_counts: dict[str, int] = {}
        loopx_subcommand_counts: dict[str, int] = {}
        successful_loopx_subcommand_counts: dict[str, int] = {}
        successful_loopx_command_records: list[dict[str, object]] = []
        returncode_counts: dict[str, int] = {}
        failure_category_counts: dict[str, int] = {}
        request_count = 0
        success_count = 0
        failure_count = 0
        loopx_cli_call_count = 0
        state_read_count = 0
        state_write_count = 0
        task_facing_operation_count = 0
        preflight_success_count = 0
        preflight_failure_count = 0
        task_facing_success_count = 0
        task_facing_failure_count = 0
        probe_operation_count = 0
        inflight_operation_count = 0
        interrupted_operation_count = 0
        task_facing_interrupted_count = 0
        raw_material_recorded = False
        starts = 0
        completions = 0
        if bridge_summary_path.exists():
            for line in bridge_summary_path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                operation = str(record.get("operation") or "unknown")[:40]
                phase = str(record.get("record_phase") or "").strip().lower()
                counts_as_request = phase != "complete"
                counts_as_completion = phase == "complete" or (
                    not phase and ("returncode" in record or "success" in record)
                )
                interrupted_completion = counts_as_completion and _bridge_operation_record_interrupted(record)
                if phase == "complete" and not interrupted_completion:
                    completions += 1
                elif phase == "start" or record.get("operation_observed") is True:
                    starts += 1
                if counts_as_request:
                    request_count += 1
                    operation_counts[operation] = (
                        operation_counts.get(operation, 0) + 1
                    )
                rc = record.get("returncode")
                if counts_as_completion:
                    if isinstance(rc, int) and not isinstance(rc, bool):
                        returncode_counts[str(rc)] = (
                            returncode_counts.get(str(rc), 0) + 1
                        )
                        if interrupted_completion:
                            interrupted_operation_count += 1
                            if record.get("task_facing_operation") is True:
                                task_facing_interrupted_count += 1
                        elif rc == 0:
                            success_count += 1
                            if operation == "preflight":
                                preflight_success_count += 1
                            if record.get("task_facing_operation") is True:
                                task_facing_success_count += 1
                        else:
                            failure_count += 1
                            if operation == "preflight":
                                preflight_failure_count += 1
                            if record.get("task_facing_operation") is True:
                                task_facing_failure_count += 1
                            category = str(
                                record.get("failure_category")
                                or "bridge_command_failed"
                            )[:80]
                            failure_category_counts[category] = (
                                failure_category_counts.get(category, 0) + 1
                            )
                    elif interrupted_completion:
                        interrupted_operation_count += 1
                        if record.get("task_facing_operation") is True:
                            task_facing_interrupted_count += 1
                    elif record.get("success") is True:
                        success_count += 1
                        if operation == "preflight":
                            preflight_success_count += 1
                        if record.get("task_facing_operation") is True:
                            task_facing_success_count += 1
                        returncode_counts["unknown_success"] = (
                            returncode_counts.get("unknown_success", 0) + 1
                        )
                    elif record.get("success") is False:
                        failure_count += 1
                        if operation == "preflight":
                            preflight_failure_count += 1
                        if record.get("task_facing_operation") is True:
                            task_facing_failure_count += 1
                        returncode_counts["unknown_failure"] = (
                            returncode_counts.get("unknown_failure", 0) + 1
                        )
                        category = str(
                            record.get("failure_category") or "bridge_command_failed"
                        )[:80]
                        failure_category_counts[category] = (
                            failure_category_counts.get(category, 0) + 1
                        )
                if counts_as_request and record.get("loopx_cli_call") is True:
                    loopx_cli_call_count += 1
                if counts_as_request and record.get("loopx_state_read") is True:
                    state_read_count += 1
                if counts_as_request and record.get("loopx_state_write") is True:
                    state_write_count += 1
                if counts_as_request and record.get("task_facing_operation") is True:
                    task_facing_operation_count += 1
                if counts_as_request and record.get("bridge_probe_operation") is True:
                    probe_operation_count += 1
                subcommands = record.get("loopx_subcommands")
                if isinstance(subcommands, list) and subcommands:
                    key = " ".join(
                        str(item)
                        for item in subcommands[:2]
                        if re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$", str(item))
                    )
                    if key and counts_as_request:
                        loopx_subcommand_counts[key] = (
                            loopx_subcommand_counts.get(key, 0) + 1
                        )
                    if key and counts_as_completion:
                        if record.get("success") is True or record.get("returncode") == 0:
                            successful_loopx_subcommand_counts[key] = (
                                successful_loopx_subcommand_counts.get(key, 0) + 1
                            )
                            command_record: dict[str, object] = {
                                "subcommand": key,
                            }
                            todo_id = _safe_loopx_todo_id(record.get("loopx_todo_id"))
                            if todo_id:
                                command_record["todo_id"] = todo_id
                            goal_id = _safe_loopx_goal_id(record.get("loopx_goal_id"))
                            if goal_id:
                                command_record["goal_id"] = goal_id
                            if len(successful_loopx_command_records) < 128:
                                successful_loopx_command_records.append(command_record)
                raw_material_recorded = raw_material_recorded or any(
                    record.get(field) is True
                    for field in (
                        "raw_request_recorded",
                        "raw_stdout_recorded",
                        "raw_stderr_recorded",
                        "raw_task_text_recorded",
                        "credential_values_recorded",
                        "host_paths_recorded",
                        "remote_paths_recorded",
                    )
                )
        inflight_operation_count = max(0, starts - completions)
        snapshot_key = str(bridge_summary_path)
        snapshot_id = self._bridge_summary_snapshot_ids.setdefault(
            snapshot_key,
            f"bridge-{uuid.uuid4().hex[:12]}",
        )
        snapshot_index = (
            self._bridge_summary_snapshot_indexes.get(snapshot_key, 0) + 1
        )
        self._bridge_summary_snapshot_indexes[snapshot_key] = snapshot_index
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": True,
            "route": self._config.route,
            "trace_kind": "remote_command_file_bridge_agent_operations",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "remote_command_file_bridge_agent_operations": {
                "schema_version": (
                    "skillsbench_remote_command_file_bridge_agent_operations_v0"
                ),
                "snapshot_id": snapshot_id,
                "snapshot_index": snapshot_index,
                "snapshot_semantics": "cumulative",
                "request_count": request_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "operation_counts": dict(sorted(operation_counts.items())),
                "returncode_counts": dict(sorted(returncode_counts.items())),
                "failure_category_counts": dict(
                    sorted(failure_category_counts.items())
                ),
                "loopx_cli_call_count": loopx_cli_call_count,
                "loopx_cli_subcommand_counts": dict(
                    sorted(loopx_subcommand_counts.items())
                ),
                "successful_loopx_cli_subcommand_counts": dict(
                    sorted(successful_loopx_subcommand_counts.items())
                ),
                "successful_loopx_cli_command_records": (
                    successful_loopx_command_records
                ),
                "loopx_state_read_count": state_read_count,
                "loopx_state_write_count": state_write_count,
                "task_facing_operation_count": task_facing_operation_count,
                "preflight_success_count": preflight_success_count,
                "preflight_failure_count": preflight_failure_count,
                "task_facing_success_count": task_facing_success_count,
                "task_facing_failure_count": task_facing_failure_count,
                "probe_operation_count": probe_operation_count,
                "inflight_operation_count": inflight_operation_count,
                "interrupted_operation_count": interrupted_operation_count,
                "task_facing_interrupted_count": task_facing_interrupted_count,
                "raw_material_recorded": raw_material_recorded,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "remote_paths_recorded": False,
                "upload_performed": False,
                "submit_performed": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _publish_remote_bridge_consumption_trace(
        self,
        bridge_probe: dict[str, Any],
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        operation_count = bridge_probe.get("operation_count")
        if not isinstance(operation_count, int) or isinstance(operation_count, bool):
            operation_count = 0
        boundary = {
            "raw_command_recorded": bridge_probe.get("raw_command_recorded") is True,
            "raw_stdout_recorded": bridge_probe.get("raw_stdout_recorded") is True,
            "raw_stderr_recorded": bridge_probe.get("raw_stderr_recorded") is True,
            "raw_task_text_recorded": bridge_probe.get("raw_task_text_recorded") is True,
            "raw_logs_recorded": bridge_probe.get("raw_logs_recorded") is True,
            "raw_trajectory_recorded": bridge_probe.get("raw_trajectory_recorded") is True,
            "credential_values_recorded": (
                bridge_probe.get("credential_values_recorded") is True
            ),
            "host_paths_recorded": bridge_probe.get("host_paths_recorded") is True,
            "remote_paths_recorded": bridge_probe.get("remote_paths_recorded") is True,
            "upload_performed": bridge_probe.get("upload_performed") is True,
            "submit_performed": bridge_probe.get("submit_performed") is True,
        }
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": bridge_probe.get("ready") is True,
            "route": self._config.route,
            "trace_kind": "remote_command_file_bridge_solver_consumption",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "remote_command_file_bridge": {
                "schema_version": "skillsbench_remote_command_file_bridge_solver_consumption_v0",
                "consumed_by_solver": True,
                "probe_ready": bridge_probe.get("ready") is True,
                "operation_count": operation_count,
                "first_blocker": _public_bridge_label(
                    bridge_probe.get("first_blocker"), limit=120
                ),
                "response_first_blocker": _public_bridge_label(
                    bridge_probe.get("response_first_blocker"), limit=120
                ),
                "stage": _public_bridge_label(bridge_probe.get("stage"), limit=80),
                "bridge_command_invoked": (
                    bridge_probe.get("bridge_command_invoked") is True
                ),
                "bridge_command_recorded": False,
                "required_operations": _public_bridge_label_list(
                    bridge_probe.get("required_operations")
                ),
                "missing_operations": _public_bridge_label_list(
                    bridge_probe.get("missing_operations")
                ),
                "failed_operations": _public_bridge_label_list(
                    bridge_probe.get("failed_operations")
                ),
                "boundary_violations": _public_bridge_label_list(
                    bridge_probe.get("boundary_violations")
                ),
                "operations": _public_bridge_operations(bridge_probe.get("operations")),
            },
            "boundary": boundary,
        }
        response_schema_version = _public_bridge_label(
            bridge_probe.get("response_schema_version"), limit=120
        )
        if response_schema_version:
            trace["remote_command_file_bridge"][
                "response_schema_version"
            ] = response_schema_version
        elapsed_ms = bridge_probe.get("elapsed_ms")
        if isinstance(elapsed_ms, int) and not isinstance(elapsed_ms, bool):
            trace["remote_command_file_bridge"]["elapsed_ms"] = max(
                0, min(elapsed_ms, 600_000)
            )
        self._write_worker_public_trace(trace)

    def _publish_codex_exec_failure_trace(
        self,
        *,
        stage: str,
        returncode: int | None,
        stdout_text: str,
        stderr_text: str,
        final_message_present: bool,
        final_message_bytes: int,
        failure_category: str | None = None,
        recoverable_turn_failure: bool | None = None,
        transport_retry_index: int = 0,
        retry_scheduled: bool = False,
        session_rollover_index: int = 0,
        session_rollover_scheduled: bool = False,
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        safe_stage = "".join(
            ch if ch.isalnum() or ch == "_" else "_"
            for ch in str(stage or "").strip().lower()
        )
        if not safe_stage:
            safe_stage = "codex_exec_failed"
        category = failure_category or _codex_exec_failure_category(
            returncode=returncode,
            stderr_text=stderr_text,
            stdout_text=stdout_text,
        )
        if recoverable_turn_failure is None:
            recoverable_turn_failure = (
                category in RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES
            )
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": False,
            "route": self._config.route,
            "trace_kind": "codex_exec_process_failure",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "codex_exec_process": {
                "schema_version": "skillsbench_codex_exec_process_failure_v0",
                "stage": safe_stage,
                "failure_category": str(category or "codex_exec_failed")[:120],
                "recoverable_turn_failure": recoverable_turn_failure,
                "transport_retry_index": max(0, int(transport_retry_index or 0)),
                "retry_scheduled": bool(retry_scheduled),
                "session_rollover_index": max(
                    0, int(session_rollover_index or 0)
                ),
                "session_rollover_scheduled": bool(session_rollover_scheduled),
                "returncode": (
                    returncode
                    if isinstance(returncode, int)
                    and not isinstance(returncode, bool)
                    else None
                ),
                "stdout_bytes": len((stdout_text or "").encode("utf-8")),
                "stderr_bytes": len((stderr_text or "").encode("utf-8")),
                "final_message_present": bool(final_message_present),
                "final_message_bytes": max(0, int(final_message_bytes or 0)),
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "remote_paths_recorded": False,
                "upload_performed": False,
                "submit_performed": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _publish_codex_exec_session_rollover_trace(
        self,
        *,
        stage: str,
        rollover_index: int,
        resume_failure_count: int,
        previous_thread_present: bool,
        fresh_thread_present: bool,
    ) -> None:
        if not self._config.worker_public_trace_dir:
            return
        safe_stage = str(stage or "failed").strip().lower()
        if safe_stage not in {"completed", "failed"}:
            safe_stage = "failed"
        trace = {
            "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
            "ok": safe_stage == "completed",
            "route": self._config.route,
            "trace_kind": "codex_exec_session_rollover",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "codex_exec_session_rollover": {
                "schema_version": "skillsbench_codex_exec_session_rollover_v0",
                "stage": safe_stage,
                "rollover_index": max(1, int(rollover_index or 1)),
                "resume_failure_count": max(2, int(resume_failure_count or 2)),
                "previous_thread_present": bool(previous_thread_present),
                "fresh_thread_present": bool(fresh_thread_present),
                "shared_sequence_deadline_preserved": True,
                "original_prompt_available_in_private_memory": True,
                "original_prompt_recorded": False,
                "thread_ids_recorded": False,
                "raw_task_text_recorded": False,
            },
            "boundary": {
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "remote_paths_recorded": False,
                "upload_performed": False,
                "submit_performed": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _run_app_server_goal_worker(
        self,
        prompt_text: str,
        *,
        session: dict[str, Any],
        session_id: str,
        stdout: TextIO,
    ) -> str:
        cwd = _safe_cwd(session.get("cwd"), default=os.getcwd())
        self._publish_worker_lifecycle_trace("prompt_received")
        with _temporary_directory_ignore_cleanup_errors(
            prefix="gh-skillsbench-goal-worker-"
        ) as tmp:
            tmp_path = Path(tmp)
            prompt_path = tmp_path / "prompt.txt"
            output_json = tmp_path / "worker.compact.json"
            response_path = tmp_path / "response.txt"
            prompt_for_worker = prompt_text
            bridge_server_proc: subprocess.Popen[str] | None = None
            bridge_summary_path: Path | None = None
            if self._config.remote_command_file_bridge_command:
                if _is_bridge_action_preflight_prompt(prompt_text):
                    bridge_probe = self._reverse_channel_json_preflight_probe()
                else:
                    bridge_probe = self._consume_remote_bridge_for_solver()
                self._publish_remote_bridge_consumption_trace(bridge_probe)
                if bridge_probe.get("ready") is not True:
                    raise RuntimeError("remote command/file bridge probe failed")
                local_cwd = tmp_path / "local-codex-cwd"
                local_cwd.mkdir(parents=True, exist_ok=True)
                cwd = str(local_cwd)
                bridge_summary_path = tmp_path / "remote-bridge-agent-ops.jsonl"
                agent_bridge_command = (
                    self._config.remote_command_file_bridge_agent_command
                    or self._config.remote_command_file_bridge_command
                    or ""
                )
                agent_bridge_command, bridge_server_proc = (
                    self._start_json_file_bridge_server(
                        tmp_path=tmp_path,
                        local_cwd=local_cwd,
                        bridge_command=agent_bridge_command,
                    )
                )
                instrumented_bridge = self._write_instrumented_bridge_wrapper(
                    tmp_path=tmp_path,
                    summary_path=bridge_summary_path,
                    bridge_command=agent_bridge_command,
                )
                prompt_for_worker = self._prompt_with_remote_bridge_packet(
                    prompt_text,
                    bridge_probe=bridge_probe,
                    bridge_command_for_agent=str(instrumented_bridge),
                )
            app_server_goal_prompt_style = _normalized_app_server_goal_prompt_style(
                self._config.app_server_goal_prompt_style
            )
            app_server_goal_closeout_injected = (
                app_server_goal_prompt_style == "native-goal"
            )
            if app_server_goal_closeout_injected:
                prompt_for_worker = _prompt_with_app_server_closeout_instruction(
                    prompt_for_worker
                )
            prompt_path.write_text(prompt_for_worker, encoding="utf-8")
            worker_script = (
                Path(self._config.worker_script).expanduser()
                if self._config.worker_script
                else Path(__file__).resolve().parents[2]
                / "scripts"
                / "skillsbench_host_codex_goal_worker.py"
            )
            worker_first_action_timeout_sec = self._config.first_action_timeout_sec
            cmd = [
                sys.executable,
                str(worker_script),
                "--dataset",
                self._config.dataset,
                "--task-id",
                self._config.task_id,
                "--run-group-id",
                self._config.run_group_id,
                "--job-name",
                self._config.job_name,
                "--rollout-name",
                self._config.rollout_name,
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
                "--first-action-timeout-sec",
                str(worker_first_action_timeout_sec),
                "--normal-followup-max",
                str(max(0, int(self._config.app_server_goal_followup_max or 0))),
                "--app-server-goal-prompt-style",
                app_server_goal_prompt_style,
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
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
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
                bridge_activity_seen = False
                last_bridge_summary_size = 0
                last_bridge_activity_at = time.monotonic()
                bridge_idle_timeout_sec = max(
                    0.0,
                    float(self._config.bridge_idle_timeout_sec or 0.0),
                )
                task_output_quiet_timeout_sec = max(
                    0.0,
                    float(self._config.task_output_quiet_timeout_sec or 0.0),
                )
                bridge_first_action_deadline = 0.0
                if (
                    bridge_summary_path is not None
                    and self._config.first_action_timeout_sec > 0
                ):
                    bridge_first_action_deadline = (
                        time.monotonic()
                        + max(1.0, self._config.first_action_timeout_sec)
                    )
                meaningful_progress_deadline = 0.0
                meaningful_progress_seen = False
                progress_route = self._config.route
                if self._config.app_server_goal_worker and progress_route == "unknown":
                    progress_route = "codex-app-server-goal-baseline"
                meaningful_progress_required = (
                    bridge_summary_path is not None
                    and self._config.first_action_timeout_sec > 0
                    and _prompt_requires_meaningful_bridge_progress(
                        prompt_for_worker,
                        route=progress_route,
                    )
                )
                allow_loopx_closeout_progress = progress_route.startswith("loopx-")
                if meaningful_progress_required:
                    meaningful_progress_deadline = (
                        time.monotonic()
                        + max(1.0, self._config.first_action_timeout_sec)
                    )
                task_output_progress_seen = False
                while proc.poll() is None:
                    now = time.monotonic()
                    if bridge_summary_path is not None:
                        try:
                            current_bridge_summary_size = (
                                bridge_summary_path.stat().st_size
                            )
                        except OSError:
                            current_bridge_summary_size = 0
                        if current_bridge_summary_size > last_bridge_summary_size:
                            last_bridge_summary_size = current_bridge_summary_size
                            last_bridge_activity_at = now
                            bridge_activity_seen = True
                        if not meaningful_progress_seen:
                            meaningful_progress_seen = (
                                _bridge_summary_has_meaningful_agent_progress(
                                    bridge_summary_path,
                                    allow_loopx_closeout=allow_loopx_closeout_progress,
                                )
                            )
                        if (
                            not task_output_progress_seen
                            and task_output_quiet_timeout_sec > 0
                        ):
                            task_output_progress_seen = (
                                _bridge_summary_has_successful_task_operation(
                                    bridge_summary_path
                                )
                            )
                    if (
                        not bridge_activity_seen
                        and bridge_summary_path is not None
                        and bridge_first_action_deadline
                        and now >= bridge_first_action_deadline
                    ):
                        self._terminate_codex_process(proc, grace_sec=2)
                        stdout_text, stderr_text = proc.communicate(timeout=2)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        if not self._publish_worker_trace(output_json):
                            self._publish_worker_failure_trace(
                                stage="first_action_timeout",
                                returncode=proc.returncode,
                                stdout_text=stdout_text,
                                stderr_text="codex_exec_first_action_timeout\n",
                            )
                        self._terminate_bridge_server_process(bridge_server_proc)
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_first_action_timeout"
                        )
                    if (
                        meaningful_progress_required
                        and not meaningful_progress_seen
                        and bridge_summary_path is not None
                        and meaningful_progress_deadline
                        and now >= meaningful_progress_deadline
                    ):
                        self._terminate_codex_process(proc, grace_sec=2)
                        stdout_text, stderr_text = proc.communicate(timeout=2)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        if not self._publish_worker_trace(output_json):
                            self._publish_worker_failure_trace(
                                stage="meaningful_bridge_progress_timeout",
                                returncode=proc.returncode,
                                stdout_text=stdout_text,
                                stderr_text="codex_exec_first_action_timeout\n",
                            )
                        self._terminate_bridge_server_process(bridge_server_proc)
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_first_action_timeout"
                        )
                    if (
                        task_output_progress_seen
                        and bridge_summary_path is not None
                        and task_output_quiet_timeout_sec > 0
                        and not _bridge_summary_has_inflight_operation(
                            bridge_summary_path
                        )
                        and now - last_bridge_activity_at
                        >= task_output_quiet_timeout_sec
                    ):
                        self._terminate_codex_process(proc, grace_sec=2)
                        stdout_text, stderr_text = proc.communicate(timeout=2)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        if not self._publish_worker_trace(output_json):
                            self._publish_worker_failure_trace(
                                stage="task_output_quiet_timeout",
                                returncode=proc.returncode,
                                stdout_text=stdout_text,
                                stderr_text=(
                                    "codex_exec_task_output_quiet_timeout\n"
                                ),
                            )
                        self._terminate_bridge_server_process(bridge_server_proc)
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_task_output_quiet_timeout"
                        )
                    if (
                        bridge_activity_seen
                        and bridge_summary_path is not None
                        and bridge_idle_timeout_sec > 0
                        and not _bridge_summary_has_inflight_operation(
                            bridge_summary_path
                        )
                        and now - last_bridge_activity_at >= bridge_idle_timeout_sec
                    ):
                        self._terminate_codex_process(proc, grace_sec=2)
                        stdout_text, stderr_text = proc.communicate(timeout=2)
                        self._publish_remote_bridge_agent_operations_trace(
                            bridge_summary_path=bridge_summary_path,
                        )
                        if not self._publish_worker_trace(output_json):
                            self._publish_worker_failure_trace(
                                stage="bridge_idle_timeout",
                                returncode=proc.returncode,
                                stdout_text=stdout_text,
                                stderr_text=stderr_text,
                            )
                        self._terminate_bridge_server_process(bridge_server_proc)
                        return _recoverable_codex_turn_failure_message(
                            "codex_exec_bridge_idle_timeout"
                        )
                    if now >= deadline:
                        self._terminate_codex_process(proc, grace_sec=2)
                        stdout_text, stderr_text = proc.communicate(timeout=2)
                        if bridge_summary_path is not None:
                            self._publish_remote_bridge_agent_operations_trace(
                                bridge_summary_path=bridge_summary_path,
                            )
                        if not self._publish_worker_trace(output_json):
                            self._publish_worker_failure_trace(
                                stage="timeout",
                                returncode=proc.returncode,
                                stdout_text=stdout_text,
                                stderr_text=stderr_text,
                            )
                        self._terminate_bridge_server_process(bridge_server_proc)
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
                stdout_text, stderr_text = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired as exc:
                self._terminate_codex_process(proc, grace_sec=2)
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                if not self._publish_worker_trace(output_json):
                    self._publish_worker_failure_trace(
                        stage="communicate_timeout",
                        returncode=proc.returncode,
                        stdout_text="",
                        stderr_text="",
                    )
                self._terminate_bridge_server_process(bridge_server_proc)
                raise TimeoutError from exc
            except BaseException:
                self._terminate_codex_process(proc, grace_sec=2)
                self._terminate_bridge_server_process(bridge_server_proc)
                raise
            if proc.returncode != 0:
                if bridge_summary_path is not None:
                    self._publish_remote_bridge_agent_operations_trace(
                        bridge_summary_path=bridge_summary_path,
                    )
                if not self._publish_worker_trace(output_json):
                    self._publish_worker_failure_trace(
                        stage="worker_exit_nonzero_before_public_trace",
                        returncode=proc.returncode,
                        stdout_text=stdout_text,
                        stderr_text=stderr_text,
                    )
                self._terminate_bridge_server_process(bridge_server_proc)
                raise RuntimeError("host app-server goal worker failed")
            trace_required = bool(self._config.worker_public_trace_dir)
            trace_published = self._publish_worker_trace(output_json)
            if bridge_summary_path is not None:
                self._publish_remote_bridge_agent_operations_trace(
                    bridge_summary_path=bridge_summary_path,
                )
            if trace_required and not trace_published:
                self._publish_worker_failure_trace(
                    stage="worker_exit_zero_before_public_trace",
                    returncode=proc.returncode,
                    stdout_text=stdout_text,
                    stderr_text=stderr_text,
                )
                self._terminate_bridge_server_process(bridge_server_proc)
                raise RuntimeError("host app-server goal worker public trace missing")
            try:
                response = response_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                self._terminate_bridge_server_process(bridge_server_proc)
                raise RuntimeError("host app-server goal worker response missing") from exc
            self._terminate_bridge_server_process(bridge_server_proc)
            return response or "host app-server goal worker returned an empty final message"

    def _publish_worker_trace(self, output_json: Path) -> bool:
        """Persist a public-safe app-server worker trace for the reducer.

        The worker output is already compact, but this method still rewrites a
        smaller allowlisted shape so the benchmark run directory never needs the
        private response text or raw app-server stream.
        """

        if not self._config.worker_public_trace_dir:
            return False
        try:
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False

        def compact_dict(source: Any, allowed: tuple[str, ...]) -> dict[str, Any]:
            if not isinstance(source, dict):
                return {}
            result: dict[str, Any] = {}
            for key in allowed:
                value = source.get(key)
                if isinstance(value, (str, bool, int, float)) and not (
                    isinstance(value, float) and (value != value)
                ):
                    result[key] = value
            return result

        worker_contract = payload.get("worker_contract")
        if not isinstance(worker_contract, dict):
            worker_contract = {}
        worker_adapter = (
            worker_contract.get("worker_adapter")
            if isinstance(worker_contract.get("worker_adapter"), dict)
            else {}
        )
        trace = {
            "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
            "ok": payload.get("ok") is True,
            "route": "codex-app-server-goal-baseline",
            "benchmark_id": str(payload.get("benchmark_id") or ""),
            "task_id": str(payload.get("task_id") or ""),
            "worker_contract": compact_dict(
                worker_contract,
                (
                    "schema_version",
                    "route",
                    "ready",
                    "runner_integration_ready",
                    "first_blocker",
                ),
            ),
            "worker_adapter": compact_dict(
                worker_adapter,
                (
                    "reasoning_effort",
                    "prompt_style",
                    "agent_execution_mode",
                    "worker_surface",
                    "context_only_followup_supported",
                ),
            ),
            "prompt": compact_dict(
                payload.get("prompt"),
                ("sha256", "chars", "raw_recorded", "style"),
            ),
            "turn": compact_dict(
                payload.get("turn"),
                (
                    "schema_version",
                    "thread_id_present",
                    "goal_get_present",
                    "goal_status",
                    "turn_id_present",
                    "turn_id_source",
                    "turn_start_response_turn_id_present",
                    "turn_event_stream_turn_id_present",
                    "turn_status",
                    "turn_completed_observed",
                    "agent_message_delta_count",
                    "agent_message_item_count",
                    "item_completed_count",
                    "assistant_message_present",
                    "assistant_message_chars",
                    "completion_hard_gate",
                    "completion_source_of_truth",
                    "first_action_timeout_sec",
                    "first_action_observed",
                    "effective_action_observed",
                    "assistant_message_context_only",
                    "post_context_assistant_chars",
                    "turn_attempt_count",
                    "turn_completed_attempt_count",
                    "assistant_message_attempt_count",
                    "context_only_turn_count",
                    "context_only_followup_max",
                    "context_only_recovery_attempted",
                    "context_only_recovery_succeeded",
                    "context_only_followup_start_attempted",
                    "context_only_followup_start_succeeded",
                    "context_only_followup_start_error_type",
                    "normal_followup_max",
                    "normal_followup_attempted",
                    "normal_followup_succeeded",
                    "normal_followup_start_attempted_count",
                    "normal_followup_start_succeeded_count",
                    "normal_followup_start_error_type",
                    "transport_reconnect_attempted",
                    "transport_reconnect_succeeded",
                    "transport_reconnect_reason",
                    "goal_reactivation_attempted",
                    "goal_reactivation_succeeded",
                    "goal_reactivation_previous_status",
                    "goal_reactivation_result_status",
                    "reasoning_effort",
                    "raw_transcript_recorded",
                    "raw_assistant_message_recorded",
                ),
            ),
            "context_only_recovery": compact_dict(
                payload.get("context_only_recovery"),
                (
                    "enabled",
                    "max_followups",
                    "attempted",
                    "succeeded",
                    "followup_start_attempted",
                    "followup_start_succeeded",
                    "followup_start_error_type",
                    "context_only_turn_count",
                    "turn_attempt_count",
                ),
            ),
            "normal_followup": compact_dict(
                payload.get("normal_followup"),
                (
                    "enabled",
                    "max_followups",
                    "attempted",
                    "succeeded",
                    "followup_start_attempted_count",
                    "followup_start_succeeded_count",
                    "followup_start_error_type",
                    "turn_attempt_count",
                    "reward_feedback_provided",
                    "verifier_feedback_provided",
                ),
            ),
            "worker_result": compact_dict(
                payload,
                (
                    "ok",
                    "error_type",
                ),
            ),
            "private_response_text": compact_dict(
                payload.get("private_response_text"),
                ("written", "path_recorded", "raw_recorded_in_public_json"),
            ),
            "boundary": compact_dict(
                payload.get("boundary"),
                (
                    "raw_task_text_recorded",
                    "raw_logs_recorded",
                    "raw_trajectory_recorded",
                    "credential_values_recorded",
                    "host_paths_recorded",
                ),
            ),
        }
        self._write_worker_public_trace(trace)
        return True

    def _publish_worker_failure_trace(
        self,
        *,
        stage: str,
        returncode: int | None,
        stdout_text: str,
        stderr_text: str,
    ) -> None:
        """Persist compact failure evidence when the host worker writes no trace."""

        if not self._config.worker_public_trace_dir:
            return
        safe_stage = "".join(
            ch if ch.isalnum() or ch == "_" else "_"
            for ch in str(stage or "").strip().lower()
        )
        if not safe_stage:
            safe_stage = "worker_failed_before_public_trace"
        failure_category = _codex_exec_failure_category(
            returncode=returncode,
            stderr_text=stderr_text,
        )
        trace = {
            "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
            "ok": False,
            "route": "codex-app-server-goal-baseline",
            "trace_kind": "host_worker_process_failure",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "worker_process": {
                "schema_version": "skillsbench_host_worker_process_failure_v0",
                "stage": safe_stage,
                "failure_category": failure_category,
                "returncode": returncode
                if isinstance(returncode, int) and not isinstance(returncode, bool)
                else None,
                "stdout_bytes": len((stdout_text or "").encode("utf-8")),
                "stderr_bytes": len((stderr_text or "").encode("utf-8")),
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "host_paths_recorded": False,
            },
            "worker_contract": {
                "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                "route": "codex-app-server-goal-baseline",
                "ready": False,
                "runner_integration_ready": True,
                "first_blocker": safe_stage,
            },
            "prompt": {"raw_recorded": False},
            "turn": {
                "thread_id_present": False,
                "goal_get_present": False,
                "turn_id_present": False,
                "turn_completed_observed": False,
                "assistant_message_present": False,
                "raw_transcript_recorded": False,
                "raw_assistant_message_recorded": False,
            },
            "private_response_text": {
                "written": False,
                "path_recorded": False,
                "raw_recorded_in_public_json": False,
            },
            "boundary": {
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _publish_worker_lifecycle_trace(self, stage: str) -> None:
        """Record public-safe relay lifecycle evidence before any prompt runs."""

        if (
            not self._config.app_server_goal_worker
            or not self._config.worker_public_trace_dir
        ):
            return
        safe_stage = "".join(
            ch if ch.isalnum() or ch == "_" else "_"
            for ch in str(stage or "").strip().lower()
        )
        if not safe_stage:
            safe_stage = "unknown"
        if safe_stage in self._published_lifecycle_stages:
            return
        self._published_lifecycle_stages.add(safe_stage)
        trace = {
            "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
            "ok": False,
            "route": "codex-app-server-goal-baseline",
            "trace_kind": "relay_lifecycle",
            "benchmark_id": self._config.dataset,
            "task_id": self._config.task_id,
            "relay": {
                "schema_version": "skillsbench_app_server_goal_worker_lifecycle_trace_v0",
                "stage": safe_stage,
                "app_server_goal_worker": True,
                "worker_public_trace_configured": True,
                "raw_prompt_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "host_paths_recorded": False,
            },
            "worker_contract": {
                "schema_version": "skillsbench_app_server_goal_worker_contract_v0",
                "route": "codex-app-server-goal-baseline",
                "ready": False,
                "runner_integration_ready": True,
                "first_blocker": "relay_lifecycle_only_no_worker_turn_yet",
            },
            "prompt": {"raw_recorded": False},
            "turn": {
                "thread_id_present": False,
                "goal_get_present": False,
                "turn_id_present": False,
                "turn_completed_observed": False,
                "assistant_message_present": False,
                "raw_transcript_recorded": False,
                "raw_assistant_message_recorded": False,
            },
            "private_response_text": {
                "written": False,
                "path_recorded": False,
                "raw_recorded_in_public_json": False,
            },
            "boundary": {
                "raw_task_text_recorded": False,
                "raw_logs_recorded": False,
                "raw_trajectory_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
            },
        }
        self._write_worker_public_trace(trace)

    def _write_worker_public_trace(self, trace: dict[str, Any]) -> None:
        if not self._config.worker_public_trace_dir:
            return
        try:
            trace_dir = Path(self._config.worker_public_trace_dir).expanduser()
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace_path = trace_dir / f"worker-{uuid.uuid4().hex[:12]}.compact.json"
            trace_path.write_text(
                json.dumps(trace, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return

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
    prompt_text: str | None = None,
    required_response_marker: str | None = None,
    model_id: str | None = "probe-model",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    argv = (
        _command_to_argv(command)
        if command
        else default_skillsbench_local_acp_relay_command()
    )
    started = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
    stage = "spawn"
    request_count = 0
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=({**os.environ, **env} if env else None),
        )
        stage = "initialize"
        initialize = _probe_request(
            proc,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            timeout_at=started + timeout_sec,
        )
        request_count += 1
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
        request_count += 1
        session_id = str(session.get("result", {}).get("sessionId") or "")
        next_id = 3
        if model_id:
            stage = "set_model"
            _probe_request(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "session/set_model",
                    "params": {"sessionId": session_id, "modelId": str(model_id)},
                },
                timeout_at=started + timeout_sec,
            )
            request_count += 1
            next_id += 1
        stage = "prompt"
        agent_message_chunks: list[str] = []
        prompt = _probe_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [
                        {
                            "type": "text",
                            "text": (
                                prompt_text
                                or SKILLSBENCH_LOCAL_ACP_RELAY_HEALTH_PROMPT
                            ),
                        }
                    ],
                },
            },
            timeout_at=started + timeout_sec,
            agent_message_chunks=agent_message_chunks,
        )
        request_count += 1
        prompt_usage = (
            prompt.get("result", {}).get("usage")
            if isinstance(prompt.get("result"), dict)
            else {}
        )
        usage_total = (
            prompt_usage.get("totalTokens") if isinstance(prompt_usage, dict) else None
        )
        usage_ready = isinstance(usage_total, int) and not isinstance(
            usage_total, bool
        ) and usage_total > 0
        agent_message_present = bool("".join(agent_message_chunks).strip())
        response_marker_observed = True
        if required_response_marker:
            response_marker_observed = (
                required_response_marker in "".join(agent_message_chunks)
            )
        ready = (
            initialize.get("result", {}).get("agentInfo", {}).get("name")
            == "loopx-skillsbench-local-acp-relay"
            and bool(session_id)
            and prompt.get("result", {}).get("stopReason") == "end_turn"
            and usage_ready
            and response_marker_observed
        )
        first_blocker = "skillsbench_local_acp_relay_ready"
        if not ready:
            first_blocker = "skillsbench_local_acp_relay_probe_failed"
            if required_response_marker and not response_marker_observed:
                first_blocker = "skillsbench_local_acp_relay_response_marker_missing"
        return _relay_probe_payload(
            ready=ready,
            first_blocker=first_blocker,
            stage="complete",
            request_count=request_count,
            prompt_usage_total_tokens=usage_total if usage_ready else 0,
            response_marker_required=bool(required_response_marker),
            response_marker_observed=response_marker_observed,
            agent_message_present=agent_message_present,
        )
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError):
        return _relay_probe_payload(
            ready=False,
            first_blocker=f"skillsbench_local_acp_relay_{stage}_failed",
            stage=stage,
            request_count=0,
            prompt_usage_total_tokens=0,
            response_marker_required=bool(required_response_marker),
            response_marker_observed=False,
            agent_message_present=False,
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
                prompt = await step(
                    "prompt",
                    client.prompt(SKILLSBENCH_LOCAL_ACP_RELAY_HEALTH_PROMPT),
                )
                request_count += 1
                agent_name = str(getattr(initialize.agent_info, "name", "") or "")
                session_id = str(getattr(session, "session_id", "") or "")
                stop_reason = str(getattr(prompt, "stop_reason", "") or "")
                ready = (
                    agent_name == "loopx-skillsbench-local-acp-relay"
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
    agent_message_chunks: list[str] | None = None,
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
                    agent_message_chunks is not None
                    and isinstance(decoded, dict)
                    and decoded.get("jsonrpc") == "2.0"
                    and decoded.get("method") == "session/update"
                ):
                    params = decoded.get("params")
                    update = (
                        params.get("update") if isinstance(params, dict) else None
                    )
                    content = (
                        update.get("content") if isinstance(update, dict) else None
                    )
                    text = content.get("text") if isinstance(content, dict) else None
                    if isinstance(text, str):
                        agent_message_chunks.append(text)
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
    prompt_usage_total_tokens: int = 0,
    response_marker_required: bool = False,
    response_marker_observed: bool = True,
    agent_message_present: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION,
        "ready": ready,
        "first_blocker": first_blocker,
        "stage": stage,
        "request_count": request_count,
        "prompt_usage_total_tokens": max(0, int(prompt_usage_total_tokens or 0)),
        "response_marker_required": bool(response_marker_required),
        "response_marker_observed": bool(response_marker_observed),
        "agent_message_present": bool(agent_message_present),
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
