#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from loopx.canary.maintainability_ratchet import (  # noqa: E402
    build_control_plane_maintainability_report,
    render_control_plane_maintainability_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report and ratchet control-plane maintainability debt."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Render a compact summary or the complete structured report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_control_plane_maintainability_report(REPOSITORY_ROOT)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_control_plane_maintainability_report(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
