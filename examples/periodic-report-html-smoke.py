#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.renderers.periodic_report_html import (  # noqa: E402
    render_periodic_report_html,
)
from loopx.presentation.renderers.periodic_report_markdown import (  # noqa: E402
    render_periodic_report_markdown,
)


FIXTURE = (
    REPO_ROOT
    / "examples"
    / "fixtures"
    / "periodic-report-editorial-dense.public.json"
)


def main() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    html_artifact = render_periodic_report_html(document)
    markdown_artifact = render_periodic_report_markdown(document)
    content = html_artifact["content"]
    primary_body, supporting = content.split(
        '<details class="supporting" data-supporting-context>',
        maxsplit=1,
    )

    assert html_artifact["document_digest"] == markdown_artifact["document_digest"]
    assert (
        html_artifact["companion_markdown_digest"]
        == markdown_artifact["content_digest"]
    )
    assert html_artifact["external_dependencies"] == []
    assert html_artifact["presentation_profile"] == "editorial_dense_v1"
    assert html_artifact["content_policy"]["supporting_context"] == "collapsed"
    assert (
        html_artifact["content_policy"]["process_narration_default_visible"]
        is False
    )
    for expected in (
        "Stable release reached all production regions",
        "reduced median processing latency by 18%",
        "Two integrations still use the legacy endpoint",
        "Confirm owners and complete both migrations",
    ):
        assert expected in primary_body
        assert expected in markdown_artifact["content"]
    assert "snapshot_example_delivery" not in primary_body
    assert "snapshot_example_delivery" in supporting
    assert "data-copy-markdown" in content
    assert "data-print-report" in content
    assert "https://cdn" not in content
    print("periodic-report-html-smoke: ok")


if __name__ == "__main__":
    main()
