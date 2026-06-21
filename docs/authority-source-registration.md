# Authority Source Registration

`loopx register-authority-source` records one local authority or material
source for a goal without storing the raw source reference. It is meant for
internal docs, private repositories, owner-review packets, and validation
snapshots where the project agent needs a public-safe projection, not the raw
link.

The command writes the selected source registry, usually the ignored
`.loopx/registry.json`, and may sync a compact projection into the shared
global registry. Public repository files should keep examples and contracts
only.

## Registry Boundary Classes

LoopX exposes a registry boundary classifier:

```bash
loopx registry-boundary --path .loopx/registry.json --require-gitignored
```

Use it before committing registry-related work. It separates four surfaces:

| Boundary | Storage | GitHub policy |
| --- | --- | --- |
| project-local private registry | `.loopx/registry.json` in one repo | must be ignored; do not push |
| shared global-local registry | `<runtime-root>/registry.global.json` | local control plane only; do not push |
| public-safe projection | generated compact counts/roles with no raw refs | ignored by default; do not push runtime registry files to GitHub |
| public example fixture | hand-written examples under `examples/` | may be tracked only when it is a fixture/contract, not live state |

The classifier reports `classification`, `should_be_gitignored`,
`github_push_allowed`, `private_marker_count`, git tracked/ignored state, and
any boundary risks. `loopx check` also reports the active registry
boundary so publish-time scans can catch a local registry that accidentally
became tracked.

This distinction is intentional: LoopX provides registry capability, and
LoopX should use that capability to manage its own source authority, but
runtime registry files are still state, not public repository artifacts. Public
docs may describe schemas, examples, and compact counts; raw local registries,
global-local registries, and generated public-safe projections stay ignored
unless they are explicitly authored as example fixtures.

## Minimal Command

```bash
loopx register-authority-source \
  --goal-id example-goal \
  --source-id product-vision \
  --source-ref "https://example.invalid/private/doc" \
  --source-kind doc \
  --role current_authority \
  --freshness current \
  --owner-status owner_review_pending \
  --gate-status readable \
  --boundary private_redacted \
  --revision "rev-2026-06-07" \
  --conflict-rule "newer owner-approved source wins" \
  --topic product_vision \
  --dry-run
```

`--source-ref` is hashed and redacted. The registry stores
`source_ref_kind`, `source_ref_sha256`, and `source_ref_redacted=true`; it does
not store the raw URL, local path, token, or document id.

## Stored Shape

The local registry receives a compact material entry under
`authority_registry.project_materials[source_id]`:

```json
{
  "schema_version": "authority_source_registration_v0",
  "id": "product-vision",
  "role": "current_authority",
  "source_kind": "doc",
  "freshness": "current",
  "owner_status": "owner_review_pending",
  "gate_status": "readable",
  "boundary": "private_redacted",
  "revision": "rev-2026-06-07",
  "conflict_rule": "newer owner-approved source wins",
  "source_ref_kind": "url",
  "source_ref_sha256": "..."
}
```

The same compact source is appended to `authority_sources` so local operators can
see the registered sources. Global sync strips this to summary counts through
the existing authority-registry projection.

## Project-Local Doc Registry Mechanism

Doc registry is a general LoopX mechanism, not an agent-harness-specific
import path. Each managed project should own its authority surface in its own
project-local registry, usually `docs/meta/DOC_REGISTRY.yaml` plus the goal's
ignored `.loopx/registry.json`. For connected projects without a tracked
`DOC_REGISTRY.yaml`, the ignored `.loopx/registry.json` is still the
project-local doc registry surface through `authority_registry.topic_authority`
and `authority_registry.project_materials`; project agents should not downgrade
new durable materials to memory-only notes.

When a project agent discovers a relevant design doc, research note, benchmark
paper, owner packet, migration report, or external material, the default order
is:

1. Identify the target project and goal first. Do not register material into
   `loopx-meta` just because the current worker found it.
2. If the material belongs to that project, add or update the project's own
   doc registry topic/source entry first.
3. Register the compact material contract into that same project's
   `.loopx/registry.json` with `register-authority-source`, or import a
   redacted summary of another project's doc registry with
   `import-doc-registry-authority`.
4. Sync only compact counts and redacted hashes into the shared global registry;
   raw paths, document ids, private URLs, comments, and source bodies stay in
   the project-local/private authority surface.
5. Refresh status or state so future review packets, read-only maps, and
   heartbeat workers can find the new authority without relying on chat memory.
   Memory extensions may duplicate the reminder, but only after the
   project-local authority registration is complete or a concrete blocker was
   recorded.

Use `import-doc-registry-authority` when a goal needs another project's
DOC_REGISTRY-style map as context. Use `register-authority-source` when the
agent found one material source that should be added to the current project's
authority map. In both cases, the current project remains the owner of its own
doc registry and conflict rules.

## Executor Skill Contract

Project executors should treat doc-registry registration as a skill-triggered
workflow, not as a meta-project side effect. The doc-registry skill trigger is
any task that introduces a durable authority source or research material that
future agents may need to route work, validate decisions, or resolve conflicts.
Register that material in the target project's own doc registry before relying
on chat memory. A user's "remember this design doc" request inside a connected
project is a doc-registry trigger even when it does not mention LoopX.

The minimal executor sequence is:

1. Resolve the target `goal_id` and project registry from LoopX state.
2. Classify the material as owned by the current project, another project, or
   out of scope.
3. For current-project material, update the project-local doc registry first,
   then run `register-authority-source` with a redacted source contract.
4. For another project's registry, run `import-doc-registry-authority` only to
   import compact counts, topic keys, and hashed references.
5. Run the relevant smoke or status refresh before spending heartbeat quota.

Stop instead of registering when the target project is ambiguous, the material
contains private content that cannot be redacted into metadata, or the next step
would require reading a gated source body. In those cases, write a project-local
todo or blocker that names the missing authority decision.

## Boundaries

- Raw private source references are never stored.
- Metadata fields such as `role`, `freshness`, `owner_status`, `gate_status`,
  `revision`, and `conflict_rule` must be public-safe summaries.
- Use `--dry-run` before writing.
- Use `--no-global-sync` when the source registry should remain local-only until
  an operator reviews the compact projection.
- Do not read or summarize the source body as part of registration. This command
  records the source contract; later project-specific work decides whether a
  source can be read.

## Importing A Doc Registry

`loopx import-doc-registry-authority` imports the authority contract from
a DOC_REGISTRY-style YAML file without copying the raw document body or the raw
registry path into the stored payload. It reads only:

- `default_entry_docs`;
- `topic_authority`;
- `status_definitions`;
- `version` and `updated_at`.

The raw `DOC_REGISTRY.yaml` path is hashed as `source_ref_sha256`. The local
registry receives a `doc_registry_authority_import_v0` material entry with
`default_entry_count`, `topic_authority_count`, `status_definition_count`, and
small samples for local operator orientation. Shared global sync keeps the usual
compact authority/material counts.

```bash
loopx import-doc-registry-authority \
  --goal-id example-goal \
  --source-id external-doc-registry \
  --doc-registry-path ../external-project/docs/meta/DOC_REGISTRY.yaml \
  --role external_doc_authority \
  --freshness current \
  --boundary private_redacted \
  --topic external_doc_registry \
  --import-topic-prefix external_ \
  --max-imported-topics 50 \
  --dry-run
```

Use `--topic` for a small hand-picked local topic key, and
`--import-topic-prefix` only when the importing goal should route a bounded set
of external registry topics through its own authority map.
