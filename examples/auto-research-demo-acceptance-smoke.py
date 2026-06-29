#!/usr/bin/env python3
"""Smoke-test the auto-research operator demo acceptance packet."""

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
    AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION,
    build_auto_research_board_projection,
    build_auto_research_demo_acceptance_packet,
    build_auto_research_demo_supervisor_plan,
    build_auto_research_projection,
    load_auto_research_fixture,
)


FIXTURE = REPO_ROOT / "examples/fixtures/decentralized-auto-research-knn.public.json"
GOAL_ID = "loopx-auto-research-knn"
AGENT_ID = "codex-side-bypass"
LANES = [
    "codex-side-bypass:hypothesis-runner",
    "codex-product-capability:evidence-promoter",
    "codex-main-control:control-plane-guard",
]


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
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


def assert_acceptance_packet(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION, payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["surface"]["stage"] == "experimental", payload
    assert payload["surface"]["first_screen_policy"] == (
        "experimental_only_not_first_screen_without_owner_review"
    ), payload
    assert payload["readiness_summary"]["operator_can_review_now"] is True, payload
    assert payload["readiness_summary"]["ready_for_real_launch"] is True, payload
    assert payload["readiness_summary"]["ready_for_public_first_screen"] is False, payload
    assert payload["board_output"]["read_only"] is True, payload
    assert payload["board_output"]["source_kind"] == "public_fixture", payload
    assert payload["board_output"]["promotion_candidate_count"] >= 1, payload
    assert payload["board_output"]["user_gate_count"] >= 4, payload
    assert payload["supervisor_rehearsal"]["mode"] == "dry_run", payload
    assert payload["supervisor_rehearsal"]["lane_count"] == 3, payload
    assert payload["supervisor_rehearsal"]["rehearsal_script_visible"] is True, payload
    assert payload["supervisor_rehearsal"]["start_script_visible"] is True, payload
    assert payload["supervisor_rehearsal"]["attach"] == "tmux attach -t loopx-auto-research", payload
    assert payload["supervisor_rehearsal"]["stop"] == "tmux kill-session -t loopx-auto-research", payload
    assert [lane["lane_id"] for lane in payload["lane_checks"]] == [
        "hypothesis-runner",
        "evidence-promoter",
        "control-plane-guard",
    ], payload
    for lane in payload["lane_checks"]:
        assert lane["role_profile_visible"] is True, lane
        assert lane["role_id"] != "missing_role", lane
        assert lane["phase"] != "missing_phase", lane
        assert lane["required_skill"] == "loopx-auto-research", lane
        assert lane["quota_guard_visible"] is True, lane
        assert lane["frontier_visible"] is True, lane
        assert lane["bootstrap_visible"] is True, lane
        assert lane["visible_codex_tui"] == "codex", lane
    checklist = "\n".join(payload["operator_checklist"])
    assert "dry-run rehearsal" in checklist, checklist
    assert "role_profile_v0" in checklist, checklist
    assert "quota should-run" in checklist, checklist
    assert "attach and stop" in checklist, checklist
    assert payload["accept_when"], payload
    assert payload["reject_when"], payload
    controls = "\n".join(payload["user_takeover"]["operator_controls"])
    assert "rehearsal script first" in controls, controls
    assert "attach to tmux" in controls, controls
    boundary = payload["public_boundary"]
    assert boundary["raw_logs_recorded"] is False, boundary
    assert boundary["private_artifacts_recorded"] is False, boundary
    assert boundary["local_paths_recorded"] is False, boundary
    assert boundary["credentials_recorded"] is False, boundary
    assert boundary["starts_tmux"] is False, boundary
    assert boundary["runs_codex"] is False, boundary
    assert boundary["writes_loopx_state"] is False, boundary
    assert boundary["spends_loopx_quota"] is False, boundary
    assert_public_safe(payload)


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    projection = build_auto_research_projection(
        load_auto_research_fixture(FIXTURE),
        agent_id=AGENT_ID,
    )
    board = build_auto_research_board_projection(projection)
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
        agent_specs=LANES,
    )
    packet = build_auto_research_demo_acceptance_packet(board, supervisor)
    assert_acceptance_packet(packet)

    cli = run_cli(
        [
            "--format",
            "json",
            "auto-research",
            "acceptance",
            "--fixture",
            str(FIXTURE),
            "--agent-id",
            AGENT_ID,
            "--agent",
            LANES[0],
            "--agent",
            LANES[1],
            "--agent",
            LANES[2],
        ]
    )
    cli_payload = json.loads(cli.stdout)
    assert_acceptance_packet(cli_payload)

    markdown = run_cli(
        [
            "auto-research",
            "acceptance",
            "--fixture",
            str(FIXTURE),
            "--agent-id",
            AGENT_ID,
            "--agent",
            LANES[0],
        ]
    ).stdout
    assert "# LoopX Auto Research Demo Acceptance" in markdown, markdown
    assert "ready_for_real_launch: `True`" in markdown, markdown
    assert "ready_for_public_first_screen: `False`" in markdown, markdown
    assert "## Operator Checklist" in markdown, markdown
    assert "## User Takeover" in markdown, markdown
    assert "tmux attach -t loopx-auto-research" in markdown, markdown
    assert_public_safe(markdown)

    print("auto-research-demo-acceptance-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
