from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def install_bundled_lark_extension(
    *,
    repo_root: Path,
    registry: Path,
    runtime_root: Path,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            "extension",
            "install",
            "--bundled",
            "loopx-lark",
            "--execute",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if payload.get("doctor", {}).get("verified") is not True:
        raise AssertionError(payload)
    return payload
