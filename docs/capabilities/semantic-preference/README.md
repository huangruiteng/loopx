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

## Module-owned surfaces

`surfaces` is a mapping keyed by arbitrary module-qualified ids. The runtime
does not branch on `issue_fix`, `content_ops`, or any other domain name.

```json
{
  "schema_version": "semantic_preference_hook_config_v0",
  "enabled": true,
  "provider": {
    "id": "local_memory",
    "argv": ["semantic-preference-provider"],
    "timeout_seconds": 30,
    "probe_argv": ["semantic-preference-provider", "doctor"],
    "setup_hints": {
      "install": "Install the provider from its official distribution.",
      "configure": "Configure it locally, then rerun this doctor with --execute."
    }
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
  ]
}
```

Provider stderr and non-zero output are reduced to a bounded failure kind.
`fail_open` returns no items and lets the domain continue; `fail_closed` stops
the caller with an actionable error. Provider failures do not become user
gates automatically.

`provider.id`, `probe_argv`, and `setup_hints` are optional. They provide
provider-neutral discovery without teaching LoopX how to install one specific
memory system. `probe_argv` must be a read-only health check owned by the
provider. The doctor never installs packages, starts services, changes config,
or writes credentials; setup hints are guidance for an explicit operator action.

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
```

Receipts contain only surface, application id, outcome, optional public
artifact reference, and hashes of provider-owned preference references. The
command returns the receipt without writing a file. Callers can attach it to
the existing evidence log, todo evidence, or `refresh-state` record; the hook
does not maintain a second reward or memory ledger.

`--context` is repeatable and each entry uses `lower_snake=value` syntax.
Invalid config, context, surface, or fail-closed requests return a structured
`semantic_preference_error_v0` payload with exit code 2 instead of a Python
traceback.

## Domain integration

```python
from loopx.capabilities.semantic_preference import application_receipt, recall

preferences = recall(
    config_path,
    project=project_root,
    surface="issue_fix.pr_description",
    execute=True,
)
# The issue-fix module decides whether and how to apply preferences["items"].
receipt = application_receipt(
    surface="issue_fix.pr_description",
    application_id="pr-123-description-v2",
    outcome="applied",
    preference_refs=[item["preference_ref"] for item in preferences["items"]],
)
# Write `receipt` through an existing LoopX evidence/state surface.
```
