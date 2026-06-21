#!/usr/bin/env python3
"""Render a public-safe HTML animation prototype from the showcase storyboard."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORYBOARD = REPO_ROOT / "docs" / "showcases" / "showcase-animation-storyboard.json"
DEFAULT_CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"
FORBIDDEN_SOURCE_FLAGS = (
    "live_registry_state",
    "local_status_exports",
    "user_specific_active_state",
    "private_docs_or_chats",
    "raw_benchmark_traces",
    "internal_project_names",
)
STACK_LABELS = {
    "remotion-agent-skills": "Remotion Agent Skills",
    "hyperframes": "HyperFrames",
    "motion-for-react": "Motion for React",
    "lottie": "Lottie",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug(value: object) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value)).strip("-")
    return safe or "scene"


def pct(seconds: float, total: float) -> str:
    return f"{(seconds / total) * 100:.4f}%"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def validate(
    storyboard: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], int]:
    if storyboard.get("schema_version") != "goal_harness_showcase_animation_storyboard_v0":
        raise ValueError("storyboard schema_version mismatch")
    if storyboard.get("source_catalog") != "docs/showcases/showcase-catalog.json":
        raise ValueError("storyboard must point to docs/showcases/showcase-catalog.json")
    if catalog.get("schema_version") != "goal_harness_showcase_catalog_v0":
        raise ValueError("catalog schema_version mismatch")

    target = storyboard.get("duration_seconds_target")
    if not isinstance(target, dict) or target.get("min") != 20 or target.get("max") != 30:
        raise ValueError("storyboard duration target must be 20-30 seconds")

    boundary = storyboard.get("public_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("storyboard public_boundary must be an object")
    for flag in FORBIDDEN_SOURCE_FLAGS:
        if boundary.get(flag) is not False:
            raise ValueError(f"storyboard public boundary must keep {flag}=false")

    cases = catalog.get("cases")
    scenes = storyboard.get("scenes")
    if not isinstance(cases, list) or not cases:
        raise ValueError("catalog must contain cases")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("storyboard must contain scenes")

    case_by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not case.get("id"):
            raise ValueError("each catalog case must have an id")
        case_by_id[str(case["id"])] = case

    previous_end: int | None = None
    referenced_case_ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("each scene must be an object")
        for required in ("id", "visual", "copy", "motion_notes"):
            if not scene.get(required):
                raise ValueError(f"scene missing {required}: {scene}")
        time_seconds = scene.get("time_seconds")
        if (
            not isinstance(time_seconds, list)
            or len(time_seconds) != 2
            or not all(isinstance(value, int) for value in time_seconds)
        ):
            raise ValueError(f"scene {scene.get('id')}: time_seconds must be [start, end]")
        start, end = time_seconds
        if start < 0 or end <= start:
            raise ValueError(f"scene {scene.get('id')}: invalid time range")
        if previous_end is not None and start != previous_end:
            raise ValueError(f"scene {scene.get('id')}: scenes must be contiguous")
        previous_end = end

        source_case_ids = scene.get("source_case_ids")
        if not isinstance(source_case_ids, list):
            raise ValueError(f"scene {scene.get('id')}: source_case_ids must be a list")
        for case_id in source_case_ids:
            case_key = str(case_id)
            if case_key not in case_by_id:
                raise ValueError(f"scene {scene.get('id')}: unknown case id {case_id}")
            referenced_case_ids.add(case_key)

    duration = int(scenes[-1]["time_seconds"][1])
    if duration < int(target["min"]) or duration > int(target["max"]):
        raise ValueError("storyboard scene duration must fit the 20-30 second target")
    if referenced_case_ids != set(case_by_id):
        raise ValueError("storyboard must reference every catalog case exactly through public ids")
    return scenes, case_by_id, duration


def render_badges(values: list[Any], *, limit: int = 3) -> str:
    return "".join(f"<span>{esc(value)}</span>" for value in values[:limit])


def render_stack_label(value: object) -> str:
    text = str(value)
    return STACK_LABELS.get(text, text.replace("-", " ").title())


def render_case_cards(scene: dict[str, Any], case_by_id: dict[str, dict[str, Any]]) -> str:
    cards: list[str] = []
    for case_id in scene.get("source_case_ids") or []:
        case = case_by_id[str(case_id)]
        frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
        badges = frontend.get("badges") if isinstance(frontend.get("badges"), list) else []
        cards.append(
            f"""
            <div class="case-card" data-source-case-id="{esc(case_id)}">
              <strong>{esc(case.get("title") or case_id)}</strong>
              <span>{esc(case.get("headline") or "")}</span>
              <small>{render_badges(badges)}</small>
            </div>
            """
        )
    if cards:
        return "\n".join(cards)
    return """
            <div class="case-card case-card--system" data-source-case-id="catalog-boundary">
              <strong>Catalog-backed control plane</strong>
              <span>The prototype reads the public storyboard and catalog only.</span>
              <small><span>public-boundary</span><span>no-live-status</span></small>
            </div>
    """


def render_scene(scene: dict[str, Any], case_by_id: dict[str, dict[str, Any]], index: int) -> str:
    scene_id = str(scene["id"])
    start, end = scene["time_seconds"]
    case_ids = ",".join(str(case_id) for case_id in scene.get("source_case_ids") or [])
    return f"""
      <article class="scene scene--{slug(scene_id)}"
        data-scene-id="{esc(scene_id)}"
        data-start-seconds="{start}"
        data-end-seconds="{end}"
        data-source-case-ids="{esc(case_ids)}">
        <div class="scene__meta">
          <span>{start:02d}-{end:02d}s</span>
          <span>Scene {index + 1}</span>
        </div>
        <h2>{esc(scene.get("copy") or "")}</h2>
        <p class="visual">{esc(scene.get("visual") or "")}</p>
        <p class="motion-note">{esc(scene.get("motion_notes") or "")}</p>
        <div class="case-strip">
          {render_case_cards(scene, case_by_id)}
        </div>
      </article>
    """


def render_timeline(scenes: list[dict[str, Any]], duration: int) -> str:
    parts: list[str] = []
    for scene in scenes:
        scene_id = str(scene["id"])
        start, end = scene["time_seconds"]
        width = end - start
        parts.append(
            f"""
          <span class="timeline__segment"
            data-scene-id="{esc(scene_id)}"
            style="--start:{pct(start, duration)}; --width:{pct(width, duration)};"></span>
            """
        )
    return "\n".join(parts)


def render_scene_keyframes(scenes: list[dict[str, Any]], duration: int) -> str:
    blocks: list[str] = []
    for scene in scenes:
        scene_class = slug(scene["id"])
        start, end = scene["time_seconds"]
        start_pct = pct(start, duration)
        fade_pct = pct(min(start + 0.7, end), duration)
        hold_pct = pct(max(end - 0.7, start + 0.7), duration)
        end_pct = pct(end, duration)
        before_pct = pct(max(start - 0.01, 0), duration)
        blocks.append(
            f"""
    .scene--{scene_class} {{ animation: scene-{scene_class} {duration}s linear infinite; }}
    @keyframes scene-{scene_class} {{
      0%, {before_pct} {{ opacity: 0; transform: translateY(18px) scale(0.985); pointer-events: none; }}
      {fade_pct}, {hold_pct} {{ opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }}
      {end_pct}, 100% {{ opacity: 0; transform: translateY(-14px) scale(0.99); pointer-events: none; }}
    }}
            """
        )
    return "\n".join(blocks)


def render(storyboard: dict[str, Any], catalog: dict[str, Any]) -> str:
    scenes, case_by_id, duration = validate(storyboard, catalog)
    scene_markup = "\n".join(render_scene(scene, case_by_id, index) for index, scene in enumerate(scenes))
    timeline = render_timeline(scenes, duration)
    scene_keyframes = render_scene_keyframes(scenes, duration)
    hero_line = storyboard.get("hero_line") or "From AI assist to async agent work."
    supporting_line = storyboard.get("supporting_line") or ""
    stack = storyboard.get("recommended_motion_stack")
    stack_label = ""
    if isinstance(stack, dict):
        stack_label = " / ".join(
            render_stack_label(stack[key])
            for key in ("video_primary", "video_fallback")
            if stack.get(key)
        )

    return f"""<!doctype html>
