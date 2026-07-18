from __future__ import annotations

from typing import Any

from loopx.capabilities.issue_fix.reviewer_notification import (
    build_issue_fix_reviewer_notification_sinks_result as build_core_sinks_result,
)
from loopx.capabilities.issue_fix.reviewer_notification_drain import (
    drain_issue_fix_reviewer_notification_queue as drain_core_queue,
)
from loopx.capabilities.issue_fix.reviewer_request import (
    build_issue_fix_reviewer_request_packet as build_core_request_packet,
)
from loopx.extensions.lark.reviewer_notification import (
    lark_reviewer_notification_sink,
)


def _with_lark_adapter(overrides: dict[str, Any] | None) -> dict[str, Any]:
    return {"lark_chat": lark_reviewer_notification_sink, **(overrides or {})}


def build_issue_fix_reviewer_notification_sinks_result(
    *args: Any,
    sink_adapters: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return build_core_sinks_result(
        *args,
        sink_adapters=_with_lark_adapter(sink_adapters),
        **kwargs,
    )


def build_issue_fix_reviewer_request_packet(
    *args: Any,
    notification_sink_adapters: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return build_core_request_packet(
        *args,
        notification_sink_adapters=_with_lark_adapter(notification_sink_adapters),
        **kwargs,
    )


def drain_issue_fix_reviewer_notification_queue(
    *args: Any,
    sink_adapters: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return drain_core_queue(
        *args,
        sink_adapters=_with_lark_adapter(sink_adapters),
        **kwargs,
    )
