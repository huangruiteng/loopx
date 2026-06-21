#!/usr/bin/env python3
"""Smoke-test the opt-in real Codex CLI worker invocation contract.

The fake executable keeps this public smoke deterministic. It proves the
runner's real-worker mode uses the Codex CLI invocation boundary without
requiring credentials, real session history, or external services.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "examples" / "codex-cli-long-run-regression-runner-smoke.py"


def write_fake_codex(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "assert sys.argv[1] == 'exec', sys.argv\n"
        "assert '--ephemeral' in sys.argv, sys.argv\n"
        "assert '--ignore-user-config' in sys.argv, sys.argv\n"
        "assert '--ignore-rules' in sys.argv, sys.argv\n"
        "assert os.environ['HOME'].endswith('/home'), os.environ['HOME']\n"
        "assert os.environ['CODEX_HOME'].endswith('/home/.codex'), os.environ['CODEX_HOME']\n"
        "project = Path(os.environ['LOOPX_LONG_RUN_PROJECT'])\n"
        "artifact = project / os.environ['LOOPX_LONG_RUN_ARTIFACT_REL']\n"
        "artifact.parent.mkdir(parents=True, exist_ok=True)\n"
        "artifact.write_text(os.environ['LOOPX_LONG_RUN_MARKER'] + '\\n', encoding='utf-8')\n"
        "print('fake codex worker wrote ' + artifact.name)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-fake-codex-") as raw_tmp:
        fake_codex = Path(raw_tmp) / "codex"
        write_fake_codex(fake_codex)
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--worker-mode",
                "real-codex",
                "--codex-cli",
                str(fake_codex),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    assert "worker_mode=real-codex" in result.stdout, result.stdout
    assert "steps=3" in result.stdout, result.stdout
    assert "codex-cli-long-run-regression-runner-smoke ok" in result.stdout, result.stdout
    print("codex-cli-long-run-real-worker-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
