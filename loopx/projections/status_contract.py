from __future__ import annotations

from typing import Any


def build_status_contract(
    *,
    schema_version: int,
    minimum_dashboard_schema_version: int,
    reload_hint: str,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "minimum_dashboard_schema_version": minimum_dashboard_schema_version,
        "producer": "loopx status",
        "reload_hint": reload_hint,
    }


def compact_status_contract_signals(
    value: Any,
    *,
    limit: int,
) -> dict[str, Any]:
    items = [str(item).strip() for item in value or [] if str(item).strip()]
    bounded = items[: max(0, limit)]
    return {
        "items": bounded,
        "total_count": len(items),
        "truncated": len(items) > len(bounded),
    }


def build_contract_health_projection(
    contract: dict[str, Any],
    *,
    signal_limit: int,
) -> dict[str, Any]:
    errors = compact_status_contract_signals(contract.get("errors"), limit=signal_limit)
    warnings = compact_status_contract_signals(contract.get("warnings"), limit=signal_limit)
    return {
        "contract_summary": contract.get("summary"),
        "contract_errors": errors["items"],
        "contract_errors_total_count": errors["total_count"],
        "contract_errors_truncated": errors["truncated"],
        "contract_warnings": warnings["items"],
        "contract_warnings_total_count": warnings["total_count"],
        "contract_warnings_truncated": warnings["truncated"],
    }
