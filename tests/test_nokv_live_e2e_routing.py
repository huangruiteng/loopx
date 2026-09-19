"""Routing selection of the live NoKV matrix script.

``examples/nokv-shadow-provider/live_e2e.py`` builds its SDK routing from
exactly one environment group. These tests load the script as a module and
exercise ``nokv_routing`` with stand-in SDK modules so the selection, the typed
unverified reasons and the endpoint-free SDK facts are pinned without a stack.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

LIVE_E2E = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "nokv-shadow-provider"
    / "live_e2e.py"
)


def _load_live_e2e() -> Any:
    spec = importlib.util.spec_from_file_location("nokv_live_e2e_under_test", LIVE_E2E)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sdk(routing: object, **extra: Any) -> types.SimpleNamespace:
    module = types.SimpleNamespace(
        __version__="0.11.0", API_VERSION=1, RoutingConfig=routing
    )
    for name, value in extra.items():
        setattr(module, name, value)
    return module


CORE = {"NOKV_ROOT_ID": "a" * 32}


def test_seed_routing_uses_the_seeds_constructor_and_reports_counts_only() -> None:
    live = _load_live_e2e()
    calls: list[tuple[Any, ...]] = []

    class RoutingConfig:
        @staticmethod
        def seeds(*args: Any) -> object:
            calls.append(args)
            return ("seeds", *args)

    sdk = _sdk(RoutingConfig, WORKSPACE_PROTOCOL_SCHEMA="nokv.workspace.rpc.v10")
    routing, facts, skip = live.nokv_routing(
        sdk, {**CORE, "NOKV_SEEDS": " 127.0.0.1:7750, 127.0.0.1:7751 "}
    )

    assert skip is None
    assert calls == [(["127.0.0.1:7750", "127.0.0.1:7751"],)]
    assert routing == ("seeds", ["127.0.0.1:7750", "127.0.0.1:7751"])
    assert facts == {
        "version": "0.11.0",
        "api_version": 1,
        "protocol_schema": "nokv.workspace.rpc.v10",
        "routing_kind": "seeds",
        "seed_count": 2,
    }
    assert "127.0.0.1" not in repr(facts)


def test_etcd_routing_keeps_the_release_shape_and_reports_no_schema() -> None:
    live = _load_live_e2e()
    calls: list[tuple[Any, ...]] = []

    class RoutingConfig:
        @staticmethod
        def etcd(*args: Any) -> object:
            calls.append(args)
            return ("etcd", *args)

    routing, facts, skip = live.nokv_routing(
        _sdk(RoutingConfig),
        {**CORE, "NOKV_ETCD": "http://127.0.0.1:2379", "NOKV_ETCD_PREFIX": "/nokv"},
    )

    assert skip is None
    assert calls == [(["http://127.0.0.1:2379"], "/nokv", 10)]
    assert routing is not None
    assert facts == {
        "version": "0.11.0",
        "api_version": 1,
        "protocol_schema": None,
        "routing_kind": "etcd",
        "seed_count": None,
    }


@pytest.mark.parametrize(
    ("env", "sdk_routing", "expected_code"),
    [
        (
            {
                "NOKV_SEEDS": "127.0.0.1:7750",
                "NOKV_ETCD": "http://x",
                "NOKV_ETCD_PREFIX": "/p",
            },
            types.SimpleNamespace(
                seeds=lambda *_a: object(), etcd=lambda *_a: object()
            ),
            "nokv_routing_env_ambiguous",
        ),
        (
            {},
            types.SimpleNamespace(seeds=lambda *_a: object()),
            "nokv_routing_env_missing",
        ),
        (
            {"NOKV_ETCD": "http://x"},
            types.SimpleNamespace(etcd=lambda *_a: object()),
            "nokv_routing_env_missing",
        ),
        (
            {"NOKV_SEEDS": "127.0.0.1:7750"},
            types.SimpleNamespace(
                etcd=lambda *_a: object(), static=lambda *_a: object()
            ),
            "nokv_sdk_capability_mismatch",
        ),
        (
            {"NOKV_ETCD": "http://x", "NOKV_ETCD_PREFIX": "/p"},
            types.SimpleNamespace(seeds=lambda *_a: object()),
            "nokv_sdk_capability_mismatch",
        ),
        (
            {"NOKV_SEEDS": "not-an-address"},
            types.SimpleNamespace(
                seeds=lambda *_a: (_ for _ in ()).throw(ValueError("bad"))
            ),
            "nokv_routing_invalid",
        ),
    ],
)
def test_routing_selection_failures_are_typed_and_never_construct_a_client(
    env: dict[str, str], sdk_routing: types.SimpleNamespace, expected_code: str
) -> None:
    live = _load_live_e2e()
    routing, facts, skip = live.nokv_routing(_sdk(sdk_routing), {**CORE, **env})

    assert routing is None and facts is None
    assert skip is not None
    reason, code = skip
    assert code == expected_code
    assert "127.0.0.1" not in reason and "http://x" not in reason


def test_matrix_reports_a_typed_unverified_reason_without_a_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = _load_live_e2e()
    monkeypatch.delenv("NOKV_COORDINATION_LIVE", raising=False)
    assert live.nokv_matrix() == (
        None,
        ("NOKV_COORDINATION_LIVE unset", "nokv_live_flag_unset"),
        None,
    )

    monkeypatch.setenv("NOKV_COORDINATION_LIVE", "1")
    monkeypatch.setitem(
        sys.modules, "nokv", _sdk(types.SimpleNamespace(etcd=lambda *_a: object()))
    )
    for name in ("NOKV_SEEDS", "NOKV_ETCD", "NOKV_ETCD_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    rows, skip, facts = live.nokv_matrix()
    assert rows is None and facts is None
    assert skip is not None and skip[1] == "nokv_routing_env_missing"
