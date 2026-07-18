from __future__ import annotations

from typing import Any

import pytest

from loopx.capabilities.issue_fix.periodic_report import (
    issue_fix_periodic_report_source_adapter,
)
from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    PeriodicReportSinkAdapter,
    PeriodicReportSourceAdapter,
    build_periodic_report_archive_bundle,
    build_periodic_report_document,
    build_periodic_report_source_result,
    build_periodic_report_trigger_decision,
)
from loopx.capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    PeriodicReportRendererAdapter,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    periodic_report_markdown_renderer_adapter,
)
from loopx.extensions.lark.presentation.periodic_report import (
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


def _archive_context(document: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    return {
        "execute": execute,
        "idempotency_key": "archive-live" if execute else "archive-preview",
        "document": document,
        "archive_root_uri": "viking://resources/reports",
        "delivery_receipts": [
            {
                "sink_id": "lark_delivery",
                "sink_kind": "lark_card",
                "sink_role": "delivery",
                "status": "sent",
                "receipt_ref": "message:example",
                "result_id": "message-result-example",
                "readback_verified": True,
            }
        ],
        "semantic_tags": ["maintenance", "weekly"],
        "memory_conclusions": [
            "Regression coverage should remain attached to the merged change."
        ],
    }


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

    archived: dict[str, dict[str, str]] = {}

    def ov_write(payload: dict[str, Any], key: str) -> dict[str, Any]:
        assert payload["semantic_type"] == "periodic_report_archive"
        assert payload["manifest"]["memory_policy"]["full_report_copied"] is False
        calls.append(f"openviking:{key}")
        resources = []
        for resource in payload["resources"]:
            result_id = f"result-{resource['resource_kind']}"
            archived[resource["resource_uri"]] = {
                "result_id": result_id,
                "content_digest": resource["content_digest"],
            }
            resources.append(
                {
                    "resource_kind": resource["resource_kind"],
                    "resource_uri": resource["resource_uri"],
                    "result_id": result_id,
                }
            )
        return {"resources": resources}

    registry.register_sink(
        periodic_report_openviking_sink_adapter(
            write=ov_write,
            readback=lambda ref: {
                "verified": True,
                "resource_uri": ref,
                **archived[ref],
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
        _archive_context(document, execute=True),
    )
    assert lark["status"] == "sent"
    assert archive["status"] == "sent"
    assert archive["result_id"] == "result-manifest"
    assert {item["resource_kind"] for item in archive["resource_receipts"]} == {
        "manifest",
        "report_body",
    }
    assert archive["memory_reference"]["full_report_copied"] is False
    assert "content" not in archive["memory_reference"]
    assert calls == ["lark:delivery-live", "openviking:archive-live"]
    for result in (lark, archive):
        assert result["readback_verified"] is True
        assert result["schedule_policy_applied"] is False
        assert result["business_evidence_judged"] is False


def test_lark_sink_rejects_private_card_context_before_send() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    artifact = periodic_report_markdown_renderer_adapter().render(document)
    calls: list[str] = []
    registry = PeriodicReportAdapterRegistry()
    registry.register_sink(
        periodic_report_lark_sink_adapter(
            send=lambda _card, key: calls.append(key) or {"message_id": "message"},
            readback=lambda ref: {"verified": True, "message_id": ref},
        )
    )

    with pytest.raises(ValueError, match="private path or credential-like value"):
        registry.deliver(
            "lark_delivery",
            artifact,
            {
                "execute": True,
                "idempotency_key": "delivery-private-context",
                "title": "/private/tmp/project-title",
            },
        )
    with pytest.raises(ValueError, match="title must be a string"):
        registry.deliver(
            "lark_delivery",
            artifact,
            {
                "execute": True,
                "idempotency_key": "delivery-structured-context",
                "title": {"to" + "ken": "super" + "sec" + "ret1234567890"},
            },
        )
    assert calls == []


def test_sink_factories_emit_canonical_custom_ids() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    artifact = periodic_report_markdown_renderer_adapter().render(document)
    registry = PeriodicReportAdapterRegistry()
    registry.register_sink(
        periodic_report_lark_sink_adapter(
            sink_id="Lark_Custom",
            send=lambda _card, _key: {},
            readback=lambda _ref: {},
        )
    )
    registry.register_sink(
        periodic_report_openviking_sink_adapter(
            sink_id="OpenViking_Custom",
            write=lambda _payload, _key: {},
            readback=lambda _ref: {},
        )
    )

    lark = registry.deliver(
        "Lark_Custom",
        artifact,
        {"execute": False, "idempotency_key": "lark-custom-preview"},
    )
    archive = registry.deliver(
        "OpenViking_Custom",
        artifact,
        _archive_context(document, execute=False),
    )
    assert lark["sink_id"] == "lark_custom"
    assert archive["sink_id"] == "openviking_custom"


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


def test_registry_rejects_renderer_artifact_for_another_document() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    stale = periodic_report_markdown_renderer_adapter().render(
        {**document, "title": "Another report"}
    )
    registry = PeriodicReportAdapterRegistry()
    registry.register_renderer(
        PeriodicReportRendererAdapter(
            renderer_id="stale_v0",
            renderer_kind="markdown",
            render=lambda _: {
                **stale,
                "schema_version": ARTIFACT_SCHEMA,
                "renderer_id": "stale_v0",
            },
        )
    )

    with pytest.raises(ValueError, match="does not match document"):
        registry.render("stale_v0", document)


def test_registry_snapshots_document_before_custom_renderer_mutation() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Original report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )

    def mutating_renderer(payload: dict[str, Any]) -> dict[str, Any]:
        payload["title"] = "Mutated report"
        rendered = periodic_report_markdown_renderer_adapter().render(payload)
        return {**rendered, "renderer_id": "mutating_v0"}

    registry = PeriodicReportAdapterRegistry()
    registry.register_renderer(
        PeriodicReportRendererAdapter(
            renderer_id="mutating_v0",
            renderer_kind="markdown",
            render=mutating_renderer,
        )
    )

    with pytest.raises(ValueError, match="does not match document"):
        registry.render("mutating_v0", document)
    assert document["title"] == "Original report"


def test_registry_rejects_stale_sent_sink_idempotency_key() -> None:
    registry = PeriodicReportAdapterRegistry()
    registry.register_sink(
        PeriodicReportSinkAdapter(
            sink_id="custom_delivery",
            sink_kind="message_channel",
            sink_role="delivery",
            deliver=lambda _artifact, _context: {
                "schema_version": "periodic_report_sink_result_v0",
                "sink_id": "custom_delivery",
                "sink_kind": "message_channel",
                "sink_role": "delivery",
                "status": "sent",
                "idempotency_key": "stale-key",
                "receipt_ref": "message:123",
                "readback_verified": True,
                "schedule_policy_applied": False,
                "business_evidence_judged": False,
            },
        )
    )
    artifact = {
        "schema_version": "periodic_report_artifact_v0",
        "artifact_id": "report",
        "renderer_id": "markdown_v0",
        "renderer_kind": "markdown",
        "artifact_ref": "artifact:report",
        "content": "# Report",
        "content_digest": "sha256:04e1d1467e73933d8841c0c22eca9710ee72d020f5d494b091d68d4d2efea89d",
        "document_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "boundary": {
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
            "external_writes_performed": False,
        },
    }

    with pytest.raises(ValueError, match="must match the delivery context"):
        registry.deliver(
            "custom_delivery",
            artifact,
            {"idempotency_key": "fresh-key"},
        )


def test_source_result_rejects_fractional_ranking_integer() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        build_periodic_report_source_result(
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
                            "item_id": "release",
                            "title": "Release",
                            "summary": "Released.",
                            "value_rank": 1.5,
                            "status": "published",
                        }
                    ],
                }
            ],
        )


