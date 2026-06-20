#!/usr/bin/env python3
"""Smoke-test Terminal-Bench task image bootstrap planning."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "terminal_bench_task_image_bootstrap.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gh-tb-image-bootstrap-") as tmp:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-image",
                "example/task:prebuilt",
                "--target-image",
                "tb__example__client",
                "--work-dir",
                str(Path(tmp) / "image-bootstrap"),
                "--network-host",
                "--pretty",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True, payload
        assert payload["execute"] is False, payload
        assert payload["source_image"] == "example/task:prebuilt"
        assert payload["target_image"] == "tb__example__client"
        assert payload["apt_packages"] == ["tmux", "asciinema"], payload
        assert payload["required_commands"] == ["tmux", "asciinema"], payload
        assert payload["use_host_network"] is True
        assert payload["contract"]["score_or_task_behavior_changed"] is False
        assert payload["boundary"]["private_paths_recorded"] is False
        assert str(tmp) not in proc.stdout

        dockerfile = Path(tmp) / "image-bootstrap" / "Dockerfile"
        text = dockerfile.read_text(encoding="utf-8")
        assert "FROM example/task:prebuilt" in text
        assert "mirrors.tuna.tsinghua.edu.cn" in text
        assert "tmux" in text
        assert "asciinema" in text

        override_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-image",
                "example/task:prebuilt",
                "--target-image",
                "tb__example__client",
                "--work-dir",
                str(Path(tmp) / "image-bootstrap-override"),
                "--apt-package",
                "curl",
                "--required-command",
                "curl",
                "--pretty",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        override_payload = json.loads(override_proc.stdout)
        assert override_payload["apt_packages"] == ["curl"], override_payload
        assert override_payload["required_commands"] == ["curl"], override_payload
        override_text = (Path(tmp) / "image-bootstrap-override" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert "install -y --no-install-recommends curl" in override_text
        assert "tmux" not in override_text
        assert "asciinema" not in override_text

    print("terminal-bench task image bootstrap smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
