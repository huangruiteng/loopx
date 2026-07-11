from __future__ import annotations

from datetime import datetime
from typing import Any

from ..runtime.time import parse_timestamp


def parse_scheduler_timestamp(value: Any) -> datetime | None:
    return parse_timestamp(value)
