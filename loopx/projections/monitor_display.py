"""Compatibility shim for loopx.control_plane.scheduler.monitor_display."""

from loopx.control_plane.scheduler import monitor_display as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
