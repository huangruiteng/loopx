from __future__ import annotations

import loopx.global_gates as global_gates


def test_global_gates_projects_only_open_gate_view(monkeypatch, tmp_path) -> None:
    summary_payload = {
        "ok": True,
        "summary": {"quota_states": {"operator_gate": 1}},
        "gates": [
            {
                "goal_id": "blocked-goal",
                "owner": "user",
                "blocks": ["todo-1"],
                "question": "Approve this run?",
            }
        ],
        "lanes": [{"goal_id": "unrelated-goal"}],
        "todos": [{"todo_id": "todo-2"}],
        "risks": [{"kind": "status_warning"}],
    }
    monkeypatch.setattr(
        global_gates,
        "build_summary_all",
        lambda **_: summary_payload,
    )

    payload = global_gates.build_global_gates(
        registry_path=tmp_path / "registry.json",
        runtime_root_override=None,
        scan_roots=[],
        agent_id=None,
        limit=5,
    )

    assert payload["request"]["command"] == "/loopx-global-gates"
    assert payload["request"]["legacy_aliases"] == ["/loop-global-gates"]
    assert payload["summary"]["open_gate_count"] == 1
    assert payload["gates"] == summary_payload["gates"]
    assert payload["groups"] == {"user_gates": summary_payload["gates"]}
    assert "lanes" not in payload
    assert "todos" not in payload
    assert "risks" not in payload
