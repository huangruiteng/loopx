#!/usr/bin/env python3
"""Emit a public-safe SkillsBench verifier dependency prewarm plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark_adapters.skillsbench import (  # noqa: E402
    SKILLSBENCH_DEFAULT_DATASET,
    build_skillsbench_verifier_dependency_prewarm_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan the minimal SkillsBench verifier dependency prewarm layer "
            "before claiming no-upload oracle sanity or case readiness."
        )
    )
    parser.add_argument("--dataset", default=SKILLSBENCH_DEFAULT_DATASET)
    parser.add_argument("--task-id", default="hello-world")
    parser.add_argument(
        "--patch-scope",
        default="temporary_task_copy",
        choices=("temporary_task_copy", "wrapper_layer", "derived_sandbox_image"),
    )
    parser.add_argument(
        "--allow-upload",
        action="store_true",
        help="Preview an invalid plan with upload enabled; strict mode will fail.",
    )
    parser.add_argument(
        "--allow-submit",
        action="store_true",
        help="Preview an invalid plan with submit enabled; strict mode will fail.",
    )
    parser.add_argument(
        "--skip-oracle-sanity",
        action="store_true",
        help="Preview an invalid plan that skips the oracle sanity gate.",
    )
    parser.add_argument("--known-blocker", action="append", default=[])
    parser.add_argument("--output-json")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = build_skillsbench_verifier_dependency_prewarm_plan(
        dataset=args.dataset,
        task_id=args.task_id,
        patch_scope=args.patch_scope,
        no_upload=not args.allow_upload,
        submit_enabled=bool(args.allow_submit),
        oracle_sanity_required=not args.skip_oracle_sanity,
        known_blockers=args.known_blocker,
    )
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if args.strict and not payload["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
