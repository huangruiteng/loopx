from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


InboxOperation = Callable[..., dict[str, Any]]
InboxContainsText = Callable[..., bool]
NotificationSinkAdapter = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class IssueFixReviewerProviderHooks:
    """Provider-neutral operations used by issue-fix reviewer workflows."""

    inspect: InboxOperation
    acknowledge: InboxOperation
    contains_text: InboxContainsText
    notification_adapter: NotificationSinkAdapter
    activation: Mapping[str, object]


IssueFixReviewerProviderHooksFactory = Callable[[], IssueFixReviewerProviderHooks]
