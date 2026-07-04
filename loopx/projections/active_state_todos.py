"""Compatibility shim for loopx.control_plane.todos.active_state_todos."""

from loopx.control_plane.todos import active_state_todos as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
