#!/usr/bin/env python3
"""Smoke-test the host integration surface protocol contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = REPO_ROOT / "docs" / "reference" / "protocols" / "host-integration-surface-v0.md"
PROTOCOL_INDEX = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet
        for snippet in snippets
        if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    protocol_index = PROTOCOL_INDEX.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    architecture = ARCHITECTURE.read_text(encoding="utf-8")

    require(
        protocol,
        [
            "Hook activation",
            "MCP adapter",
            "Loopback server adapter",
            "CLI fallback",
            "## Thin Hook Activation",
            "## Lifecycle Reads",
            "## Controlled Writes",
            "## Compact Status Projection",
            "## CLI Fallback",
            "## Public/Private Boundary",
            "thin `/goal` body",
            "visible TUI as the primary surface",
            "controlled todo/gate writes",
            "future optional lease writes",
            "does not prove that any adapter is installed",
            "does not\n grant write authority beyond the existing CLI-equivalent",
            "loopx --format json --registry",
            "loopx todo claim",
            "loopx todo complete",
            "loopx quota spend-slot",
            "task_graph_projection_v0",
            "cadence_hint_v0",
            "do not add graph write authority",
            "task_lease_v0_when_shipped",
            "Browser/frontstage/server writes remain non-authoritative",
            "raw_transcripts_copied",
            "credentials_copied",
            "private_paths_copied",
            "remote_bind_default",
            "duplicate todo claim",
            "daemon-down cases fail\n   closed or fall back to CLI",
            "marks optional\n   projections as read-only inputs rather than authority",
        ],
        source=PROTOCOL,
    )
    forbidden = [
        "replace the user's visible TUI/control surface",
        "silently switch to hidden\n`codex exec`",
        "invent host-specific permission rules",
        "Bind remotely by default",
    ]
    require(protocol, forbidden, source=PROTOCOL)
    assert protocol.index("## Roles") < protocol.index("## Thin Hook Activation")
    assert protocol.index("## Thin Hook Activation") < protocol.index("## Lifecycle Reads")
    assert protocol.index("## Lifecycle Reads") < protocol.index("## Controlled Writes")
    assert protocol.index("## Controlled Writes") < protocol.index("## Compact Status Projection")
    assert protocol.index("## Compact Status Projection") < protocol.index("## CLI Fallback")
    assert protocol.index("## CLI Fallback") < protocol.index("## Public/Private Boundary")

    require(
        protocol_index,
        ["Host integration surface v0", "host-integration-surface-v0.md"],
        source=PROTOCOL_INDEX,
    )
    require(
        docs_index,
        ["Host integration surface v0", "reference/protocols/host-integration-surface-v0.md"],
        source=DOCS_INDEX,
    )
    require(
        architecture,
        [
            "host-integration surface",
            "hook/MCP/server adapters",
            "host-integration-surface-v0",
            "optional derived projections remain read-only",
            "CLI fallback remains available",
        ],
        source=ARCHITECTURE,
    )
    print("host-integration-surface-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
