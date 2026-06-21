# Agent Profile Contract

`agent_profile_v0` is the registry-owned source of truth for recurring Goal
Harness workers. It tells an automation who it is, what lane it should prefer,
which checkout policy it must obey, and how it should hand work back for
review. It is not a replacement for todo claims, user gates, capability gates,
or write-scope checks.

The practical problem is simple: once a goal has one primary agent and one or
more side agents, each worker needs stable identity and scope without copying a
large custom prompt into every automation. The profile makes that identity
durable and inspectable.

## Layering

Keep three concepts separate:

| Layer | Question answered | Source of truth |
| --- | --- | --- |
| `agent_profile_v0` | Who is this agent and what lane should it normally work in? | Project registry `coordination.agent_profiles` |
| `agent_member_v0` | What should a dashboard or review packet show about the active agent? | Read-only projection from registry, quota, todos, and run history |
| `claimed_by` / future `task_lease_v0` | Who currently owns this exact todo? | Active-state todo metadata, later lease records |

The profile can guide default selection and prompt generation. It must not
override a user gate, quota state, required capability, protected write scope,
workspace guard, or an existing claim/lease on the selected todo.

## Registry Shape

The preferred registry shape is:

```json
{
  "coordination": {
    "primary_agent": "codex-main-control",
    "registered_agents": ["codex-main-control", "codex-side-bypass"],
    "agent_profiles": {
      "codex-main-control": {
        "schema_version": "agent_profile_v0",
        "agent_id": "codex-main-control",
        "role": "primary-agent",
        "scope_summary": "Benchmark execution, high-risk runtime work, final review, and publication.",
        "default_task_classes": ["advancement_task"],
        "preferred_action_kinds": ["benchmark_*", "primary_review_*"],
        "avoid_action_kinds": [],
        "worktree_policy": {
          "mode": "primary_checkout_allowed",
          "requires_independent_worktree": false
        },
        "review_policy": {
          "can_self_merge": true,
          "reviews_side_agent_work": true
        }
      },
      "codex-side-bypass": {
        "schema_version": "agent_profile_v0",
        "agent_id": "codex-side-bypass",
        "role": "side-agent",
        "primary_agent": "codex-main-control",
        "scope_summary": "Productization, showcase, documentation, and low-risk control-plane ergonomics.",
        "default_task_classes": ["advancement_task", "continuous_monitor"],
        "preferred_action_kinds": ["showcase_*", "product_*", "repository_quality_monitor"],
        "avoid_action_kinds": ["benchmark_*", "production_*", "primary_review_*"],
        "worktree_policy": {
          "mode": "independent_worktree_required",
          "requires_independent_worktree": true
        },
        "review_policy": {
          "can_self_merge": "small_validated_docs_or_metadata_only",
          "handoff_agent": "codex-main-control",
          "handoff_required_for": ["runtime", "benchmark_adapter", "permission", "public_evidence_policy"]
        }
      }
    }
  }
}
```

`registered_agents` stays as the compatibility list for old projects and quick
validation. `agent_profiles` is the richer contract. A project should fail
closed when a todo is claimed by an unknown agent, and it should warn when a
profile exists without a matching `registered_agents` entry.

## Prompt Generation

Today, scoped heartbeat setup passes both identity and natural-language scope:

```bash
loopx heartbeat-prompt --thin \
  --goal-id loopx-meta \
  --agent-id codex-side-bypass \
  --agent-scope "Productization showcase docs lane. Avoid benchmark work."
```

After `agent_profile_v0` is implemented, the common path should be:

```bash
loopx heartbeat-prompt --thin \
  --goal-id loopx-meta \
  --agent-id codex-side-bypass
```

The CLI resolves `coordination.agent_profiles.codex-side-bypass`, renders the
role, primary agent, scope summary, worktree policy, review policy, and
selection hints, then records the profile version in the generated prompt.
`--agent-scope` can remain as a temporary override for migration and detached
tests, but profile-backed generation should be preferred for registered goals.

If a goal has registered profiles and the requested profile is missing, prompt
generation should fail with a concrete registration command instead of emitting
an unscoped automation body.

## Selection Rules

The profile should make side-agent behavior more predictable without turning a
scope summary into authority:

1. Filter out todos already claimed by another agent unless the profile says the
   current agent may review that owner.
2. Prefer todos whose action kind or title matches `preferred_action_kinds`.
3. Skip todos whose action kind matches `avoid_action_kinds` unless the primary
   agent explicitly transfers or claims them to this agent.
4. Enforce capability gates, workspace guards, and write-scope checks after the
   profile match.
5. If no in-scope todo is executable, write a concrete blocker or add a primary
   review / routing todo instead of silently taking a primary-owned item.

These rules are advisory until hard `task_lease_v0` exists. The active todo's
`claimed_by` field remains the visible ownership marker for current work.

## Worktree And Review Policy

Side-agent productization is only safe when checkout policy is explicit. The
profile should distinguish:

- `primary_checkout_allowed`: the agent may work from the main project checkout
  when no local policy forbids it.
- `independent_worktree_required`: repository edits must happen in a separate
  git worktree and branch.
- `read_only_only`: the agent may inspect and write control-plane notes, but
  must not edit public repo files.

Review policy should be equally explicit. A side agent may self-merge only when
the profile and repository policy both allow it, validation passes, and the
change is small, public-safe, and low risk. Otherwise the side agent should add
or update a todo claimed by the primary agent for review, verification, and
merge.

## Projection

`agent_member_v0` should be a read-only status/review-packet projection derived
from the profile and current work:

```json
{
  "schema_version": "agent_member_v0",
  "agent_id": "codex-side-bypass",
  "role": "side-agent",
  "primary_agent": "codex-main-control",
  "scope_summary": "Productization, showcase, documentation, and low-risk control-plane ergonomics.",
  "worktree_policy": "independent_worktree_required",
  "current_claims": ["todo_abc123"],
  "last_action": "docs_only_self_merge",
  "handoff_agent": "codex-main-control"
}
```

Dashboards may show this member card to humans, but writes still go through
LoopX todo, gate, lease, reward, and refresh commands.

## Migration Path

1. Keep `coordination.registered_agents` and `coordination.primary_agent` as the
   required minimum.
2. Add optional `coordination.agent_profiles` for goals with multiple agents.
3. Teach `heartbeat-prompt --agent-id` to resolve profile-backed scope when
   `--agent-scope` is omitted.
4. Project `agent_member_v0` in status/review packets after the runtime can
   derive current claims and last action.
5. Promote `task_lease_v0` separately for contention, TTL, renewal, transfer,
   and overlapping write-scope conflict checks.

This sequence keeps old single-agent projects working while making multi-agent
projects safer and less prompt-fragile.
