"""Small process I/O helpers shared by SkillsBench ACP relay paths."""

from __future__ import annotations

import subprocess
import threading


def write_process_stdin_async(
    proc: subprocess.Popen[str],
    stdin_text: str | None,
) -> None:
    """Feed stdin without letting a full pipe bypass timeout watchdogs."""

    if stdin_text is None or proc.stdin is None:
        return
    stdin_pipe = proc.stdin
    proc.stdin = None

    def writer() -> None:
        try:
            stdin_pipe.write(stdin_text)
            stdin_pipe.close()
        except (BrokenPipeError, ValueError, OSError):
            pass

    threading.Thread(
        target=writer,
        name="loopx-skillsbench-acp-stdin-writer",
        daemon=True,
    ).start()
