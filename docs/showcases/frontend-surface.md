# Showcase Frontend Surface

This note defines the first public-facing showcase surface that can consume
`docs/showcases/showcase-catalog.json`. It is a product explanation surface,
not the local operator dashboard.

The goal is to help a new user understand Goal Harness in one screen:

- Codex, Claude Code, Cursor, and similar tools execute agent loops.
- Goal Harness keeps the long-running goal control plane visible across those
  loops: gates, todos, ownership, safe fallback, run history, quota, and
  evidence.
- A case is useful only when it shows a reusable control-plane behavior, not
  just that an agent did work.

## Source Of Truth

The frontend should read `showcase-catalog.json` instead of scraping Markdown.
Case pages provide narrative context; the catalog provides renderable data.

Use these catalog fields directly:

| Field | Frontend Use |
| --- | --- |
| `id`, `date`, `title` | Stable card identity and sort key. |
| `status` | Badge and rendering state. |
| `case_page` | Link to the narrative source. |
| `demo_command` | "Try the demo" command when available. |
| `storyboard_path` | Link to a frontend-ready storyboard when a runnable demo is not available. |
| `domain`, `audience`, `pattern_tags` | Filters and grouping. |
| `headline` | Main card copy. |
| `problem` | Situation before Goal Harness helped. |
| `goal_harness_behavior` | Timeline or behavior list. |
| `user_value` | Outcome in plain language. |
| `evidence_boundary` | Redaction and claim boundary drawer. |
| `frontend_card.visual_metaphor` | Suggested visual treatment. |
| `frontend_card.primary_metric_hint` | Lightweight signal, not a hard claim. |
| `frontend_card.badges` | Compact chips. |
| `frontend_card.story_beats` | Case detail timeline. |

## First Screen

The first screen should answer the recurring confusion: "Is this replacing
Codex goal mode?"

Use a compact comparison block:

| Surface | Role |
| --- | --- |
| Codex goal / automation / CLI loop | Executes bounded work inside an agent session or scheduled turn. |
| Goal Harness | Preserves the lifetime-goal control plane across turns, tools, agents, gates, evidence, and quota. |

Recommended headline stack for Chinese-first material:

```text
Gate-aware human-in-the-loop control plane
让人的判断成为控制面，而不是让 agent 在等待里空转。
```

Recommended English explanation:

```text
Goal Harness keeps user decisions, agent todos, safe fallback, run history,
and quota in one shared state layer: the gated route waits clearly, while
independent safe side work can keep moving with evidence.
```

## Case Card Model

Each case card should show:

- title;
- status badge;
- one-line headline;
- pattern tags;
- user value;
- evidence boundary badge;
- demo command only when `demo_command` is present.

Do not render raw run logs, screenshots, private chat excerpts, task ids, or
internal document links. A public case card should feel like a reusable product
pattern, not a transcript.

## Detail Story Model

A case detail view should be a short visual story:

1. **Trigger**: what made the long-running goal hard to manage.
2. **Visible State**: which Goal Harness objects made the situation explicit.
3. **Agent Move**: what bounded action remained safe.
4. **Human Role**: what the user did or did not need to decide.
5. **Evidence**: what public-safe validation supports the case.

For `redacted_stub_pending_contributor_details`, show the missing evidence
plainly. Do not fill the gap with speculative claims.

## Status Rendering

| Status | Badge | Behavior |
| --- | --- | --- |
| `reproducible_synthetic_demo` | Reproducible | Show demo command and link to synthetic fixture. |
| `public_evidence_case` | Public evidence | Show Git/doc/smoke-backed evidence summary. |
| `redacted_stub_pending_contributor_details` | Redacted stub | Show the pattern and missing public evidence. |
| `public_safe_case_spec` | Case spec | Show narrative and storyboard link when present. |

New statuses should be added to the catalog smoke before they appear in the
website.

## Public Boundary

The showcase frontend may include:

- sanitized domain labels;
- reusable control-plane patterns;
- synthetic demos;
- compact public Git evidence;
- explicit evidence boundaries.

It must not include:

- raw screenshots from internal tools;
- private document, wiki, or chat links;
- raw benchmark task text, trajectories, logs, verifier tails, or task ids;
- credentials, auth material, or local filesystem paths;
- unpublished project artifacts or user-specific active state.

## First Implementation Slice

The first implementation should be static and catalog-driven:

1. Load `showcase-catalog.json`.
2. Validate the known `schema_version`.
3. Render the comparison block, case grid, and detail story from catalog fields.
4. Link back to Markdown case pages.
5. Use `docs/assets/control-plane-board.svg` as the first shared visual asset.
6. Use `examples/showcase-frontstage-prototype.py` as the no-build static
   prototype until a real frontend app exists.
7. Run `python3 examples/showcase-catalog-smoke.py`,
   `python3 examples/showcase-frontstage-prototype-smoke.py`, and
   `goal-harness check --scan-path docs/showcases --scan-path docs/assets`.

This keeps the marketing surface honest: if a case is not in the catalog, it
does not appear on the public showcase frontend.
