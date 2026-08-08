"""Render the session dash projection as one self-contained HTML page.

This renderer is presentation-only and intentionally mirrors the goal channel
HTML renderer: it accepts an already-compact projection, escapes all text, and
avoids form/button/write controls so the generated page stays a read-only
snapshot instead of a second source of truth.

The page shows only what an operator needs to follow task progress: an
overview of the fleet, then one card per session (agent runtime) with the
goals it owns and each goal's status, todo progress, waiting reason, and
latest run evidence. Internal control machinery is not rendered.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping

from ..projections.session_dash import SESSION_DASH_PROJECTION_SCHEMA_VERSION

_BUCKET_LABELS = {
    "active": "Active",
    "needs_user": "Needs you",
    "blocked": "Blocked",
    "done": "Done",
    "other": "Other",
}


def _as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_mappings(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _text(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return escape(text if text else fallback)


def _attr(value: Any) -> str:
    return escape(str(value), quote=True)


def _badge(label: str, tone: str) -> str:
    return f'<span class="badge badge-{tone}">{_text(label)}</span>'


def _status_badge(entry: Mapping[str, Any]) -> str:
    bucket = str(entry.get("status_bucket") or "other")
    tone = {
        "active": "green",
        "needs_user": "orange",
        "blocked": "red",
        "done": "blue",
    }.get(bucket, "gray")
    return _badge(_BUCKET_LABELS.get(bucket, bucket.title()), tone)


def _state_badge(state: str) -> str:
    tone = {
        "active": "green",
        "monitoring": "blue",
        "waiting": "orange",
        "blocked": "red",
    }.get(str(state or "").lower(), "gray")
    return _badge(state or "unknown", tone)


def _progress_bar(entry: Mapping[str, Any]) -> str:
    done = int(entry.get("done_todos") or 0)
    open_agent = int(entry.get("open_agent_todos") or 0)
    open_user = int(entry.get("open_user_todos") or 0)
    total = done + open_agent + open_user
    if total == 0:
        return '<span class="muted">no todos</span>'
    percent = round(done * 100 / total)
    caption = (
        f"<span class=\"muted\">{done} done · {open_agent} agent · "
        f"{open_user} user</span>"
    )
    return (
        f'<div class="bar" role="progressbar" aria-valuenow="{percent}" '
        f'aria-valuemin="0" aria-valuemax="100">'
        f'<div class="bar-fill" style="width:{percent}%"></div></div>'
        f'<div class="bar-caption">{caption}</div>'
    )


def _goal_rows(goals: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for entry in goals:
        goal_id = _text(entry.get("goal_id"), fallback="goal")
        name = _text(entry.get("display_name"), fallback=goal_id)
        lifecycle = _text(entry.get("lifecycle_phase"))
        domain = _text(entry.get("domain"))
        sub = []
        if goal_id != name:
            sub.append(goal_id)
        if domain and domain != name:
            sub.append(domain)
        if lifecycle:
            sub.append(lifecycle)
        sub_html = (
            '<div class="goal-sub"><code>' + '</code> · <code>'.join(
                _text(part) for part in sub
            ) + '</code></div>' if sub else ""
        )
        waiting = _text(entry.get("waiting_on"), fallback="auto")
        latest = _text(entry.get("latest_run_at"), fallback="—")
        action = _text(entry.get("next_action"), fallback="—")
        rows.append(
            f'<tr data-goal-id="{_attr(entry.get("goal_id"))}">'
            f'<td class="goal-name"><div class="goal-title">{name}</div>'
            f"{sub_html}</td>"
            f'<td>{_status_badge(entry)}</td>'
            f"<td>{_progress_bar(entry)}</td>"
            f'<td><span class="waiting">{_text(waiting)}</span></td>'
            f"<td><span class=\"muted\">{latest}</span></td>"
            f'<td class="action">{action}</td>'
            f"</tr>"
        )
    if not rows:
        return '<tr><td colspan="6" class="empty">No goals projected.</td></tr>'
    return "".join(rows)


def _session_card(session: Mapping[str, Any]) -> str:
    goals = _as_mappings(session.get("goals"))
    session_id = _text(session.get("session_id"), fallback="session")
    role = _text(session.get("role"))
    model = _text(session.get("agent_model"))
    state = str(session.get("state") or "unknown")
    goal_count = int(session.get("goal_count") or len(goals))
    next_action = _text(session.get("next_action"))
    last_activity = _text(session.get("last_activity_at"), fallback="—")
    header_meta = " · ".join(
        part for part in (role, model) if part
    )
    action_line = (
        f'<p class="session-action">Next: {next_action}</p>' if next_action else ""
    )
    return (
        f'<article class="session-card" data-session-id="{_attr(session.get("session_id"))}">'
        f'<header class="session-head">'
        f"<div><h3 class=\"session-name\">{session_id}</h3>"
        f"{action_line}"
        f'<p class="session-meta">{_text(header_meta)} · last activity {last_activity}</p></div>'
        f'<div class="session-badges">'
        f"{_state_badge(state)}"
        f'<span class="pill">goals: {goal_count}</span>'
        f"</div></header>"
        f'<div class="table-wrap"><table class="goals">'
        f"<thead><tr><th>Goal</th><th>Status</th><th>Progress</th>"
        f"<th>Waiting on</th><th>Last run</th><th>Next action</th></tr></thead>"
        f"<tbody>{_goal_rows(goals)}</tbody></table></div>"
        f"</article>"
    )


def _render_overview(projection: Mapping[str, Any]) -> str:
    overview = _as_mapping(projection.get("overview"))
    by_status = _as_mapping(overview.get("goals_by_status"))

    def stat(label: str, value: Any) -> str:
        return (
            f'<div class="stat"><div class="stat-value">{_text(value)}</div>'
            f'<div class="stat-label">{_text(label)}</div></div>'
        )

    bucket = by_status or {}
    return (
        f'<section class="stats" data-panel="overview">'
        f"{stat('Sessions', overview.get('session_count'))}"
        f"{stat('Goals', overview.get('goal_count'))}"
        f"{stat('Active', bucket.get('active', 0))}"
        f"{stat('Needs you', bucket.get('needs_user', 0))}"
        f"{stat('Blocked', bucket.get('blocked', 0))}"
        f"{stat('Done', bucket.get('done', 0))}"
        f"{stat('Open todos', overview.get('open_agent_todos'))}"
        f"{stat('Runs 24h', overview.get('runs_24h'))}"
        f"</section>"
    )


def render_session_dash_main(projection: Mapping[str, Any]) -> str:
    """Render only the ``<main>`` content of the session dash page.

    Used by the live server's ``/panel`` endpoint so the page can refresh its
    panels in place without a full reload.
    """

    _validate_projection(projection)
    return _render_main(projection)


def render_session_dash_html(
    projection: Mapping[str, Any],
    *,
    live_refresh_seconds: int | None = None,
) -> str:
    """Render a read-only static HTML page for a session dash projection.

    When ``live_refresh_seconds`` is set, the page embeds a small polling
    script that re-fetches the ``/panel`` fragment from the serving loopback
    server and swaps it in place, so the operator can keep the panel open and
    watch session task progress without reloading the tab.
    """

    _validate_projection(projection)

    css = """
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f1f5f9;
      color: #0f172a;
    }
    body { margin: 0; }
    main { max-width: 1080px; margin: 0 auto; padding: 36px 22px 64px; }
    header.hero { border-bottom: 1px solid #e2e8f0; padding-bottom: 22px; margin-bottom: 22px; }
    h1 { font-size: 30px; line-height: 1.15; margin: 0 0 6px; letter-spacing: -0.02em; }
    h2 { font-size: 17px; line-height: 1.25; margin: 0 0 14px; letter-spacing: -0.01em; }
    h3 { font-size: 15px; line-height: 1.25; margin: 0; }
    .subtitle { color: #64748b; margin: 0 0 14px; font-size: 14px; }
    p { color: #475569; margin: 0; line-height: 1.55; }
    code { background: #e2e8f0; border-radius: 4px; padding: 1px 5px; font-size: 12px; color: #334155; }
    .meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .pill { border: 1px solid #cbd5e1; border-radius: 999px; color: #334155; background: #ffffff; padding: 4px 10px; font-size: 12px; }
    .pill-live { border-color: #86efac; background: #f0fdf4; color: #15803d; }

    .stats { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); margin-bottom: 24px; }
    .stat { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; }
    .stat-value { font-size: 26px; font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; }
    .stat-label { color: #64748b; font-size: 12px; font-weight: 600; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }

    .session-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 18px; overflow: hidden; }
    .session-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 16px 18px; border-bottom: 1px solid #eef2f7; }
    .session-name { font-weight: 700; font-size: 16px; }
    .session-meta { color: #94a3b8; font-size: 12px; margin-top: 4px; }
    .session-action { color: #475569; font-size: 13px; margin-top: 6px; }
    .session-badges { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

    .badge { border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 600; white-space: nowrap; }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-orange { background: #ffedd5; color: #9a3412; }
    .badge-red { background: #ffe4e6; color: #be123c; }
    .badge-blue { background: #e0e7ff; color: #3730a3; }
    .badge-gray { background: #f1f5f9; color: #475569; }

    .table-wrap { overflow-x: auto; }
    table.goals { width: 100%; border-collapse: collapse; font-size: 13px; }
    .goals th { text-align: left; color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 18px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
    .goals td { padding: 12px 18px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .goals tr:last-child td { border-bottom: none; }
    .goal-title { font-weight: 600; color: #0f172a; }
    .goal-sub { margin-top: 3px; font-size: 12px; color: #94a3b8; }
    .goal-sub code { background: none; padding: 0; color: #64748b; }
    .waiting { font-weight: 600; color: #475569; }
    .action { max-width: 300px; color: #475569; }
    .muted { color: #94a3b8; }
    .empty { color: #94a3b8; padding: 14px 18px; }

    .bar { height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; width: 120px; }
    .bar-fill { height: 100%; background: #22c55e; border-radius: 999px; }
    .bar-caption { margin-top: 4px; font-size: 11px; color: #64748b; }

    section.section-title { margin: 26px 0 12px; display: flex; align-items: baseline; gap: 10px; }
    section.section-title h2 { margin: 0; }
    section.section-title .count { color: #94a3b8; font-size: 13px; }
    @media (max-width: 760px) {
      main { padding: 24px 12px 44px; }
      h1 { font-size: 24px; }
      .session-head { flex-direction: column; }
      .action { max-width: none; }
    }
    """

    refresh_script = ""
    if live_refresh_seconds and live_refresh_seconds > 0:
        refresh_script = f"""
  <script>
    const refreshSeconds = {int(live_refresh_seconds)};
    async function refreshDash() {{
      try {{
        const res = await fetch('panel');
        if (!res.ok) return;
        const html = await res.text();
        const next = document.createElement('main');
        next.innerHTML = html;
        const current = document.querySelector('main');
        if (current && next.querySelector('[data-panel]')) {{
          current.innerHTML = next.innerHTML;
        }}
      }} catch (e) {{ /* keep the last good view */ }}
    }}
    setInterval(refreshDash, refreshSeconds * 1000);
  </script>
"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LoopX Session Dashboard</title>
  <style>{css}</style>
</head>
<body>
{render_session_dash_main(projection)}
{refresh_script}
</body>
</html>
"""


def _validate_projection(projection: Mapping[str, Any]) -> None:
    if projection.get("schema_version") != SESSION_DASH_PROJECTION_SCHEMA_VERSION:
        raise ValueError("unsupported session dash projection schema_version")
    if projection.get("mode") != "read_only":
        raise ValueError("session dash renderer only accepts read_only mode")


def _render_main(projection: Mapping[str, Any]) -> str:
    """Render the ``<main>`` block shared by the full page and live fragment."""

    sessions = _as_mappings(projection.get("sessions"))
    unassigned = _as_mappings(projection.get("unassigned_goals"))
    generated = _text(projection.get("generated_at"), fallback="unknown")
    focus = _text(projection.get("focus_goal_id"))

    session_sections: list[str] = []
    if sessions:
        session_sections.append(
            f'<section class="section-title" data-panel="sessions-head"><h2>Sessions</h2>'
            f'<span class="count">{len(sessions)}</span></section>'
        )
        session_sections.append(
            '<section data-panel="sessions">'
            + "".join(_session_card(session) for session in sessions)
            + "</section>"
        )
    else:
        session_sections.append(
            '<section class="session-card" data-panel="sessions">'
            '<div class="empty" style="padding:18px">No sessions projected.</div></section>'
        )

    unassigned_section = ""
    if unassigned and not focus:
        unassigned_section = (
            f'<section class="section-title" data-panel="unassigned-head"><h2>Goals without a session</h2>'
            f'<span class="count">{len(unassigned)}</span></section>'
            f'<section class="session-card" data-panel="unassigned"><div class="table-wrap">'
            f'<table class="goals"><thead><tr><th>Goal</th><th>Status</th><th>Progress</th>'
            f"<th>Waiting on</th><th>Last run</th><th>Next action</th></tr></thead>"
            f'<tbody>{_goal_rows(unassigned)}</tbody></table></div></section>'
        )

    focus_pill = (
        f'<span class="pill">focus: <code>{focus}</code></span>' if focus else ""
    )
    return f"""<main
    data-schema="{_attr(projection.get('schema_version'))}"
    data-mode="{_attr(projection.get('mode'))}"
  >
    <header class="hero">
      <h1>LoopX Session Dashboard</h1>
      <p class="subtitle">Live progress and results across agent sessions</p>
      <div class="meta">
        <span class="pill">updated {generated}</span>
        <span class="pill pill-live">live · read-only</span>
        {focus_pill}
      </div>
    </header>
    {_render_overview(projection)}
    {''.join(session_sections)}
    {unassigned_section}
  </main>
"""
