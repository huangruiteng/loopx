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


def render_case(case: dict[str, Any], *, output: Path | None) -> str:
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    badges = frontend.get("badges") if isinstance(frontend.get("badges"), list) else []
    tags = case.get("pattern_tags") if isinstance(case.get("pattern_tags"), list) else []
    story_beats = frontend.get("story_beats") if isinstance(frontend.get("story_beats"), list) else []
    behavior = case.get("goal_harness_behavior") if isinstance(case.get("goal_harness_behavior"), list) else []
    demo_command = case.get("demo_command")
    case_href = repo_link(str(case.get("case_page") or ""), output=output)
    storyboard_path = case.get("storyboard_path")
    storyboard_href = (
        repo_link(str(storyboard_path), output=output)
        if isinstance(storyboard_path, str) and storyboard_path
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
    story = "".join(f"<li>{esc(beat)}</li>" for beat in story_beats)
    behavior_items = "".join(f"<li>{esc(item)}</li>" for item in behavior)

    return f"""
      <article class="case-card" data-case-id="{esc(case.get("id") or "")}">
        <div class="case-card__header">
          <span class="status-badge">{esc(status_label)}</span>
          <time>{esc(case.get("date") or "")}</time>
        </div>
        <h3>{esc(case.get("title") or "")}</h3>
        <p class="headline">{esc(case.get("headline") or "")}</p>
        <div class="badges">{render_badges(badges)}</div>
        <dl>
          <div><dt>Pattern</dt><dd>{render_badges(tags)}</dd></div>
          <div><dt>User value</dt><dd>{esc(case.get("user_value") or "")}</dd></div>
          <div><dt>Evidence boundary</dt><dd>{esc(case.get("evidence_boundary") or "")}</dd></div>
        </dl>
        <div class="case-flow">
          <div>
            <h4>Goal Harness behavior</h4>
            <ol>{behavior_items}</ol>
          </div>
          <div>
            <h4>Story beats</h4>
            <ol>{story}</ol>
          </div>
        </div>
        {demo}
        {storyboard}
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
  <title>Goal Harness Showcase Frontstage</title>
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
    .cases {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 18px; }}
    .case-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 20px; background: var(--paper); }}
    .case-card__header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; color: var(--muted); font-size: 13px; }}
    .status-badge {{ color: var(--blue); font-weight: 700; }}
    h3 {{ font-size: 21px; margin: 0 0 10px; }}
    h4 {{ margin: 0 0 8px; font-size: 14px; }}
    .headline {{ color: var(--muted); margin: 0 0 14px; }}
    .badges, dd {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .badges span, dd span {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; }}
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
    @media (max-width: 840px) {{
      main {{ padding: 28px 16px 44px; }}
      .hero, .comparison {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 34px; }}
      .punchline {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <p class="eyebrow">Goal Harness Showcases</p>
        <h1>Gate-aware human-in-the-loop control plane</h1>
        <p class="punchline">让人的判断成为控制面，而不是让 agent 在等待里空转。</p>
        <p class="summary">Goal Harness keeps user decisions, agent todos, safe fallback, run history, and quota in one shared state layer: the gated route waits clearly, while independent safe side work can keep moving with evidence.</p>
      </div>
      <img src="{esc(asset_href)}" alt="Goal Harness control-plane board">
    </section>
    <section class="metrics" aria-label="Catalog metrics">
      <div><strong>{case_count}</strong><span>public-safe cases</span></div>
      <div><strong>{pattern_count}</strong><span>pattern tags</span></div>
      <div><strong>{esc(catalog.get("schema_version") or "")}</strong><span>catalog schema</span></div>
    </section>
    <section class="comparison" aria-label="Executor loop versus control plane">
      <section>
        <h2>Codex goal / automation / CLI loop</h2>
        <p>Executes bounded work inside an agent session or scheduled turn.</p>
      </section>
      <section>
        <h2>Goal Harness</h2>
        <p>Preserves the lifetime-goal control plane across turns, tools, agents, gates, evidence, and quota.</p>
      </section>
    </section>
    <section class="cases" aria-label="Showcase cases">
      {case_cards}
    </section>
    <section class="boundary">
      <p>Every card is rendered from <code>docs/showcases/showcase-catalog.json</code>. Case pages carry narrative context; the catalog carries public-safe renderable data and evidence boundaries.</p>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, help="Write HTML here instead of stdout.")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != "goal_harness_showcase_catalog_v0":
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
