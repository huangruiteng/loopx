#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from loopx.capabilities.issue_fix.periodic_report import (
    issue_fix_periodic_report_source_adapter,
)
from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    PeriodicReportSourceAdapter,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    periodic_report_markdown_renderer_adapter,
)
from loopx.presentation.sinks.lark.periodic_report import (
    periodic_report_lark_sink_adapter,
)
from loopx.presentation.sinks.openviking_periodic_report import (
    periodic_report_openviking_sink_adapter,
)


def release_source(_: dict[str, Any]) -> dict[str, Any]:
    return build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[
            {
                "section_id": "completed",
                "title": "Completed",
                "order": 10,
                "items": [
                    {
                        "item_id": "release_2.4",
                        "title": "Release 2.4",
                        "summary": "Published the stable release.",
                        "value_rank": 50,
                    }
                ],
            }
        ],
    )


def forbidden_effect(*_: Any) -> dict[str, Any]:
    raise AssertionError("preview must not call external effects")


def main() -> None:
    registry = PeriodicReportAdapterRegistry()
    registry.register_source(issue_fix_periodic_report_source_adapter())
    registry.register_source(
        PeriodicReportSourceAdapter(
            source_id="release_notes",
            source_kind="release_activity",
            collect=release_source,
        )
    )
    registry.register_renderer(periodic_report_markdown_renderer_adapter())
    registry.register_sink(
        periodic_report_lark_sink_adapter(
            send=forbidden_effect,
            readback=forbidden_effect,
        )
    )
    registry.register_sink(
        periodic_report_openviking_sink_adapter(
            write=forbidden_effect,
            readback=forbidden_effect,
        )
    )

    issue_source = registry.collect(
        "issue_fix",
        {
            "schema_version": "issue_fix_outcome_collection_projection_v0",
            "goal_id": "example-goal",
            "generated_at": "2026-07-20T00:30:00Z",
            "issue_fix_outcomes": [
                {
                    "outcome_id": "example/repo:issue-12",
                    "title": "Fix retrieval regression",
                    "summary": "Merged with regression coverage.",
                    "priority": "P0",
                    "stage": "merged",
                    "status": "done",
                    "result": {"kind": "merged"},
                }
            ],
            "source_counts": {"unprojected_pr_lifecycle": 0},
            "warnings": [],
        },
    )
    release = registry.collect("release_notes", {})
    document = build_periodic_report_document(
        title="Maintenance report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[issue_source, release],
    )
    artifact = registry.render("markdown_v0", document)
    previews = [
        registry.deliver(
            sink_id,
            artifact,
            {"execute": False, "idempotency_key": f"preview-{sink_id}"},
        )
        for sink_id in ("lark_delivery", "openviking_archive")
    ]
    assert {item["source_id"] for item in document["source_snapshots"]} == {
        "issue_fix",
        "release_notes",
    }
    assert all(item["status"] == "pending" for item in previews)
    assert all(item["external_writes_performed"] is False for item in previews)
    print("periodic-report-adapters-smoke: ok")


if __name__ == "__main__":
    main()
