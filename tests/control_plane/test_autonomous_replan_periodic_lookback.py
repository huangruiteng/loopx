from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loopx.cli_commands.status import (
    _status_collection_limit_for_agent_lane,
    _trim_run_history_for_status_display,
)
from loopx.control_plane.goals.goal_frontier.ack_policy import (
    autonomous_replan_ack_satisfies_obligation,
)
from loopx.control_plane.runtime.run_context_retention import (
    latest_runs_with_agent_context,
)
from loopx.history import collect_history
from loopx.status import (
    AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
    AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD,
    autonomous_replan_obligation_from_runs,
    autonomous_replan_periodic_review_from_runs,
)


def _periodic_runs(*, minute_offset: int = 0) -> list[dict[str, object]]:
    return [
        {
            "classification": f"bounded_delivery_{index:02d}",
            "generated_at": (
                f"2026-08-27T{minute_offset // 60:02d}:"
                f"{minute_offset % 60:02d}:{59 - index:02d}Z"
            ),
            "agent_id": "codex-fixture",
        }
        for index in range(AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD)
    ]


def test_periodic_replan_lookback_survives_interleaved_neutral_runs() -> None:
    latest_runs: list[dict[str, object]] = []
    for index in range(AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD):
        latest_runs.extend(
            [
                {
                    "classification": "quota_slot_spent",
                    "generated_at": f"2026-08-27T00:{59 - index:02d}:01Z",
                    "agent_id": "codex-fixture",
                },
                {
                    "classification": f"bounded_delivery_{index:02d}",
                    "generated_at": f"2026-08-27T00:{59 - index:02d}:00Z",
                    "agent_id": "codex-fixture",
                },
            ]
        )

    selected_runs = latest_runs[:AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK]
    obligation = autonomous_replan_periodic_review_from_runs(
        selected_runs,
        agent_todos=None,
    )

    assert len(selected_runs) == len(latest_runs)
    assert obligation is not None
    trigger = obligation["triggers"][0]
    assert trigger["kind"] == "periodic_review_due"
    assert trigger["run_count"] == AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD


def test_periodic_replan_obligation_rotates_with_the_review_window() -> None:
    first = autonomous_replan_periodic_review_from_runs(
        _periodic_runs(minute_offset=0),
        agent_todos=None,
    )
    replay = autonomous_replan_periodic_review_from_runs(
        _periodic_runs(minute_offset=0),
        agent_todos=None,
    )
    later = autonomous_replan_periodic_review_from_runs(
        _periodic_runs(minute_offset=60),
        agent_todos=None,
    )

    assert first is not None
    assert replay is not None
    assert later is not None
    assert replay["obligation_id"] == first["obligation_id"]
    assert later["obligation_id"] != first["obligation_id"]
    assert not autonomous_replan_ack_satisfies_obligation(
        {
            "recorded": True,
            "semantic_delta": {
                "accepted": True,
                "obligation_id": first["obligation_id"],
                "outcomes": ["new_runnable_successor"],
            },
        },
        replan_obligation=later,
        acceptance_gaps=[],
    )


def test_agent_lane_keeps_periodic_control_history_off_the_display_path() -> None:
    display_limit = 5
    collection_limit = _status_collection_limit_for_agent_lane(
        requested_limit=display_limit,
        agent_id="codex-fixture",
    )
    rows = [
        {"classification": f"bounded_delivery_{index:02d}"}
        for index in range(collection_limit)
    ]
    payload: dict[str, object] = {
        "run_history": {
            "recent_runs": list(rows),
            "goals": [{"id": "fixture-goal", "latest_runs": list(rows)}],
        }
    }

    _trim_run_history_for_status_display(
        payload,
        display_limit=display_limit,
        collection_limit=collection_limit,
    )

    run_history = payload["run_history"]
    assert isinstance(run_history, dict)
    assert len(run_history["recent_runs"]) == display_limit
    assert len(run_history["goals"][0]["latest_runs"]) == display_limit
    assert payload["agent_lane_projection_lookback"] == {
        "schema_version": "agent_lane_projection_lookback_v0",
        "collection_limit": AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
        "display_limit": display_limit,
        "reason": (
            "status --agent-id collected quota-equivalent run history for "
            "agent-lane frontier projection, then restored the requested "
            "status display limit"
        ),
    }


PEER_AGENT_ID = "codex-peer-lane"
LANE_AGENT_ID = "codex-fixture"
MULTI_LANE_GOAL_ID = "multi-lane-goal"


def _peer_lane_runs(*, count: int) -> list[dict[str, Any]]:
    """Return newest-first peer-lane rows that fill the goal-wide window."""

    return [
        {
            "classification": f"peer_delivery_{index:02d}",
            "generated_at": f"2026-09-01T00:{index:02d}:00Z",
            "agent_id": PEER_AGENT_ID,
        }
        for index in range(count)
    ]


