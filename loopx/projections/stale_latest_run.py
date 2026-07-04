"""Compatibility shim for loopx.control_plane.work_items.stale_latest_run."""

from loopx.control_plane.work_items import stale_latest_run as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
