from __future__ import annotations

import hashlib
import json
import re
from typing import Any


_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+.+$")


def json_shape_paths(value: Any, *, path: str = "$") -> list[str]:
    paths = {path}
    if isinstance(value, dict):
        for key, child in value.items():
            paths.update(json_shape_paths(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        list_path = f"{path}[]"
        paths.add(list_path)
        for child in value:
            paths.update(json_shape_paths(child, path=list_path))
    return sorted(paths)


def action_signature_semantic_sha256(value: Any) -> str | None:
    signatures: list[dict[str, Any]] = []

    def collect(current: Any, *, path: str) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                child_path = f"{path}.{key}"
                if key == "action_signature":
                    normalized = child
                    if isinstance(child, dict):
                        normalized = {
                            "schema_version": child.get("schema_version"),
                            "coverage": child.get("coverage"),
                            "matches": child.get("matches"),
                            "source_envelope_hashes_present": (
                                "source_hash" in child and "envelope_hash" in child
                            ),
                            "source_envelope_match": (
                                child.get("source_hash") == child.get("envelope_hash")
                            ),
                            "source_decision_hash_present": (
                                "source_decision_hash" in child
                            ),
                        }
                    signatures.append({"path": child_path, "value": normalized})
                collect(child, path=child_path)
        elif isinstance(current, list):
            for child in current:
                collect(child, path=f"{path}[]")

    collect(value, path="$")
    if not signatures:
        return None
    canonical = json.dumps(
        signatures,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def markdown_headings(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _MARKDOWN_HEADING.match(line)]
