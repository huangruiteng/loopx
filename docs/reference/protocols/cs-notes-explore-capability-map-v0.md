# cs_notes_explore_capability_map_v0

Status: public-safe selection map v0.

This map records the reusable exploration capabilities selected from a
CS-Notes read-only mechanism scan. It is a capability map, not an import of
CS-Notes material, private queues, drafts, or source bodies. The selected
patterns are useful because they turn "go look around" into bounded,
observable, and gated product work.

## Boundary

The scan used only generic mechanism surfaces: skill contracts, snippet
entrypoints, README-style workflow notes, and deterministic helper-script
interfaces. It intentionally excludes private local state, raw material queues,
auth configuration, platform session artifacts, personal drafts, and raw source
content.

A pattern is eligible for LoopX only when it is:

- source-agnostic enough to work for GitHub, browser, chat, paper, or document
  connectors;
- explicit about read status, access route, and fallback;
- safe to represent as compact metadata before any private source body is read;
- able to produce a small artifact or validation result;
- useful to a repo issue-fix, content-ops, experiment, or general connector
  workflow without copying CS-Notes-specific prose.

## Selected Capabilities

| Capability | What To Reuse | LoopX Target | First Product Slice |
| --- | --- | --- | --- |
| `material_intake_profile_v0` | Intent profiles, source lanes, S/A/B/Unread decisions, and deep/quick/background/carryover routing. | Connector discovery and content-ops signal ranking. | Add an `exploration_plan_packet_v0` fixture that records chosen lanes, read status, evidence quality, and next safe source action. |
| `trusted_source_scan_plan_v0` | A scan plan is not a read result: it records source route, access level, fallback, and the template for later writeback. | Browser/chat/document connector preflight. | Teach connector trials to emit route/access/fallback before any live source read. |
| `pre_tick_gate_v0` | Cheap read-only signals produce one recommended action, gates, guards, and validation expectations. | Heartbeat and quota preflight for long-running agents. | Add a preflight packet that distinguishes status-only ticks from delivery ticks. |
| `todo_triage_index_v0` | Legacy tasks become structured categories: agent-runnable, user/environment blocked, stale material flow, merged workflow, or completed. | Repo issue fix and deferred-todo visibility. | Build a fixture that maps imported issue/todo rows into LoopX user/agent/deferred lanes. |
| `snippet_registry_contract_v0` | Reusable scripts and prompts must have a named entrypoint, trigger scenario, boundary note, and validation command. | Capability catalog and connector pack governance. | Add catalog fields for entrypoint, boundary, validation, and public-safety class. |
| `guarded_heartbeat_visibility_v0` | Prefer user-visible automation; use headless fallback only with idle guards and visibility caveats. | Project heartbeat prompt and connector monitor UX. | Surface transport mode and visibility risk in heartbeat/status packets. |

## Scenario Fit

Repo issue fix:

- `todo_triage_index_v0` can turn GitHub issues, review comments, and stale
  local todos into one compact runnable set with explicit user gates.
- `trusted_source_scan_plan_v0` prevents an agent from treating a linked issue,
  external doc, or repo as read before it actually inspected the source.

Self-media and creator operations:

- `material_intake_profile_v0` matches the connector-to-information-to-anchor
  workflow: first choose source lanes, then rank evidence, then promote only
  public-safe anchors into drafts.
- `trusted_source_scan_plan_v0` and `snippet_registry_contract_v0` keep
  browser/chat connectors metadata-bounded until owner review allows more.

Experiment and other vertical state surfaces:

- `pre_tick_gate_v0` and `todo_triage_index_v0` are reusable for ML experiment
  lanes: pending runs, result availability, failed environment checks, and
  human interpretation gates can all be represented before a full experiment
  state surface exists.
- `snippet_registry_contract_v0` gives each vertical pack a minimal "how to
  run, what it reads, what it writes, how to validate" contract.

## Not Imported

These are useful in CS-Notes but should not be copied into LoopX as-is:

- exact learning-material queues or personal priority text;
- platform auth setup, session artifacts, private connector configuration, or
  local automation service files;
- raw writing drafts, raw chat/source bodies, screenshots, or private
  evidence;
- the full text of CS-Notes skills when a small generic packet contract is
  enough;
- source-specific ranking biases that only make sense for one person's career
  roadmap.

## Recommended Next Step

Implement `exploration_plan_packet_v0` first. It should combine the strongest
parts of `material_intake_profile_v0` and `trusted_source_scan_plan_v0`:

- selected source lanes;
- access/read status;
- route and fallback;
- evidence quality;
- candidate promotion target;
- user gate when the next read would cross a private boundary;
- validation that no source body, credential, local path, or external write was
  captured.

That packet is the common substrate for repo issue discovery, content-ops
signal intake, and future experiment state surfaces.
