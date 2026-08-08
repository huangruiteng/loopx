from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "examples" / "loopx-history-conclusion-recall-smoke.py"


def _load_contract() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "loopx_history_conclusion_export_contract",
        SMOKE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("history-conclusion export contract is not importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_history_conclusion_export_contract() -> None:
    contract = _load_contract()
    assert not contract._run_cases()
