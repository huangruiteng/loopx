#!/usr/bin/env python3
"""Compute the full tracked-tree inventory; optionally export a local report.

Usage:
  uv run python scripts/generate_semantic_inventory.py             # JSON to stdout, no writes
  uv run python scripts/generate_semantic_inventory.py --output .local/inventory.json
  uv run python scripts/generate_semantic_inventory.py --output .local/inventory.json --check
  uv run python scripts/generate_semantic_inventory.py --report    # advisory consumer ranking
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.semantics.inventory import (  # noqa: E402
    build_inventory,
    consumer_ranking,
    load_sources,
    render_inventory,
)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="write an optional report to this path instead of stdout")
    destination.add_argument("--report", action="store_true", help="print the advisory consumer ranking")
    parser.add_argument("--check", action="store_true", help="compare an explicit --output report without writing")
    parser.add_argument("--top", type=int, default=25, help="rows to print with --report")
    args = parser.parse_args()
    if args.check and args.output is None:
        parser.error("--check requires --output; inventories are no longer committed. "
                     "Run examples/semantic-vocabulary-drift-smoke.py for semantic validation.")

    inventory = build_inventory(ROOT)
    content = render_inventory(inventory)
    if args.report:
        rows = consumer_ranking(inventory, load_sources(ROOT))[: args.top]
        width = max((len(row["name"]) for row in rows), default=0)
        print("external_consumer_modules  values  name  module")
        for row in rows:
            print(f"{row['external_consumer_modules']:>25}  {row['values']:>6}  {row['name']:<{width}}  {row['module']}")
        return 0
    if args.output is None:
        print(content, end="")
        return 0
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != content:
            print(f"stale or missing semantic inventory report: {args.output}; "
                  "rerun with the same --output path without --check", file=sys.stderr)
            return 1
        print(f"semantic inventory report up to date: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"generated semantic inventory report: {args.output}")
    print(json.dumps(inventory["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
