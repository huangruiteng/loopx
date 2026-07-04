"""Compatibility shim for loopx.control_plane.goals.dreaming."""

from loopx.control_plane.goals import dreaming as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
