#!/usr/bin/env python3
"""Create Docker Compose-safe Terminal-Bench run ids."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "terminal_bench_safe_run_id_v0"
_INVALID_CHARS = re.compile(r"[^a-z0-9_-]+")
_DASH_RUNS = re.compile(r"-+")
_COMPOSE_PROJECT = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def sanitize_run_id(raw: str, *, max_length: int = 120) -> str:
    text = str(raw or "").strip().lower()
    text = _INVALID_CHARS.sub("-", text)
    text = _DASH_RUNS.sub("-", text).strip("-_")
    if not text or not text[0].isalnum():
        text = f"tb-{text}" if text else "tb-run"
    if len(text) > max_length:
        text = text[:max_length].rstrip("-_")
    if not text or not text[0].isalnum():
        text = "tb-run"
    return text


def build_plan(
    *,
    run_id: str | None,
    prefix: str,
    timestamp_utc: str | None,
    max_length: int,
) -> dict[str, Any]:
    raw = run_id
    generated_timestamp = False
    if not raw:
        stamp = timestamp_utc
        if not stamp:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
            generated_timestamp = True
        raw = f"{prefix}-{stamp}"
    safe = sanitize_run_id(raw, max_length=max_length)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(_COMPOSE_PROJECT.fullmatch(safe)),
        "first_blocker": ""
        if _COMPOSE_PROJECT.fullmatch(safe)
        else "terminal_bench_safe_run_id_invalid_after_sanitize",
        "safe_run_id": safe,
        "changed": safe != raw,
        "raw_run_id_chars": len(raw),
        "safe_run_id_chars": len(safe),
        "generated_timestamp": generated_timestamp,
        "compose_project_name_safe": bool(_COMPOSE_PROJECT.fullmatch(safe)),
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "private_paths_recorded": False,
        },
        "contract": {
            "terminal_bench_run_id_lowercase": True,
            "docker_compose_project_name_safe": True,
            "score_or_task_behavior_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize a Terminal-Bench run id so it can be reused as a Docker "
            "Compose project/container prefix."
        )
    )
    parser.add_argument("--run-id")
    parser.add_argument("--prefix", default="terminal-bench-run")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--max-length", type=int, default=120)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_plan(
        run_id=args.run_id,
        prefix=args.prefix,
        timestamp_utc=args.timestamp_utc,
        max_length=args.max_length,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
