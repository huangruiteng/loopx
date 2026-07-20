from __future__ import annotations

from typing import Any

import pytest

from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.extensions.lark.presentation import periodic_report_miaoda_html_sink_adapter
from loopx.extensions.lark.presentation import periodic_report as miaoda_module
from loopx.presentation.renderers.periodic_report_html import (
    periodic_report_html_renderer_adapter,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    periodic_report_markdown_renderer_adapter,
)


def _document() -> dict[str, Any]:
    source = build_periodic_report_source_result(
        source_id="release_notes",
        source_kind="release_activity",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[],
    )
    return build_periodic_report_document(
        title="Maintenance report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "maintenance", "profile_version": "v1"},
        sources=[source],
    )


def _registry(*, publish: Any, readback: Any) -> PeriodicReportAdapterRegistry:
    registry = PeriodicReportAdapterRegistry()
    registry.register_sink(
        periodic_report_miaoda_html_sink_adapter(
            publish=publish,
            readback=readback,
        )
    )
    return registry


def test_miaoda_preview_runs_size_preflight_without_external_effects() -> None:
    artifact = periodic_report_html_renderer_adapter().render(_document())

    def forbidden(*_: Any) -> dict[str, Any]:
        raise AssertionError("preview must not call external effects")

    result = _registry(publish=forbidden, readback=forbidden).deliver(
        "miaoda_html_delivery",
        artifact,
        {
            "execute": False,
            "idempotency_key": "miaoda-preview",
            "app_id": "app_example123",
        },
    )

    assert result["status"] == "pending"
    assert result["external_writes_performed"] is False
    assert result["preflight"]["status"] == "passed"
    assert result["preflight"]["html_bytes"] > 0
    assert result["artifact_digest"] == artifact["content_digest"]


def test_miaoda_publish_requires_exact_app_and_url_readback() -> None:
    artifact = periodic_report_html_renderer_adapter().render(_document())
    calls: list[str] = []

    def publish(
        observed_artifact: dict[str, Any], app_id: str, key: str
    ) -> dict[str, Any]:
        assert observed_artifact["content_digest"] == artifact["content_digest"]
        calls.append(f"publish:{app_id}:{key}")
        return {
            "app_id": app_id,
            "url": "https://example.test/app/app_example123",
        }

    def readback(app_id: str) -> dict[str, Any]:
        calls.append(f"readback:{app_id}")
        return {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "is_published": True,
            "access_scope": "Range",
            "require_login": True,
        }

    result = _registry(publish=publish, readback=readback).deliver(
        "miaoda_html_delivery",
        artifact,
        {
            "execute": True,
            "idempotency_key": "miaoda-live",
            "app_id": "app_example123",
        },
    )

    assert result["status"] == "sent"
    assert result["receipt_ref"] == "https://example.test/app/app_example123"
    assert result["result_id"] == "app_example123"
    assert result["readback_verified"] is True
    assert result["access_scope"] == "Range"
    assert result["require_login"] is True
    assert calls == [
        "publish:app_example123:miaoda-live",
        "readback:app_example123",
    ]


def test_miaoda_publish_fails_closed_on_wrong_artifact_or_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document()
    markdown = periodic_report_markdown_renderer_adapter().render(document)
    registry = _registry(
        publish=lambda _artifact, app_id, _key: {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
        },
        readback=lambda app_id: {
            "app_id": app_id,
            "online_url": "https://example.test/app/other",
            "is_published": True,
        },
    )

    with pytest.raises(ValueError, match="requires an HTML artifact"):
        registry.deliver(
            "miaoda_html_delivery",
            markdown,
            {
                "execute": False,
                "idempotency_key": "wrong-renderer",
                "app_id": "app_example123",
            },
        )

    artifact = periodic_report_html_renderer_adapter().render(document)
    result = registry.deliver(
        "miaoda_html_delivery",
        artifact,
        {
            "execute": True,
            "idempotency_key": "wrong-readback",
            "app_id": "app_example123",
        },
    )
    assert result["status"] == "unknown"
    assert result["readback_verified"] is False
    assert result["retryable"] is True

    monkeypatch.setattr(miaoda_module, "MIAODA_HTML_MAX_BYTES", 1)
    with pytest.raises(ValueError, match="size limit exceeded"):
        registry.deliver(
            "miaoda_html_delivery",
            artifact,
            {
                "execute": False,
                "idempotency_key": "oversize",
                "app_id": "app_example123",
            },
        )
