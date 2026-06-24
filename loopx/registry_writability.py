from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Any


WRITE_DENIED_ERRNOS = {errno.EACCES, errno.EPERM, errno.EROFS}


def is_write_denied_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    return isinstance(exc, OSError) and getattr(exc, "errno", None) in WRITE_DENIED_ERRNOS


def probe_registry_write_path(path: Path, *, create_parent: bool = True) -> dict[str, Any]:
    path = path.expanduser()
    parent = path.parent
    probe_target = path.with_name(f".{path.name}.{os.getpid()}.write-probe")
    probe_temp = path.with_name(f".{path.name}.{os.getpid()}.write-probe.tmp")
    cleanup_paths = (probe_temp, probe_target)
    try:
        if create_parent:
            parent.mkdir(parents=True, exist_ok=True)
        elif not parent.exists():
            raise FileNotFoundError(f"registry parent directory does not exist: {parent}")
        probe_temp.write_text("loopx registry write probe\n", encoding="utf-8")
        probe_temp.replace(probe_target)
        probe_target.unlink()
        return {
            "schema_version": "loopx_registry_writability_v0",
            "ok": True,
            "path": str(path),
            "parent": str(parent),
            "create_parent": create_parent,
            "probe": str(probe_target),
        }
    except OSError as exc:
        return {
            "schema_version": "loopx_registry_writability_v0",
            "ok": False,
            "path": str(path),
            "parent": str(parent),
            "create_parent": create_parent,
            "probe": str(probe_target),
            "error_kind": "registry_write_denied" if is_write_denied_error(exc) else "registry_write_probe_failed",
            "errno": getattr(exc, "errno", None),
            "error": str(exc),
            "requires_host_permission": is_write_denied_error(exc),
            "recommended_action": (
                f"Grant write access to `{path}` and `{parent}`, then rerun the LoopX command. "
                "If this is a sandboxed host, re-run from a thread or shell that can write the "
                "shared LoopX runtime root."
            ),
        }
    finally:
        for candidate in cleanup_paths:
            try:
                if candidate.exists():
                    candidate.unlink()
            except OSError:
                pass
