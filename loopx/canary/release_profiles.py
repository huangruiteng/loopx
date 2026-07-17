from __future__ import annotations

from typing import Any


RELEASE_PROMOTION_PROFILE: dict[str, Any] = {
    "id": "release-promotion",
    "title": "Release promotion readiness",
    "quality_risk": "high",
    "purpose": "Check whether the release/canary promotion path is ready without mutating the install.",
    "catalog_families": ["Work Routing", "Planning Governance", "State And Boundary"],
    "trigger_hints": (
        "release",
        "release promotion",
        "promotion",
        "canary-promotion",
        "promotion-readiness",
    ),
    "checks": [
        {
            "command": "python3 examples/canary/canary-promotion-readiness-smoke.py",
            "tier": "default",
            "reason": "checks promotion readiness from compact run history",
        },
        {
            "command": "python3 examples/release/exact-release-commit-qualification-smoke.py",
            "tier": "default",
            "reason": "guards exact source identity, bounded lane receipts, and read-only release qualification",
        },
        {
            "command": "python3 examples/canary/canary-promotion-readiness-boundary-smoke.py",
            "tier": "default",
            "reason": "guards dashboard release-boundary planning for source checkouts and release snapshots",
        },
        {
            "command": "python3 examples/canary/canary-promotion-no-write-contract-smoke.py",
            "tier": "default",
            "reason": "guards no-write promotion readiness behavior",
        },
        {
            "command": "python3 examples/canary/canary-promotion-readiness-writeback-smoke.py",
            "tier": "deep",
            "reason": "exercises promotion readiness writeback after explicit opt-in",
        },
    ],
}
