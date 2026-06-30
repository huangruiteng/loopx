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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e  # noqa: E402

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
        "multiround_research_kernel",
        "multiround_research_preview",
    }, payload
    assert payload["result_source"] in {
        "lightweight_multiround_kernel",
        "lightweight_multiround_kernel_preview",
    }, payload
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
    protected_eval = payload["protected_eval_result"]
    loop = payload["research_loop"]
    assert protected_eval["executed"] is executed, payload
    assert loop["executed"] is executed, payload
    if executed:
        assert loop["result_source"] == "knn_pack_protected_eval", payload
        assert loop["candidate_count"] == 2, payload
        assert loop["dev_round_count"] == 2, payload
        assert loop["evidence_event_count"] == 3, payload
        assert loop["selected_hypothesis_id"] == "hyp_partial_selection", payload
        assert loop["decision"] == "validated_positive", payload
        assert loop["baseline_metric"] == 1.0, payload
        assert loop["dev_metric"] == 4.0, payload
        assert loop["holdout_metric"] == 4.5, payload
        assert loop["dev_gain_over_baseline"] == 3.0, payload
        assert loop["holdout_gain_over_baseline"] == 3.5, payload
        assert [item["role"] for item in loop["worker_rounds"]] == [
            "hypothesis_mapper",
            "evidence_runner",
            "evidence_verifier",
        ], payload
        assert {item["loopx_contract"] for item in loop["worker_rounds"]} == {
            "role_profile_quota_frontier_cli_writeback"
        }, payload
        assert protected_eval["result_source"] == "generated_quickstart_pack_protected_eval", payload
        assert protected_eval["status"] == "supported", payload
        assert protected_eval["dev_metric"] == 4.0, payload
        assert protected_eval["holdout_metric"] == 4.5, payload
        assert protected_eval["dev_exact"] is True, payload
        assert protected_eval["holdout_exact"] is True, payload
        assert protected_eval["protected_scope_clean"] is True, payload
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
        assert loop["result_source"] == "lightweight_multiround_kernel_preview", payload
        assert "two dev rounds plus holdout" in loop["expected_rounds"], payload
        assert protected_eval["result_source"] == "lightweight_multiround_kernel_preview", payload
        assert protected_eval["expected_positive_result"] == "dev=4.0x holdout=4.5x after --execute", payload
    assert_public_safe(payload)


