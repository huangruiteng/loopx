#!/usr/bin/env python3
"""Smoke-test the one-command auto-research positive demo path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-knn"
TRACKING_GOAL_ID = "loopx-meta"
AGENT_ID = "codex-side-bypass"
GUIDE = REPO_ROOT / "docs" / "guides" / "auto-research-command-path.md"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(args: list[str], *, registry: Path, runtime_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            *args,
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def assert_e2e_payload(
    payload: dict[str, Any],
    *,
    executed: bool,
    tracking_goal_id: str | None = None,
) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "auto_research_demo_e2e_result_v0", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["tracking_goal_id"] == tracking_goal_id, payload
    route = payload["route_contract"]
    assert route["schema_version"] == "auto_research_demo_frontier_route_v0", payload
    assert route["frontier_goal_id"] == GOAL_ID, payload
    assert route["visible_lanes_read_goal_id"] == GOAL_ID, payload
    assert route["tracking_goal_id"] == tracking_goal_id, payload
    assert route["tracking_goal_drives_frontier"] is False, payload
    assert route["dedicated_positive_demo_frontier"] is True, payload
    assert payload["agent_id"] == AGENT_ID, payload
    assert payload["reasoning_effort"] == "high", payload
    assert payload["execution_kind"] in {
        "deterministic_replay",
        "deterministic_replay_preview",
    }, payload
    assert payload["result_source"] == "generated_quickstart_pack_protected_eval_replay", payload
    live = payload["live_codex_e2e"]
    assert live["executed"] is False, payload
    assert live["claim_allowed"] is False, payload
    assert live["evidence_source"] == "not_collected_from_codex_lane_output", payload
    assert payload["supervisor"]["lane_count"] == 3, payload
    assert payload["supervisor"]["reasoning_contract"]["default_reasoning_effort"] == "high", payload
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    assert payload["public_boundary"]["private_artifacts_recorded"] is False, payload
    assert payload["public_boundary"]["absolute_paths_recorded"] is False, payload
    assert payload["public_boundary"]["credentials_recorded"] is False, payload
    assert payload["public_boundary"]["local_workspace_path_redacted"] is True, payload
    assert payload["public_boundary"]["live_codex_sessions_recorded"] is False, payload
    replay = payload["replay_result"]
    assert replay["executed"] is executed, payload
    if executed:
        assert replay["result_source"] == "generated_quickstart_pack_protected_eval_replay", payload
        assert replay["status"] == "supported", payload
        assert replay["dev_metric"] == 4.0, payload
        assert replay["holdout_metric"] == 4.5, payload
        assert replay["dev_exact"] is True, payload
        assert replay["holdout_exact"] is True, payload
        assert replay["protected_scope_clean"] is True, payload
        assert payload["append"]["appended_count"] == 3, payload
        assert payload["append"]["counts_by_kind"] == {
            "research_evidence": 2,
            "research_hypothesis": 1,
        }, payload
        assert payload["board"]["rollout_backed"] is True, payload
        claim_boundary = payload["board"]["claim_boundary"]
        assert claim_boundary["schema_version"] == "auto_research_public_claim_boundary_v0", payload
        assert claim_boundary["metric_source_kind"] == "loopx_rollout_event_log", payload
        assert claim_boundary["claim_source"] == "live_codex_e2e", payload
        assert claim_boundary["live_claim_scope"] == "dev_only", payload
        assert claim_boundary["holdout_result_scope"] == "rollout_context_only", payload
        assert claim_boundary["holdout_claim_allowed"] is False, payload
        assert claim_boundary["promotion_claim_allowed"] is False, payload
        assert claim_boundary["first_screen_claim_allowed"] is False, payload
        labels = [item["label"] for item in payload["board"]["value_metrics"]]
        assert "Rollout held-out context" in labels, labels
        assert "Held-out result" not in labels, labels
        assert payload["board"]["promotion_candidate_count"] >= 1, payload
        assert payload["acceptance"]["ready_for_real_launch"] is True, payload
        assert payload["acceptance"]["claim_boundary"]["live_claim_scope"] == "dev_only", payload
        assert payload["acceptance"]["claim_boundary"]["promotion_claim_allowed"] is False, payload
    else:
        assert replay["result_source"] == "deterministic_replay_preview", payload
        assert replay["expected_positive_result"] == "dev=4.0x holdout=4.5x after --execute", payload
    assert_public_safe(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        dry_run = run_cli(
            [
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
            ],
            registry=registry,
            runtime_root=runtime_root,
        )
        assert_e2e_payload(json.loads(dry_run.stdout), executed=False)

        executed = run_cli(
            [
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--tracking-goal-id",
                TRACKING_GOAL_ID,
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
        )
        executed_payload = json.loads(executed.stdout)
        assert_e2e_payload(executed_payload, executed=True, tracking_goal_id=TRACKING_GOAL_ID)
        replay_command = executed_payload["commands"]["deterministic_replay"]
        visible_command = executed_payload["commands"]["deterministic_replay_with_visible_lanes"]
        assert f"--goal-id {GOAL_ID}" in replay_command, replay_command
        assert f"--goal-id {GOAL_ID}" in visible_command, visible_command
        assert f"--tracking-goal-id {TRACKING_GOAL_ID}" in replay_command, replay_command
        assert f"--tracking-goal-id {TRACKING_GOAL_ID}" in visible_command, visible_command

        markdown = run_cli(
            [
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
            ],
            registry=registry,
            runtime_root=runtime_root,
        ).stdout
        assert "# LoopX Auto Research Demo Replay" in markdown, markdown
        assert "execution_kind: `deterministic_replay_preview`" in markdown, markdown
        assert "frontier_goal_id: `loopx-auto-research-knn`" in markdown, markdown
        assert "tracking_goal_drives_frontier: `False`" in markdown, markdown
        assert "live_codex_e2e_claim_allowed: `False`" in markdown, markdown
        assert "live_codex_e2e_evidence_source: `not_collected_from_codex_lane_output`" in markdown, markdown
        assert "board_live_claim_scope" not in markdown, markdown
        assert "reasoning_effort: `high`" in markdown, markdown
        assert "deterministic replay:" in markdown, markdown
        assert_public_safe(markdown)

        guide = GUIDE.read_text(encoding="utf-8")
        assert "## 0. Prove The Deterministic Positive Replay" in guide, guide
        assert "auto-research demo-e2e" in guide, guide
        assert "does not claim that live Codex lanes authored the research result" in guide, guide
        assert "--reasoning-effort high" in guide, guide
        assert "--execute" in guide, guide
        assert "--launch-visible" in guide, guide
        assert "--tracking-goal-id loopx-meta" in guide, guide
        assert "tracking metadata never drives the visible lane frontier" in guide, guide
        assert "--attach" in guide, guide
        assert "--replace-existing" in guide, guide
        assert "tmux kill-session -t loopx-auto-research" in guide, guide
        assert "replay_result.dev_metric" in guide, guide
        assert "`4.0`" in guide, guide
        assert "replay_result.holdout_metric" in guide, guide
        assert "`4.5`" in guide, guide
        assert "acceptance.ready_for_real_launch" in guide, guide
        assert "live_codex_e2e.executed" in guide, guide
        assert "live_codex_e2e.claim_allowed" in guide, guide
        assert "not_collected_from_codex_lane_output" in guide, guide
        assert "capture-live-evidence" in guide, guide
        assert "--live-evidence" in guide, guide
        assert "raw logs" in guide, guide
        assert "private artifacts" in guide, guide
        assert "credentials" in guide, guide
        assert "local absolute workspace paths" in guide, guide
        e2e_section = guide.split("## 0. Prove The Deterministic Positive Replay", 1)[1].split(
            "## 1. Preview The Research Pack",
            1,
        )[0]
        assert_public_safe(e2e_section)

    print("auto-research-demo-e2e-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
