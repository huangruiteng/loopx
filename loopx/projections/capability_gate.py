"""Compatibility shim for loopx.control_plane.agents.capability_gate."""

from loopx.control_plane.agents import capability_gate as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
