from __future__ import annotations

import pytest

from loopx.capabilities.periodic_report import (
    build_periodic_report_document,
    build_periodic_report_generation_bundle,
    build_project_progress_periodic_report_source,
    project_progress_periodic_report_source_adapter,
)
from loopx.presentation.renderers.periodic_report_html import (
    render_periodic_report_html,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    render_periodic_report_markdown,
)


def _projection(*, extra_items: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "periodic_report_project_progress_projection_v0",
        "goal_id": "example-project",
        "observed_at": "2026-07-20T08:00:00Z",
        "items": [
            {
                "item_id": "delivery",
                "title": "Shipped the project milestone",
                "summary": "The validated outcome is available to users.",
                "content_kind": "outcome",
                "value_rank": 10,
            },
            {
                "item_id": "capability",
                "title": "Simplified report activation",
                "summary": "A working session can use the built-in weekly preset.",
                "content_kind": "capability_change",
                "value_rank": 20,
                "details": [
                    {"label": "Before", "text": "A custom profile was required."},
                    {"label": "Now", "text": "The built-in preset is enough."},
                ],
            },
            {
                "item_id": "next",
                "title": "Collect the next reporting window",
                "summary": "Continue from validated project state.",
                "content_kind": "next_action",
                "value_rank": 30,
            },
            *(extra_items or []),
        ],
    }


def test_project_progress_source_builds_domain_neutral_report_hierarchy() -> None:
    result = build_project_progress_periodic_report_source(_projection())

    assert result["source_id"] == "project_progress"
    assert result["source_kind"] == "validated_project_progress"
    assert [section["section_id"] for section in result["sections"]] == [
        "progress",
        "capability_evolution",
        "next_actions",
    ]
    assert result["item_count"] == 3
    assert result["status"] == "complete"
    assert result["boundary"]["external_reads_performed"] is False
    assert result["boundary"]["external_writes_performed"] is False
    adapter = project_progress_periodic_report_source_adapter()
    assert adapter.source_id == "project_progress"
    assert adapter.collect(_projection())["snapshot_digest"] == result["snapshot_digest"]


def test_project_progress_source_keeps_runtime_supporting_and_caps_primary_items() -> None:
    runtime = {
        "item_id": "runtime",
        "title": "Validation receipt",
        "summary": "Focused checks passed.",
        "content_kind": "runtime",
        "visibility": "supporting",
    }
    result = build_project_progress_periodic_report_source(
        _projection(extra_items=[runtime])
    )
    supporting = next(
        section
        for section in result["sections"]
        if section["section_id"] == "supporting_evidence"
    )
    assert supporting["items"][0]["visibility"] == "supporting"

    extras = [
        {
            "item_id": f"extra_{index}",
            "title": f"Extra outcome {index}",
            "summary": "A compact validated outcome.",
            "content_kind": "outcome",
        }
        for index in range(6)
    ]
    with pytest.raises(ValueError, match="summarize to at most 8"):
        build_project_progress_periodic_report_source(
            _projection(extra_items=extras)
        )


def test_project_progress_source_renders_matching_local_artifacts() -> None:
    source = build_project_progress_periodic_report_source(_projection())
    document = build_periodic_report_document(
        title="Weekly project report",
        generated_at="2026-07-20T08:05:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "weekly_progress", "profile_version": "v1"},
        sources=[source],
    )
    bundle = build_periodic_report_generation_bundle(
        document=document,
        artifacts=[
            render_periodic_report_markdown(document),
            render_periodic_report_html(document),
        ],
    )

    assert bundle["generation_receipt"]["provider_required"] is False
    assert bundle["generation_receipt"]["external_writes_performed"] is False
    assert {artifact["renderer_kind"] for artifact in bundle["artifacts"]} == {
        "markdown",
        "html",
    }
    assert all(
        "Shipped the project milestone" in artifact["content"]
        for artifact in bundle["artifacts"]
    )
