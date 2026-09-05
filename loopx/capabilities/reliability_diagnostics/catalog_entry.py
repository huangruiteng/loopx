"""Capability-owned catalog entry for Reliability Diagnostics (L1 shadow observer)."""

from __future__ import annotations

from typing import Any

from .envelope import (
    CAPABILITY_ID,
    DSH_PROVIDER_ID,
    OBSERVER_ENVELOPE_SCHEMA_VERSION,
    OBSERVER_STATS_SCHEMA_VERSION,
)
from .projection import DIAGNOSTIC_PROJECTION_SCHEMA_VERSION
from .receipt import INTEGRITY_RECEIPT_SCHEMA_VERSION

_README = "loopx/capabilities/reliability_diagnostics/README.md"

RELIABILITY_DIAGNOSTICS_CATALOG_ENTRY: dict[str, Any] = {
    "id": CAPABILITY_ID,
    "origin": "builtin",
    "visibility": "public",
    "provider_id": "loopx-core",
    "documentation": {
        "source_root": "loopx/capabilities/reliability_diagnostics",
        "site_root": "capabilities/reliability-diagnostics",
        "canonical": "README.md",
    },
    "title": "Passive reliability diagnostics from one-way harness events",
    "status": "experimental",
    "default_enabled": False,
    "real_world_anchor": (
        "long-running agent sessions whose stalls, repetition, and recovery must "
        "be observed without changing the worker"
    ),
    "user_value": (
        "Turn read-only harness events into an independent diagnostic ledger, a "
        "treatment-integrity receipt, and a compact stall/repetition/recovery "
        "projection that carries no runtime authority."
    ),
    "entry_command": "loopx reliability-diagnostics status --goal-id <goal-id> --format json",
    "commands": [
        {
            "command": (
                "loopx reliability-diagnostics ingest --goal-id <goal-id> "
                "--input <envelopes.ndjson|-> --format json"
            ),
            "purpose": "Validate observer envelopes and append accepted ones to the goal's diagnostic ledger.",
            "write_boundary": (
                "appends only to the LoopX-owned diagnostic ledger; rejects control-shaped "
                "and raw-material-bearing records; never touches goal, todo, gate, or session state"
            ),
        },
        {
            "command": "loopx reliability-diagnostics receipt --goal-id <goal-id> --format json",
            "purpose": "Render the treatment-integrity receipt (loss, drops, clock, endpoints, status).",
            "write_boundary": "read-only ledger reduction; no state write",
        },
        {
            "command": "loopx reliability-diagnostics status --goal-id <goal-id> --format json",
            "purpose": "Render the compact read-only stage/stall/repetition/recovery projection.",
            "write_boundary": "read-only ledger reduction; `mode=read_only`, `authority=none`",
        },
    ],
    "implemented_protocols": [
        {"schema_version": schema_version, "module": module, "doc": _README}
        for schema_version, module in (
            (OBSERVER_ENVELOPE_SCHEMA_VERSION, "loopx.capabilities.reliability_diagnostics.envelope"),
            (OBSERVER_STATS_SCHEMA_VERSION, "loopx.capabilities.reliability_diagnostics.intake"),
            (INTEGRITY_RECEIPT_SCHEMA_VERSION, "loopx.capabilities.reliability_diagnostics.receipt"),
            (DIAGNOSTIC_PROJECTION_SCHEMA_VERSION, "loopx.capabilities.reliability_diagnostics.projection"),
        )
    ],
    "implementation_providers": [
        {
            "provider_id": DSH_PROVIDER_ID,
            "origin": "extension",
            "protocol": OBSERVER_ENVELOPE_SCHEMA_VERSION,
            "package": "packages/dsh-loopx-plugin",
            "status": "declared_default_off",
        }
    ],
    "smokes": [
        "python3 examples/reliability_diagnostics/dsh-shadow-observer-fixture-smoke.py",
        "python3 -m pytest tests/capabilities/test_reliability_diagnostics.py -q",
    ],
    "docs": [_README, "loopx/capabilities/reliability_diagnostics/README.zh-CN.md"],
    "boundaries": [
        "L1 only: the observer consumes read-only harness events and owns no send, schedule, retry, stop, resume, gate, tool, or worker-state path.",
        "Envelopes are a strict allowlist; control-shaped and raw-material-shaped fields are rejected and counted, never persisted.",
        "The diagnostic ledger and projection are siblings of session-runtime state and are never merged into goal, todo, gate, or quota authority.",
        "Observer failure is isolated and counted; it marks the receipt quarantined and can never pause or fail the worker.",
        "The DSH provider is default off and declared only; enabling it requires an explicit per-goal opt-in in the plugin environment.",
    ],
    "next_real_step": (
        "Enable the DSH provider for one goal, ingest its ledger, and compare the "
        "receipt against a native baseline run to report observer overhead."
    ),
}
