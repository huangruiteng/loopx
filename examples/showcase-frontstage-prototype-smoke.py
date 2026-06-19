#!/usr/bin/env python3
"""Smoke-test the catalog-driven showcase frontstage prototype."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"
PROTOTYPE = REPO_ROOT / "examples" / "showcase-frontstage-prototype.py"
PRIVATE_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("lark", "office.com"),
        ("internal", "-api-drive"),
        ("bytedance.com", "/wiki"),
        ("/", "Users/"),
        (".codex", "/goal-harness"),
        ("BEGIN", " PRIVATE ", "KEY"),
        ("Author", "ization:"),
        ("to", "ken="),
        ("pass", "word="),
    )
)


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    cases = catalog["cases"]
    with tempfile.TemporaryDirectory(prefix="goal-harness-showcase-frontstage-") as tmp:
        output = Path(tmp) / "frontstage.html"
        result = subprocess.run(
            [sys.executable, str(PROTOTYPE), "--output", str(output)],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        assert str(output) in result.stdout, result.stdout
        html = output.read_text(encoding="utf-8")

    for marker in PRIVATE_MARKERS:
        assert marker not in html, marker

    for required in (
        '<section class="hero">',
        '<p class="punchline">',
        'aria-label="Executor loop versus control plane"',
        "docs/showcases/showcase-catalog.json",
        "control-plane-board.svg",
        str(catalog["schema_version"]),
    ):
        assert required in html, required

    for case in cases:
        case_id = str(case["id"])
        assert f'data-case-id="{case_id}"' in html, case_id
        for field in ("title", "headline", "user_value", "evidence_boundary"):
            assert str(case[field]) in html, (case_id, field)
        assert str(case["case_page"]).replace("docs/showcases/", "") in html or str(case["case_page"]) in html
        storyboard_path = case.get("storyboard_path")
        if isinstance(storyboard_path, str) and storyboard_path:
            assert storyboard_path.replace("docs/showcases/", "") in html or storyboard_path in html
        for tag in case.get("pattern_tags", []):
            assert str(tag) in html, (case_id, tag)
        frontend = case["frontend_card"]
        for beat in frontend.get("story_beats", []):
            assert str(beat) in html, (case_id, beat)

    print("showcase-frontstage-prototype-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
