from __future__ import annotations

import base64
import io
import json
import sys
import types
from typing import Any

import pytest

from loopx.control_plane.coordination.nokv_jsonl_helper import (
    ClientAdmissionUnavailable,
    RequestError,
    SdkCapabilityMismatch,
    build_client,
    handle_request,
    main,
    serve,
)


class FakeClient:
    def __init__(self) -> None:
        self.find_pages: list[dict[str, Any]] = []
        self.read_result: dict[str, Any] | BaseException = FileNotFoundError("missing")
        self.publish_result: dict[str, Any] | BaseException = publish_result()
        self.publish_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def find_workspaces(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["limit"] == 100
        return self.find_pages.pop(0)

    def read(self, *args: Any) -> dict[str, Any]:
        if isinstance(self.read_result, BaseException):
            raise self.read_result
        return self.read_result

    def publish_bytes(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.publish_calls.append((args, kwargs))
        if isinstance(self.publish_result, BaseException):
            raise self.publish_result
        return self.publish_result


def request(operation: str, **values: Any) -> dict[str, Any]:
    return {"request_id": "request-a", "operation": operation, **values}


def identity_page() -> dict[str, Any]:
    return {
        "workspaces": [
            {
                "workspace": {
                    "workbench": "authority-workbench",
                    "workspace_incarnation_id": "c" * 32,
                }
            }
        ],
        "next_cursor": None,
    }


def read_result() -> dict[str, Any]:
    return {
        "bytes": b"canonical bytes",
        "metadata": {
            "workbench": "authority-workbench",
            "path": "metadata/head.json",
            "workspace_incarnation_id": "c" * 32,
            "generation": 7,
        },
    }


def publish_result(*, generation: int = 1) -> dict[str, Any]:
    return {
        "operation_id": "a" * 32,
        "artifact_revision_id": "b" * 32,
        "workbench": "authority-workbench",
        "path": "metadata/head.json",
        "generation": generation,
    }


def test_store_identity_follows_all_pages_and_binds_the_workspace_incarnation() -> None:
    client = FakeClient()
    client.find_pages = [
        {
            "workspaces": [{"workspace": {"workbench": "other"}}],
            "next_cursor": b"page-two",
        },
        {
            "workspaces": [
                {
                    "workspace": {
                        "workbench": "authority-workbench",
                        "workspace_incarnation_id": "a" * 32,
                    }
                }
            ],
            "next_cursor": None,
        },
    ]

    result = handle_request(
        client,
        request("store_identity", workbench="authority-workbench"),
    )
    assert result == {
        "request_id": "request-a",
        "status": "available",
        "store_identity": f"nokv:authority-workbench:{'a' * 32}",
    }


def test_store_identity_never_turns_an_outage_or_missing_workspace_into_identity() -> (
    None
):
    unavailable = FakeClient()
    unavailable.find_pages = []

    def fail(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("route unavailable")

    unavailable.find_workspaces = fail  # type: ignore[method-assign]
    result = handle_request(
        unavailable,
        request("store_identity", workbench="authority-workbench"),
    )
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "nokv_identity_unavailable"
    assert result["reason"] == "NoKV identity lookup is unavailable"
    assert "route unavailable" not in result["reason"]

    absent = FakeClient()
    absent.find_pages = [{"workspaces": [], "next_cursor": None}]
    result = handle_request(
        absent,
        request("store_identity", workbench="authority-workbench"),
    )
    assert result["status"] == "failed"
    assert result["reason_code"] == "provider_protocol_violation"


def test_read_blob_preserves_missing_unavailable_and_generation() -> None:
    client = FakeClient()
    assert handle_request(
        client,
        request(
            "read_blob", workbench="authority-workbench", path="metadata/head.json"
        ),
    ) == {"request_id": "request-a", "status": "missing"}

    client.read_result = RuntimeError("server unavailable")
    unavailable = handle_request(
        client,
        request(
            "read_blob", workbench="authority-workbench", path="metadata/head.json"
        ),
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["reason_code"] == "nokv_read_unavailable"
    assert unavailable["reason"] == "NoKV blob read is unavailable"
    assert "server unavailable" not in unavailable["reason"]

    client.find_pages = [identity_page()]
    client.read_result = read_result()
    loaded = handle_request(
        client,
        request(
            "read_blob", workbench="authority-workbench", path="metadata/head.json"
        ),
    )
    assert loaded == {
        "request_id": "request-a",
        "status": "loaded",
        "bytes_base64": base64.b64encode(b"canonical bytes").decode("ascii"),
        "generation": 7,
    }


def test_cas_publish_blob_forwards_exact_generation_bytes_and_identities() -> None:
    client = FakeClient()
    client.publish_result = publish_result(generation=5)
    payload = b'{"head":true}'
    result = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=4,
            bytes_base64=base64.b64encode(payload).decode("ascii"),
            operation_id="a" * 32,
            artifact_revision_id="b" * 32,
        ),
    )

    assert result == {
        "request_id": "request-a",
        "status": "applied",
        "generation": 5,
    }
    args, kwargs = client.publish_calls[0]
    assert args == ("authority-workbench", "metadata/head.json", payload)
    assert kwargs == {
        "content_type": "application/json",
        "expected_generation": 4,
        "operation_id": "a" * 32,
        "artifact_revision_id": "b" * 32,
    }


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("workbench", "other-workbench"),
        ("path", "metadata/other.json"),
        ("workspace_incarnation_id", "d" * 32),
    ],
)
def test_read_blob_rejects_sdk_metadata_bound_to_another_object_or_incarnation(
    field: str,
    wrong_value: object,
) -> None:
    client = FakeClient()
    client.find_pages = [identity_page()]
    client.read_result = read_result()
    client.read_result["metadata"][field] = wrong_value

    result = handle_request(
        client,
        request(
            "read_blob", workbench="authority-workbench", path="metadata/head.json"
        ),
    )

    assert result["status"] == "failed"
    assert result["reason_code"] == "provider_protocol_violation"


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("workbench", "other-workbench"),
        ("path", "metadata/other.json"),
        ("operation_id", "d" * 32),
        ("artifact_revision_id", "e" * 32),
        ("generation", 6),
    ],
)
def test_publish_never_reports_applied_for_an_sdk_result_bound_to_another_write(
    field: str,
    wrong_value: object,
) -> None:
    client = FakeClient()
    client.publish_result = publish_result(generation=5)
    client.publish_result[field] = wrong_value

    result = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=4,
            bytes_base64=base64.b64encode(b"{}").decode("ascii"),
            operation_id="a" * 32,
            artifact_revision_id="b" * 32,
        ),
    )

    assert result["status"] == "ambiguous"
    assert result["reason_code"] == "provider_protocol_violation"


