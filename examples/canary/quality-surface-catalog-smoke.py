#!/usr/bin/env python3
"""Smoke-test the high-risk quality surface catalog and CLI audit."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.planner import (  # noqa: E402
    CURRENT_REPO_PROFILES,
    build_quality_surface_catalog_audit,
)


def main() -> int:
    audit = build_quality_surface_catalog_audit()
    assert audit["ok"] is True, audit
    assert audit["drift_count"] == 0, audit
    assert audit["classified_surface_count"] == audit["high_risk_profile_count"], audit

    high_risk_ids = {
        str(profile["id"])
        for profile in CURRENT_REPO_PROFILES
        if profile.get("quality_risk") == "high"
    }
    classified_ids = {
        str(surface["canary_profile_id"]) for surface in audit["surfaces"]
    }
    assert classified_ids == high_risk_ids, audit
    assert all(gap.get("owner") and gap.get("rationale") for gap in audit["gaps"]), audit

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "quality-audit",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    cli_audit = json.loads(completed.stdout)
    assert cli_audit["schema_version"] == "quality_surface_catalog_audit_v0", cli_audit
    assert cli_audit["drift_count"] == 0, cli_audit
    assert cli_audit["executes_checks"] is False, cli_audit
    print("quality surface catalog smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
