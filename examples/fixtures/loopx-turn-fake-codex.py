#!/usr/bin/env python3
"""Deterministic Codex CLI fixture for the public LoopX Turn E2E contract."""

import json
import pathlib
import re
import sys


MARKER_NAME = "docs/turn-e2e-marker.txt"
MARKER_PREFIX = "loopx-turn-real-e2e-step-"

args = sys.argv[1:]
prompt = sys.stdin.read()
turn_key = re.search(r'"turn_key":"([^"]+)"', prompt).group(1)
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
advisor = "loopx_turn_advisor_v0" in schema_path.read_text(encoding="utf-8")
guided_executor = not advisor and "A read-only advisor produced" in prompt
print(
    json.dumps(
        {
            "type": "thread.started",
            "thread_id": "advisor-session-fixture" if advisor else "session-fixture-0001",
        }
    ),
    flush=True,
)
print(
    json.dumps(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 40 if advisor else 70 if guided_executor else 120,
                "cached_input_tokens": 5 if advisor else 10 if guided_executor else 20,
                "output_tokens": 8 if advisor else 20 if guided_executor else 30,
                "reasoning_output_tokens": 3 if advisor else 5 if guided_executor else 10,
                "total_tokens": 48 if advisor else 90 if guided_executor else 150,
            },
        }
    ),
    flush=True,
)
if advisor:
    output_path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_turn_advisor_v0",
                "turn_key": turn_key,
                "summary": "Keep the marker update bounded to one step.",
                "recommendations": ["Inspect the current marker before writing."],
                "risks": ["Do not advance more than one step."],
                "validation_focus": ["Verify the exact next marker value."],
            }
        ),
        encoding="utf-8",
    )
    raise SystemExit(0)

marker = pathlib.Path(MARKER_NAME)
turn_number = 1
if marker.is_file():
    current = marker.read_text(encoding="utf-8").strip()
    match = re.fullmatch(re.escape(MARKER_PREFIX) + r"([1-9][0-9]*)", current)
    if match is None:
        raise SystemExit("unexpected marker value")
    turn_number = int(match.group(1)) + 1
marker.write_text(MARKER_PREFIX + str(turn_number), encoding="utf-8")
output_path.write_text(
    json.dumps(
        {
            "schema_version": "loopx_turn_result_v0",
            "turn_key": turn_key,
            "result_kind": "validated_progress",
            "completed_phases": ["host_execute", "typed_result"],
            "classification": f"real_cli_e2e_step_{turn_number}_progress",
            "recommended_action": f"Advance the marker to step {turn_number + 1}.",
            "next_action": f"Run the independently validated step {turn_number + 1} Turn.",
            "delivery_batch_scale": "single_surface",
            "delivery_outcome": "outcome_progress",
            "vision_unchanged_reason": "The fixture objective remains unchanged.",
            "summary": f"The isolated public marker reached step {turn_number}.",
        }
    ),
    encoding="utf-8",
)
