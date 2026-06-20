#!/usr/bin/env python3
"""Smoke-test the public-safe GitHub Pages frontstage workflow source."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "frontstage-pages.yml"


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing workflow contract: {needle}")


def assert_absent(text: str, needle: str) -> None:
    if needle in text:
        raise AssertionError(f"workflow must not reference {needle!r}")


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

    for needle in [
        "workflow_dispatch:",
        "pull_request:",
        "branches:",
        "actions: read",
        "contents: read",
        "pages: write",
        "id-token: write",
        'node-version: "20"',
        "npm install -g npm@11",
        "npm ci --include=dev --no-audit --no-fund --registry=https://registry.npmjs.org",
        "npm run smoke:frontstage-share-bundle",
        "npm run export:frontstage-share -- --base /goal-harness/ --out-dir ../../output/frontstage-pages",
        "actions/configure-pages@v6",
        "enablement: true",
        "actions/upload-pages-artifact@v5",
        "path: output/frontstage-pages/site",
        "actions/deploy-pages@v5",
        "if: github.event_name != 'pull_request'",
    ]:
        assert_contains(text, needle)

    for forbidden in [
        "serve-status",
        "status.local.json",
        ".codex/goals",
        ".goal-" + "harness/",
        "registry.global.json",
        "enable-reward-write-api",
        "npm run dev",
        "npm run preview",
    ]:
        assert_absent(text, forbidden)

    print("frontstage-pages-workflow-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
