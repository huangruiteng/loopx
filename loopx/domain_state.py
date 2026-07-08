from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]


_DOMAIN_STATE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")


def _domain_state_token(value: str, *, field: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError(f"{field} must be non-empty")
    if not _DOMAIN_STATE_TOKEN_RE.match(token):
        raise ValueError(
            f"{field} must be a compact token using letters, digits, dot, colon, dash, or underscore"
        )
    return token


def default_domain_state_file_path(
    *,
    project: str | Path = ".",
    goal_id: str,
    domain_pack: str,
    filename: str,
) -> Path:
    """Return the project-local domain-state path for a goal and pack."""

    compact_goal_id = _domain_state_token(goal_id, field="goal_id")
    compact_pack = _domain_state_token(domain_pack, field="domain_pack")
    compact_filename = _domain_state_token(filename, field="filename")
    return (
        Path(project).expanduser()
        / ".loopx"
        / "domain-state"
        / compact_goal_id
        / compact_pack
        / compact_filename
    )


def upsert_domain_state_jsonl(
    ledger_path: str | Path,
    payload: dict[str, Any],
    *,
    key: dict[str, Any],
    existing_key_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Upsert a payload into a JSONL domain-state file by stable key."""

    if not isinstance(key, dict) or not key:
        raise ValueError("domain-state upsert key must be a non-empty dict")
    path = Path(ledger_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            rows: list[dict[str, Any]] = []
            updated = False
            if path.exists():
                for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid JSONL row {index} in domain-state ledger") from exc
                    row_key = row.get("domain_state_key") if isinstance(row, dict) else None
                    if row_key is None and existing_key_fn is not None and isinstance(row, dict):
                        row_key = existing_key_fn(row)
                    if isinstance(row, dict) and row_key == key:
                        if not updated:
                            rows.append({**payload, "domain_state_key": key})
                            updated = True
                        continue
                    rows.append(row)
            if not updated:
                rows.append({**payload, "domain_state_key": key})

            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f"{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_name = tmp_file.name
                tmp_file.write(
                    "".join(
                        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
                        for row in rows
                    )
                )
            os.replace(tmp_name, path)
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return {
        "status": "updated" if updated else "inserted",
        "row_count": len(rows),
        "ledger_key": key,
        "path_recorded": False,
    }
