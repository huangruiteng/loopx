# computer_use_runtime_connector_v0

Status: public-safe research and design contract v0.

Computer-use agents can operate browsers, desktops, and enterprise tools, but
the raw execution loop is usually too low-level for long-horizon work: clicks,
screenshots, focus changes, and modal errors do not by themselves say whether a
goal is allowed, blocked, valuable, or safe to continue.

This contract treats a computer-use runtime as an execution surface beside
LoopX. The runtime observes and acts in the UI. LoopX owns the durable
control-plane projection: goal state, todo granularity, quota, gates, evidence
pointers, scheduler policy, and human attention routing.

## Design Intent

The useful split is:

- the computer-use runtime owns pixels, accessibility trees, browser sessions,
  app focus, low-level actions, replay handles, and host credentials;
- LoopX owns the goal contract, middle-grained todos, allowed action boundary,
  review gates, compact receipts, and validated writeback;
- the product surface owns the human-facing review card, approval prompt,
  takeover path, and recovery affordance.

LoopX should not become a UI automation framework. It should make a UI
automation framework safe and recoverable enough to run inside a long task.

## Middle-Grained Action Pattern

Computer-use loops often fail at both extremes:

- raw UI primitives are too small for planning and review;
- whole workflows are too large to validate, retry, or hand back to a human.

The LoopX connector should introduce a middle-grained action unit that maps to a
todo or action packet:

```text
goal boundary
  -> bounded computer-use todo
  -> runtime action plan
  -> observed UI receipts
  -> compact validation
  -> LoopX todo/gate/evidence writeback
```

Examples of middle-grained units:

- inspect a settings screen and report whether a toggle exists;
- draft a post but stop before publish;
- fill a form from approved fields and stop at the final submit gate;
- capture a replay handle for a successful navigation path;
- recover from a modal error by returning a blocker packet instead of clicking
  through unknown prompts.

## Runtime Records

| Record | Purpose |
| --- | --- |
| `computer_use_capability_profile_v0` | Public-safe runtime capabilities: browser, desktop, accessibility tree, screenshot, replay, sandbox, and write modes. |
| `computer_use_session_v0` | Compact session envelope with host kind, visibility, account/source status, and raw-data redaction booleans. |
| `computer_use_action_plan_v0` | Middle-grained action intent derived from a LoopX todo, including stop condition and validation target. |
| `computer_use_observation_v0` | Compact UI facts from the runtime; no raw screenshots, DOM dumps, private bodies, or credentials. |
| `computer_use_action_receipt_v0` | What the runtime actually attempted, whether it stopped at the gate, and which evidence handle proves it. |
| `computer_use_replay_handle_v0` | Optional host-owned replay or record pointer; LoopX stores the handle class and safety flags, not raw replay data. |
| `computer_use_handoff_gate_v0` | Human decision point before private reads, account writes, external sends, purchases, production changes, or final submission. |

## Read-Only Profile

A runtime may advertise capability before any source access:

```json
{
  "schema_version": "computer_use_capability_profile_v0",
  "connector_id": "computer_use_runtime",
  "host_kind": "browser_or_desktop_runtime",
  "visibility": "visible_or_replayable",
  "capabilities": {
    "screenshots": "host_owned",
    "accessibility_tree": "optional",
    "browser_session": "optional",
    "record_replay": "optional",
    "external_write": "gated",
    "private_source_read": "gated"
  },
  "boundary": {
    "credentials_copied": false,
    "cookies_exported": false,
    "raw_screenshots_copied": false,
    "raw_private_bodies_copied": false,
    "external_write_allowed_without_gate": false
  }
}
```

This profile is a readiness fact, not permission to operate a real account or
read private material.

## Action Plan Shape

```json
{
  "schema_version": "computer_use_action_plan_v0",
  "goal_id": "loopx-meta",
  "todo_id": "todo_example",
  "connector_id": "computer_use_runtime",
  "action_unit": "draft_until_review_gate",
  "source_status": "private_needs_review",
  "allowed_actions": [
    "open approved screen",
    "fill approved draft fields",
    "capture compact receipt"
  ],
  "forbidden_actions": [
    "submit",
    "publish",
    "purchase",
    "change production state",
    "export cookies",
    "copy raw private content"
  ],
  "stop_condition": "stop at final confirmation or unknown modal",
  "validation_target": "draft screen is reachable and final action remains unclicked"
}
```

