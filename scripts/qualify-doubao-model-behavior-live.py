#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from loopx.control_plane.testing.actual_default_model_behavior_portfolio import (
    build_actual_default_model_behavior_scenario_packets,
    run_actual_default_model_behavior_portfolio,
)
from loopx.control_plane.testing.doubao_model_behavior_actor import (
    DoubaoModelBehaviorActor,
    DoubaoOnboardingModelBehaviorActor,
)
from loopx.control_plane.testing.release_commit_qualification import (
    collect_release_source_identity,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the actual-default behavior portfolio against the real Ark "
            "Doubao API and print only its bounded receipt."
        )
    )
    parser.add_argument("--qualification-id", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def main() -> int:
    args = _parser().parse_args()
    source = collect_release_source_identity(args.repo_root)
    if source["git_dirty"]:
        raise RuntimeError(
            "live Doubao qualification requires a clean candidate checkout"
        )
    turn_actor = DoubaoModelBehaviorActor.from_environment(
        timeout_seconds=args.timeout_seconds
    )
    onboarding_actor = DoubaoOnboardingModelBehaviorActor.from_environment(
        timeout_seconds=args.timeout_seconds
    )
    with TemporaryDirectory(prefix="loopx-doubao-live-") as temp_dir:
        packets = build_actual_default_model_behavior_scenario_packets(Path(temp_dir))
        result = run_actual_default_model_behavior_portfolio(
            packets,
            qualification_id=args.qualification_id,
            turn_actor=turn_actor,
            onboarding_actor=onboarding_actor,
        )
    result["source"] = source
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["qualification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
