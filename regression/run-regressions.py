#!/usr/bin/env python3
"""Run LoopX behavior regressions in safe contract-only mode."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Regression:
    path: str
    description: str


CONTRACT_ONLY_REGRESSIONS = (
    Regression(
        path="regression/cli-command-module-contract.py",
        description="modular CLI command seam preserves the public doctor invocation",
    ),
    Regression(
        path="regression/blocked-priority-fallback-contract.py",
        description="blocked P0 work stays visible while safe fallback work proceeds",
    ),
    Regression(
        path="regression/scoped-user-gate-fallback-contract.py",
        description="scoped user gates notify the user while non-dependent fallback work proceeds",
    ),
    Regression(
        path="regression/no-progress-self-repair-contract.py",
        description="two no-progress signals force autonomous self-repair before quiet waiting",
    ),
    Regression(
        path="regression/autonomous-replan-vs-dreaming-contract.py",
        description="dreaming proposals stay advisory gates while autonomous replan remains executable",
    ),
    Regression(
        path="regression/quota-executable-backlog-projection.py",
        description="quota selects executable backlog work over unchanged monitor context",
    ),
    Regression(
        path="regression/automation-loop-heartbeat-poll-contract.py",
        description="automation heartbeat polls stay bounded, compact, and spend only after writeback",
    ),
    Regression(
        path="regression/external-evidence-observation-real-codex.py",
        description="external evidence waits require observation; launched advancement work stays bounded delivery",
    ),
    Regression(
        path="regression/agentissue-lagent239-real-codex-runner.py",
        description="AgentIssue lagent_239 runner materializes public-safe boundaries",
    ),
    Regression(
        path="regression/codex-app-server-goal-baseline-contract.py",
        description="Codex Goal benchmark baselines require app-server goal-state evidence",
    ),
)


def main() -> int:
    failures: list[str] = []
    for regression in CONTRACT_ONLY_REGRESSIONS:
        script = REPO_ROOT / regression.path
        print(f"==> {regression.path}: {regression.description}", flush=True)
        result = subprocess.run([sys.executable, str(script)], cwd=REPO_ROOT)
        if result.returncode != 0:
            failures.append(f"{regression.path} exited {result.returncode}")

    if failures:
        for failure in failures:
            print(f"failed: {failure}", file=sys.stderr)
        return 1

    print(f"ok: {len(CONTRACT_ONLY_REGRESSIONS)} contract-only regression(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
