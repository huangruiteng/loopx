from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from ..control_plane.capability_hooks import (
    POST_WRITEBACK_HOOK_DISPATCH_SCHEMA_VERSION,
    PostWritebackHookRegistration,
    dispatch_post_writeback_hooks,
)
from ..history import load_registry
from ..paths import resolve_runtime_root


PostWritebackProjectionBuilder = Callable[..., Mapping[str, object]]


def dispatch_committed_cli_post_writeback_hooks(
    *,
    payload: Mapping[str, Any],
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
    event_kind: str,
    identity: Mapping[str, Any],
    state_version: str,
    committed_at: str,
    hooks: Sequence[PostWritebackHookRegistration],
    projection_builder: PostWritebackProjectionBuilder | None,
) -> dict[str, Any]:
    """Bridge one committed CLI mutation into the TS-owned hook lifecycle.

    Projection and provider failures are isolated from the primary mutation.
    The helper intentionally owns no capability policy and grants no effects.
    """

    try:
        runtime_root = resolve_runtime_root(
            load_registry(registry_path), runtime_root_arg
        )
        projection = (
            dict(
                projection_builder(
                    payload=payload,
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    goal_id=goal_id,
                    agent_id=str(identity.get("agent_id") or ""),
                )
            )
            if projection_builder is not None
            else {}
        )
        return dispatch_post_writeback_hooks(
            hooks,
            source={
                "schema_version": "loopx_post_writeback_hook_source_v0",
                "event_kind": event_kind,
                "status": "committed",
                "durable": True,
                "identity": {
                    "goal_id": goal_id,
                    "agent_id": str(identity.get("agent_id") or ""),
                    "todo_id": (
                        str(identity["todo_id"])
                        if identity.get("todo_id")
                        else None
                    ),
                    "turn_instance_id": str(
                        identity.get("turn_instance_id") or ""
                    ),
                    "effect_id": str(identity.get("effect_id") or ""),
                },
                "state_version": state_version,
                "committed_at": committed_at,
                "projection": projection,
            },
            runtime_root=runtime_root,
        )
    except Exception:  # Optional hooks never alter primary truth.
        return {
            "schema_version": POST_WRITEBACK_HOOK_DISPATCH_SCHEMA_VERSION,
            "phase": "post_writeback",
            "registered_count": len(hooks),
            "intent_count": 0,
            "failures": [
                {
                    "hook_id": "composition",
                    "capability_id": "unknown",
                    "error_code": "source_projection_failed",
                }
            ],
            "primary_writeback_preserved": True,
            "external_writes_performed": False,
        }


__all__ = [
    "PostWritebackProjectionBuilder",
    "dispatch_committed_cli_post_writeback_hooks",
]
