#!/usr/bin/env python3
"""Smoke-test the dry-run auto-research demo supervisor packet."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research import (  # noqa: E402
    AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
    build_auto_research_demo_supervisor_plan,
)


GOAL_ID = "loopx-auto-research-knn"
LANES = [
    "codex-side-bypass:hypothesis-runner",
    "codex-product-capability:evidence-promoter",
    "codex-main-control:control-plane-guard",
]


def assert_no_private_surface(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http" + "://",
        "https" + "://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_supervisor_contract(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION, payload
    assert payload["mode"] == "dry_run", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["coordination_model"]["leader_agent_required"] is False, payload
    assert payload["coordination_model"]["supervisor_role"] == "host_shell_layout_only", payload

    lanes = payload["lanes"]
    assert [lane["lane_id"] for lane in lanes] == [
        "hypothesis-runner",
        "evidence-promoter",
        "control-plane-guard",
    ], payload
    for lane in lanes:
        assert "quota should-run" in lane["quota_guard"], lane
        assert f"--agent-id {lane['agent_id']}" in lane["quota_guard"], lane
        assert "auto-research frontier" in lane["frontier"], lane
        assert "codex-cli-bootstrap-message" in lane["bootstrap_message"], lane
        assert lane["visible_codex_tui"] == "codex", lane
        phases = [item["phase"] for item in lane["lane_timeline"]]
        assert phases == [
            "quota_guard",
            "frontier_projection",
            "bootstrap_prompt",
            "visible_codex",
        ], lane
        assert lane["lane_timeline"][0]["command_ref"] == "quota_guard", lane
        assert "operator is attached" in lane["lane_timeline"][-1]["continue_when"], lane

    start_script = "\n".join(payload["commands"]["start_script"])
    assert "tmux new-session" in start_script, start_script
    assert "tmux new-window" in start_script, start_script
    assert "LOOPX_PROJECT" in start_script, start_script
    assert "codex-cli-bootstrap-message" in start_script, start_script
    assert "auto-research frontier" in start_script, start_script
    assert payload["commands"]["attach"] == "tmux attach -t loopx-auto-research", payload

    one_click = payload["one_click_demo"]
    assert one_click["schema_version"] == "auto_research_one_click_demo_v0", payload
    assert one_click["mode"] == "copy_paste_dry_run_rehearsal", payload
    assert one_click["default_safe"] is True, payload
    rehearsal = "\n".join(one_click["script"])
    assert "dry-run rehearsal only" in rehearsal, rehearsal
    assert "does not start tmux" in rehearsal, rehearsal
    assert "LOOPX_PROJECT" in rehearsal, rehearsal
    assert "start script - inspect before pasting" in rehearsal, rehearsal
    assert "tmux new-session" in rehearsal, rehearsal
    assert "tmux attach -t loopx-auto-research" in rehearsal, rehearsal
    assert "tmux kill-session -t loopx-auto-research" in rehearsal, rehearsal
    assert "start tmux" in one_click["does_not"], one_click
    assert "launch Codex" in one_click["does_not"], one_click

    acceptance = payload["demo_acceptance"]
    assert acceptance["schema_version"] == "auto_research_demo_acceptance_v0", payload
    assert "lanes[].lane_timeline" in acceptance["required_visible_fields"], acceptance
    assert any("without executing it" in item for item in acceptance["operator_can_accept_when"]), acceptance
    assert any("hides attach/stop" in item for item in acceptance["operator_must_reject_when"]), acceptance

    takeover = payload["user_takeover"]
    assert takeover["schema_version"] == "auto_research_user_takeover_v0", payload
    assert any("rehearsal script first" in item for item in takeover["operator_controls"]), takeover
    assert any("attach to tmux" in item for item in takeover["operator_controls"]), takeover
    assert any("quota guard" in item for item in takeover["visible_status_cues"]), takeover

    boundary = payload["boundary"]
    assert boundary["dry_run_plan_only"] is True, payload
    assert boundary["starts_tmux"] is False, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert payload["future_gates"][0]["capability"] == "execute_start_script", payload
    assert_no_private_surface(payload)


def run_cli_json() -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "demo-supervisor",
            "--goal-id",
            GOAL_ID,
            "--agent",
            LANES[0],
            "--agent",
            LANES[1],
            "--agent",
            LANES[2],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    payload = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
        agent_specs=LANES,
    )
    assert_supervisor_contract(payload)

    cli_payload = run_cli_json()
    assert_supervisor_contract(cli_payload)

    markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "auto-research",
            "demo-supervisor",
            "--goal-id",
            GOAL_ID,
            "--agent",
            LANES[0],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "# LoopX Auto Research Demo Supervisor" in markdown, markdown
    assert "leader_agent_required: `False`" in markdown, markdown
    assert "## Lane Timeline" in markdown, markdown
    assert "`quota_guard` via `quota_guard`" in markdown, markdown
    assert "## One-Click Dry Run" in markdown, markdown
    assert "copy_paste_dry_run_rehearsal" in markdown, markdown
    assert "## User Takeover" in markdown, markdown
    assert "## Visible Status Cues" in markdown, markdown
    assert "## Demo Acceptance" in markdown, markdown
    assert "accept when:" in markdown, markdown
    assert "tmux attach -t loopx-auto-research" in markdown, markdown

    print("auto-research-demo-supervisor-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
