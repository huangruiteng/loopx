#!/usr/bin/env python3
"""Smoke-test that the release wrapper is not shadowed by the caller cwd."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-release-wrapper-") as tmp:
        root = Path(tmp)
        release = root / "releases" / "20260624T000000Z"
        stale = root / "stale-checkout"
        wrapper = release / "scripts" / "loopx"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "scripts" / "loopx", wrapper)
        wrapper.chmod(0o755)
        _write(release / ".loopx-python", f"{sys.executable}\n")

        _write(release / "loopx" / "__init__.py", "")
        _write(
            release / "loopx" / "cli.py",
            "\n".join(
                [
                    "from __future__ import annotations",
                    "import json",
                    "import os",
                    "from pathlib import Path",
                    "",
                    "payload = {",
                    "    'source': 'release',",
                    "    'cwd_basename': Path.cwd().name,",
                    "    'argv0_basename': Path(__import__('sys').argv[0]).name,",
                    "    'argv_tail': __import__('sys').argv[1:],",
                    "    'module_file_inside_release': str(Path(__file__).resolve()).startswith(os.environ['LOOPX_RELEASE_ROOT']),",
                    "}",
                    "print(json.dumps(payload, sort_keys=True))",
                ]
            )
            + "\n",
        )
        _write(stale / "loopx" / "__init__.py", "")
        _write(
            stale / "loopx" / "cli.py",
            "raise SystemExit('stale checkout shadowed release wrapper')\n",
        )

        env = dict(os.environ)
        env["PYTHONPATH"] = str(stale)
        completed = subprocess.run(
            [str(wrapper), "--sentinel"],
            cwd=stale,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(completed.stdout)
        assert payload["source"] == "release", payload
        assert payload["cwd_basename"] == stale.name, payload
        assert payload["argv0_basename"] == "loopx", payload
        assert payload["argv_tail"] == ["--sentinel"], payload
        assert payload["module_file_inside_release"] is True, payload

    print("release-wrapper-import-isolation-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
