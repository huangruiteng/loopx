"""Compatibility shim for loopx.control_plane.work_items.issue_meta_surface."""

from loopx.control_plane.work_items import issue_meta_surface as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
