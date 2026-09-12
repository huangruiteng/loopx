# Explicit Todo continuation: Stage A

Status: a bounded local CLI workflow. The former general memory-substrate
proposal is replaced by a cross-agent continuation workflow over the
canonical Todo authority. It does not freeze a public memory schema.

## Problem: switching coding agents mid-work

When a developer switches from one coding agent to another (e.g. Claude Code
to Codex), the target agent has no context about what was done, what was
tried and failed, and what comes next. The developer must re-explain the
entire project state. This workflow gives the source agent a structured way
to dump complete working context so the target agent can continue without
re-explanation.

Stage A solves the **same-machine, different registered agent** scenario: an
explicit handoff where the source prepares a rich continuation note and the
target inspects, verifies, and adopts the Todo. It does not implement automatic
context capture, agent-agnostic protocols, or zero-config onboarding. Those
require a different product layer beyond this control-plane primitive.

## Ownership and placement

The existing Todo coordination boundary owns current execution state, stable
Todo IDs, revision checks and claim/lease decisions. The built-in local
`file_v0` authority supplies persistence; no new capability, provider, database,
index, discovery API, recovery service or ownership protocol is introduced.
The CLI is a host adapter to that TypeScript boundary.

Historical retrieval and long-term memory belong to optional providers through
existing `decision_context` / `agent_turn_recall` capability boundaries. Their
absence does not affect this workflow. Stage A neither invokes those providers
nor grants permission to index a workspace or read source-reference bodies.

## First usable path

Prerequisites: an **already explicitly promoted local file authority**, an open,
active agent Todo claimed by a registered agent, and no lease on that Todo.
The existing metadata writer cannot prove lease-bearing updates, so Stage A
rejects hard-lease goals and lease-bearing Todos. It never promotes authority,
changes handoff mode, releases another owner's work or falls back to Markdown.

The user explicitly hands a Todo from one session to another session of a
**different registered agent on the same host**. The source writes a revision-
guarded continuation note (legacy rationale or rich context) into the existing
Todo note; the target inspects current authority, verifies local artifact
availability, and continues through the existing claim transaction with
current-authority readback. Stop source execution before continuing in the
target. Session IDs below are provenance, not authentication or a session
lease. This slice does not implement automatic host launch.

Use the same registry/runtime arguments as the existing Todo CLI. Substitute
an existing goal, Todo and registered agents for these example identifiers:

```sh
# Source: inspect current state, including its provider_revision.
loopx --format json handoff inspect --goal-id demo --todo-id todo_a \
  --agent-id agent-a --session-id source-session --workspace .

# Copy the exact returned revision into REVISION, then explicitly replace the
# current Todo note with rich handoff context from a JSON file.
loopx handoff prepare --goal-id demo --todo-id todo_a \
  --agent-id agent-a --session-id source-session --operation-id handoff-1 \
  --expected-revision "$REVISION" --from-context ./handoff-context.json

# Or use the legacy compact form (rationale + source references):
loopx handoff prepare --goal-id demo --todo-id todo_a \
  --agent-id agent-a --session-id source-session --operation-id handoff-1 \
  --expected-revision "$REVISION" --rationale 'The narrow change preserves the existing authority boundary' \
  --source-ref 'artifact:decision.md'

# Target: inspect again as the receiving agent; verify evidence and current artifact availability.
loopx handoff inspect --goal-id demo --todo-id todo_a \
  --agent-id agent-b --session-id target-session --workspace . --artifact decision.md

# Target: inspect with a readable handoff digest (any registered agent, any session).
loopx --format json handoff inspect --goal-id demo --todo-id todo_a \
  --agent-id agent-a --session-id target-session --workspace . --format digest

# Use the target inspect revision, then claim through the existing boundary.
# --target-agent-id specifies the receiving agent (defaults to --agent-id).
loopx handoff adopt --goal-id demo --todo-id todo_a \
  --agent-id agent-b --session-id target-session --operation-id resume-1 \
  --expected-revision "$REVISION" --target-agent-id agent-b --workspace . --artifact decision.md
```

Inspect reports the current goal/Todo/revision, decision rationale, source
pointers, local workspace/artifact availability and next action from the current
Todo. With `--format digest`, inspect renders a readable handoff summary that any
target agent can directly consume, including work summary, approaches tried,
next steps, files touched, key decisions, and open questions. References are
evidence pointers supplied by the source, not verified remote content. Artifact
checks prove local existence, not content integrity. Adopt preserves the Todo
ID, invokes the existing claim transaction and reads back current authority.
A same-owner claim may correctly be a no-op; it does not create a Todo or
manufacture a new lease.

