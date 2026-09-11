"""Return a worker's audience-ready conclusion through the original Lark inbox."""

from __future__ import annotations

from .goal_channel_contracts import bindings_for_goal
from .goal_channel_targets import goal_channel_target_for_name
from .goal_topic_runtime import _inbox_config
from .manager_routing import authorized_manager_goal_ids
from .event_inbox import load_lark_event_inbox_config, _load_processed
from .inbox_reply import reply_lark_event_inbox
from ...capabilities.manager_context import authority


def send_return(
    *,
    root,
    registry,
    snapshot_provider,
    route,
    session,
    turn,
    text,
    runner=None,
    cancelled=lambda: False,
):
    def resolve():
        if cancelled():
            raise ValueError("manager return service stopped")
        snapshot = snapshot_provider()
        # Validate live binding/session independently of the worker's target Goal.
        # Delegation grants permit only this request's audience-ready reply.
        if not authorized_manager_goal_ids(snapshot, session, runtime_root=root):
            raise ValueError("manager connection no longer authorized")
        target = {k: route[k] for k in ("goal_id", "agent_id")}
        grant = authority(root, registry, session, turn)
        if (
            target not in grant["targets"]
            or grant.get("source_id") != route["source_id"]
        ):
            raise ValueError("context return authority revoked")
        matches = []
        for gid, payload in snapshot.get("binding_payloads", {}).items():
            for binding in bindings_for_goal(payload, gid):
                if (
                    binding.get("enabled") is True
                    and binding.get("session_id") == route["session_id"]
                    and (binding.get("routing") or {}).get("conversation_kind")
                    == "manager"
                ):
                    matches.append(binding)
        if len(matches) != 1:
            raise ValueError("manager return binding ambiguous")
        binding = matches[0]
        target_config = goal_channel_target_for_name(
            snapshot["target_payload"], binding["target_ref"]
        )
        if not target_config or target_config.get("enabled") is not True:
            raise ValueError("manager return target disabled")
        routing = {
            "target_ref": binding["target_ref"],
            "conversation_kind": "manager",
            "app_ref": (target_config.get("identity") or {}).get("sender_profile")
            or "default",
            "topic_root_message_id": (binding.get("topic") or {}).get("root_message_id")
            or (binding.get("channel") or {}).get("pinned_message_id")
            or "",
        }
        return snapshot, routing, target_config

    snapshot, routing, target_config = resolve()
    config_path, _ = _inbox_config(
        runtime_root=root, route=routing, target_payload=snapshot["target_payload"]
    )
    message_id = route["source_id"].removeprefix("lark:")
    config = load_lark_event_inbox_config(project=root, config_path=config_path)
    if message_id not in _load_processed(config["inbox_path"] / "processed.json"):
        raise ValueError("initial reply has not been acknowledged")

    def before_send(_intent):
        current = resolve()
        return {"continue_delivery": current[1:] == (routing, target_config)}

    return reply_lark_event_inbox(
        project=root,
        config_path=config_path,
        message_id=message_id,
        text=text,
        execute=True,
        before_send=before_send,
        **({"runner": runner} if runner else {}),
    )


def start_return_service(server, runtime_root):
    """Compose the return pump at the existing Chat/Lark service boundary."""
    from ...capabilities.manager_context.roundtrip import ReturnService

    service = ReturnService(
        runtime_root,
        server.registry_path,
        server.chat_store,
        lambda route, session, turn, text: send_return(
            root=runtime_root,
            registry=server.registry_path,
            snapshot_provider=server.lark_goal_topic_runtime.snapshot_provider,
            route=route,
            session=session,
            turn=turn,
            text=text,
            cancelled=service.stop.is_set,
        ),
    )
    service.start()
    return service
