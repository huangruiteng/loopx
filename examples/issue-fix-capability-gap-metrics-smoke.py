#!/usr/bin/env python3
"""Contract smoke for typed capability-gap lifecycle metrics."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_EXAMPLES = ROOT / "examples" / "control_plane"
for path in (ROOT, CONTROL_PLANE_EXAMPLES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from todo_lifecycle_fixtures import (  # noqa: E402
    GOAL_ID,
    run_cli,
    run_cli_error,
    write_fixture,
)

ACTOR_AGENT_ID = "codex-main-control"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-capability-gap-metrics-") as tmp:
        registry_path, _state_file = write_fixture(Path(tmp))
        project = registry_path.parents[1]
        runtime = Path(
            json.loads(registry_path.read_text(encoding="utf-8"))["common_runtime_root"]
        )
        domain = project / ".loopx" / "domain-state" / GOAL_ID / "issue_fix"
        domain.mkdir(parents=True, exist_ok=True)
        (domain / "feasibility.jsonl").write_text("", encoding="utf-8")
        (domain / "pr-lifecycle.jsonl").write_text("", encoding="utf-8")

        invalid = run_cli_error(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Record one missing metric contract.",
            "--capability-gap-status",
            "found",
        )
        assert "requires at least one --target-capability" in invalid["error"], invalid

        added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Record one missing metric contract.",
            "--target-capability",
            "issue_fix_monthly_metrics",
            "--capability-gap-status",
            "found",
        )
        assert added["capability_gap_event"]["event_kind"] == "capability_gap", added
        todo_id = added["todo_id"]

        missing_evidence = run_cli_error(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            todo_id,
            "--agent-id",
            ACTOR_AGENT_ID,
            "--role",
            "agent",
            "--target-capability",
            "issue_fix_monthly_metrics",
            "--capability-gap-status",
            "real_callsite_verified",
        )
        assert "require public-safe --evidence" in missing_evidence["error"], (
            missing_evidence
        )

        verified = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            todo_id,
            "--agent-id",
            ACTOR_AGENT_ID,
            "--role",
            "agent",
            "--target-capability",
            "issue_fix_monthly_metrics",
            "--capability-gap-status",
            "real_callsite_verified",
            "--evidence",
            "fixture replay composed one verified gap",
        )
        assert verified["capability_gap_event"]["status"] == "real_callsite_verified", verified

        event_log = runtime / "goals" / GOAL_ID / "rollout-event-log.jsonl"
        events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
        gap_events = [event for event in events if event.get("event_kind") == "capability_gap"]
        assert [event["status"] for event in gap_events] == [
            "found",
            "real_callsite_verified",
        ], gap_events
        assert all(event["todo_id"] == todo_id for event in gap_events), gap_events
        assert gap_events[-1]["details"]["evidence"] == (
            "fixture replay composed one verified gap"
        ), gap_events

        common_args = (
            "issue-fix",
            "metrics-supplement",
            "--goal-id",
            GOAL_ID,
            "--project",
            str(project),
            "--repo",
            "public-fixture/widgets",
            "--period-start",
            "2026-07-01T00:00:00Z",
            "--period-end",
            "2026-08-01T00:00:00Z",
            "--generated-at",
            "2026-08-01T00:01:00Z",
        )
        partial = run_cli(registry_path, *common_args)
        assert partial["supplement"]["coverage"]["capability_gap"] == {
            "source": "loopx_rollout_event_log",
            "observed_gaps": 1,
            "complete": False,
        }, partial
        assert "loopx_capability_gaps_found" in partial["missing_fields"], partial

        complete = run_cli(
            registry_path,
            *common_args,
            "--capability-gap-coverage-start",
            "2026-07-01T00:00:00Z",
        )
        counts = complete["supplement"]["counts"]
        assert counts["loopx_capability_gaps_found"] == 1, complete
        assert counts["loopx_capability_gaps_fixed"] == 1, complete
        assert counts["loopx_capability_gaps_real_callsite_verified"] == 1, complete
        assert complete["supplement"]["coverage"]["capability_gap"] == {
            "source": "loopx_rollout_event_log",
            "observed_gaps": 1,
            "complete": True,
            "complete_from": "2026-07-01T00:00:00Z",
        }, complete
        assert complete["source_summary"]["rollout_event_rows"] >= 4, complete

    print("issue-fix capability-gap metrics smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
