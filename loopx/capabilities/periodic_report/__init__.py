"""Provider-neutral periodic report contracts and adapter registry."""

from .adapters import (
    PeriodicReportAdapterRegistry,
    PeriodicReportRendererAdapter,
    PeriodicReportSinkAdapter,
    PeriodicReportSourceAdapter,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from .archive import (
    build_periodic_report_archive_bundle,
    verify_periodic_report_archive_receipts,
)
from .core import build_periodic_report_run
from .triggers import build_periodic_report_trigger_decision

__all__ = [
    "PeriodicReportAdapterRegistry",
    "PeriodicReportRendererAdapter",
    "PeriodicReportSinkAdapter",
    "PeriodicReportSourceAdapter",
    "build_periodic_report_document",
    "build_periodic_report_archive_bundle",
    "build_periodic_report_run",
    "build_periodic_report_source_result",
    "build_periodic_report_trigger_decision",
    "verify_periodic_report_archive_receipts",
]
