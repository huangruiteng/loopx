from __future__ import annotations

from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_html import (
    periodic_report_html_renderer_adapter,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    periodic_report_markdown_renderer_adapter,
)


def _document() -> dict[str, object]:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[
            {
                "section_id": "completed",
                "title": "Completed <week>",
                "order": 10,
                "items": [
                    {
                        "item_id": "release_2.4",
                        "title": "Release <script>alert(1)</script>",
                        "summary": "Published & verified.",
                        "value_rank": 50,
                        "status": "published",
                        "source_ref": "javascript:alert(1)",
                        "next_action": "Observe adoption.",
                    },
                    {
                        "item_id": "release_2.5",
                        "title": "Release candidate",
                        "summary": "Ready for review.",
                        "value_rank": 60,
                        "source_ref": "https://example.test/releases/2.5",
                    },
                ],
            }
        ],
    )
    return build_periodic_report_document(
        title="Engineering report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )


def test_html_artifact_is_self_contained_interactive_and_registry_valid() -> None:
    registry = PeriodicReportAdapterRegistry()
    registry.register_renderer(periodic_report_html_renderer_adapter())

    artifact = registry.render("html_artifact_v0", _document())
    content = artifact["content"]

    assert content.startswith("<!doctype html>")
    assert 'data-renderer="html_artifact_v0"' in content
    assert "data-report-search" in content
    assert 'data-section-filter="completed"' in content
    assert 'data-presentation="editorial_dense_v1"' in content
    assert "data-copy-markdown" in content
    assert "data-print-report" in content
    assert "Release &lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "<script>alert(1)</script>" not in content
    assert 'href="javascript:' not in content
    assert 'href="https://example.test/releases/2.5"' in content
    assert "https://cdn" not in content
    assert '<details class="supporting" data-supporting-context>' in content
    assert content.index("Release candidate") < content.index(
        "Report metadata and source receipts"
    )
    assert artifact["renderer_kind"] == "html"
    assert artifact["media_type"] == "text/html; charset=utf-8"
    assert artifact["single_file"] is True
    assert artifact["zero_build"] is True
    assert artifact["external_dependencies"] == []
    assert artifact["presentation_profile"] == "editorial_dense_v1"
    assert artifact["content_policy"] == {
        "primary_body_fields": [
            "title",
            "status",
            "tags",
            "summary",
            "next_action",
            "source_ref",
        ],
        "supporting_context": "collapsed",
        "process_narration_default_visible": False,
    }
    assert artifact["boundary"] == {
        "schedule_policy_applied": False,
        "business_evidence_judged": False,
        "external_writes_performed": False,
    }


def test_html_artifact_is_deterministic_for_the_same_document() -> None:
    renderer = periodic_report_html_renderer_adapter()
    first = renderer.render(_document())
    second = renderer.render(_document())

    assert first["content"] == second["content"]
    assert first["content_digest"] == second["content_digest"]
    assert first["artifact_ref"] == second["artifact_ref"]


def test_html_and_markdown_share_one_document_and_primary_content() -> None:
    document = _document()
    html_artifact = periodic_report_html_renderer_adapter().render(document)
    markdown_artifact = periodic_report_markdown_renderer_adapter().render(document)

    assert html_artifact["document_digest"] == markdown_artifact["document_digest"]
    assert (
        html_artifact["companion_markdown_digest"]
        == markdown_artifact["content_digest"]
    )
    for expected in (
        "Release &lt;script&gt;alert(1)&lt;/script&gt;",
        "Published &amp; verified.",
        "Observe adoption.",
        "Release candidate",
        "Ready for review.",
    ):
        assert expected in html_artifact["content"]
    for expected in (
        "Release <script>alert(1)</script>",
        "Published & verified.",
        "Observe adoption.",
        "Release candidate",
        "Ready for review.",
    ):
        assert expected in markdown_artifact["content"]


def test_source_receipts_are_supporting_context_not_visible_body_copy() -> None:
    artifact = periodic_report_html_renderer_adapter().render(_document())
    content = artifact["content"]
    primary_body, supporting = content.split(
        '<details class="supporting" data-supporting-context>',
        maxsplit=1,
    )

    assert "Release candidate" in primary_body
    assert "snapshot_" not in primary_body
    assert "source receipts" not in primary_body.lower()
    assert "snapshot_" in supporting
    assert "source receipts" in supporting.lower()
