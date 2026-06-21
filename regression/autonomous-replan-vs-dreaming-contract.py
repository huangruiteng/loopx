#!/usr/bin/env python3
"""Regression for keeping autonomous replan separate from dreaming proposals."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "dreaming-contract-fixture"


def run_cli(*args: str, registry_path: Path, runtime: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    runs_dir = runtime / "goals" / GOAL_ID / "runs"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Dreaming Contract Fixture\n\n"
        "## Next Action\n\n"
        "- Continue normal delivery only after approved work is projected.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Continue a normal bounded delivery task if quota allows it.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "dreaming-contract-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-01-01T00:00:00+00:00"
    json_path = runs_dir / "dreaming-proposal.json"
    markdown_path = runs_dir / "dreaming-proposal.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "dreaming_exploration_proposal",
        "recommended_action": "Review the advisory dreaming proposal before promoting it.",
        "operator_question": "Should this project open a delivery todo for duplicate state handling?",
        "agent_command": "python should-not-run.py",
        "dreaming": {
            "lane": "exploration",
            "evidence_window": "last_20_runs",
            "proposal_type": "refactor_warning",
            "confidence": "medium",
            "requires_project_controller": True,
            "server_planning_contract": {
                "schema_version": "server_managed_planning_contract_v0",
                "lane": "dreaming_planning",
                "authority": "proposal_only_until_promoted",
                "may_rank_candidate_todos": True,
                "may_suggest_evidence_probes": True,
                "may_execute_protected_actions": False,
                "may_read_private_material": False,
                "may_mutate_active_state": False,
                "may_append_delivery_history": False,
                "may_spend_delivery_quota": False,
                "promotion_required": True,
                "promotion_requirements": [
                    "operator_or_controller_approval",
                    "normal_quota_should_run_decision",
                    "goal_boundary_write_scope_approval",
                ],
            },
        },
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text("# Dreaming Proposal\n", encoding="utf-8")
    (runs_dir / "index.jsonl").write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    return registry_path, runtime


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-dreaming-contract-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp))

        status_payload = run_cli("status", registry_path=registry_path, runtime=runtime)
        items = status_payload.get("attention_queue", {}).get("items") or []
        assert len(items) == 1, status_payload
        item = items[0]
        assert item["status"] == "dreaming_exploration_proposal", item
        assert item["waiting_on"] == "user_or_controller", item
        assert "agent_command" not in item, item
        assert "next_safe_command" not in item["project_asset"], item
        proposal = item["project_asset"]["dreaming_proposal"]
        assert proposal["schema_version"] == "dreaming_proposal_v0", proposal
        assert proposal["advisory"] is True, proposal
        assert proposal["promoted_to_delivery"] is False, proposal
        assert proposal["execution_allowed"] is False, proposal
        assert proposal["delivery_spend_allowed"] is False, proposal
        assert proposal["proposal_type"] == "refactor_warning", proposal
        planning_contract = proposal["server_planning_contract"]
        assert planning_contract["schema_version"] == "server_managed_planning_contract_v0", proposal
        assert planning_contract["authority"] == "proposal_only_until_promoted", proposal
        assert planning_contract["may_rank_candidate_todos"] is True, proposal
        assert planning_contract["may_suggest_evidence_probes"] is True, proposal
        assert planning_contract["may_execute_protected_actions"] is False, proposal
        assert planning_contract["may_read_private_material"] is False, proposal
        assert planning_contract["may_mutate_active_state"] is False, proposal
        assert planning_contract["may_append_delivery_history"] is False, proposal
        assert planning_contract["may_spend_delivery_quota"] is False, proposal
        assert planning_contract["promotion_required"] is True, proposal
        lane_badge = item["project_asset"]["dreaming_lane_badge"]
        assert item["dreaming_lane_badge"] == lane_badge, item
        assert lane_badge["schema_version"] == "dreaming_lane_badge_v0", lane_badge
        assert lane_badge["lane"] == "dreaming", lane_badge
        assert lane_badge["label"] == "Dreaming", lane_badge
        assert lane_badge["status"] == "dreaming_exploration_proposal", lane_badge
        assert lane_badge["proposal_type"] == "refactor_warning", lane_badge
        assert lane_badge["advisory"] is True, lane_badge
        assert lane_badge["review_required"] is True, lane_badge
        assert lane_badge["interrupts_delivery"] is False, lane_badge
        assert lane_badge["execution_allowed"] is False, lane_badge
        assert lane_badge["delivery_spend_allowed"] is False, lane_badge
        assert lane_badge["promoted_to_delivery"] is False, lane_badge
        assert lane_badge["server_planning"]["lane"] == "dreaming_planning", lane_badge

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert guard["should_run"] is False, guard
        assert guard["normal_delivery_allowed"] is False, guard
        assert guard["state"] == "operator_gate", guard
        assert guard["effective_action"] == "operator_gate_notify", guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] == "ask_operator_gate", guard
        assert guard["requires_user_action"] is True, guard
        assert "agent_command" not in guard, guard
        assert "autonomous_replan_obligation" not in guard, guard
        assert guard["dreaming_proposal"] == proposal, guard
        assert guard["dreaming_lane_badge"] == lane_badge, guard

        interaction = guard["interaction_contract"]
        assert interaction["mode"] == "user_gate", interaction
        assert interaction["user_channel"]["action_required"] is True, interaction
        assert interaction["user_channel"]["notify"] == "NOTIFY", interaction
        assert interaction["agent_channel"]["must_attempt"] is False, interaction
        assert interaction["agent_channel"]["delivery_allowed"] is False, interaction
        assert interaction["cli_channel"]["spend_allowed_now"] is False, interaction
        assert interaction["cli_channel"]["spend_after_validation"] is False, interaction
        assert interaction["cli_channel"]["next_cli_actions"] == [
            "no quota spend for blocker-push/gate-notification"
        ], interaction

        packet = guard["protocol_action_packet"]["summary"]
        assert "actor=user" in packet, packet
        assert "user_action_required=true" in packet, packet
        assert "agent_action_required=false" in packet, packet
        assert "llm=no_api" in packet, packet
    print("autonomous-replan-vs-dreaming-contract-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
