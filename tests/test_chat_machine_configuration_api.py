from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from loopx.capabilities.machine_configuration.contract import (
    MachineConfigurationNamespace,
    MachineConfigurationRegistry,
)
from loopx.capabilities.machine_configuration.store import (
    configure_machine_configuration,
    read_machine_configuration,
)
from loopx.chat_machine_configuration_api import (
    CHAT_MACHINE_CONFIGURATION_APPLY_PATH,
    CHAT_MACHINE_CONFIGURATION_PATH,
    CHAT_MACHINE_CONFIGURATION_PREVIEW_PATH,
    CHAT_MACHINE_CONFIGURATION_ROLLBACK_PATH,
    MachineConfigurationRequestMixin,
)


def _configuration(*, enabled: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "loopx_machine_configuration_v0",
        "namespaces": {
            "periodic_report": {
                "schema_version": "periodic_report_machine_defaults_v0",
                "enabled": enabled,
                "inheritance": "live_machine_default",
                "profile_preset": "weekly-progress",
                "route_ref": "loopx-manager",
                "timezone": "Asia/Shanghai",
            }
        },
    }


def _namespace(*, enabled: bool = True) -> dict[str, Any]:
    return _configuration(enabled=enabled)["namespaces"]["periodic_report"]


class _Handler(MachineConfigurationRequestMixin):
    def __init__(self, runtime_root: Path, body: dict[str, Any] | None = None) -> None:
        self.server = SimpleNamespace(runtime_root=runtime_root)
        self.body = body or {}
        self.responses: list[dict[str, Any]] = []

    def _read_json(self) -> dict[str, Any]:
        return self.body

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        self.responses.append({"status_code": status, **payload})

    def _send_error(
        self,
        message: str,
        *,
        status: int,
        error_code: str,
        **_kwargs: Any,
    ) -> None:
        self.responses.append(
            {
                "ok": False,
                "status_code": status,
                "error": message,
                "error_code": error_code,
            }
        )


class _MultiNamespaceHandler(_Handler):
    def _machine_configuration_registry(self) -> MachineConfigurationRegistry:
        registry = super()._machine_configuration_registry()
        return registry.register(
            MachineConfigurationNamespace(
                namespace="search_defaults",
                schema_versions=frozenset({"search_defaults_v0"}),
                normalize=lambda value: dict(value),
                project_public=lambda value: dict(value),
                apply_public_update=lambda _current, update: dict(update),
            )
        )


def _normalize_private_namespace(value: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(value) - {"schema_version", "enabled", "secret"})
    if unknown:
        raise ValueError("private namespace contains unsupported fields")
    if not isinstance(value.get("enabled"), bool):
        raise TypeError("private namespace enabled must be a boolean")
    return dict(value)


def _apply_private_namespace_public_update(
    current: Mapping[str, Any] | None,
    update: Mapping[str, Any],
) -> dict[str, Any]:
    unknown = sorted(set(update) - {"schema_version", "enabled"})
    if unknown:
        raise ValueError("private namespace public update contains unsupported fields")
    return {**dict(current or {}), **dict(update)}


class _PrivateNamespaceHandler(_Handler):
    def _machine_configuration_registry(self) -> MachineConfigurationRegistry:
        return MachineConfigurationRegistry().register(
            MachineConfigurationNamespace(
                namespace="private_defaults",
                schema_versions=frozenset({"private_defaults_v0"}),
                normalize=_normalize_private_namespace,
                project_public=lambda value: {
                    key: item for key, item in value.items() if key != "secret"
                },
                apply_public_update=_apply_private_namespace_public_update,
            )
        )


def test_machine_configuration_uses_generic_chat_routes() -> None:
    assert CHAT_MACHINE_CONFIGURATION_PATH == "/api/chat/machine-configuration"
    assert CHAT_MACHINE_CONFIGURATION_PREVIEW_PATH.endswith("/preview")
    assert CHAT_MACHINE_CONFIGURATION_APPLY_PATH.endswith("/apply")
    assert CHAT_MACHINE_CONFIGURATION_ROLLBACK_PATH.endswith("/rollback")


