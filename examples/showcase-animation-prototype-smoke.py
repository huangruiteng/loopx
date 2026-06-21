#!/usr/bin/env python3
"""Smoke-test the public-safe showcase animation prototype artifact."""

from __future__ import annotations

import html as html_lib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STORYBOARD = REPO_ROOT / "docs" / "showcases" / "showcase-animation-storyboard.json"
CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"
PROTOTYPE = REPO_ROOT / "examples" / "showcase-animation-prototype.py"
SHOWCASE_README = REPO_ROOT / "docs" / "showcases" / "README.md"
COMMITTED_ARTIFACT = REPO_ROOT / "docs" / "showcases" / "showcase-animation-prototype.html"
PRIVATE_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("lark", "office.com"),
        ("internal", "-api-drive"),
        ("bytedance.com", "/wiki"),
        ("/", "Users/"),
        (".codex", "/loopx"),
        ("BEGIN", " PRIVATE ", "KEY"),
        ("Author", "ization:"),
        ("to", "ken="),
        ("pass", "word="),
        ("registry", ".global.json"),
        ("ACTIVE", "_GOAL_STATE.md"),
    )
)


def escaped(value: object) -> str:
    return html_lib.escape(str(value), quote=True)


def main() -> int:
    storyboard = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    scenes = storyboard["scenes"]
    cases = catalog["cases"]
    duration = scenes[-1]["time_seconds"][1]

    with tempfile.TemporaryDirectory(prefix="loopx-showcase-animation-") as tmp:
        output = Path(tmp) / "showcase-animation.html"
        result = subprocess.run(
            [sys.executable, str(PROTOTYPE), "--output", str(output)],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        assert str(output) in result.stdout, result.stdout
        rendered = output.read_text(encoding="utf-8")

    committed = COMMITTED_ARTIFACT.read_text(encoding="utf-8")
    assert committed == rendered, "committed prototype must match generated output"

    for marker in PRIVATE_MARKERS:
        assert marker not in rendered, marker

    for required in (
        '<section class="stage" aria-label="30 second storyboard prototype">',
        'data-source-storyboard="docs/showcases/showcase-animation-storyboard.json"',
        'data-source-catalog="docs/showcases/showcase-catalog.json"',
        f'data-duration-seconds="{duration}"',
        f"{duration}s loop",
        "No live registry, local status export, transcript, or private active state.",
        "docs/showcases/showcase-animation-storyboard.json",
        "docs/showcases/showcase-catalog.json",
        "Remotion Agent Skills / HyperFrames",
        "@keyframes progress",
    ):
        assert required in rendered, required

    assert storyboard["duration_seconds_target"] == {"min": 20, "max": 30}, storyboard
    assert 20 <= duration <= 30, duration
    assert rendered.count('class="scene scene--') == len(scenes), rendered
    assert rendered.count("@keyframes scene-") == len(scenes), rendered
    assert rendered.count('class="timeline__segment"') == len(scenes), rendered

    for scene in scenes:
        scene_id = str(scene["id"])
        start, end = scene["time_seconds"]
        assert f'data-scene-id="{escaped(scene_id)}"' in rendered, scene_id
        assert f'data-start-seconds="{start}"' in rendered, scene_id
        assert f'data-end-seconds="{end}"' in rendered, scene_id
        for field in ("copy", "visual", "motion_notes"):
            assert escaped(scene[field]) in rendered, (scene_id, field)
        for case_id in scene["source_case_ids"]:
            assert f'data-source-case-id="{escaped(case_id)}"' in rendered, (scene_id, case_id)

    for case in cases:
        case_id = str(case["id"])
        assert case_id in rendered, case_id
        assert escaped(case["title"]) in rendered, case_id
        assert escaped(case["headline"]) in rendered, case_id
        frontend = case["frontend_card"]
        for badge in frontend.get("badges", [])[:3]:
            assert escaped(badge) in rendered, (case_id, badge)

    readme = SHOWCASE_README.read_text(encoding="utf-8")
    assert "showcase-animation-prototype.py" in readme, SHOWCASE_README
    assert "showcase-animation-prototype.html" in readme, SHOWCASE_README
    assert "showcase-animation-prototype-smoke.py" in readme, SHOWCASE_README

    print("showcase-animation-prototype-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
