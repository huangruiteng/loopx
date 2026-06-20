from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


CODEX_APP_SERVER_GOAL_BASELINE_SCHEMA_VERSION = (
    "codex_app_server_goal_baseline_v0"
)
CODEX_APP_SERVER_GOAL_BASELINE_PROOF_SCHEMA_VERSION = (
    "codex_app_server_goal_baseline_proof_v0"
)
CODEX_APP_SERVER_GOAL_WORKER_SCHEMA_VERSION = "codex_app_server_goal_worker_v0"
CODEX_APP_SERVER_GOAL_WORKER_PROOF_SCHEMA_VERSION = (
    "codex_app_server_goal_worker_proof_v0"
)
DEFAULT_CODEX_GOAL_BASELINE_CLIENT_NAME = "goal_harness_benchmark_goal_baseline"
DEFAULT_CODEX_GOAL_BASELINE_CLIENT_TITLE = "Goal Harness Benchmark Goal Baseline"
DEFAULT_CODEX_GOAL_BASELINE_CLIENT_VERSION = "0.1.0"
CODEX_APP_SERVER_GOAL_METHODS = (
    "initialize",
    "thread/start",
    "thread/goal/set",
    "thread/goal/get",
)
CODEX_APP_SERVER_GOAL_WORKER_METHODS = (
    *CODEX_APP_SERVER_GOAL_METHODS,
    "turn/start",
)


class CodexAppServerGoalProbeError(RuntimeError):
    """Raised when an optional real Codex app-server goal probe fails."""


def stable_text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_codex_app_server_goal_baseline_plan(
    *,
    objective: str,
    cwd: str = "<benchmark-workspace>",
    sandbox: str = "workspace-write",
    approval_policy: str = "never",
    status: str = "active",
    token_budget: int | None = None,
    client_name: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_NAME,
    client_title: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_TITLE,
    client_version: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_VERSION,
) -> dict[str, Any]:
    """Describe the supported Codex Goal baseline app-server message seam.

    The returned object is a public-safe command contract, not a live benchmark
    launch. It keeps the benchmark-facing baseline honest: `codex exec` may be
    used as a connectivity smoke, but the paired baseline needs persistent
    `thread/goal/set` plus `thread/goal/get` evidence.
    """

    objective_text = str(objective or "").strip()
    if not objective_text:
        raise ValueError("objective must be non-empty")
    if status not in {"active", "paused", "budgetLimited", "complete"}:
        raise ValueError(f"unsupported Codex Goal status: {status}")

    initialize = {
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": client_name,
                "title": client_title,
                "version": client_version,
            },
            "capabilities": {"experimentalApi": True},
        },
    }
    initialized = {"method": "initialized", "params": {}}
    thread_start = {
        "id": 2,
        "method": "thread/start",
        "params": {
            "cwd": cwd,
            "sandbox": sandbox,
            "approvalPolicy": approval_policy,
        },
    }
    goal_set_params: dict[str, Any] = {
        "threadId": "<thread-id>",
        "objective": objective_text,
        "status": status,
    }
    if token_budget is not None:
        goal_set_params["tokenBudget"] = int(token_budget)
    goal_set = {"id": 3, "method": "thread/goal/set", "params": goal_set_params}
    goal_get = {
        "id": 4,
        "method": "thread/goal/get",
        "params": {"threadId": "<thread-id>"},
    }

    return {
        "schema_version": CODEX_APP_SERVER_GOAL_BASELINE_SCHEMA_VERSION,
        "surface": "codex_app_server",
        "baseline_mode": "codex_goal_mode",
        "requires_experimental_api": True,
        "methods": list(CODEX_APP_SERVER_GOAL_METHODS),
        "objective_sha256": stable_text_digest(objective_text),
        "objective_chars": len(objective_text),
        "status": status,
        "token_budget_present": token_budget is not None,
        "connectivity_smoke": {
            "codex_exec_allowed": True,
            "codex_exec_is_goal_baseline": False,
        },
        "manual_fallback": {
            "surface": "interactive_cli_slash_goal",
            "must_be_labeled_manual_or_pty_fallback": True,
        },
        "messages": {
            "initialize": initialize,
            "initialized": initialized,
            "thread_start": thread_start,
            "thread_goal_set": goal_set,
            "thread_goal_get": goal_get,
        },
        "claim_boundary": {
            "requires_thread_goal_get_evidence": True,
            "slash_prefix_prompt_is_unverified": True,
            "polling_loop_is_unverified": True,
            "must_not_include_goal_harness_state": True,
        },
    }


