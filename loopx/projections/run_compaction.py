"""Compatibility shim for loopx.control_plane.runtime.run_compaction."""

from loopx.control_plane.runtime import run_compaction as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