<html lang="en"
  data-source-storyboard="docs/showcases/showcase-animation-storyboard.json"
  data-source-catalog="docs/showcases/showcase-catalog.json"
  data-duration-seconds="{duration}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Goal Harness Showcase Animation Prototype</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #15171c;
      --muted: #596272;
      --line: #d8dee8;
      --paper: #ffffff;
      --soft: #f4f7fb;
      --green: #087f5b;
      --blue: #2454c6;
      --amber: #a66000;
      --red: #b42318;
      --shadow: 0 24px 60px rgba(18, 24, 38, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #f7f9fc;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1180px, calc(100vw - 32px));
      min-height: 100vh;
      margin: 0 auto;
      padding: 32px 0 44px;
      display: grid;
      grid-template-columns: minmax(280px, 0.88fr) minmax(480px, 1.12fr);
      gap: 28px;
      align-items: center;
    }}
    .intro h1 {{
      margin: 0 0 16px;
      font-size: 48px;
      line-height: 1.04;
      letter-spacing: 0;
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--green);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    .intro p {{
      max-width: 620px;
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 18px;
    }}
    .source-box {{
      display: grid;
      gap: 10px;
      max-width: 560px;
      padding: 16px;
      border: 1px solid var(--line);
      background: var(--paper);
      border-radius: 8px;
      box-shadow: 0 10px 28px rgba(18, 24, 38, 0.08);
    }}
    .source-box span {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .source-box code {{
      display: block;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
      color: #253044;
      white-space: normal;
      overflow-wrap: anywhere;
    }}
    .stage {{
      position: relative;
      min-height: 620px;
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(36, 84, 198, 0.08), transparent 42%),
        linear-gradient(315deg, rgba(8, 127, 91, 0.08), transparent 44%),
        var(--paper);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .stage::before {{
      content: "";
      position: absolute;
      inset: 24px;
      border: 1px dashed rgba(89, 98, 114, 0.28);
      border-radius: 8px;
      pointer-events: none;
    }}
    .stage__header {{
      position: relative;
      z-index: 2;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 18px;
    }}
    .stage__header span {{
      display: inline-flex;
      padding: 5px 9px;
      border-radius: 999px;
      background: #eaf7f1;
      color: var(--green);
      font-size: 12px;
      font-weight: 800;
    }}
    .stage__header strong {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-align: right;
    }}
    .timeline {{
      position: relative;
      z-index: 3;
      height: 12px;
      margin: 0 0 18px;
      border-radius: 999px;
      background: #e8edf5;
      overflow: hidden;
    }}
    .timeline::after {{
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 12%;
      border-radius: 999px;
      background: var(--blue);
      animation: progress {duration}s linear infinite;
    }}
    .timeline__segment {{
      position: absolute;
      inset: 0 auto 0 var(--start);
      width: var(--width);
      border-left: 1px solid rgba(255, 255, 255, 0.92);
      border-right: 1px solid rgba(255, 255, 255, 0.92);
    }}
    .scene-stack {{
      position: relative;
      z-index: 2;
      min-height: 490px;
    }}
    .scene {{
      position: absolute;
      inset: 0;
      display: grid;
      align-content: center;
      gap: 16px;
      padding: 28px;
      border: 1px solid rgba(216, 222, 232, 0.94);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.92);
      opacity: 0;
      box-shadow: 0 12px 34px rgba(18, 24, 38, 0.08);
    }}
    .scene__meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .scene h2 {{
      max-width: 740px;
      margin: 0;
      font-size: 34px;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    .visual {{
      max-width: 720px;
      margin: 0;
      color: #303947;
      font-size: 18px;
      font-weight: 650;
    }}
    .motion-note {{
      max-width: 720px;
      margin: 0;
      color: var(--muted);
      font-size: 15px;
    }}
    .case-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
      margin-top: 4px;
    }}
    .case-card {{
      display: grid;
      gap: 8px;
      min-height: 142px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcff;
    }}
    .case-card strong {{
      font-size: 15px;
      line-height: 1.25;
    }}
    .case-card span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .case-card small {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-self: end;
    }}
    .case-card small span {{
      padding: 3px 7px;
      border-radius: 999px;
      background: #edf2ff;
      color: var(--blue);
      font-size: 11px;
      font-weight: 800;
    }}
    .case-card--system small span {{
      background: #eaf7f1;
      color: var(--green);
    }}
    @keyframes progress {{
      0% {{ width: 0%; }}
      100% {{ width: 100%; }}
    }}
    {scene_keyframes}
    @media (max-width: 900px) {{
      main {{
        grid-template-columns: 1fr;
        align-items: start;
      }}
      .intro h1 {{ font-size: 38px; }}
      .stage {{ min-height: 680px; }}
      .scene-stack {{ min-height: 548px; }}
      .scene h2 {{ font-size: 28px; }}
    }}
    @media (max-width: 560px) {{
      main {{
        width: min(100% - 20px, 1180px);
        padding-top: 18px;
      }}
      .stage {{
        min-height: 760px;
        padding: 14px;
      }}
      .scene-stack {{ min-height: 640px; }}
      .scene {{ padding: 18px; }}
      .stage__header {{
        display: grid;
      }}
      .stage__header strong {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="intro" aria-label="Prototype overview">
      <p class="eyebrow">Goal Harness public showcase animation</p>
      <h1>{esc(hero_line)}</h1>
      <p>{esc(supporting_line)}</p>
      <div class="source-box">
        <span>Prototype source boundary</span>
        <code>docs/showcases/showcase-animation-storyboard.json</code>
        <code>docs/showcases/showcase-catalog.json</code>
        <span>{esc(stack_label or "HTML/CSS prototype")}</span>
      </div>
    </section>
    <section class="stage" aria-label="30 second storyboard prototype">
      <div class="stage__header">
        <span>{duration}s loop</span>
        <strong>Public catalog demo. No live registry, local status export, transcript, or private active state.</strong>
      </div>
      <div class="timeline" aria-label="Scene timeline">
        {timeline}
      </div>
      <div class="scene-stack">
        {scene_markup}
      </div>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, help="Write the HTML prototype to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    storyboard = read_json(args.storyboard)
    catalog = read_json(args.catalog)
    output = render(storyboard, catalog)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