def test_cas_publish_blob_maps_only_proven_collision_to_conflict() -> None:
    client = FakeClient()
    client.publish_result = FileExistsError("already exists")
    conflict = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=None,
            bytes_base64=base64.b64encode(b"{}").decode("ascii"),
            operation_id="a" * 32,
            artifact_revision_id="b" * 32,
        ),
    )
    assert conflict["status"] == "conflict"
    assert conflict["current_generation"] is None

    client.publish_result = RuntimeError("generation conflict or lost response")
    ambiguous = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=1,
            bytes_base64=base64.b64encode(b"{}").decode("ascii"),
            operation_id="a" * 32,
            artifact_revision_id="b" * 32,
        ),
    )
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["reason_code"] == "nokv_publish_outcome_unknown"
    assert ambiguous["reason"] == "NoKV publish outcome is unknown"
    assert "lost response" not in ambiguous["reason"]

    client.publish_result = ValueError("post-call conversion exposed an endpoint")
    malformed = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=1,
            bytes_base64=base64.b64encode(b"{}").decode("ascii"),
            operation_id="a" * 32,
            artifact_revision_id="b" * 32,
        ),
    )
    assert malformed["status"] == "ambiguous"
    assert "endpoint" not in malformed["reason"]


def test_invalid_publish_request_fails_before_calling_the_sdk() -> None:
    client = FakeClient()
    invalid = handle_request(
        client,
        request(
            "cas_publish_blob",
            workbench="authority-workbench",
            path="metadata/head.json",
            expected_generation=True,
            bytes_base64="not base64",
            operation_id="short",
            artifact_revision_id="b" * 32,
        ),
    )
    assert invalid["status"] == "failed"
    assert invalid["reason_code"] == "invalid_request"
    assert client.publish_calls == []


