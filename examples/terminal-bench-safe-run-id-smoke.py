#!/usr/bin/env python3
"""Smoke-test Terminal-Bench safe run-id normalization."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "terminal_bench_safe_run_id.py"


def main() -> int:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--run-id",
            "Build-Cython-Ext-Host-Codex-Goal-R5-20260620T140515Z",
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload
    assert payload["changed"] is True, payload
    assert payload["safe_run_id"] == (
        "build-cython-ext-host-codex-goal-r5-20260620t140515z"
    )
    assert payload["compose_project_name_safe"] is True, payload
    assert payload["contract"]["docker_compose_project_name_safe"] is True, payload
    assert payload["boundary"]["raw_task_text_read"] is False, payload

    generated = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prefix",
            "Build_Cython",
            "--timestamp-utc",
            "20260620T140515Z",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    generated_payload = json.loads(generated.stdout)
    assert generated_payload["safe_run_id"] == "build_cython-20260620t140515z"
    assert generated_payload["generated_timestamp"] is False

    print("terminal-bench safe run-id smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