The action plan should be generated from LoopX todo/gate state and current
connector policy, not from an ad hoc prompt pasted into the automation runtime.

## Receipt Shape

```json
{
  "schema_version": "computer_use_action_receipt_v0",
  "goal_id": "loopx-meta",
  "todo_id": "todo_example",
  "connector_id": "computer_use_runtime",
  "outcome": "stopped_at_gate",
  "observed_facts": {
    "screen_reached": true,
    "draft_present": true,
    "final_action_clicked": false,
    "unknown_modal": false
  },
  "evidence": {
    "handle_kind": "host_replay_or_screenshot_pointer",
    "raw_evidence_copied": false,
    "private_source_redacted": true
  },
  "next_loopx_writeback": {
    "complete_todo": false,
    "create_user_gate": true,
    "recommended_action": "ask the user to review the host-owned draft before external action"
  }
}
```

Receipts are compact control facts. They can complete a LoopX todo only when the
todo's validation target is satisfied and the receipt proves no gated action was
performed.

## Operating Modes

| Mode | Default LoopX behavior | Gate before |
| --- | --- | --- |
| Public web metadata | Allow compact observation and source handle. | Quoting body text, outreach, posting, or trend claims. |
| Private enterprise tool | Emit owner gate and capability profile only. | Reading private records, changing status, assigning users, exporting content. |
| Local desktop or browser session | Allow install/readiness checks and synthetic fixture runs. | Using logged-in accounts, downloading private files, destructive local actions. |
| Drafting workflow | Allow draft preparation from approved inputs. | Send, publish, submit, purchase, delete, production mutation. |
| Replay or skill capture | Store handle class and safety flags only. | Copying raw replay data, screenshots, credentials, or private UI text into LoopX state. |
| Benchmark or sandbox | Allow bounded sandbox receipts when task/source policy permits. | Raw task text, trajectories, verifier output, uploads, or leaderboard submissions. |

## Human Attention Contract

The connector is useful when it reduces the number of human interventions while
making the remaining interventions clearer. A user should see:

- what the runtime is trying to do;
- what it is explicitly forbidden to do;
- what evidence was captured;
- whether the next step needs human review, another agent todo, or no action;
- how to take over the host surface if the runtime is stuck.

When a user gate is required, the projection must name the exact decision:

```text
Review the host-owned draft and approve or reject the final external action.
```

It should not say only "owner gate" or "waiting for user".

## Failure And Recovery

The runtime should return a blocker instead of improvising when it sees:

- an unknown modal, captcha, login, payment, permission prompt, or destructive
  confirmation;
- a source whose privacy status is unclear;
- repeated focus or app-lifecycle failures;
- missing replay/evidence handle for a claimed action;
- stale LoopX quota, gate, or todo state.

The recovery path is another LoopX todo or user gate, not a longer chain of
unbounded UI clicks.

## Smoke Expectations

Initial coverage should use synthetic or fixture data. It should not depend on a
real logged-in account or private UI.

Useful public smokes:

- capability profile builder rejects raw screenshots, cookies, credentials, and
  private bodies;
- action-plan builder refuses external writes without a gate;
- receipt builder distinguishes `completed`, `stopped_at_gate`, and
  `blocked_by_unknown_modal`;
- status projection surfaces a concrete user question when a gate is required;
- quota spend happens only after LoopX writeback records a validated receipt.

Live connector tests may be added later, but they must use the same compact
packet shape and keep raw host evidence in the host or private project store.

## Relationship To Existing Contracts

- [Runtime connector catalog](../../runtime-connector-catalog.md) lists
  computer-use runtime as one connector family beside app heartbeats, TUI loops,
  shell workers, webhooks, and worker bridges.
- [Host integration surface v0](host-integration-surface-v0.md) defines the
  CLI-equivalent read/write baseline for host integrations.
- [Session runtime to LoopX projection v0](session-runtime-loopx-projection-v0.md)
  defines the compact projection discipline for host session facts.
- [Content ops surface v0](content-ops-surface-v0.md) and
  [value connector plan v0](value-connector-plan-v0.md) define adjacent
  publish-gate and external-value patterns for browser-backed workflows.
