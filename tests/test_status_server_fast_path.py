from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from threading import Thread
from typing import Iterator
import urllib.request
import urllib.error

import pytest

from loopx.status_server import (
    DEFAULT_CONFIGURE_GOAL_APPLY_PATH,
    DEFAULT_CONFIGURE_GOAL_DRY_RUN_PATH,
    DEFAULT_REWARD_APPEND_PATH,
    DEFAULT_REWARD_DRY_RUN_PATH,
    DEFAULT_STATUS_PATH,
    StatusHTTPServer,
    StatusRequestHandler,
)


@contextmanager
def _status_server(tmp_path: Path, *, reward_write_enabled: bool = False) -> Iterator[str]:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"goals": []}) + "\n", encoding="utf-8")
    server = StatusHTTPServer(("127.0.0.1", 0), StatusRequestHandler)
    server.registry_path = registry
    server.runtime_root_override = None
    server.scan_roots = [tmp_path]
    server.limit = 80
    server.status_path = DEFAULT_STATUS_PATH
    server.reward_dry_run_path = DEFAULT_REWARD_DRY_RUN_PATH
    server.reward_append_path = DEFAULT_REWARD_APPEND_PATH
    server.reward_write_enabled = reward_write_enabled
    server.configure_goal_dry_run_path = DEFAULT_CONFIGURE_GOAL_DRY_RUN_PATH
    server.configure_goal_apply_path = DEFAULT_CONFIGURE_GOAL_APPLY_PATH
    server.control_plane_write_enabled = False
    server.goal_subagent_configuration_enabled = False
    server.verbose = False
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_status_endpoint_defers_repository_boundary_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_collect_status(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"ok": True, "contract": {"ok": True}}

    monkeypatch.setattr("loopx.status_server.collect_status", fake_collect_status)

    with _status_server(tmp_path) as base_url:
        with urllib.request.urlopen(f"{base_url}{DEFAULT_STATUS_PATH}", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert payload["ok"] is True
    assert len(calls) == 1
    assert calls[0]["include_public_boundary_scan"] is False
    assert calls[0]["include_goal_subagent_configuration"] is False


def test_status_endpoint_forwards_goal_activation_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_collect_status(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"ok": True, "contract": {"ok": True}}

    monkeypatch.setattr("loopx.status_server.collect_status", fake_collect_status)

    with _status_server(tmp_path) as base_url:
        with urllib.request.urlopen(
            f"{base_url}{DEFAULT_STATUS_PATH}?goal_activation=active",
            timeout=5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert payload["ok"] is True
    assert calls[0]["activation_state_filter"] == "active"


def test_status_endpoint_rejects_unknown_goal_activation_scope(tmp_path: Path) -> None:
    with _status_server(tmp_path) as base_url:
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(
                f"{base_url}{DEFAULT_STATUS_PATH}?goal_activation=archived",
                timeout=5,
            )

    assert raised.value.code == 400
    payload = json.loads(raised.value.read().decode("utf-8"))
    assert payload["error"] == "goal_activation must be active or stopped"


def test_status_service_identity_is_public_and_versioned(tmp_path: Path) -> None:
    with _status_server(tmp_path) as base_url:
        with urllib.request.urlopen(base_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert payload["source"] == "serve-status"
    assert payload["runtime_identity"]["schema_version"] == (
        "loopx_runtime_identity_v1"
    )
    assert set(payload["runtime_identity"]) == {
        "schema_version",
        "package_version",
        "release_id",
        "source_revision",
    }


def test_status_endpoint_rejects_blank_goal_activation_scope(tmp_path: Path) -> None:
    """A blank `?goal_activation=` value must fail closed with HTTP 400."""
    with _status_server(tmp_path) as base_url:
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(
                f"{base_url}{DEFAULT_STATUS_PATH}?goal_activation=",
                timeout=5,
            )

    assert raised.value.code == 400
    payload = json.loads(raised.value.read().decode("utf-8"))
    assert payload["error"] == "goal_activation must be active or stopped"


def test_status_endpoint_rejects_mixed_blank_goal_activation_scope(
    tmp_path: Path,
) -> None:
    """`?goal_activation=active&goal_activation=` must not collapse to one value."""
    with _status_server(tmp_path) as base_url:
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(
                f"{base_url}{DEFAULT_STATUS_PATH}?goal_activation=active&goal_activation=",
                timeout=5,
            )

    assert raised.value.code == 400
    payload = json.loads(raised.value.read().decode("utf-8"))
    assert payload["error"] == "goal_activation must be active or stopped"


@pytest.mark.parametrize(
    "field",
    [
        "clear_allowed_domains",
        "clear_registered_agents",
        "clear_peer_task_coordinator",
        "self_repair_enabled",
        "self_repair_health",
        "self_repair_waiting_projection",
        "spawn_allowed",
        "clear_supervisor",
        "replace_write_scope",
        "clear_write_scope",
        "clear_boundary_authority",
    ],
)
def test_configure_goal_rejects_string_boolean_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_configure_goal(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "dry_run": True,
            "execute": False,
            "written": False,
            "changed": False,
            "goal_id": "goal-a",
            "changed_fields": [],
            "before": {},
            "after": {},
        }

    monkeypatch.setattr(
        "loopx.status_server.configure_goal_with_global_sync",
        fake_configure_goal,
    )
    with _status_server(tmp_path) as base_url:
        request = urllib.request.Request(
            f"{base_url}{DEFAULT_CONFIGURE_GOAL_DRY_RUN_PATH}",
            data=json.dumps({"goal_id": "goal-a", field: "false"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=5)

    assert raised.value.code == 400
    payload = json.loads(raised.value.read().decode("utf-8"))
    assert payload["error"] == f"{field} must be a JSON boolean"
    assert calls == []


def test_reward_append_rejects_string_boolean_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "loopx.status_server.append_human_reward",
        lambda **kwargs: calls.append(kwargs) or {"goal_id": "goal-a"},
    )

    with _status_server(tmp_path, reward_write_enabled=True) as base_url:
        request = urllib.request.Request(
            f"{base_url}{DEFAULT_REWARD_APPEND_PATH}",
            data=json.dumps(
                {
                    "goal_id": "goal-a",
                    "run_generated_at": "2026-09-07T00:00:00Z",
                    "decision": "ship",
                    "reward": "positive",
                    "reason_summary": "verified",
                    "preview_id": "preview",
                    "write_active_state_summary": "false",
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Origin": "http://127.0.0.1",
            },
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=5)

    assert raised.value.code == 400
    payload = json.loads(raised.value.read().decode("utf-8"))
    assert payload["error"] == "write_active_state_summary must be a JSON boolean"
    assert calls == []
