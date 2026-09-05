"""Typed word-level raw-material classification for the session-runtime projection."""

from __future__ import annotations

import pytest

from loopx.control_plane.runtime.session_runtime import (
    compact_session_runtime_readonly_projection,
)
from loopx.session_runtime import (
    KeyState,
    RawMaterialCategory,
    build_session_runtime_readonly_projection,
    classify_session_runtime_key,
)


@pytest.mark.parametrize(
    "key",
    [
        # projection inputs
        "kind", "status", "actor", "summary", "recommended_action",
        "created_at", "session_id", "artifact_id",
        # pointers and counts that merely contain a raw-looking word
        "trace_id", "message_id", "catalog_id", "dialog_id", "login_at", "log_count",
        "conversation_id",
        # `message` is an exact raw key, not a raw word: its pointer/count neighbours stay compact
        "message_count", "message_ref",
        # usage metrics
        "token_count", "tokens_used", "max_tokens", "input_tokens", "output_tokens",
        "prompt_tokens", "prompt_token_count", "completion_tokens",
    ],
)
def test_compact_keys(key: str) -> None:
    assert classify_session_runtime_key(key).state is KeyState.COMPACT


@pytest.mark.parametrize(
    "key", ["logical_clock", "backlog", "changelog", "drawer", "content_type", "message_text", ""]
)
def test_unclassified_keys_are_neither_compact_nor_raw(key: str) -> None:
    assert classify_session_runtime_key(key) == (KeyState.UNCLASSIFIED, None)


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("token", RawMaterialCategory.CREDENTIAL),
        ("access_token", RawMaterialCategory.CREDENTIAL),
        ("auth_token", RawMaterialCategory.CREDENTIAL),
        ("api_token", RawMaterialCategory.CREDENTIAL),
        ("bearer_token", RawMaterialCategory.CREDENTIAL),
        ("refresh_token", RawMaterialCategory.CREDENTIAL),
        ("id_token", RawMaterialCategory.CREDENTIAL),
        ("accessToken", RawMaterialCategory.CREDENTIAL),
        ("api_key", RawMaterialCategory.CREDENTIAL),
        ("password", RawMaterialCategory.CREDENTIAL),
        ("secret", RawMaterialCategory.CREDENTIAL),
        ("credential_hint", RawMaterialCategory.CREDENTIAL),
        ("raw_transcript", RawMaterialCategory.TRANSCRIPT),
        ("transcript_path", RawMaterialCategory.TRANSCRIPT),
        ("messages", RawMaterialCategory.TRANSCRIPT),
        ("prompt", RawMaterialCategory.TRANSCRIPT),
        ("content", RawMaterialCategory.TRANSCRIPT),
        ("body", RawMaterialCategory.TRANSCRIPT),
        ("message", RawMaterialCategory.TRANSCRIPT),
        ("log", RawMaterialCategory.LOG),
        ("logs", RawMaterialCategory.LOG),
        ("log_path", RawMaterialCategory.LOG),
        ("raw_log", RawMaterialCategory.LOG),
        ("trace", RawMaterialCategory.LOG),
        ("traces", RawMaterialCategory.LOG),
        ("stack_trace", RawMaterialCategory.LOG),
        ("trace_path", RawMaterialCategory.LOG),
        ("raw_trace", RawMaterialCategory.LOG),
        ("local_path", RawMaterialCategory.LOCAL_PATH),
        ("file_path", RawMaterialCategory.LOCAL_PATH),
        ("output_text", RawMaterialCategory.RAW_OUTPUT),
        ("stdout_tail", RawMaterialCategory.RAW_OUTPUT),
        ("stderr_tail", RawMaterialCategory.RAW_OUTPUT),
        ("diff", RawMaterialCategory.RAW_OUTPUT),
        ("patch", RawMaterialCategory.RAW_OUTPUT),
    ],
)
def test_raw_material_keys_carry_a_typed_category(key: str, category: RawMaterialCategory) -> None:
    assert classify_session_runtime_key(key) == (KeyState.RAW_MATERIAL, category)


