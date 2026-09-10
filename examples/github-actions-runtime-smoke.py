#!/usr/bin/env python3
"""Keep public workflows on official Actions with a native Node 24 runtime."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

NODE24_ACTION_MAJORS = {
    "actions/checkout": "v7",
    "actions/setup-node": "v6",
    "actions/setup-python": "v6",
    "actions/upload-artifact": "v7",
}

PRIMARY_NODE_VERSION = "24"
MINIMUM_NODE_VERSION = "22.6"
FORWARD_NODE_VERSION = "26"


def declared_major(reference: str) -> str:
    revision = reference.split("@", 1)[1].split("#", 1)[0].strip()
    if revision.startswith("v"):
        return revision.split(".", 1)[0]

    assert re.fullmatch(r"[0-9a-f]{40}", revision), reference
    annotation = re.search(r"#\s*(v\d+)(?:\.|\s|$)", reference)
    assert annotation is not None, (
        f"immutable action pins need a human-readable major annotation: {reference}"
    )
    return annotation.group(1)


def main() -> int:
    workflows = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOWS.glob("*.yml"))
    }
    workflow_text = "\n".join(workflows.values())

    for action, major in NODE24_ACTION_MAJORS.items():
        references = [
            line.strip()
            for line in workflow_text.splitlines()
            if f"uses: {action}@" in line
        ]
        assert references, f"missing workflow reference for {action}"
        assert all(declared_major(reference) == major for reference in references), references

    declared_versions = {
        name: re.findall(r'^\s*node-version:\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
        for name, text in workflows.items()
    }
    for name, versions in declared_versions.items():
        if not versions:
            continue
        expected = (
            {PRIMARY_NODE_VERSION, MINIMUM_NODE_VERSION, FORWARD_NODE_VERSION}
            if name == "python-tests.yml"
            else {PRIMARY_NODE_VERSION}
        )
        assert set(versions) <= expected, (name, versions)

    python_versions = declared_versions["python-tests.yml"]
    assert python_versions.count(MINIMUM_NODE_VERSION) == 1, python_versions
    assert python_versions.count(FORWARD_NODE_VERSION) == 1, python_versions
    assert PRIMARY_NODE_VERSION in python_versions, python_versions

    python_workflow = workflows["python-tests.yml"]
    assert "node-forward-compatibility:" in python_workflow
    assert "continue-on-error: true" in python_workflow
    assert "needs: [changes, pytest, node-minimum-compatibility," in python_workflow

    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["engines"]["node"] == f">={MINIMUM_NODE_VERSION}"

    print("github-actions-runtime-smoke ok: Node 24 primary, 22.6 minimum, 26 forward")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