def build_codex_app_server_goal_worker_plan(
    *,
    objective: str,
    task_instruction: str,
    cwd: str = "<benchmark-workspace>",
    sandbox: str = "workspace-write",
    approval_policy: str = "never",
    status: str = "active",
    token_budget: int | None = None,
    model: str | None = None,
    effort: str | None = None,
    client_name: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_NAME,
    client_title: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_TITLE,
    client_version: str = DEFAULT_CODEX_GOAL_BASELINE_CLIENT_VERSION,
) -> dict[str, Any]:
    """Describe the app-server Goal worker path used by benchmark launches.

    This is still a compact control contract, not a benchmark result. A scored
    baseline needs both persistent Goal proof and `turn/start` proof for the
    benchmark task inside the case launch.
    """

    task_text = str(task_instruction or "").strip()
    if not task_text:
        raise ValueError("task_instruction must be non-empty")

    plan = build_codex_app_server_goal_baseline_plan(
        objective=objective,
        cwd=cwd,
        sandbox=sandbox,
        approval_policy=approval_policy,
        status=status,
        token_budget=token_budget,
        client_name=client_name,
        client_title=client_title,
        client_version=client_version,
    )
    turn_start_params: dict[str, Any] = {
        "threadId": "<thread-id>",
        "input": [{"type": "text", "text": task_text}],
        "cwd": cwd,
        "approvalPolicy": approval_policy,
    }
    if model:
        turn_start_params["model"] = str(model)
    if effort:
        turn_start_params["effort"] = str(effort)

    worker_messages = dict(plan["messages"])
    worker_messages["turn_start"] = {
        "id": 5,
        "method": "turn/start",
        "params": turn_start_params,
    }

    return {
        **plan,
        "schema_version": CODEX_APP_SERVER_GOAL_WORKER_SCHEMA_VERSION,
        "worker_mode": "codex_app_server_goal_turn",
        "methods": list(CODEX_APP_SERVER_GOAL_WORKER_METHODS),
        "task_instruction_sha256": stable_text_digest(task_text),
        "task_instruction_chars": len(task_text),
        "messages": worker_messages,
        "claim_boundary": {
            **plan["claim_boundary"],
            "requires_turn_start_evidence": True,
            "turn_start_input_must_match_task": True,
        },
    }


