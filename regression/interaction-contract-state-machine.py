#!/usr/bin/env python3
"""Regression wrapper for the interaction contract state machine."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = (
    REPO_ROOT
    / "examples"
    / "control_plane"
    / "interaction-contract-state-machine-smoke.py"
)


def main() -> int:
    spec = importlib.util.spec_from_file_location(
        "interaction_contract_state_machine_smoke",
        SMOKE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {SMOKE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
