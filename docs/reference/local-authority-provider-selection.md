# Local authority provider selection

LoopX now has one typed local-provider boundary for every provider-first
coordination command. When a goal has no selector, the boundary resolves the
`file` profile (`source_authority=file_v0`). This makes File/SQLite provider
semantics the default local contract without silently promoting an existing
Markdown goal or changing its writer fence.

## Selection contract

`openLocalAuthorityStoreHandle(runtime_root, goal_id)` resolves a handle with:

| Field | Meaning |
| --- | --- |
| `store` | The provider-neutral `AuthorityStore` implementation |
| `provider` | `file`, `sqlite`, or `postgresql` |
| `sourceAuthority` | The provider evidence label (`*_v0`) |

An absent selector is the explicit default File profile. A SQLite selector uses
the existing `loopx_local_authority_provider_v0` marker and its database
incarnation. A PostgreSQL selector uses the same marker schema plus a
`tenant_id` and `postgresql:<32 lowercase hex>` store identity.

The PostgreSQL marker contains no URL, credential, or database client. Opening
it requires a service-owned `openPostgresqlStore` factory. The factory receives
only the validated public binding facts and must return a PostgreSQL-labelled
`AuthorityStore` whose identity matches the selector. This is the runtime seam
for the medium-term switchable PostgreSQL profile; it does not ship an
authenticated service or grant an Agent database access.

## Failure and compatibility rules

- A selected provider never falls back to File when its selector, database,
  factory, identity, or metadata is unavailable.
- `source_authority` identifies the selected provider even when opening it
  fails; unresolved or malformed selection reports `null`.
- `decision_read_from_provider` is false for selection/open failures, and
  `legacy_fallback_used` remains false.
- The legacy `openLocalAuthorityStore` function still returns only the store,
  so existing callers remain source-compatible. Runtime entrypoints use one
  shared opening seam and no longer duplicate provider construction.
- Provider identity is observability metadata. It does not decide Todo
  eligibility, claims, leases, receipts, or promotion.

The default profile is a routing decision, not a migration. Existing Markdown
state, writer fences, qualification gates, and explicit File/SQLite promotion
holds remain unchanged. SQLite stays an opt-in qualified candidate until the
shared-authority RFC's D2 evidence and owner approval are complete. PostgreSQL
remains an independent service-provider qualification path.

## Validation

The provider selection matrix is exercised with the production-scale synthetic
coordination fixture. Tests cover the default File handle, SQLite persistence,
selected-provider failure without fallback, PostgreSQL factory identity
fencing, and the factory's rejection of a different provider. File, SQLite,
and PostgreSQL continue to share the provider-neutral transaction conformance
contract; PostgreSQL's real-server qualification remains a separate gate.
