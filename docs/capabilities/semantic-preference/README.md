# Semantic preference hook

For the built-in OpenViking project-scoped adapter, see
[OpenViking project peer provider](openviking-project-peer.md).

LoopX can optionally recall semantic preferences before a domain action and
build a compact application receipt afterwards. The hook is deliberately thin:
the provider owns storage, ranking, and semantic content; the caller owns how a
preference affects its output and writes the receipt through existing LoopX
evidence or state surfaces.

The hook is disabled unless a caller supplies an enabled local-private JSON
config. Config files inside a git project must be ignored; tracked configs are
rejected. LoopX never copies the provider command, config path, recalled
semantic content, or raw provider errors into receipts.

The preferred provider path is an explicitly activated extension. The
compatibility path still accepts a direct subprocess `argv`; both paths use the
same core request, response, failure-policy, and receipt contracts.

## Module-owned surfaces

`surfaces` is a mapping keyed by arbitrary module-qualified ids. The runtime
does not branch on `issue_fix`, `content_ops`, or any other domain name.

```json
{
  "schema_version": "semantic_preference_hook_config_v0",
  "enabled": true,
  "provider": {
    "id": "local_memory",
    "extension_id": "semantic-preference-provider",
    "args": ["--project", "."]
  },
  "surfaces": {
    "issue_fix.pr_description": {
      "query": "PR description structure and reviewer language preferences"
    },
    "content_ops.draft_language": {
      "query": "Draft language and section preferences",
      "limit": 3
    }
  }
}
```

`extension_id` resolves only from enabled, doctor-verified local activation
state. `args` are appended after the manifest-owned entrypoint arguments. The
manifest owns protocol, permission, timeout, and doctor; config cannot override
them. `extension_state_file` is an optional local-private override for tests or
specialized embeddings; the CLI's global `--runtime-root` selects the normal
isolated runtime. If an activated extension is later disabled or unavailable,
recall follows the surface's existing `fail_open` or `fail_closed` policy.

For a legacy provider that has not adopted the extension manifest, replace the
provider object with:

```json
{
  "id": "local_memory",
  "argv": ["semantic-preference-provider"],
  "timeout_seconds": 30,
  "probe_argv": ["semantic-preference-provider", "doctor"]
}
```

`argv` and `extension_id` are mutually exclusive.

A domain module owns the surface id, query, context keys, and decision about
how recalled items influence its output. Adding another module is a config
change, not a LoopX runtime change.

## Provider protocol

On `recall --execute`, LoopX sends one
`semantic_preference_provider_request_v0` JSON object on stdin. A provider
returns one `semantic_preference_provider_response_v0` object on stdout:

```json
{
  "schema_version": "semantic_preference_provider_response_v0",
  "items": [
    {
      "preference_ref": "provider-owned-reference",
      "summary": "Use concise Chinese sections for this surface."
    }
  ],
  "corpus_inventory": [
    {
      "corpus_id": "project_preferences",
      "scope_ref": "provider-owned-scope-reference",
      "read_role": "primary",
      "write_mode": "provider_managed",
      "write_actor_ref": "provider-owned-actor-reference",
      "source_of_truth": "repository_revision_and_explicit_feedback",
      "writeback_triggers": ["explicit_feedback", "source_truth_changed"],
      "closure_policy": "write_wait_l2_read_scoped_recall"
    }
  ]
}
```

`corpus_inventory` is optional and provider-neutral. It describes which bounded
corpora contributed to the recall and what closes a maintenance decision; it
does not contain raw memory. LoopX validates the inventory and derives
`semantic_preference_maintenance_guidance_v0`. A fixed function boundary can
therefore expose the corpus ids, writeback triggers, and closure policy in the
same provider call instead of relying on the agent to remember a separate
runbook. Providers that omit the field remain compatible.

An explicit feedback or source-of-truth change does not imply that every corpus
must be rewritten. The caller either performs the provider-owned update and
verifies the configured closure policy, or records a `no_write_rationale`.
LoopX does not infer semantic updates, mirror provider storage, or turn a soft
preference into an execution permission.

Provider stderr and non-zero output are reduced to a bounded failure kind.
`fail_open` returns no items and lets the domain continue; `fail_closed` stops
the caller with an actionable error. Provider failures do not become user
gates automatically.

`provider.id` and `setup_hints` are optional. Legacy `probe_argv` must be a
read-only health check owned by the provider. Extension providers use the
manifest doctor instead. Neither doctor path installs packages, starts
services, changes config, or writes credentials; setup hints remain guidance
for an explicit operator action.

## CLI

```bash
loopx semantic-preference recall \
  --project . \
  --config <ignored-config.json> \
  --surface issue_fix.pr_description \
  --context repository=owner/repo \
  --execute

loopx semantic-preference doctor \
  --project . \
  --config <ignored-config.json> \
  --execute

loopx semantic-preference receipt \
  --surface issue_fix.pr_description \
  --application-id pr-123-description-v2 \
  --outcome applied \
  --preference-ref <provider-owned-reference> \
  --artifact-ref https://github.com/owner/repo/pull/123

loopx semantic-preference maintenance-receipt \
  --trigger source_truth_changed \
  --outcome verified \
  --corpus-id project_preferences \
  --scope-ref <provider-owned-scope-reference> \
  --evidence-ref project-preference-readback-v2
```

Receipts contain only surface, application id, outcome, optional public
artifact reference, and hashes of provider-owned preference references. The
command returns the receipt without writing a file. Callers can attach it to
the existing evidence log, todo evidence, or `refresh-state` record; the hook
does not maintain a second reward or memory ledger.

Maintenance receipts are also stateless. They contain only the trigger,
outcome, corpus ids, optional compact evidence reference, and hashes of scope
references. A `verified` outcome means the provider-specific write, queue or
index wait, direct read, and scoped recall required by the inventory have all
passed. A `no_write_rationale` outcome records that the trigger was assessed
but no durable semantic change was needed.

`--context` is repeatable and each entry uses `lower_snake=value` syntax.
Invalid config, context, surface, or fail-closed requests return a structured
`semantic_preference_error_v0` payload with exit code 2 instead of a Python
traceback.

## Domain integration

For reviewed reward-memory records, Stage 3 also exposes
`run_semantic_preference_reward_memory`. The caller supplies the exact corpus,
module-owned surface, query steps, read-authority checkpoint, provider binding,
and model application callback. The shared reward-memory core performs the
scope/freshness/conflict guards and returns a compact receipt; this module does
not add another store, router, or scheduler. Function-boundary mode permits one
query, while bounded agentic mode permits at most three caller/model-authored
queries.

```python
from loopx.capabilities.semantic_preference import application_receipt, recall

preferences = recall(
    config_path,
    project=project_root,
    surface="issue_fix.pr_description",
    execute=True,
)
# The same result identifies provider-owned corpora that must be assessed after
# explicit feedback or a source-of-truth change.
guidance = preferences.get("maintenance_guidance")
# The issue-fix module decides whether and how to apply preferences["items"].
receipt = application_receipt(
    surface="issue_fix.pr_description",
    application_id="pr-123-description-v2",
    outcome="applied",
    preference_refs=[item["preference_ref"] for item in preferences["items"]],
)
# Write `receipt` through an existing LoopX evidence/state surface.
```
