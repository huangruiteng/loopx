#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.periodic_report import (  # noqa: E402
    build_periodic_report_activation,
    resolve_periodic_report_profile_preset,
)


def main() -> None:
    fixture_path = (
        REPO_ROOT
        / "examples"
        / "fixtures"
        / "periodic-report-product-profiles.public.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    activations = {
        profile["profile_id"]: build_periodic_report_activation(profile)
        for profile in fixture["profiles"]
    }

    assert activations["disabled_project"]["status"] == "disabled"
    assert activations["weekly_progress"]["extension_mode"] == "portable"
    assert activations["weekly_progress"]["profile"] == (
        resolve_periodic_report_profile_preset("weekly")
    )
    assert len(activations["weekly_progress"]["profile"]["renderer_bindings"]) == 2
    assert activations["release_summary"]["extension_mode"] == "enhanced"
    assert activations["release_summary"]["optional_extension_count"] == 1
    assert activations["research_milestones"]["extension_mode"] == "portable"
    assert all(
        item["boundary"]["external_writes_performed"] is False
        for item in activations.values()
    )
    serialized = json.dumps(activations, ensure_ascii=False).lower()
    assert "issue_fix" not in serialized and "pull_request" not in serialized
    print("periodic-report-profile-smoke: ok")


if __name__ == "__main__":
    main()
