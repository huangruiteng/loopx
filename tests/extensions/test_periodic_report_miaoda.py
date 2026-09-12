from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from loopx.capabilities.periodic_report import (
    PeriodicReportAdapterRegistry,
    build_periodic_report_delivery_receipt,
    build_periodic_report_document,
    build_periodic_report_extension_readiness,
    build_periodic_report_generation_bundle,
    build_periodic_report_source_result,
)
from loopx.cli import main
from loopx.extensions.manifest import load_extension_manifest
from loopx.extensions.lark.miaoda_report import (
    DELIVERY_INTENT_SCHEMA,
    LarkCliMiaodaProvider,
    MIAODA_DELIVERY_REQUEST_SCHEMA,
    deliver_periodic_report_to_miaoda,
)
from loopx.extensions.lark.presentation import periodic_report as miaoda_module
from loopx.extensions.lark.presentation import periodic_report_miaoda_html_sink_adapter
from loopx.presentation.renderers.periodic_report_html import (
    periodic_report_html_renderer_adapter,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    periodic_report_markdown_renderer_adapter,
)


ROOT = Path(__file__).resolve().parents[2]
LARK_EXTENSION_VERSION = str(
    load_extension_manifest(ROOT / "loopx/extensions/lark/extension.toml")["provider"][
        "version"
    ]
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


def _delivery_request() -> dict[str, Any]:
    document = _document()
    artifact = periodic_report_html_renderer_adapter().render(document)
    generation = build_periodic_report_generation_bundle(
        document=document,
        artifacts=[artifact],
    )
    return {
        "schema_version": MIAODA_DELIVERY_REQUEST_SCHEMA,
        "profile": {
            "schema_version": "periodic_report_profile_v0",
            "enabled": True,
            "profile_id": "maintenance",
            "profile_version": "v1",
            "source_bindings": [
                {
                    "source_id": "release_notes",
                    "source_kind": "release_activity",
                    "adapter_id": "release_activity_v0",
                    "provider": {"kind": "builtin"},
                }
            ],
            "renderer_bindings": [
                {
                    "renderer_id": "html",
                    "renderer_kind": "html",
                    "adapter_id": "html_artifact_v0",
                    "provider": {"kind": "builtin"},
                }
            ],
            "sink_bindings": [
                {
                    "schema_version": "periodic_report_sink_binding_v0",
                    "sink_id": "miaoda_html_delivery",
                    "sink_kind": "miaoda_html",
                    "sink_role": "delivery",
                    "dependency_policy": "optional",
                    "capability": {
                        "capability_id": "report.miaoda_html.publish",
                        "capability_version": "v0",
                    },
                    "extension": {
                        "extension_id": "loopx-lark",
                        "extension_version": LARK_EXTENSION_VERSION,
                        "protocol": "periodic_report_sink_v0",
                    },
                }
            ],
        },
        "generation_bundle": generation,
        "delivery_intent": {
            "schema_version": DELIVERY_INTENT_SCHEMA,
            "kind": "hosted",
            "sink_id": "miaoda_html_delivery",
            "sink_kind": "miaoda_html",
            "app_id": "app_example123",
            "idempotency_key": "maintenance-week-29",
        },
    }


def _extension_activation() -> dict[str, Any]:
    return {
        "schema_version": "loopx_extension_activation_v0",
        "extension_id": "loopx-lark",
        "provider_version": LARK_EXTENSION_VERSION,
        "revision": "publicfixture123",
        "enabled": True,
        "doctor_verified": True,
        "required_permissions": ["lark.miaoda_html.publish"],
    }


def _sent_miaoda_delivery_receipt_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any]
]:
    request = _delivery_request()
    generation = request["generation_bundle"]["generation_receipt"]
    binding = request["profile"]["sink_bindings"][0]
    readiness = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[binding],
        extension_receipts=[
            {
                "extension_id": "loopx-lark",
                "extension_version": LARK_EXTENSION_VERSION,
                "protocol": "periodic_report_sink_v0",
                "status": "ready",
                "readback_verified": True,
                "capabilities": [binding["capability"]],
            }
        ],
    )
    sink_result = _registry(
        publish=lambda _artifact, app_id, _key: {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "release_id": "release_example123",
        },
        readback=lambda app_id, release_id: {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "is_published": True,
            "release_readback": {
                "release_id": release_id,
                "status": "finished",
                "verified": True,
            },
            "access_scope_readback": {
                "status": "unsupported_by_app_type",
                "retryable": False,
                "reason": "creative_html_scope_readback_unavailable",
            },
        },
    ).deliver(
        "miaoda_html_delivery",
        request["generation_bundle"]["artifacts"][0],
        {
            "execute": True,
            "idempotency_key": "weak-receipt-test",
            "app_id": "app_example123",
        },
    )
    return generation, readiness, sink_result


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
            "release_id": "release_example123",
        }

    def readback(app_id: str, release_id: str) -> dict[str, Any]:
        calls.append(f"readback:{app_id}:{release_id}")
        return {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "is_published": True,
            "release_readback": {
                "release_id": release_id,
                "status": "finished",
                "verified": True,
            },
            "access_scope_readback": {
                "status": "verified",
                "retryable": False,
                "scope": "Range",
                "require_login": True,
            },
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
    assert result["release_readback"] == {
        "release_id": "release_example123",
        "status": "finished",
        "verified": True,
    }
    assert result["access_scope_readback"]["status"] == "verified"
    assert result["content_readback"] == {
        "status": "unavailable",
        "digest_verified": False,
        "reason": "provider_does_not_expose_remote_content_digest",
    }
    assert result["access_scope"] == "Range"
    assert result["require_login"] is True
    assert calls == [
        "publish:app_example123:miaoda-live",
        "readback:app_example123:release_example123",
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
            "release_id": "release_example123",
        },
        readback=lambda app_id, release_id: {
            "app_id": app_id,
            "online_url": "https://example.test/app/other",
            "is_published": True,
            "release_readback": {
                "release_id": release_id,
                "status": "processing",
                "verified": False,
            },
            "access_scope_readback": {
                "status": "unsupported_by_app_type",
                "retryable": False,
                "reason": "creative_html_scope_readback_unavailable",
            },
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


def test_miaoda_access_scope_failure_does_not_erase_finished_release() -> None:
    artifact = periodic_report_html_renderer_adapter().render(_document())
    result = _registry(
        publish=lambda _artifact, app_id, _key: {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "release_id": "release_example123",
        },
        readback=lambda app_id, release_id: {
            "app_id": app_id,
            "online_url": "https://example.test/app/app_example123",
            "is_published": True,
            "release_readback": {
                "release_id": release_id,
                "status": "finished",
                "verified": True,
            },
            "access_scope_readback": {
                "status": "unavailable",
                "retryable": True,
                "reason": "provider_query_failed",
            },
        },
    ).deliver(
        "miaoda_html_delivery",
        artifact,
        {
            "execute": True,
            "idempotency_key": "scope-readback-unavailable",
            "app_id": "app_example123",
        },
    )

    assert result["status"] == "sent"
    assert result["readback_verified"] is True
    assert result["access_scope_readback"] == {
        "status": "unavailable",
        "retryable": True,
        "reason": "provider_query_failed",
    }


def test_hosted_intent_preview_is_not_satisfied_by_local_html() -> None:
    def forbidden(*_: Any) -> dict[str, Any]:
        raise AssertionError("preview must not call lark-cli")

    result = deliver_periodic_report_to_miaoda(
        _delivery_request(),
        extension_activation=_extension_activation(),
        execute=False,
        runner=forbidden,
    )

    assert result["ok"] is True
    assert result["status"] == "pending_execution"
    assert result["intent_satisfied"] is False
    assert result["generation_usable"] is True
    assert result["sink_result"]["status"] == "pending"
    assert result["delivery_receipt"]["status"] == "pending"
    assert result["boundary"]["local_generation_satisfies_intent"] is False
    assert result["boundary"]["external_writes_performed"] is False


def test_hosted_intent_executes_lark_cli_publish_and_exact_readback() -> None:
    calls: list[list[str]] = []

    def runner(
        args: Any,
        cwd: Any = None,
        _timeout: Any = None,
    ) -> dict[str, Any]:
        command = [str(item) for item in args]
        calls.append(command)
        if "+html-publish" in command:
            assert command[-2:] == ["--format", "json"]
            assert "./index.html" in command
            assert cwd is not None
            assert (
                (cwd / "index.html")
                .read_text(encoding="utf-8")
                .startswith("<!doctype html>")
            )
            payload = {"ok": True, "data": {"release_id": "release_example"}}
        elif "+release-get" in command:
            assert command[command.index("--release-id") + 1] == "release_example"
            payload = {
                "ok": True,
                "data": {
                    "release_id": "release_example",
                    "status": "finished",
                    "online_url": "https://example.test/page/example123",
                },
            }
        elif "+access-scope-get" in command:
            return {
                "returncode": 1,
                "stderr": json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "code": 40002,
                            "message": "unsupported for this app type",
                        },
                    }
                ),
            }
        else:
            payload = {
                "ok": True,
                "data": {
                    "has_more": False,
                    "page_token": "",
                    "items": [
                        {
                            "app_id": "app_example123",
                            "app_type": "html",
                            "is_published": True,
                            "online_url": "https://example.test/page/example123",
                        }
                    ],
                },
            }
        return {"returncode": 0, "stdout": json.dumps(payload)}

    result = deliver_periodic_report_to_miaoda(
        _delivery_request(),
        extension_activation=_extension_activation(),
        execute=True,
        cli_bin="lark-cli",
        runner=runner,
    )

    assert result["ok"] is True
    assert result["status"] == "satisfied"
    assert result["intent_satisfied"] is True
    assert result["sink_result"]["readback_verified"] is True
    assert result["sink_result"]["release_readback"]["status"] == "finished"
    assert result["sink_result"]["access_scope_readback"] == {
        "status": "unsupported_by_app_type",
        "retryable": False,
        "reason": "creative_html_scope_readback_unavailable",
    }
    assert result["sink_result"]["content_readback"]["digest_verified"] is False
    assert result["delivery_receipt"]["status"] == "succeeded"
    sink_receipt = result["delivery_receipt"]["sink_receipts"][0]
    assert sink_receipt["release_readback"]["release_id"] == "release_example"
    assert sink_receipt["access_scope_readback"]["status"] == (
        "unsupported_by_app_type"
    )
    assert sink_receipt["content_readback"]["status"] == "unavailable"
    assert [
        next((item for item in call if item.startswith("+")), "") for call in calls
    ] == [
        "+html-publish",
        "+list",
        "+list",
        "+release-get",
        "+access-scope-get",
    ]


