#!/usr/bin/env python3
"""Guard the public showcase animation path against private/live sources."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPIKE_DOC = REPO_ROOT / "docs" / "outreach" / "showcase-animation-skill-spike.md"
SHOWCASE_INDEX = REPO_ROOT / "docs" / "showcases" / "README.md"
CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"

REQUIRED_SPIKE_PHRASES = (
    "20-30 second animated demo",
    "docs/showcases/showcase-catalog.json",
    "must not read live registry state",
    "local status exports",
    "private chats",
    "raw benchmark traces",
    "internal project names",
    "Remotion Agent Skills",
    "HyperFrames",
    "Motion for React",
    "Run `python3 examples/showcase-animation-source-boundary-smoke.py`",
)

FORBIDDEN_SOURCE_PROMOTIONS = (
    "status.frontstage-share.json",
    "status.local.json",
    "registry.global.json",
    ".goal-harness/registry.json",
    ".codex/goals/",
    "ACTIVE_GOAL_STATE.md",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_required_content() -> None:
    spike = read(SPIKE_DOC)
    for phrase in REQUIRED_SPIKE_PHRASES:
        assert phrase in spike, f"{SPIKE_DOC}: missing {phrase!r}"

    showcase_index = read(SHOWCASE_INDEX)
    assert "showcase-animation-skill-spike.md" in showcase_index, SHOWCASE_INDEX
    assert "showcase-catalog.json` as the only case data source" in showcase_index, SHOWCASE_INDEX


def assert_no_live_source_promotion() -> None:
    spike = read(SPIKE_DOC)
    for marker in FORBIDDEN_SOURCE_PROMOTIONS:
        assert marker not in spike, f"{SPIKE_DOC}: live/private source marker {marker!r}"


def assert_catalog_is_frontstage_ready() -> None:
    catalog = json.loads(read(CATALOG))
    assert catalog.get("schema_version") == "goal_harness_showcase_catalog_v0", catalog
    cases = catalog.get("cases")
    assert isinstance(cases, list) and len(cases) >= 4, catalog
    for case in cases:
        assert case.get("id"), case
        assert case.get("headline"), case
        assert case.get("evidence_boundary"), case
        frontend = case.get("frontend_card")
        assert isinstance(frontend, dict), case
        beats = frontend.get("story_beats")
        assert isinstance(beats, list) and len(beats) >= 3, case


def main() -> int:
    assert_required_content()
    assert_no_live_source_promotion()
    assert_catalog_is_frontstage_ready()
    print("showcase-animation-source-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
