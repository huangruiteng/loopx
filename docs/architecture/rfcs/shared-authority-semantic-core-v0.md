# RFC: Shared Authority Semantic Core v0

- Status: Proposed
- Scope: the TypeScript control-plane migration and shared-authority provider RFCs
- Date: 2026-09-12

## Summary

The two current RFCs establish a provider-neutral authority contract, but provider
adapters still contain repeated wire decoding and transaction-shaping rules. This
RFC makes the semantic core executable: one strict transaction codec is shared by
file and NoKV today and is the required seam for SQLite and PostgreSQL adapters.
Providers retain storage-specific revision and failure behavior; they no longer
own copies of the canonical transaction shape.

## Semantic changes

1. A committed transaction has one canonical decoder with exact keys and strict
   JSON object/list validation. Unknown keys, malformed lists, and non-string
   identity fields fail closed identically across providers.
2. Revision input is derived from one shared `transactionForRevision` projection,
   preventing a provider from accidentally including its own storage metadata in
   the logical transaction payload. Provider-specific envelopes remain in the
   provider revision hash.
3. Cloning is explicit at the shared boundary, so scan/read callers cannot mutate
   provider-owned history through an adapter-specific copy convention.
4. The refactor is behavior preserving for valid records and intentionally tightens
   malformed-record parity. No claim, lease, archive, or promotion authority is
   granted by the codec.

## Delivery plan

Stage A extracts the shared TypeScript module and adds a complex fixture covering
valid native records, legacy-compatible records, reordered keys, unknown keys,
malformed receipts, and revision projection. Stage B migrates SQLite and PostgreSQL
call sites and removes their local shape helpers. Stage C qualifies the complete
provider matrix and the ten-day local persistence target from the shared-authority
RFC.

## Validation and real state

The focused TypeScript suite and full control-plane suite must pass. A read-only
`loopx --format json status --goal-id loopx-meta` run is required before delivery;
its warnings are evidence about the live goal and are not rewritten by this RFC.

## Duplication removed

Before this stage, `file_authority_store.ts` and `nokv_authority_store.ts` each
implemented the same exact-key check, identity validation, event/projection/receipt
canonicalization, transaction clone, and revision-input projection. The copies
were vulnerable to drift: one provider could accept a payload the other rejected.
The new module owns those shared semantics; only storage envelope decoding and
provider-specific revision salts remain local.
