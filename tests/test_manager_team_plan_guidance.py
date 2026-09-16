"""The steward's shipped guidance owns the one-sentence team plan contract."""

from __future__ import annotations

from loopx.chat_manager import manager_skill_text


def test_manager_guidance_orders_one_team_preview_before_any_effect() -> None:
    """A team request is answered with one preview, never with silent creates."""

    text = manager_skill_text()

    ordered = [
        "the lanes and the Agent each one runs on",
        "the first bounded Todo per lane",
        "quota or cadence envelope",
        "acceptance signal",
        "stop condition",
    ]
    positions = [text.index(marker) for marker in ordered]
    assert positions == sorted(positions), ordered

    # The preview gates every effect, and the effects keep their canonical owners.
    assert "proposal, never an effect" in text
    assert "until the owner confirms that exact preview" in text
    # A plan is admitted only for the Goal it names, and the confirmation is the
    # product surface's typed action rather than something the steward performs.
    assert "Name the exact Goal the plan\nstaffs" in text
    assert "dropped instead of shown" in text
    assert "typed team-plan action from the product\nsurface" in text
    # A lane may not be claimed to exist before its apply receipt returns.
    assert "before the\napply receipt returns" in text
    assert "the plan went stale" in text
    assert "Agent\nregistration, Todo creation, quota or goal policy" in text
    assert "charge quota for the preview itself" in text
    # An unstaffable lane is named as a gap rather than invented.
    assert "as a gap, with the missing registration or grant" in text
    assert "inventing a lane, an Agent, or a capability" in text


def test_the_owner_visible_failure_names_the_executor_that_refused() -> None:
    """A host gate is the executor's refusal, not a defect in the manager."""

    from loopx.extensions.lark.manager_context import manager_failure_reply

    class _Refused(RuntimeError):
        error_code = "host_gate"

    code, text = manager_failure_reply(_Refused("upstream refused"))

    assert code == "host_gate"
    assert "上游执行器" in text
    assert "管家处理失败" not in text
    # An unmapped code still falls back to the bounded generic label.
    class _Unknown(RuntimeError):
        error_code = "some_future_code"

    assert manager_failure_reply(_Unknown("x"))[0] == "processing_failed"
