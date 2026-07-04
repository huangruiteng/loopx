"""Compatibility shim for loopx.control_plane.work_items.delivery_signals."""

from loopx.control_plane.work_items import delivery_signals as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
