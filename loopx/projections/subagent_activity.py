"""Compatibility shim for loopx.control_plane.agents.subagent_activity."""

from loopx.control_plane.agents import subagent_activity as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
