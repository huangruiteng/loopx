from __future__ import annotations

from pathlib import Path

import pytest

from loopx.capabilities.periodic_report.workspace import (
    build_periodic_report_workspace_projection,
    collect_periodic_report_workspace_index,
    read_published_periodic_report_workspace_projection,
    write_periodic_report_workspace_projection,
)
from loopx.capabilities.periodic_report.incremental import (
    build_periodic_report_publication_candidate,
    commit_periodic_report_publication_cursor,
)


def _document() -> dict[str, object]:
    return {
        "title": "Synthetic milestone report",
        "generated_at": "2026-01-10T12:00:00Z",
        "period_window": {
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-01-10T12:00:00Z",
        },
        "editorial": {"summary": "A compact public-safe progress summary."},
        "sections": [
            {
                "items": [
                    {
                        "item_id": "outcome_1",
                        "source_ref": "todo:one",
                        "title": "First capability slice",
                        "summary": "The bounded slice passed focused validation.",
                        "content_kind": "outcome",
                    },
                    {
                        "item_id": "next_1",
                        "source_ref": "todo:two",
                        "title": "Follow-up validation",
                        "summary": "Run the remaining browser checks.",
                        "content_kind": "next_action",
                    },
                ]
            }
        ],
    }


def _facts() -> list[dict[str, str]]:
    return [
        {
            "fact_id": "fact_one",
            "title": "First capability slice",
            "summary": "The bounded slice passed focused validation.",
            "source_ref": "todo:one",
            "status": "done",
            "content_kind": "outcome",
            "change_kind": "added",
        },
        {
            "fact_id": "fact_two",
            "title": "Follow-up validation",
            "summary": "Run the remaining browser checks.",
            "source_ref": "todo:two",
            "status": "open",
            "content_kind": "next_action",
            "change_kind": "changed",
            "previous_status": "blocked",
        },
    ]


def _published(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    projection = build_periodic_report_workspace_projection(
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        generation_id="report_generation_example",
        document=_document(),
        facts=_facts(),
    )
    path = (
        tmp_path
        / "goals/synthetic-goal/periodic_reports/run-one/workspace-projection.json"
    )
    write_periodic_report_workspace_projection(path=path, projection=projection)
    candidate = build_periodic_report_publication_candidate(
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        generation_id="report_generation_example",
        trigger_receipt={"coalesced_trigger_ids": ["trigger_one"]},
        facts=[
            {
                **fact,
                "fact_fingerprint": "sha256:" + str(index) * 64,
            }
            for index, fact in enumerate(_facts(), start=1)
        ],
        baseline=None,
        workspace_projection_sha256=str(projection["content_sha256"]),
    )
    cursor = commit_periodic_report_publication_cursor(
        runtime_root=tmp_path,
        candidate=candidate,
        publication_id="publication_one",
        delivered_at="2026-01-10T12:05:00Z",
        covered_until="2026-01-10T12:00:00Z",
    )
    return projection, cursor


def test_workspace_index_excludes_generation_without_publication_cursor(
    tmp_path: Path,
) -> None:
    projection = build_periodic_report_workspace_projection(
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        generation_id="report_generation_example",
        document=_document(),
        facts=_facts(),
    )
    write_periodic_report_workspace_projection(
        path=tmp_path
        / "goals/synthetic-goal/periodic_reports/run/workspace-projection.json",
        projection=projection,
    )

    assert collect_periodic_report_workspace_index(runtime_root=tmp_path) == {
        "schema_version": "periodic_report_workspace_index_v0",
        "count": 0,
        "returned_count": 0,
        "total_count": 0,
        "limit": 100,
        "offset": 0,
        "truncated": False,
        "items": [],
    }


def test_workspace_index_bounds_latest_items_and_supports_offset(
    tmp_path: Path,
) -> None:
    projection, _cursor = _published(tmp_path)
    for index in range(4):
        agent_id = f"synthetic-agent-{index}"
        candidate = build_periodic_report_publication_candidate(
            goal_id="synthetic-goal",
            agent_id=agent_id,
            generation_id=f"report_generation_{index}",
            trigger_receipt={"coalesced_trigger_ids": [f"trigger_{index}"]},
            facts=[
                {
                    **fact,
                    "fact_fingerprint": "sha256:" + str(index + 1) * 64,
                }
                for fact in _facts()
            ],
            baseline=None,
            workspace_projection_sha256=str(projection["content_sha256"]),
        )
        commit_periodic_report_publication_cursor(
            runtime_root=tmp_path,
            candidate=candidate,
            publication_id=f"publication_{index}",
            delivered_at=f"2026-01-{index + 1:02d}T12:05:00Z",
            covered_until=f"2026-01-{index + 1:02d}T12:00:00Z",
        )

    latest = collect_periodic_report_workspace_index(
        runtime_root=tmp_path,
        goal_id="synthetic-goal",
        limit=2,
    )
    page = collect_periodic_report_workspace_index(
        runtime_root=tmp_path,
        goal_id="synthetic-goal",
        limit=2,
        offset=2,
    )

    assert latest["count"] == 2
    assert latest["returned_count"] == 2
    assert latest["total_count"] == 5
    assert latest["limit"] == 2
    assert latest["offset"] == 0
    assert latest["truncated"] is True
    assert page["count"] == 2
    assert page["returned_count"] == 2
    assert page["offset"] == 2
    assert page["items"][0]["delivered_at"] < latest["items"][-1]["delivered_at"]
    assert page["items"][-1]["delivered_at"] == "2026-01-02T12:05:00Z"


def test_published_workspace_projection_preserves_delta_and_lineage(
    tmp_path: Path,
) -> None:
    projection, cursor = _published(tmp_path)

    index = collect_periodic_report_workspace_index(
        runtime_root=tmp_path, goal_id="synthetic-goal"
    )
    detail = read_published_periodic_report_workspace_projection(
        runtime_root=tmp_path,
        **index["items"][0]["detail_ref"],
    )

    assert index["count"] == 1
    assert detail["delta"]["added_count"] == 1
    assert detail["delta"]["changed_count"] == 1
    assert detail["publication"]["cursor_id"] == cursor["cursor_id"]
    assert detail["content_sha256"] == projection["content_sha256"]
    assert detail["interaction"] == {
        "attention_kind": "progress",
        "interaction": "inform",
        "delivery": "surface",
        "form": "milestone_report",
        "writable": False,
    }


def test_workspace_detail_rejects_stale_or_mismatched_ref(tmp_path: Path) -> None:
    projection, _cursor = _published(tmp_path)

    with pytest.raises(ValueError, match="not the current publication"):
        read_published_periodic_report_workspace_projection(
            runtime_root=tmp_path,
            goal_id="synthetic-goal",
            agent_id="synthetic-agent",
            generation_id="report_generation_old",
            content_sha256=str(projection["content_sha256"]),
        )
