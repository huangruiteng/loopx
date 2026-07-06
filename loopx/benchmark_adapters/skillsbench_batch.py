"""SkillsBench batch runner helpers."""

from __future__ import annotations

import argparse
import asyncio
import re
import time
from typing import Any


BATCH_CASE_INTERNAL_ARG_KEYS = frozenset(
    {
        "apt_risk_fail_fast_defaulted",
        "bootstrap_light_fail_fast_defaulted",
        "update_current_aggregate",
        "verifier_bootstrap_fail_fast_defaulted",
    }
)


def split_task_ids_arg(value: str | None) -> list[str]:
    return [part for part in re.split(r"[,\s]+", value or "") if part]


def safe_batch_suffix(task_id: str, index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", task_id).strip("-")
    return f"{index + 1:02d}-{slug or 'task'}"


def batch_task_ids(args: argparse.Namespace) -> list[str]:
    return split_task_ids_arg(getattr(args, "task_ids", None)) or [
        str(args.task_id)
    ]


def clone_args_for_batch_case(
    args: argparse.Namespace,
    *,
    task_id: str,
    index: int,
    total: int,
    run_group_id: str,
) -> argparse.Namespace:
    case_args = argparse.Namespace(**vars(args))
    case_args.task_id = task_id
    case_args.task_ids = None
    case_args.run_group_id = run_group_id
    if total > 1:
        suffix = safe_batch_suffix(task_id, index)
        if args.job_name:
            case_args.job_name = f"{args.job_name}-{suffix}"
        if args.rollout_name:
            case_args.rollout_name = f"{args.rollout_name}-{suffix}"
    return case_args


def batch_case_args_to_cli(case_args: argparse.Namespace) -> list[str]:
    cli: list[str] = []
    for key, value in sorted(vars(case_args).items()):
        if key == "task_ids":
            continue
        if key in BATCH_CASE_INTERNAL_ARG_KEYS:
            continue
        if (
            key == "fail_fast_on_apt_risk"
            and getattr(case_args, "apt_risk_fail_fast_defaulted", False)
        ):
            continue
        if (
            key == "fail_fast_on_verifier_bootstrap_risk"
            and getattr(case_args, "verifier_bootstrap_fail_fast_defaulted", False)
        ):
            continue
        option = "--" + key.replace("_", "-")
        if key == "parallel_cases":
            value = 1
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                cli.append(option)
            continue
        cli.extend([option, str(value)])
    return cli


def parallel_batch_requires_subprocess_isolation(parallel_cases: int) -> bool:
    return parallel_cases > 1


class BatchCaseStartPacer:
    """Enforce a minimum gap between starts in a batch run."""

    def __init__(self, start_gap_sec: float | int | None) -> None:
        self.start_gap_sec = max(0.0, float(start_gap_sec or 0.0))
        self._lock = asyncio.Lock()
        self._last_start_monotonic: float | None = None

    async def wait_for_slot(self) -> float:
        if self.start_gap_sec <= 0:
            return 0.0
        async with self._lock:
            wait_sec = 0.0
            now = time.monotonic()
            if self._last_start_monotonic is not None:
                wait_sec = max(
                    0.0,
                    self._last_start_monotonic + self.start_gap_sec - now,
                )
                if wait_sec > 0:
                    await asyncio.sleep(wait_sec)
            self._last_start_monotonic = time.monotonic()
            return wait_sec

    def annotate_payload(
        self,
        payload: dict[str, Any],
        wait_sec: float,
    ) -> dict[str, Any]:
        if self.start_gap_sec > 0:
            payload["batch_case_start_gap_sec"] = self.start_gap_sec
            payload["batch_case_start_wait_sec"] = wait_sec
        return payload
