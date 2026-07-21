#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.help_surface import render_manpage  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the LoopX manpage from the canonical command catalog."
    )
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="write the generated manpage")
    destination.add_argument(
        "--check",
        type=Path,
        metavar="PATH",
        help="fail if PATH differs from the generated manpage",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rendered = render_manpage()
    if args.check is not None:
        actual = args.check.read_text(encoding="utf-8") if args.check.is_file() else ""
        if actual == rendered:
            return 0
        diff = difflib.unified_diff(
            actual.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile=str(args.check),
            tofile="generated manpage",
        )
        sys.stderr.writelines(diff)
        return 1
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        return 0
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
