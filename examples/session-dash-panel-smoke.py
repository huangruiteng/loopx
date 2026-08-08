#!/usr/bin/env python3
"""Smoke-test the auto-generated single-page session dash panel.

Proves the generated panel is read-only, renders fleet progress/status the way
an operator reads it (sessions -> goals -> status), and rejects private
material at the boundary. Uses only public-safe fixtures; no live state,
credentials, or local paths required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.projections.session_dash import (  # noqa: E402
    SESSION_DASH_PROJECTION_SCHEMA_VERSION,
    build_session_dash_projection,
)
from loopx.presentation.public_safety import (  # noqa: E402
    PUBLIC_BOUNDARY_PATTERNS,
    scan_public_boundary_text,
)
from loopx.presentation.renderers.session_dash_html import (  # noqa: E402
    render_session_dash_html,
    render_session_dash_main,
)

PRIVATE_TRAP_MARKERS = (
    "/" + "Users/example/private-control-plane.md",
    "BEGIN " + "OPENSSH PRIVATE KEY",
    "api_" + "key=" + "GH_FAKE_LIVE_KEY",
)


def _load_status_fixture() -> dict[str, object]:
    fixture = json.loads((REPO_ROOT / "examples" / "status.example.json").read_text())
    assert isinstance(fixture, dict), "status.example.json must be an object"
    return fixture


def _build_fleet_fixture() -> dict[str, object]:
    """Start from status.example.json and enrich it into a small fleet.

    The shipped fixture has one goal and four sessions; we add a second goal
    (with finished todos) and a second session so the smoke proves the
    session -> goal grouping and progress signal actually render.
    """

    status = _load_status_fixture()
    status = dict(status)
    run_history = dict(status.get("run_history") or {})
    goals = [g for g in run_history.get("goals", []) if isinstance(g, dict)]
    goals = [dict(g) for g in goals]
    run_history["goals"] = goals
    run_history["goal_count"] = len(goals) + 1
    status["run_history"] = run_history

    # Add a second goal with finished + open todos.
    goals.append(
        {
            "id": "docs-polish",
            "domain": "loopx-platform",
            "status": "active-progress",
            "lifecycle_phase": "adapter_running",
            "registry_member": True,
            "quota": {"state": "ready", "compute": 1.0},
            "latest_runs": [
                {
                    "generated_at": "2026-07-06T10:15:00Z",
                    "goal_id": "docs-polish",
                    "classification": "progress_signal",
                    "agent_id": "codex-docs-agent",
                    "recommended_action": "Continue drafting the dashboard README.",
                }
            ],
        }
    )
    run_history["goals"] = goals
    status["run_history"] = run_history

    # Second session owning the second goal.
    agents = [a for a in (status.get("agent_management_projection") or {}).get("agents", [])]
    agents = [dict(a) for a in agents]
    agents.append(
        {
            "agent_id": "codex-docs-agent",
            "agent_model": "peer_v1",
            "profile_role": "docs-validation",
            "state": "active",
            "next_action": "Continue drafting the dashboard README.",
            "last_activity_at": "2026-07-06T10:15:00Z",
            "goal_ids": ["docs-polish"],
        }
    )
    status["agent_management_projection"] = {
        "schema_version": "agent_management_projection_v0",
        "mode": "read_only",
        "agents": agents,
    }

    # Todos for the second goal: one finished, one open agent todo.
    todo_items = [t for t in (status.get("todo_index") or {}).get("items", []) if isinstance(t, dict)]
    todo_items = [dict(t) for t in todo_items]
    todo_items.append(
        {
            "todo_id": "todo_docs_1",
            "goal_id": "docs-polish",
            "role": "agent",
            "status": "done",
            "done": True,
            "title": "Draft dashboard README.",
        }
    )
    todo_items.append(
        {
            "todo_id": "todo_docs_2",
            "goal_id": "docs-polish",
            "role": "agent",
            "status": "open",
            "done": False,
            "title": "Add a usage example.",
        }
    )
    status["todo_index"] = {
        "schema_version": "todo_index_v0",
        "total_count": len(todo_items),
        "items": todo_items,
    }
    return status


def _build_sample_projection() -> dict[str, object]:
    status = _build_fleet_fixture()
    return build_session_dash_projection(
        status_payload=status,
        run_history=status.get("run_history"),
        todo_index=status.get("todo_index"),
        agent_management=status.get("agent_management_projection"),
        usage_summary=status.get("usage_summary"),
        generated_at="2026-07-06T10:20:00Z",
    )


def test_projection_is_read_only_and_fleet_shaped() -> None:
    projection = _build_sample_projection()
    assert projection["schema_version"] == SESSION_DASH_PROJECTION_SCHEMA_VERSION
    assert projection["mode"] == "read_only"

    overview = projection["overview"]
    assert overview["session_count"] == 5  # 4 fixture sessions + 1 added
    assert overview["goal_count"] == 2
    assert overview["runs_24h"] == 20
    assert overview["open_agent_todos"] >= 1
    assert overview["done_todos"] >= 1

    sessions = projection["sessions"]
    assert isinstance(sessions, list) and sessions
    assert all("goals" in session and "session_id" in session for session in sessions)
    # the added session owns exactly one goal and reports its progress
    docs_session = next(s for s in sessions if s["session_id"] == "codex-docs-agent")
    assert docs_session["goal_count"] == 1
    goal = docs_session["goals"][0]
    assert goal["goal_id"] == "docs-polish"
    assert goal["done_todos"] == 1
    assert goal["open_agent_todos"] == 1
    assert goal["status_bucket"] == "active"

    # no internal machinery in the projection that humans can't read
    assert "truth_contract" not in projection
    assert "work_lane" not in projection
    assert "decision_frame" not in projection


def test_focus_goal_id_narrows_the_fleet() -> None:
    status = _build_fleet_fixture()
    projection = build_session_dash_projection(
        status_payload=status,
        run_history=status.get("run_history"),
        todo_index=status.get("todo_index"),
        agent_management=status.get("agent_management_projection"),
        focus_goal_id="docs-polish",
    )
    session_ids = [s["session_id"] for s in projection["sessions"]]
    assert session_ids == ["codex-docs-agent"]
    assert projection["overview"]["goal_count"] == 1


def test_html_renders_human_focused_sections() -> None:
    projection = _build_sample_projection()
    html = render_session_dash_html(projection)

    assert 'data-schema="session_dash_projection_v1"' in html
    assert 'data-mode="read_only"' in html
    for panel in ("overview", "sessions"):
        assert f'data-panel="{panel}"' in html, f"missing panel: {panel}"
    # the session -> goal hierarchy renders
    assert "codex-docs-agent" in html
    assert "docs-polish" in html
    assert "loopx-meta" in html
    # progress + result statistics render
    assert 'class="bar"' in html
    assert "Runs 24h" in html
    # jargon-heavy machinery is gone from the page
    for hidden in (
        "decision-frame",
        "work_lane",
        "truth-contract",
        "source-warnings",
        "lease_until",
        "write_scope",
    ):
        assert hidden not in html, f"internal machinery leaked into the page: {hidden}"
    # no write controls on the generated page
    assert "<form" not in html
    assert "method=\"post\"" not in html


def test_html_escapes_and_passes_boundary_scan() -> None:
    projection = _build_sample_projection()
    html = render_session_dash_html(projection)

    boundary = scan_public_boundary_text(html)
    assert boundary["ok"] is True, boundary

    # private trap markers must never appear in generated output
    for marker in PRIVATE_TRAP_MARKERS:
        assert marker not in html, f"private marker leaked into generated page: {marker}"


def test_boundary_scan_flags_private_material() -> None:
    # the scanner itself must reject private material (negative control)
    probe = " ".join(PRIVATE_TRAP_MARKERS)
    boundary = scan_public_boundary_text(probe)
    assert boundary["ok"] is False, "private material must be flagged"
    assert boundary["warnings"], "expected at least one boundary warning"

    # patterns are shared with the static-site exporter
    from loopx.presentation.static_site import _PUBLIC_BOUNDARY_PATTERNS  # noqa: PLC0415

    assert _PUBLIC_BOUNDARY_PATTERNS is PUBLIC_BOUNDARY_PATTERNS


def test_escape_prevents_injection() -> None:
    projection = _build_sample_projection()
    projection = dict(projection)
    sessions = [dict(s) for s in projection["sessions"]]
    sessions[0]["session_id"] = '<script>alert("xss")</script>'
    projection["sessions"] = sessions
    html = render_session_dash_html(projection)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_live_serve_page_has_refresh_and_fragment() -> None:
    projection = _build_sample_projection()
    html = render_session_dash_html(projection, live_refresh_seconds=10)
    fragment = render_session_dash_main(projection)

    # the live page embeds an in-place auto-refresh script polling /panel
    assert "async function refreshDash" in html
    assert "setInterval(refreshDash, refreshSeconds * 1000)" in html
    assert "fetch('panel')" in html
    # the fragment endpoint returns the main block only, no full page
    assert fragment.lstrip().startswith("<main")
    assert "</main>" in fragment
    assert "<html" not in fragment
    assert "<script" not in fragment
    # both renderers agree on the panel content
    assert 'data-panel="sessions"' in fragment
    assert 'data-panel="overview"' in html


def test_live_server_handler_is_read_only() -> None:
    # serve_dash binds loopback only and exposes no write routes
    from loopx.dash_server import DEFAULT_DASH_HOST, serve_dash  # noqa: PLC0415

    assert DEFAULT_DASH_HOST == "127.0.0.1"
    assert "POST" not in dir(serve_dash)


def _build_polluted_status_fixture() -> dict[str, object]:
    """Fleet fixture whose projected session/goal text carries private traps.

    Injects PRIVATE_TRAP_MARKERS into the exact fields the projection copies
    verbatim (goal ``recommended_action`` and session ``next_action``) so the
    negative tests prove the boundary gate withholds on the real output path.
    """

    status = _build_fleet_fixture()
    status = dict(status)
    marker_text = " ".join(PRIVATE_TRAP_MARKERS)

    attention = dict(status.get("attention_queue") or {})
    items = [dict(item) for item in (attention.get("items") or [])]
    for item in items:
        item["recommended_action"] = marker_text
    attention["items"] = items
    status["attention_queue"] = attention

    run_history = dict(status.get("run_history") or {})
    goals = [dict(goal) for goal in (run_history.get("goals") or [])]
    for goal in goals:
        goal = dict(goal)
        latest_runs = [dict(run) for run in (goal.get("latest_runs") or [])]
        for run in latest_runs:
            run["recommended_action"] = marker_text
        goal["latest_runs"] = latest_runs
    run_history["goals"] = goals
    status["run_history"] = run_history

    agents = [
        dict(agent)
        for agent in (status.get("agent_management_projection") or {}).get("agents", [])
    ]
    for agent in agents:
        agent["next_action"] = marker_text
    status["agent_management_projection"] = {
        "schema_version": "agent_management_projection_v0",
        "mode": "read_only",
        "agents": agents,
    }
    return status


def _build_polluted_projection() -> dict[str, object]:
    status = _build_polluted_status_fixture()
    return build_session_dash_projection(
        status_payload=status,
        run_history=status.get("run_history"),
        todo_index=status.get("todo_index"),
        agent_management=status.get("agent_management_projection"),
        usage_summary=status.get("usage_summary"),
        generated_at="2026-07-06T10:20:00Z",
    )


def test_private_session_text_is_withheld_from_generated_html() -> None:
    projection = _build_polluted_projection()
    for html in (
        render_session_dash_html(projection),
        render_session_dash_main(projection),
    ):
        boundary = scan_public_boundary_text(html)
        assert boundary["ok"] is False, (
            "private next_action/session text must fail the boundary scan"
        )
        assert boundary["warnings"], "expected at least one boundary warning"
        for marker in PRIVATE_TRAP_MARKERS:
            assert marker in html, (
                f"trap marker must be present to keep the test honest: {marker}"
            )


def test_dash_generate_withholds_private_output_and_writes_no_file() -> None:
    import argparse
    import tempfile

    from loopx.cli_commands import dash as dash_module

    real_collect_status = dash_module.collect_status
    dash_module.collect_status = lambda **kwargs: _build_polluted_status_fixture()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "snap.html"
            captured: dict[str, object] = {}

            def print_payload(payload: dict[str, object], fmt: str, renderer: object) -> None:
                captured["payload"] = payload

            args = argparse.Namespace(
                command="dash",
                dash_command="generate",
                goal_id=None,
                out=str(out_path),
                no_boundary_scan=False,
            )
            rc = dash_module._handle_generate(
                args,
                registry_path=Path(tmp) / "registry.json",
                runtime_root_arg=None,
                print_payload=print_payload,
                output_format=lambda unused_args: "json",
            )
            assert rc == 1, "private output must fail the generate command"
            payload = captured["payload"]
            assert payload["ok"] is False
            assert payload["boundary_ok"] is False
            assert payload["write_performed"] is False
            for key in ("html", "html_path", "projection"):
                assert key not in payload, f"private output leaked via payload.{key}"
            assert not out_path.exists(), (
                "--out file must not be written when the boundary scan fails"
            )
    finally:
        dash_module.collect_status = real_collect_status


def test_live_server_withholds_private_endpoints() -> None:
    import io

    import loopx.dash_server as dash_server_module
    from loopx.dash_server import DashRequestHandler

    class _StubDashServer:
        registry_path = None
        runtime_root_override = None
        scan_roots = []
        goal_id = None
        refresh_seconds = 10
        verbose = False

    class _FakeConnection:
        def __init__(self, request_line: bytes) -> None:
            self._in = io.BytesIO(request_line)
            self._out = io.BytesIO()

        def makefile(self, mode: str, *args: object) -> io.BytesIO:
            return self._in if "r" in mode else self._out

        def sendall(self, data: bytes) -> None:
            self._out.write(data)

        def close(self) -> None:
            pass

    def _request(path: str) -> str:
        conn = _FakeConnection(
            f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("ascii")
        )
        DashRequestHandler(conn, ("127.0.0.1", 0), _StubDashServer())
        return conn._out.getvalue().decode("utf-8", "replace")

    real_collect_status = dash_server_module.collect_status
    try:
        dash_server_module.collect_status = (
            lambda **kwargs: _build_polluted_status_fixture()
        )
        for path in ("/", "/panel", "/status.json"):
            body = _request(path)
            status_line = body.split("\r\n", 1)[0]
            assert "500" in status_line, f"{path} must withhold private output"
            assert "withheld" in body, f"{path} must explain the withhold"
        dash_server_module.collect_status = lambda **kwargs: _build_fleet_fixture()
        for path in ("/", "/panel", "/status.json"):
            body = _request(path)
            status_line = body.split("\r\n", 1)[0]
            assert "200" in status_line, (
                f"{path} must serve clean output: {status_line}"
            )
    finally:
        dash_server_module.collect_status = real_collect_status


if __name__ == "__main__":
    test_projection_is_read_only_and_fleet_shaped()
    test_focus_goal_id_narrows_the_fleet()
    test_html_renders_human_focused_sections()
    test_html_escapes_and_passes_boundary_scan()
    test_boundary_scan_flags_private_material()
    test_escape_prevents_injection()
    test_live_serve_page_has_refresh_and_fragment()
    test_live_server_handler_is_read_only()
    test_private_session_text_is_withheld_from_generated_html()
    test_dash_generate_withholds_private_output_and_writes_no_file()
    test_live_server_withholds_private_endpoints()
    print("session dash panel smoke: OK")
