"""Compatibility shim for loopx.control_plane.work_items.autonomous_replan_ack."""

from loopx.control_plane.work_items import autonomous_replan_ack as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
