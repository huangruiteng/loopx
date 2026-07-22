from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from loopx.capabilities.periodic_report import build_periodic_report_activation
from loopx.capabilities.periodic_report import cli as periodic_report_cli
from loopx.capabilities.periodic_report.extension_envelope import (
    build_openviking_archive_execution_envelope,
)
from loopx.extensions.bundled import bundled_extension_manifest
from loopx.extensions.manifest import load_extension_manifest
from loopx.extensions.openviking_periodic_report import activation as activation_module
from loopx.extensions.openviking_periodic_report.activation import (
    resolve_openviking_periodic_report_activation,
    validate_openviking_periodic_report_activation,
)
from loopx.extensions.openviking_periodic_report.provider import (
    REQUEST_SCHEMA,
    archive_request,
)


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _profile(*, enabled: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "periodic_report_profile_v0",
        "enabled": enabled,
        "profile_id": "project_weekly",
        "profile_version": "v1",
        "trigger_policy": {
            "enabled_kinds": ["cadence_due", "vision_closed"],
            "minimum_interval_seconds": 0,
        },
        "source_bindings": [
            {
                "source_id": "project_state",
                "source_kind": "validated_outcomes",
                "adapter_id": "project_state_v0",
                "provider": {"kind": "builtin"},
            }
        ],
        "renderer_bindings": [
            {
                "renderer_id": "markdown",
                "renderer_kind": "markdown",
                "adapter_id": "markdown_v0",
                "provider": {"kind": "builtin"},
            }
        ],
        "sink_bindings": [
            {
                "schema_version": "periodic_report_sink_binding_v0",
                "sink_id": "openviking_archive",
                "sink_kind": "project_resource",
                "sink_role": "archive",
                "dependency_policy": "optional",
                "capability": {
                    "capability_id": "report.archive.write",
                    "capability_version": "v0",
                },
                "extension": {
                    "extension_id": "openviking-periodic-report",
                    "extension_version": "1.0.0",
                    "protocol": "periodic_report_sink_v0",
                },
            }
        ],
    }


def _document() -> dict[str, Any]:
    return {
        "schema_version": "periodic_report_document_v0",
        "title": "Project weekly report",
        "generated_at": "2026-07-20T09:00:00+08:00",
        "period_window": {
            "start_at": "2026-07-13T09:00:00+08:00",
            "end_at": "2026-07-20T09:00:00+08:00",
        },
        "profile": {"profile_id": "project_weekly", "profile_version": "v1"},
        "source_snapshots": [
            {
                "source_id": "project_state",
                "source_kind": "validated_outcomes",
                "status": "complete",
                "observed_at": "2026-07-20T08:59:00+08:00",
                "snapshot_digest": "sha256:" + "1" * 64,
                "snapshot_ref": "loopx://project/state",
                "item_count": 2,
                "retryable": False,
            }
        ],
        "sections": [],
    }


def _artifact(document: Mapping[str, Any]) -> dict[str, Any]:
    content = "# Project weekly report\n\n- shipped one verified outcome\n"
    return {
        "schema_version": "periodic_report_artifact_v0",
        "artifact_id": "weekly_markdown",
        "renderer_id": "markdown",
        "renderer_kind": "markdown",
        "artifact_ref": "loopx://periodic-report/project-weekly/report.md",
        "content": content,
        "content_digest": _sha256(content),
        "document_digest": _sha256(_canonical(document)),
    }


EXTENSION_REVISION = "revision-1"


def _request(
    *,
    execute: bool = True,
) -> dict[str, Any]:
    document = _document()
    request = {
        "schema_version": REQUEST_SCHEMA,
        "activation_receipt": build_periodic_report_activation(_profile()),
        "artifact": _artifact(document),
        "document": document,
        "context": {
            "sink_id": "openviking_archive",
            "idempotency_key": "weekly-project-2026-07-20",
            "archive_root_uri": "viking://resources/loopx/reports",
            "semantic_tags": ["project_weekly"],
        },
        "execute": execute,
    }
    if execute:
        request["execution_envelope"] = build_openviking_archive_execution_envelope(
            request,
            extension_revision=EXTENSION_REVISION,
        )
    return request


