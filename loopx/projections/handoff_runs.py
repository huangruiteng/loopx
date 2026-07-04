"""Compatibility shim for loopx.control_plane.handoff.handoff_runs."""

from loopx.control_plane.handoff import handoff_runs as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
