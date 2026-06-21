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

from goal_harness.benchmark_adapters.skillsbench import (  # noqa: E402
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_TASK,
    build_skillsbench_app_server_goal_worker_contract,
)
from goal_harness.benchmark_case_state import (  # noqa: E402
    benchmark_case_lifecycle_contract,
    render_benchmark_case_lifecycle_contract_lines,
)
from goal_harness.codex_goal_baseline import stable_text_digest  # noqa: E402
from scripts.codex_app_server_goal_driver import (  # noqa: E402
    compact_turn_metadata,
    observe_codex_app_server_goal_turn,
    start_codex_app_server_goal_turn,
)


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


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


def _completion_marker_path(work_dir: Path, prompt: str) -> Path:
    digest = stable_text_digest(prompt)[:12]
    return work_dir / f".goal_harness_app_server_goal_worker_response_{digest}.txt"


def build_goal_harness_case_lifecycle_packet(
    args: argparse.Namespace,
) -> tuple[str, dict[str, object] | None]:
    if args.goal_harness_mode != "codex_goal_harness":
        return "", None
    if args.goal_harness_access_packet_mode == "none":
        return "", None
    case_id = args.goal_harness_case_id or args.task_id
    contract = benchmark_case_lifecycle_contract(
        benchmark_id=args.dataset,
        case_id=case_id,
        arm_id=args.goal_harness_arm_id,
        max_rounds=args.goal_harness_max_rounds,
    )
    lines = [
        "skillsbench_goal_harness_case_lifecycle_packet_v0:",
        f"  packet_mode: {args.goal_harness_access_packet_mode}",
        "  benchmark_family: benchflow",
    ]
    lines.extend(render_benchmark_case_lifecycle_contract_lines(contract))
    return "\n".join(lines), contract


def _prompt_with_goal_harness_case_lifecycle_packet(
    prompt: str,
    packet: str,
) -> str:
    packet_text = packet.strip()
    if not packet_text:
        return prompt
    return (
        prompt.rstrip()
        + "\n\n"
        + "Goal Harness case lifecycle packet:\n"
        + packet_text
        + "\n\n"
        + "Use this packet as observational control-plane context. Keep the "
        + "official SkillsBench/BenchFlow verifier authoritative, do not expose "
        + "reward or verifier output during the agent loop, and do not rely on "
        + "runner-internal polling alone when claiming Goal Harness treatment "
        + "evidence."
    )


def _prompt_with_completion_marker(prompt: str, marker_name: str) -> str:
    return (
        prompt.rstrip()
        + "\n\n"
        + "Goal Harness worker coordination: after you have completed the task, "
        + f"write a concise final status message to ./{marker_name} and then stop. "
        + "This hidden file is a temporary harness marker and will be removed before "
        + "verification; do not include raw task text or credential material in it."
    )


def _wait_for_worker_completion_marker(
    turn: Any,
    marker_path: Path,
    *,
    timeout_sec: float,
    poll_interval_sec: float = 1.0,
) -> tuple[bool, str, bool]:
    deadline = time.monotonic() + max(0.0, timeout_sec)
    marker_text = ""
    while time.monotonic() < deadline:
        observe_codex_app_server_goal_turn(turn, timeout_sec=0.0, raise_on_error=False)
        if marker_path.exists():
            marker_text = marker_path.read_text(encoding="utf-8").strip()
            try:
                marker_path.unlink()
                marker_deleted = True
            except OSError:
                marker_deleted = False
            observe_codex_app_server_goal_turn(
                turn,
                timeout_sec=min(2.0, max(0.0, poll_interval_sec)),
                raise_on_error=False,
            )
            return True, marker_text, marker_deleted
        if turn.turn_completed_observed:
            return False, "", False
        time.sleep(max(0.1, poll_interval_sec))
    observe_codex_app_server_goal_turn(turn, timeout_sec=0.0, raise_on_error=False)
    return False, "", False


