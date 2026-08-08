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


def _extract_paths_block(text: str, event: str) -> str:
    """Extract the paths list under a given event (pull_request or push)."""
    marker = f"\n  {event}:"
    idx = text.find(marker)
    if idx == -1:
        return ""
    rest = text[idx + len(marker):]
    paths_marker = "\n    paths:"
    pi = rest.find(paths_marker)
    if pi == -1:
        return ""
    block = rest[pi + len(paths_marker):]
    # Stop at the next top-level key (indented with exactly 2 spaces, not 6)
    lines = block.split("\n")
    collected = []
    for line in lines:
        if line and not line.startswith("      ") and not line.startswith("        "):
            break
        collected.append(line)
    return "\n".join(collected)


def assert_pr_and_push_trigger(trigger_text: str, path: str) -> None:
    marker = f'      - "{path}"'
    pr_block = _extract_paths_block(trigger_text, "pull_request")
    push_block = _extract_paths_block(trigger_text, "push")
    pr_count = pr_block.count(marker)
    push_count = push_block.count(marker)
    if pr_count != 1:
        raise AssertionError(
            f"workflow must trigger pull_request exactly once for {path!r}; found {pr_count}"
        )
    if push_count != 1:
        raise AssertionError(
            f"workflow must trigger push exactly once for {path!r}; found {push_count}"
        )


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger_text = text.split("\npermissions:", 1)[0]

    for needle in [
        "workflow_dispatch:",
        "schedule:",
        'cron: "37 */6 * * *"',
        "pull_request:",
        "branches:",
        "actions: read",
        "contents: read",
        "pages: write",
        "id-token: write",
        'node-version: "20"',
        "npm install -g npm@11",
        "npm ci --include=dev --no-audit --no-fund --registry=https://registry.npmjs.org",
        "docs/showcases/**",
        "docs/assets/long-running-loop-openviking-trajectory.png",
        "docs/assets/long-running-loop-ml-experiment-trajectory.png",
        "apps/presentation/site/**",
        "examples/showcase-catalog-smoke.py",
        "python3 examples/showcase-catalog-smoke.py",
        "examples/readme-star-history-smoke.py",
        "python3 examples/readme-star-history-smoke.py",
        "scripts/render-star-history.py",
        "secrets.STAR_HISTORY_READ_TOKEN",
        "Missing star-history credential",
        "fine-grained PAT limited to this repository with Metadata: read",
        "gh api graphql --paginate --slurp",
        "stargazerCount",
        "edges { starredAt }",
        "pageInfo { hasNextPage endCursor }",
        "{starred_at: .starredAt}",
        'jq \'length\'',
        "--expected-count",
        "output/frontstage-pages/site/site-assets/star-history.svg",
        "python3 examples/dev-book-publication-smoke.py",
        "python3 examples/dev-book-publication-smoke.py --site-dir output/frontstage-pages/site/docs/book",
        "npm run smoke:frontstage-share-bundle",
        "npm run export:frontstage-share -- --base /loopx/ --out-dir ../../../output/frontstage-pages",
        "mkdocs build --strict --site-dir output/frontstage-pages/site/docs",
        "mkdocs build --strict --config-file mkdocs.book.zh.yaml --site-dir output/frontstage-pages/site/docs/book",
        "mkdocs build --strict --config-file mkdocs.book.en.yaml --site-dir output/frontstage-pages/site/docs/book/en",
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
        "GH_TOKEN: ${{ github.token }}",
        '"/stargazers?per_page=100"',
    ]:
        assert_absent(text, forbidden)

    for path in [
        "mkdocs.book.zh.yaml",
        "mkdocs.book.en.yaml",
        "examples/dev-book-publication-smoke.py",
    ]:
        assert_pr_and_push_trigger(trigger_text, path)

    print("frontstage-pages-workflow-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
