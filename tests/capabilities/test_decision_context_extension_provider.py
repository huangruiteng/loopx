from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from loopx.capabilities.decision_context import extension_provider as provider_module
from loopx.capabilities.decision_context.extension_provider import (
    build_extension_context_provider,
)
from loopx.extensions.runtime import (
    ExtensionCapabilityResolution,
    disable_extension,
    doctor_installed_extension,
    enable_extension,
    install_extension,
)


OBSERVED_AT = "2026-09-05T00:00:00+00:00"
PRIVATE_TRANSCRIPT = "Private peer reasoning remains transient."
PRIVATE_RESOURCE_REF = "obelisk:codex:thread-a:message-1"
READY_RESOLUTION = ExtensionCapabilityResolution(
    status="ready",
    extension_id="loopx-obelisk",
    installed=True,
    enabled=True,
    doctor_verified=True,
    next_action=None,
    binding={
        "schema_version": "loopx_extension_runtime_binding_v0",
        "extension_id": "loopx-obelisk",
        "provider_version": "0.1.0",
        "timeout_seconds": 30,
        "argv": ["loopx-obelisk"],
    },
)


def _state_file(tmp_path: Path) -> Path:
    path = tmp_path / "extensions" / "state.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_extension_state_v0",
                "extensions": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def _retrieve(provider: Any) -> Any:
    return provider.retrieve(
        namespace="peer-session",
        scope_ref="host-session:codex:thread-a",
        query="current implementation decision",
        query_summary="peer task decision",
        max_results=4,
        timeout_seconds=10,
        observed_at=OBSERVED_AT,
    )


