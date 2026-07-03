#!/usr/bin/env python3
"""Smoke-test promotion canary dashboard-boundary planning."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CANARY_PATH = REPO_ROOT / "examples" / "canary" / "canary-promotion-readiness-smoke.py"


def load_canary_module():
    spec = importlib.util.spec_from_file_location(
        "canary_promotion_readiness_smoke",
        CANARY_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    canary = load_canary_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        release_dashboard = root / "release" / "apps" / "dashboard"
        source_dashboard = root / "source" / "apps" / "dashboard"
        source_dashboard.mkdir(parents=True)
        (source_dashboard / "package.json").write_text("{}\n", encoding="utf-8")

        auto_release = canary.dashboard_readiness_plan(dashboard_dir=release_dashboard)
        assert auto_release["status"] == "skip", auto_release
        assert "apps/dashboard is not present" in auto_release["reason"], auto_release

        required_release = canary.dashboard_readiness_plan(
            dashboard_dir=release_dashboard,
            dashboard_mode="require",
        )
        assert required_release["status"] == "fail", required_release

        browser_release = canary.dashboard_readiness_plan(
            dashboard_dir=release_dashboard,
            include_browser=True,
        )
        assert browser_release["status"] == "fail", browser_release

        skipped_release = canary.dashboard_readiness_plan(
            dashboard_dir=release_dashboard,
            dashboard_mode="skip",
            include_browser=True,
        )
        assert skipped_release["status"] == "skip", skipped_release
        assert skipped_release["reason"] == "dashboard readiness explicitly skipped", skipped_release

        source_plan = canary.dashboard_readiness_plan(dashboard_dir=source_dashboard)
        assert source_plan["status"] == "run", source_plan
        assert source_plan["command"][-1] == "--skip-browser", source_plan

        source_browser_plan = canary.dashboard_readiness_plan(
            dashboard_dir=source_dashboard,
            include_browser=True,
        )
        assert source_browser_plan["status"] == "run", source_browser_plan
        assert "--skip-browser" not in source_browser_plan["command"], source_browser_plan

    print("canary-promotion-readiness-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
