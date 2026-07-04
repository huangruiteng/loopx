"""Compatibility shim for loopx.control_plane.runtime.session_runtime."""

from loopx.control_plane.runtime import session_runtime as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
