from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import pytest

from loopx.extensions.process_runtime import run_capped_process


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group regression")
def test_timeout_terminates_provider_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-effect"
    ready_marker = tmp_path / "descendant-ready"
    child_code = (
        "from pathlib import Path; import signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(ready_marker)!r}).write_text('ready', encoding='utf-8'); "
        "time.sleep(2.5); "
        f"Path({str(marker)!r}).write_text('effect', encoding='utf-8')"
    )
    provider_code = (
        "from pathlib import Path; import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        f"ready = Path({str(ready_marker)!r}); "
        "\nwhile not ready.exists(): time.sleep(0.01)\n"
        "time.sleep(5)"
    )

    result = run_capped_process(
        [sys.executable, "-c", provider_code],
        stdin=json.dumps({"schema_version": "request_v0"}).encode(),
        timeout_seconds=1,
        output_limit_bytes=1024,
    )

    assert result.failure_kind == "timeout"
    time.sleep(0.5)
    assert not marker.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group regression")
def test_descendant_receives_the_full_termination_grace_period(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-cleanup"
    ready_marker = tmp_path / "descendant-ready"
    child_code = (
        "from pathlib import Path; import signal, time; "
        "stopping = [False]; "
        "signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__(0, True)); "
        f"Path({str(ready_marker)!r}).write_text('ready', encoding='utf-8'); "
        "\nwhile not stopping[0]: time.sleep(0.01)\n"
        "time.sleep(0.2); "
        f"Path({str(marker)!r}).write_text('cleaned', encoding='utf-8')"
    )
    provider_code = (
        "from pathlib import Path; import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        f"ready = Path({str(ready_marker)!r}); "
        "\nwhile not ready.exists(): time.sleep(0.01)\n"
        "time.sleep(5)"
    )

    result = run_capped_process(
        [sys.executable, "-c", provider_code],
        stdin=b"{}",
        timeout_seconds=1,
        output_limit_bytes=1024,
    )

    assert result.failure_kind == "timeout"
    assert marker.read_text(encoding="utf-8") == "cleaned"


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group regression")
def test_output_overflow_terminates_provider_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-effect"
    child_code = (
        "from pathlib import Path; import time; "
        "time.sleep(0.6); "
        f"Path({str(marker)!r}).write_text('effect', encoding='utf-8')"
    )
    provider_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        "sys.stdout.buffer.write(b'x' * 1025); sys.stdout.flush(); time.sleep(5)"
    )

    result = run_capped_process(
        [sys.executable, "-c", provider_code],
        stdin=b"{}",
        timeout_seconds=5,
        output_limit_bytes=1024,
    )

    assert result.failure_kind == "response_too_large"
    time.sleep(0.8)
    assert not marker.exists()
