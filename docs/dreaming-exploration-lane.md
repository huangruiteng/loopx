# Dreaming Exploration Lane

LoopX should eventually support a separate dreaming / exploration lane
for long-running projects. This lane is not the same as the project agent that
is actively shipping work. Its job is to spend low-pressure background time on
cross-run learning, option discovery, and refactor warnings.

## Why This Exists

Project agents are optimized for the current task:

- preserve local context,
- execute the next bounded change,
- avoid scope creep,
- respect active worktree and delivery pressure.

That makes them a poor fit for broad exploration. The same agent that is trying
to land a fix should not also be asked to freely rethink architecture, search
for alternatives, or propose large refactors. Those activities are valuable,
but they need a separate lane with different permissions and output rules.

Recent agent-platform and research signals point in the same direction:

- Anthropic's Managed Agents dreaming feature frames dreaming as scheduled
  review of previous sessions and memory stores, extracting patterns and
  curating memory so agents improve between sessions.
- Auto-Dreamer frames the same idea as offline memory consolidation: separate
  fast per-session acquisition from slower cross-session abstraction, pruning,
  and replacement.
- Agent-memory surveys identify continual consolidation, trustworthy
  reflection, learned forgetting, and privacy governance as open engineering
  problems for autonomous agents.

LoopX should adopt the useful shape, not the hype: dreaming is a
governed background lane for consolidation and proposals, not autonomous
permission to rewrite project truth.

## Priority

Priority: **P1 after the operator gate and reward loop are stable**.

This lane should not block v0.1 bootstrap, registry sync, status contract,
operator dashboard, or project-local refresh. It becomes important once several
real projects are connected and LoopX has enough run history for
cross-project learning to be useful.

## Role

The dreaming / exploration agent can act as:

- **Explorer**: search alternatives, compare designs, read adjacent docs,
  inspect slow-moving background questions, and prepare options.
- **Memory consolidator**: compress repeated run lessons into project-local
  playbooks, proposed skill updates, or active-state suggestions.
- **Refactor applicant**: identify when repeated local fixes suggest a larger
  refactor, but file it as an application for review rather than making the
  change directly.
- **Warning agent**: flag risks that busy project agents may normalize away:
  duplicated state, stale docs, unsafe public/private boundary drift,
  recurring validation failures, or accumulating local-only glue.

## Permissions

Default permissions are intentionally narrow:

- read project state, run history, public docs, and explicit private local
  state only when the owner project allows it;
- do not mutate project files by default;
- do not append human reward or controller opt-in;
- do not rewrite active project truth without an operator gate;
- never publish private evidence into public docs or examples.

The output of dreaming is a proposal, warning, or candidate patch plan. The
operator or project controller decides whether it becomes normal project work.

## Relationship To Replanning

Dreaming and autonomous replanning are control-plane planning lanes. They are
allowed to repair the execution track, summarize cross-run patterns, and create
reviewable options. They must not silently become the task policy that decides
how the project agent solves the current implementation problem.

Use this boundary:

| Lane | Output authority | Typical output | Promotion path |
| --- | --- | --- | --- |
| Delivery agent policy | Executes within the current authorized boundary. | Implementation plan, debug strategy, validation choice, bounded patch. | Writes validated work events and active-state updates after delivery. |
| Autonomous replan | Bounded control-plane obligation when execution is stuck or stale. | Split/retire/add todo, request blocker writeback, ask for operator decision, name next validation command and stop condition. | Writes control-plane state only after validation, or routes to user/controller gate. |
| Dreaming / exploration | Advisory proposal by default. | Refactor warning, memory consolidation, option comparison, archive suggestion, risk note. | Enters operator/controller review before becoming normal delivery work or active project truth. |

The question for any planning output is whether it is `authority` or
`proposal`. Guard and freshness outputs can be authority-like control signals;
dreaming outputs are proposals unless a later operator/controller decision
promotes them. This keeps LoopX from becoming a second brittle agent
while still letting it maintain the long-horizon execution track.

For periodic autonomous replan, keep the ownership split explicit:

| Layer | Responsibility |
| --- | --- |
| LoopX | Detect that a periodic review is due from compact run history, state freshness, quota, and boundary facts; emit the obligation, stop condition, and compact guidance vocabulary; record the later replan acknowledgement. |
| Agent loop | Read the obligation during preflight, route the current turn into a bounded replan segment, inject current state into the model/executor, run validated todo writes, and spend only after writeback. |
| Model / executor | Decide semantically which work to keep, split, add, retire, or escalate to a user/controller decision; explain the tradeoff and choose the next bounded slice. |

The v0 implementation may compute the periodic-review trigger synchronously in
`status` / `quota` because that is deterministic control-plane projection. If
the review becomes more expensive or semantic, move it to a server/dreaming
planning lane as an advisory proposal. The server may run that proposal in
parallel with delivery observation, but promotion and execution should remain
client-serial through the normal agent loop, `quota should-run`, and
goal-boundary checks.

