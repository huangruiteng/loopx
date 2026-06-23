# Issue/PR Solver Anchor Coordination

This note defines how LoopX coordinates a selected public issue/PR solver
anchor after maintainer intake. The solver may be a partner tool, a human
contributor, or a future LoopX-managed worker. LoopX's role is not to claim
every issue. Its role is to keep the anchor valuable, bounded, measurable, and
safe enough to become product evidence.

Use this after
[`issue_pr_solver_maintainer_intake_v0`](issue-pr-solver-maintainer-intake.md)
has selected a candidate as a high-value anchor.

## Why This Exists

Issue/PR solving is a useful proof path only when it demonstrates more than raw
coding ability. A good anchor should show that LoopX can help a maintainer:

- choose a worthwhile repository or issue;
- keep ownership and publication gates explicit;
- turn scattered solver activity into compact evidence;
- compare useful outcomes against cost and human attention;
- decide whether the case graduates into onboarding, showcase, or product work.

That makes the issue/PR solver lane a secondary value proof for LoopX's
management surface: a maintainer can see what happened, what it cost, where a
human judgment was needed, and whether the next anchor should change.

## Coordination Packet

```yaml
issue_pr_solver_anchor_coordination_v0:
  anchor:
    anchor_id: "stable public-safe id"
    repo_handle: "owner/repo or public-safe alias"
    issue_or_pr_handle: "public issue or PR id"
    intake_ref: "issue_pr_solver_maintainer_intake_v0 handle"
    objective: "what useful maintainer outcome this anchor should test"
  owner_split:
    loopx_maintainer:
      owns:
        - anchor selection
        - boundary policy
        - metric board
        - showcase graduation
    partner_solver:
      owns:
        - solver execution proposal
        - implementation attempt when authorized
        - compact result handoff
    repo_maintainer:
      owns:
        - repository review decision
        - public comment or PR acceptance
        - merge or rejection outcome
    human_reviewer:
      owns:
        - value score
        - quality score
        - attention-cost feedback
  allowed_actions:
    current_level: observe | triage | reproduce | draft_plan | prepare_patch | publish | showcase
    next_gate: source_boundary | owner_route | validation | publish | showcase | none
  evidence_boundary:
    allowed:
      - public issue or PR handle
      - task label and owner route
      - compact reproduction result
      - patch summary
      - CI or review status
      - maintainer outcome
      - reviewer score
    forbidden:
      - private source context
      - credentials
      - unpublished maintainer messages
      - raw runtime traces
      - sensitive local paths
  metric_board:
    usefulness:
      selected_anchor_count: 0
      useful_outcome_count: 0
      accepted_or_advanced_count: 0
    quality:
      validation_passed_count: 0
      reviewer_quality_score: null
      boundary_incident_count: 0
    cost:
      token_or_runtime_cost: null
      human_attention_minutes: null
      iteration_count: 0
    learning:
      feedback_signal_count: 0
      next_anchor_change: "keep | narrow | broaden | stop"
  human_gates:
    - source boundary unclear
    - partner solver wants to write code
    - external comment or PR would be published
    - showcase consent is missing
    - reviewer score changes the next anchor strategy
  graduation:
    status: signal | selected_anchor | pilot_running | result_review | case_catalog | showcase | archived
    graduation_condition: "what must be true before the next status"
    stop_condition: "what makes this anchor no longer worth pursuing"
```

## Seed Workflow

1. **Collect signals.** Keep raw candidates as searchable signals, not todos.
   Sources can include GitHub issues, maintainer requests, partner solver
   suggestions, user conversations, or operator notes.
2. **Run maintainer intake.** Use the intake packet to decide whether the
   candidate is worth becoming an anchor.
3. **Select a tiny anchor set.** Prefer one to three anchors with clear user
   value, public evidence, and a reachable owner route.
4. **Set the allowed action level.** Start at Observe or Triage. Promote only
   when the next human gate has passed.
5. **Hand off to the solver.** Give the solver only the approved handle,
   objective, allowed actions, validation surface, and stop conditions.
