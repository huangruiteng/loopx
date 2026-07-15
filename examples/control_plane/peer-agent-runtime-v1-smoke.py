#!/usr/bin/env python3
"""Run the durable peer-agent runtime and migration contract suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKS = (
    "examples/control_plane/agent-identity-readmodel-smoke.py",
    "examples/control_plane/peer-agent-hard-cut-boundary-smoke.py",
    "examples/control_plane/quota-replan-decision-plane-smoke.py",
    "examples/control_plane/todo-continuation-policy-smoke.py",
    "examples/control_plane/peer-agent-migration-smoke.py",
    "examples/control_plane/peer-agent-workspace-guard-smoke.py",
    "examples/control_plane/quota-spend-workspace-causality-smoke.py",
    "examples/control_plane/peer-agent-continuation-state-machine-smoke.py",
    "examples/control_plane/task-orchestration-smoke.py",
    "examples/control_plane/agent-onboard-host-loop-activation-smoke.py",
)


def main() -> int:
    for check in CHECKS:
        subprocess.run(
            [sys.executable, check],
            cwd=REPO_ROOT,
            check=True,
        )
    print("peer-agent-runtime-v1-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