def test_source_result_rejects_raw_fields_before_projection() -> None:
    with pytest.raises(ValueError, match="forbidden raw/private field"):
        build_periodic_report_source_result(
            source_id="release_notes",
            source_kind="release_activity",
            status="complete",
            observed_at="2026-07-20T00:40:00Z",
            sections=[
                {
                    "section_id": "completed",
                    "title": "Completed",
                    "items": [
                        {
                            "item_id": "release",
                            "title": "Release",
                            "summary": "Released.",
                            "raw_body": "must not be silently discarded",
                        }
                    ],
                }
            ],
        )


def test_source_result_requires_strict_retryable_boolean() -> None:
    with pytest.raises(ValueError, match="retryable must be a boolean"):
        build_periodic_report_source_result(
            source_id="release_notes",
            source_kind="release_activity",
            status="failed",
            observed_at="2026-07-20T00:40:00Z",
            sections=[],
            retryable="false",  # type: ignore[arg-type]
        )


def test_adapter_identities_are_canonicalized_for_registration_and_lookup() -> None:
    registry = PeriodicReportAdapterRegistry()
    adapter = PeriodicReportSourceAdapter(
        source_id="Release_Notes",
        source_kind="Release_Activity",
        collect=lambda _: build_periodic_report_source_result(
            source_id="release_notes",
            source_kind="release_activity",
            status="complete",
            observed_at="2026-07-20T00:40:00Z",
            sections=[],
        ),
    )
    registry.register_source(adapter)

    assert adapter.source_id == "release_notes"
    assert adapter.source_kind == "release_activity"
    assert registry.collect("Release_Notes", {})["source_id"] == "release_notes"


