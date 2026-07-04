"""Compatibility shim for loopx.control_plane.handoff.project_handoff."""

from loopx.control_plane.handoff import project_handoff as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
