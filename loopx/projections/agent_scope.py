"""Compatibility shim for loopx.control_plane.agents.agent_scope."""

from loopx.control_plane.agents import agent_scope as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
