"""The inbox renderer must not point agents at a nonexistent review digest."""

from loopx.cli_commands.lark_inbox import _render


def _payload(guidance: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "enabled": True,
        "pending_count": 0,
        "write_performed": False,
        "items": [],
        "outbound_guidance": guidance,
    }


def test_review_required_renders_the_digest_hint():
    rendered = _render(
        _payload(
            {
                "status": "required_guidance_missing",
                "agent_review_required": True,
                "guidance": [{"content_summary": "prefer short confirmations"}],
                "review_digest": "sha256:abc123",
            }
        )
    )
    assert "--reviewed-guidance-digest sha256:abc123" in rendered
    assert "guidance: prefer short confirmations" in rendered


def test_configuration_error_renders_repair_hint_instead_of_none_digest():
    rendered = _render(
        _payload(
            {
                "status": "configuration_error",
                "reason_code": "scope_mismatch",
                "guidance": [],
                "agent_review_required": True,
                "recommended_action": (
                    "Repair the enabled Reward Memory configuration and verify it with "
                    "reward-memory experiment-status before retrying."
                ),
            }
        )
    )
    assert "None" not in rendered
    assert "--reviewed-guidance-digest" not in rendered
    assert "Repair the enabled Reward Memory configuration" in rendered