def test_json_lines_server_emits_one_typed_response_per_request() -> None:
    client = FakeClient()
    incoming = io.StringIO(
        json.dumps(
            request(
                "read_blob",
                workbench="authority-workbench",
                path="metadata/head.json",
            )
        )
        + "\n"
        + "not-json\n"
    )
    outgoing = io.StringIO()

    serve(client, incoming, outgoing)

    rows = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert rows[0] == {"request_id": "request-a", "status": "missing"}
    assert rows[1]["request_id"] is None
    assert rows[1]["status"] == "failed"
    assert rows[1]["reason_code"] == "invalid_json"


def test_static_route_requires_positive_generation_and_epoch_before_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    static_calls: list[tuple[Any, ...]] = []

    class RoutingConfig:
        @staticmethod
        def static(*args: Any) -> object:
            static_calls.append(args)
            return object()

    module = types.SimpleNamespace(
        __version__="0.11.0",
        API_VERSION=1,
        Client=lambda **_kwargs: object(),
        ObjectStoreConfig=types.SimpleNamespace(memory=lambda: object()),
        RoutingConfig=RoutingConfig,
    )
    monkeypatch.setitem(sys.modules, "nokv", module)
    base = {
        "root_id": "a" * 32,
        "routing": {
            "kind": "static",
            "endpoint": "127.0.0.1:7000",
            "logical_shard_id": "b" * 32,
            "object_namespace_id": "c" * 32,
            "placement_generation": 1,
            "owner_epoch": 1,
        },
        "object_store": {"kind": "memory"},
    }
    for field, value in [
        ("placement_generation", None),
        ("placement_generation", True),
        ("owner_epoch", 0),
    ]:
        invalid = json.loads(json.dumps(base))
        invalid["routing"][field] = value
        with pytest.raises(RequestError):
            build_client(invalid)
    assert static_calls == []


def test_client_constructor_value_error_is_typed_as_admission_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RoutingConfig:
        @staticmethod
        def etcd(*_args: Any) -> object:
            return object()

    def unavailable_client(**_kwargs: Any) -> object:
        raise ValueError("provider endpoint and credential detail")

    module = types.SimpleNamespace(
        __version__="0.11.0",
        API_VERSION=1,
        Client=unavailable_client,
        ObjectStoreConfig=types.SimpleNamespace(memory=lambda: object()),
        RoutingConfig=RoutingConfig,
    )
    monkeypatch.setitem(sys.modules, "nokv", module)

    with pytest.raises(ClientAdmissionUnavailable) as raised:
        build_client(
            {
                "root_id": "a" * 32,
                "routing": {
                    "kind": "etcd",
                    "endpoints": ["http://unused.invalid"],
                    "key_prefix": "/nokv/control",
                    "lease_ttl_seconds": 10,
                },
                "object_store": {"kind": "memory"},
            }
        )
    assert "endpoint" not in str(raised.value)


@pytest.mark.parametrize("unknown_location", ["top", "routing", "object_store"])
def test_unknown_config_keys_fail_before_any_sdk_object_is_constructed(
    monkeypatch: pytest.MonkeyPatch,
    unknown_location: str,
) -> None:
    construction_calls: list[str] = []

    class RoutingConfig:
        @staticmethod
        def etcd(*_args: Any) -> object:
            construction_calls.append("routing")
            return object()

    class ObjectStoreConfig:
        @staticmethod
        def memory() -> object:
            construction_calls.append("object_store")
            return object()

    def client(**_kwargs: Any) -> object:
        construction_calls.append("client")
        return object()

    module = types.SimpleNamespace(
        __version__="0.11.0",
        API_VERSION=1,
        Client=client,
        ObjectStoreConfig=ObjectStoreConfig,
        RoutingConfig=RoutingConfig,
    )
    monkeypatch.setitem(sys.modules, "nokv", module)
    config = {
        "root_id": "a" * 32,
        "routing": {
            "kind": "etcd",
            "endpoints": ["http://unused.invalid"],
            "key_prefix": "/nokv/control",
            "lease_ttl_seconds": 10,
        },
        "object_store": {"kind": "memory"},
    }
    secret_marker = "must-not-appear"
    if unknown_location == "top":
        config["routing_typo"] = secret_marker
    elif unknown_location == "routing":
        config["routing"]["endpoints_typo"] = secret_marker
    else:
        config["object_store"]["secret_access_key_typo"] = secret_marker

    with pytest.raises(RequestError) as raised:
        build_client(config)

    assert construction_calls == []
    assert secret_marker not in str(raised.value)