def run_worker(args: argparse.Namespace) -> dict[str, Any]:
    prompt_path = Path(args.prompt_file).expanduser()
    work_dir = Path(args.work_dir).expanduser()
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("prompt file is empty")

    objective = args.objective or f"Complete SkillsBench task {args.task_id}"
    marker_path = _completion_marker_path(work_dir, prompt)
    work_dir.mkdir(parents=True, exist_ok=True)
    if marker_path.exists():
        marker_path.unlink()
    lifecycle_packet, lifecycle_contract = build_goal_harness_case_lifecycle_packet(args)
    effective_prompt = _prompt_with_goal_harness_case_lifecycle_packet(
        prompt,
        lifecycle_packet,
    )
    with_marker_prompt = _prompt_with_completion_marker(
        effective_prompt,
        marker_path.name,
    )
    marker_observed = False
    marker_deleted = False
    turn = start_codex_app_server_goal_turn(
        codex_bin=args.codex_bin,
        work_dir=work_dir,
        objective=objective,
        prompt=with_marker_prompt,
        model_name=args.model,
        reasoning_effort=args.reasoning_effort,
        approval_policy=args.approval_policy,
        sandbox=args.sandbox,
        response_timeout_sec=args.response_timeout_sec,
        wait_for_completion=False,
    )
    try:
        if not args.no_wait_for_completion:
            marker_observed, marker_text, marker_deleted = _wait_for_worker_completion_marker(
                turn,
                marker_path,
                timeout_sec=args.turn_timeout_sec,
            )
            if marker_text:
                turn.assistant_message = marker_text
            if not marker_observed and not turn.turn_completed_observed:
                raise TimeoutError(
                    "timed out waiting for app-server worker marker or turn completion"
                )
        compact = compact_turn_metadata(turn)
        compact.update(
            {
                "completion_hard_gate": False,
                "completion_marker_requested": True,
                "completion_marker_observed": marker_observed,
                "completion_marker_deleted": marker_deleted,
                "goal_harness_mode": args.goal_harness_mode,
                "goal_harness_access_packet_mode": args.goal_harness_access_packet_mode,
                "goal_harness_case_lifecycle_packet_injected": bool(lifecycle_packet),
                "benchmark_case_lifecycle_contract": lifecycle_contract,
            }
        )
        private_response_written = False
        if args.response_text_file and turn.assistant_message:
            response_path = Path(args.response_text_file).expanduser()
            response_path.parent.mkdir(parents=True, exist_ok=True)
            response_path.write_text(turn.assistant_message, encoding="utf-8")
            private_response_written = True
    finally:
        turn.terminate()
    ok = bool(compact.get("turn_id_present")) and (
        args.no_wait_for_completion
        or compact.get("turn_completed_observed") is True
        or marker_observed
    )
    return {
        "schema_version": "skillsbench_host_codex_goal_worker_result_v0",
        "ok": ok,
        "route": "codex-app-server-goal-baseline",
        "benchmark_id": args.dataset,
        "task_id": args.task_id,
        "goal_harness_mode": args.goal_harness_mode,
        "goal_harness_access_packet_mode": args.goal_harness_access_packet_mode,
        "goal_harness_case_lifecycle_packet_injected": bool(lifecycle_packet),
        "benchmark_case_lifecycle_contract": lifecycle_contract,
        "worker_contract": build_contract_payload(args),
        "prompt": {
            "sha256": stable_text_digest(prompt),
            "chars": len(prompt),
            "effective_sha256": stable_text_digest(with_marker_prompt),
            "effective_chars": len(with_marker_prompt),
            "raw_recorded": False,
        },
        "turn": compact,
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
    parser.add_argument(
        "--no-wait-for-completion",
        action="store_true",
        help=(
            "Return after turn/start instead of waiting for the temporary "
            "worker marker or turn/completed. Use only for external pollers; "
            "SkillsBench scored workers should wait and write a private "
            "response text file."
        ),
    )
    parser.add_argument(
        "--runner-integration-ready",
        action="store_true",
        help="Mark the surrounding BenchFlow worker integration as ready.",
    )
    parser.add_argument(
        "--goal-harness-mode",
        default="codex_goal_mode_baseline",
        help=(
            "Goal Harness benchmark arm mode. Use codex_goal_harness only for "
            "treatment runs that intentionally receive a case lifecycle packet."
        ),
    )
    parser.add_argument(
        "--goal-harness-access-packet-mode",
        default="none",
        help="Set to compact to inject the public-safe case lifecycle packet.",
    )
    parser.add_argument(
        "--goal-harness-case-id",
        default="",
        help="Public case id for the per-case/arm Goal Harness lifecycle contract.",
    )
    parser.add_argument(
        "--goal-harness-arm-id",
        default="codex_app_server_goal_baseline",
        help="Public arm id for the per-case/arm Goal Harness lifecycle contract.",
    )
    parser.add_argument(
        "--goal-harness-max-rounds",
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
        lifecycle_packet, lifecycle_contract = build_goal_harness_case_lifecycle_packet(
            args
        )
        payload.update(
            {
                "goal_harness_mode": args.goal_harness_mode,
                "goal_harness_access_packet_mode": args.goal_harness_access_packet_mode,
                "goal_harness_case_lifecycle_packet_injected": bool(lifecycle_packet),
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
