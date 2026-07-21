#!/usr/bin/env python3
"""Independent validators for public LoopX Turn benchmark fixtures."""

from __future__ import annotations

import ast
import json
import pathlib
import sys


json.load(sys.stdin)
case_id = sys.argv[1]
expected_marker = sys.argv[2] if len(sys.argv) > 2 else ""


def read(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8")


valid = False
if case_id == "marker-step":
    path = pathlib.Path("docs/turn-e2e-marker.txt")
    valid = path.is_file() and read(str(path)).strip() == expected_marker
elif case_id == "arithmetic-fix":
    namespace: dict[str, object] = {}
    exec(compile(read("calculator.py"), "calculator.py", "exec"), namespace)
    add = namespace.get("add")
    valid = callable(add) and add(2, 3) == 5 and add(-1, 1) == 0
elif case_id == "json-normalization":
    value = json.loads(read("config/settings.json"))
    valid = value == {"enabled": True, "retries": 3}
elif case_id == "multi-file-docs":
    guide = read("docs/guide.md")
    index = read("docs/index.md")
    valid = (
        "# Guide" in guide
        and "Status: stable" in guide
        and "draft" not in guide.lower()
        and "[Guide](guide.md)" in index
        and "stable" in index.lower()
        and "draft" not in index.lower()
    )
elif case_id == "bounded-refactor":
    source = read("names.py")
    namespace = {}
    exec(compile(source, "names.py", "exec"), namespace)
    tree = ast.parse(source)
    functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    valid = (
        functions == {"_slug", "user_slug", "project_slug"}
        and namespace["user_slug"](" Alice Smith ") == "alice-smith"
        and namespace["project_slug"](" Loop X ") == "loop-x"
        and source.count('.strip().lower().replace(" ", "-")') == 1
    )

raise SystemExit(0 if valid else 9)
