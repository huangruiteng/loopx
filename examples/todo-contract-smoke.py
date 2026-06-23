#!/usr/bin/env python3
"""Smoke-test public todo status contract helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loopx.todo_contract import (
    normalize_todo_status,
    todo_done_for_status,
    todo_terminal_for_status,
)


def main() -> None:
    assert normalize_todo_status("done") == "done"
    assert normalize_todo_status("completed") is None
    assert todo_done_for_status("done")
    assert not todo_done_for_status("completed")
    for value in ("done", "deferred", "completed", "closed", "archived"):
        assert todo_terminal_for_status(value), value
    for value in ("open", "blocked", "", None):
        assert not todo_terminal_for_status(value), value


if __name__ == "__main__":
    main()