def _archive(
    request: Mapping[str, Any],
    *,
    client: "FakeOpenViking",
    extension_revision: str = EXTENSION_REVISION,
) -> dict[str, Any]:
    return archive_request(
        request,
        client=client,
        extension_revision=extension_revision,
    )


class FakeOpenViking:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.writes: list[str] = []

    def read(self, uri: str, offset: int = 0, limit: int = -1) -> str:
        del offset, limit
        if uri not in self.files:
            raise FileNotFoundError(uri)
        return self.files[uri]

    def write(
        self,
        uri: str,
        content: str,
        mode: str = "replace",
        wait: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        del wait, timeout
        if mode == "create" and uri in self.files:
            raise FileExistsError(uri)
        self.files[uri] = content
        self.writes.append(uri)
        return {"uri": uri}


def test_bundled_manifest_implements_core_capability_without_new_capability() -> None:
    manifest = load_extension_manifest(
        bundled_extension_manifest("openviking-periodic-report")
    )

    assert manifest["capabilities"] == []
    assert manifest["implementations"] == [
        {
            "capability_id": "periodic-report",
            "protocol": "periodic_report_sink_v0",
            "provider_id": "openviking-periodic-report",
            "provider_version": "1.0.0",
        }
    ]
    assert manifest["runtime"]["required_permissions"] == ["openviking_context_write"]


def test_activation_requires_enabled_profile_and_observed_runtime_capability() -> None:
    disabled = build_periodic_report_activation(_profile(enabled=False))
    with pytest.raises(ValueError, match="profile must be enabled"):
        validate_openviking_periodic_report_activation(
            disabled,
            available_capabilities=["openviking_context_write"],
            sink_id="openviking_archive",
        )

    enabled = build_periodic_report_activation(_profile())
    with pytest.raises(ValueError, match="observed runtime capability"):
        validate_openviking_periodic_report_activation(
            enabled,
            available_capabilities=[],
            sink_id="openviking_archive",
        )


def test_activation_binds_revision_ready_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        activation_module,
        "resolve_extension_binding",
        lambda *args, **kwargs: {
            "extension_id": "openviking-periodic-report",
            "provider_version": "1.0.0",
            "revision": "revision-1",
            "protocol": "periodic_report_sink_v0",
            "argv": ["provider"],
            "timeout_seconds": 30,
        },
    )

    resolved = resolve_openviking_periodic_report_activation(
        build_periodic_report_activation(_profile()),
        available_capabilities=["openviking_context_write"],
        sink_id="openviking_archive",
        state_file=Path("unused.json"),
    )

    assert resolved["extension_receipt"]["readback_verified"] is True
    assert resolved["extension_receipt"]["extension_revision"] == "revision-1"
    assert resolved["external_writes_performed"] is False


def test_capability_dispatch_creates_revision_bound_execution_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        activation_module,
        "resolve_openviking_periodic_report_activation",
        lambda *args, **kwargs: {
            "runtime_binding": {
                "schema_version": "loopx_extension_runtime_binding_v0",
                "extension_id": "openviking-periodic-report",
                "revision": EXTENSION_REVISION,
                "protocol": "periodic_report_sink_v0",
                "argv": ["provider"],
                "timeout_seconds": 30,
            },
            "extension_receipt": {"status": "ready"},
        },
    )

    def fake_execute(
        binding: Mapping[str, Any],
        *,
        request: Mapping[str, Any],
        environment: Mapping[str, str],
    ) -> dict[str, Any]:
        captured.update(
            {
                "binding": dict(binding),
                "request": dict(request),
                "environment": dict(environment),
            }
        )
        return {"ok": True}

    monkeypatch.setattr(
        periodic_report_cli,
        "execute_extension_runtime_binding",
        fake_execute,
    )
    request = _request(execute=False)
    request.pop("execute")
    args = SimpleNamespace(
        available_capability=["openviking_context_write"],
        runtime_root=None,
        openviking_url=None,
        openviking_path=None,
        openviking_config=None,
        openviking_actor_peer_id=None,
        openviking_api_key_env="OPENVIKING_API_KEY",
        execute=True,
    )

    result = periodic_report_cli._archive_openviking(request, args)

    provider_request = captured["request"]
    envelope = provider_request["execution_envelope"]
    assert envelope["action"] == "report.archive.write"
    assert envelope["extension"] == {
        "id": "openviking-periodic-report",
        "revision": EXTENSION_REVISION,
    }
    assert "available_capabilities" not in provider_request
    assert captured["environment"]["LOOPX_EXTENSION_REVISION"] == EXTENSION_REVISION
    assert result["extension_receipt"] == {"status": "ready"}


