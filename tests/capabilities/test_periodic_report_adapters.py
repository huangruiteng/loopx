from __future__ import annotations

from typing import Any

import pytest

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


def _issue_fix_projection() -> dict[str, Any]:
    return {
        "schema_version": "issue_fix_outcome_collection_projection_v0",
        "goal_id": "project-maintenance",
        "generated_at": "2026-07-20T00:30:00Z",
        "issue_fix_outcomes": [
            {
                "outcome_id": "example/repo:issue-12",
                "title": "Fix high-value retrieval regression",
                "summary": "Merged with focused regression coverage.",
                "priority": "P0",
                "stage": "merged",
                "status": "done",
                "issue": {"url": "https://example.test/issues/12"},
                "pull_request": {"url": "https://example.test/pulls/34"},
                "result": {"kind": "merged"},
            },
            {
                "outcome_id": "example/repo:issue-13",
                "title": "Repair lifecycle projection",
                "summary": "Patch is ready; review remains open.",
                "priority": "P1",
                "stage": "review",
                "status": "in_progress",
                "issue": {"url": "https://example.test/issues/13"},
                "pull_request": {"url": "https://example.test/pulls/35"},
                "result": {"kind": "pull_request"},
                "next_action": "Obtain reviewer approval and merge.",
            },
        ],
        "source_counts": {"unprojected_pr_lifecycle": 0},
        "warnings": [],
    }


def _release_source(_: dict[str, Any]) -> dict[str, Any]:
    return build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        snapshot_ref="release:2026-w29",
        sections=[
            {
                "section_id": "completed",
                "title": "Completed",
                "order": 10,
                "items": [
                    {
                        "item_id": "release_2026w29",
                        "title": "Release 2.4",
                        "summary": "Published the stable release.",
                        "value_rank": 50,
                        "status": "published",
                        "source_ref": "https://example.test/releases/2.4",
                    }
                ],
            }
        ],
    )


def _registry(*, calls: list[str]) -> PeriodicReportAdapterRegistry:
    registry = PeriodicReportAdapterRegistry()
    registry.register_source(issue_fix_periodic_report_source_adapter())
    registry.register_source(
        PeriodicReportSourceAdapter(
            source_id="release_notes",
            source_kind="release_activity",
            collect=_release_source,
        )
    )
    registry.register_renderer(periodic_report_markdown_renderer_adapter())

    def lark_send(card: dict[str, Any], key: str) -> dict[str, str]:
        assert card["header"]["title"]["content"] == "Weekly maintenance"
        calls.append(f"lark:{key}")
        return {"message_id": "om_report_123"}

    registry.register_sink(
        periodic_report_lark_sink_adapter(
            send=lark_send,
            readback=lambda ref: {
                "verified": True,
                "message_id": ref,
            },
        )
    )

    def ov_write(payload: dict[str, Any], key: str) -> dict[str, str]:
        assert payload["semantic_type"] == "periodic_report"
        calls.append(f"openviking:{key}")
        return {
            "resource_uri": "viking://resources/reports/2026-w29",
            "result_id": "result-2026-w29",
        }

    registry.register_sink(
        periodic_report_openviking_sink_adapter(
            write=ov_write,
            readback=lambda ref: {
                "verified": True,
                "resource_uri": ref,
                "result_id": "result-2026-w29",
            },
        )
    )
    return registry


def test_registry_composes_issue_fix_and_second_domain_without_semantic_leak() -> None:
    calls: list[str] = []
    registry = _registry(calls=calls)
    issue_fix = registry.collect("issue_fix", _issue_fix_projection())
    release = registry.collect("release_notes", {})

    assert [item["title"] for item in issue_fix["sections"][0]["items"]] == [
        "Fix high-value retrieval regression"
    ]
    next_actions = next(
        section
        for section in issue_fix["sections"]
        if section["section_id"] == "next_actions"
    )
    assert next_actions["items"][0]["summary"] == (
        "Obtain reviewer approval and merge."
    )
    assert issue_fix["boundary"]["schedule_policy_owned_by_source"] is False

    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00+08:00",
            "end_at": "2026-07-20T00:00:00+08:00",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[release, issue_fix],
    )
    completed = document["sections"][0]
    assert completed["section_id"] == "completed"
    assert [item["source_id"] for item in completed["items"]] == [
        "issue_fix",
        "release_notes",
    ]
    assert document["boundary"]["renderer_owns_business_semantics"] is False

    artifact = registry.render("markdown_v0", document)
    assert "Fix high-value retrieval regression" in artifact["content"]
    assert "Release 2.4" in artifact["content"]
    assert artifact["boundary"]["schedule_policy_applied"] is False
    assert registry.describe() == {
        "schema_version": "periodic_report_adapter_registry_v0",
        "sources": ["issue_fix", "release_notes"],
        "renderers": ["markdown_v0"],
        "sinks": ["lark_delivery", "openviking_archive"],
        "schedule_policy_owned": False,
        "business_evidence_judged": False,
    }


def test_sink_preview_has_no_effect_and_execute_requires_exact_readback() -> None:
    calls: list[str] = []
    registry = _registry(calls=calls)
    issue_fix = registry.collect("issue_fix", _issue_fix_projection())
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[issue_fix],
    )
    artifact = registry.render("markdown_v0", document)

    preview = registry.deliver(
        "lark_delivery",
        artifact,
        {"execute": False, "idempotency_key": "delivery-preview"},
    )
    assert preview["status"] == "pending"
    assert preview["external_writes_performed"] is False
    assert calls == []

    lark = registry.deliver(
        "lark_delivery",
        artifact,
        {
            "execute": True,
            "idempotency_key": "delivery-live",
            "title": "Weekly maintenance",
        },
    )
    archive = registry.deliver(
        "openviking_archive",
        artifact,
        {"execute": True, "idempotency_key": "archive-live"},
    )
    assert lark["status"] == "sent"
    assert archive["status"] == "sent"
    assert archive["result_id"] == "result-2026-w29"
    assert calls == ["lark:delivery-live", "openviking:archive-live"]
    for result in (lark, archive):
        assert result["readback_verified"] is True
        assert result["schedule_policy_applied"] is False
        assert result["business_evidence_judged"] is False


def test_registry_rejects_identity_drift_and_duplicate_adapters() -> None:
    registry = PeriodicReportAdapterRegistry()
    adapter = PeriodicReportSourceAdapter(
        source_id="release_notes",
        source_kind="release_activity",
        collect=_release_source,
    )
    registry.register_source(adapter)
    with pytest.raises(ValueError, match="duplicate periodic report adapter"):
        registry.register_source(adapter)

    drifting = PeriodicReportSourceAdapter(
        source_id="declared_source",
        source_kind="release_activity",
        collect=_release_source,
    )
    second = PeriodicReportAdapterRegistry()
    second.register_source(drifting)
    with pytest.raises(ValueError, match="different source_id"):
        second.collect("declared_source", {})
