#!/usr/bin/env python3
"""Validate the public core-control-plane diagram docs stay linked and safe."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "docs" / "product" / "core-control-plane"

FILES = [
    DOC_DIR / "README.md",
    DOC_DIR / "interaction-catalog.md",
    DOC_DIR / "state-definitions.md",
    DOC_DIR / "state-machine.md",
]

FORBIDDEN_PUBLIC_STRINGS = [
    "bytedance",
    "larkoffice",
    "EAAtdvU1bokXbyxXdv7cDAAbnSb",
    "/Users/",
    "/private/tmp",
    "127.0.0.1",
    "localhost",
    "appSecret",
    "accessToken",
]


def read(path: Path) -> str:
    assert path.exists(), f"missing doc: {path}"
    return path.read_text(encoding="utf-8")


def main() -> None:
    docs = {path.name: read(path) for path in FILES}
    combined = "\n".join(docs.values())

    for text in FORBIDDEN_PUBLIC_STRINGS:
        assert text.lower() not in combined.lower(), f"private marker leaked: {text}"

    readme = docs["README.md"]
    for filename in ("interaction-catalog.md", "state-definitions.md", "state-machine.md"):
        assert f"]({filename})" in readme, f"README does not link {filename}"

    assert "interaction_pattern_lens_v0" in docs["interaction-catalog.md"]
    assert "Core Pattern Map" in docs["interaction-catalog.md"]
    assert "State Definitions" in docs["state-definitions.md"]
    assert "Canonical State Bodies" in docs["state-definitions.md"]
    assert "Derived Runtime States" in docs["state-definitions.md"]
    assert "Top-Level Machine" in docs["state-machine.md"]
    assert "Gate Scope Submachine" in docs["state-machine.md"]
    assert "Projection Sink Submachine" in docs["state-machine.md"]
    assert "```mermaid" in combined


if __name__ == "__main__":
    main()
