#!/usr/bin/env python3
"""Render a static Goal Harness status dashboard from JSON output.

Usage:
  goal-harness --format json status > /tmp/goal-status.json
  python3 examples/render-status-dashboard.py /tmp/goal-status.json /tmp/goal-status.html
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


LANES = [
    ("user", "User / Controller", {"user_or_controller", "controller"}),
    ("codex", "Codex Ready", {"codex"}),
    ("watch", "Watching Evidence", {"external_evidence"}),
]


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_status(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("status JSON must be an object")
    return payload


def queue_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    queue = payload.get("attention_queue")
    if not isinstance(queue, dict):
        return []
    items = queue.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def recent_runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    history = payload.get("run_history")
    if not isinstance(history, dict):
        return []
    runs = history.get("recent_runs")
    if not isinstance(runs, list):
        return []
    return [run for run in runs if isinstance(run, dict)]


def severity_class(item: dict[str, Any]) -> str:
    severity = str(item.get("severity") or "action")
    return severity if severity in {"high", "action", "watch"} else "action"


def render_item(item: dict[str, Any]) -> str:
    status = esc(item.get("status"))
    waiting = esc(item.get("waiting_on"))
    source = esc(item.get("source"))
    action = esc(item.get("recommended_action"))
    missing = item.get("missing_gates") if isinstance(item.get("missing_gates"), list) else []
    missing_text = ", ".join(esc(gate) for gate in missing if gate)
    gate_block = ""
    if item.get("controller_stage") or missing_text or item.get("next_handoff_condition"):
        gate_block = f"""
          <div class="gate-summary">
            <strong>{esc(item.get("controller_stage"))}</strong>
            <span>{missing_text}</span>
            <p>{esc(item.get("next_handoff_condition"))}</p>
          </div>
        """
    return f"""
        <article class="item {severity_class(item)}">
          <div class="item-top">
            <h3>{esc(item.get("goal_id"))}</h3>
            <span>{esc(item.get("severity"))}</span>
          </div>
          <dl>
            <dt>Status</dt><dd>{status}</dd>
            <dt>Waiting</dt><dd>{waiting}</dd>
            <dt>Source</dt><dd>{source}</dd>
          </dl>
          <p>{action}</p>
          {gate_block}
        </article>
    """


def render_run(run: dict[str, Any]) -> str:
    reward = run.get("human_reward") if isinstance(run.get("human_reward"), dict) else {}
    readiness = run.get("controller_readiness") if isinstance(run.get("controller_readiness"), dict) else {}
    reward_block = ""
    if reward:
        reward_block = f"""
          <div class="reward">
            <strong>Human reward</strong>
            <span>{esc(reward.get("decision"))} · {esc(reward.get("reward"))}</span>
            <p>{esc(reward.get("reason_summary"))}</p>
          </div>
        """
    readiness_block = ""
    if readiness:
        gates = readiness.get("gates") if isinstance(readiness.get("gates"), list) else []
        gate_rows = "\n".join(
            f"<li>{'PASS' if gate.get('ok') else 'MISS'} · {esc(gate.get('id'))}: {esc(gate.get('review'))}</li>"
            for gate in gates
            if isinstance(gate, dict)
        )
        readiness_block = f"""
          <div class="readiness">
            <strong>Controller readiness</strong>
            <span>{esc(readiness.get("classification"))}</span>
            <p>{esc(readiness.get("review_judgment"))}</p>
            <ul>{gate_rows}</ul>
          </div>
        """
    return f"""
        <article class="run">
          <div class="item-top">
            <h3>{esc(run.get("goal_id"))}</h3>
            <span>{esc(run.get("health_check"))}</span>
          </div>
          <dl>
            <dt>Run</dt><dd>{esc(run.get("generated_at"))}</dd>
            <dt>Class</dt><dd>{esc(run.get("classification"))}</dd>
            <dt>Files</dt><dd>{esc(run.get("json_exists"))}/{esc(run.get("markdown_exists"))}</dd>
          </dl>
          <p>{esc(run.get("recommended_action"))}</p>
          {readiness_block}
          {reward_block}
        </article>
    """


def render_lane(title: str, waiting_values: set[str], items: list[dict[str, Any]]) -> str:
    lane_items = [item for item in items if str(item.get("waiting_on")) in waiting_values]
    body = "\n".join(render_item(item) for item in lane_items)
    if not body:
        body = '<p class="empty">No goals in this lane.</p>'
    return f"""
      <section class="lane">
        <header>
          <h2>{esc(title)}</h2>
          <strong>{len(lane_items)}</strong>
        </header>
        {body}
      </section>
    """


def render_dashboard(payload: dict[str, Any]) -> str:
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    queue = payload.get("attention_queue") if isinstance(payload.get("attention_queue"), dict) else {}
    items = queue_items(payload)
    lanes = "\n".join(render_lane(title, values, items) for _, title, values in LANES)
    runs = recent_runs(payload)
    run_details = "\n".join(render_run(run) for run in runs[:5])
    if not run_details:
        run_details = '<p class="empty">No recent runs.</p>'
    errors = contract.get("errors") if isinstance(contract.get("errors"), list) else []
    warnings = contract.get("warnings") if isinstance(contract.get("warnings"), list) else []
    checks = contract.get("checks") if isinstance(contract.get("checks"), list) else []

    def render_health_column(title: str, entries: list[Any], empty: str) -> str:
        rows = "\n".join(f"<li>{esc(entry)}</li>" for entry in entries)
        if not rows:
            rows = f"<li class=\"empty-row\">{esc(empty)}</li>"
        return f"""
          <div class="health-column">
            <div class="health-column-top">
              <h3>{esc(title)}</h3>
              <strong>{len(entries)}</strong>
            </div>
            <ul>{rows}</ul>
          </div>
        """

    health_details = "\n".join(
        [
            render_health_column("Errors", errors, "No blocking errors"),
            render_health_column("Warnings", warnings, "No warnings"),
            render_health_column("Checks", checks, "No recent checks"),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Goal Harness Status</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #101014;
      --muted: #667085;
      --line: #d9dee7;
      --panel: #ffffff;
      --green: #047857;
      --blue: #0369a1;
      --amber: #b45309;
      --red: #be123c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.45;
      -webkit-font-smoothing: antialiased;
    }}
    main {{
      width: min(1180px, calc(100vw - 32px));
      margin: 32px auto;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
      margin-bottom: 20px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 28px; font-weight: 720; }}
    .meta {{ color: var(--muted); margin-top: 6px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(88px, 1fr));
      gap: 10px;
      min-width: min(520px, 100%);
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .metric span {{ color: var(--muted); font-size: 12px; display: block; }}
    .metric strong {{ font-size: 22px; }}
    .lanes {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      align-items: start;
    }}
    .lane {{
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 220px;
    }}
    .lane header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .lane h2 {{ font-size: 16px; }}
    .lane header strong {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 28px;
      height: 28px;
      border-radius: 999px;
      background: var(--ink);
      color: white;
      font-size: 13px;
    }}
    .item {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 5px solid var(--blue);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 10px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .item.high {{ border-left-color: var(--red); }}
    .item.action {{ border-left-color: var(--amber); }}
    .item.watch {{ border-left-color: var(--green); }}
    .item-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .item h3 {{ font-size: 15px; overflow-wrap: anywhere; }}
    .item-top span {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    dl {{
      display: grid;
      grid-template-columns: 78px 1fr;
      gap: 4px 8px;
      margin: 10px 0;
      font-size: 13px;
    }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    .item p, .empty {{ color: var(--muted); font-size: 13px; }}
    .gate-summary {{
      margin-top: 10px;
      border: 1px solid #fed7aa;
      border-radius: 8px;
      background: #fff7ed;
      padding: 10px;
      color: #7c2d12;
      font-size: 12px;
    }}
    .gate-summary strong, .gate-summary span {{ display: block; overflow-wrap: anywhere; }}
    .gate-summary p {{ margin-top: 6px; color: #9a3412; }}
    .run-section {{
      margin-top: 18px;
    }}
    .run-section h2 {{
      font-size: 16px;
      margin: 0 0 10px;
    }}
    .runs {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .run {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .run p {{ color: var(--muted); font-size: 13px; }}
    .reward {{
      margin-top: 10px;
      border: 1px solid #a7f3d0;
      border-radius: 8px;
      background: #ecfdf5;
      padding: 10px;
      color: #064e3b;
      font-size: 13px;
    }}
    .reward strong, .reward span {{ display: block; }}
    .reward p {{ margin-top: 6px; color: #065f46; }}
    .readiness {{
      margin-top: 10px;
      border: 1px solid #bae6fd;
      border-radius: 8px;
      background: #f0f9ff;
      padding: 10px;
      color: #0c4a6e;
      font-size: 13px;
    }}
    .readiness strong, .readiness span {{ display: block; }}
    .readiness p {{ margin-top: 6px; color: #075985; }}
    .readiness ul {{ margin: 8px 0 0; padding-left: 18px; }}
    .health {{
      margin-top: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .health-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }}
    .health h2, .health h3 {{ font-size: 16px; margin: 0; }}
    .health-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .health-column {{ padding: 14px; border-right: 1px solid var(--line); }}
    .health-column:last-child {{ border-right: 0; }}
    .health-column-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .health-column-top h3 {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .health-column-top strong {{
      color: var(--muted);
      font-size: 13px;
    }}
    .health ul {{ margin: 0; padding-left: 18px; color: var(--muted); }}
    .health li {{ margin: 6px 0; overflow-wrap: anywhere; }}
    .empty-row {{ list-style: none; margin-left: -18px; }}
    @media (max-width: 860px) {{
      .topbar {{ display: block; }}
      .summary {{ margin-top: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .lanes {{ grid-template-columns: 1fr; }}
      .runs {{ grid-template-columns: 1fr; }}
      .health-grid {{ grid-template-columns: 1fr; }}
      .health-column {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .health-column:last-child {{ border-bottom: 0; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="topbar">
      <div>
        <h1>Goal Harness Status</h1>
        <p class="meta">Registry: {esc(payload.get("registry"))}</p>
        <p class="meta">Runtime: {esc(payload.get("runtime_root"))}</p>
      </div>
      <div class="summary">
        <div class="metric"><span>OK</span><strong>{esc(payload.get("ok"))}</strong></div>
        <div class="metric"><span>Goals</span><strong>{esc(payload.get("goal_count"))}</strong></div>
        <div class="metric"><span>Runs</span><strong>{esc(payload.get("run_count"))}</strong></div>
        <div class="metric"><span>Queue</span><strong>{esc(queue.get("item_count"))}</strong></div>
      </div>
    </section>
    <section class="lanes">
      {lanes}
    </section>
    <section class="run-section">
      <h2>Recent Runs</h2>
      <div class="runs">{run_details}</div>
    </section>
    <section class="health">
      <div class="health-head">
        <h2>Contract Health</h2>
        <p class="meta">ok={esc(contract.get("ok"))}, errors={esc(summary.get("errors"))}, warnings={esc(summary.get("warnings"))}, checks={esc(summary.get("checks"))}</p>
      </div>
      <div class="health-grid">{health_details}</div>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Goal Harness status JSON as a static HTML dashboard.")
    parser.add_argument("status_json", help="Path to goal-harness --format json status output.")
    parser.add_argument("output_html", help="Path to write the rendered dashboard HTML.")
    args = parser.parse_args()

    payload = load_status(Path(args.status_json))
    output = Path(args.output_html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(payload), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
