"""Compatibility shim for loopx.control_plane.work_items.lifecycle."""

from loopx.control_plane.work_items import lifecycle as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