def test_capability_dispatch_rejects_caller_supplied_execution_envelope() -> None:
    request = _request(execute=False)
    request["execution_envelope"] = {"action": "report.archive.write"}

    with pytest.raises(ValueError, match="created by the capability command"):
        periodic_report_cli._archive_openviking(request, SimpleNamespace())


def test_archive_writes_markdown_then_manifest_and_exactly_replays() -> None:
    client = FakeOpenViking()
    request = _request()

    created = _archive(request, client=client)
    first_writes = list(client.writes)
    replayed = _archive(request, client=client)

    assert [uri.rsplit("/", 1)[-1] for uri in first_writes] == [
        "report.md",
        "manifest.json",
    ]
    assert created["status"] == "sent"
    assert created["write_status"] == "created"
    assert created["readback_verified"] is True
    assert replayed["status"] == "sent"
    assert replayed["write_status"] == "already_present"
    assert replayed["result_id"] == created["result_id"]
    assert client.writes == first_writes
    manifest = json.loads(client.files[first_writes[-1]])
    assert manifest["archive_commit"]["manifest_written_last"] is True
    assert manifest["archive_commit"]["result_id"] == created["result_id"]
    assert not any("html" in uri for uri in client.files)


def test_archive_dry_run_and_conflict_fail_closed() -> None:
    client = FakeOpenViking()
    preview = _archive(_request(execute=False), client=client)
    assert preview["status"] == "pending"
    assert preview["external_writes_performed"] is False
    assert client.files == {}

    request = _request()
    result = _archive(request, client=client)
    report_uri = next(
        item["resource_uri"]
        for item in result["resource_receipts"]
        if item["resource_kind"] == "report_body"
    )
    client.files[report_uri] = "tampered"
    with pytest.raises(ValueError, match="already differs"):
        _archive(request, client=client)

    client.files[report_uri] = _artifact(_document())["content"]
    different_key = _request()
    different_key["context"]["idempotency_key"] = "different-logical-delivery"
    different_key["execution_envelope"] = build_openviking_archive_execution_envelope(
        different_key,
        extension_revision=EXTENSION_REVISION,
    )
    with pytest.raises(ValueError, match="already differs"):
        _archive(different_key, client=client)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing", "execution_envelope must be an object"),
        ("action", "execution envelope action does not match"),
        ("scope", "execution envelope scope does not match"),
        ("wider_scope", "execution envelope scope does not match"),
        ("request", "execution envelope request_digest does not match"),
        ("revision", "execution envelope extension does not match"),
    ],
)
def test_provider_rechecks_execution_envelope_before_any_write(
    mutation: str,
    error: str,
) -> None:
    client = FakeOpenViking()
    request = _request()
    revision = EXTENSION_REVISION
    if mutation == "missing":
        request.pop("execution_envelope")
    elif mutation == "action":
        request["execution_envelope"]["action"] = "report.archive.delete"
    elif mutation == "scope":
        request["execution_envelope"]["scope"]["sink_id"] = "other_sink"
    elif mutation == "wider_scope":
        request["execution_envelope"]["scope"]["archive_root_uri"] = "viking://resources"
    elif mutation == "request":
        request["document"]["title"] = "Different report"
    elif mutation == "revision":
        revision = "different-revision"

    with pytest.raises(ValueError, match=error):
        _archive(request, client=client, extension_revision=revision)

    assert client.files == {}
