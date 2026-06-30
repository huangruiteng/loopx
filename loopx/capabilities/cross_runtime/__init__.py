"""Cross-runtime product capability helpers."""

from .impl_review import (
    CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
    DEFAULT_GOAL_ID,
    DEFAULT_IMPLEMENTER_AGENT_ID,
    DEFAULT_REQUIREMENT,
    DEFAULT_REVIEWER_AGENT_ID,
    DEFAULT_VERIFIER,
    build_cross_runtime_impl_review_demo_packet,
    render_cross_runtime_impl_review_demo_markdown,
)

__all__ = [
    "CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION",
    "DEFAULT_GOAL_ID",
    "DEFAULT_IMPLEMENTER_AGENT_ID",
    "DEFAULT_REQUIREMENT",
    "DEFAULT_REVIEWER_AGENT_ID",
    "DEFAULT_VERIFIER",
    "build_cross_runtime_impl_review_demo_packet",
    "render_cross_runtime_impl_review_demo_markdown",
]
