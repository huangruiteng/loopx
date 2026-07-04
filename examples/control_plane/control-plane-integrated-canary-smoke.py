#!/usr/bin/env python3
"""Bounded canary for the status -> quota -> review-packet event read path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    TODO_ADDED,
    TODO_CLAIMED,
    TODO_COMPLETED,
    make_state_event,
)


GOAL_ID = "control-plane-integrated-canary"
AGENT_ID = "codex-product-capability"
CANARY_TODO_ID = "todo_integrated_canary"
CANARY_TODO_TITLE = "Design bounded status/quota/review-packet/event/read-path canary"
VALIDATED_PROGRESS_CLASSIFICATION = "integrated_canary_validated_progress"
DEFAULT_MAX_SECONDS = 120.0


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    event_log = state_file.with_name("events.jsonl")
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-06-27T00:00:00+00:00\n"
        "---\n\n"
        "# Control Plane Integrated Canary\n\n"
        "## Next Action\n\n"
        "- Keep the fixture-only integrated canary under two minutes.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P2] Markdown fallback todo that should lose to the event log.\n"
        "  <!-- loopx:todo todo_id=todo_markdown_fallback status=open "
        "task_class=advancement_task action_kind=stale_markdown -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-06-27T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "control-plane-canary",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "state_event_log": f".codex/goals/{GOAL_ID}/events.jsonl",
                        "adapter": {
                            "kind": "generic_project_goal_v0",
                            "status": "connected",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "slot_minutes": 1,
                            "allowed_slots": 10,
                        },
                        "coordination": {
                            "registered_agents": [AGENT_ID],
                            "primary_agent": AGENT_ID,
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    runtime.mkdir(parents=True, exist_ok=True)
    return registry_path, state_file, event_log


def append_event_todos(event_log: Path) -> None:
    store = AppendOnlyStateEventStore(event_log)

    def append(event_id: str, event_type: str, todo_id: str, payload: dict[str, Any], seq: int) -> None:
        store.append(
            make_state_event(
                event_id=event_id,
                goal_id=GOAL_ID,
                event_type=event_type,
                refs={"todo_id": todo_id},
                payload=payload,
                recorded_at=f"2026-06-27T00:00:{seq:02d}Z",
                producer="control-plane-integrated-canary-smoke",
            )
        )

    append(
        "evt-integrated-canary-add",
        TODO_ADDED,
        CANARY_TODO_ID,
        {
            "role": "agent",
            "priority": "P1",
            "title": CANARY_TODO_TITLE,
            "planner_order": 1,
            "task_class": "advancement_task",
            "action_kind": "integrated_canary_design",
            "target_capabilities": ["status_quota_review_packet_event_read_path_canary"],
        },
        1,
    )
    append(
        "evt-integrated-canary-claim",
        TODO_CLAIMED,
        CANARY_TODO_ID,
        {"claimed_by": AGENT_ID},
        2,
    )
    append(
        "evt-user-prior-approval-add",
        TODO_ADDED,
        "todo_user_prior_approval",
        {
            "role": "user",
            "priority": "P2",
            "title": "Prior canary scope approval",
            "planner_order": 1,
            "task_class": "user_gate",
        },
        3,
    )
    append(
        "evt-user-prior-approval-complete",
        TODO_COMPLETED,
        "todo_user_prior_approval",
        {"evidence": "fixture gate already cleared"},
        4,
    )


def run_cli(registry_path: Path, runtime_root: Path, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime_root),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def find_queue_item(status_payload: dict[str, Any]) -> dict[str, Any]:
    queue = status_payload.get("attention_queue")
    assert isinstance(queue, dict), status_payload
    for item in queue.get("items") or []:
        if isinstance(item, dict) and item.get("goal_id") == GOAL_ID:
            return item
    raise AssertionError(f"{GOAL_ID} missing from attention queue: {status_payload}")


def assert_event_projected_agent_todo(summary: dict[str, Any]) -> None:
    items = summary.get("items") if isinstance(summary.get("items"), list) else []
    if not items:
        items = (
            summary.get("first_open_items")
            if isinstance(summary.get("first_open_items"), list)
            else []
        )
    if not items:
        items = (
            summary.get("first_executable_items")
            if isinstance(summary.get("first_executable_items"), list)
            else []
        )
    assert [item.get("todo_id") for item in items] == [CANARY_TODO_ID], summary
    item = items[0]
    assert item["title"] == CANARY_TODO_TITLE, summary
    assert item["claimed_by"] == AGENT_ID, summary
    assert item["task_class"] == "advancement_task", summary
    assert "todo_markdown_fallback" not in json.dumps(summary, sort_keys=True), summary


def read_run_index(runtime_root: Path) -> list[dict[str, Any]]:
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    if not index_path.exists():
        return []
    return [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_bounded_delivery_state_machine_bundle(quota_payload: dict[str, Any]) -> None:
    """Assert that the major hot-path state machines agree on active work."""

    contract = quota_payload["interaction_contract"]
    assert contract["mode"] == "bounded_delivery", quota_payload
    assert contract["user_channel"] == {
        "action_required": False,
        "notify": "DONT_NOTIFY",
    }, contract
    agent_channel = contract["agent_channel"]
    assert agent_channel["must_attempt"] is True, contract
    assert agent_channel["delivery_allowed"] is True, contract
    assert agent_channel["quiet_noop_allowed"] is False, contract
    assert agent_channel["primary_action"].startswith(f"{CANARY_TODO_ID}: [P1]"), contract
    cli_channel = contract["cli_channel"]
    assert cli_channel["spend_allowed_now"] is False, contract
    assert cli_channel["spend_after_validation"] is True, contract
    assert cli_channel["spend_policy"] == "spend once after validated writeback", contract
    assert any("refresh-state" in action for action in cli_channel["next_cli_actions"]), contract
    assert any("spend-slot" in action for action in cli_channel["next_cli_actions"]), contract

    lane = quota_payload["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane

    scheduler = quota_payload["scheduler_hint"]
    assert scheduler["action"] == "run_now", scheduler
    assert scheduler["cadence_class"] == "active_work", scheduler
    codex_app = scheduler["codex_app"]
    assert codex_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=3", scheduler
    assert codex_app["no_spend_for_cadence_change"] is True, scheduler
    assert codex_app["stateful_backoff"]["apply_needed"] is True, scheduler

    frontier = quota_payload["goal_frontier_projection"]
    assert frontier["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 1,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 0,
    }, frontier
    assert frontier["monitor_only_lanes"]["present"] is False, frontier
    assert frontier["replan_required"] is False, frontier

    liveness = quota_payload["automation_liveness"]
    assert liveness["keep_active"] is True, liveness
    assert liveness["pause_allowed"] is False, liveness
    assert liveness["automation_action"] == "execute_bounded_work", liveness


def assert_scheduler_ack_state_machine(
    registry_path: Path,
    runtime_root: Path,
    quota_payload: dict[str, Any],
) -> dict[str, Any]:
    codex_app = quota_payload["scheduler_hint"]["codex_app"]
    backoff = codex_app["stateful_backoff"]
    ack_payload = run_cli(
        registry_path,
        runtime_root,
        "quota",
        "scheduler-ack",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--surface",
        "codex_app",
        "--state-key",
        backoff["state_key"],
        "--applied-rrule",
        codex_app["recommended_rrule"],
        "--reset-token",
        backoff["reset_token"],
        "--identity-signature",
        backoff["identity_signature"],
        "--execute",
    )
    assert ack_payload["ok"] is True, ack_payload
    assert ack_payload["mode"] == "scheduler-ack", ack_payload
    assert ack_payload["dry_run"] is False, ack_payload

    steady_payload = run_cli(
        registry_path,
        runtime_root,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    steady_codex_app = steady_payload["scheduler_hint"]["codex_app"]
    assert steady_codex_app["stateful_backoff"]["apply_needed"] is False, steady_payload
    assert steady_codex_app["stateful_backoff"]["state_status"] == "same_identity", steady_payload
    assert steady_codex_app["host_action"] == "none", steady_payload
    assert "recommended_rrule" not in steady_codex_app, steady_payload
    return steady_payload


def assert_refresh_and_spend_state_machine(registry_path: Path, runtime_root: Path) -> None:
    refresh_payload = run_cli(
        registry_path,
        runtime_root,
        "refresh-state",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--agent-lane",
        "product_capability",
        "--progress-scope",
        "agent_lane",
        "--classification",
        VALIDATED_PROGRESS_CLASSIFICATION,
        "--delivery-batch-scale",
        "multi_surface",
        "--delivery-outcome",
        "outcome_progress",
        "--recommended-action",
        "Integrated canary fixture validated the active transition bundle.",
    )
    assert refresh_payload["ok"] is True, refresh_payload
    assert refresh_payload["appended"] is True, refresh_payload
    assert refresh_payload["classification"] == VALIDATED_PROGRESS_CLASSIFICATION, refresh_payload
    assert refresh_payload["delivery_batch_scale"] == "multi_surface", refresh_payload
    assert refresh_payload["delivery_outcome"] == "outcome_progress", refresh_payload

    matching_runs = [
        run for run in read_run_index(runtime_root)
        if run.get("classification") == VALIDATED_PROGRESS_CLASSIFICATION
    ]
    assert len(matching_runs) == 1, matching_runs
    assert matching_runs[0]["progress_scope"] == "agent_lane", matching_runs
    assert matching_runs[0]["agent_id"] == AGENT_ID, matching_runs

    spend_payload = run_cli(
        registry_path,
        runtime_root,
        "quota",
        "spend-slot",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--slots",
        "1",
        "--source",
        "heartbeat",
        "--execute",
    )
    assert spend_payload["ok"] is True, spend_payload
    assert spend_payload["appended"] is True, spend_payload
    assert spend_payload["dry_run"] is False, spend_payload

    spent_payload = run_cli(
        registry_path,
        runtime_root,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert spent_payload["quota"]["spent_slots"] == 1, spent_payload
    assert spent_payload["quota"]["state"] == "eligible", spent_payload


def run_fixture_canary(root: Path) -> None:
    registry_path, _, event_log = write_fixture(root)
    runtime_root = root / "runtime"
    append_event_todos(event_log)

    status_payload = run_cli(
        registry_path,
        runtime_root,
        "status",
        "--scan-root",
        str(root / "project"),
        "--agent-id",
        AGENT_ID,
        "--limit",
        "3",
    )
    assert status_payload["ok"] is True, status_payload
    queue_item = find_queue_item(status_payload)
    allowed_status = {"active_state_agent_todo", "connected_without_run"}
    assert queue_item["status"] in allowed_status, queue_item
    assert queue_item["waiting_on"] == "codex", queue_item
    assert CANARY_TODO_TITLE in queue_item["recommended_action"], queue_item
    assert queue_item["state_event_projection"]["source"] == "event_log", queue_item
    assert_event_projected_agent_todo(queue_item["agent_todos"])
    assert_event_projected_agent_todo(queue_item["project_asset"]["agent_todos"])

    quota_payload = run_cli(
        registry_path,
        runtime_root,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert quota_payload["ok"] is True, quota_payload
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["effective_action"] == "normal_run", quota_payload
    assert quota_payload["interaction_contract"]["agent_channel"]["must_attempt"] is True, quota_payload
    assert CANARY_TODO_TITLE in quota_payload["recommended_action"], quota_payload
    assert_event_projected_agent_todo(quota_payload["agent_todo_summary"])
    assert_bounded_delivery_state_machine_bundle(quota_payload)
    assert_scheduler_ack_state_machine(registry_path, runtime_root, quota_payload)
    assert_refresh_and_spend_state_machine(registry_path, runtime_root)

    packet_payload = run_cli(
        registry_path,
        runtime_root,
        "review-packet",
        "--goal-id",
        GOAL_ID,
        "--format",
        "json",
    )
    assert packet_payload["ok"] is True, packet_payload
    assert packet_payload["status"] in allowed_status, packet_payload
    assert packet_payload["project_asset_source"] == "project_asset", packet_payload
    assert CANARY_TODO_TITLE in packet_payload["project_agent_handoff"], packet_payload
    assert packet_payload["handoff_interface_budget"]["within_budget"] is True, packet_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep-run", action="store_true", help="Reserved for explicit heavier checks.")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.deep_run:
        raise SystemExit("--deep-run is intentionally not implemented for the fixture canary yet")
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="loopx-control-plane-canary-") as tmp:
        run_fixture_canary(Path(tmp))
    elapsed = time.monotonic() - start
    assert elapsed <= args.max_seconds, {
        "elapsed_seconds": elapsed,
        "max_seconds": args.max_seconds,
    }
    print(f"control-plane-integrated-canary-smoke ok elapsed={elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
