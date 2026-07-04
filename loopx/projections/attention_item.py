"""Compatibility shim for loopx.control_plane.work_items.attention_item."""

from loopx.control_plane.work_items import attention_item as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
