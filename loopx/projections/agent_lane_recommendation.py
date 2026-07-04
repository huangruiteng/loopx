"""Compatibility shim for loopx.control_plane.agents.agent_lane_recommendation."""

from loopx.control_plane.agents import agent_lane_recommendation as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
