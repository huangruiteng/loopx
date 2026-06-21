# Reward-Style Replanning Hints

LoopX already records exact run-bound `human_reward` overlays and
operator gates. The next product problem is not "train on the user's chat".
It is smaller and safer: when a human repeatedly rewards, corrects, or steers a
long-running agent, LoopX should convert that explicit feedback into
compact replanning hints that help the next bounded turn choose a better todo.

This note defines the product shape for public-safe reward-style learning. It
is a design contract, not an implementation of a ranking model.

## Product Goal

Make human feedback survive into replanning without turning it into hidden
autonomy.

The replanner should be able to answer:

- what kind of work the user recently rewarded;
- what kind of repeated behavior the user corrected;
- which future candidate todos are more likely to be useful;
- what feedback changed in the plan since the last turn;
- where a hint stops because a gate, claim, scope, capability, or boundary has
  higher authority.

The output should improve candidate ordering and explanation. It must not grant
permission, approve a gate, claim a todo, spend quota, publish artifacts, or
read private material.

## Inputs

Only explicit and compact sources should feed this lane:

- `human_reward` overlays attached to exact runs;
- user corrections that were written back as public-safe todos, blockers,
  reward reasons, or refresh-state notes;
- repeated steering patterns already summarized in run history, such as
  "surface-only progress loop" or "missing validation evidence";
- explicit owner decisions recorded through LoopX commands.

Excluded inputs:

- raw chat transcripts;
- private documents or internal links;
- raw benchmark logs, trajectories, verifier tails, or production traces;
- inferred personality profiles;
- hidden preferences that the user cannot inspect or correct.

## Hint Shape

A future implementation can project compact hints as `replan_hint_v0` records:

```json
{
  "schema_version": "replan_hint_v0",
  "goal_id": "loopx-meta",
  "source_refs": [
    {"kind": "human_reward", "run_generated_at": "2026-06-20T04:16:49+08:00"},
    {"kind": "todo", "todo_id": "todo_abc123"}
  ],
  "hint_kind": "prefer_candidate",
  "summary": "Prefer bounded work that produces validated outcome evidence over surface-only docs churn.",
  "applies_to": {
    "task_class": "advancement_task",
    "action_kinds": ["outcome_evidence", "validated_writeback"]
  },
  "anti_pattern": "surface_only_progress_loop",
  "strength": "medium",
  "confidence": "explicit",
  "expires_after_days": 30,
  "hard_gate": false,
  "boundary": {
    "may_reorder_candidates": true,
    "may_override_user_gate": false,
    "may_override_claim": false,
    "may_override_scope": false,
    "may_override_capability_gate": false
  }
}
```

The important field is `hard_gate=false`. A hint is a ranking influence, not a
permission rule.

## Replanning Use

During the steering audit, LoopX can combine candidate todos with active
hints:

1. Build candidate todos from the current active state and status projection.
2. Remove candidates blocked by user gates, missing capabilities, worktree
   guards, required claims, protected write scope, or public/private boundary.
3. Apply hints only to the remaining candidates.
4. Explain the selected candidate with source refs, for example:
   "selected because recent feedback favored validated outcome evidence over
   another docs-only propagation step."
5. Preserve losing high-value candidates when the hint changes their ordering.

This keeps preference learning subordinate to the control plane. It can help the
agent choose better work, but it cannot make unsafe or unauthorized work safe.

## Operator Surface

The dashboard or review packet should show a compact "What feedback changed"
surface:

- rewarded behavior;
- corrected behavior;
- candidate ranking effect;
- source refs;
- expiration or decay;
- one-click path to retire or edit the hint.

Non-technical users should see plain-language effects, not model weights. For
example:

```text
Your last correction deprioritized "status-only updates" when a validated
artifact can be produced. This turn will prefer a bounded implementation or
evidence writeback before another summary-only note.
```

## Privacy And Boundary Rules

- Store summaries, not raw feedback bodies.
- Keep source refs to exact runs, todos, or reward overlays.
- Prefer short-lived hints with decay; old feedback should not silently govern
  new contexts forever.
- Do not merge unrelated projects into one preference profile by default.
- Do not use inferred preferences as safety policy.
- Do not expose private material in public docs, fixture data, or showcase
  examples.

## First Implementation Slices

1. **Read-only hint preview**: derive candidate hints from existing compact
   `human_reward` and todo evidence without writing them.
2. **Projection smoke**: prove that hints can reorder two safe candidate todos
   but cannot override a user gate, claim, capability gate, or side-agent
   workspace guard.
3. **Status/dashboard projection**: show at most three active hints with source
   refs and expiration.
4. **Operator edit path**: allow a user to retire or rewrite a bad hint through
   an explicit local write command.

Until those slices exist, human reward remains the durable source of truth and
replanning hints remain a product design note.
