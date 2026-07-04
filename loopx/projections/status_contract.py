"""Compatibility shim for loopx.control_plane.work_items.status_contract."""

from loopx.control_plane.work_items import status_contract as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
