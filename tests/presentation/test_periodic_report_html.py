from __future__ import annotations

from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_html import (
    periodic_report_html_renderer_adapter,
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
    assert "Release &lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "<script>alert(1)</script>" not in content
    assert 'href="javascript:' not in content
    assert 'href="https://example.test/releases/2.5"' in content
    assert "https://cdn" not in content
    assert artifact["renderer_kind"] == "html"
    assert artifact["media_type"] == "text/html; charset=utf-8"
    assert artifact["single_file"] is True
    assert artifact["zero_build"] is True
    assert artifact["external_dependencies"] == []
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
