#!/usr/bin/env python3
"""Run the ssh-goal treatment on the native Codex app-server Goal surface.

The LoopX toolkit owns the JSON-RPC transaction and event reducer.  This
runner only adds the benchmark-host action that wen performs when a Goal is
blocked: clear the waiting gate and start the next turn on the existing thread.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

from native_codex_goal import (
    NativeGoalConfig,
    NativeGoalProtocolError,
    StdioNativeGoalTransport,
    compact_native_goal_receipt,
    probe_native_goal_process,
    observe_native_goal_event,
    refresh_native_goal_status,
    start_native_goal_turn,
)
from workspace_delivery import head_sha, normalize_delivery, write_receipt


def _restart_turn_same_thread(transport, config, turn, instruction=None):
    result = transport.request(
        "turn/start",
        {
            "threadId": turn.thread_id,
            "input": [{"type": "text", "text": instruction or config.task_instruction}],
            "cwd": config.cwd,
            "approvalPolicy": config.approval_policy,
            **({"model": config.model} if config.model else {}),
            **({"effort": config.effort} if config.effort else {}),
            **(
                {"sandboxPolicy": dict(config.sandbox_policy)}
                if config.sandbox_policy is not None
                else {}
            ),
        },
    )
    turn.methods.append("turn/start")
    nested = result.get("turn")
    nested = nested if isinstance(nested, dict) else {}
    turn_id = str(nested.get("id") or result.get("turnId") or "")
    if not turn_id:
        raise NativeGoalProtocolError("turn_start_id_missing")
    turn.turn_id = turn_id
    turn.response_turn_id = turn_id
    turn.turn_status = str(nested.get("status") or "accepted")
    return turn


def _reactivate_goal(transport, config, turn) -> None:
    payload = {
        "threadId": turn.thread_id,
        "objective": config.objective,
        "status": "active",
    }
    if config.token_budget is not None:
        payload["tokenBudget"] = config.token_budget
    transport.request("thread/goal/set", payload)
    turn.methods.append("thread/goal/set")
    turn.post_goal_status = "active"


def _clear_blocked(
    *,
    loopx_cli: str,
    registry: str,
    runtime_root: str,
    goal_id: str,
    agent_id: str,
    cwd: str,
) -> None:
    command = [
        loopx_cli,
        "--registry",
        registry,
        "--runtime-root",
        runtime_root,
        "--format",
        "json",
        "configure-goal",
        "--goal-id",
        goal_id,
        "--clear-waiting-on",
        "--agent-work-mode",
        f"{agent_id}=active",
        "--write-scope",
        cwd,
        "--execute",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode:
        detail = (result.stderr or result.stdout)[-240:]
        raise NativeGoalProtocolError(f"blocked_recovery_failed:{detail}")


def _terminal_error(event: Mapping[str, Any]) -> str | None:
    method = str(event.get("method") or "")
    params = event.get("params") if isinstance(event.get("params"), Mapping) else {}
    event_type = str(event.get("type") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
    payload_type = str(payload.get("type") or "")
    terminal = method == "turn/completed" or (
        event_type == "event_msg" and payload_type in {"task_complete", "task_completed", "turn_completed"}
    )
    if not terminal:
        return None
    turn = params.get("turn") if isinstance(params.get("turn"), Mapping) else {}
    for container in (payload, turn, params):
        error = container.get("error") if isinstance(container, Mapping) else None
        if error is None:
            continue
        if isinstance(error, Mapping):
            return str(error.get("message") or error.get("type") or error)
        return str(error)
    return None


def _wait_turn(
    transport,
    turn,
    *,
    deadline: float,
    completed_before: int,
    idle_timeout_seconds: float,
    interrupt_grace_seconds: float,
) -> str | None:
    error: str | None = None
    last_event_at = time.monotonic()
    interrupt_deadline: float | None = None
    while turn.turn_completed_count <= completed_before:
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            raise NativeGoalProtocolError("goal_timeout_before_terminal")
        event = transport.next_event(timeout_sec=min(0.25, remaining))
        if event is not None:
            last_event_at = time.monotonic()
            error = _terminal_error(event) or error
            observe_native_goal_event(turn, event)
            continue
        now = time.monotonic()
        if interrupt_deadline is not None:
            if now >= interrupt_deadline:
                raise NativeGoalProtocolError("turn_interrupt_timeout")
            continue
        if now - last_event_at >= idle_timeout_seconds:
            transport.request(
                "turn/interrupt",
                {"threadId": turn.thread_id, "turnId": turn.turn_id},
            )
            error = f"turn idle timeout after {idle_timeout_seconds:g} seconds"
            interrupt_deadline = min(deadline, now + interrupt_grace_seconds)
    return error


def _is_transient_model_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "rate limit",
            "overloaded",
            "server error",
            "timed out",
            "timeout",
            "deployment_disabled",
            "insufficient quota available",
        )
    )


def _benchmark_todo_terminal(args: argparse.Namespace, project: Path) -> bool:
    result = subprocess.run(
        [
            args.loopx_cli,
            "--registry",
            args.registry,
            "--runtime-root",
            args.runtime_root,
            "--format",
            "json",
            "todo",
            "list",
            "--goal-id",
            args.goal_id,
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        return False
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return False
    todos = payload.get("todos") if isinstance(payload, dict) else None
    if not isinstance(todos, list):
        return False
    statuses = [
        item.get("status")
        for item in todos
        if isinstance(item, dict) and item.get("priority") == "P0"
    ]
    return bool(statuses) and all(status in {"done", "deferred"} for status in statuses)


def run_goal(args: argparse.Namespace):
    project = Path(args.cwd).resolve()
    base_sha = head_sha(project)
    delivery_path = Path("/logs/agent/delivery_receipt.json")
    config = NativeGoalConfig(
        cwd=args.cwd,
        objective=Path(args.objective_file).read_text(encoding="utf-8").strip(),
        task_instruction=Path(args.task_file).read_text(encoding="utf-8").strip(),
        model=args.model,
        effort=args.effort,
        token_budget=args.token_budget,
        sandbox=args.sandbox,
        required_skill_ids=tuple(
            item for item in (part.strip() for part in args.required_skill_ids.split(",")) if item
        ),
    )
    process_command = [
        args.codex_bin,
        "app-server",
        "--listen",
        "stdio://",
        "--enable",
        "goals",
        "--enable",
        "unified_exec",
    ]
    process_env = os.environ.copy()
    if args.preflight_only:
        return probe_native_goal_process(
            config,
            codex_bin=args.codex_bin,
            process_command=process_command,
            process_env=process_env,
            process_cwd=args.cwd,
            response_timeout_sec=args.response_timeout_seconds,
        ), 0

    with StdioNativeGoalTransport.spawn(
        process_command,
        cwd=args.cwd,
        env=process_env,
        response_timeout_sec=args.response_timeout_seconds,
    ) as transport:
        turn = start_native_goal_turn(transport, config)
        deadline = time.monotonic() + args.goal_timeout_seconds
        completed_before = turn.turn_completed_count
        unblocks = 0
        delivery_retries = 0
        transient_retries = 0
        delivery = None
        benchmark_todo_terminal = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeGoalProtocolError("goal_timeout_before_terminal")
            turn_error = _wait_turn(
                transport,
                turn,
                deadline=deadline,
                completed_before=completed_before,
                idle_timeout_seconds=args.turn_idle_timeout_seconds,
                interrupt_grace_seconds=args.interrupt_grace_seconds,
            )
            completed_before = turn.turn_completed_count
            if turn_error is not None:
                if not _is_transient_model_error(turn_error):
                    raise NativeGoalProtocolError(f"non_transient_model_error:{turn_error}")
                if transient_retries >= args.max_transient_retries:
                    raise NativeGoalProtocolError(
                        f"transient_model_retries_exhausted:{turn_error}"
                    )
                transient_retries += 1
                delay = min(
                    args.retry_backoff_cap_seconds,
                    args.retry_backoff_base_seconds * (2 ** (transient_retries - 1)),
                    max(0.0, deadline - time.monotonic()),
                )
                if delay <= 0:
                    raise NativeGoalProtocolError("goal_timeout_during_transient_backoff")
                time.sleep(delay)
                _reactivate_goal(transport, config, turn)
                turn = _restart_turn_same_thread(
                    transport,
                    config,
                    turn,
                    "The previous model turn ended in a transient provider error. "
                    "Resume the active P0 task from the current Goal and workspace state; "
                    "do not repeat completed investigation.",
                )
                completed_before = turn.turn_completed_count
                continue
            status = refresh_native_goal_status(transport, turn)
            if status == "active":
                continue
            delivery = normalize_delivery(project, base_sha)
            write_receipt(delivery_path, delivery)
            benchmark_todo_terminal = _benchmark_todo_terminal(args, project)
            if delivery["treatment_valid"] and benchmark_todo_terminal:
                break

            can_recover_blocked = (
                status == "blocked" and args.recover_blocked and unblocks < args.max_unblocks
            )
            can_recover_delivery = (
                (not delivery["treatment_valid"] or not benchmark_todo_terminal)
                and delivery_retries < args.max_delivery_retries
            )
            if not can_recover_blocked and not can_recover_delivery:
                raise NativeGoalProtocolError(
                    f"goal_terminal_without_valid_delivery:status={status}:"
                    f"delivery={delivery.get('status')}"
                )
            if can_recover_blocked:
                unblocks += 1
                _clear_blocked(
                    loopx_cli=args.loopx_cli,
                    registry=args.registry,
                    runtime_root=args.runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    cwd=args.cwd,
                )
            if can_recover_delivery:
                delivery_retries += 1
            _reactivate_goal(transport, config, turn)
            repair = (
                "Runner delivery check failed. Continue the active P0 task in /app, or recover your linked "
                "worktree, and do not complete the Goal until git diff from the task base "
                "is non-empty, committed, and the repository's public tests pass."
            )
            turn = _restart_turn_same_thread(transport, config, turn, repair)
            completed_before = turn.turn_completed_count
    if delivery is None:
        delivery = normalize_delivery(project, base_sha)
        write_receipt(delivery_path, delivery)
    if not delivery["treatment_valid"]:
        raise NativeGoalProtocolError("native_goal_finished_without_valid_delivery")
    return (
        turn,
        unblocks,
        delivery_retries,
        transient_retries,
        benchmark_todo_terminal,
        delivery,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--objective-file", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--token-budget", type=int)
    parser.add_argument("--response-timeout-seconds", type=float, default=30)
    parser.add_argument("--goal-timeout-seconds", type=float, default=3600)
    parser.add_argument("--sandbox", default="danger-full-access")
    parser.add_argument("--required-skill-ids", default="")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--recover-blocked", action="store_true")
    parser.add_argument("--max-unblocks", type=int, default=8)
    parser.add_argument("--max-delivery-retries", type=int, default=3)
    parser.add_argument("--max-transient-retries", type=int, default=12)
    parser.add_argument("--retry-backoff-base-seconds", type=float, default=5)
    parser.add_argument("--retry-backoff-cap-seconds", type=float, default=60)
    parser.add_argument("--turn-idle-timeout-seconds", type=float, default=300)
    parser.add_argument("--interrupt-grace-seconds", type=float, default=60)
    parser.add_argument("--loopx-cli", default="loopx")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--mode", choices=("ssh-goal",), default="ssh-goal")
    args = parser.parse_args()

    result = run_goal(args)
    if args.preflight_only:
        turn, unblocks = result
        delivery_retries = 0
        transient_retries = 0
        benchmark_todo_terminal = False
        delivery = None
    else:
        (
            turn,
            unblocks,
            delivery_retries,
            transient_retries,
            benchmark_todo_terminal,
            delivery,
        ) = result
    receipt = compact_native_goal_receipt(turn)
    receipt["execution_mode"] = "goal_attachment_preflight" if args.preflight_only else "goal_until_terminal"
    receipt["loopx_mode"] = args.mode
    receipt["continuation_owner"] = "codex"
    receipt["loopx_unblock_count"] = unblocks
    receipt["loopx_blocked_recovery"] = bool(args.recover_blocked)
    receipt["delivery_retry_count"] = delivery_retries
    receipt["transient_retry_count"] = transient_retries
    receipt["turn_idle_timeout_seconds"] = args.turn_idle_timeout_seconds
    receipt["benchmark_todo_terminal"] = benchmark_todo_terminal
    receipt["delivery"] = delivery
    receipt["treatment_valid"] = bool(delivery and delivery.get("treatment_valid"))
    receipt["host_surface"] = "native_goal_appserver"
    receipt["model"] = args.model
    receipt["effort"] = args.effort
    receipt["task_correctness_authority"] = "independent_verifier"
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
