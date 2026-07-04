"""Compatibility shim for loopx.control_plane.work_items.backlog_hygiene."""

from loopx.control_plane.work_items import backlog_hygiene as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
