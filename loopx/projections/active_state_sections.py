"""Compatibility shim for loopx.control_plane.goals.active_state_sections."""

from loopx.control_plane.goals import active_state_sections as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
