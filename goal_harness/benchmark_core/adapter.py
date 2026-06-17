from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class BenchmarkRequest:
    """Adapter-neutral request for a benchmark case run."""

    benchmark_id: str
    case_id: str
    route: str
    arm_id: str = ""
    max_rounds: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    external_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LaunchResult:
    process_started: bool
    handle: RunHandle | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    lifecycle: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestResult:
    benchmark_run: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterClassification:
    decision: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LedgerUpdate:
    written: bool
    payload: dict[str, Any] = field(default_factory=dict)


class BenchmarkAdapter(Protocol):
    """Minimal control-plane interface implemented by benchmark adapters."""

    id: str

    def preflight(self, request: BenchmarkRequest) -> PreflightResult:
        ...

    def launch(self, request: BenchmarkRequest) -> LaunchResult:
        ...

    def observe(self, handle: RunHandle) -> Observation:
        ...

    def ingest(self, artifact: str) -> IngestResult:
        ...

    def classify(self, run: IngestResult) -> AdapterClassification:
        ...

    def ledger(self, run: IngestResult) -> LedgerUpdate:
        ...
