"""Compatibility shim for loopx.control_plane.goals.global_registry_health."""

from loopx.control_plane.goals import global_registry_health as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