def _lane_material_runs(*, count: int) -> list[dict[str, Any]]:
    """Return newest-first material rows for the requesting lane."""

    return [
        {
            "classification": f"lane_delivery_{index:02d}",
            "generated_at": f"2026-08-31T23:{59 - index:02d}:00Z",
            "agent_id": LANE_AGENT_ID,
        }
        for index in range(count)
    ]


def _lane_replan_ack_run() -> dict[str, Any]:
    return {
        "classification": "state_refreshed",
        "generated_at": "2026-08-31T23:00:00Z",
        "agent_id": LANE_AGENT_ID,
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "refresh_state_semantic_delta",
            "semantic_delta": {
                "accepted": True,
                "obligation_id": f"replan-{'0' * 16}",
                "outcomes": ["new_surface"],
            },
        },
    }


def _multi_lane_runs() -> list[dict[str, Any]]:
    """Peer volume fills the goal-wide window ahead of one lane's own review."""

    return [
        *_peer_lane_runs(count=AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
        *_lane_material_runs(count=AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD),
        _lane_replan_ack_run(),
    ]


def _write_multi_lane_history(tmp_path: Path, runs: list[dict[str, Any]]) -> tuple[Path, Path]:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("{}\n", encoding="utf-8")
    runtime_root = tmp_path / "runtime"
    runs_dir = runtime_root / "goals" / MULTI_LANE_GOAL_ID / "runs"
    runs_dir.mkdir(parents=True)
    rows = []
    for position, run in enumerate(runs):
        row = dict(run)
        row.setdefault("json_path", f"artifacts/{MULTI_LANE_GOAL_ID}-{position}.json")
        row.setdefault("markdown_path", f"artifacts/{MULTI_LANE_GOAL_ID}-{position}.md")
        rows.append(json.dumps(row))
    (runs_dir / "index.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return registry_path, runtime_root


def test_peer_lane_volume_cannot_hide_one_lane_periodic_review(tmp_path: Path) -> None:
    """A lane-scoped replan trigger must not depend on peer-lane volume.

    The guarded Turn selects the replan obligation for one agent lane, and the
    writeback derives it again from the full run index. When the goal-wide
    window cannot decide the lane's material-run count, the two derivations
    disagree and the guarded writeback can never discharge the obligation.
    """

    runs = _multi_lane_runs()
    registry_path, runtime_root = _write_multi_lane_history(tmp_path, runs)

    shared_window = collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=MULTI_LANE_GOAL_ID,
        limit=AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
    )
    goal_window_runs = shared_window["goals"][0]["latest_runs"]
    assert not [
        run
        for run in goal_window_runs
        if str(run.get("agent_id") or "") == LANE_AGENT_ID
    ]
    assert (
        autonomous_replan_obligation_from_runs(
            goal_window_runs,
            agent_todos=None,
            agent_id=LANE_AGENT_ID,
        )
        is None
    )

    lane_window = collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=MULTI_LANE_GOAL_ID,
        limit=AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
        agent_lane_id=LANE_AGENT_ID,
    )
    lane_obligation = autonomous_replan_obligation_from_runs(
        lane_window["goals"][0]["latest_runs"],
        agent_todos=None,
        agent_id=LANE_AGENT_ID,
    )
    complete_history_obligation = autonomous_replan_obligation_from_runs(
        runs,
        agent_todos=None,
        agent_id=LANE_AGENT_ID,
    )

    assert lane_obligation is not None
    assert complete_history_obligation is not None
    assert lane_obligation["triggers"][0]["kind"] == "periodic_review_due"
    assert (
        lane_obligation["obligation_id"]
        == complete_history_obligation["obligation_id"]
    )


def test_lane_window_keeps_goal_rows_and_adds_the_lane_rows() -> None:
    runs = _multi_lane_runs()

    lane_window = latest_runs_with_agent_context(
        runs,
        limit=AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
        agent_lane_id=LANE_AGENT_ID,
    )

    assert lane_window[: AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK] == runs[
        : AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK
    ]
    lane_rows = [
        run for run in lane_window if str(run.get("agent_id") or "") == LANE_AGENT_ID
    ]
    assert len(lane_rows) == AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD + 1
    assert lane_window[-1]["generated_at"] == "2026-08-31T23:00:00Z"


def test_lane_window_leaves_other_lanes_untouched() -> None:
    runs = _lane_material_runs(count=2)

    assert latest_runs_with_agent_context(
        runs, limit=1, agent_lane_id="codex-absent-lane"
    ) == runs[:1]
