from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from loopx.command_invocation import command_argv, resolve_command_path


@pytest.mark.skipif(os.name != "nt", reason="PowerShell script discovery is Windows-specific")
def test_resolve_and_run_powershell_script_from_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is not installed")
    script = tmp_path / "loopx.ps1"
    script.write_text(
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        'Write-Output ($args -join "|")\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))

    resolved = resolve_command_path("loopx")

    assert resolved == script
    argv = command_argv(resolved, ["alpha", "two words"], pwsh=pwsh)
    result = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alpha|two words"
