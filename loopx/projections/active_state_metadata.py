"""Compatibility shim for loopx.control_plane.goals.active_state_metadata."""

from loopx.control_plane.goals import active_state_metadata as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