def test_real_chat_http_catalog_and_machine_write_boundary(tmp_path: Path) -> None:
    from loopx.chat_server import ChatHTTPServer, ChatRequestHandler

    server = ChatHTTPServer(("127.0.0.1", 0), ChatRequestHandler)
    server.runtime_root = tmp_path
    server.verbose = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request("GET", CHAT_MACHINE_CONFIGURATION_PATH)
        response = connection.getresponse()
        assert response.status == 200
        catalog = json.loads(response.read())["capability_catalog"]["capabilities"]
        assert {item["capability_id"] for item in catalog} >= {
            "periodic_report",
            "multi_subagent",
            "explore_graph",
        }
        connection.request(
            "POST",
            CHAT_MACHINE_CONFIGURATION_PREVIEW_PATH,
            body=json.dumps(
                {
                    "namespace": "multi_subagent",
                    "namespace_configuration": {"enabled": True},
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        rejected = connection.getresponse()
        assert rejected.status == 400
        assert json.loads(rejected.read())["ok"] is False
        connection.request(
            "POST",
            CHAT_MACHINE_CONFIGURATION_PREVIEW_PATH,
            body=json.dumps(
                {
                    "namespace": "periodic_report",
                    "namespace_configuration": _namespace(),
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        accepted = connection.getresponse()
        assert accepted.status == 201
        assert json.loads(accepted.read())["status"] == "preview"
    finally:
        connection.close()
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_inspection_lists_registered_namespaces_without_local_refs(
    tmp_path: Path,
) -> None:
    handler = _Handler(tmp_path)

    handler._machine_configuration_inspect()

    response = handler.responses[0]
    assert response["status"] == "absent"
    assert response["available_namespaces"] == [
        "change_quality_qualification",
        "periodic_report",
        "todo_replan_cadence",
    ]
    namespace_catalog = {
        item["namespace"]: item for item in response["namespace_catalog"]["namespaces"]
    }
    assert namespace_catalog["periodic_report"]["configuration_template"] == {
        "schema_version": "periodic_report_machine_defaults_v0",
        "enabled": False,
        "inheritance": "live_machine_default",
        "timezone": "UTC",
    }
    assert namespace_catalog["todo_replan_cadence"]["configuration_template"] == {
        "schema_version": "todo_replan_cadence_machine_defaults_v0",
        "completed_todos": 5,
    }
    assert namespace_catalog["change_quality_qualification"][
        "configuration_template"
    ] == {
        "schema_version": "change_quality_machine_defaults_v0",
        "enabled": False,
        "safe_fix": False,
        "strict_receipt": False,
    }
    capability_catalog = response["capability_catalog"]
    assert capability_catalog["schema_version"] == "capability_configuration_catalog_v0"
    capabilities = {
        item["capability_id"]: item for item in capability_catalog["capabilities"]
    }
    capability = capabilities["periodic_report"]
    assert capability["capability_id"] == "periodic_report"
    assert capability["available_scopes"] == ["machine", "goal"]
    assert capability["machine_namespace"] == "periodic_report"
    assert (
        capability["default"]
        == namespace_catalog["periodic_report"]["configuration_template"]
    )
    assert capability["configuration_editor"]["supported_scopes"] == [
        "machine",
        "goal",
    ]
    assert [field["key"] for field in capability["configuration_editor"]["fields"]] == [
        "enabled",
        "profile_preset",
        "route_ref",
        "timezone",
    ]
    effective = capability["effective_configuration"]
    assert effective["source"] == "capability_default"
    assert effective["configuration"] == capability["default"]
    assert effective["goal_override_present"] is False
    assert effective["machine_default_present"] is False
    assert str(effective["effective_revision"]).startswith("sha256:")
    assert response["machine_configuration"] is None
    encoded = json.dumps(response)
    assert str(tmp_path) not in encoded
    assert "defaults_ref" not in response


def test_machine_catalog_discovers_goal_features_without_granting_machine_writes(
    tmp_path: Path,
) -> None:
    from loopx.configuration_catalog import build_goal_configuration_catalog

    handler = _Handler(tmp_path)
    handler._machine_configuration_inspect()
    machine = {
        item["capability_id"]: item
        for item in handler.responses[0]["capability_catalog"]["capabilities"]
    }
    goal = build_goal_configuration_catalog(
        goal_id="sample",
        settings={},
        feature_summary={},
        default_multi_subagent_max_children=2,
        explore_harness_profiles=(),
    )
    assert set(machine) == {feature["feature_id"] for feature in goal["features"]}
    assert "multi_subagent" in machine
    for capability_id, item in machine.items():
        assert "current" not in item
        assert "commands" not in item
        if capability_id not in {
            "periodic_report",
            "todo_replan_cadence",
            "change_quality_qualification",
        }:
            assert item["available_scopes"] == ["goal"]
            assert "machine_namespace" not in item
            assert "machine" not in item["configuration_editor"]["writable_scopes"]
            assert item["effective_configuration"]["source"] == "not_configured"
        else:
            assert item["available_scopes"] == ["machine", "goal"]
            assert item["machine_namespace"] == capability_id
            assert "machine" in item["configuration_editor"]["writable_scopes"]

    rejected = _Handler(
        tmp_path,
        {"namespace": "multi_subagent", "namespace_configuration": {"enabled": True}},
    )
    rejected._machine_configuration_update(execute=False)
    assert rejected.responses[0]["ok"] is False
    assert rejected.responses[0]["status_code"] == 400


def test_preview_apply_inspect_and_rollback_are_revision_locked(tmp_path: Path) -> None:
    configuration = _configuration()
    preview_handler = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
        },
    )
    preview_handler._machine_configuration_update(execute=False)
    preview = preview_handler.responses[0]
    assert preview["status"] == "preview"
    assert preview["action"] == "create"
    assert preview["changed_namespaces"] == ["periodic_report"]

    apply_handler = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
            "expected_plan_revision": preview["plan_revision"],
        },
    )
    apply_handler._machine_configuration_update(execute=True)
    receipt = apply_handler.responses[0]
    assert receipt["status"] == "applied"
    assert receipt["readback_verified"] is True
    assert receipt["rollback_available"] is True
    assert "transaction_ref" not in receipt
    assert "backup_ref" not in receipt

    inspect_handler = _Handler(tmp_path)
    inspect_handler._machine_configuration_inspect()
    inspection = inspect_handler.responses[0]
    assert inspection["status"] == "configured"
    assert inspection["machine_configuration"] == configuration

    rollback_preview_handler = _Handler(
        tmp_path,
        {"transaction_id": receipt["transaction_id"], "execute": False},
    )
    rollback_preview_handler._machine_configuration_rollback()
    rollback_preview = rollback_preview_handler.responses[0]
    assert rollback_preview["rollback_allowed"] is True
    assert rollback_preview["action"] == "delete"

    rollback_handler = _Handler(
        tmp_path,
        {
            "transaction_id": receipt["transaction_id"],
            "execute": True,
            "expected_plan_revision": rollback_preview["plan_revision"],
        },
    )
    rollback_handler._machine_configuration_rollback()
    rollback = rollback_handler.responses[0]
    assert rollback["status"] == "rolled_back"
    assert rollback["readback_verified"] is True
    assert "rollback_ref" not in rollback

    final_handler = _Handler(tmp_path)
    final_handler._machine_configuration_inspect()
    assert final_handler.responses[0]["status"] == "absent"


def test_apply_rejects_a_stale_preview_without_writing(tmp_path: Path) -> None:
    first = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
        },
    )
    first._machine_configuration_update(execute=False)

    stale = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(enabled=False),
            "expected_plan_revision": first.responses[0]["plan_revision"],
        },
    )
    stale._machine_configuration_update(execute=True)

    assert stale.responses[0]["status_code"] == 409
    assert stale.responses[0]["error_code"] == "machine_configuration_preview_stale"


