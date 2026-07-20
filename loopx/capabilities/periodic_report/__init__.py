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
from .bindings import (
    build_periodic_report_delivery_receipt,
    build_periodic_report_extension_readiness,
    build_periodic_report_generation_bundle,
    normalize_periodic_report_sink_bindings,
)
from .core import build_periodic_report_run
from .profile import (
    build_periodic_report_activation,
    normalize_periodic_report_profile,
)
from .triggers import (
    build_periodic_report_trigger_decision,
    normalize_periodic_report_trigger_policy,
)

__all__ = [
    "PeriodicReportAdapterRegistry",
    "PeriodicReportRendererAdapter",
    "PeriodicReportSinkAdapter",
    "PeriodicReportSourceAdapter",
    "build_periodic_report_activation",
    "build_periodic_report_document",
    "build_periodic_report_delivery_receipt",
    "build_periodic_report_extension_readiness",
    "build_periodic_report_generation_bundle",
    "build_periodic_report_archive_bundle",
    "build_periodic_report_run",
    "build_periodic_report_source_result",
    "build_periodic_report_trigger_decision",
    "normalize_periodic_report_profile",
    "normalize_periodic_report_sink_bindings",
    "normalize_periodic_report_trigger_policy",
    "verify_periodic_report_archive_receipts",
]
