from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def compact_explore_graph_policy(value: Any) -> dict[str, bool]:
    """Return the strict, default-off per-goal Explore Graph gate."""

    policy = value if isinstance(value, Mapping) else {}
    return {"enabled": policy.get("enabled") is True}
