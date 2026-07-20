#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.periodic_report import (  # noqa: E402
    build_periodic_report_activation,
    build_periodic_report_document,
    build_periodic_report_source_result,
)
from loopx.extensions.openviking_periodic_report.provider import (  # noqa: E402
    REQUEST_SCHEMA,
    archive_request,
)
from loopx.presentation.renderers.periodic_report_markdown import (  # noqa: E402
    render_periodic_report_markdown,
)


class FakeOpenViking:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.writes: list[str] = []

    def read(self, uri: str, offset: int = 0, limit: int = -1) -> str:
        del offset, limit
        if uri not in self.files:
            raise FileNotFoundError(uri)
        return self.files[uri]

    def write(
        self,
        uri: str,
        content: str,
        mode: str = "replace",
        wait: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        del wait, timeout
        if mode != "create" or uri in self.files:
            raise FileExistsError(uri)
        self.files[uri] = content
        self.writes.append(uri)
        return {"uri": uri}


def main() -> None:
    profiles = json.loads(
        (
            REPO_ROOT
            / "examples"
            / "fixtures"
            / "periodic-report-product-profiles.public.json"
        ).read_text(encoding="utf-8")
    )
    profile = next(
        item
        for item in profiles["profiles"]
        if item.get("profile_id") == "release_summary"
    )
    source = build_periodic_report_source_result(
        source_id="release_state",
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
        title="Release report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "release_summary", "profile_version": "v1"},
        sources=[source],
    )
    artifact = render_periodic_report_markdown(document)
    request = {
        "schema_version": REQUEST_SCHEMA,
        "activation_receipt": build_periodic_report_activation(profile),
        "available_capabilities": ["openviking_context_write"],
        "artifact": artifact,
        "document": document,
        "context": {
            "sink_id": "project_archive",
            "idempotency_key": "release-summary-2026-07-20",
            "archive_root_uri": "viking://resources/loopx/reports",
            "semantic_tags": ["release_summary"],
        },
        "execute": True,
    }
    client = FakeOpenViking()
    first = archive_request(request, client=client)
    replay = archive_request(request, client=client)
    assert first["status"] == replay["status"] == "sent"
    assert first["result_id"] == replay["result_id"]
    assert replay["write_status"] == "already_present"
    assert [uri.rsplit("/", 1)[-1] for uri in client.writes] == [
        "report.md",
        "manifest.json",
    ]
    print("openviking-periodic-report-extension-smoke: ok")


if __name__ == "__main__":
    main()
