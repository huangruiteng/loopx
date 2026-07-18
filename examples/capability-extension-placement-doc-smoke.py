#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs" / "reference" / "extensions.md").read_text(encoding="utf-8")

for anchor in (
    "## Capability And Extension Placement",
    "loopx/capabilities/<capability>/",
    "loopx/extensions/",
    "extensions/<extension-id>/",
    "capability id, provider id",
    "name public capabilities after caller outcomes",
):
    assert anchor in AGENTS, anchor

for anchor in (
    "## Placement Decision For Agents",
    "What user outcome and caller-visible contract is being added or changed?",
    "Does the implementation need independent installation",
    "Some work belongs on both axes.",
    "`value-connectors` is an existing compatibility CLI",
    "Migrate each profile to",
    "capability_id: <existing-or-new-contract>",
    "reason: <why the nearest existing owner is or is not sufficient>",
):
    assert anchor in GUIDE, anchor

print("capability-extension-placement-doc-smoke: ok")
