# todo_suggestion_prompt_v0

`todo_suggestion_prompt_v0` is a prompt contract for asking the user's current
project agent to produce a small candidate todo decision queue.

LoopX does not analyze the repository in this path. LoopX only provides the
bounded task body, candidate schema, promotion policy, source lanes, and
frequency limits. The project agent reads the current repo and returns
`suggested_todos`; those candidates are not formal LoopX todos until the user
or primary controller promotes one.

## Command

```bash
loopx todo suggest --goal-id <goal-id> --from recent-repo --from loopx-deferred --limit 3
```

Useful triggers:

- post-connect onboarding, after the project has a valid LoopX state;
- explicit user request such as "what looks worth doing next?";
- no runnable agent todo after status/quota inspection;
- material repo changes since the last candidate review.
- `quality-watch` cadence turns, where the agent should compare fresh signals
  against the last known state and return candidates only for new or
  still-uncovered evidence.

Avoid running this on every heartbeat. The default limit is 3 and the hard cap
is 5.

## Candidate Shape

The agent's output should use a `suggested_todos` list. Each item uses
`suggested_todo_candidate_v0`:

```json
{
  "schema_version": "suggested_todo_candidate_v0",
  "candidate_id": "suggested_todo_repo_smoke_gap",
  "title": "Add a smoke for the new setup path",
  "why_now": "Recent docs changed the setup flow, but no smoke covers the wording.",
  "evidence": ["README.md", "examples/project/project-prompt-smoke.py"],
  "first_safe_action": "Inspect the existing setup smoke and draft one failing assertion.",
  "requires_user_decision": false,
  "risk": "low",
  "value": "prevents onboarding regressions",
  "confidence": "medium",
  "suggested_owner_agent": "codex-main-control",
  "promotion_preview": "loopx todo add --goal-id <goal-id> --role agent --text '...'"
}
```

## Rules

- Candidate generation is read-only by default.
- A candidate is not a user todo.
- `requires_user_decision=true` is only for owner choice, protected access,
  external action, or private material approval.
- The agent may return an empty list when evidence is weak or already covered.
- Promotion uses `loopx todo add` after explicit approval; this protocol does
  not write active state.
