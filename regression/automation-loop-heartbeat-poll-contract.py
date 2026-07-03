#!/usr/bin/env python3
"""Regression wrapper for automation-loop heartbeat poll contracts.

The durable behavior lives in `examples/control_plane/heartbeat-quota-flow-smoke.py`.
This wrapper makes the default regression suite cover it without duplicating
fixtures or pulling in real Codex/Docker/model execution.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = REPO_ROOT / "examples" / "heartbeat-quota-flow-smoke.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location(
        "heartbeat_quota_flow_smoke",
        SMOKE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {SMOKE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
