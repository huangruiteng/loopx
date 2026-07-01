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

from loopx.capabilities.auto_research.legacy_core import (  # noqa: E402
    AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
    build_auto_research_demo_supervisor_plan,
)


GOAL_ID = "loopx-auto-research-knn"
LANES = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
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
    assert "quota_should_run" in payload["coordination_model"]["source_of_truth"], payload
    surface = payload["goal_surface"]
    assert surface["schema_version"] == "auto_research_shared_goal_surface_v0", surface
    assert surface["shared_goal_id"] == GOAL_ID, surface
    assert surface["lane_count"] == 4, surface
    assert surface["lane_ids"] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
        "evidence-verifier",
    ], surface
    assert surface["uses_default_lanes"] is False, surface
    assert surface["default_lane_count"] == 3, surface
    assert surface["shared_frontier"] is True, surface
    assert surface["all_lane_workspace_isolation"] is False, surface
    assert "mutating evidence-runner attempts" in surface["mutation_isolation_policy"], surface
    assert surface["explicit_agent_override"] is True, surface

    lanes = payload["lanes"]
    assert [lane["lane_id"] for lane in lanes] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
        "evidence-verifier",
    ], payload
    assert [lane["role_id"] for lane in lanes] == [
        "research_curator",
        "hypothesis_mapper",
        "evidence_runner",
        "evidence_verifier",
    ], payload
    for lane in lanes:
        profile = lane["role_profile"]
        assert profile["schema_version"] == "auto_research_role_profile_v0", profile
        assert profile["goal_id"] == GOAL_ID, profile
        assert profile["agent_id"] == lane["agent_id"], profile
        assert profile["lane_id"] == lane["lane_id"], profile
        assert profile["role_id"] == lane["role_id"], profile
        assert profile["required_skill"] == "loopx-auto-research", profile
        assert profile["skill_distribution"] == "worker_local", profile
        assert profile["worker_skill_source"].endswith("auto_research/worker_skill/SKILL.md"), profile
        assert profile["phase"], profile
        assert profile["allowed_actions"], profile
        assert profile["skill_section"], profile
        assert profile["write_scope"], profile
        assert profile["protected_scope"], profile
        assert profile["stop_conditions"], profile
        assert profile["takeover_controls"], profile
        assert profile["pane_title_is_authority"] is False, profile
        assert "quota should-run" in lane["quota_guard"], lane
        assert f"--agent-id {lane['agent_id']}" in lane["quota_guard"], lane
        assert "auto-research frontier" in lane["frontier"], lane
        assert "You are a visible LoopX auto-research lane" in lane["bootstrap_message"], lane
        assert "Do not run loopx bootstrap-command-pack" in lane["bootstrap_message"], lane
        assert "codex-cli-bootstrap-message" not in lane["bootstrap_message"], lane
        assert "Minimal live worker-turn path" in lane["bootstrap_message"], lane
        assert "auto-research worker-turn" in lane["bootstrap_message"], lane
        assert "--complete-selected-todo" in lane["bootstrap_message"], lane
        assert "$LOOPX_PANE_LOOPX" in lane["bootstrap_message"], lane
        assert "[LoopX role profile]" in lane["visible_launch_command"], lane
        assert "[LoopX visible acceptance]" in lane["visible_launch_command"], lane
        assert "LOOPX_GOAL_ID" in lane["visible_launch_command"], lane
        assert "LOOPX_VISIBLE_BOOTSTRAP_PAUSE_SECONDS" in lane["visible_launch_command"], lane
        assert "LOOPX_ROLE_PROFILE_JSON" in lane["visible_launch_command"], lane
        assert "LOOPX_ROLE_PROFILE_PATH" in lane["visible_launch_command"], lane
        assert "role_profile_artifact=%s.public.json" in lane["visible_launch_command"], lane
        assert "role_profile_path=%s" not in lane["visible_launch_command"], lane
        assert "LOOPX_REQUIRED_SKILL" in lane["visible_launch_command"], lane
        assert "bootstrap-or-stop" in lane["visible_launch_command"], lane
        assert lane["visible_codex_tui"] == "codex", lane
        phases = [item["phase"] for item in lane["lane_timeline"]]
        assert phases == [
            "role_profile",
            "quota_guard",
            "frontier_projection",
            "bootstrap_prompt",
            "visible_codex",
        ], lane
        assert lane["lane_timeline"][0]["command_ref"] == "role_profile", lane
        assert lane["lane_timeline"][1]["command_ref"] == "quota_guard", lane
        assert "operator is attached" in lane["lane_timeline"][-1]["continue_when"], lane
    expected_action_hints = {
        "research_curator": "`write_research_contract`",
        "hypothesis_mapper": "`propose_hypothesis`",
        "evidence_runner": "`run_dev_eval` or `write_evidence`",
        "evidence_verifier": "`run_holdout_eval`, `classify_evidence`, or `write_evaluation_summary`",
    }
    for lane in lanes:
        assert expected_action_hints[lane["role_id"]] in lane["bootstrap_message"], lane

    start_script = "\n".join(payload["commands"]["start_script"])
    assert "tmux new-session" in start_script, start_script
    assert "tmux new-window" in start_script, start_script
    assert "LOOPX_PROJECT" in start_script, start_script
    assert "[Codex bootstrap]" in start_script, start_script
    assert "bootstrap_prompt_artifact" in start_script, start_script
    assert "[Codex bootstrap prompt]" not in start_script, start_script
    assert "You are a visible LoopX auto-research lane" in start_script, start_script
    assert "codex-cli-bootstrap-message" not in start_script, start_script
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
    assert "launch posture" in rehearsal, rehearsal
    assert "demo-e2e --execute" in rehearsal, rehearsal
    assert "machine JSON/artifacts" in rehearsal, rehearsal
    assert "start script - inspect before pasting" not in rehearsal, rehearsal
    assert "tmux new-session" not in rehearsal, rehearsal
    assert "LOOPX_ROLE_PROFILE_JSON" not in rehearsal, rehearsal
    assert "tmux attach -t loopx-auto-research" in rehearsal, rehearsal
    assert "tmux kill-session -t loopx-auto-research" in rehearsal, rehearsal
    assert "prints the real one-command launch posture" in " ".join(
        one_click["expected_visible_result"]
    ), one_click
    assert "start tmux" in one_click["does_not"], one_click
    assert "launch Codex" in one_click["does_not"], one_click

    acceptance = payload["demo_acceptance"]
    assert acceptance["schema_version"] == "auto_research_demo_acceptance_v0", payload
    assert "commands.start_script" not in acceptance["required_visible_fields"], acceptance
    assert "lanes[].role_profile" in acceptance["required_visible_fields"], acceptance
    assert "lanes[].lane_timeline" in acceptance["required_visible_fields"], acceptance
    assert any("role_profile_v0" in item for item in acceptance["operator_can_accept_when"]), acceptance
    assert any("launch posture" in item for item in acceptance["operator_can_accept_when"]), acceptance
    assert any("role_profile_v0" in item for item in acceptance["operator_must_reject_when"]), acceptance
    assert any("hides attach/stop" in item for item in acceptance["operator_must_reject_when"]), acceptance

    takeover = payload["user_takeover"]
    assert takeover["schema_version"] == "auto_research_user_takeover_v0", payload
    assert any("rehearsal script first" in item for item in takeover["operator_controls"]), takeover
    assert any("start_script is machine-bound" in item for item in takeover["operator_controls"]), takeover
    assert any("attach to tmux" in item for item in takeover["operator_controls"]), takeover
    assert any("role_profile_v0" in item for item in takeover["visible_status_cues"]), takeover
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
    assert boundary["shared_goal_surface"] is True, payload
    assert boundary["all_lane_workspace_isolation"] is False, payload
    assert "mutating evidence-runner attempts" in boundary["mutation_isolation_policy"], payload
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
            "--agent",
            LANES[3],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    default_payload = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
    )
    assert [lane["agent_id"] for lane in default_payload["lanes"]] == [
        "codex-product-capability",
        "codex-side-bypass",
        "codex-main-control",
    ], default_payload
    assert [lane["lane_id"] for lane in default_payload["lanes"]] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
    ], default_payload
    assert default_payload["goal_surface"]["lane_count"] == 3, default_payload
    assert default_payload["goal_surface"]["lane_ids"] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
    ], default_payload
    assert default_payload["goal_surface"]["uses_default_lanes"] is True, default_payload
    assert default_payload["goal_surface"]["default_lane_count"] == 3, default_payload
    assert default_payload["goal_surface"]["default_lane_ids"] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
    ], default_payload
    assert "codex-value-explorer" not in json.dumps(default_payload), default_payload

    payload = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
        agent_specs=LANES,
    )
    assert_supervisor_contract(payload)

    try:
        build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=["codex-main-control:evidence-runner:not_a_role"],
        )
    except ValueError as exc:
        assert "role_id must be one of" in str(exc), exc
    else:
        raise AssertionError("explicit invalid role_id must not silently fallback")

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
    assert "## Role Profiles" in markdown, markdown
    assert "loopx-auto-research" in markdown, markdown
    assert "## Lane Timeline" in markdown, markdown
    assert "required_worker_playbook: `loopx-auto-research`" in markdown, markdown
    assert "skill_distribution: `worker_local`" in markdown, markdown
    assert "worker_skill_source: `loopx/capabilities/auto_research/worker_skill/SKILL.md`" in markdown, markdown
    assert "`role_profile` via `role_profile`" in markdown, markdown
    assert "`quota_guard` via `quota_guard`" in markdown, markdown
    assert "## One-Click Dry Run" in markdown, markdown
    assert "copy_paste_dry_run_rehearsal" in markdown, markdown
    assert "## User Takeover" in markdown, markdown
    assert "## Visible Status Cues" in markdown, markdown
    assert "## Demo Acceptance" in markdown, markdown
    assert "accept when:" in markdown, markdown
    assert "tmux attach -t loopx-auto-research" in markdown, markdown
    assert "start_script: `machine_json_only`" in markdown, markdown
    assert "loopx auto-research demo-e2e --execute" in markdown, markdown
    assert "tmux new-session" not in markdown, markdown
    assert "LOOPX_ROLE_PROFILE_JSON" not in markdown, markdown

    print("auto-research-demo-supervisor-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