@pytest.mark.parametrize(
    ("sdk_version", "api_version"),
    [("incompatible-version", 1), ("0.11.0", 999)],
)
def test_sdk_version_or_api_mismatch_fails_before_provider_construction(
    monkeypatch: pytest.MonkeyPatch,
    sdk_version: str,
    api_version: int,
) -> None:
    construction_calls: list[str] = []
    module = types.SimpleNamespace(
        __version__=sdk_version,
        API_VERSION=api_version,
        Client=lambda **_kwargs: construction_calls.append("client"),
        ObjectStoreConfig=types.SimpleNamespace(
            memory=lambda: construction_calls.append("object_store")
        ),
        RoutingConfig=types.SimpleNamespace(
            etcd=lambda *_args: construction_calls.append("routing")
        ),
    )
    monkeypatch.setitem(sys.modules, "nokv", module)

    with pytest.raises(RequestError) as raised:
        build_client(
            {
                "root_id": "a" * 32,
                "routing": {
                    "kind": "etcd",
                    "endpoints": ["http://unused.invalid"],
                    "key_prefix": "/nokv/control",
                    "lease_ttl_seconds": 10,
                },
                "object_store": {"kind": "memory"},
            }
        )

    assert construction_calls == []
    assert "incompatible-version" not in str(raised.value)
    assert "999" not in str(raised.value)


def test_open_handshake_reports_the_qualified_sdk_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.SimpleNamespace(
        __version__="0.11.0",
        API_VERSION=1,
        Client=lambda **_kwargs: object(),
        ObjectStoreConfig=types.SimpleNamespace(memory=lambda: object()),
        RoutingConfig=types.SimpleNamespace(etcd=lambda *_args: object()),
    )
    monkeypatch.setitem(sys.modules, "nokv", module)
    incoming = io.StringIO(
        json.dumps(
            {
                "request_id": "open-a",
                "operation": "open",
                "config": {
                    "root_id": "a" * 32,
                    "routing": {
                        "kind": "etcd",
                        "endpoints": ["http://unused.invalid"],
                        "key_prefix": "/nokv/control",
                        "lease_ttl_seconds": 10,
                    },
                    "object_store": {"kind": "memory"},
                },
            }
        )
        + "\n"
    )
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdin", incoming)
    monkeypatch.setattr(sys, "stdout", outgoing)

    assert main() == 0
    assert json.loads(outgoing.getvalue().splitlines()[0]) == {
        "request_id": "open-a",
        "status": "ready",
        "nokv_api_version": 1,
        "nokv_protocol_schema": None,
        "nokv_sdk_version": "0.11.0",
    }


def _sdk_module(routing: object, **overrides: Any) -> types.SimpleNamespace:
    module = types.SimpleNamespace(
        __version__="0.11.0",
        API_VERSION=1,
        Client=lambda **_kwargs: object(),
        ObjectStoreConfig=types.SimpleNamespace(memory=lambda: object()),
        RoutingConfig=routing,
    )
    for name, value in overrides.items():
        setattr(module, name, value)
    return module


def _seeds_config(**routing_extra: Any) -> dict[str, Any]:
    return {
        "root_id": "a" * 32,
        "routing": {"kind": "seeds", "endpoints": ["127.0.0.1:7750"], **routing_extra},
        "object_store": {"kind": "memory"},
    }


def test_seeds_route_uses_the_sdk_seeds_constructor_with_exact_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeds_calls: list[tuple[Any, ...]] = []

    class RoutingConfig:
        @staticmethod
        def seeds(*args: Any) -> object:
            seeds_calls.append(args)
            return object()

    monkeypatch.setitem(sys.modules, "nokv", _sdk_module(RoutingConfig))

    build_client(_seeds_config())
    assert seeds_calls == [(["127.0.0.1:7750"],)]

    for invalid in (
        _seeds_config(key_prefix="/nokv/control"),
        {**_seeds_config(), "routing": {"kind": "seeds"}},
        {**_seeds_config(), "routing": {"kind": "seeds", "endpoints": []}},
    ):
        with pytest.raises(RequestError):
            build_client(invalid)
    assert len(seeds_calls) == 1


