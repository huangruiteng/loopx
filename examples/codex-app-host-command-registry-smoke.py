#!/usr/bin/env python3
"""Smoke-test the Codex App host command registry contract."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "codex-app-host-command-registry-v0.md"
INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX_PATH = REPO_ROOT / "docs" / "README.md"
HOST_SURFACE_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "host-integration-surface-v0.md"

REQUIRED_CANONICAL_COMMANDS = {
    "/loopx",
    "/loopx <goal text>",
    "/loopx-global-summary",
    "/loopx-global-gates",
    "/loopx-global-todos",
    "/loopx-global-risks",
}

REQUIRED_LEGACY_ALIASES = {
    "/loop-global-summary",
}

REJECTED_ALIASES = {
    "/loopx-summary-all",
}

PRIVATE_PATTERNS = [
    re.compile(r"/" + r"Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/" + r"private/tmp/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def json_blocks(markdown: str) -> list[dict]:
    blocks: list[dict] = []
    for match in re.finditer(r"```json\n(.*?)\n```", markdown, flags=re.S):
        blocks.append(json.loads(match.group(1)))
    return blocks


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def main() -> int:
    contract = read(CONTRACT_PATH)
    index = read(INDEX_PATH)
    docs_index = read(DOCS_INDEX_PATH)
    host_surface = read(HOST_SURFACE_PATH)

    for label, text in {
        "contract": contract,
        "protocol index": index,
        "docs index": docs_index,
        "host surface": host_surface,
    }.items():
        assert_public_safe(text, label)

    assert_contains(index, "codex_app_host_command_registry_v0", "protocol index")
    assert_contains(docs_index, "Codex App host command registry v0", "docs index")
    assert_contains(host_surface, "codex_app_host_command_registry_v0", "host surface")

    for command in REQUIRED_CANONICAL_COMMANDS:
        assert_contains(contract, command, "canonical command set")
    for alias in REQUIRED_LEGACY_ALIASES:
        assert_contains(contract, alias, "legacy alias note")
    for alias in REJECTED_ALIASES:
        if alias in contract:
            raise AssertionError(f"contract should not mention superseded alias {alias!r}")

    for needle in [
        "loopx bootstrap-command-pack --project .",
        "loopx start-goal --guided --project . --goal-text",
        "loopx slash-commands",
        "loopx_goal_command_v0",
        "global_manager_command_v0",
        "fail_closed_with_slash_help",
        "skill-level recognition",
    ]:
        assert_contains(contract, needle, "host command registry contract")

    blocks = json_blocks(contract)
    registry = next(item for item in blocks if item.get("schema_version") == "codex_app_host_command_registry_v0")
    assert registry["host_kind"] == "codex_app", registry
    commands = {item["command"]: item for item in registry["commands"]}
    assert commands["/loopx"]["mutation_policy"] == "read_first", commands
    assert commands["/loopx <goal text>"]["mutation_policy"] == "explicit_goal_start", commands
    assert commands["/loopx-global-summary"]["protocol"] == "global_manager_command_v0", commands
    assert commands["/loopx-global-summary"]["legacy_aliases"] == ["/loop-global-summary"], commands
    assert registry["unknown_command_policy"] == "fail_closed_with_slash_help", registry

    handoff = next(item for item in blocks if item.get("schema_version") == "codex_app_host_command_handoff_v0")
    assert handoff["canonical_command"] == "/loopx <goal text>", handoff
    assert handoff["project_root_label"] == "current workspace", handoff
    assert handoff["authority"]["project_local_write_allowed"] is True, handoff
    assert handoff["authority"]["global_control_write_allowed"] is False, handoff
    assert "project_root" not in handoff, handoff
    assert "private" not in json.dumps(handoff).lower(), handoff

    print("codex-app-host-command-registry-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
