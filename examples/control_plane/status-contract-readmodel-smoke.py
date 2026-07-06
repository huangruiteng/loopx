#!/usr/bin/env python3
"""Smoke-test status contract read-model parity."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.work_items import status_contract as status_contract_read_model  # noqa: E402


def direct_status_contract() -> dict[str, Any]:
    return status_contract_read_model.build_status_contract(
        schema_version=status_module.STATUS_CONTRACT_SCHEMA_VERSION,
        minimum_dashboard_schema_version=status_module.MINIMUM_DASHBOARD_STATUS_CONTRACT_SCHEMA_VERSION,
        reload_hint=status_module.STATUS_CONTRACT_RELOAD_HINT,
    )


def direct_compact_signals(value: Any, *, limit: int | None = None) -> dict[str, Any]:
    return status_contract_read_model.compact_status_contract_signals(
        value,
        limit=status_module.STATUS_CONTRACT_SIGNAL_LIMIT if limit is None else limit,
    )


def direct_contract_health(contract: dict[str, Any]) -> dict[str, Any]:
    return status_contract_read_model.build_contract_health_projection(
        contract,
        signal_limit=status_module.STATUS_CONTRACT_SIGNAL_LIMIT,
    )


def main() -> None:
    assert status_module.build_status_contract() == direct_status_contract()

    signals = [" first ", "", None, "second", "third"]
    assert direct_compact_signals(signals, limit=2) == {
        "items": ["first", "None"],
        "total_count": 4,
        "truncated": True,
    }
    assert direct_compact_signals(signals, limit=0) == {
        "items": [],
        "total_count": 4,
        "truncated": True,
    }

    contract = {
        "summary": {"errors": 3, "warnings": 2, "checks": 5},
        "errors": ["error-a", "error-b", "error-c"],
        "warnings": ["warning-a", "warning-b"],
    }
    assert status_module.build_contract_health_projection(contract) == direct_contract_health(contract)

    empty_contract = {"summary": {"errors": 0, "warnings": 0, "checks": 1}}
    assert status_module.build_contract_health_projection(empty_contract) == direct_contract_health(empty_contract)

    print("status-contract-readmodel-smoke ok")


if __name__ == "__main__":
    main()
