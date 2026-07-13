#!/usr/bin/env python3
"""Keep public workflows on official Actions with a native Node 24 runtime."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

NODE24_ACTION_MAJORS = {
    "actions/checkout": "v7",
    "actions/setup-node": "v6",
    "actions/setup-python": "v6",
    "actions/upload-artifact": "v7",
}


def main() -> int:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml"))
    )

    for action, major in NODE24_ACTION_MAJORS.items():
        references = [
            line.strip()
            for line in workflow_text.splitlines()
            if f"uses: {action}@" in line
        ]
        assert references, f"missing workflow reference for {action}"
        assert all(reference.endswith(f"@{major}") for reference in references), references

    print("github-actions-runtime-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
