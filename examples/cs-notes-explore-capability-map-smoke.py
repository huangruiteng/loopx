#!/usr/bin/env python3
"""Smoke-test the public-safe CS-Notes exploration capability map."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "reference" / "protocols" / "cs-notes-explore-capability-map-v0.md"
INDEX = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"


REQUIRED_CAPABILITIES = (
    "material_intake_profile_v0",
    "trusted_source_scan_plan_v0",
    "pre_tick_gate_v0",
    "todo_triage_index_v0",
    "snippet_registry_contract_v0",
    "guarded_heartbeat_visibility_v0",
)

REQUIRED_SECTIONS = (
    "## Boundary",
    "## Selected Capabilities",
    "## Scenario Fit",
    "## Not Imported",
    "## Recommended Next Step",
)

PRIVATE_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"https?://"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

FORBIDDEN_TERMS = tuple(
    "".join(parts)
    for parts in (
        (".", "local"),
        ("LEARNING", "_MATERIAL", "_CANDIDATES"),
        ("coo", "kie"),
        ("pass", "word"),
        ("se", "cret"),
        ("to", "ken="),
        ("raw", " transcript"),
    )
)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    assert text.startswith("# cs_notes_explore_capability_map_v0"), text[:80]
    for section in REQUIRED_SECTIONS:
        assert section in text, section
    for capability in REQUIRED_CAPABILITIES:
        assert capability in text, capability
    assert "exploration_plan_packet_v0" in text, text
    assert "Repo issue fix" in text, text
    assert "Self-media and creator operations" in text, text
    assert "Experiment and other vertical state surfaces" in text, text

    for pattern in PRIVATE_PATTERNS:
        assert not pattern.search(text), pattern.pattern
    lowered = text.lower()
    leaked = [term for term in FORBIDDEN_TERMS if term.lower() in lowered]
    assert not leaked, leaked

    index = INDEX.read_text(encoding="utf-8")
    assert "cs-notes-explore-capability-map-v0.md" in index, "protocol index link"

    print("cs-notes-explore-capability-map-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