def assert_visible_demo_local_control_plane(*, registry: Path, runtime_root: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_append_evidence(_packet_path: str) -> dict[str, object]:
        return {
            "appended_count": 3,
            "skipped_existing_count": 0,
            "counts_by_kind": {"research_evidence": 2, "research_hypothesis": 1},
        }

    def fake_visible_launcher(
        supervisor: dict[str, object],
        visible_registry: Path,
        visible_runtime_root: str | None,
        default_workspace: Path,
    ) -> dict[str, object]:
        captured["registry"] = visible_registry
        captured["runtime_root"] = visible_runtime_root
        captured["workspace"] = default_workspace
        assert default_workspace.is_dir(), default_workspace
        assert list(default_workspace.glob(".local/auto-research-demo/**/protected_eval.py")), default_workspace
        expected_actions = {
            "codex-product-capability": "write_research_contract",
            "codex-side-bypass": "propose_hypothesis",
            "codex-main-control": "claim_attempt",
        }
        lane_workspaces = {
            str(lane.get("agent_id")): Path(str(lane.get("workspace"))).resolve()
            for lane in supervisor.get("lanes", [])
            if isinstance(lane, dict) and lane.get("workspace")
        }
        for agent_id, action in expected_actions.items():
            lane_cwd = lane_workspaces.get(agent_id, default_workspace)
            assert lane_cwd.is_dir(), lane_cwd
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
            quota = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "loopx.cli",
                    "--registry",
                    str(visible_registry),
                    "--runtime-root",
                    str(visible_runtime_root),
                    "--format",
                    "json",
                    "quota",
                    "should-run",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    agent_id,
                ],
                cwd=lane_cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            quota_payload = json.loads(quota.stdout)
            next_action = quota_payload["agent_lane_next_action"]
            assert next_action["action_kind"] == action, quota_payload
            assert next_action["claimed_by"] == agent_id, quota_payload
            frontier = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "loopx.cli",
                    "--registry",
                    str(visible_registry),
                    "--runtime-root",
                    str(visible_runtime_root),
                    "--format",
                    "json",
                    "auto-research",
                    "frontier",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    agent_id,
                ],
                cwd=lane_cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            frontier_payload = json.loads(frontier.stdout)
            selected = frontier_payload["frontier"]["selected"]
            assert selected["allowed_action"] == action, frontier_payload
            assert selected["claimed_by"] == agent_id, frontier_payload
        return {
            "mode": "executed_visible_launch",
            "launch_result": {
                "started_lane_count": len(supervisor.get("lanes") or []),
                "surviving_lane_count": len(supervisor.get("lanes") or []),
                "visible_acceptance": {"accepted": True, "missing_lanes": []},
            },
            "boundary": {
                "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
                "starts_tmux": False,
                "runs_codex": False,
            },
        }

    payload = run_auto_research_demo_e2e(
        agent_id=AGENT_ID,
        goal_id=GOAL_ID,
        tracking_goal_id=TRACKING_GOAL_ID,
        objective="Improve exact k-nearest-neighbor inference under a protected evaluator.",
        output_dir=".local/auto-research-demo",
        execute=True,
        launch_visible=True,
        keep_workspace=False,
        registry_path=registry,
        runtime_root_arg=str(runtime_root),
        session_name="loopx-auto-research-smoke",
        cli_bin="loopx",
        codex_bin="codex",
        tmux_bin="tmux",
        reasoning_effort="high",
        live_evidence_path=None,
        append_evidence=fake_append_evidence,
        visible_launcher=fake_visible_launcher,
    )
    assert captured["registry"] != registry, captured
    assert captured["runtime_root"] != str(runtime_root), captured
    assert captured["workspace"] != REPO_ROOT, captured
    control = payload["visible_control_plane"]
    assert control["schema_version"] == "auto_research_visible_demo_control_plane_v0", payload
    assert control["mode"] == "demo_local_loopx_queue", payload
    assert control["goal_id"] == GOAL_ID, payload
    assert control["registry_scope"] == "demo_local_runtime", payload
    assert control["registered_agent_count"] == 3, payload
    assert control["seeded_todo_count"] == 3, payload
    assert {item["action_kind"] for item in control["seeded_todos"]} == {
        "write_research_contract",
        "propose_hypothesis",
        "claim_attempt",
    }, payload
    workspace_route = control["workspace_route"]
    assert workspace_route["shared_goal_surface"] == "demo_local_loopx_registry_and_runtime", payload
    assert workspace_route["side_lane_workspace"] == "independent_git_worktree", payload
    assert workspace_route["side_lane_worktree_count"] == 2, payload
    assert workspace_route["absolute_paths_recorded"] is False, payload
    assert control["absolute_paths_recorded"] is False, payload
    assert payload["workspace_retained"] is True, payload
    assert payload["live_codex_e2e"]["visible_lanes_accepted"] is True, payload
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
        kernel_command = executed_payload["commands"]["multiround_kernel"]
        visible_command = executed_payload["commands"]["multiround_kernel_with_visible_lanes"]
        assert f"--goal-id {GOAL_ID}" in kernel_command, kernel_command
        assert f"--goal-id {GOAL_ID}" in visible_command, visible_command
        assert f"--tracking-goal-id {TRACKING_GOAL_ID}" in kernel_command, kernel_command
        assert f"--tracking-goal-id {TRACKING_GOAL_ID}" in visible_command, visible_command
        assert_visible_demo_local_control_plane(registry=registry, runtime_root=runtime_root)

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
        assert "# LoopX Auto Research Multi-Round Demo" in markdown, markdown
        assert "execution_kind: `multiround_research_preview`" in markdown, markdown
        assert "research_loop_executed: `False`" in markdown, markdown
        assert "research_loop_source: `lightweight_multiround_kernel_preview`" in markdown, markdown
        assert "research_loop_dev_rounds:" in markdown, markdown
        assert "research_loop_evidence_events:" in markdown, markdown
        assert "frontier_goal_id: `loopx-auto-research-knn`" in markdown, markdown
        assert "tracking_goal_drives_frontier: `False`" in markdown, markdown
        assert "live_codex_e2e_claim_allowed: `False`" in markdown, markdown
        assert "live_codex_e2e_evidence_source: `not_collected_from_codex_lane_output`" in markdown, markdown
        assert "board_live_claim_scope" not in markdown, markdown
        assert "reasoning_effort: `high`" in markdown, markdown
        assert "multi-round research:" in markdown, markdown
        assert_public_safe(markdown)

        guide = GUIDE.read_text(encoding="utf-8")
        normalized_guide = " ".join(guide.split())
        help_text = run_cli(
            [
                "auto-research",
                "demo-e2e",
                "--help",
            ],
            registry=registry,
            runtime_root=runtime_root,
        ).stdout
        normalized_help = " ".join(help_text.split())
        assert "Visible panes alone do not make the" in normalized_help, help_text
        assert "round kernel a live Codex E2E result." in normalized_help, help_text
        assert "Visible panes alone do not make the replay" not in help_text, help_text
        assert "## 0. Prove The Multi-Round Positive Path" in guide, guide
        assert "auto-research demo-e2e" in guide, guide
        assert "does not claim that visible Codex lanes authored the research result" in normalized_guide, guide
        assert "--reasoning-effort high" in guide, guide
        assert "--execute" in guide, guide
        assert "--launch-visible" in guide, guide
        assert "--tracking-goal-id loopx-meta" in guide, guide
        assert "tracking metadata never drives the visible lane frontier" in guide, guide
        assert "--attach" in guide, guide
        assert "--replace-existing" in guide, guide
        assert "tmux kill-session -t loopx-auto-research" in guide, guide
        assert "research_loop.dev_round_count" in guide, guide
        assert "research_loop.evidence_event_count" in guide, guide
        assert "research_loop.dev_gain_over_baseline" in guide, guide
        assert "research_loop.holdout_gain_over_baseline" in guide, guide
        assert "protected_eval_result.dev_metric" in guide, guide
        assert "`4.0`" in guide, guide
        assert "protected_eval_result.holdout_metric" in guide, guide
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
        e2e_section = guide.split("## 0. Prove The Multi-Round Positive Path", 1)[1].split(
            "## 1. Preview The Research Pack",
            1,
        )[0]
        assert_public_safe(e2e_section)

    print("auto-research-demo-e2e-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
