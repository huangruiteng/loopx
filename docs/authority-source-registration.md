# Authority Source Registration

`goal-harness register-authority-source` records one local authority or material
source for a goal without storing the raw source reference. It is meant for
internal docs, private repositories, owner-review packets, and validation
snapshots where the project agent needs a public-safe projection, not the raw
link.

The command writes the selected source registry, usually the ignored
`.goal-harness/registry.json`, and may sync a compact projection into the shared
global registry. Public repository files should keep examples and contracts
only.

## Minimal Command

```bash
goal-harness register-authority-source \
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
