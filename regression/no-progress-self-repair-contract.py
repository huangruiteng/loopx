#!/usr/bin/env python3
"""Regression wrapper for autonomous no-progress self-repair contracts."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = REPO_ROOT / "examples" / "autonomous-replan-obligation-smoke.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("autonomous_replan_obligation_smoke", SMOKE_PATH)
    assert spec is not None and spec.loader is not None, SMOKE_PATH
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.main()
    assert result == 0, result
    print("no-progress-self-repair-contract-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
