"""Per-job qualification: an intentional exemption is not an accidental skip."""

from __future__ import annotations

import argparse
import json
import os
from impact_plan import Change, OUTPUTS, candidate, job_flags, plan, write_plan

JOB_OUTPUT = {
    "checks": "core_tests",
    "pytest": "python_tests",
    "node-minimum-compatibility": "core_tests",
    "stage2c-correctness-e2e": "stage2c_tests",
    "windows-powershell": "python_tests",
    "presentation": "presentation_tests",
}
CORE_JOBS = tuple(JOB_OUTPUT)


def requires_core_tests(paths: list[str]) -> bool:
    return candidate([Change("M", path) for path in paths])[0] != "docs"


def verify(needs: object) -> None:
    if not isinstance(needs, dict) or set(needs) != {"changes", *CORE_JOBS}:
        raise ValueError("missing or unexpected merge-gate dependencies")
    changes = needs["changes"]
    if not isinstance(changes, dict) or changes.get("result") != "success":
        raise ValueError("change classification did not succeed")
    outputs = changes.get("outputs")
    if not isinstance(outputs, dict) or any(outputs.get(key) not in {"true", "false"} for key in OUTPUTS):
        raise ValueError("missing or invalid job classification")
    kind = outputs.get("change_kind")
    expected = job_flags(kind, presentation=kind == "full" and outputs["presentation_tests"] == "true")
    if any(outputs[key] != str(value).lower() for key, value in expected.items()):
        raise ValueError("contradictory job exemptions")
    for name, output in JOB_OUTPUT.items():
        required = "success" if outputs[output] == "true" else "skipped"
        job = needs[name]
        if not isinstance(job, dict) or job.get("result") != required:
            raise ValueError(f"{name} must be {required}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify")
    classify.add_argument("--base", required=True)
    classify.add_argument("--head", required=True)
    classify.add_argument("--plan")
    classify.add_argument("--non-pr", action="store_true")
    classify.add_argument("--force-full", action="store_true")
    sub.add_parser("verify")
    args = parser.parse_args()
    if args.command == "classify":
        packet = plan(args.base, args.head, pull_request=not args.non_pr, force_full=args.force_full)
        if args.plan:
            write_plan(packet, args.plan)
            print(f"change_kind={packet['change_kind']}")
            for key in OUTPUTS:
                print(f"{key}={str(packet[key]).lower()}")
        else:
            print(f"core_tests={str(packet['core_tests']).lower()}")
    else:
        verify(json.loads(os.environ["NEEDS_JSON"]))
        print("merge-gate: qualification complete")


if __name__ == "__main__":
    main()
