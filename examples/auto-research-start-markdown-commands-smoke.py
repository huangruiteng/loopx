#!/usr/bin/env python3
"""Smoke-test operator commands in auto-research start Markdown output."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTION = "How should LoopX make visible multi-agent auto research useful?"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.human_view import (  # noqa: E402
    render_auto_research_markdown,
)
from loopx.capabilities.auto_research.user_contract import (  # noqa: E402
    build_auto_research_user_contract,
)


def require(needle: str, text: str) -> None:
    assert needle in text, f"missing {needle!r}\n{text}"


def forbid(needle: str, text: str) -> None:
    assert needle not in text, f"unexpected {needle!r}\n{text}"


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "auto-research",
            "start",
            QUESTION,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    markdown = result.stdout
    require("## Operator Commands", markdown)
    require("## Minimal A2A Recipe", markdown)
    require("- user_plus_preset_lines: `5`", markdown)
    require("- shared_kernel_counted: `False`", markdown)
    require(
        "- preset_role: hypothesis-proposer / 假设生成",
        markdown,
    )
    require(
        f"- evidence-first start: `loopx auto-research start '{QUESTION}' --execute`",
        markdown,
    )
    require(
        f"- immediate takeover: `loopx auto-research start '{QUESTION}' --execute --attach`",
        markdown,
    )
    require("--attach means operator takeover first", markdown)
    forbid("--no-wake-visible-after-launch", markdown)
    forbid("- tmux attach:", markdown)

    payload = {
        "ok": True,
        "schema_version": "auto_research_demo_e2e_result_v0",
        "mode": "execute",
        "execution_kind": "visible_worker_launch",
        "result_source": "visible_worker_launcher",
        "goal_id": "loopx-auto-research-markdown-smoke",
        "tracking_goal_id": None,
        "route_contract": {"frontier_goal_id": "loopx-auto-research-markdown-smoke"},
        "agent_id": "auto-research-operator",
        "reasoning_effort": "high",
        "user_contract": build_auto_research_user_contract(QUESTION),
        "contract_acceptance": {"accepted": True},
        "commands": {},
        "supervisor": {"lane_count": 4},
        "visible_worker_proof": {
            "visible_lanes_launched": True,
            "visible_lanes_accepted": True,
        },
        "visible_pane_a2a_rounds": {},
        "visible_readiness": {},
        "visible_launch": {
            "launch_result": {
                "attach_command": "tmux attach -t loopx-auto-research",
                "stop_command": "tmux kill-session -t loopx-auto-research",
            }
        },
    }
    launched = render_auto_research_markdown(payload)
    require("- tmux attach: `tmux attach -t loopx-auto-research`", launched)
    require("- tmux stop: `tmux kill-session -t loopx-auto-research`", launched)
    forbid("--no-wake-visible-after-launch", launched)

    print("auto-research-start-markdown-commands-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
