"""Compatibility shim for loopx.control_plane.todos.todo_summary."""

from loopx.control_plane.todos import todo_summary as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})
