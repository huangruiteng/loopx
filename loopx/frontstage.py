from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence


GOAL_CHANNEL_PROJECTION_SCHEMA_VERSION = "goal_channel_projection_v0"

RAW_MATERIAL_KEY_HINTS = (
    "credential",
    "local_path",
    "log",
    "raw",
    "secret",
    "stderr",
    "stdout",
    "token",
    "trace",
    "transcript",
)

PRIVATE_VALUE_HINTS = (
    "/private/",
    "/users/",
    "credential" + "-value",
    "secret" + "-value",
    "token" + "-value",
)


def _as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_mappings(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if not values:
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _private_value(value: Any) -> bool:
    text = str(value).lower()
    private_doc_host = ".".join(("byte" + "dance", "lark" + "office"))
    return private_doc_host in text or any(hint in text for hint in PRIVATE_VALUE_HINTS)


def _text(value: Any, *, limit: int = 180) -> str | None:
    if value is None or _private_value(value):
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _raw_material_keys(*values: Any) -> list[str]:
    keys: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                lowered = str(key).lower()
                if any(hint in lowered for hint in RAW_MATERIAL_KEY_HINTS):
                    keys.add(str(key))
                if _private_value(child):
                    keys.add(str(key))
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for value in values:
        visit(value)
    return sorted(keys)


def _first_text(*values: Any, limit: int = 180) -> str | None:
    for value in values:
        text = _text(value, limit=limit)
        if text:
            return text
    return None


def _project_asset(status_item: Mapping[str, Any]) -> dict[str, Any]:
    asset = status_item.get("project_asset")
    return dict(asset) if isinstance(asset, Mapping) else {}


def _source_refs(
    *,
    status_payload: Mapping[str, Any],
    project_asset: Mapping[str, Any],
    run_history_goal: Mapping[str, Any],
    review_packet: Mapping[str, Any],
) -> dict[str, Any]:
    latest_runs = (
        run_history_goal.get("latest_runs")
        if isinstance(run_history_goal.get("latest_runs"), list)
        else []
    )
    latest_run = latest_runs[0] if latest_runs and isinstance(latest_runs[0], Mapping) else {}
    return {
        "status_generated_at": _first_text(
            status_payload.get("generated_at"),
            project_asset.get("status_generated_at"),
            limit=80,
        ),
        "active_state_updated_at": _first_text(
            project_asset.get("state_updated_at"),
            project_asset.get("active_state_updated_at"),
            status_payload.get("state_updated_at"),
            limit=80,
        ),
        "latest_run_generated_at": _first_text(latest_run.get("generated_at"), limit=80),
        "review_packet_generated_at": _first_text(
            review_packet.get("generated_at"),
            review_packet.get("created_at"),
            limit=80,
        ),
        "event_ledger_source": "run_history",
    }


def _compact_quota(quota_payload: Mapping[str, Any], project_asset: Mapping[str, Any]) -> dict[str, Any]:
    source = quota_payload.get("quota") if isinstance(quota_payload.get("quota"), Mapping) else {}
    if not source and isinstance(project_asset.get("quota"), Mapping):
        source = project_asset["quota"]
    compact: dict[str, Any] = {}
    for key in ("state", "reason", "spend_policy", "spent_slots", "allowed_slots"):
        value = _text(source.get(key), limit=220)
        if value is not None:
            compact[key] = value
    return compact


def _todo_candidates(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "first_open_items",
        "first_executable_items",
        "open_items",
        "backlog_items",
        "items",
    ):
        values = summary.get(key)
        if isinstance(values, list) and values:
            return [dict(item) for item in values if isinstance(item, Mapping)]
    return []


def _compact_todo(item: Mapping[str, Any]) -> dict[str, Any] | None:
    title = _first_text(item.get("title"), item.get("text"), limit=220)
    if not title:
        return None
    compact: dict[str, Any] = {
        "title": title,
        "status": _first_text(item.get("status"), limit=40) or "open",
    }
    for key in ("todo_id", "priority", "claimed_by", "task_class", "action_kind"):
        value = _text(item.get(key), limit=120)
        if value:
            compact[key] = value
    return compact


def _compact_todos(project_asset: Mapping[str, Any], role: str) -> list[dict[str, Any]]:
    summary = project_asset.get(f"{role}_todos")
    if not isinstance(summary, Mapping):
        return []
    compact: list[dict[str, Any]] = []
    for item in _todo_candidates(summary):
        todo = _compact_todo(item)
        if todo:
            compact.append(todo)
    return compact


def _open_gates(
    *,
    quota_payload: Mapping[str, Any],
    project_asset: Mapping[str, Any],
    user_todos: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    raw_gates = project_asset.get("open_gates")
    if isinstance(raw_gates, list):
        for gate in raw_gates:
            if not isinstance(gate, Mapping):
                continue
            status = _first_text(gate.get("status"), gate.get("state"), limit=80)
            if status in {None, "done", "closed", "resolved"}:
                continue
            compact = {
                "gate_id": _first_text(gate.get("gate_id"), gate.get("id"), limit=120)
                or "gate",
                "kind": _first_text(gate.get("kind"), gate.get("type"), limit=80)
                or "operator_gate",
                "status": status or "open",
            }
            blocks = gate.get("blocks")
            if isinstance(blocks, list):
                compact["blocks"] = [_text(item, limit=120) for item in blocks if _text(item, limit=120)]
            gates.append(compact)
    interaction = quota_payload.get("interaction_contract")
    user_channel = (
        interaction.get("user_channel")
        if isinstance(interaction, Mapping) and isinstance(interaction.get("user_channel"), Mapping)
        else {}
    )
    if user_channel.get("action_required") is True and not gates:
        gates.append(
            {
                "gate_id": "interaction_contract_user_channel",
                "kind": "user_channel",
                "status": "action_required",
                "blocks": [
                    str(todo.get("todo_id") or todo.get("title") or "user_todo")
                    for todo in user_todos
                ],
            }
        )
    return gates


def _active_leases(
    *,
    active_leases: Sequence[Mapping[str, Any]] | None,
    agent_todos: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    explicit = _as_mappings(active_leases)
    if explicit:
        source = explicit
    else:
        source = [
            {
                "todo_id": item.get("todo_id"),
                "owner_agent": item.get("claimed_by"),
                "status": "soft_claim",
            }
            for item in agent_todos
            if item.get("claimed_by")
        ]
    compact: list[dict[str, Any]] = []
    for item in source:
        todo_id = _text(item.get("todo_id"), limit=120)
        owner = _first_text(item.get("owner_agent"), item.get("claimed_by"), limit=120)
        if not (todo_id or owner):
            continue
        lease: dict[str, Any] = {}
        if todo_id:
            lease["todo_id"] = todo_id
        if owner:
            lease["owner_agent"] = owner
        for key in ("lease_until", "status"):
            value = _text(item.get(key), limit=120)
            if value:
                lease[key] = value
        write_scope = item.get("write_scope")
        if isinstance(write_scope, list):
            lease["write_scope"] = [
                scope
                for scope in (_text(value, limit=120) for value in write_scope)
                if scope
            ]
        compact.append(lease)
    return compact


def _compact_artifacts(artifacts: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in _as_mappings(artifacts):
        artifact: dict[str, Any] = {}
        for key in ("kind", "label", "path", "run_id"):
            value = _text(item.get(key), limit=160)
            if value:
                artifact[key] = value
        if artifact:
            compact.append(artifact)
    return compact


def _recent_events(run_history_goal: Mapping[str, Any]) -> list[dict[str, Any]]:
    runs = (
        run_history_goal.get("latest_runs")
        if isinstance(run_history_goal.get("latest_runs"), list)
        else []
    )
    events: list[dict[str, Any]] = []
    for run in runs[:5]:
        if not isinstance(run, Mapping):
            continue
        event: dict[str, Any] = {}
        for key in ("generated_at", "classification"):
            value = _text(run.get(key), limit=160)
            if value:
                event[key] = value
        summary = _first_text(run.get("health_check"), run.get("recommended_action"), limit=260)
        if summary:
            event["summary"] = summary
        if event:
            events.append(event)
    return events


def _source_warnings(raw_keys: Sequence[str]) -> list[dict[str, Any]]:
    if not raw_keys:
        return []
    return [
        {
            "kind": "raw_or_private_material_omitted",
            "key_names": list(raw_keys),
            "message": (
                "raw/private-looking fields were omitted; inspect the compact "
                "source references instead of copying raw material into the "
                "frontstage channel projection"
            ),
        }
    ]


def _html_text(value: Any, *, fallback: str = "") -> str:
    text = _text(value, limit=500)
    return escape(text if text is not None else fallback)


def _html_attr(value: Any) -> str:
    return escape(str(value), quote=True)


def _html_dict_list(items: Sequence[Mapping[str, Any]], *, keys: Sequence[str]) -> str:
    rows: list[str] = []
    for item in items:
        cells = []
        for key in keys:
            value = item.get(key)
            if value in (None, "", []):
                continue
            cells.append(
                f"<dt>{_html_text(key.replace('_', ' ').title())}</dt>"
                f"<dd>{_html_text(value)}</dd>"
            )
        if cells:
            rows.append("<li><dl>" + "".join(cells) + "</dl></li>")
    return "\n".join(rows)


def _html_panel(
    *,
    panel: str,
    title: str,
    body: str,
    tone: str = "neutral",
) -> str:
    return (
        f'<section class="panel panel-{_html_attr(tone)}" data-panel="{_html_attr(panel)}">'
        f"<h2>{_html_text(title)}</h2>"
        f"{body}"
        "</section>"
    )


def _html_kv_panel(panel: str, title: str, values: Mapping[str, Any], *, tone: str = "neutral") -> str:
    pairs = []
    for key, value in values.items():
        if value in (None, "", []):
            continue
        pairs.append(
            f"<dt>{_html_text(str(key).replace('_', ' ').title())}</dt>"
            f"<dd>{_html_text(value)}</dd>"
        )
    body = "<dl>" + "".join(pairs) + "</dl>" if pairs else '<p class="empty">No compact fields.</p>'
    return _html_panel(panel=panel, title=title, body=body, tone=tone)


def _html_item_panel(
    panel: str,
    title: str,
    items: Sequence[Mapping[str, Any]],
    *,
    keys: Sequence[str],
    empty: str,
    tone: str = "neutral",
) -> str:
    if items:
        body = "<ol>" + _html_dict_list(items, keys=keys) + "</ol>"
    else:
        body = f'<p class="empty">{_html_text(empty)}</p>'
    return _html_panel(panel=panel, title=title, body=body, tone=tone)


def build_goal_channel_projection(
    *,
    goal_id: str,
    status_item: Mapping[str, Any] | None = None,
    status_payload: Mapping[str, Any] | None = None,
    quota_payload: Mapping[str, Any] | None = None,
    run_history_goal: Mapping[str, Any] | None = None,
    review_packet: Mapping[str, Any] | None = None,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    active_leases: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a read-only channel snapshot for a LoopX goal.

    The returned object is a frontstage projection, not a new source of truth.
    It summarizes existing compact status/quota/history/todo surfaces and
    records raw/private-looking inputs as warnings without copying their values.
    """

    status_item_dict = _as_mapping(status_item)
    status_payload_dict = _as_mapping(status_payload)
    quota_payload_dict = _as_mapping(quota_payload)
    run_history_goal_dict = _as_mapping(run_history_goal)
    review_packet_dict = _as_mapping(review_packet)
    project_asset = _project_asset(status_item_dict)
    user_todos = _compact_todos(project_asset, "user")
    agent_todos = _compact_todos(project_asset, "agent")
    raw_keys = _raw_material_keys(
        status_item_dict,
        status_payload_dict,
        quota_payload_dict,
        run_history_goal_dict,
        review_packet_dict,
        artifacts or [],
        active_leases or [],
    )

    interaction = quota_payload_dict.get("interaction_contract")
    user_channel = (
        interaction.get("user_channel")
        if isinstance(interaction, Mapping) and isinstance(interaction.get("user_channel"), Mapping)
        else {}
    )
    agent_channel = (
        interaction.get("agent_channel")
        if isinstance(interaction, Mapping) and isinstance(interaction.get("agent_channel"), Mapping)
        else {}
    )

    projection = {
        "schema_version": GOAL_CHANNEL_PROJECTION_SCHEMA_VERSION,
        "goal_id": str(goal_id),
        "mode": "read_only",
        "generated_at": _text(generated_at, limit=80),
        "display_name": _first_text(
            project_asset.get("display_name"),
            status_item_dict.get("display_name"),
            status_item_dict.get("domain"),
            goal_id,
            limit=120,
        ),
        "source_refs": _source_refs(
            status_payload=status_payload_dict,
            project_asset=project_asset,
            run_history_goal=run_history_goal_dict,
            review_packet=review_packet_dict,
        ),
        "waiting_on": _first_text(
            status_item_dict.get("waiting_on"),
            quota_payload_dict.get("waiting_on"),
            limit=80,
        ),
        "latest_status": _first_text(
            status_item_dict.get("status"),
            quota_payload_dict.get("status"),
            limit=160,
        ),
        "next_action": _first_text(
            quota_payload_dict.get("recommended_action"),
            project_asset.get("next_action"),
            status_item_dict.get("recommended_action"),
            limit=260,
        ),
        "decision_frame": {
            "user_action_required": bool(user_channel.get("action_required")),
            "agent_action_required": bool(agent_channel.get("must_attempt")),
            "quiet_noop_allowed": bool(agent_channel.get("quiet_noop_allowed")),
        },
        "quota": _compact_quota(quota_payload_dict, project_asset),
        "user_todos": user_todos,
        "agent_todos": agent_todos,
        "open_gates": _open_gates(
            quota_payload=quota_payload_dict,
            project_asset=project_asset,
            user_todos=user_todos,
        ),
        "artifacts": _compact_artifacts(artifacts),
        "active_leases": _active_leases(
            active_leases=active_leases,
            agent_todos=agent_todos,
        ),
        "recent_events": _recent_events(run_history_goal_dict),
        "source_warnings": _source_warnings(raw_keys),
        "truth_contract": {
            "event_ledger_is_source_of_truth": True,
            "projection_is_writable": False,
            "write_authority": "none",
            "recompute_rule": (
                "refresh from LoopX status/quota/run history; do not "
                "edit the channel projection as project truth"
            ),
        },
    }
    return {key: value for key, value in projection.items() if value is not None}


def render_goal_channel_projection_html(projection: Mapping[str, Any]) -> str:
    """Render a read-only static HTML fixture for a channel projection.

    This renderer is intentionally presentation-only. It accepts an already
    compact projection, exposes source warnings, and avoids form/button/write
    controls so dashboard prototypes can validate the frontstage shape without
    becoming a second source of truth.
    """

    if projection.get("schema_version") != GOAL_CHANNEL_PROJECTION_SCHEMA_VERSION:
        raise ValueError("unsupported goal channel projection schema_version")
    if projection.get("mode") != "read_only":
        raise ValueError("goal channel projection renderer only accepts read_only mode")

    goal_id = projection.get("goal_id") or "goal"
    display_name = projection.get("display_name") or goal_id
    decision_frame = _as_mapping(projection.get("decision_frame"))
    quota = _as_mapping(projection.get("quota"))
    source_refs = _as_mapping(projection.get("source_refs"))
    truth_contract = _as_mapping(projection.get("truth_contract"))
    user_todos = _as_mappings(projection.get("user_todos"))
    agent_todos = _as_mappings(projection.get("agent_todos"))
    open_gates = _as_mappings(projection.get("open_gates"))
    artifacts = _as_mappings(projection.get("artifacts"))
    active_leases = _as_mappings(projection.get("active_leases"))
    recent_events = _as_mappings(projection.get("recent_events"))
    source_warnings = _as_mappings(projection.get("source_warnings"))

    panels = [
        _html_kv_panel("decision-frame", "Decision Frame", decision_frame, tone="blue"),
        _html_kv_panel("quota", "Quota Guard", quota, tone="purple"),
        _html_item_panel(
            "user-todos",
            "User Todos",
            user_todos,
            keys=("priority", "status", "todo_id", "title"),
            empty="No open user todo projected.",
            tone="orange",
        ),
        _html_item_panel(
            "agent-todos",
            "Agent Todos",
            agent_todos,
            keys=("priority", "status", "claimed_by", "todo_id", "title"),
            empty="No open agent todo projected.",
            tone="green",
        ),
        _html_item_panel(
            "open-gates",
            "Open Gates",
            open_gates,
            keys=("kind", "status", "gate_id", "blocks"),
            empty="No open gate projected.",
            tone="orange",
        ),
        _html_item_panel(
            "active-leases",
            "Claims And Leases",
            active_leases,
            keys=("status", "owner_agent", "todo_id", "lease_until", "write_scope"),
            empty="No active claim or lease projected.",
            tone="green",
        ),
        _html_item_panel(
            "artifacts",
            "Artifacts",
            artifacts,
            keys=("kind", "label", "path", "run_id"),
            empty="No public-safe artifact projected.",
        ),
        _html_item_panel(
            "recent-events",
            "Recent Events",
            recent_events,
            keys=("generated_at", "classification", "summary"),
            empty="No compact run event projected.",
        ),
        _html_item_panel(
            "source-warnings",
            "Source Warnings",
            source_warnings,
            keys=("kind", "key_names", "message"),
            empty="No source warning.",
            tone="red",
        ),
        _html_kv_panel("source-refs", "Source References", source_refs),
        _html_kv_panel("truth-contract", "Truth Contract", truth_contract, tone="blue"),
    ]

    css = """
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #111827;
    }
    body { margin: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }
    header { border-bottom: 1px solid #d7dde8; padding-bottom: 22px; margin-bottom: 24px; }
    h1 { font-size: 34px; line-height: 1.15; margin: 0 0 10px; letter-spacing: 0; }
    h2 { font-size: 18px; line-height: 1.25; margin: 0 0 16px; letter-spacing: 0; }
    p { color: #4b5563; margin: 0; line-height: 1.55; }
    code { background: #eef2ff; border-radius: 4px; padding: 2px 5px; }
    .meta { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .pill { border: 1px solid #cfd8e7; border-radius: 999px; color: #334155; padding: 6px 10px; font-size: 13px; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
    .panel { background: #ffffff; border: 1px solid #d8dee9; border-radius: 8px; padding: 18px; min-height: 160px; }
    .panel-blue { border-color: #3b82f6; background: #eff6ff; }
    .panel-green { border-color: #22c55e; background: #f0fdf4; }
    .panel-orange { border-color: #f59e0b; background: #fffbeb; }
    .panel-purple { border-color: #8b5cf6; background: #f5f3ff; }
    .panel-red { border-color: #f43f5e; background: #fff1f2; }
    ol { margin: 0; padding-left: 20px; display: grid; gap: 12px; }
    dl { display: grid; grid-template-columns: minmax(92px, 0.35fr) 1fr; gap: 7px 12px; margin: 0; }
    dt { color: #64748b; font-size: 13px; font-weight: 700; }
    dd { margin: 0; color: #1f2937; font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
    .empty { color: #64748b; }
    @media (max-width: 720px) {
      main { padding: 28px 16px 40px; }
      h1 { font-size: 28px; }
      dl { grid-template-columns: 1fr; }
    }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_text(display_name)} - Goal Channel Projection</title>
  <style>{css}</style>
</head>
<body>
  <main
    data-schema="{_html_attr(projection.get('schema_version'))}"
    data-mode="{_html_attr(projection.get('mode'))}"
    data-goal-id="{_html_attr(goal_id)}"
  >
    <header>
      <h1>{_html_text(display_name)}</h1>
      <p>{_html_text(projection.get('next_action'), fallback='No next action projected.')}</p>
      <div class="meta">
        <span class="pill">goal: <code>{_html_text(goal_id)}</code></span>
        <span class="pill">status: {_html_text(projection.get('latest_status'), fallback='unknown')}</span>
        <span class="pill">waiting on: {_html_text(projection.get('waiting_on'), fallback='unknown')}</span>
        <span class="pill">generated: {_html_text(projection.get('generated_at'), fallback='unknown')}</span>
      </div>
    </header>
    <div class="grid">
      {"".join(panels)}
    </div>
  </main>
</body>
</html>
"""