def test_source_result_rejects_credential_like_text_values() -> None:
    with pytest.raises(ValueError, match="private path or credential-like value"):
        build_periodic_report_source_result(
            source_id="release_notes",
            source_kind="release_activity",
            status="complete",
            observed_at="2026-07-20T00:40:00Z",
            sections=[
                {
                    "section_id": "completed",
                    "title": "Completed",
                    "items": [
                        {
                            "item_id": "release",
                            "title": "Release",
                            "summary": "to" + "ken=super" + "sec" + "retabcdef1234567890",
                            "status": "published",
                        }
                    ],
                }
            ],
        )


def test_document_window_uses_chronological_timestamp_order() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:00:00Z",
        sections=[],
    )

    with pytest.raises(ValueError, match="start_at must be earlier"):
        build_periodic_report_document(
            title="Invalid window",
            generated_at="2026-07-20T00:00:01Z",
            period_window={
                "start_at": "2026-07-20T00:00:00.100000Z",
                "end_at": "2026-07-20T00:00:00Z",
            },
            profile={"profile_id": "maintenance", "profile_version": "v1"},
            sources=[source],
        )

    valid = build_periodic_report_document(
        title="Valid window",
        generated_at="2026-07-20T00:00:01Z",
        period_window={
            "start_at": "2026-07-20T00:00:00Z",
            "end_at": "2026-07-20T00:00:00.100000Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    assert valid["period_window"]["end_at"].endswith(".100000Z")


def test_archive_bundle_rejects_artifact_for_another_document() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Current report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    stale_artifact = periodic_report_markdown_renderer_adapter().render(
        {**document, "title": "Previous report"}
    )

    with pytest.raises(ValueError, match="does not match document"):
        build_periodic_report_archive_bundle(
            artifact=stale_artifact,
            document=document,
            archive_root_uri="viking://resources/reports",
        )


def test_document_rejects_trigger_receipt_for_another_profile() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    trigger = build_periodic_report_trigger_decision(
        {
            "schema_version": "periodic_report_trigger_request_v0",
            "evaluated_at": "2026-07-20T01:00:00Z",
            "profile": {"profile_id": "another", "profile_version": "v1"},
            "trigger_policy": {"enabled_kinds": ["manual"]},
            "candidates": [
                {
                    "trigger_kind": "manual",
                    "observed_at": "2026-07-20T00:40:00Z",
                    "source_ref": "manual:another",
                    "evidence_digest": "sha256:another",
                    "facts": {"authorized": True},
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="must match the document profile"):
        build_periodic_report_document(
            title="Current report",
            generated_at="2026-07-20T01:00:00Z",
            period_window={
                "start_at": "2026-07-13T00:00:00Z",
                "end_at": "2026-07-20T00:00:00Z",
            },
            profile={"profile_id": "maintenance", "profile_version": "v1"},
            sources=[source],
            trigger_receipt=trigger,
        )


def test_archive_bundle_keeps_resource_history_separate_from_memory() -> None:
    calls: list[str] = []
    registry = _registry(calls=calls)
    source = registry.collect("issue_fix", _issue_fix_projection())
    trigger = build_periodic_report_trigger_decision(
        {
            "schema_version": "periodic_report_trigger_request_v0",
            "evaluated_at": "2026-07-20T01:00:00Z",
            "profile": {"profile_id": "maintenance", "profile_version": "v1"},
            "trigger_policy": {"enabled_kinds": ["vision_closed"]},
            "candidates": [
                {
                    "trigger_kind": "vision_closed",
                    "observed_at": "2026-07-20T00:50:00Z",
                    "source_ref": "vision:maintenance-stage",
                    "evidence_digest": "sha256:maintenance-stage-closed",
                    "facts": {
                        "transition": "vision_closed",
                        "acceptance": "validated",
                        "continuation": "successor_established",
                    },
                }
            ],
        }
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
        trigger_receipt=trigger,
    )
    artifact = registry.render("markdown_v0", document)
    context = _archive_context(document, execute=False)
    bundle = build_periodic_report_archive_bundle(
        artifact=artifact,
        document=document,
        archive_root_uri=context["archive_root_uri"],
        delivery_receipts=context["delivery_receipts"],
        semantic_tags=context["semantic_tags"],
        memory_conclusions=context["memory_conclusions"],
    )
    assert [item["resource_kind"] for item in bundle["resources"]] == [
        "report_body",
        "manifest",
    ]
    assert bundle["manifest"]["source_snapshots"][0]["source_id"] == "issue_fix"
    assert bundle["manifest"]["title"] == "Weekly maintenance"
    assert bundle["manifest"]["delivery_receipts"][0]["sink_id"] == "lark_delivery"
    assert bundle["manifest"]["trigger_receipt"]["report_kind"] == ("milestone_update")
    assert bundle["boundary"]["project_resource_is_history_source_of_truth"] is True
    assert bundle["memory_reference"] == {
        "schema_version": "periodic_report_memory_reference_v0",
        "archive_id": bundle["archive_id"],
        "report_uri": bundle["resources"][0]["resource_uri"],
        "manifest_uri": bundle["resources"][1]["resource_uri"],
        "semantic_tags": ["maintenance", "periodic_report", "weekly"],
        "conclusions": [
            "Regression coverage should remain attached to the merged change."
        ],
        "distillation_required": True,
        "full_report_copied": False,
    }


def test_archive_bundle_rejects_query_or_fragment_root() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    artifact = periodic_report_markdown_renderer_adapter().render(document)
    unsafe_root = "viking://resources/reports?" + "to" + "ken=value1234567890"

    with pytest.raises(ValueError, match="private path or credential-like value"):
        build_periodic_report_archive_bundle(
            artifact=artifact,
            document=document,
            archive_root_uri=unsafe_root,
            delivery_receipts=[],
            semantic_tags=[],
            memory_conclusions=[],
        )


@pytest.mark.parametrize(
    "unsafe_root",
    [
        "viking://resources/reports?",
        "viking://resources/reports#/",
        "viking://resources/reports/%2e%2e/private",
        "viking://resources/reports/%2Fprivate",
        "viking://resources/reports/%252e%252e/private",
    ],
)
def test_archive_bundle_rejects_ambiguous_resource_root(unsafe_root: str) -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    artifact = periodic_report_markdown_renderer_adapter().render(document)

    with pytest.raises(ValueError, match="must stay under"):
        build_periodic_report_archive_bundle(
            artifact=artifact,
            document=document,
            archive_root_uri=unsafe_root,
            delivery_receipts=[],
            semantic_tags=[],
            memory_conclusions=[],
        )


def test_archive_sink_fails_closed_on_result_id_or_digest_drift() -> None:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    document = build_periodic_report_document(
        title="Weekly maintenance",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )
    renderer = periodic_report_markdown_renderer_adapter()
    artifact = renderer.render(document)
    written: dict[str, dict[str, str]] = {}

    def write(payload: dict[str, Any], _: str) -> dict[str, Any]:
        resources = []
        for item in payload["resources"]:
            result_id = f"result-{item['resource_kind']}"
            written[item["resource_uri"]] = {
                "result_id": result_id,
                "content_digest": item["content_digest"],
            }
            resources.append(
                {
                    "resource_kind": item["resource_kind"],
                    "resource_uri": item["resource_uri"],
                    "result_id": result_id,
                }
            )
        return {"resources": resources}

    sink = periodic_report_openviking_sink_adapter(
        write=write,
        readback=lambda uri: {
            "verified": True,
            "resource_uri": uri,
            "result_id": written[uri]["result_id"],
            "content_digest": (
                "sha256:" + "0" * 64
                if uri.endswith("manifest.json")
                else written[uri]["content_digest"]
            ),
        },
    )
    registry = PeriodicReportAdapterRegistry()
    registry.register_sink(sink)
    result = registry.deliver(
        "openviking_archive",
        artifact,
        _archive_context(document, execute=True),
    )
    assert result["status"] == "unknown"
    assert result["retryable"] is True
    assert result["readback_verified"] is False