def test_miaoda_access_scope_protocol_failure_is_retryable_evidence() -> None:
    def runner(
        args: Any,
        _cwd: Any = None,
        _timeout: Any = None,
    ) -> dict[str, Any]:
        command = [str(item) for item in args]
        if "+access-scope-get" in command:
            return {"returncode": 1, "stderr": "provider returned no JSON"}
        if "+release-get" in command:
            payload = {
                "ok": True,
                "data": {"release_id": "release_example", "status": "finished"},
            }
        else:
            payload = {
                "ok": True,
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "app_id": "app_example123",
                            "app_type": "html",
                            "is_published": True,
                            "online_url": "https://example.test/page/example123",
                        }
                    ],
                },
            }
        return {"returncode": 0, "stdout": json.dumps(payload)}

    observed = LarkCliMiaodaProvider(
        cli_bin="lark-cli",
        runner=runner,
    ).readback("app_example123", "release_example")

    assert observed["release_readback"]["verified"] is True
    assert observed["access_scope_readback"] == {
        "status": "unavailable",
        "retryable": True,
        "reason": "provider_query_failed",
    }


@pytest.mark.parametrize(
    "missing_field",
    ["release_readback", "access_scope_readback", "content_readback"],
)
def test_delivery_receipt_rejects_weak_miaoda_success(
    missing_field: str,
) -> None:
    generation, readiness, canonical_result = _sent_miaoda_delivery_receipt_inputs()
    sink_result = deepcopy(canonical_result)
    sink_result.pop(missing_field)

    with pytest.raises(ValueError, match="missing structured readback"):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=readiness,
            sink_results=[sink_result],
        )