def _provider_executable(path: Path) -> Path:
    path.write_text(
        f"""#!{sys.executable}
import json
import sys

if "--doctor" in sys.argv:
    raise SystemExit(0)

request = json.load(sys.stdin)
json.dump({{
    "schema_version": "decision_context_advisory_retrieve_response_v0",
    "ok": True,
    "status": "completed",
    "reason_code": None,
    "items": [{{
        "resource_ref": "obelisk:codex:thread-a:message-1",
        "summary": "Historical Codex task assistant",
        "content": "{PRIVATE_TRANSCRIPT}",
        "score": -0.75
    }}]
}}, sys.stdout)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _manifest(path: Path, *, entrypoint: Path) -> Path:
    path.write_text(
        f"""schema_version = "loopx_extension_manifest_v0"
id = "loopx-obelisk"
version = "0.1.0"
requires_loopx_api = ">=1,<2"
permissions = ["decision_context.read"]

[runtime]
protocol = "decision_context_advisory_provider_v0"
entrypoint = {json.dumps(str(entrypoint))}
doctor_args = ["--doctor"]
required_permissions = ["decision_context.read"]
timeout_seconds = 30

[[implements]]
capability_id = "decision-context"
protocol = "decision_context_advisory_provider_v0"
""",
        encoding="utf-8",
    )
    return path


def test_provider_resolves_one_lifecycle_binding_and_keeps_content_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = _state_file(tmp_path)
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=_provider_executable(tmp_path / "provider"),
    )
    install_extension(manifest, state_file=state_file, execute=True)
    requests: list[dict[str, Any]] = []
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )

    def execute(binding: object, *, request: dict[str, Any]) -> dict[str, Any]:
        assert isinstance(binding, dict)
        assert binding["timeout_seconds"] == 10
        requests.append(request)
        return {
            "schema_version": "decision_context_advisory_retrieve_response_v0",
            "ok": True,
            "status": "completed",
            "reason_code": None,
            "items": [
                {
                    "resource_ref": PRIVATE_RESOURCE_REF,
                    "summary": "Historical Codex task assistant",
                    "content": PRIVATE_TRANSCRIPT,
                    "score": -0.75,
                }
            ],
        }

    monkeypatch.setattr(
        provider_module,
        "execute_extension_runtime_binding",
        execute,
    )

    provider = build_extension_context_provider(
        {"provider": "extension"},
        runtime_root=tmp_path,
    )
    result = _retrieve(provider)
    public = result.public_packet()
    serialized = json.dumps(public, sort_keys=True)

    assert result.provider == "loopx-obelisk"
    assert requests[0]["scope_ref"] == "host-session:codex:thread-a"
    assert result.items[0].content == PRIVATE_TRANSCRIPT
    assert public["provider"] == "loopx-obelisk"
    assert public["results"][0]["summary"] == (
        "Historical Codex task assistant"
    )
    assert PRIVATE_TRANSCRIPT not in serialized
    assert PRIVATE_RESOURCE_REF not in serialized


def test_provider_runs_only_through_enabled_doctor_ready_extension(
    tmp_path: Path,
) -> None:
    state_file = _state_file(tmp_path)
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=_provider_executable(tmp_path / "provider"),
    )
    install_extension(manifest, state_file=state_file, execute=True)

    provider = build_extension_context_provider(
        {"provider": "extension"},
        runtime_root=tmp_path,
    )
    result = _retrieve(provider)
    assert result.status == "completed"
    assert result.provider == "loopx-obelisk"
    assert result.provider_version == "0.1.0"
    assert result.items[0].content == PRIVATE_TRANSCRIPT

    disable_extension(
        "loopx-obelisk",
        state_file=state_file,
        execute=True,
    )
    unavailable = build_extension_context_provider(
        {"provider": "extension"},
        runtime_root=tmp_path,
    )
    unavailable_retrieval = _retrieve(unavailable)
    receipt = unavailable_retrieval.public_packet()
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "extension_disabled"
    assert unavailable_retrieval.provider_readiness["next_action"] == (
        "enable_extension"
    )


def test_retrieval_readiness_uses_the_same_lifecycle_snapshot(
    tmp_path: Path,
) -> None:
    state_file = _state_file(tmp_path)
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=_provider_executable(tmp_path / "provider"),
    )
    install_extension(manifest, state_file=state_file, execute=True)
    provider = build_extension_context_provider(
        {"provider": "extension", "extension_id": "loopx-obelisk"},
        runtime_root=tmp_path,
    )
    disable_extension(
        "loopx-obelisk",
        state_file=state_file,
        execute=True,
    )

    retrieval = _retrieve(provider)

    assert retrieval.status == "unavailable"
    assert retrieval.reason_code == "extension_disabled"
    assert retrieval.provider_readiness == {
        "schema_version": "loopx_extension_provider_readiness_v0",
        "extension_id": "loopx-obelisk",
        "status": "extension_disabled",
        "installed": True,
        "enabled": False,
        "doctor_verified": False,
        "next_action": "enable_extension",
    }


def test_profile_config_cannot_override_extension_lifecycle_route(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError, match="unsupported fields: extension_state_file"
    ):
        build_extension_context_provider(
            {
                "provider": "extension",
                "extension_id": "loopx-obelisk",
                "extension_state_file": str(tmp_path / "other-state.json"),
            },
            runtime_root=tmp_path / "invocation-runtime",
        )


def test_missing_extension_is_typed_unavailable_without_running_provider(
    tmp_path: Path,
) -> None:
    config = {"provider": "extension", "extension_id": "loopx-obelisk"}
    provider = build_extension_context_provider(config, runtime_root=tmp_path)
    missing_retrieval = _retrieve(provider)
    receipt = missing_retrieval.public_packet()

    assert receipt["reason_code"] == "extension_not_installed"
    assert receipt["search_performed"] is False
    assert receipt["read_performed"] is False
    assert missing_retrieval.provider_readiness == {
        "schema_version": "loopx_extension_provider_readiness_v0",
        "extension_id": "loopx-obelisk",
        "status": "extension_not_installed",
        "installed": False,
        "enabled": False,
        "doctor_verified": False,
        "next_action": "install_extension",
    }
    assert not (tmp_path / "extensions").exists()

    state_file = _state_file(tmp_path)
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=_provider_executable(tmp_path / "provider"),
    )
    install_extension(manifest, state_file=state_file, execute=True)
    ready = build_extension_context_provider(config, runtime_root=tmp_path)

    ready_retrieval = _retrieve(ready)
    assert ready_retrieval.status == "completed"
    assert ready_retrieval.provider_readiness["status"] == "ready"


def test_stale_doctor_degrades_then_recovers_without_profile_change(
    tmp_path: Path,
) -> None:
    state_file = _state_file(tmp_path)
    executable = _provider_executable(tmp_path / "provider")
    manifest = _manifest(tmp_path / "extension.toml", entrypoint=executable)
    install_extension(manifest, state_file=state_file, execute=True)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["extensions"]["loopx-obelisk"].pop("doctor_verified_revision")
    state_file.write_text(json.dumps(state), encoding="utf-8")

    unavailable = build_extension_context_provider(
        {"provider": "extension", "extension_id": "loopx-obelisk"},
        runtime_root=tmp_path,
    )
    unavailable_retrieval = _retrieve(unavailable)
    assert unavailable_retrieval.reason_code == "extension_doctor_not_ready"
    assert (
        unavailable_retrieval.provider_readiness["next_action"]
        == "run_extension_doctor"
    )

    doctor_installed_extension(
        "loopx-obelisk",
        state_file=state_file,
        execute=True,
    )
    ready = build_extension_context_provider(
        {"provider": "extension", "extension_id": "loopx-obelisk"},
        runtime_root=tmp_path,
    )

    ready_retrieval = _retrieve(ready)
    assert ready_retrieval.status == "completed"
    assert ready_retrieval.provider_readiness["status"] == "ready"


def test_disabled_extension_recovers_after_enable_without_config_change(
    tmp_path: Path,
) -> None:
    state_file = _state_file(tmp_path)
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=_provider_executable(tmp_path / "provider"),
    )
    install_extension(manifest, state_file=state_file, execute=True)
    config = {"provider": "extension", "extension_id": "loopx-obelisk"}
    disable_extension("loopx-obelisk", state_file=state_file, execute=True)

    unavailable = build_extension_context_provider(config, runtime_root=tmp_path)
    unavailable_retrieval = _retrieve(unavailable)
    assert unavailable_retrieval.reason_code == "extension_disabled"
    assert unavailable_retrieval.provider_readiness["next_action"] == (
        "enable_extension"
    )

    enable_extension("loopx-obelisk", state_file=state_file, execute=True)
    ready = build_extension_context_provider(config, runtime_root=tmp_path)

    ready_retrieval = _retrieve(ready)
    assert ready_retrieval.status == "completed"
    assert ready_retrieval.provider_readiness["status"] == "ready"


def test_provider_rejects_unbounded_or_extra_extension_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )
    monkeypatch.setattr(
        provider_module,
        "execute_extension_runtime_binding",
        lambda *_, **__: {
            "schema_version": "decision_context_advisory_retrieve_response_v0",
            "ok": True,
            "status": "completed",
            "reason_code": None,
            "items": [],
            "authority_revision": 7,
        },
    )
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="unsupported: authority_revision"):
        _retrieve(provider)


def test_provider_rejects_missing_response_or_item_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )
    responses = iter(
        [
            {
                "schema_version": "decision_context_advisory_retrieve_response_v0",
                "ok": True,
                "status": "completed",
                "reason_code": None,
            },
            {
                "schema_version": "decision_context_advisory_retrieve_response_v0",
                "ok": True,
                "status": "completed",
                "reason_code": None,
                "items": [
                    {
                        "resource_ref": PRIVATE_RESOURCE_REF,
                        "summary": "Historical Codex task assistant",
                        "content": PRIVATE_TRANSCRIPT,
                    }
                ],
            },
        ]
    )
    monkeypatch.setattr(
        provider_module,
        "execute_extension_runtime_binding",
        lambda *_, **__: next(responses),
    )
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="missing: items"):
        _retrieve(provider)
    with pytest.raises(ValueError, match="missing: score"):
        _retrieve(provider)


def test_provider_rejects_non_finite_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )
    monkeypatch.setattr(
        provider_module,
        "execute_extension_runtime_binding",
        lambda *_, **__: {
            "schema_version": "decision_context_advisory_retrieve_response_v0",
            "ok": True,
            "status": "completed",
            "reason_code": None,
            "items": [
                {
                    "resource_ref": "obelisk:codex:thread-a:message-1",
                    "summary": "Historical Codex task assistant",
                    "content": PRIVATE_TRANSCRIPT,
                    "score": float("nan"),
                }
            ],
        },
    )
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="score must be finite"):
        _retrieve(provider)


@pytest.mark.parametrize(
    "timeout_seconds",
    [0.5, float("nan"), float("inf")],
)
def test_provider_rejects_invalid_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timeout_seconds: float,
) -> None:
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="between 1 and 120"):
        provider.retrieve(
            namespace="peer-session",
            scope_ref="host-session:codex:thread-a",
            query="current implementation decision",
            query_summary="peer task decision",
            max_results=4,
            timeout_seconds=timeout_seconds,
            observed_at=OBSERVED_AT,
        )


def test_provider_preserves_fractional_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )

    def execute(binding: object, *, request: dict[str, Any]) -> dict[str, Any]:
        assert isinstance(binding, dict)
        assert binding["timeout_seconds"] == 1.5
        requests.append(request)
        return {
            "schema_version": "decision_context_advisory_retrieve_response_v0",
            "ok": True,
            "status": "completed",
            "reason_code": None,
            "items": [],
        }

    monkeypatch.setattr(provider_module, "execute_extension_runtime_binding", execute)
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    result = provider.retrieve(
        namespace="peer-session",
        scope_ref="host-session:codex:thread-a",
        query="current implementation decision",
        query_summary="peer task decision",
        max_results=4,
        timeout_seconds=1.5,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "completed"
    assert requests[0]["timeout_seconds"] == 1.5


def test_provider_rejects_non_integer_result_limit() -> None:
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=Path("extensions.json"),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="max_results must be an integer"):
        provider.retrieve(
            namespace="peer-session",
            scope_ref="host-session:codex:thread-a",
            query="current implementation decision",
            query_summary="peer task decision",
            max_results=1.5,  # type: ignore[arg-type]
            timeout_seconds=10,
            observed_at=OBSERVED_AT,
        )


@pytest.mark.parametrize(
    ("status", "reason_code", "expected_error"),
    [
        ("completed", "provider_unavailable", "cannot return reason_code"),
        ("unavailable", None, "requires reason_code"),
    ],
)
def test_provider_rejects_inconsistent_status_reason_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    reason_code: str | None,
    expected_error: str,
) -> None:
    monkeypatch.setattr(
        provider_module,
        "resolve_optional_capability_binding",
        lambda **_: READY_RESOLUTION,
    )
    monkeypatch.setattr(
        provider_module,
        "execute_extension_runtime_binding",
        lambda *_, **__: {
            "schema_version": "decision_context_advisory_retrieve_response_v0",
            "ok": True,
            "status": status,
            "reason_code": reason_code,
            "items": [],
        },
    )
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=_state_file(tmp_path),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match=expected_error):
        _retrieve(provider)


def test_provider_is_read_only() -> None:
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=Path("extensions.json"),
        extension_id="loopx-obelisk",
    )

    receipt = provider.sync(
        namespace="peer-session",
        resources=[("ref", "content")],
        timeout_seconds=10,
        observed_at=OBSERVED_AT,
        execute=True,
    ).public_packet()

    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "read_only_provider"
    assert receipt["external_writes_performed"] is False


def test_provider_rejects_private_text_in_public_query_summary() -> None:
    provider = provider_module.DecisionContextExtensionProvider(
        state_file=Path("extensions.json"),
        extension_id="loopx-obelisk",
    )

    with pytest.raises(ValueError, match="query_summary is not public safe"):
        provider.retrieve(
            namespace="peer-session",
            scope_ref="host-session:codex:thread-a",
            query="private query",
            query_summary="Read /Users/example/private/session.jsonl",
            max_results=4,
            timeout_seconds=10,
            observed_at=OBSERVED_AT,
        )
