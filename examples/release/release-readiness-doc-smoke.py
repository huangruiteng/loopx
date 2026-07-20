#!/usr/bin/env python3
"""Validate the public release-readiness doc wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "product" / "release-readiness.md"
README = ROOT / "README.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
PRODUCT_INDEX = ROOT / "docs" / "product" / "README.md"

FORBIDDEN_PUBLIC_STRINGS = [
    "/Users/",
    "/private/tmp/",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "raw_thread",
    "session_history",
    "verifier_output_tail",
    "ACTIVE_GOAL_STATE.md:",
]


def read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing expected file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def validate_boundary(path: Path) -> None:
    text = read(path)
    label = str(path.relative_to(ROOT))
    for forbidden in FORBIDDEN_PUBLIC_STRINGS:
        if forbidden in text:
            raise AssertionError(f"{label} contains forbidden string {forbidden!r}")


def main() -> None:
    for path in [DOC, README, DOCS_INDEX, PRODUCT_INDEX]:
        validate_boundary(path)

    doc = compact(read(DOC))
    for required in [
        "Status: v0.x maintainer contract.",
        "## Supported Install And Update Paths",
        "loopx update --check",
        "loopx update --dry-run",
        "loopx update --execute",
        "## Named Version Contract",
        "The version source is `loopx.__version__`, mirrored by `pyproject.toml`",
        "examples/release/release-version-contract-smoke.py",
        "## Compatibility Gate",
        "examples/release/codex-cli-no-clone-release-verification-smoke.py",
        "examples/release/release-readiness-doc-smoke.py",
        "loopx canary release-qualification",
        "exact_release_commit_qualification_manifest_v0",
        "same Git commit, Git tree id, package version, and version tag",
        "## Canary Model",
        "catalog-informed readiness slice",
        "near-E2E",
        "do not add new IPs solely to describe a validation bundle",
        "examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence",
        "python3 -m loopx.cli canary smoke-suite --profile public-smoke-watch --jobs 4 --timeout-seconds 60",
        "python3 examples/run-smokes.py --suite full-public --jobs 4 --timeout-seconds 60",
        "## What Is Safe To Depend On",
        "loopx doctor",
        "quota should-run",
        "/loopx-global-summary",
        "benchmark runner behavior, scoring, upload",
        "## Release Note Checklist",
        "Optional capability activation",
        "If no persistent switch exists",
        "### Capability Narrative Gate",
        "**User outcome**",
        "**Shipped layer**",
        "**Last-mile boundary**",
        "A built-in capability is not an optional extension",
        "Do not overclaim a complete workflow",
        "public/private scan",
        "## 中文摘要",
        "Bilingual releases must preserve these same group boundaries",
        "mirrors the English group structure and material claims",
    ]:
        assert_contains(doc, required, "release-readiness doc")

    root_readme = read(README)
    docs_index = read(DOCS_INDEX)
    product_index = read(PRODUCT_INDEX)
    assert_contains(root_readme, "docs/product/release-readiness.md", "root README")
    assert_contains(docs_index, "product/release-readiness.md", "docs index")
    assert_contains(product_index, "release-readiness.md", "product index")

    print("release-readiness-doc-smoke ok")


if __name__ == "__main__":
    main()