@pytest.mark.parametrize(
    ("invalid_evidence", "error"),
    [
        ("release_id", "requires exact release readback"),
        ("release_status", "requires exact release readback"),
        ("release_verified", "verified does not match exact release readback"),
        ("access_scope", "scope is required"),
        ("content_proof", "content_readback.status is invalid"),
    ],
)
def test_delivery_receipt_rejects_semantically_weak_miaoda_success(
    invalid_evidence: str,
    error: str,
) -> None:
    generation, readiness, canonical_result = _sent_miaoda_delivery_receipt_inputs()
    sink_result = deepcopy(canonical_result)
    if invalid_evidence == "release_id":
        sink_result["release_readback"] = {
            "release_id": "release_other",
            "status": "finished",
            "verified": False,
        }
    elif invalid_evidence == "release_status":
        sink_result["release_readback"] = {
            "release_id": sink_result["release_id"],
            "status": "processing",
            "verified": False,
        }
    elif invalid_evidence == "release_verified":
        sink_result["release_readback"]["verified"] = False
    elif invalid_evidence == "access_scope":
        sink_result["access_scope_readback"] = {
            "status": "verified",
            "retryable": False,
            "require_login": True,
        }
    else:
        sink_result["content_readback"] = {
            "status": "verified",
            "digest_verified": True,
        }

    with pytest.raises(ValueError, match=error):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=readiness,
            sink_results=[sink_result],
        )


def test_hosted_intent_requires_explicit_profile_sink() -> None:
    request = _delivery_request()
    request["profile"]["sink_bindings"] = []

    with pytest.raises(ValueError, match="exactly one profile sink"):
        deliver_periodic_report_to_miaoda(
            request,
            extension_activation=_extension_activation(),
        )


def test_publish_miaoda_cli_previews_typed_intent(
    tmp_path: Any,
    capsys: Any,
) -> None:
    runtime_root = tmp_path / "runtime"
    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "install",
                "--bundled",
                "loopx-lark",
                "--execute",
            ]
        )
        == 0
    )
    capsys.readouterr()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_delivery_request()), encoding="utf-8")

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "periodic-report",
                "publish-miaoda",
                "--request-json",
                str(request_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "periodic_report_miaoda_delivery_result_v0"
    assert payload["status"] == "pending_execution"
    assert payload["intent_satisfied"] is False
