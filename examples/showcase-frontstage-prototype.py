#!/usr/bin/env python3
"""Render a static public showcase frontstage from the showcase catalog."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"

STATUS_LABELS = {
    "reproducible_synthetic_demo": "Reproducible demo",
    "public_evidence_case": "Public evidence",
    "public_safe_case_spec": "Case spec",
    "redacted_stub_pending_contributor_details": "Redacted stub",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def repo_link(repo_relative: str, *, output: Path | None) -> str:
    if output is None:
        return repo_relative
    target = (REPO_ROOT / repo_relative).resolve()
    base = output.resolve().parent
    return os.path.relpath(target, base).replace(os.sep, "/")


def render_badges(values: list[Any]) -> str:
    return "".join(f"<span>{esc(value)}</span>" for value in values)


def format_range(value: dict[str, Any] | None, *, suffix: str = "") -> str:
    if not isinstance(value, dict):
        return ""
    low = value.get("low")
    high = value.get("high")
    if low is None or high is None:
        return ""
    if isinstance(low, float) or isinstance(high, float):
        return f"{esc(f'{float(low):.1f}')}-{esc(f'{float(high):.1f}')}{suffix}"
    return f"{esc(low)}-{esc(high)}{suffix}"


def render_efficiency_panel(case: dict[str, Any]) -> str:
    workload = case.get("workload_signal")
    if not isinstance(workload, dict):
        return ""
    model = workload.get("efficiency_model")
    if not isinstance(model, dict):
        return ""
    whole = workload.get("whole_repository") if isinstance(workload.get("whole_repository"), dict) else {}
    public_window = workload.get("public_window") if isinstance(workload.get("public_window"), dict) else {}
    baseline = model.get("estimated_developer_days")
    single = model.get("single_engineer_calendar_compression")
    team = model.get("two_person_team_calendar_compression")
    baseline_label = format_range(baseline, suffix="d")
    single_label = format_range(single, suffix="x")
    team_label = format_range(team, suffix="x")
    if not baseline_label or not single_label:
        return ""
    calendar_days = public_window.get("calendar_days")
    commit_count = whole.get("commit_count")
    claim_boundary = str(model.get("claim_boundary") or "directional public evidence")
    return f"""
        <section class="efficiency-panel" aria-label="Efficiency evidence model">
          <div class="efficiency-panel__header">
            <div>
              <span>Efficiency Evidence Model</span>
              <h4>Baseline vs actual public window</h4>
            </div>
            <strong>{single_label}</strong>
          </div>
          <div class="efficiency-grid">
            <div><strong>{esc(commit_count or "")}</strong><span>public commits</span></div>
            <div><strong>{esc(calendar_days or "")}d</strong><span>actual Git window</span></div>
            <div><strong>{baseline_label}</strong><span>AI-assisted baseline</span></div>
            <div><strong>{team_label}</strong><span>two-person lens</span></div>
          </div>
          <p>{esc(claim_boundary)}</p>
        </section>
    """


def search_blob(case: dict[str, Any]) -> str:
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    workload = case.get("workload_signal") if isinstance(case.get("workload_signal"), dict) else {}
    efficiency = workload.get("efficiency_model") if isinstance(workload.get("efficiency_model"), dict) else {}
    values: list[Any] = [
        case.get("id"),
        case.get("date"),
        case.get("title"),
        case.get("headline"),
        case.get("domain"),
        case.get("status"),
        case.get("user_value"),
        case.get("evidence_boundary"),
        frontend.get("primary_metric_hint"),
        efficiency.get("baseline"),
        efficiency.get("claim_boundary"),
    ]
    for key in ("audience", "pattern_tags", "loopx_behavior"):
        field = case.get(key)
        if isinstance(field, list):
            values.extend(field)
    for key in ("badges", "story_beats"):
        field = frontend.get(key)
        if isinstance(field, list):
            values.extend(field)
    return " ".join(str(value).lower() for value in values if value)


def render_status_filters(cases: list[dict[str, Any]]) -> str:
    statuses = sorted({str(case.get("status") or "") for case in cases if case.get("status")})
    buttons = ['<button type="button" data-status-filter="all" aria-pressed="true">All cases</button>']
    for status in statuses:
        label = STATUS_LABELS.get(status, status.replace("_", " "))
        buttons.append(
            f'<button type="button" data-status-filter="{esc(status)}" aria-pressed="false">{esc(label)}</button>'
        )
    return "\n          ".join(buttons)


def render_case(case: dict[str, Any], *, output: Path | None) -> str:
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    badges = frontend.get("badges") if isinstance(frontend.get("badges"), list) else []
    tags = case.get("pattern_tags") if isinstance(case.get("pattern_tags"), list) else []
    story_beats = frontend.get("story_beats") if isinstance(frontend.get("story_beats"), list) else []
    behavior = case.get("loopx_behavior") if isinstance(case.get("loopx_behavior"), list) else []
    demo_command = case.get("demo_command")
    case_href = repo_link(str(case.get("case_page") or ""), output=output)
    storyboard_path = case.get("storyboard_path")
    storyboard_href = (
        repo_link(str(storyboard_path), output=output)
        if isinstance(storyboard_path, str) and storyboard_path
        else None
    )
    feedback_contract_path = case.get("feedback_contract_path")
    feedback_contract_href = (
        repo_link(str(feedback_contract_path), output=output)
        if isinstance(feedback_contract_path, str) and feedback_contract_path
        else None
    )
    status = str(case.get("status") or "")
    status_label = STATUS_LABELS.get(status, status.replace("_", " "))
    demo = (
        f'<div class="demo-command"><span>Demo</span><code>{esc(demo_command)}</code></div>'
        if isinstance(demo_command, str) and demo_command
        else ""
    )
    storyboard = (
        f'<a class="case-link" href="{esc(storyboard_href)}">Open storyboard</a>'
        if storyboard_href
        else ""
    )
    feedback_contract = (
        f'<a class="case-link" href="{esc(feedback_contract_href)}">Open feedback contract</a>'
        if feedback_contract_href
        else ""
    )
    story = "".join(f"<li>{esc(beat)}</li>" for beat in story_beats)
    behavior_items = "".join(f"<li>{esc(item)}</li>" for item in behavior)
    efficiency_panel = render_efficiency_panel(case)

    return f"""
      <article class="case-card"
        data-case-id="{esc(case.get("id") or "")}"
        data-status="{esc(status)}"
        data-domain="{esc(case.get("domain") or "")}"
        data-search="{esc(search_blob(case))}">
        <div class="case-card__header">
          <span class="status-badge">{esc(status_label)}</span>
          <time>{esc(case.get("date") or "")}</time>
        </div>
        <h3>{esc(case.get("title") or "")}</h3>
        <p class="headline">{esc(case.get("headline") or "")}</p>
        <div class="badges">{render_badges(badges)}</div>
        {efficiency_panel}
        <dl>
          <div><dt>Pattern</dt><dd>{render_badges(tags)}</dd></div>
          <div><dt>User value</dt><dd>{esc(case.get("user_value") or "")}</dd></div>
          <div><dt>Evidence boundary</dt><dd>{esc(case.get("evidence_boundary") or "")}</dd></div>
        </dl>
        <div class="case-flow">
          <div>
            <h4>LoopX behavior</h4>
            <ol>{behavior_items}</ol>
          </div>
          <div>
            <h4>Story beats</h4>
            <ol>{story}</ol>
          </div>
        </div>
        {demo}
        {storyboard}
        {feedback_contract}
        <a class="case-link" href="{esc(case_href)}">Open case page</a>
      </article>
    """


def render(catalog: dict[str, Any], *, output: Path | None) -> str:
    cases = catalog.get("cases")
    if not isinstance(cases, list):
        raise ValueError("showcase catalog must contain a cases list")
    asset_href = repo_link("docs/assets/control-plane-board.svg", output=output)
    case_cards = "\n".join(render_case(case, output=output) for case in cases)
    case_count = len(cases)
    status_filters = render_status_filters(cases)
    schema_version = str(catalog.get("schema_version") or "")
    schema_label = schema_version.removeprefix("loopx_showcase_catalog_") or schema_version
    pattern_count = len(
        {
            tag
            for case in cases
            for tag in (case.get("pattern_tags") if isinstance(case.get("pattern_tags"), list) else [])
        }
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LoopX Showcase Frontstage</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #5b6475;
      --line: #d9dee8;
      --paper: #ffffff;
      --soft: #f5f7fb;
      --green: #087f5b;
      --blue: #1d4ed8;
      --amber: #9a6700;
      --red: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 480px); gap: 32px; align-items: center; }}
    .eyebrow {{ color: var(--green); font-weight: 700; margin: 0 0 10px; }}
    h1 {{ font-size: 46px; line-height: 1.05; margin: 0 0 16px; letter-spacing: 0; }}
    .punchline {{ font-size: 25px; margin: 0 0 16px; font-weight: 700; }}
    .summary {{ max-width: 760px; color: var(--muted); font-size: 17px; margin: 0; }}
    .hero img {{ width: 100%; border: 1px solid var(--line); border-radius: 8px; background: var(--soft); }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 28px 0; }}
    .metrics div {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; flex: 1 1 140px; min-width: 0; background: var(--soft); }}
    .metrics strong {{ display: block; font-size: 22px; overflow-wrap: anywhere; }}
    .metrics span {{ color: var(--muted); font-size: 13px; }}
    .comparison {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin: 28px 0 34px; }}
    .comparison section {{ border: 1px solid var(--line); border-radius: 8px; padding: 18px; }}
    .comparison h2 {{ font-size: 18px; margin: 0 0 8px; }}
    .comparison p {{ margin: 0; color: var(--muted); }}
    .showcase-controls {{ border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: 18px 0; margin: 0 0 24px; display: grid; gap: 12px; }}
    .control-row {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 320px); gap: 16px; align-items: center; }}
    .segmented-controls {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .segmented-controls button {{
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      min-height: 38px;
      padding: 7px 11px;
    }}
    .segmented-controls button[aria-pressed="true"] {{ border-color: var(--green); color: var(--green); background: #eefaf4; }}
    .search-control {{ display: grid; gap: 6px; color: var(--muted); font-size: 13px; font-weight: 700; }}
    .search-control input {{ border: 1px solid var(--line); border-radius: 8px; color: var(--ink); font: inherit; min-height: 40px; padding: 8px 10px; width: 100%; }}
    .result-count {{ color: var(--muted); margin: 0; }}
    .result-count strong {{ color: var(--ink); }}
    .cases {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 18px; }}
    .case-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 20px; background: var(--paper); }}
    .case-card__header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; color: var(--muted); font-size: 13px; }}
    .status-badge {{ color: var(--blue); font-weight: 700; }}
    h3 {{ font-size: 21px; margin: 0 0 10px; }}
    h4 {{ margin: 0 0 8px; font-size: 14px; }}
    .headline {{ color: var(--muted); margin: 0 0 14px; }}
    .badges, dd {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .badges span, dd span {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; }}
    .efficiency-panel {{ margin: 16px 0; border: 1px solid #b7e4d2; border-radius: 8px; background: #f0fbf6; padding: 14px; }}
    .efficiency-panel__header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 12px; }}
    .efficiency-panel__header span {{ color: var(--green); font-size: 12px; font-weight: 800; text-transform: uppercase; }}
    .efficiency-panel__header h4 {{ margin: 3px 0 0; font-size: 15px; }}
    .efficiency-panel__header strong {{ color: var(--green); font-size: 25px; line-height: 1; white-space: nowrap; }}
    .efficiency-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }}
    .efficiency-grid div {{ min-width: 0; border: 1px solid #caeadc; border-radius: 8px; background: var(--paper); padding: 8px; }}
    .efficiency-grid strong {{ display: block; font-size: 17px; overflow-wrap: anywhere; }}
    .efficiency-grid span {{ color: var(--muted); font-size: 11px; }}
    .efficiency-panel p {{ margin: 10px 0 0; color: var(--muted); font-size: 12px; }}
    dl {{ margin: 16px 0; display: grid; gap: 12px; }}
    dt {{ font-size: 12px; text-transform: uppercase; color: var(--muted); font-weight: 700; margin-bottom: 4px; }}
    dd {{ margin: 0; }}
    .case-flow {{ display: grid; gap: 14px; }}
    ol {{ margin: 0; padding-left: 20px; color: var(--muted); }}
    .demo-command {{ margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: grid; gap: 4px; background: var(--soft); }}
    .demo-command span {{ font-size: 12px; color: var(--green); font-weight: 700; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; white-space: normal; }}
    .case-link {{ display: inline-block; margin-top: 16px; color: var(--blue); font-weight: 700; text-decoration: none; }}
    .boundary {{ margin-top: 34px; border-left: 4px solid var(--amber); padding-left: 16px; color: var(--muted); }}
    [hidden] {{ display: none !important; }}
    @media (max-width: 840px) {{
      main {{ padding: 28px 16px 44px; }}
      .hero, .comparison, .control-row {{ grid-template-columns: 1fr; }}
      .efficiency-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      h1 {{ font-size: 34px; }}
      .punchline {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <p class="eyebrow">LoopX Showcases</p>
        <h1>Gate-aware human-in-the-loop control plane</h1>
        <p class="punchline">让人的判断成为控制面，而不是让 agent 在等待里空转。</p>
        <p class="summary">LoopX keeps user decisions, agent todos, safe fallback, run history, and quota in one shared state layer: the gated route waits clearly, while independent safe side work can keep moving with evidence.</p>
      </div>
      <img src="{esc(asset_href)}" alt="LoopX control-plane board">
    </section>
    <section class="metrics" aria-label="Catalog metrics">
      <div><strong>{case_count}</strong><span>public-safe cases</span></div>
      <div><strong>{pattern_count}</strong><span>pattern tags</span></div>
      <div title="{esc(schema_version)}"><strong>{esc(schema_label)}</strong><span>catalog schema</span></div>
    </section>
    <section class="comparison" aria-label="Executor loop versus control plane">
      <section>
        <h2>Codex goal / automation / CLI loop</h2>
        <p>Executes bounded work inside an agent session or scheduled turn.</p>
      </section>
      <section>
        <h2>LoopX</h2>
        <p>Preserves the lifetime-goal control plane across turns, tools, agents, gates, evidence, and quota.</p>
      </section>
    </section>
    <section class="showcase-controls" aria-label="Showcase filters">
      <div class="control-row">
        <div class="segmented-controls" role="group" aria-label="Filter by evidence status">
          {status_filters}
        </div>
        <label class="search-control">
          Search
          <input type="search" data-case-search placeholder="Pattern, audience, domain">
        </label>
      </div>
      <p class="result-count" aria-live="polite"><strong data-visible-count>{case_count}</strong> of {case_count} cases visible</p>
    </section>
    <section class="cases" aria-label="Showcase cases">
      {case_cards}
    </section>
    <section class="boundary">
      <p>Every card is rendered from <code>docs/showcases/showcase-catalog.json</code>. Case pages carry narrative context; the catalog carries public-safe renderable data and evidence boundaries.</p>
    </section>
  </main>
  <script>
    (() => {{
      const buttons = [...document.querySelectorAll("[data-status-filter]")];
      const cards = [...document.querySelectorAll("[data-case-id]")];
      const input = document.querySelector("[data-case-search]");
      const visibleCount = document.querySelector("[data-visible-count]");
      let activeStatus = "all";

      const update = () => {{
        const query = (input?.value || "").trim().toLowerCase();
        let count = 0;
        for (const card of cards) {{
          const matchesStatus = activeStatus === "all" || card.dataset.status === activeStatus;
          const matchesQuery = !query || (card.dataset.search || "").includes(query);
          const visible = matchesStatus && matchesQuery;
          card.hidden = !visible;
          if (visible) {{
            count += 1;
          }}
        }}
        if (visibleCount) {{
          visibleCount.textContent = String(count);
        }}
        for (const button of buttons) {{
          button.setAttribute("aria-pressed", String(button.dataset.statusFilter === activeStatus));
        }}
      }};

      for (const button of buttons) {{
        button.addEventListener("click", () => {{
          activeStatus = button.dataset.statusFilter || "all";
          update();
        }});
      }}
      input?.addEventListener("input", update);
      update();
    }})();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, help="Write HTML here instead of stdout.")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != "loopx_showcase_catalog_v0":
        raise ValueError("unsupported showcase catalog schema_version")
    html_text = render(catalog, output=args.output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html_text, encoding="utf-8")
        print(args.output)
    else:
        print(html_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
