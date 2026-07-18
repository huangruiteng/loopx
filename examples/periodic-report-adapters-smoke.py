#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.issue_fix.periodic_report import (  # noqa: E402
    issue_fix_periodic_report_source_adapter,
)
from loopx.capabilities.periodic_report import (  # noqa: E402
    PeriodicReportAdapterRegistry,
    PeriodicReportSourceAdapter,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_markdown import (  # noqa: E402
    periodic_report_markdown_renderer_adapter,
)
from loopx.presentation.renderers.periodic_report_html import (  # noqa: E402
    periodic_report_html_renderer_adapter,
)
from loopx.extensions.lark.presentation.periodic_report import (  # noqa: E402
    periodic_report_lark_sink_adapter,
)
from loopx.presentation.sinks.openviking_periodic_report import (  # noqa: E402
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
    registry.register_renderer(periodic_report_html_renderer_adapter())
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
    html_artifact = registry.render("html_artifact_v0", document)
    lark_preview = registry.deliver(
        "lark_delivery",
        artifact,
        {"execute": False, "idempotency_key": "preview-lark_delivery"},
    )
    archive_preview = registry.deliver(
        "openviking_archive",
        artifact,
        {
            "execute": False,
            "idempotency_key": "preview-openviking_archive",
            "document": document,
            "archive_root_uri": "viking://resources/reports",
            "delivery_receipts": [],
            "semantic_tags": ["maintenance"],
            "memory_conclusions": [],
        },
    )
    previews = [lark_preview, archive_preview]
    assert {item["source_id"] for item in document["source_snapshots"]} == {
        "issue_fix",
        "release_notes",
    }
    assert all(item["status"] == "pending" for item in previews)
    assert all(item["external_writes_performed"] is False for item in previews)
    assert archive_preview["memory_reference"]["full_report_copied"] is False
    assert html_artifact["renderer_kind"] == "html"
    assert html_artifact["single_file"] is True
    assert "Fix retrieval regression" in html_artifact["content"]
    print("periodic-report-adapters-smoke: ok")


if __name__ == "__main__":
    main()
