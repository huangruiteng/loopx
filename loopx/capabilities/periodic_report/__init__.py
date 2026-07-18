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

__all__ = [
    "PeriodicReportAdapterRegistry",
    "PeriodicReportRendererAdapter",
    "PeriodicReportSinkAdapter",
    "PeriodicReportSourceAdapter",
    "build_periodic_report_document",
    "build_periodic_report_archive_bundle",
    "build_periodic_report_run",
    "build_periodic_report_source_result",
    "verify_periodic_report_archive_receipts",
]