## Run Record Shape

Dreaming runs should be visible but not mixed with delivery runs:

```json
{
  "goal_id": "example-project-main-control",
  "classification": "dreaming_exploration_proposal",
  "recommended_action": "review the proposed refactor warning in the operator gate",
  "operator_question": "Should this project open a refactor task for duplicate state handling?",
  "agent_command": null,
  "dreaming": {
    "lane": "exploration",
    "evidence_window": "last_20_runs",
    "proposal_type": "refactor_warning",
    "confidence": "medium",
    "requires_project_controller": true
  }
}
```

Candidate classifications:

- `dreaming_exploration_proposal`
- `dreaming_memory_consolidation`
- `dreaming_refactor_warning`
- `dreaming_archive_suggestion`

These should normally enter `waiting_on=user_or_controller` with
`operator_question`, not `waiting_on=codex`, because the lane is advisory by
default.

## UI Implication

The dashboard should show dreaming output as a separate lane or badge:

```text
Goal
  Operator gate: approve / reject / defer proposal
  Delivery lane: latest project-agent run
  Dreaming lane: refactor warning or memory consolidation proposal
```

This keeps project-agent work clean while still giving the user a central place
to review broader learning and refactor requests.

`loopx status` should expose the proposal plus a compact lane badge:

```json
{
  "dreaming_proposal": {
    "schema_version": "dreaming_proposal_v0",
    "classification": "dreaming_exploration_proposal",
    "proposal_type": "refactor_warning",
    "advisory": true,
    "execution_allowed": false,
    "delivery_spend_allowed": false
  },
  "dreaming_lane_badge": {
    "schema_version": "dreaming_lane_badge_v0",
    "lane": "dreaming",
    "label": "Dreaming",
    "status": "dreaming_exploration_proposal",
    "proposal_type": "refactor_warning",
    "advisory": true,
    "interrupts_delivery": false,
    "review_required": true,
    "execution_allowed": false,
    "delivery_spend_allowed": false,
    "promoted_to_delivery": false
  }
}
```

The badge intentionally carries routing facts, not the full explanation. The
full rationale stays in `dreaming_proposal` and the run artifact, while
dashboards and heartbeat consumers can render a separate Dreaming lane without
mistaking the advisory proposal for delivery work.

## First Implementation Slice

The first useful slice is documentation and status schema, not an autonomous
agent:

1. Add public vocabulary for dreaming classifications and proposal fields.
2. Let `loopx status` surface dreaming proposals as operator gates.
3. Add a local-only command or script that reads recent run history and emits a
   dry-run proposal without writing project files.
4. Only after real proposals prove useful, add scheduled heartbeats or
   automation.

The local-only entry point is:

```bash
loopx dreaming dry-run --goal-id <goal-id> --limit 20
```

This command reads compact run history through the selected registry/runtime
root and returns an advisory `run_record_preview`. It does not append runtime
history, mutate active state, grant an `agent_command`, or spend quota. The
preview is meant for operator/controller review before any proposal is promoted
into ordinary delivery work.

## Server-Managed Planning Semantics

A future LoopX server may schedule dreaming/planning work, but the
server-owned lane keeps the same authority boundary as the CLI dry run:

```json
{
  "schema_version": "server_managed_planning_contract_v0",
  "lane": "dreaming_planning",
  "authority": "proposal_only_until_promoted",
  "may_rank_candidate_todos": true,
  "may_suggest_evidence_probes": true,
  "may_execute_protected_actions": false,
  "may_read_private_material": false,
  "may_mutate_active_state": false,
  "may_spend_delivery_quota": false,
  "promotion_required": true,
  "promotion_requirements": [
    "operator_or_controller_approval",
    "normal_quota_should_run_decision",
    "goal_boundary_write_scope_approval",
    "public_private_boundary_scan_for_public_artifacts"
  ]
}
```

The server may rank candidate todos, propose evidence probes, and emit refactor
or memory-consolidation warnings. It may not execute a protected action, read
private material, mutate active state, append delivery history, or spend
delivery quota until the proposal is promoted through the normal operator,
quota, and goal-boundary path. This keeps dreaming useful for long-horizon
product taste while preventing it from becoming a second hidden project agent.

Acceptance criterion: a project can receive a dreaming proposal without the
project agent being interrupted, and the user can approve, reject, or defer it
from LoopX.

## References

- Anthropic, "New in Claude Managed Agents: dreaming, outcomes, and
  multiagent orchestration":
  <https://claude.com/blog/new-in-claude-managed-agents>
- Auto-Dreamer: Learning Offline Memory Consolidation for Language Agents:
  <https://arxiv.org/abs/2605.20616>
- Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging
  Frontiers:
  <https://arxiv.org/abs/2603.07670>
