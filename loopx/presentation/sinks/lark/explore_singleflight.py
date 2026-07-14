from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any

from ....file_lock import try_exclusive_file_lock


@contextmanager
def explore_feishu_sync_singleflight(
    *, config_path: Path, execute: bool
) -> Iterator[bool]:
    """Fail fast when another process is already delivering this board.

    Dry-runs never contend because they perform no remote or config writes.
    The lock target is local-private and only the acquired/busy state enters
    public packets.
    """

    if not execute:
        yield True
        return
    target = config_path.with_name(f"{config_path.name}.feishu-sync")
    with try_exclusive_file_lock(target) as lock_path:
        yield lock_path is not None


def explore_feishu_sync_busy_packet(
    *, schema_version: str = "loopx_lark_explore_sync_v0"
) -> dict[str, Any]:
    """Return the compact retryable contract for a rejected overlapping sync."""

    return {
        "ok": False,
        "schema_version": schema_version,
        "status": "sync_busy",
        "execute": True,
        "retryable": True,
        "reason_code": "explore_feishu_sync_in_progress",
        "external_write_performed": False,
        "row_readback_verified": False,
        "required_action": "retry after the active Explore Feishu sync exits",
        "error": "another Explore Feishu sync is already active for this config",
    }


def singleflight_issue_fix_material_sync(
    config_path_resolver: Callable[[Path | None], Path],
) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    """Serialize an issue-fix material sync across row, visual, and checkpoint writes."""

    def decorate(
        function: Callable[..., dict[str, Any]],
    ) -> Callable[..., dict[str, Any]]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
            registry_path = kwargs.get("registry_path")
            if registry_path is None and args:
                registry_path = args[0]
            resolved_registry = (
                Path(registry_path) if registry_path is not None else None
            )
            execute = bool(kwargs.get("execute", False))
            delivery_authorized = bool(
                kwargs.get("external_sink_delivery_authorized", True)
            )
            with explore_feishu_sync_singleflight(
                config_path=config_path_resolver(resolved_registry),
                execute=bool(execute and delivery_authorized),
            ) as acquired:
                if not acquired:
                    return explore_feishu_sync_busy_packet(
                        schema_version="issue_fix_explore_lark_material_sync_v0"
                    )
                return function(*args, **kwargs)

        return wrapped

    return decorate
