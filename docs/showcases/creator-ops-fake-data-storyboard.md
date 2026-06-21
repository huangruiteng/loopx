# Creator-Ops Fake-Data Storyboard

This storyboard turns the creator-operator case into a frontend-ready public
demo flow. It uses only synthetic data. It is not a crawler, publishing tool,
or claim about real creator performance.

The goal is to show how LoopX makes a long-running creator-agent loop
legible:

- research can continue;
- publishing stays gated;
- feedback changes the plan;
- private material and public demo data remain separated.

## Surface Shape

The first mock should render as a work surface, not a marketing landing page.
Use seven connected panels:

1. Trend discovery
2. Preference map
3. Insight board
4. Draft queue
5. Material library
6. Human feedback
7. Controlled replan

Each panel should show one control-plane object or transition. Avoid raw agent
logs, prompt text, screenshots, platform data, and live browsing output.

## Fake Data Fixture

The mock can use this small fixture directly.

```json
{
  "goal": "Keep a weekly creator-operator research loop moving.",
  "mode": "safe_side_path",
  "gate": {
    "label": "Publishing decision",
    "status": "waiting_on_user",
    "question": "Approve tone and source policy before publishing?"
  },
  "trend_candidates": [
    {
      "id": "trend_ai_note_workflows",
      "title": "AI note workflows for solo operators",
      "fit": "high",
      "boundary": "synthetic_public_demo"
    },
    {
      "id": "trend_research_to_shortform",
      "title": "Short-form content from long research notes",
      "fit": "medium",
      "boundary": "synthetic_public_demo"
    },
    {
      "id": "trend_human_approval_before_publish",
      "title": "Human approval before agent publication",
      "fit": "high",
      "boundary": "synthetic_public_demo"
    }
  ],
  "preference_map": [
    "practical case studies",
    "plain evidence boundaries",
    "avoid growth-hack language",
    "show what the agent will not do"
  ],
  "insight_board": [
    {
      "insight": "A long-running creator agent needs a dashboard, not another hidden prompt.",
      "source_status": "synthetic"
    },
    {
      "insight": "The user gate is not a failure; it is the product boundary.",
      "source_status": "synthetic"
    },
    {
      "insight": "Safe side paths keep research useful while publishing waits.",
      "source_status": "synthetic"
    }
  ],
  "draft_queue": [
    {
      "title": "How I keep a research agent from waiting forever",
      "status": "outline_ready",
      "gate": "tone_review"
    },
    {
      "title": "What a creator agent should show before it publishes",
      "status": "idea_only",
      "gate": "publish_policy"
    },
    {
      "title": "Material libraries as memory for creative work",
      "status": "source_map_needed",
      "gate": "no_publish_yet"
    }
  ],
  "material_library": [
    "reusable hooks",
    "source summaries",
    "phrasing examples",
    "rejected angles with reasons",
    "boundary notes"
  ],
  "feedback_options": [
    {
      "label": "This angle is useful",
      "effect": "reward_preference_hint"
    },
    {
      "label": "Too salesy",
      "effect": "draft_revision_todo"
    },
    {
      "label": "Do not use this source",
      "effect": "boundary_correction"
    },
    {
      "label": "Publish after tone review",
      "effect": "user_gate_decision"
    }
  ],
  "controlled_replan": {
    "next_action": "Revise the first draft angle using the practical-case-study preference.",
    "safe_side_path": "Continue organizing synthetic material-library examples.",
    "blocked_route": "Publishing waits for tone and source-policy approval."
  }
}
```

## Panel Details

### 1. Trend Discovery

Purpose: show candidate topics and why they might matter.

Render:

- three candidate rows;
- fit indicator;
- source boundary badge.

Do not render raw social posts or live platform names. The point is control
plane legibility, not data acquisition.

### 2. Preference Map

Purpose: show that user taste can guide planning without becoming a hard gate.

Render:

- preference chips;
- one sentence explaining that preferences are planning hints;
- separate badge for hard permission gates.

### 3. Insight Board

Purpose: turn research into reusable candidate insights.

Render:

- insight cards;
- source status;
- "needs review" marker when source status is not public-safe.

### 4. Draft Queue

Purpose: make draft readiness and gates visible.

Render:

- draft title;
- readiness status;
- gate label;
- allowed safe side work.

### 5. Material Library

Purpose: show memory as governed material, not a raw transcript dump.

Render:

- material categories;
- source status;
- rejected-angle notes.

### 6. Human Feedback

Purpose: let the user steer without editing state manually.

Render feedback buttons as explicit control-plane effects:

| Button | Effect |
| --- | --- |
| This angle is useful | reward / preference hint |
| Too salesy | draft revision todo |
| Do not use this source | boundary correction |
| Publish after tone review | gate decision |

The feedback classes and source-status rules are defined in
[creator-ops-feedback-boundary-contract.md](creator-ops-feedback-boundary-contract.md).

### 7. Controlled Replan

Purpose: show how feedback changes the next agent move.

Render:

- next action;
- safe side path;
- blocked route;
- validation expectation.

The replan panel should make clear that the agent can keep organizing safe
synthetic material while publishing still waits.

## Frontend Acceptance Criteria

The first static mock is good enough when:

- every visible data item comes from the fake fixture or catalog fields;
- no card requires live platform access;
- no user feedback is treated as a hidden memory;
- the publish gate is visible on the first screen;
- the safe side path remains visible beside the blocked publish route;
- source boundaries are visible for trend, insight, draft, and material panels;
- the case still renders from `docs/showcases/showcase-catalog.json` without
  scraping the narrative case page.

## Boundary

This storyboard may be used for a public README image, website mock, or static
HTML demo. It must not include real user drafts, private preferences, platform
screenshots, raw browsing traces, local paths, credentials, or claims about
engagement, reach, conversion, revenue, or model quality improvement.
