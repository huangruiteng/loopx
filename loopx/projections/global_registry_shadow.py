"""Compatibility shim for loopx.control_plane.goals.global_registry_shadow."""

from loopx.control_plane.goals import global_registry_shadow as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