def test_namespace_removal_uses_the_same_preview_and_revision_fence(
    tmp_path: Path,
) -> None:
    create_preview = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
        },
    )
    create_preview._machine_configuration_update(execute=False)
    create = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
            "expected_plan_revision": create_preview.responses[0]["plan_revision"],
        },
    )
    create._machine_configuration_update(execute=True)

    remove_preview = _Handler(
        tmp_path,
        {"namespace": "periodic_report", "operation": "remove"},
    )
    remove_preview._machine_configuration_update(execute=False)
    preview = remove_preview.responses[0]
    assert preview["action"] == "delete"
    assert preview["machine_configuration"] is None

    remove = _Handler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "operation": "remove",
            "expected_plan_revision": preview["plan_revision"],
        },
    )
    remove._machine_configuration_update(execute=True)
    assert remove.responses[0]["status"] == "applied"
    assert remove.responses[0]["machine_configuration"] is None

    inspection = _Handler(tmp_path)
    inspection._machine_configuration_inspect()
    assert inspection.responses[0]["status"] == "absent"


def test_namespace_patch_preserves_other_capability_namespaces(tmp_path: Path) -> None:
    first_preview_handler = _MultiNamespaceHandler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
        },
    )
    first_preview_handler._machine_configuration_update(execute=False)
    first_apply_handler = _MultiNamespaceHandler(
        tmp_path,
        {
            "namespace": "periodic_report",
            "namespace_configuration": _namespace(),
            "expected_plan_revision": first_preview_handler.responses[0][
                "plan_revision"
            ],
        },
    )
    first_apply_handler._machine_configuration_update(execute=True)

    second_preview_handler = _MultiNamespaceHandler(
        tmp_path,
        {
            "namespace": "search_defaults",
            "namespace_configuration": {
                "schema_version": "search_defaults_v0",
                "index": "public",
            },
        },
    )
    second_preview_handler._machine_configuration_update(execute=False)

    namespaces = second_preview_handler.responses[0]["machine_configuration"][
        "namespaces"
    ]
    assert namespaces["periodic_report"] == _namespace()
    assert namespaces["search_defaults"] == {
        "schema_version": "search_defaults_v0",
        "index": "public",
    }