def _goal_from_response(response: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    goal = response.get("goal")
    return goal if isinstance(goal, dict) else {}


def _turn_from_response(response: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    turn = response.get("turn")
    return turn if isinstance(turn, dict) else {}


def _turn_start_input_text(request: dict[str, Any] | None) -> str:
    if not isinstance(request, dict):
        return ""
    params = request.get("params")
    if not isinstance(params, dict):
        return ""
    inputs = params.get("input")
    if not isinstance(inputs, list):
        return ""
    texts: list[str] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            texts.append(item["text"])
    return "\n".join(texts).strip()


def _turn_start_thread_id(request: dict[str, Any] | None) -> str:
    if not isinstance(request, dict):
        return ""
    params = request.get("params")
    if not isinstance(params, dict):
        return ""
    return str(params.get("threadId") or "")


def compact_goal(goal: dict[str, Any]) -> dict[str, Any]:
    objective = str(goal.get("objective") or "")
    status = str(goal.get("status") or "")
    return {
        "thread_id_present": bool(goal.get("threadId")),
        "objective_sha256": stable_text_digest(objective) if objective else None,
        "objective_chars": len(objective),
        "status": status or None,
        "token_budget_present": goal.get("tokenBudget") is not None,
        "tokens_used": goal.get("tokensUsed"),
        "time_used_seconds": goal.get("timeUsedSeconds"),
    }


def compact_turn(turn: dict[str, Any]) -> dict[str, Any]:
    status = str(turn.get("status") or "")
    return {
        "turn_id_present": bool(turn.get("id")),
        "status": status or None,
        "items_count": len(turn.get("items") or [])
        if isinstance(turn.get("items"), list)
        else None,
        "started_at_present": turn.get("startedAt") is not None,
        "completed_at_present": turn.get("completedAt") is not None,
        "error_present": turn.get("error") is not None,
    }


def build_codex_app_server_goal_baseline_proof(
    *,
    set_response: dict[str, Any] | None,
    get_response: dict[str, Any] | None,
    expected_objective: str | None = None,
    expected_status: str = "active",
    notifications: list[str] | None = None,
    used_codex_exec: bool = False,
    used_slash_prefix_prompt: bool = False,
    included_goal_harness_state: bool = False,
    raw_paths_recorded: bool = False,
    raw_transcript_recorded: bool = False,
    credentials_read_or_recorded: bool = False,
) -> dict[str, Any]:
    """Reduce app-server Goal responses into public-safe baseline evidence."""

    set_goal = _goal_from_response(set_response)
    get_goal = _goal_from_response(get_response)
    set_objective = str(set_goal.get("objective") or "")
    get_objective = str(get_goal.get("objective") or "")
    expected = str(expected_objective or set_objective or get_objective)

    thread_matches = bool(set_goal.get("threadId")) and (
        set_goal.get("threadId") == get_goal.get("threadId")
    )
    objective_matches = bool(expected) and set_objective == get_objective == expected
    status_matches = str(get_goal.get("status") or "") == expected_status
    persistent_goal_evidence = bool(
        thread_matches
        and objective_matches
        and status_matches
        and get_goal.get("threadId")
    )
    unsupported_shortcut_used = bool(used_codex_exec or used_slash_prefix_prompt)
    private_boundary_clean = not any(
        [
            included_goal_harness_state,
            raw_paths_recorded,
            raw_transcript_recorded,
            credentials_read_or_recorded,
        ]
    )
    baseline_claim_allowed = bool(
        persistent_goal_evidence
        and not unsupported_shortcut_used
        and private_boundary_clean
    )

    return {
        "schema_version": CODEX_APP_SERVER_GOAL_BASELINE_PROOF_SCHEMA_VERSION,
        "surface": "codex_app_server",
        "baseline_mode": "codex_goal_mode",
        "persistent_goal_evidence": persistent_goal_evidence,
        "baseline_claim_allowed": baseline_claim_allowed,
        "required_methods_observed": {
            "thread_goal_set": bool(set_goal),
            "thread_goal_get": bool(get_goal),
        },
        "matches": {
            "thread": thread_matches,
            "objective": objective_matches,
            "status": status_matches,
        },
        "set_goal": compact_goal(set_goal),
        "get_goal": compact_goal(get_goal),
        "notifications": sorted(set(notifications or [])),
        "negative_controls": {
            "codex_exec_only": bool(used_codex_exec),
            "slash_prefix_prompt_only": bool(used_slash_prefix_prompt),
            "included_goal_harness_state": bool(included_goal_harness_state),
        },
        "read_boundary": {
            "raw_paths_recorded": bool(raw_paths_recorded),
            "raw_transcript_recorded": bool(raw_transcript_recorded),
            "credentials_read_or_recorded": bool(credentials_read_or_recorded),
        },
    }


def build_codex_app_server_goal_worker_proof(
    *,
    set_response: dict[str, Any] | None,
    get_response: dict[str, Any] | None,
    turn_start_request: dict[str, Any] | None,
    turn_start_response: dict[str, Any] | None,
    expected_objective: str | None = None,
    expected_task_instruction: str | None = None,
    expected_status: str = "active",
    notifications: list[str] | None = None,
    used_codex_exec: bool = False,
    used_slash_prefix_prompt: bool = False,
    included_goal_harness_state: bool = False,
    raw_paths_recorded: bool = False,
    raw_transcript_recorded: bool = False,
    credentials_read_or_recorded: bool = False,
) -> dict[str, Any]:
    """Reduce app-server Goal plus turn-start responses into worker evidence."""

    baseline = build_codex_app_server_goal_baseline_proof(
        set_response=set_response,
        get_response=get_response,
        expected_objective=expected_objective,
        expected_status=expected_status,
        notifications=notifications,
        used_codex_exec=used_codex_exec,
        used_slash_prefix_prompt=used_slash_prefix_prompt,
        included_goal_harness_state=included_goal_harness_state,
        raw_paths_recorded=raw_paths_recorded,
        raw_transcript_recorded=raw_transcript_recorded,
        credentials_read_or_recorded=credentials_read_or_recorded,
    )
    set_goal = _goal_from_response(set_response)
    turn = _turn_from_response(turn_start_response)
    request_thread_id = _turn_start_thread_id(turn_start_request)
    goal_thread_id = str(set_goal.get("threadId") or "")
    task_text = _turn_start_input_text(turn_start_request)
    expected_task = str(expected_task_instruction or "").strip()
    task_matches = bool(task_text) and (
        not expected_task or task_text == expected_task
    )
    thread_matches = bool(goal_thread_id) and request_thread_id == goal_thread_id
    turn_started = bool(turn.get("id")) and bool(str(turn.get("status") or ""))
    worker_claim_allowed = bool(
        baseline.get("baseline_claim_allowed")
        and thread_matches
        and task_matches
        and turn_started
    )

    return {
        "schema_version": CODEX_APP_SERVER_GOAL_WORKER_PROOF_SCHEMA_VERSION,
        "surface": "codex_app_server",
        "baseline_mode": "codex_goal_mode",
        "worker_mode": "codex_app_server_goal_turn",
        "persistent_goal_evidence": bool(baseline.get("persistent_goal_evidence")),
        "turn_start_evidence": bool(turn_started),
        "baseline_claim_allowed": worker_claim_allowed,
        "required_methods_observed": {
            **baseline.get("required_methods_observed", {}),
            "turn_start": bool(turn_started),
        },
        "matches": {
            **baseline.get("matches", {}),
            "turn_thread": thread_matches,
            "task_instruction": task_matches,
        },
        "set_goal": baseline.get("set_goal", {}),
        "get_goal": baseline.get("get_goal", {}),
        "turn": compact_turn(turn),
        "task_instruction": {
            "present": bool(task_text),
            "sha256": stable_text_digest(task_text) if task_text else None,
            "chars": len(task_text),
            "raw_recorded": False,
        },
        "notifications": baseline.get("notifications", []),
        "negative_controls": baseline.get("negative_controls", {}),
        "read_boundary": baseline.get("read_boundary", {}),
    }


def _reader_thread(stream: Any, out: "queue.Queue[dict[str, Any] | Exception]") -> None:
    try:
        for line in stream:
            if not line:
                continue
            try:
                out.put(json.loads(line))
            except Exception as exc:  # pragma: no cover - defensive optional path
                out.put(exc)
    finally:
        out.put(EOFError("codex app-server stream closed"))


def _send_json(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise CodexAppServerGoalProbeError("codex app-server stdin is closed")
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _wait_for_response(
    proc: subprocess.Popen[str],
    responses: "queue.Queue[dict[str, Any] | Exception]",
    request_id: int,
    *,
    notifications: list[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            msg = responses.get(timeout=max(0.1, min(0.5, deadline - time.monotonic())))
        except queue.Empty:
            continue
        if isinstance(msg, EOFError):
            raise CodexAppServerGoalProbeError("codex app-server exited before response")
        if isinstance(msg, Exception):
            raise CodexAppServerGoalProbeError(str(msg))
        method = msg.get("method")
        if method:
            notifications.append(str(method))
            continue
        if msg.get("id") == request_id:
            if msg.get("error"):
                raise CodexAppServerGoalProbeError(json.dumps(msg["error"], sort_keys=True))
            result = msg.get("result")
            return result if isinstance(result, dict) else {}
    raise CodexAppServerGoalProbeError(f"timed out waiting for response id={request_id}")


def run_isolated_codex_app_server_goal_probe(
    *,
    objective: str,
    codex_bin: str = "codex",
    status: str = "paused",
    sandbox: str = "read-only",
    approval_policy: str = "never",
    token_budget: int | None = 1,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Optionally prove the app-server Goal seam against a real local Codex CLI.

    This helper intentionally uses an isolated HOME/CODEX_HOME and records only
    compact public-safe evidence. The default status is `paused` so the probe
    verifies persistence without starting a delivery turn.
    """

    plan = build_codex_app_server_goal_baseline_plan(
        objective=objective,
        cwd="<isolated-temp-project>",
        sandbox=sandbox,
        approval_policy=approval_policy,
        status=status,
        token_budget=token_budget,
    )
    with tempfile.TemporaryDirectory(prefix="goal-harness-codex-goal-") as tmp:
        root = Path(tmp)
        home = root / "home"
        codex_home = root / "codex"
        project = root / "project"
        home.mkdir()
        codex_home.mkdir()
        project.mkdir()
        (project / ".gitkeep").write_text("", encoding="utf-8")

        env = dict(os.environ)
        env["HOME"] = str(home)
        env["CODEX_HOME"] = str(codex_home)
        proc = subprocess.Popen(
            [codex_bin, "app-server", "--listen", "stdio://", "--enable", "goals"],
            cwd=str(project),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        notifications: list[str] = []
        responses: "queue.Queue[dict[str, Any] | Exception]" = queue.Queue()
        assert proc.stdout is not None
        thread = threading.Thread(target=_reader_thread, args=(proc.stdout, responses))
        thread.daemon = True
        thread.start()
        try:
            initialize = plan["messages"]["initialize"]
            _send_json(proc, initialize)
            _wait_for_response(
                proc,
                responses,
                int(initialize["id"]),
                notifications=notifications,
                timeout_seconds=timeout_seconds,
            )
            _send_json(proc, plan["messages"]["initialized"])

            thread_start = dict(plan["messages"]["thread_start"])
            thread_start["params"] = dict(thread_start["params"])
            thread_start["params"]["cwd"] = str(project)
            _send_json(proc, thread_start)
            thread_result = _wait_for_response(
                proc,
                responses,
                int(thread_start["id"]),
                notifications=notifications,
                timeout_seconds=timeout_seconds,
            )
            thread_id = str(((thread_result.get("thread") or {}).get("id")) or "")
            if not thread_id:
                raise CodexAppServerGoalProbeError("thread/start did not return thread id")

            goal_set = dict(plan["messages"]["thread_goal_set"])
            goal_set["params"] = dict(goal_set["params"])
            goal_set["params"]["threadId"] = thread_id
            _send_json(proc, goal_set)
            set_response = _wait_for_response(
                proc,
                responses,
                int(goal_set["id"]),
                notifications=notifications,
                timeout_seconds=timeout_seconds,
            )

            goal_get = dict(plan["messages"]["thread_goal_get"])
            goal_get["params"] = dict(goal_get["params"])
            goal_get["params"]["threadId"] = thread_id
            _send_json(proc, goal_get)
            get_response = _wait_for_response(
                proc,
                responses,
                int(goal_get["id"]),
                notifications=notifications,
                timeout_seconds=timeout_seconds,
            )
            proof = build_codex_app_server_goal_baseline_proof(
                set_response=set_response,
                get_response=get_response,
                expected_objective=objective,
                expected_status=status,
                notifications=notifications,
            )
            return {
                "schema_version": CODEX_APP_SERVER_GOAL_BASELINE_PROOF_SCHEMA_VERSION,
                "real_codex_app_server": True,
                "isolated_home": True,
                "isolated_codex_home": True,
                "temp_paths_recorded": False,
                "requested_status": status,
                "proof": proof,
            }
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive optional path
                proc.kill()
