# Decision Scope v0

Status: public-safe protocol contract for scoped user/controller decisions.

User gates are not global booleans. A user or controller decision should say
which authority is still needed, and an agent action should say which authority
it depends on. LoopX can then decide whether the selected action is blocked,
whether a safe fallback may continue, or whether the projection itself needs
repair.

This contract turns the interaction catalog's Decision Scope Model into a
machine-facing schema. It does not implement the runtime migration by itself;
CLI/state/status/quota consumers should use this shape as the migration target.

## Fields

### `decision_scope`

Attached to a user todo, operator gate, or controller decision.

| Field | Required | Meaning |
| --- | --- | --- |
| `kind` | yes | `private_read`, `write_scope`, `resource`, `production`, `public_claim`, `direction`, or `other`. |
| `granularity` | yes | `action`, `lane`, `goal`, `project`, or `global`. |
| `scope_key` | yes | Public-safe key that names the blocked authority, path, lane, resource, or decision. |
| `decision_id` | no | Stable todo/gate/run id when the decision already exists. |
| `expires_at` | no | Optional ISO timestamp for temporary authority. |
| `reason_summary` | no | Public-safe one-line reason shown in status/UI. |

### `required_decision_scopes`

Attached to an agent todo, next action, handoff packet, or candidate runtime
action. Each item uses the same `kind`, `granularity`, and `scope_key` fields
as `decision_scope`.

An action is covered by a gate when at least one unresolved decision scope
matches or dominates one of its required scopes. Dominance is intentionally
small in v0:

- same `kind` and same `scope_key`;
- same `kind` and broader `granularity` over the same goal/project boundary;
- explicit `scope_key="*"` only when the owner/controller recorded it.

If the relation is ambiguous, status/quota must repair projection or ask the
user/controller; it must not infer permission from prose.

### Markdown metadata compact form

Todo metadata stores decision scopes as a compact public-safe token instead of
inline JSON:

```md
<!-- loopx:todo decision_scope=direction:action:benchmark_target_choice -->
<!-- loopx:todo required_decision_scopes=direction:action:benchmark_target_choice -->
```

The token is `kind:granularity:scope_key`. `decision_scope` is singular on a
user gate; `required_decision_scopes` may contain a comma-separated list on an
agent todo. Status/quota normalize those tokens back into
`decision_scope_v0` objects before evaluating gate coverage.

### `safety_class`

Attached to agent work candidates and selected actions.

| Value | Meaning |
| --- | --- |
| `read_only` | May inspect public/local allowed state without mutation. |
| `local_write` | Mutates repository or LoopX state within the current write boundary. |
| `external_run` | Launches or advances external compute, benchmark, CI, or hosted runtime work. |
| `protected_write` | Writes protected state, production systems, private materials, public submissions, or external authority surfaces. |

`safety_class` does not grant permission. It lets LoopX choose the correct gate
comparison and notification behavior.

## Minimal Shape

```json
{
  "schema_version": "decision_scope_v0",
  "user_todo": {
    "todo_id": "todo_user_123",
    "decision_scope": {
      "kind": "private_read",
      "granularity": "project",
      "scope_key": "private_authority_source",
      "reason_summary": "owner must approve reading private source material"
    }
  },
  "agent_todo": {
    "todo_id": "todo_agent_123",
    "required_decision_scopes": [
      {
        "kind": "private_read",
        "granularity": "project",
        "scope_key": "private_authority_source"
      }
    ],
    "required_write_scopes": ["docs/**"],
    "safety_class": "read_only"
  },
  "scope_relation": {
    "state": "gate_covers_action",
    "fallback_available": true,
    "user_channel": "notify_concrete_gate",
    "agent_channel": "execute_independent_fallback"
  }
}
```

## Status And Quota Rules

Status and quota should read decision scopes in this order:

1. explicit `decision_scope`, `required_decision_scopes`, and `safety_class`;
2. structured todo fields such as `task_class`, `required_write_scopes`, and
   action kind;
3. compatibility inference from legacy title/body text;
4. projection repair when no confident relation exists.

Markdown text inference is a lint, not gate truth. A legacy `Next Action`
regex may detect suspicious prose and create a projection-gap warning, but it
must not override an explicit `interaction_contract`, structured todo fields,
or an open runnable agent todo.

LLM-assisted interpretation belongs only in cold-path authoring helpers or
repair proposals. It may suggest a structured decision scope, but it must not
decide delivery gates, spend policy, write permission, or safe fallback at
runtime.

## Migration Phases

1. **Contract only:** document this schema and keep current behavior unchanged.
2. **State authoring:** teach todo/gate write paths to accept and preserve
   `decision_scope` and `required_decision_scopes`. `safety_class` remains a
   later authoring field.
3. **Projection:** surface the fields in status, quota, review packets, and
   frontstage local ops mode.
4. **Hot path:** make status/quota prefer structured scope relation over text
   inference.
5. **Lint fallback:** keep regex and optional LLM proposals as projection-gap
   repair helpers, not runtime authority.

## Failure Semantics

- Missing structured fields on legacy state: fall back to compatibility lint
  and emit a projection-gap repair hint.
- Conflicting structured fields: fail closed with a concrete blocker.
- User todo requires action but has no concrete payload: report
  `具体 user todo 未投影，需修复 LoopX 状态投影`.
- Action claims no gate but requires protected write: block and repair scope.
- Safe fallback exists outside the gate scope: notify the concrete gate, run
  the independent fallback, validate, write back, and spend once.

## Acceptance Checks

A decision-scope implementation is acceptable when:

1. structured fields can be authored without hand-editing Markdown;
2. status and quota expose the computed scope relation;
3. explicit fields outrank title/body regex inference;
4. ambiguous scope fails closed instead of guessing;
5. safe fallback continues only when its required scopes are independent; and
6. legacy regex/LLM assistance remains a cold-path repair signal, not runtime
   gate truth.
