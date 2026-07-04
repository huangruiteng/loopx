"""Compatibility shim for loopx.control_plane.work_items.project_asset."""

from loopx.control_plane.work_items import project_asset as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
