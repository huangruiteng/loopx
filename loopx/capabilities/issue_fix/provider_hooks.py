from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


InboxOperation = Callable[..., dict[str, Any]]
InboxContainsText = Callable[..., bool]


@dataclass(frozen=True)
class ReviewerInboxHooks:
    """Provider-neutral operations used by issue-fix reviewer workflows."""

    inspect: InboxOperation
    acknowledge: InboxOperation
    contains_text: InboxContainsText
    activation: Mapping[str, object]


ReviewerInboxHooksFactory = Callable[[], ReviewerInboxHooks]
