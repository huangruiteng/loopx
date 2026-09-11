#!/usr/bin/env python3
"""Explicit release opt-in; never called by default PR CI or canaries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loopx.control_plane.testing.doubao_model_behavior_actor import (  # noqa: E402
    DOUBAO_SEED_EVOLVING_MODEL, _direct_ark_transport,
)
from loopx.control_plane.testing.host_prompt_behavior import run_probe  # noqa: E402
from loopx.control_plane.testing.model_tool_behavior import DoubaoExecToolClient  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-live", action="store_true")
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=2)
    args = parser.parse_args(argv)
    if not args.release_live:
        print(json.dumps({"status": "skipped", "reason": "release_opt_in_required", "provider_call_count": 0}))
        return 0
    key = os.environ.get("ARK_API_KEY", "")
    if not key:
        print(json.dumps({"status": "skipped", "reason": "provider_credential_unavailable", "provider_call_count": 0}))
        return 0
    client = DoubaoExecToolClient(api_key=key, model=DOUBAO_SEED_EVOLVING_MODEL,
        timeout_seconds=90, transport=_direct_ark_transport)
    try:
        report = run_probe(client, repeats=args.repeats)
    except Exception:
        # Never publish a transport exception, raw response or credential.
        print(json.dumps({"status": "failed", "reason": "probe_execution_failed"}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["qualification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
