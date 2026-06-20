#!/usr/bin/env python3
"""Smoke-test Terminal-Bench no-rebuild compose guard patching."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.terminal_bench_no_rebuild_guard import OLD_SNIPPET, build_plan


def _write_manager(root: Path) -> None:
    manager = root / "terminal_bench/terminal/docker_compose_manager.py"
    manager.parent.mkdir(parents=True)
    manager.write_text(
        "class DockerComposeManager:\n"
        "    def start(self):\n"
        "        if not self._no_rebuild:\n"
        '            self._run_docker_compose_command(["build"])\n'
        f"{OLD_SNIPPET}"
        "        return self._client_container\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "terminal-bench"
        _write_manager(root)

        preview = build_plan(root, apply=False)
        assert preview["ok"] is False
        assert preview["first_blocker"] == "terminal_bench_no_rebuild_guard_not_applied"
        assert preview["files"][0]["status"] == "needs_guard_patch"
        assert preview["boundary"]["raw_task_text_read"] is False
        assert preview["private_root_recorded"] is False

        applied = build_plan(root, apply=True)
        assert applied["ok"] is True
        assert applied["patched_file_count"] == 1
        manager_text = (root / "terminal_bench/terminal/docker_compose_manager.py").read_text(
            encoding="utf-8"
        )
        assert "--no-build" in manager_text
        assert "self._no_rebuild" in manager_text

        second = build_plan(root, apply=True)
        assert second["ok"] is True
        assert second["patched_file_count"] == 0
        assert second["files"][0]["status"] == "already_guarded"

    print("terminal-bench no-rebuild guard smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
