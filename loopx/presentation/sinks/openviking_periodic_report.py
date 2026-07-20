"""Compatibility import; OpenViking transport is owned by its LoopX extension."""

from ...extensions.openviking_periodic_report.sink import (
    periodic_report_openviking_sink_adapter,
)

__all__ = ["periodic_report_openviking_sink_adapter"]
