from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
import tomllib
from typing import Any


EXTENSION_MANIFEST_SCHEMA_VERSION = "loopx_extension_manifest_v0"
LOOPX_EXTENSION_API_VERSION = 1
_API_CLAUSE = re.compile(r"^(>=|<=|==|>|<)?\s*(\d+)$")
_PROTOCOL_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}_v\d+$")
_PYTHON_MODULE_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


def _required_string(record: Mapping[str, Any], key: str, *, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires non-empty string `{key}`")
    return value.strip()


def _string_list(record: Mapping[str, Any], key: str, *, context: str) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{context} requires `{key}` to be an array of strings")
    return [item.strip() for item in value]


def _runtime_contract(
    raw: Mapping[str, Any],
    *,
    permissions: list[str],
    context: str,
) -> dict[str, Any] | None:
    value = raw.get("runtime")
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} requires `runtime` to be a TOML table")
    runtime_context = f"{context} runtime"
    protocol = _required_string(value, "protocol", context=runtime_context)
    if not _PROTOCOL_RE.fullmatch(protocol):
        raise ValueError(
            f"{runtime_context} protocol must be a versioned lower-snake token"
        )
    entrypoint_raw = value.get("entrypoint")
    python_module_raw = value.get("python_module")
    if (entrypoint_raw is None) == (python_module_raw is None):
        raise ValueError(
            f"{runtime_context} requires exactly one of `entrypoint` or `python_module`"
        )
    entrypoint: str | None = None
    python_module: str | None = None
    if entrypoint_raw is not None:
        entrypoint = _required_string(value, "entrypoint", context=runtime_context)
        if "\x00" in entrypoint:
            raise ValueError(f"{runtime_context} entrypoint contains an invalid byte")
    else:
        python_module = _required_string(
            value,
            "python_module",
            context=runtime_context,
        )
        if not _PYTHON_MODULE_RE.fullmatch(python_module):
            raise ValueError(
                f"{runtime_context} python_module must be a dotted Python module name"
            )
    args = _string_list(value, "args", context=runtime_context)
    doctor_args = _string_list(value, "doctor_args", context=runtime_context)
    required_permissions = _string_list(
        value,
        "required_permissions",
        context=runtime_context,
    )
    undeclared = sorted(set(required_permissions) - set(permissions))
    if undeclared:
        raise ValueError(
            f"{runtime_context} requires undeclared permissions {undeclared}"
        )
    timeout_seconds = value.get("timeout_seconds", 30)
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 120:
        raise ValueError(
            f"{runtime_context} timeout_seconds must be an integer from 1 to 120"
        )
    runtime = {
        "protocol": protocol,
        "args": args,
        "doctor_args": doctor_args,
        "required_permissions": required_permissions,
        "timeout_seconds": timeout_seconds,
    }
    runtime["entrypoint" if entrypoint is not None else "python_module"] = (
        entrypoint if entrypoint is not None else python_module
    )
    return runtime


def _require_compatible_loopx_api(requirement: str, *, context: str) -> None:
    clauses = [clause.strip() for clause in requirement.split(",")]
    if not clauses or any(not clause for clause in clauses):
        raise ValueError(f"{context} has invalid `requires_loopx_api` `{requirement}`")
    comparisons = {
        ">=": lambda wanted: LOOPX_EXTENSION_API_VERSION >= wanted,
        "<=": lambda wanted: LOOPX_EXTENSION_API_VERSION <= wanted,
        "==": lambda wanted: LOOPX_EXTENSION_API_VERSION == wanted,
        ">": lambda wanted: LOOPX_EXTENSION_API_VERSION > wanted,
        "<": lambda wanted: LOOPX_EXTENSION_API_VERSION < wanted,
    }
    for clause in clauses:
        match = _API_CLAUSE.fullmatch(clause)
        if match is None:
            raise ValueError(
                f"{context} has invalid `requires_loopx_api` clause `{clause}`; "
                "expected integer constraints such as `>=1,<2`"
            )
        operator = match.group(1) or "=="
        wanted = int(match.group(2))
        if not comparisons[operator](wanted):
            raise ValueError(
                f"{context} requires LoopX extension API `{requirement}`, "
                f"but this runtime provides `{LOOPX_EXTENSION_API_VERSION}`"
            )


def load_extension_manifest(path: str | Path) -> dict[str, Any]:
    """Read one declarative manifest without importing extension code."""

    manifest_path = Path(path).expanduser()
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(
            f"cannot read extension manifest `{manifest_path}`: {exc}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise ValueError(
            f"extension manifest `{manifest_path}` must contain a TOML table"
        )

    context = f"extension manifest `{manifest_path}`"
    schema_version = _required_string(raw, "schema_version", context=context)
    if schema_version != EXTENSION_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"{context} has unsupported schema_version `{schema_version}`; "
            f"expected `{EXTENSION_MANIFEST_SCHEMA_VERSION}`"
        )
    extension_id = _required_string(raw, "id", context=context)
    version = _required_string(raw, "version", context=context)
    requires_loopx_api = _required_string(raw, "requires_loopx_api", context=context)
    _require_compatible_loopx_api(requires_loopx_api, context=context)
    permissions = _string_list(raw, "permissions", context=context)
    runtime = _runtime_contract(raw, permissions=permissions, context=context)
    provided = raw.get("provides", [])
    implemented = raw.get("implements", [])
    if not isinstance(provided, list):
        raise ValueError(f"{context} requires `provides` to contain TOML tables")
    if not isinstance(implemented, list):
        raise ValueError(f"{context} requires `implements` to contain TOML tables")
    if runtime is None and not provided and not implemented:
        raise ValueError(
            f"{context} requires an executable `runtime`, `[[provides]]`, "
            "or `[[implements]]`"
        )

    capabilities: list[dict[str, Any]] = []
    for index, item in enumerate(provided):
        item_context = f"{context} provides[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{item_context} must be a TOML table")
        capability = dict(item)
        capability["id"] = _required_string(item, "id", context=item_context)
        capability["capability_kind"] = _required_string(
            item,
            "kind",
            context=item_context,
        )
        capability["origin"] = "extension"
        capability["visibility"] = str(item.get("visibility", "public")).strip()
        capability["provider_id"] = extension_id
        capability["provider_version"] = version
        capabilities.append(capability)

    implementations: list[dict[str, Any]] = []
    for index, item in enumerate(implemented):
        item_context = f"{context} implements[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{item_context} must be a TOML table")
        protocol = _required_string(item, "protocol", context=item_context)
        if not _PROTOCOL_RE.fullmatch(protocol):
            raise ValueError(
                f"{item_context} protocol must be a versioned lower-snake token"
            )
        if runtime is None:
            raise ValueError(f"{item_context} requires an executable runtime")
        if runtime["protocol"] != protocol:
            raise ValueError(
                f"{item_context} protocol must match runtime protocol "
                f"`{runtime['protocol']}`"
            )
        implementations.append(
            {
                "capability_id": _required_string(
                    item,
                    "capability_id",
                    context=item_context,
                ),
                "protocol": protocol,
                "provider_id": extension_id,
                "provider_version": version,
            }
        )

    return {
        "provider": {
            "id": extension_id,
            "origin": "extension",
            "declared": True,
            "installed": False,
            "enabled": False,
            "ready": False,
            "version": version,
            "requires_loopx_api": requires_loopx_api,
            "permissions": permissions,
        },
        "capabilities": capabilities,
        "implementations": implementations,
        "runtime": runtime,
    }
