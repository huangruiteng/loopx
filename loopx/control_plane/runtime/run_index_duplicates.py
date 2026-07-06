from __future__ import annotations

import json
from typing import Any


STRUCTURED_INDEX_KEYS = (
    "benchmark_run",
    "benchmark_result",
    "benchmark_comparison",
    "benchmark_learning_ledger",
    "benchmark_experiment_report",
    "active_user_assisted_pilot",
)


def index_identity(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("generated_at") or ""),
        str(record.get("json_path") or ""),
        str(record.get("markdown_path") or ""),
    )


def structured_index_payload_keys(record: dict[str, Any]) -> list[str]:
    return [key for key in STRUCTURED_INDEX_KEYS if isinstance(record.get(key), dict)]


def has_structured_index_payload(record: dict[str, Any]) -> bool:
    return bool(structured_index_payload_keys(record))


def _normalized_index_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "human_reward"}


def _normalized_key(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False)


def is_repairable_structured_artifact_duplicate(records: list[dict[str, Any]]) -> bool:
    classifications = {str(record.get("classification") or "") for record in records}
    health_checks = {str(record.get("health_check") or "") for record in records if record.get("health_check")}
    structured_rows = [record for record in records if has_structured_index_payload(record)]
    return (
        len(structured_rows) == 1
        and len(classifications) == 1
        and len(health_checks) > 1
        and all(
            has_structured_index_payload(record)
            or all(key not in record for key in STRUCTURED_INDEX_KEYS)
            for record in records
        )
    )


def is_structured_artifact_bundle(records: list[dict[str, Any]]) -> bool:
    """Return true when one artifact intentionally indexes multiple compact rows."""

    if len(records) <= 1:
        return False
    if any(isinstance(record.get("human_reward"), dict) for record in records):
        return False
    if not all(record.get("health_check") for record in records):
        return False
    if not all(len(structured_index_payload_keys(record)) == 1 for record in records):
        return False
    payload_fingerprints = {
        _normalized_key({key: record[key] for key in structured_index_payload_keys(record)})
        for record in records
    }
    return len(payload_fingerprints) == len(records)


def classify_index_duplicate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_keys = {_normalized_key(_normalized_index_record(record)) for record in records}
    reward_records = sum(1 for record in records if isinstance(record.get("human_reward"), dict))
    if reward_records and len(normalized_keys) == 1:
        return {
            "duplicate_kind": "reward_overlay",
            "severity": "info",
            "repair_hint": "no index repair needed; reward overlay rows merge into the base run",
            "action": "preserve_reward_overlay",
            "repairable": False,
            "reason": "reward overlay rows are intentionally merged by status checks",
        }

    if len(normalized_keys) == 1:
        return {
            "duplicate_kind": "plain_duplicate",
            "severity": "warning",
            "repair_hint": "append-only ledger repair can archive or supersede the extra identical index row",
            "action": "drop_plain_duplicate_rows",
            "repairable": True,
            "reason": "duplicate rows are byte-equivalent after reward fields are ignored",
        }

    if is_structured_artifact_bundle(records):
        return {
            "duplicate_kind": "structured_artifact_bundle",
            "severity": "info",
            "repair_hint": "no index repair needed; rows are compact projections from one reviewed artifact bundle",
            "action": "preserve_structured_artifact_bundle",
            "repairable": False,
            "reason": "multiple compact structured rows share one artifact identity by design",
        }

    if is_repairable_structured_artifact_duplicate(records):
        return {
            "duplicate_kind": "artifact_identity_collision",
            "severity": "warning",
            "repair_hint": "append-only ledger repair can keep the row with compact structured payload",
            "action": "keep_structured_artifact_row",
            "repairable": True,
            "reason": "one row carries the compact structured artifact payload and siblings only repeat the artifact identity",
        }

    return {
        "duplicate_kind": "artifact_identity_collision",
        "severity": "warning",
        "repair_hint": (
            "do not delete blindly; inspect artifacts and append an explicit repair/supersede event "
            "or rebuild a reviewed index copy"
        ),
        "action": "blocked_artifact_identity_collision",
        "repairable": False,
        "reason": "artifact identity collision is not auto-repairable without reviewed merge semantics",
    }


def duplicate_repair_decision(records: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    line_numbers = [line_number for line_number, _ in records]
    payload = classify_index_duplicate_records([record for _, record in records])
    action = payload.get("action")
    kept_line_numbers = line_numbers
    removed_line_numbers: list[int] = []
    if action == "drop_plain_duplicate_rows":
        kept_line_numbers = [line_numbers[0]]
        removed_line_numbers = line_numbers[1:]
    elif action == "keep_structured_artifact_row":
        structured_lines = [
            line_number
            for line_number, record in records
            if has_structured_index_payload(record)
        ]
        kept_line_numbers = [structured_lines[0]]
        removed_line_numbers = [line_number for line_number in line_numbers if line_number != structured_lines[0]]

    return {
        "action": action,
        "repairable": payload.get("repairable"),
        "line_numbers": line_numbers,
        "kept_line_numbers": kept_line_numbers,
        "removed_line_numbers": removed_line_numbers,
        "reason": payload.get("reason"),
    }