def test_public_api_update_preserves_provider_private_namespace_state(
    tmp_path: Path,
) -> None:
    registry = _PrivateNamespaceHandler(tmp_path)._machine_configuration_registry()
    initial = {
        "schema_version": "loopx_machine_configuration_v0",
        "namespaces": {
            "private_defaults": {
                "schema_version": "private_defaults_v0",
                "enabled": False,
                "secret": "keep-me",
            }
        },
    }
    seed_plan = configure_machine_configuration(
        runtime_root=tmp_path,
        configuration=initial,
        registry=registry,
    )
    configure_machine_configuration(
        runtime_root=tmp_path,
        configuration=initial,
        registry=registry,
        execute=True,
        expected_plan_revision=seed_plan["plan_revision"],
    )

    preview_handler = _PrivateNamespaceHandler(
        tmp_path,
        {
            "namespace": "private_defaults",
            "namespace_configuration": {
                "schema_version": "private_defaults_v0",
                "enabled": True,
            },
        },
    )
    preview_handler._machine_configuration_update(execute=False)
    preview = preview_handler.responses[0]
    assert preview["machine_configuration"]["namespaces"]["private_defaults"] == {
        "schema_version": "private_defaults_v0",
        "enabled": True,
    }

    apply_handler = _PrivateNamespaceHandler(
        tmp_path,
        {
            "namespace": "private_defaults",
            "namespace_configuration": {
                "schema_version": "private_defaults_v0",
                "enabled": True,
            },
            "expected_plan_revision": preview["plan_revision"],
        },
    )
    apply_handler._machine_configuration_update(execute=True)

    persisted = read_machine_configuration(tmp_path, registry=registry)
    assert persisted is not None
    assert persisted["namespaces"]["private_defaults"] == {
        "schema_version": "private_defaults_v0",
        "enabled": True,
        "secret": "keep-me",
    }
