#!/usr/bin/env python3
"""Compare a strong-model Turn baseline with Advisor plus cheaper execution."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_SCRIPT = REPO_ROOT / "examples" / "loopx-turn-codex-cli-e2e-smoke.py"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("turn count must be at least 1")
    return parsed


def _run_arm(
    *,
    real: bool,
    codex_bin: Path | None,
    model: str,
    advisor_model: str | None,
    turn_count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(E2E_SCRIPT),
        "--codex-model",
        model,
        "--turn-count",
        str(turn_count),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    if real:
        command.append("--real-codex-cli")
    if codex_bin is not None:
        command.extend(["--codex-bin", str(codex_bin)])
    if advisor_model:
        command.extend(["--advisor-model", advisor_model])
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(30.0, timeout_seconds * turn_count * (2 if advisor_model else 1) + 30.0),
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "exit_code": completed.returncode,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _quality_ok(arm: dict[str, Any], *, turn_count: int) -> bool:
    payload = arm["payload"]
    return bool(
        arm["exit_code"] == 0
        and payload.get("requested_turn_count") == turn_count
        and payload.get("committed_turn_count") == turn_count
        and payload.get("marker_valid") is True
        and payload.get("validation_status") == "passed"
        and payload.get("replay_exit_code") == 0
    )


def _usage(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("model_usage")
    return dict(usage) if isinstance(usage, dict) else {}


def _tokens(usage: dict[str, Any], phase: str = "total") -> int | None:
    row = usage.get(phase)
    if not isinstance(row, dict):
        return None
    value = row.get("total_tokens")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-model", required=True)
    parser.add_argument("--advisor-model", required=True)
    parser.add_argument("--executor-model", required=True)
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--turn-count", type=_positive_int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use the deterministic no-provider fixture instead of real Codex CLI calls.",
    )
    args = parser.parse_args()
    if args.advisor_model == args.executor_model:
        raise SystemExit("advisor and executor models must be distinct")

    baseline = _run_arm(
        real=not args.fixture,
        codex_bin=args.codex_bin,
        model=args.baseline_model,
        advisor_model=None,
        turn_count=args.turn_count,
        timeout_seconds=args.timeout_seconds,
    )
    advisor = _run_arm(
        real=not args.fixture,
        codex_bin=args.codex_bin,
        model=args.executor_model,
        advisor_model=args.advisor_model,
        turn_count=args.turn_count,
        timeout_seconds=args.timeout_seconds,
    )
    baseline_usage = _usage(baseline["payload"])
    advisor_usage = _usage(advisor["payload"])
    baseline_tokens = _tokens(baseline_usage)
    advisor_tokens = _tokens(advisor_usage)
    quality_ok = _quality_ok(baseline, turn_count=args.turn_count) and _quality_ok(
        advisor, turn_count=args.turn_count
    )
    usage_available = baseline_tokens is not None and advisor_tokens is not None
    token_delta = (
        advisor_tokens - baseline_tokens
        if baseline_tokens is not None and advisor_tokens is not None
        else None
    )
    token_reduction_ratio = (
        round((baseline_tokens - advisor_tokens) / baseline_tokens, 4)
        if baseline_tokens and advisor_tokens is not None
        else None
    )
    token_reduced = bool(usage_available and token_delta is not None and token_delta < 0)
    receipt = {
        "schema_version": "loopx_turn_advisor_qualification_v0",
        "real_codex_cli_invoked": not args.fixture,
        "turn_count": args.turn_count,
        "quality_ok": quality_ok,
        "usage_available": usage_available,
        "baseline": {
            "quality_ok": _quality_ok(baseline, turn_count=args.turn_count),
            "total_tokens": baseline_tokens,
        },
        "advisor": {
            "quality_ok": _quality_ok(advisor, turn_count=args.turn_count),
            "advisor_tokens": _tokens(advisor_usage, "advisor"),
            "executor_tokens": _tokens(advisor_usage, "executor"),
            "total_tokens": advisor_tokens,
        },
        "token_delta": token_delta,
        "token_reduction_ratio": token_reduction_ratio,
        "token_reduced": token_reduced,
        "raw_model_output_recorded": False,
        "automatic_promotion_allowed": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if quality_ok and token_reduced else 1


if __name__ == "__main__":
    raise SystemExit(main())
