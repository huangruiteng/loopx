"""Optional OpenViking archive implementation for periodic-report."""

from .activation import (
    OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
    OPENVIKING_PERIODIC_REPORT_PERMISSION,
    PERIODIC_REPORT_SINK_PROTOCOL,
    resolve_openviking_periodic_report_activation,
    validate_openviking_periodic_report_activation,
)

__all__ = [
    "OPENVIKING_PERIODIC_REPORT_EXTENSION_ID",
    "OPENVIKING_PERIODIC_REPORT_PERMISSION",
    "PERIODIC_REPORT_SINK_PROTOCOL",
    "resolve_openviking_periodic_report_activation",
    "validate_openviking_periodic_report_activation",
]