def test_substrings_never_match() -> None:
    # Every hint of the retired substring denylist embedded in a longer word.
    for key in ("catalog", "dialogue", "backlog", "tokenizer", "tracer", "drawn", "rawhide"):
        assert classify_session_runtime_key(key).state is not KeyState.RAW_MATERIAL, key


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("tokens_password", RawMaterialCategory.CREDENTIAL),
        ("tokens_transcript", RawMaterialCategory.TRANSCRIPT),
        ("raw_tokens", RawMaterialCategory.RAW_OUTPUT),
    ],
)
def test_raw_words_outrank_the_tokens_metric_rule(
    key: str,
    category: RawMaterialCategory,
) -> None:
    assert classify_session_runtime_key(key) == (KeyState.RAW_MATERIAL, category)


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("secret_id", RawMaterialCategory.CREDENTIAL),
        ("password_id", RawMaterialCategory.CREDENTIAL),
        ("transcript_id", RawMaterialCategory.TRANSCRIPT),
        ("raw_id", RawMaterialCategory.RAW_OUTPUT),
        ("stdout_id", RawMaterialCategory.RAW_OUTPUT),
        ("api_key_id", RawMaterialCategory.CREDENTIAL),
        ("access_token_ref", RawMaterialCategory.CREDENTIAL),
        ("tool_result_ref", RawMaterialCategory.RAW_OUTPUT),
        # neighbours of the explicit safe collisions stay fail-closed
        ("prompt_id", RawMaterialCategory.TRANSCRIPT),
        ("prompt_text_tokens", RawMaterialCategory.TRANSCRIPT),
        ("conversation_ref", RawMaterialCategory.TRANSCRIPT),
        ("conversation_log_count", RawMaterialCategory.TRANSCRIPT),
        ("messages_count", RawMaterialCategory.TRANSCRIPT),
    ],
)
def test_raw_evidence_outranks_generic_pointer_suffix(
    key: str,
    category: RawMaterialCategory,
) -> None:
    assert classify_session_runtime_key(key) == (KeyState.RAW_MATERIAL, category)


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("secret_id", RawMaterialCategory.CREDENTIAL),
        ("api_key_id", RawMaterialCategory.CREDENTIAL),
        ("transcript_id", RawMaterialCategory.TRANSCRIPT),
        ("raw_id", RawMaterialCategory.RAW_OUTPUT),
    ],
)
def test_pointer_shaped_raw_key_blocks_projection_without_copying_value(
    key: str,
    category: RawMaterialCategory,
) -> None:
    marker = f"RAW_POINTER_MARKER_{key}"
    payload = build_session_runtime_readonly_projection(
        goal_id="g",
        sessions=[
            {
                "session_id": "s",
                "next_action": "advance",
                key: marker,
            }
        ],
    )

    assert payload["boundary"]["raw_material_detected"] is True
    assert payload["boundary"]["raw_material_key_names"] == [key]
    assert payload["boundary"]["raw_material_categories"] == [category.value]
    assert payload["first_screen"]["agent_can_continue"] is False
    assert payload["work_lane_contract"]["must_attempt_work"] is False
    assert marker not in repr(payload)


def test_message_material_is_flagged_and_never_copied_to_first_screen() -> None:
    marker = "RAW_TRANSCRIPT_MARKER full conversation material"
    payload = build_session_runtime_readonly_projection(
        goal_id="g",
        events=[
            {
                "event_id": "e1",
                "kind": "blocker",
                "status": "blocked",
                "message": marker,
            }
        ],
    )
    assert payload["boundary"]["raw_material_detected"] is True
    assert payload["boundary"]["raw_material_key_names"] == ["message"]
    assert payload["boundary"]["raw_material_categories"] == ["transcript"]
    assert marker not in repr(payload)
    assert payload["first_screen"]["latest_blocker"] is None


def test_unclassified_keys_are_reported_but_do_not_block() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="g",
        sessions=[{"session_id": "s", "next_action": "advance", "backlog": "x", "drawer": "y"}],
    )
    assert payload["boundary"]["raw_material_detected"] is False
    assert payload["boundary"]["unclassified_key_names"] == ["backlog", "drawer"]
    assert payload["first_screen"]["agent_can_continue"] is True
    assert payload["work_lane_contract"]["must_attempt_work"] is True


def test_unclassified_key_report_is_bounded() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="g",
        sessions=[{f"opaque{index:03d}": index for index in range(40)}],
    )
    assert len(payload["boundary"]["unclassified_key_names"]) == 24


def test_compaction_keeps_typed_boundary_fields_bounded() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="g",
        sessions=[
            {
                "session_id": "s",
                "api_key": "k",
                "raw_transcript": "t",
                "backlog": "b",
                **{f"opaque{index:02d}": index for index in range(12)},
            }
        ],
    )
    compact = compact_session_runtime_readonly_projection(payload)
    assert compact is not None
    boundary = compact["boundary"]
    assert boundary["raw_material_key_names"] == ["api_key", "raw_transcript"]
    assert boundary["raw_material_categories"] == ["credential", "transcript"]
    assert len(boundary["unclassified_key_names"]) == 8
