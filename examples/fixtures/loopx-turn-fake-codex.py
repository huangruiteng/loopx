#!/usr/bin/env python3
"""Deterministic Codex CLI fixture for the public LoopX Turn E2E contract."""

import json
import pathlib
import re
import sys


MARKER_NAME = "docs/turn-e2e-marker.txt"
MARKER_PREFIX = "loopx-turn-real-e2e-step-"
args = sys.argv[1:]
if args == ["debug", "models"]:
    print(
        json.dumps(
            {
                "models": [
                    {"slug": "gpt-5.6-sol"},
                    {"slug": "gpt-5.6-luna"},
                ]
            }
        )
    )
    raise SystemExit(0)

CASE_ID = pathlib.Path(__file__).with_name("case-id.txt").read_text(encoding="utf-8").strip()
prompt = sys.stdin.read()
turn_key = re.search(r'"turn_key":"([^"]+)"', prompt).group(1)
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
schema = schema_path.read_text(encoding="utf-8")
checkpoint = "loopx_turn_complexity_checkpoint_v0" in schema
advisor = "loopx_turn_advisor_v0" in schema
guided_executor = not advisor and "A read-only advisor produced" in prompt
turn_number = 1
if CASE_ID == "marker-step":
    current_marker = pathlib.Path(MARKER_NAME)
    if current_marker.is_file():
        current = current_marker.read_text(encoding="utf-8").strip()
        match = re.fullmatch(re.escape(MARKER_PREFIX) + r"([1-9][0-9]*)", current)
        if match is None:
            raise SystemExit("unexpected marker value")
        turn_number = int(match.group(1)) + 1
if advisor:
    usage = {
        "input_tokens": 18,
        "cached_input_tokens": 3,
        "output_tokens": 4,
        "reasoning_output_tokens": 2,
        "total_tokens": 22,
    }
elif checkpoint:
    usage = {
        "input_tokens": 35 * (turn_number - 1) + 20,
        "cached_input_tokens": 5 * (turn_number - 1) + 4,
        "output_tokens": 10 * (turn_number - 1) + 5,
        "reasoning_output_tokens": 3 * (turn_number - 1) + 2,
        "total_tokens": 45 * (turn_number - 1) + 25,
    }
elif guided_executor:
    usage = {
        "input_tokens": 35 * turn_number,
        "cached_input_tokens": 5 * turn_number,
        "output_tokens": 10 * turn_number,
        "reasoning_output_tokens": 3 * turn_number,
        "total_tokens": 45 * turn_number,
    }
else:
    usage = {
        "input_tokens": 120 * turn_number,
        "cached_input_tokens": 20 * turn_number,
        "output_tokens": 30 * turn_number,
        "reasoning_output_tokens": 10 * turn_number,
        "total_tokens": 150 * turn_number,
    }
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
            "usage": usage,
        }
    ),
    flush=True,
)
if checkpoint:
    output_path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_turn_complexity_checkpoint_v0",
                "turn_key": turn_key,
                "complexity": "complex",
                "signals": ["invariant_risk"],
                "evidence_summary": "The fixture has an independently validated postcondition that must be preserved.",
                "relevant_paths": [MARKER_NAME],
                "open_questions": ["Which exact next value preserves the one-step invariant?"],
            }
        ),
        encoding="utf-8",
    )
    raise SystemExit(0)
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

print(
    json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "apply deterministic fixture update",
            },
        }
    ),
    flush=True,
)
if CASE_ID == "marker-step":
    marker = pathlib.Path(MARKER_NAME)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(MARKER_PREFIX + str(turn_number), encoding="utf-8")
elif CASE_ID == "arithmetic-fix":
    pathlib.Path("calculator.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
elif CASE_ID == "json-normalization":
    pathlib.Path("config/settings.json").write_text(
        '{"enabled":true,"retries":3}\n', encoding="utf-8"
    )
elif CASE_ID == "multi-file-docs":
    pathlib.Path("docs/guide.md").write_text(
        "# Guide\n\nStatus: stable\n", encoding="utf-8"
    )
    pathlib.Path("docs/index.md").write_text(
        "# Index\n\n- [Guide](guide.md) — stable\n", encoding="utf-8"
    )
elif CASE_ID == "bounded-refactor":
    pathlib.Path("names.py").write_text(
        "def _slug(value):\n"
        "    return value.strip().lower().replace(\" \", \"-\")\n\n"
        "def user_slug(value):\n"
        "    return _slug(value)\n\n"
        "def project_slug(value):\n"
        "    return _slug(value)\n",
        encoding="utf-8",
    )
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
