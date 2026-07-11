from __future__ import annotations

import json

from loopx.control_plane.runtime.goal_start_control_score import (
    compact_goal_start_product_mode_control_score,
)


def test_compact_goal_start_control_score_preserves_public_contract() -> None:
    compact = compact_goal_start_product_mode_control_score(
        {
            "schema_version": "goal_start_product_mode_control_score_v0",
            "required": True,
            "satisfied": True,
            "score": 1,
            "planned_todo_count": -2,
            "selected_p0_todo_id": "todo_public_solver",
            "planned_todo_ids": [f"todo-{index}" for index in range(10)],
            "goal_start_todo_snapshot": {
                "schema_version": "goal_start_todo_snapshot_v0",
                "raw_material_recorded": False,
                "completed_todo_id_count": -1,
                "planned_todos": [
                    {
                        "todo_id": "todo_public_solver",
                        "role": "agent",
                        "status": "done",
                        "text_public_safe": "Fix the public fixture",
                        "claim_count": -1,
                        "private_detail": "drop",
                    }
                ],
                "private_detail": "drop",
            },
            "private_detail": "drop",
        }
    )

    assert compact["required"] is True
    assert compact["satisfied"] is True
    assert compact["score"] == 1.0
    assert compact["planned_todo_count"] == 0
    assert len(compact["planned_todo_ids"]) == 8
    assert compact["goal_start_todo_snapshot"]["completed_todo_id_count"] == 0
    assert compact["goal_start_todo_snapshot"]["planned_todos"] == [
        {
            "todo_id": "todo_public_solver",
            "role": "agent",
            "status": "done",
            "text_public_safe": "Fix the public fixture",
            "claim_count": 0,
        }
    ]
    assert "private_detail" not in json.dumps(compact, sort_keys=True)


def test_compact_goal_start_control_score_rejects_non_mapping_input() -> None:
    assert compact_goal_start_product_mode_control_score(None) == {}
    assert compact_goal_start_product_mode_control_score([]) == {}
