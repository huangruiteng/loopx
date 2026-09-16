#!/usr/bin/env python3
"""Run the LoopX codex-cli arm through the real ``turn run-once`` host."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from workspace_delivery import head_sha, normalize_delivery, write_receipt


def _json_payload(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _goal_terminal(todo_payload: dict[str, Any]) -> bool:
    todos = todo_payload.get("todos")
    if not isinstance(todos, list):
        return False
    statuses = [
        item.get("status")
        for item in todos
        if isinstance(item, dict) and item.get("priority") == "P0"
    ]
    return bool(statuses) and all(status in {"done", "deferred"} for status in statuses)


def _todo_state(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    completed = subprocess.run(
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
    payload = _json_payload(completed.stdout)
    return {
        "returncode": completed.returncode,
        "terminal": completed.returncode == 0 and _goal_terminal(payload),
        "payload": payload,
        "stdout_tail": completed.stdout[-800:],
        "stderr_tail": completed.stderr[-800:],
    }


def _claim_primary_p0(
    args: argparse.Namespace,
    project: Path,
) -> dict[str, Any]:
    """Keep the benchmark P0 selected across validated-progress segments."""
    state = _todo_state(args, project)
    if state["returncode"] != 0:
        return {
            "ok": False,
            "reason": "todo_list_failed",
            "returncode": state["returncode"],
            "stdout_tail": state["stdout_tail"],
            "stderr_tail": state["stderr_tail"],
        }
    if state["terminal"]:
        return {"ok": True, "terminal": True, "claimed": False}

    todos = state["payload"].get("todos")
    open_p0 = [
        item
        for item in todos if isinstance(item, dict)
        and item.get("priority") == "P0"
        and item.get("role") == "agent"
        and item.get("status") == "open"
    ] if isinstance(todos, list) else []
    if len(open_p0) != 1:
        return {
            "ok": False,
            "reason": f"expected_one_open_agent_p0_got_{len(open_p0)}",
        }

    todo = open_p0[0]
    todo_id = str(todo.get("todo_id") or "")
    if not todo_id:
        return {"ok": False, "reason": "open_agent_p0_missing_todo_id"}
    if todo.get("claimed_by") == args.agent_id:
        return {
            "ok": True,
            "terminal": False,
            "claimed": False,
            "todo_id": todo_id,
            "claimed_by": args.agent_id,
        }
    if todo.get("claimed_by") not in {None, ""}:
        return {
            "ok": False,
            "reason": "benchmark_p0_claimed_by_other_agent",
            "todo_id": todo_id,
            "claimed_by": todo.get("claimed_by"),
        }

    completed = subprocess.run(
        [
            args.loopx_cli,
            "--registry",
            args.registry,
            "--runtime-root",
            args.runtime_root,
            "--format",
            "json",
            "todo",
            "claim",
            "--goal-id",
            args.goal_id,
            "--todo-id",
            todo_id,
            "--claimed-by",
            args.agent_id,
            "--agent-id",
            args.agent_id,
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    payload = _json_payload(completed.stdout)
    ok = completed.returncode == 0 and payload.get("ok") is not False
    return {
        "ok": ok,
        "terminal": False,
        "claimed": ok,
        "todo_id": todo_id,
        "claimed_by": args.agent_id if ok else None,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-800:],
        "stderr_tail": completed.stderr[-800:],
    }


def _retry_delay(
    payload: dict[str, Any],
    args: argparse.Namespace,
    failure_streak: int,
) -> float:
    if not failure_streak:
        return args.segment_interval_seconds
    delay = args.retry_backoff_base_seconds * (2 ** (failure_streak - 1))
    host_failure = payload.get("host_failure")
    if isinstance(host_failure, dict) and host_failure.get("retryable") is True:
        retry = host_failure.get("retry")
        if isinstance(retry, dict):
            recommended = retry.get("backoff_seconds")
            if isinstance(recommended, (int, float)) and recommended > 0:
                delay = max(delay, float(recommended))
    return min(args.retry_backoff_cap_seconds, delay)


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    project = Path(args.cwd).resolve()
    base_sha = head_sha(project)
    deadline = time.monotonic() + args.goal_timeout_seconds
    delivery_path = Path("/logs/agent/delivery_receipt.json")
    receipts: list[dict[str, Any]] = []
    failure_streak = 0
    wrapper = Path(__file__).with_name("codex_nosandbox_wrapper.py")
    delivery_helper = Path(__file__).with_name("workspace_delivery.py")

    if args.preflight_only:
        payload = {
            "schema_version": "deepswe_codex_cli_runner_v1",
            "host_surface": "codex_cli_turn_run_once",
            "preflight": wrapper.is_file() and delivery_helper.is_file(),
        }
        return payload, 0 if payload["preflight"] else 2

    for segment in range(1, args.max_segments + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        claim = _claim_primary_p0(args, project)
        if claim.get("terminal"):
            delivery = normalize_delivery(project, base_sha)
            write_receipt(delivery_path, delivery)
            if delivery["treatment_valid"]:
                result = {
                    "schema_version": "deepswe_codex_cli_runner_v1",
                    "execution_mode": "loopx_turn_run_once",
                    "host_surface": "codex_cli",
                    "model": args.model,
                    "effort": args.effort,
                    "turn_status": "completed",
                    "segments": receipts,
                    "segment_count": len(receipts),
                    "delivery": delivery,
                    "treatment_valid": True,
                    "task_correctness_authority": "independent_verifier",
                }
                return result, 0
        if not claim.get("ok"):
            receipts.append({
                "segment": segment,
                "returncode": claim.get("returncode", 1),
                "status": "claim_failed",
                "result_kind": None,
                "validation_status": None,
                "p0_claim": claim,
            })
            break
        segment_timeout = max(60.0, min(args.segment_timeout_seconds, remaining))
        validation = [
            "python3",
            str(delivery_helper),
            "--project",
            str(project),
            "--base-sha",
            base_sha,
            "--receipt",
            str(delivery_path),
            "--require-valid",
        ]
        command = [
            args.loopx_cli,
            "--registry",
            args.registry,
            "--runtime-root",
            args.runtime_root,
            "--format",
            "json",
            "turn",
            "run-once",
            "--goal-id",
            args.goal_id,
            "--agent-id",
            args.agent_id,
            "--turn-instance-id",
            f"deepswe-codex-cli-{segment}",
            "--host",
            "codex-cli",
            "--execution-mode",
            "isolated-headless",
            "--scheduler-owner",
            "agent_cli_loop",
            "--project",
            str(project),
            "--codex-bin",
            str(wrapper),
            "--codex-sandbox",
            "workspace-write",
            "--codex-model",
            args.model or "",
            "--validation-command-json",
            json.dumps(validation),
            "--validation-timeout-seconds",
            "180",
            "--timeout-seconds",
            str(segment_timeout),
            "--no-global-sync",
            "--execute",
        ]
        env = os.environ.copy()
        env["MR_REAL_CODEX"] = args.codex_bin
        env["MR_LOOPX_PROJECT"] = str(project)
        env["MR_CODEX_REASONING_EFFORT"] = args.effort or ""
        completed = subprocess.run(
            command,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=segment_timeout + 240,
            check=False,
        )
        payload = _json_payload(completed.stdout)
        receipts.append(
            {
                "segment": segment,
                "returncode": completed.returncode,
                "status": payload.get("status"),
                "result_kind": payload.get("result_kind"),
                "validation_status": payload.get("validation_status"),
                "p0_claim": claim,
                "stdout_tail": completed.stdout[-1200:],
                "stderr_tail": completed.stderr[-1200:],
            }
        )
        delivery = normalize_delivery(project, base_sha)
        write_receipt(delivery_path, delivery)
        todo_state = _todo_state(args, project)
        receipts[-1]["goal_terminal"] = todo_state["terminal"]
        receipts[-1]["todo_state_returncode"] = todo_state["returncode"]
        if delivery["treatment_valid"] and (
            completed.returncode == 0
            and (
                payload.get("status") == "committed"
                or payload.get("validation_status") == "passed"
            )
            and todo_state["terminal"]
        ):
            result = {
                "schema_version": "deepswe_codex_cli_runner_v1",
                "execution_mode": "loopx_turn_run_once",
                "host_surface": "codex_cli",
                "model": args.model,
                "effort": args.effort,
                "turn_status": "completed",
                "segments": receipts,
                "segment_count": len(receipts),
                "delivery": delivery,
                "treatment_valid": True,
                "task_correctness_authority": "independent_verifier",
            }
            return result, 0
        if completed.returncode != 0 and not payload:
            break
        failure_streak = failure_streak + 1 if completed.returncode else 0
        if segment < args.max_segments:
            delay = _retry_delay(payload, args, failure_streak)
            time.sleep(min(delay, max(0.0, deadline - time.monotonic())))

    delivery = normalize_delivery(project, base_sha)
    write_receipt(delivery_path, delivery)
    result = {
        "schema_version": "deepswe_codex_cli_runner_v1",
        "execution_mode": "loopx_turn_run_once",
        "host_surface": "codex_cli",
        "model": args.model,
        "effort": args.effort,
        "turn_status": "failed",
        "segments": receipts,
        "segment_count": len(receipts),
        "delivery": delivery,
        "treatment_valid": False,
        "task_correctness_authority": "independent_verifier",
        "error": "codex_cli_did_not_reach_validated_delivery",
    }
    return result, 12


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--cwd", required=True)
    result.add_argument("--objective-file", required=True)
    result.add_argument("--task-file", required=True)
    result.add_argument("--codex-bin", default="codex")
    result.add_argument("--model")
    result.add_argument("--effort")
    result.add_argument("--token-budget", type=int)
    result.add_argument("--response-timeout-seconds", type=float, default=180)
    result.add_argument("--goal-timeout-seconds", type=float, default=5400)
    result.add_argument("--segment-timeout-seconds", type=float, default=7200)
    result.add_argument("--max-segments", type=int, default=256)
    result.add_argument("--segment-interval-seconds", type=float, default=5)
    result.add_argument("--retry-backoff-base-seconds", type=float, default=10)
    result.add_argument("--retry-backoff-cap-seconds", type=float, default=60)
    result.add_argument("--sandbox", default="danger-full-access")
    result.add_argument("--required-skill-ids", default="")
    result.add_argument("--preflight-only", action="store_true")
    result.add_argument("--recover-blocked", action="store_true")
    result.add_argument("--max-unblocks", type=int, default=8)
    result.add_argument("--loopx-cli", required=True)
    result.add_argument("--registry", required=True)
    result.add_argument("--runtime-root", required=True)
    result.add_argument("--goal-id", required=True)
    result.add_argument("--agent-id", required=True)
    result.add_argument("--mode")
    return result


def main() -> int:
    payload, code = run(parser().parse_args())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
