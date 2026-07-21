from __future__ import annotations

from typing import Any, Protocol


class RecordTarget(Protocol):
    cli_bin: str
    identity: str
    base_token: str
    table_id: str


def lark_record_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    fields = data.get("fields") if isinstance(data, dict) else None
    rows = data.get("data") if isinstance(data, dict) else None
    record_ids = data.get("record_id_list") if isinstance(data, dict) else None
    if not isinstance(fields, list) or not isinstance(rows, list):
        return []
    records: list[dict[str, Any]] = []
    for index, values in enumerate(rows):
        if not isinstance(values, list):
            continue
        record = {
            str(field): values[pos] if pos < len(values) else None
            for pos, field in enumerate(fields)
        }
        if isinstance(record_ids, list) and index < len(record_ids):
            record["_record_id"] = record_ids[index]
        records.append(record)
    return records


def todo_record_entries(parsed: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for record in lark_record_rows(parsed if isinstance(parsed, dict) else {}):
        todo_id = str(record.get("LoopX Todo ID") or "").strip()
        goal_id = str(record.get("LoopX Goal ID") or "").strip()
        record_id = str(record.get("_record_id") or "").strip()
        if todo_id and goal_id and record_id:
            result.append({"key": f"{goal_id}:{todo_id}", "record_id": record_id})
    return result


def record_list_is_complete(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    data = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
    if not isinstance(data, dict):
        return False
    return (
        data.get("has_more") is False
        and not str(data.get("page_token") or data.get("next_page_token") or "").strip()
    )


def todo_record_list_is_authoritative(parsed: Any) -> bool:
    if not record_list_is_complete(parsed) or not isinstance(parsed, dict):
        return False
    data = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
    if not isinstance(data, dict):
        return False
    fields = data.get("fields")
    rows = data.get("data")
    record_ids = data.get("record_id_list")
    return (
        isinstance(fields, list)
        and {"LoopX Goal ID", "LoopX Todo ID"}.issubset(
            {str(field) for field in fields}
        )
        and isinstance(rows, list)
        and isinstance(record_ids, list)
        and len(record_ids) == len(rows)
    )


def build_record_delete_command(
    config: RecordTarget,
    *,
    record_ids: list[str],
) -> list[str]:
    args = [
        config.cli_bin,
        "base",
        "+record-delete",
        "--as",
        config.identity,
        "--base-token",
        config.base_token,
        "--table-id",
        config.table_id,
    ]
    for record_id in record_ids:
        args.extend(["--record-id", record_id])
    return [*args, "--yes"]
