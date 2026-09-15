#!/usr/bin/env python3
"""Generate or check the repository-wide semantic inventory.

Usage:
  uv run python scripts/generate_semantic_inventory.py            # rewrite inventory_v0.json
  uv run python scripts/generate_semantic_inventory.py --check    # exit 1 when the file is stale
  uv run python scripts/generate_semantic_inventory.py --report   # print advisory consumer ranking
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

INVENTORY_PATH = ROOT / "loopx" / "semantics" / "inventory_v0.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail when the committed inventory is stale")
    parser.add_argument("--report", action="store_true", help="print the advisory consumer ranking")
    parser.add_argument("--top", type=int, default=25, help="rows to print with --report")
    args = parser.parse_args()

    inventory = build_inventory(ROOT)
    content = render_inventory(inventory)
    if args.report:
        rows = consumer_ranking(inventory, load_sources(ROOT))[: args.top]
        width = max(len(row["name"]) for row in rows)
        print("external_consumer_modules  values  name  module")
        for row in rows:
            print(f"{row['external_consumer_modules']:>25}  {row['values']:>6}  {row['name']:<{width}}  {row['module']}")
        return 0
    current = INVENTORY_PATH.read_text(encoding="utf-8") if INVENTORY_PATH.exists() else None
    if current == content:
        print(f"semantic inventory up to date: {INVENTORY_PATH.relative_to(ROOT)}")
        return 0
    if args.check:
        print(
            f"stale semantic inventory: {INVENTORY_PATH.relative_to(ROOT)}; "
            "from the repository root run uv run python scripts/generate_semantic_inventory.py and commit the result",
            file=sys.stderr,
        )
        return 1
    INVENTORY_PATH.write_text(content, encoding="utf-8")
    print(f"generated {INVENTORY_PATH.relative_to(ROOT)}")
    print(json.dumps(inventory["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
