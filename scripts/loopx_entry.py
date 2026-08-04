from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys


def main() -> int:
    if sys.version_info < (3, 11):
        print(
            "loopx runtime error: Python 3.11+ is required; "
            f"selected Python is {sys.version_info.major}.{sys.version_info.minor}",
            file=sys.stderr,
        )
        return 2
    release_root_text = os.environ.get("LOOPX_RELEASE_ROOT")
    if not release_root_text:
        print("loopx runtime error: LOOPX_RELEASE_ROOT is not set", file=sys.stderr)
        return 2
    release_root = Path(release_root_text).expanduser().resolve()
    if not (release_root / "loopx" / "cli.py").is_file():
        print(
            f"loopx runtime error: release root is incomplete: {release_root}",
            file=sys.stderr,
        )
        return 2

    cwd = Path.cwd().resolve()
    filtered_path: list[str] = []
    for entry in sys.path:
        if entry in {"", "."}:
            continue
        absolute = Path(entry).resolve()
        if absolute in {cwd, release_root}:
            continue
        filtered_path.append(entry)
    sys.path[:] = [str(release_root), *filtered_path]
    sys.argv[0] = str(release_root / "scripts" / "loopx")
    runpy.run_module("loopx.cli", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