## Rich handoff context

The `--from-context` flag accepts a JSON file with structured handoff context:

```json
{
  "work_summary": "Implementing cross-agent handoff with typed transfer grant. Need to enforce note invariant.",
  "approaches_tried": [
    {"approach": "Unstructured note with hash only", "outcome": "failed", "reason": "Any caller can compute public facts"},
    {"approach": "Typed transfer_grant without note validation", "outcome": "partial", "reason": "Still accepts arbitrary JSON"}
  ],
  "next_steps": ["Add shared validateContinuationNote predicate", "Add regression tests"],
  "files_touched": [
    {"path": "todo_claim.ts", "action": "edited", "summary": "Added validateContinuationNote"},
    {"path": "todo_continuation.ts", "action": "edited", "summary": "Adopt uses noteValidation.noteFacts"}
  ],
  "key_decisions": [
    {"decision": "Typed transfer_grant", "rationale": "Binds source/target/todo/revision/note"}
  ],
  "open_questions": ["Stage B should support agent-agnostic handoff?"]
}
```

Fields:
- `work_summary` (max 2000 chars): primary description of what was done and why.
  At least one of `work_summary` or `rationale` is required.
- `approaches_tried` (max 20): what was attempted, the outcome (`success`,
  `partial`, or `failed`), and why.
- `next_steps` (max 20): what the target agent should do next.
- `files_touched` (max 50): files read/edited/created/deleted, with optional
  summaries.
- `key_decisions` (max 20): decisions made and their rationale.
- `open_questions` (max 20): unresolved issues the target should address.
- Legacy: `rationale` (max 600 chars) and `source_refs` (max 20) are still
  supported for backward compat.

## Record lifecycle and failures

The source agent produces a note **only on explicit prepare**. It saves the
non-reconstructable context into the existing Todo note in one revision-guarded
update. It replaces that current note; it does not append a history or retain
an additional store. The note's marker and execution-fact fingerprint are
internal details, not a general-purpose versioned memory API.

Missing, malformed or overwritten notes permit inspection but block adoption:
ask the source to prepare a current note. A changed Todo execution fact expires
the note on read. Completion, archive and a different claim owner reject the
flow. Source prepare replaces stale notes; there is no background expiry worker.
Any provider revision change after inspect rejects a fresh adopt, even if the
Todo itself did not change. Reinspect and reconsider before using a new operation.

Normal restart reads the note from the existing durable file authority. Reuse
both the operation ID and original expected revision after an uncertain write.
A failed write leaves the previous note intact; committed-but-lost responses
recover through existing receipts. Historical receipt replay never substitutes
for current open status, owner, note and revision readback. Missing artifacts
block adoption without mutation. Do not resume execution unless `ok` and
`current_authority_verified` are both true.

There is no enablement toggle: only explicit commands run this workflow. Stop
using them to disable it; replace the note with `loopx todo update --note ...`
if it is obsolete. Existing Todo/claim commands keep their defaults. Never put
credentials or raw private transcripts in context fields; these fields share
the existing Todo projection visibility, not a private memory ACL.

## Validation and bounded next step

The focused test runs separate source and target Python CLI processes against
a disposable real file authority, plus restart, lost acknowledgment, failed
write, missing artifact, stale revision, changed owner, completed Todo, rich
context, and legacy backward-compat cases. Existing claim/update suites cover
default behavior and lease rejection.

```sh
node --experimental-strip-types --test tests/control_plane_ts/todo_continuation.test.ts
```

The shared `continuation_note` module is the single source of truth for
continuation-note validation. Both the handoff helper (`todo_continuation.ts`)
and the final claim authority (`todo_claim.ts`) use `validateContinuationNote`,
which enforces the typed `loopx-explicit-continuation` marker, bounded fields,
source session, and current `todo_facts`. An arbitrary JSON note with matching
hash is rejected because it lacks the typed invariant.

Cross-agent transfer is implemented through a typed `transfer_grant` that
binds source owner, target owner, Todo ID, exact revision, and current note facts.
Only the handoff flow (`handoff prepare/inspect/adopt`) can produce this grant;
regular `loopx todo claim` without a grant still rejects foreign-owner Todos with
`claim_owner_mismatch`, preserving the default claim behavior. Lease-bearing note
updates remain deferred to their owning boundaries.
