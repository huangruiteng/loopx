from loopx.control_plane.todos.update_intent import (
    build_canonical_update_intent,
    canonical_update_is_supported,
)


def test_update_intent_keeps_explicit_clears_and_empty_scalars() -> None:
    intent = build_canonical_update_intent(
        reason="",
        required_capabilities=[],
        clear_claim=True,
        clear_global_gate=True,
    )

    assert intent == {
        "reason": "",
        "required_capabilities": [],
        "clear_global_gate": True,
        "clear_claim": True,
    }


def test_update_route_promotes_declarative_decision_metadata() -> None:
    supported = build_canonical_update_intent(
        action_kind="publish",
        task_domain="delivery",
        task_repository="git:github.com/example/project",
        required_write_scopes=["src/**"],
    )
    assert canonical_update_is_supported(
        text=None,
        note=None,
        intent=supported,
        monitor_metadata=None,
        authority_reason=None,
        status=None,
    )

    # Declarative scope metadata now crosses the same typed planning
    # transaction; terminal outcomes remain on their effect-owned path.
    governance = build_canonical_update_intent(
        decision_scope={"kind": "write_scope", "granularity": "action", "scope_key": "release"},
    )
    assert canonical_update_is_supported(
        text=None,
        note=None,
        intent=governance,
        monitor_metadata=None,
        authority_reason=None,
        status=None,
    )


def test_terminal_and_monitor_updates_stay_off_canonical_route() -> None:
    intent = build_canonical_update_intent(reason="ordinary")
    assert not canonical_update_is_supported(
        text=None,
        note=None,
        intent=intent,
        monitor_metadata={"material_change": True},
        authority_reason=None,
        status=None,
    )
    assert not canonical_update_is_supported(
        text=None,
        note=None,
        intent=intent,
        monitor_metadata=None,
        authority_reason=None,
        status="done",
    )
    assert not canonical_update_is_supported(
        text=None,
        note="   ",
        intent={},
        monitor_metadata=None,
        authority_reason=None,
        status=None,
    )
