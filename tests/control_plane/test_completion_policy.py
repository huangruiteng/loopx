from __future__ import annotations

from dataclasses import fields

from loopx.control_plane.todos.completion_policy import CompletionPolicy


def test_completion_policy_does_not_duplicate_runtime_model_authority() -> None:
    assert "agent_model" not in {field.name for field in fields(CompletionPolicy)}
