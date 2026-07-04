"""Compatibility shim for loopx.control_plane.work_items.attention_fields."""

from loopx.control_plane.work_items import attention_fields as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
