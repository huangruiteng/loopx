"""Provider-neutral periodic report contracts and adapter registry."""

from .adapters import (
    PeriodicReportAdapterRegistry,
    PeriodicReportRendererAdapter,
    PeriodicReportSinkAdapter,
    PeriodicReportSourceAdapter,
    build_periodic_report_document,
    build_periodic_report_editorial,
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
from .presets import (
    PERIODIC_REPORT_PROFILE_PRESET_ALIASES,
    PERIODIC_REPORT_PROFILE_PRESET_IDS,
    WEEKLY_PROGRESS_PRESET_ID,
    build_periodic_report_preset_activation,
    resolve_periodic_report_profile_preset,
)
from .project_progress import (
    PROJECT_PROGRESS_PROJECTION_SCHEMA,
    build_project_progress_periodic_report_source,
    project_progress_periodic_report_source_adapter,
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
    "PERIODIC_REPORT_PROFILE_PRESET_ALIASES",
    "PERIODIC_REPORT_PROFILE_PRESET_IDS",
    "PROJECT_PROGRESS_PROJECTION_SCHEMA",
    "WEEKLY_PROGRESS_PRESET_ID",
    "build_periodic_report_activation",
    "build_periodic_report_document",
    "build_periodic_report_delivery_receipt",
    "build_periodic_report_editorial",
    "build_periodic_report_extension_readiness",
    "build_periodic_report_generation_bundle",
    "build_periodic_report_preset_activation",
    "build_project_progress_periodic_report_source",
    "build_periodic_report_archive_bundle",
    "build_periodic_report_run",
    "build_periodic_report_source_result",
    "build_periodic_report_trigger_decision",
    "normalize_periodic_report_profile",
    "normalize_periodic_report_sink_bindings",
    "normalize_periodic_report_trigger_policy",
    "project_progress_periodic_report_source_adapter",
    "resolve_periodic_report_profile_preset",
    "verify_periodic_report_archive_receipts",
]
