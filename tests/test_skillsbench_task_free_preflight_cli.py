from __future__ import annotations

import json

from scripts import skillsbench_automation_loop as automation_loop


def test_local_codex_participant_ping_bypasses_launch_route_guards(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        automation_loop.codex_runtime,
        "materialize_local_codex_participant",
        lambda **_kwargs: {
            "schema_version": "skillsbench_local_codex_participant_v0",
            "codex_cli_invoked": True,
            "ready": True,
        },
    )

    assert automation_loop.main(["--local-codex-participant-ping"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is True


def test_worker_handshake_preflight_bypasses_launch_route_guards(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        automation_loop,
        "ensure_skillsbench_dependency_python",
        lambda _args: None,
    )
    monkeypatch.setattr(
        automation_loop,
        "inspect_skillsbench_worker_handshake",
        lambda **_kwargs: {
            "schema_version": "skillsbench_worker_handshake_preflight_v0",
            "ready": True,
        },
    )

    assert (
        automation_loop.main(["--local-driver-worker-handshake-preflight"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is True
