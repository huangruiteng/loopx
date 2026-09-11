"""Conservative PR classification and fail-closed core CI aggregation."""

from __future__ import annotations

import argparse
import json
import os
from impact_plan import Change, candidate, plan, write_plan

CORE_JOBS = (
    "pytest",
    "node-minimum-compatibility",
    "stage2c-correctness-e2e",
    "windows-powershell",
)


def requires_core_tests(paths: list[str]) -> bool:
    # Unknown paths, executable documentation, policy and runtime prompts run CI.
    # Disable rename detection at the caller so both old and new paths count.
    if not paths:
        return True
    return candidate([Change("M", path) for path in paths])[0] != "docs"


def verify(needs: object, *, shadow: bool = False) -> None:
    expected_jobs = {"changes", *CORE_JOBS, *(["impact-shadow"] if shadow else [])}
    if not isinstance(needs, dict) or set(needs) != expected_jobs:
        raise ValueError("missing or unexpected merge-gate dependencies")
    changes = needs["changes"]
    if not isinstance(changes, dict) or changes.get("result") != "success":
        raise ValueError("change classification did not succeed")
    outputs = changes.get("outputs")
    classification = outputs.get("core_tests") if isinstance(outputs, dict) else None
    if classification not in ("true", "false"):
        raise ValueError("missing or invalid core-test classification")
    expected = "success" if classification == "true" else "skipped"
    for name in CORE_JOBS:
        job = needs[name]
        if not isinstance(job, dict) or job.get("result") != expected:
            raise ValueError(f"{name} must be {expected}")
    if shadow:
        profile = outputs.get("impact_profile")
        if profile not in {"docs", "full", "vision"} or (profile == "docs") != (classification == "false"):
            raise ValueError("missing or contradictory impact profile")
        shadow_profile = outputs.get("shadow_profile")
        if shadow_profile not in {"vision", "none"} or (profile == "docs" and shadow_profile != "none") or (profile == "vision" and shadow_profile != "vision"):
            raise ValueError("missing or contradictory shadow profile")
        expected_shadow = "success" if shadow_profile == "vision" else "skipped"
        job = needs["impact-shadow"]
        if not isinstance(job, dict) or job.get("result") != expected_shadow:
            raise ValueError(f"impact-shadow must be {expected_shadow}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify")
    classify.add_argument("--base", required=True)
    classify.add_argument("--head", required=True)
    classify.add_argument("--plan", help="write the non-authoritative impact plan")
    classify.add_argument("--non-pr", action="store_true")
    sub.add_parser("verify").add_argument("--shadow", action="store_true")
    args = parser.parse_args()
    if args.command == "classify":
        packet = plan(args.base, args.head, pull_request=not args.non_pr)
        if args.plan:
            write_plan(packet, args.plan)
        print(f"core_tests={str(packet['candidate_profile'] != 'docs').lower()}")
        if args.plan:
            print(f"impact_profile={packet['candidate_profile']}")
            print(f"shadow_profile={packet['shadow_profile']}")
    else:
        verify(json.loads(os.environ["NEEDS_JSON"]), shadow=args.shadow)
        print("merge-gate: qualification complete")


if __name__ == "__main__":
    main()
