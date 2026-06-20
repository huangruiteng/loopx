#!/usr/bin/env python3
"""Guard Terminal-Bench no-rebuild runs from implicit compose rebuilds.

Terminal-Bench can skip the explicit ``docker compose build`` step while still
letting ``docker compose up`` trigger a build because task compose files include
``build:``.  This cloud-host guard patches a local Terminal-Bench checkout so
``no_rebuild`` also implies ``docker compose up --no-build -d``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "terminal_bench_no_rebuild_guard_v0"
MANAGER_RELATIVE_PATH = Path("terminal_bench/terminal/docker_compose_manager.py")
OLD_SNIPPET = '        self._run_docker_compose_command(["up", "-d"])\n'
NEW_SNIPPET = (
    '        up_command = ["up", "-d"]\n'
    "        if self._no_rebuild:\n"
    '            up_command.insert(1, "--no-build")\n'
    "        self._run_docker_compose_command(up_command)\n"
)


def _candidate_paths(root: Path) -> list[Path]:
    candidates = [root / MANAGER_RELATIVE_PATH]
    candidates.extend(
        sorted(
            root.glob(
                ".venv/lib/python*/site-packages/"
                "terminal_bench/terminal/docker_compose_manager.py"
            )
        )
    )
    return [path for path in candidates if path.exists()]


def _classify_text(text: str) -> tuple[str, bool]:
    if NEW_SNIPPET in text:
        return "already_guarded", False
    if OLD_SNIPPET in text:
        return "needs_guard_patch", True
    if "--no-build" in text and "self._no_rebuild" in text:
        return "custom_guard_present", False
    return "unsupported_manager_shape", False


def build_plan(root: Path, *, apply: bool = False) -> dict[str, Any]:
    root = root.expanduser()
    manager_paths = _candidate_paths(root)
    files: list[dict[str, Any]] = []
    patched = 0
    unsupported = 0
    needs_patch = 0

    for path in manager_paths:
        text = path.read_text(encoding="utf-8")
        status, patchable = _classify_text(text)
        if status == "needs_guard_patch":
            needs_patch += 1
        if status == "unsupported_manager_shape":
            unsupported += 1
        if apply and patchable:
            path.write_text(text.replace(OLD_SNIPPET, NEW_SNIPPET), encoding="utf-8")
            status = "patched"
            patched += 1
        files.append(
            {
                "relative_path": str(path.relative_to(root)),
                "status": status,
                "patchable": patchable,
                "patched": status == "patched",
            }
        )

    first_blocker = ""
    if not manager_paths:
        first_blocker = "terminal_bench_manager_not_found"
    elif unsupported:
        first_blocker = "terminal_bench_manager_unsupported_shape"
    elif needs_patch and not apply:
        first_blocker = "terminal_bench_no_rebuild_guard_not_applied"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not first_blocker,
        "first_blocker": first_blocker,
        "terminal_bench_root_basename": root.name,
        "private_root_recorded": False,
        "apply": apply,
        "manager_file_count": len(manager_paths),
        "patched_file_count": patched,
        "files": files,
        "contract": {
            "no_rebuild_implies_compose_no_build": True,
            "score_or_task_behavior_changed": False,
            "runner_surface_changed": "docker_compose_startup_only",
        },
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "private_paths_recorded": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or patch a local Terminal-Bench checkout so no-rebuild "
            "also disables implicit compose builds."
        )
    )
    parser.add_argument("--terminal-bench-root", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_plan(Path(args.terminal_bench_root), apply=args.apply)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
