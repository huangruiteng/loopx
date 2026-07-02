#!/usr/bin/env python3
"""Host-side SkillsBench worker for native Codex app-server Goal turns.

This script is intentionally thin. SkillsBench/BenchFlow owns task staging and
verification; this worker owns only the host Codex app-server Goal turn. Public
outputs must stay compact: hashes, counts, method/proof shape, and no raw task
text, raw trajectories, raw logs, credentials, or local paths.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench import (  # noqa: E402
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_TASK,
    build_skillsbench_app_server_goal_worker_contract,
)
from loopx.benchmark_case_state import (  # noqa: E402
    build_benchmark_case_lifecycle_packet,
)
from loopx.codex_goal_baseline import stable_text_digest  # noqa: E402
from scripts.codex_app_server_goal_driver import (  # noqa: E402
    CodexAppServerGoalDriverError,
    compact_turn_metadata,
    observe_codex_app_server_goal_turn,
    start_codex_app_server_goal_followup_turn,
    start_codex_app_server_goal_turn,
)

SKILLS_INSTRUCTIONS_END_MARKER = "</skills_instructions>"


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _public_safe_label(value: Any, *, limit: int = 80) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = []
    for char in text:
        cleaned.append(
            char.lower() if char.isalnum() or char in {"-", "_", ".", ":"} else "-"
        )
    label = "".join(cleaned).strip("-_.:")
    while "--" in label:
        label = label.replace("--", "-")
    return label[:limit]


def build_contract_payload(args: argparse.Namespace) -> dict[str, Any]:
    return build_skillsbench_app_server_goal_worker_contract(
        dataset=args.dataset,
        task_id=args.task_id,
        cwd="<skillsbench-task-workspace>",
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        codex_bin=args.codex_bin,
        sandbox=args.sandbox,
        approval_policy=args.approval_policy,
        no_upload=True,
        submit_enabled=False,
        compact_reducer_ready=True,
        runner_integration_ready=args.runner_integration_ready,
    )


def build_loopx_case_lifecycle_packet(
    args: argparse.Namespace,
) -> tuple[str, dict[str, object] | None]:
    if args.loopx_mode != "codex_loopx":
        return "", None
    if args.loopx_access_packet_mode == "none":
        return "", None
    case_id = args.loopx_case_id or args.task_id
    return build_benchmark_case_lifecycle_packet(
        packet_header="skillsbench_loopx_case_lifecycle_packet_v0:",
        packet_mode=args.loopx_access_packet_mode,
        benchmark_family="benchflow",
        benchmark_id=args.dataset,
        case_id=case_id,
        arm_id=args.loopx_arm_id,
        max_rounds=args.loopx_max_rounds,
        indent="  ",
    )


def _prompt_with_loopx_case_lifecycle_packet(
    prompt: str,
    packet: str,
) -> str:
    packet_text = packet.strip()
    if not packet_text:
        return prompt
    return (
        prompt.rstrip()
        + "\n\n"
        + "LoopX case lifecycle packet:\n"
        + packet_text
        + "\n\n"
        + "Use this packet as the canonical LoopX product-mode lifecycle contract. Keep the "
        + "official SkillsBench/BenchFlow verifier authoritative, do not expose "
        + "reward or verifier output during the agent loop, and do not rely on "
        + "runner-internal polling or marker files as LoopX treatment evidence."
    )


def _post_context_assistant_chars(turn: Any) -> int:
    message = str(getattr(turn, "assistant_message", "") or "")
    stripped = message.strip()
    if not stripped:
        return 0
    marker_index = stripped.rfind(SKILLS_INSTRUCTIONS_END_MARKER)
    if marker_index < 0:
        return len(stripped)
    tail = stripped[marker_index + len(SKILLS_INSTRUCTIONS_END_MARKER) :].strip()
    return len(tail)


def _assistant_message_context_only(turn: Any) -> bool:
    message = str(getattr(turn, "assistant_message", "") or "")
    stripped = message.strip()
    if not stripped or _post_context_assistant_chars(turn) > 0:
        return False
    return (
        stripped.startswith("<permissions instructions>")
        or stripped.startswith("<skills_instructions>")
        or "<skills_instructions>" in stripped[:4096]
    )


def _first_action_observed(turn: Any) -> bool:
    if int(getattr(turn, "agent_message_delta_count", 0) or 0) > 0:
        return True
    if _assistant_message_context_only(turn):
        return False
    if int(getattr(turn, "agent_message_item_count", 0) or 0) > 0:
        return True
    if int(getattr(turn, "non_user_item_completed_count", 0) or 0) > 0:
        return True
    notifications = getattr(turn, "notifications", []) or []
    for method in notifications:
        text = str(method or "")
        if text.startswith("item/agentMessage"):
            return True
    return False


def _effective_action_observed(turn: Any) -> bool:
    if _assistant_message_context_only(turn):
        return False
    if bool(getattr(turn, "turn_completed_observed", False)):
        return True
    if str(getattr(turn, "assistant_message", "") or ""):
        return True
    if int(getattr(turn, "agent_message_item_count", 0) or 0) > 0:
        return True
    if int(getattr(turn, "non_user_item_completed_count", 0) or 0) > 0:
        return True
    return False


def _terminal_app_server_failure(turn: Any) -> str:
    if bool(getattr(turn, "turn_completed_observed", False)):
        return ""
    if bool(getattr(turn, "stream_eof_observed", False)):
        return "codex_app_server_stream_eof_before_completion"
    if bool(getattr(turn, "stream_error_observed", False)):
        return "codex_app_server_stream_error_before_completion"
    process = getattr(turn, "process", None)
    returncode = None
    if process is not None:
        try:
            returncode = process.poll()
        except Exception:
            returncode = None
    if returncode is not None or bool(getattr(turn, "process_exit_observed", False)):
        return "codex_app_server_process_exited_before_completion"
    return ""


def _compact_worker_turn(
    turn: Any,
    *,
    args: argparse.Namespace,
    lifecycle_packet: str,
    lifecycle_contract: dict[str, object] | None,
) -> dict[str, Any]:
    compact = compact_turn_metadata(turn)
    compact.update(
        {
            "completion_hard_gate": False,
            "completion_source_of_truth": "codex_turn_completion",
            "first_action_timeout_sec": max(
                0.0, float(args.first_action_timeout_sec or 0.0)
            ),
            "first_action_observed": _first_action_observed(turn),
            "effective_action_observed": _effective_action_observed(turn),
            "assistant_message_context_only": _assistant_message_context_only(turn),
            "post_context_assistant_chars": _post_context_assistant_chars(turn),
            "reasoning_effort": _public_safe_label(args.reasoning_effort) or "high",
            "loopx_mode": args.loopx_mode,
            "loopx_access_packet_mode": args.loopx_access_packet_mode,
            "loopx_case_lifecycle_packet_injected": bool(lifecycle_packet),
            "benchmark_case_lifecycle_contract": lifecycle_contract,
        }
    )
    return compact


def _wait_for_worker_turn_completion(
    turn: Any,
    *,
    timeout_sec: float,
    first_action_timeout_sec: float = 0.0,
    poll_interval_sec: float = 1.0,
) -> bool:
    started_at = time.monotonic()
    deadline = started_at + max(0.0, timeout_sec)
    first_action_deadline = 0.0
    if first_action_timeout_sec > 0:
        first_action_deadline = started_at + max(0.1, first_action_timeout_sec)
    while time.monotonic() < deadline:
        observe_codex_app_server_goal_turn(turn, timeout_sec=0.0, raise_on_error=False)
        terminal_failure = _terminal_app_server_failure(turn)
        if terminal_failure:
            raise CodexAppServerGoalDriverError(terminal_failure)
        if turn.turn_completed_observed:
            return True
        if (
            first_action_deadline
            and not _effective_action_observed(turn)
            and time.monotonic() >= first_action_deadline
        ):
            raise TimeoutError("codex_exec_first_action_timeout")
        time.sleep(max(0.1, poll_interval_sec))
    observe_codex_app_server_goal_turn(turn, timeout_sec=0.0, raise_on_error=False)
    terminal_failure = _terminal_app_server_failure(turn)
    if terminal_failure:
        raise CodexAppServerGoalDriverError(terminal_failure)
    return bool(turn.turn_completed_observed)


def run_worker(args: argparse.Namespace) -> dict[str, Any]:
    prompt_path = Path(args.prompt_file).expanduser()
    work_dir = Path(args.work_dir).expanduser()
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("prompt file is empty")

    objective = args.objective or f"Complete SkillsBench task {args.task_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    lifecycle_packet, lifecycle_contract = build_loopx_case_lifecycle_packet(args)
    effective_prompt = _prompt_with_loopx_case_lifecycle_packet(
        prompt,
        lifecycle_packet,
    )
    turn = start_codex_app_server_goal_turn(
        codex_bin=args.codex_bin,
        work_dir=work_dir,
        objective=objective,
        prompt=effective_prompt,
        model_name=args.model,
        reasoning_effort=args.reasoning_effort,
        approval_policy=args.approval_policy,
        sandbox=args.sandbox,
        response_timeout_sec=args.response_timeout_sec,
        wait_for_completion=False,
    )
    worker_error_type = ""
    active_turn = turn
    attempt_compacts: list[dict[str, Any]] = []
    try:
        followup_budget = max(0, int(args.context_only_followup_max or 0))
        attempt_number = 1
        while True:
            if not args.no_wait_for_completion:
                try:
                    turn_completed = _wait_for_worker_turn_completion(
                        active_turn,
                        timeout_sec=args.turn_timeout_sec,
                        first_action_timeout_sec=args.first_action_timeout_sec,
                    )
                    if not turn_completed:
                        raise TimeoutError(
                            "timed out waiting for app-server worker turn completion"
                        )
                except (TimeoutError, CodexAppServerGoalDriverError) as exc:
                    if str(exc) == "codex_exec_first_action_timeout":
                        worker_error_type = "codex_exec_first_action_timeout"
                    elif str(exc).startswith("codex_app_server_"):
                        worker_error_type = str(exc)
                    else:
                        worker_error_type = "codex_app_server_turn_timeout"
            compact = _compact_worker_turn(
                active_turn,
                args=args,
                lifecycle_packet=lifecycle_packet,
                lifecycle_contract=lifecycle_contract,
            )
            compact.update(
                {
                    "attempt_number": attempt_number,
                    "selected_final_turn": False,
                }
            )
            attempt_compacts.append(compact)
            if worker_error_type or args.no_wait_for_completion:
                break
            if compact.get("assistant_message_context_only") is not True:
                break
            if followup_budget <= 0:
                worker_error_type = "codex_app_server_context_only_assistant_message"
                break
            followup_budget -= 1
            attempt_number += 1
            try:
                active_turn = start_codex_app_server_goal_followup_turn(
                    active_turn,
                    work_dir=work_dir,
                    prompt=effective_prompt,
                    model_name=args.model,
                    reasoning_effort=args.reasoning_effort,
                    approval_policy=args.approval_policy,
                    response_timeout_sec=args.response_timeout_sec,
                    wait_for_completion=False,
                )
            except CodexAppServerGoalDriverError as exc:
                detail = str(exc)
                worker_error_type = (
                    detail
                    if detail.startswith("codex_app_server_")
                    else "codex_app_server_context_only_followup_start_failed"
                )
                break
        turn = active_turn
        compact = _compact_worker_turn(
            turn,
            args=args,
            lifecycle_packet=lifecycle_packet,
            lifecycle_contract=lifecycle_contract,
        )
        context_only_turn_count = sum(
            1
            for attempt in attempt_compacts
            if attempt.get("assistant_message_context_only") is True
        )
        compact.update(
            {
                "attempt_number": len(attempt_compacts) or 1,
                "selected_final_turn": True,
                "turn_attempt_count": len(attempt_compacts) or 1,
                "turn_completed_attempt_count": sum(
                    1
                    for attempt in attempt_compacts
                    if attempt.get("turn_completed_observed") is True
                ),
                "assistant_message_attempt_count": sum(
                    1
                    for attempt in attempt_compacts
                    if attempt.get("assistant_message_present") is True
                ),
                "context_only_turn_count": context_only_turn_count,
                "context_only_followup_max": max(
                    0, int(args.context_only_followup_max or 0)
                ),
                "context_only_recovery_attempted": bool(
                    context_only_turn_count and len(attempt_compacts) > 1
                ),
                "context_only_recovery_succeeded": bool(
                    context_only_turn_count
                    and compact.get("assistant_message_context_only") is not True
                    and not worker_error_type
                )
            }
        )
        if attempt_compacts:
            attempt_compacts[-1] = dict(compact)
        if (
            not worker_error_type
            and not args.no_wait_for_completion
            and compact.get("assistant_message_present") is not True
        ):
            worker_error_type = "codex_app_server_no_assistant_message"
        if (
            not worker_error_type
            and not args.no_wait_for_completion
            and compact.get("assistant_message_context_only") is True
        ):
            worker_error_type = "codex_app_server_context_only_assistant_message"
        private_response_written = False
        if args.response_text_file and turn.assistant_message:
            response_path = Path(args.response_text_file).expanduser()
            response_path.parent.mkdir(parents=True, exist_ok=True)
            response_path.write_text(turn.assistant_message, encoding="utf-8")
            private_response_written = True
    finally:
        active_turn.terminate()
    worker_contract = build_contract_payload(args)
    if worker_error_type:
        worker_contract = dict(worker_contract)
        blockers = list(worker_contract.get("blockers") or [])
        if worker_error_type not in blockers:
            blockers.insert(0, worker_error_type)
        worker_contract.update(
            {
                "ready": False,
                "first_blocker": worker_error_type,
                "blockers": blockers,
            }
        )
    ok = not worker_error_type and bool(compact.get("turn_id_present")) and (
        args.no_wait_for_completion
        or compact.get("turn_completed_observed") is True
    )
    return {
        "schema_version": "skillsbench_host_codex_goal_worker_result_v0",
        "ok": ok,
        "error_type": worker_error_type,
        "route": "codex-app-server-goal-baseline",
        "benchmark_id": args.dataset,
        "task_id": args.task_id,
        "run_group_id": args.run_group_id,
        "job_name": args.job_name,
        "rollout_name": args.rollout_name,
        "loopx_mode": args.loopx_mode,
        "loopx_access_packet_mode": args.loopx_access_packet_mode,
        "loopx_case_lifecycle_packet_injected": bool(lifecycle_packet),
        "benchmark_case_lifecycle_contract": lifecycle_contract,
        "worker_contract": worker_contract,
        "prompt": {
            "sha256": stable_text_digest(prompt),
            "chars": len(prompt),
            "effective_sha256": stable_text_digest(effective_prompt),
            "effective_chars": len(effective_prompt),
            "raw_recorded": False,
        },
        "turn": compact,
        "turn_attempts": attempt_compacts,
        "context_only_recovery": {
            "enabled": max(0, int(args.context_only_followup_max or 0)) > 0,
            "max_followups": max(0, int(args.context_only_followup_max or 0)),
            "attempted": bool(compact.get("context_only_recovery_attempted")),
            "succeeded": bool(compact.get("context_only_recovery_succeeded")),
            "context_only_turn_count": int(
                compact.get("context_only_turn_count") or 0
            ),
            "turn_attempt_count": int(compact.get("turn_attempt_count") or 1),
        },
        "private_response_text": {
            "written": private_response_written,
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=SKILLSBENCH_DEFAULT_DATASET)
    parser.add_argument("--task-id", default=SKILLSBENCH_DEFAULT_TASK)
    parser.add_argument("--run-group-id", default="")
    parser.add_argument("--job-name", default="")
    parser.add_argument("--rollout-name", default="")
    parser.add_argument("--model", default=SKILLSBENCH_DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        help=(
            "Codex app-server turn/start effort. Formal benchmark runs default "
            "to high; smoke/debug runs may override this explicitly."
        ),
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--approval-policy", default="never")
    parser.add_argument("--objective")
    parser.add_argument("--work-dir")
    parser.add_argument("--prompt-file")
    parser.add_argument("--output-json")
    parser.add_argument("--response-text-file")
    parser.add_argument("--response-timeout-sec", type=float, default=30.0)
    parser.add_argument("--turn-timeout-sec", type=float, default=7200.0)
    parser.add_argument("--first-action-timeout-sec", type=float, default=0.0)
    parser.add_argument(
        "--context-only-followup-max",
        type=int,
        default=1,
        help=(
            "Retry in the same app-server thread when a completed turn only "
            "echoes startup context. The retry keeps xhigh/Goal runs from "
            "writing the context preamble as the scored answer."
        ),
    )
    parser.add_argument(
        "--no-wait-for-completion",
        action="store_true",
        help=(
            "Return after turn/start instead of waiting for turn/completed. "
            "Use only for external pollers; SkillsBench scored workers should "
            "wait and write a private response text file."
        ),
    )
    parser.add_argument(
        "--runner-integration-ready",
        action="store_true",
        help="Mark the surrounding BenchFlow worker integration as ready.",
    )
    parser.add_argument(
        "--loopx-mode",
        default="codex_goal_mode_baseline",
        help=(
            "LoopX benchmark arm mode. Use codex_loopx only for "
            "treatment runs that intentionally receive a case lifecycle packet."
        ),
    )
    parser.add_argument(
        "--loopx-access-packet-mode",
        default="none",
        help="Set to compact to inject the public-safe case lifecycle packet.",
    )
    parser.add_argument(
        "--loopx-case-id",
        default="",
        help="Public case id for the per-case/arm LoopX lifecycle contract.",
    )
    parser.add_argument(
        "--loopx-arm-id",
        default="codex_app_server_goal_baseline",
        help="Public arm id for the per-case/arm LoopX lifecycle contract.",
    )
    parser.add_argument(
        "--loopx-max-rounds",
        type=int,
        default=5,
        help="Maximum public prompt-polling round budget for treatment metadata.",
    )
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="Print only the public-safe worker contract without invoking Codex.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.contract_only:
        payload = {
            "ok": True,
            "contract_only": True,
            "worker_contract": build_contract_payload(args),
        }
        lifecycle_packet, lifecycle_contract = build_loopx_case_lifecycle_packet(
            args
        )
        payload.update(
            {
                "loopx_mode": args.loopx_mode,
                "loopx_access_packet_mode": args.loopx_access_packet_mode,
                "loopx_case_lifecycle_packet_injected": bool(lifecycle_packet),
                "benchmark_case_lifecycle_contract": lifecycle_contract,
            }
        )
    else:
        if not args.work_dir or not args.prompt_file:
            raise SystemExit("--work-dir and --prompt-file are required unless --contract-only")
        payload = run_worker(args)

    text = json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n"
    if args.output_json:
        Path(args.output_json).expanduser().write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
