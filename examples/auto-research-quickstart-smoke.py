#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research import (
    AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION,
    build_auto_research_quickstart,
)


def _run_json(command: list[str], *, cwd: Path) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preview = build_auto_research_quickstart(
            agent_id="codex-side-bypass",
            output_dir="auto_research_knn_pack",
            execute=False,
            cwd=root,
        )
        assert preview["schema_version"] == AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION
        assert preview["mode"] == "dry_run"
        assert not (root / "auto_research_knn_pack").exists()

        created = build_auto_research_quickstart(
            agent_id="codex-side-bypass",
            output_dir="auto_research_knn_pack",
            execute=True,
            cwd=root,
        )
        assert created["mode"] == "execute"
        pack = root / "auto_research_knn_pack"
        assert (pack / "research_contract.json").exists()
        assert (pack / "protected_eval.py").exists()
        assert (pack / "solution_candidate.py").exists()

        dev = _run_json(
            [
                sys.executable,
                "protected_eval.py",
                "--solution",
                "solution_candidate.py",
                "--split",
                "dev",
            ],
            cwd=pack,
        )
        holdout = _run_json(
            [
                sys.executable,
                "protected_eval.py",
                "--solution",
                "solution_candidate.py",
                "--split",
                "holdout",
            ],
            cwd=pack,
        )
        assert dev["exact"] is True
        assert holdout["exact"] is True
        assert dev["metric"]["value"] == 4.0
        assert holdout["metric"]["value"] == 4.5
        assert dev["protected_scope_clean"] is True
        assert holdout["protected_scope_clean"] is True
    print("auto-research quickstart smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
