from __future__ import annotations

from enum import Enum
from typing import Any


class DeliveryBatchScale(str, Enum):
    """Structured machine signal for the scale of a delivery run."""

    TEST_ONLY = "test_only"
    SINGLE_SURFACE = "single_surface"
    MULTI_SURFACE = "multi_surface"
    IMPLEMENTATION = "implementation"


DELIVERY_BATCH_SCALE_CHOICES = tuple(scale.value for scale in DeliveryBatchScale)
SMALL_DELIVERY_BATCH_SCALES = frozenset(
    {
        DeliveryBatchScale.TEST_ONLY,
        DeliveryBatchScale.SINGLE_SURFACE,
    }
)
UNKNOWN_DELIVERY_BATCH_SCALE = "unknown"


def normalize_delivery_batch_scale(value: Any) -> DeliveryBatchScale | None:
    if isinstance(value, DeliveryBatchScale):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return DeliveryBatchScale(text)
    except ValueError:
        return None


def require_delivery_batch_scale(value: Any) -> DeliveryBatchScale:
    scale = normalize_delivery_batch_scale(value)
    if scale is None:
        raise ValueError("delivery_batch_scale must be one of: " + ", ".join(DELIVERY_BATCH_SCALE_CHOICES))
    return scale


def delivery_batch_scale_value(value: Any) -> str | None:
    scale = normalize_delivery_batch_scale(value)
    return scale.value if scale else None
