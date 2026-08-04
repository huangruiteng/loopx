from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from loopx.file_lock import exclusive_file_lock


def test_try_exclusive_file_lock_rejects_second_process(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    repo_root = Path(__file__).resolve().parents[1]
    child_code = """
from pathlib import Path
import sys

from loopx.file_lock import try_exclusive_file_lock

with try_exclusive_file_lock(Path(sys.argv[1])) as lock_path:
    print("blocked" if lock_path is None else "acquired")
    raise SystemExit(0 if lock_path is None else 7)
"""
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )

    with exclusive_file_lock(target):
        result = subprocess.run(
            [sys.executable, "-c", child_code, str(target)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "blocked"
