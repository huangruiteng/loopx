#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.periodic_report import (  # noqa: E402
    build_periodic_report_delivery_receipt,
    build_periodic_report_document,
    build_periodic_report_extension_readiness,
    build_periodic_report_generation_bundle,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_html import (  # noqa: E402
    render_periodic_report_html,
)
from loopx.presentation.renderers.periodic_report_markdown import (  # noqa: E402
    render_periodic_report_markdown,
)


def _generation() -> dict[str, object]:
    source = build_periodic_report_source_result(
        source_id="project_progress",
        source_kind="validated_outcomes",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[
            {
                "section_id": "completed",
                "title": "Completed",
                "order": 10,
                "items": [
                    {
                        "item_id": "release_2.4",
                        "title": "Release 2.4",
                        "summary": "Published the stable release.",
                    }
                ],
            }
        ],
    )
    document = build_periodic_report_document(
        title="Project report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "project", "profile_version": "v1"},
        sources=[source],
    )
    return build_periodic_report_generation_bundle(
        document=document,
        artifacts=[
            render_periodic_report_markdown(document),
            render_periodic_report_html(document),
        ],
    )


def main() -> None:
    fixture_path = (
        REPO_ROOT
        / "examples"
        / "fixtures"
        / "periodic-report-extension-modes.public.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    generation = _generation()["generation_receipt"]
    modes: dict[str, tuple[str, str]] = {}
    for profile in fixture["profiles"]:
        readiness = build_periodic_report_extension_readiness(
            generation_receipt=generation,
            sink_bindings=profile["sink_bindings"],
        )
        delivery = build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=readiness,
        )
        assert readiness["delivery_mode"] == profile["expected_delivery_mode"]
        assert readiness["generation_usable"] is True
        modes[profile["profile_id"]] = (
            readiness["status"],
            delivery["status"],
        )

    assert modes == {
        "portable_changelog": ("not_required", "not_required"),
        "enhanced_research": ("degraded", "partial"),
        "durable_maintenance": ("blocked", "failed"),
    }
    print("periodic-report-bindings-smoke: ok")


if __name__ == "__main__":
    main()
