#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_text = str(REPO_ROOT)
if sys.path[0] != repo_root_text:
    sys.path.insert(0, repo_root_text)

from loopx.control_plane.testing.release_commit_qualification import (  # noqa: E402
    collect_release_source_identity,
)
from loopx.control_plane.testing.terminal_settlement_tool_behavior import (  # noqa: E402
    DoubaoTerminalSettlementToolBehaviorActor,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the terminal settlement tool behavior against the real Ark "
            "Doubao API and print only bounded receipts."
        )
    )
    parser.add_argument("--qualification-id", required=True)
    parser.add_argument(
        "--scenario",
        choices=("ordered-settlement", "rejection-reentry"),
        default="ordered-settlement",
        help=(
            "Qualification path: the existing quota settlement chain or the "
            "post-refresh-rejection lifecycle reentry path."
        ),
    )
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.attempts < 1 or args.attempts > 3:
        raise ValueError("attempts must be between 1 and 3")
    source = collect_release_source_identity(args.repo_root)
    if source["git_dirty"]:
        raise RuntimeError(
            "live Doubao qualification requires a clean candidate checkout"
        )
    actor = DoubaoTerminalSettlementToolBehaviorActor.from_environment(
        timeout_seconds=args.timeout_seconds
    )
    receipts: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="loopx-doubao-terminal-settlement-") as temp_dir:
        temp_root = Path(temp_dir)
        for attempt in range(1, args.attempts + 1):
            run_id = f"{args.qualification_id}:r{attempt}"
            run_digest = sha256(run_id.encode("utf-8")).hexdigest()[:16]
            qualify = (
                actor.qualify_reentry
                if args.scenario == "rejection-reentry"
                else actor.qualify
            )
            receipts.append(
                qualify(
                    qualification_id=run_id,
                    fixture_root=temp_root / run_digest,
                )
            )
    passed = all(item.get("qualification_passed") is True for item in receipts)
    result = {
        "schema_version": "terminal_settlement_model_behavior_live_v0",
        "qualification_id": args.qualification_id,
        "scenario": args.scenario,
        "qualification_passed": passed,
        "attempts_required": args.attempts,
        "attempts_completed": len(receipts),
        "provider_call_count": sum(
            int(item.get("provider_call_count") or item.get("tool_call_count") or 0)
            for item in receipts
        ),
        "receipts": receipts,
        "source": source,
        "boundary": {
            "raw_prompts_persisted": False,
            "raw_provider_responses_persisted": False,
            "raw_commands_persisted": False,
            "external_writes_executed": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
