"""Intermediate public-safe read models for presentation views."""

from .session_dash import (
    SESSION_DASH_PROJECTION_SCHEMA_VERSION,
    build_session_dash_projection,
)

__all__ = [
    "SESSION_DASH_PROJECTION_SCHEMA_VERSION",
    "build_session_dash_projection",
]
