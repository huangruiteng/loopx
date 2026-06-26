#!/usr/bin/env python3
"""Smoke-test the SkillsBench goal-start product-mode route plan surface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--route",
            "loopx-goal-start-product-mode",
            "--task-id",
            "planning-granularity",
            "--plan-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["plan_only"] is True, payload
    plan = payload["launch_plan"]
    assert plan["route"] == "loopx-goal-start-product-mode", plan
    assert plan["rollout_name"].endswith("__loopx_goal_start_product_mode"), plan
    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["goal_start_product_mode"] is True, prerequisites
    assert prerequisites["goal_start_plan_required"] is True, prerequisites
    assert prerequisites["goal_start_planned_todo_count_expected"] == 3, prerequisites
    assert prerequisites["goal_start_selected_p0_lifecycle_required"] is True, prerequisites
    assert prerequisites["benchflow_intermediate_soft_verify_policy"] == "every-round"
    assert plan["public_boundary"]["public_raw_prompt"] is False, plan
    assert plan["public_boundary"]["public_raw_trajectory"] is False, plan
    print("skillsbench-goal-start-product-mode-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
