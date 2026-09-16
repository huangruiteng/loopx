#!/usr/bin/env python3
"""Runner-owned recurring heartbeat host for the DeepSWE LoopX arm."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from workspace_delivery import head_sha, normalize_delivery, write_receipt


def _decode_tail(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return value[-800:]


def _run_codex_segment(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    trace: Path,
    timeout: float,
) -> dict[str, Any]:
    """Run one heartbeat wake without letting its timeout kill the supervisor."""
    timed_out = False
    with trace.open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            _, stderr = process.communicate(timeout=timeout)
            returncode = process.returncode
            stderr_tail = _decode_tail(stderr)
        except subprocess.TimeoutExpired as exc:
            returncode = 124
            stderr_tail = _decode_tail(exc.stderr)
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            # The CLI launcher can exit before its native child. Kill the whole
            # isolated group even when the direct child has already returned.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, final_stderr = process.communicate()
            if final_stderr:
                stderr_tail = _decode_tail(final_stderr)
    return {
        "returncode": returncode,
        "stderr_tail": stderr_tail,
        "timed_out": timed_out,
    }


def _invoke_json(command: list[str], *, cwd: Path, timeout: float = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        payload = {}
    return {
        "returncode": completed.returncode,
        "payload": payload if isinstance(payload, dict) else {},
        "stdout_tail": completed.stdout[-800:],
        "stderr_tail": completed.stderr[-800:],
    }


def _loopx(args: argparse.Namespace, *command: str, cwd: Path) -> dict[str, Any]:
    return _invoke_json(
        [
            args.loopx_cli,
            "--registry",
            args.registry,
            "--runtime-root",
            args.runtime_root,
            "--format",
            "json",
            *command,
        ],
        cwd=cwd,
    )


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


def _trace_thread_id(trace: Path) -> str | None:
    try:
        with trace.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                thread_id = event.get("thread_id")
                if event.get("type") == "thread.started" and isinstance(thread_id, str):
                    return thread_id
    except OSError:
        return None
    return None


def _release_canonical_duplicate(
    project: Path, base_sha: str, delivery: dict[str, Any]
) -> bool:
    """Keep linked continuation work without leaving two changed checkouts."""
    if not delivery.get("treatment_valid") or not delivery.get(
        "recovered_from_linked_worktree"
    ):
        return False
    source = Path(str(delivery.get("source_worktree") or "")).resolve()
    if source == project:
        return False
    completed = subprocess.run(
        ["git", "-C", str(project), "reset", "--hard", base_sha],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            "could not release canonical continuation duplicate: "
            + _decode_tail(completed.stderr)
        )
    return True


def _repair_todo(args: argparse.Namespace, wake: int, cwd: Path) -> dict[str, Any]:
    return _loopx(
        args,
        "todo",
        "add",
        "--goal-id",
        args.goal_id,
        "--role",
        "agent",
        "--todo-id",
        f"deepswe-delivery-repair-{wake}",
        "--text",
        "Recover or implement the requested task in /app, run public tests, and leave a non-empty committed patch. Do not complete the Goal before this delivery exists.",
        "--task-class",
        "advancement_task",
        "--status",
        "open",
        "--execute",
        cwd=cwd,
    )


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    project = Path(args.cwd).resolve()
    base_sha = head_sha(project)
    deadline = time.monotonic() + args.goal_timeout_seconds
    task_text = Path(args.task_file).read_text(encoding="utf-8").strip()
    logs_dir = Path(args.logs_dir)
    delivery_path = logs_dir / "delivery_receipt.json"
    wakes: list[dict[str, Any]] = []
    resume_session_id: str | None = None
    continuation_worktree: str | None = None

    if args.preflight_only:
        prompt = _loopx(
            args,
            "heartbeat-prompt",
            "--thin",
            "--goal-id",
            args.goal_id,
            "--agent-id",
            args.agent_id,
            "--available-capability",
            "shell",
            "--available-capability",
            "filesystem_write",
            "--runtime-profile",
            "outer_controller",
            cwd=project,
        )
        payload = {
            "schema_version": "deepswe_heartbeat_supervisor_v1",
            "host_surface": "recurring_outer_controller_heartbeat",
            "preflight": prompt["returncode"] == 0 and bool(prompt["payload"].get("task_body")),
        }
        return payload, 0 if payload["preflight"] else 2

    for wake in range(1, args.max_wakes + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        prompt_result = _loopx(
            args,
            "heartbeat-prompt",
            "--thin",
            "--goal-id",
            args.goal_id,
            "--agent-id",
            args.agent_id,
            "--available-capability",
            "shell",
            "--available-capability",
            "filesystem_write",
            "--runtime-profile",
            "outer_controller",
            cwd=project,
        )
        task_body = str(prompt_result["payload"].get("task_body") or "")
        if prompt_result["returncode"] != 0 or not task_body:
            wakes.append({"wake": wake, "prompt": prompt_result, "error": "heartbeat_prompt_failed"})
            break
        prompt = (
            task_body
            + "\n\nBenchmark delivery fence: work on the task below in /app (a linked "
            "worktree is allowed but will be recovered), run the repository's public tests, "
            "and do not mark the Goal/Todo complete until a non-empty committed patch exists.\n\n"
            + task_text
        )
        if continuation_worktree:
            prompt += (
                "\n\nHeartbeat continuation fence: continue the existing implementation in "
                f"{continuation_worktree}; do not create another worktree or edit the "
                "canonical checkout directly. Finish validation and the LoopX lifecycle "
                "settlement before starting unrelated work."
            )
        segment_timeout = max(60.0, min(args.segment_timeout_seconds, remaining))
        with tempfile.TemporaryDirectory(prefix="deepswe-heartbeat-") as tmp:
            last = Path(tmp) / "last.txt"
            trace = logs_dir / f"heartbeat-wake-{wake}.jsonl"
            trace.parent.mkdir(parents=True, exist_ok=True)
            common = [
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
                "--model",
                args.model or "",
                "-c",
                f"model_reasoning_effort={args.effort}",
                "--output-last-message",
                str(last),
                "--json",
            ]
            if resume_session_id:
                command = [
                    args.codex_bin,
                    "exec",
                    "resume",
                    *common,
                    resume_session_id,
                    prompt,
                ]
            else:
                command = [
                    args.codex_bin,
                    "exec",
                    *common,
                    "-C",
                    str(project),
                    "--",
                    prompt,
                ]
            segment = _run_codex_segment(
                command,
                cwd=project,
                env=os.environ.copy(),
                trace=trace,
                timeout=segment_timeout,
            )
            observed_session_id = _trace_thread_id(trace)
            if observed_session_id:
                resume_session_id = observed_session_id
            last_text = last.read_text(encoding="utf-8", errors="replace") if last.exists() else ""
        delivery = normalize_delivery(project, base_sha)
        write_receipt(delivery_path, delivery)
        todos = _loopx(args, "todo", "list", "--goal-id", args.goal_id, cwd=project)
        terminal = _goal_terminal(todos["payload"])
        wakes.append(
            {
                "wake": wake,
                "host_process": "codex_exec",
                "returncode": segment["returncode"],
                "timed_out": segment["timed_out"],
                "resumed": wake > 1 and resume_session_id is not None,
                "session_id": resume_session_id,
                "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(),
                "last_message_tail": last_text[-800:],
                "stderr_tail": segment["stderr_tail"],
                "delivery_status": delivery["status"],
                "goal_terminal": terminal,
            }
        )
        if delivery["treatment_valid"] and terminal:
            result = {
                "schema_version": "deepswe_heartbeat_supervisor_v1",
                "execution_mode": "recurring_heartbeat",
                "host_surface": "outer_controller_heartbeat",
                "model": args.model,
                "effort": args.effort,
                "continuation_owner": "benchmark_supervisor",
                "turn_status": "completed",
                "wake_count": len(wakes),
                "wakes": wakes,
                "delivery": delivery,
                "treatment_valid": True,
                "task_correctness_authority": "independent_verifier",
            }
            return result, 0
        if terminal and not delivery["treatment_valid"]:
            _repair_todo(args, wake, project)
        canonical_released = _release_canonical_duplicate(project, base_sha, delivery)
        wakes[-1]["canonical_released_for_continuation"] = canonical_released
        if canonical_released:
            continuation_worktree = str(delivery["source_worktree"])
        if wake < args.max_wakes:
            time.sleep(args.heartbeat_interval_seconds)

    delivery = normalize_delivery(project, base_sha)
    write_receipt(delivery_path, delivery)
    result = {
        "schema_version": "deepswe_heartbeat_supervisor_v1",
        "execution_mode": "recurring_heartbeat",
        "host_surface": "outer_controller_heartbeat",
        "model": args.model,
        "effort": args.effort,
        "continuation_owner": "benchmark_supervisor",
        "turn_status": "failed",
        "wake_count": len(wakes),
        "wakes": wakes,
        "delivery": delivery,
        "treatment_valid": False,
        "task_correctness_authority": "independent_verifier",
        "error": "heartbeat_did_not_reach_terminal_validated_delivery",
    }
    return result, 12


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--cwd", required=True)
    result.add_argument("--logs-dir", default="/logs/agent")
    result.add_argument("--objective-file", required=True)
    result.add_argument("--task-file", required=True)
    result.add_argument("--codex-bin", default="codex")
    result.add_argument("--model")
    result.add_argument("--effort")
    result.add_argument("--token-budget", type=int)
    result.add_argument("--response-timeout-seconds", type=float, default=180)
    result.add_argument("--goal-timeout-seconds", type=float, default=14400)
    result.add_argument("--segment-timeout-seconds", type=float, default=7200)
    result.add_argument("--max-wakes", type=int, default=8)
    result.add_argument("--heartbeat-interval-seconds", type=float, default=5)
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
