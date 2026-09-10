"""Conservative PR classification and fail-closed core CI aggregation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import PurePosixPath
import subprocess


CORE_JOBS = (
    "pytest",
    "node-minimum-compatibility",
    "stage2c-correctness-e2e",
    "windows-powershell",
)
ROOT_DOCS = {"README.md", "README.zh-CN.md", "CHANGELOG.md", "CONTRIBUTING.md"}


def requires_core_tests(paths: list[str]) -> bool:
    # Unknown paths, executable documentation, policy and runtime prompts run CI.
    # Disable rename detection at the caller so both old and new paths count.
    if not paths:
        return True
    return any(
        not (
            path in ROOT_DOCS
            or (path.startswith("docs/") and PurePosixPath(path).suffix == ".md")
        )
        for path in paths
    )


def verify(needs: object) -> None:
    if not isinstance(needs, dict) or set(needs) != {"changes", *CORE_JOBS}:
        raise ValueError("missing or unexpected merge-gate dependencies")
    changes = needs["changes"]
    if not isinstance(changes, dict) or changes.get("result") != "success":
        raise ValueError("change classification did not succeed")
    outputs = changes.get("outputs")
    classification = outputs.get("core_tests") if isinstance(outputs, dict) else None
    if classification not in ("true", "false"):
        raise ValueError("missing or invalid core-test classification")
    expected = "success" if classification == "true" else "skipped"
    for name in CORE_JOBS:
        job = needs[name]
        if not isinstance(job, dict) or job.get("result") != expected:
            raise ValueError(f"{name} must be {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify")
    classify.add_argument("--base", required=True)
    classify.add_argument("--head", required=True)
    sub.add_parser("verify")
    args = parser.parse_args()
    if args.command == "classify":
        # SHAs come through environment variables, never interpolated shell code.
        # Git failure propagates; it must never become a documentation-only pass.
        base = subprocess.check_output(
            ["git", "merge-base", args.base, args.head], text=True
        ).strip()
        raw = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, args.head, "--"]
        )
        paths = [os.fsdecode(path) for path in raw.split(b"\0") if path]
        print(f"core_tests={str(requires_core_tests(paths)).lower()}")
    else:
        verify(json.loads(os.environ["NEEDS_JSON"]))
        print("merge-gate: qualification complete")


if __name__ == "__main__":
    main()