@pytest.mark.parametrize(
    ("routing_config", "sdk_routing"),
    [
        (
            {"kind": "seeds", "endpoints": ["127.0.0.1:7750"]},
            types.SimpleNamespace(
                etcd=lambda *_args: object(), static=lambda *_args: object()
            ),
        ),
        (
            {
                "kind": "etcd",
                "endpoints": ["http://unused.invalid"],
                "key_prefix": "/nokv/control",
                "lease_ttl_seconds": 10,
            },
            types.SimpleNamespace(seeds=lambda *_args: object()),
        ),
    ],
)
def test_routing_kind_the_sdk_cannot_build_is_a_typed_capability_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    routing_config: dict[str, Any],
    sdk_routing: types.SimpleNamespace,
) -> None:
    constructed: list[str] = []
    module = _sdk_module(
        sdk_routing,
        Client=lambda **_kwargs: constructed.append("client"),
    )
    module.ObjectStoreConfig = types.SimpleNamespace(
        memory=lambda: constructed.append("object_store")
    )
    monkeypatch.setitem(sys.modules, "nokv", module)

    with pytest.raises(SdkCapabilityMismatch) as raised:
        build_client(
            {
                "root_id": "a" * 32,
                "routing": routing_config,
                "object_store": {"kind": "memory"},
            }
        )

    assert isinstance(raised.value, RequestError)
    assert f"RoutingConfig.{routing_config['kind']}" in str(raised.value)
    assert "127.0.0.1" not in str(raised.value)
    assert "unused.invalid" not in str(raised.value)
    assert constructed == []


def test_unknown_routing_kind_is_invalid_config_not_a_capability_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _sdk_module(types.SimpleNamespace(seeds=lambda *_args: object()))
    monkeypatch.setitem(sys.modules, "nokv", module)

    with pytest.raises(RequestError) as raised:
        build_client(
            {**_seeds_config(), "routing": {"kind": "gossip", "endpoints": ["x"]}}
        )
    assert not isinstance(raised.value, SdkCapabilityMismatch)


def test_open_handshake_reports_capability_mismatch_as_a_typed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _sdk_module(types.SimpleNamespace(etcd=lambda *_args: object()))
    monkeypatch.setitem(sys.modules, "nokv", module)
    incoming = io.StringIO(
        json.dumps(
            {"request_id": "open-b", "operation": "open", "config": _seeds_config()}
        )
        + "\n"
    )
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdin", incoming)
    monkeypatch.setattr(sys, "stdout", outgoing)

    assert main() == 2
    response = json.loads(outgoing.getvalue().splitlines()[0])
    assert response["request_id"] == "open-b"
    assert response["status"] == "failed"
    assert response["reason_code"] == "nokv_sdk_capability_mismatch"
    assert "RoutingConfig.seeds" in response["reason"]
    assert "127.0.0.1" not in response["reason"]


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        ("nokv.workspace.rpc.v10", "nokv.workspace.rpc.v10"),
        (None, None),
        (10, None),
        ("", None),
    ],
)
def test_open_handshake_echoes_only_a_well_formed_sdk_protocol_schema(
    monkeypatch: pytest.MonkeyPatch,
    declared: object,
    expected: str | None,
) -> None:
    extra: dict[str, Any] = {}
    if declared is not None:
        extra["WORKSPACE_PROTOCOL_SCHEMA"] = declared
    module = _sdk_module(types.SimpleNamespace(seeds=lambda *_args: object()), **extra)
    monkeypatch.setitem(sys.modules, "nokv", module)
    incoming = io.StringIO(
        json.dumps(
            {"request_id": "open-c", "operation": "open", "config": _seeds_config()}
        )
        + "\n"
    )
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdin", incoming)
    monkeypatch.setattr(sys, "stdout", outgoing)

    assert main() == 0
    assert json.loads(outgoing.getvalue().splitlines()[0]) == {
        "request_id": "open-c",
        "status": "ready",
        "nokv_api_version": 1,
        "nokv_protocol_schema": expected,
        "nokv_sdk_version": "0.11.0",
    }
