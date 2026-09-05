from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from threading import Thread
from typing import Iterator
import urllib.error
import urllib.parse
import urllib.request

from loopx.capabilities.periodic_report.workspace import (
    build_periodic_report_workspace_projection,
    write_periodic_report_workspace_projection,
)
from loopx.capabilities.periodic_report.incremental import (
    build_periodic_report_publication_candidate,
    commit_periodic_report_publication_cursor,
)
from loopx.status_server import (
    DEFAULT_CONFIGURE_GOAL_APPLY_PATH,
    DEFAULT_CONFIGURE_GOAL_DRY_RUN_PATH,
    DEFAULT_PERIODIC_REPORT_INDEX_PATH,
    DEFAULT_PERIODIC_REPORT_PROJECTION_PATH,
    DEFAULT_REWARD_APPEND_PATH,
    DEFAULT_REWARD_DRY_RUN_PATH,
    DEFAULT_STATUS_PATH,
    StatusHTTPServer,
    StatusRequestHandler,
)


def _request(url: str, *, origin: str | None = None) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url, headers={"Origin": origin} if origin else {}, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


@contextmanager
def _server(tmp_path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    runtime = tmp_path / "runtime"
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"common_runtime_root": str(runtime), "goals": []}) + "\n"
    )
    document = {
        "title": "Synthetic milestone",
        "generated_at": "2026-01-02T00:00:00Z",
        "period_window": {
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-01-02T00:00:00Z",
        },
        "editorial": {"summary": "A synthetic, public-safe milestone."},
        "sections": [
            {
                "items": [
                    {
                        "item_id": "outcome_1",
                        "source_ref": "todo:one",
                        "title": "Validated slice",
                        "summary": "The focused smoke passed.",
                        "content_kind": "outcome",
                    }
                ]
            }
        ],
    }
    facts = [
        {
            "fact_id": "fact_one",
            "title": "Validated slice",
            "summary": "The focused smoke passed.",
            "source_ref": "todo:one",
            "status": "done",
            "content_kind": "outcome",
            "change_kind": "added",
        }
    ]
    projection = build_periodic_report_workspace_projection(
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        generation_id="report_generation_example",
        document=document,
        facts=facts,
    )
    write_periodic_report_workspace_projection(
        path=runtime
        / "goals/synthetic-goal/periodic_reports/run/workspace-projection.json",
        projection=projection,
    )
    candidate = build_periodic_report_publication_candidate(
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        generation_id="report_generation_example",
        trigger_receipt={"coalesced_trigger_ids": ["trigger_one"]},
        facts=[
            {
                **facts[0],
                "fact_fingerprint": "sha256:" + "1" * 64,
            }
        ],
        baseline=None,
        workspace_projection_sha256=str(projection["content_sha256"]),
    )
    commit_periodic_report_publication_cursor(
        runtime_root=runtime,
        candidate=candidate,
        publication_id="publication_one",
        delivered_at="2026-01-02T00:05:00Z",
        covered_until="2026-01-02T00:00:00Z",
    )

    server = StatusHTTPServer(("127.0.0.1", 0), StatusRequestHandler)
    server.registry_path = registry
    server.runtime_root_override = None
    server.scan_roots = [tmp_path]
    server.limit = 5
    server.status_path = DEFAULT_STATUS_PATH
    server.reward_dry_run_path = DEFAULT_REWARD_DRY_RUN_PATH
    server.reward_append_path = DEFAULT_REWARD_APPEND_PATH
    server.reward_write_enabled = False
    server.configure_goal_dry_run_path = DEFAULT_CONFIGURE_GOAL_DRY_RUN_PATH
    server.configure_goal_apply_path = DEFAULT_CONFIGURE_GOAL_APPLY_PATH
    server.control_plane_write_enabled = False
    server.verbose = False
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}", projection
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_status_server_serves_only_exact_published_report_ref(tmp_path: Path) -> None:
    with _server(tmp_path) as (base, projection):
        status, capabilities = _request(f"{base}/")
        assert status == 200
        assert (
            capabilities["periodic_report_index_url"]
            == DEFAULT_PERIODIC_REPORT_INDEX_PATH
        )
        status, index_response = _request(
            f"{base}{DEFAULT_PERIODIC_REPORT_INDEX_PATH}?goal_id=synthetic-goal",
            origin="http://127.0.0.1:5173",
        )
        assert status == 200
        index = index_response["periodic_reports"]
        assert isinstance(index, dict)
        assert index["limit"] == 100
        assert index["offset"] == 0
        assert index["truncated"] is False
        ref = index["items"][0]["detail_ref"]
        status, detail = _request(
            f"{base}{DEFAULT_PERIODIC_REPORT_PROJECTION_PATH}?"
            + urllib.parse.urlencode(ref),
            origin="http://127.0.0.1:5173",
        )

    assert status == 200
    assert detail["projection"]["content_sha256"] == projection["content_sha256"]


def test_status_server_rejects_public_origin_and_mismatched_digest(
    tmp_path: Path,
) -> None:
    with _server(tmp_path) as (base, projection):
        status, payload = _request(
            f"{base}{DEFAULT_PERIODIC_REPORT_INDEX_PATH}",
            origin="https://public.example",
        )
        assert status == 403
        assert payload["ok"] is False
        query = urllib.parse.urlencode(
            {
                "goal_id": "synthetic-goal",
                "agent_id": "synthetic-agent",
                "generation_id": "report_generation_example",
                "content_sha256": "sha256:" + "0" * 64,
            }
        )
        status, payload = _request(
            f"{base}{DEFAULT_PERIODIC_REPORT_PROJECTION_PATH}?{query}",
            origin="http://127.0.0.1:5173",
        )

    assert status == 400
    assert "not the current publication" in str(payload["error"])
    assert projection["content_sha256"] not in str(payload)


def test_status_server_bounds_periodic_report_index_window(
    tmp_path: Path,
) -> None:
    with _server(tmp_path) as (base, _projection):
        status, payload = _request(
            f"{base}{DEFAULT_PERIODIC_REPORT_INDEX_PATH}?limit=201",
            origin="http://127.0.0.1:5173",
        )

    assert status == 400
    assert "limit must be between 0 and 200" in str(payload["error"])