6. **Ingest compact evidence.** Store result labels, validation status, review
   outcome, and cost signals. Do not store private transcripts or raw runtime
   material.
7. **Review like work output.** The human reviewer scores value, quality, cost,
   and attention. The score changes future anchor selection.
8. **Graduate or archive.** A useful public outcome can become a case-catalog
   entry or showcase card. A noisy or unsafe anchor should be archived with the
   reason visible.

## Metric Board

Do not optimize for raw issue count or raw PR count. Those are easy to inflate
and do not prove that a long-running agent is manageable.

The first useful board should track:

- **Selected anchors**: how many candidates survived maintainer intake.
- **Useful outcomes**: merged PR, accepted plan, clear maintainer rejection,
  reproduced bug, validated blocker, or product insight.
- **Quality**: validation result, reviewer score, and whether the solver stayed
  inside the boundary.
- **Cost**: token/runtime cost, number of iterations, and human attention
  minutes.
- **Learning**: what feedback changed the next anchor choice.

This aligns with the broader Loop Agent reward model:

```text
value = f(quantity, quality, token/runtime cost, human attention cost)
```

## Human Gates

Every anchor should expose concrete gates rather than a generic "owner gate":

- **Source boundary gate**: can the issue, code, and evidence be handled
  publicly or compactly?
- **Solver autonomy gate**: may the partner solver move from observing to
  reproducing, planning, or preparing code?
- **Publication gate**: may anyone post a comment, open a PR, or publish a
  branch?
- **Showcase gate**: may the outcome be named, anonymized, or reused in launch
  material?
- **Review gate**: does human feedback say to continue, narrow, broaden, or stop
  the anchor class?

When a gate blocks progress, write it as a user todo with the concrete decision
needed. When a gate is resolved, record the decision as compact evidence.

## Graduation Path

An anchor should move through explicit states:

| State | Meaning | Next condition |
| --- | --- | --- |
| Signal | Candidate exists, not selected | maintainer intake says it is worth testing |
| Selected anchor | Boundary and owner route are plausible | allowed action level and solver handoff are ready |
| Pilot running | Solver is working inside approved actions | compact result or blocker arrives |
| Result review | Human reviews value, quality, cost, and attention | score and next-anchor decision are recorded |
| Case catalog | The result is reusable internally or publicly | consent and boundary allow publication |
| Showcase | The case can teach LoopX's product value | public card or demo copy is approved |
| Archived | The case is no longer useful or safe | reason is visible for future selection |

Graduation is not automatic. A solved issue may still fail showcase graduation
if the evidence is private, the value is hard to explain, or the human attention
cost is too high.

## LoopX Writeback

The coordination lane should write normal LoopX objects:

- a selected `anchor_v0` or signal archive decision;
- an agent todo for solver handoff, evidence ingest, or case-catalog drafting;
- a user todo for source, publication, or showcase gates;
- a `review_event_v0` with value, quality, cost, and attention feedback;
- a compact metric-board update;
- a case-catalog or showcase todo only after consent.

For the first repo-local projection, an active state may also include a compact
`## Issue Meta Surface` section. `loopx status` lifts each public-safe
key-value bullet into `issue_meta_surface_v0` and mirrors it under
`project_asset.issue_meta_surface`:

```md
## Issue Meta Surface

- anchor_id=issue_anchor_parser_bug repo=sample-org/sample-repo issue=#128 labels=bug,good-first-issue owner_route=repo_maintainer_review related_code=src/parser.py validation=unit_smoke promotion_target=agent_todo:todo_issue_fix status=selected_anchor freshness=fresh
```

This is the small state face for issue/PR anchor selection. It keeps labels,
owner route, related-code hint, validation surface, and promotion target visible
to agents and dashboards without storing issue bodies, private source context,
raw solver traces, or publication authority.

This keeps open-source PR-led growth connected to LoopX's core promise:
long-running agent work should be selectable, bounded, reviewable, and improved
through human feedback.
