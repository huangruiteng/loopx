import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStoreCommit, AuthorityStoreCommittedTransaction } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  canonicalAuthorityObjectList,
  hasExactAuthorityKeys,
  isAuthorityJsonObject,
  requireAuthorityStoreId,
  parseAuthorityCursor,
  canonicalAuthorityBytes,
} from "./authority_store_codec.ts";

/** Shared wire decoder used by every authority provider. */
export function decodeAuthorityTransaction(value: unknown): AuthorityStoreCommittedTransaction {
  if (!isAuthorityJsonObject(value) || !hasExactAuthorityKeys(value, [
    "cursor", "provider_revision", "operation_id", "events", "projection", "receipts",
  ])) throw new AuthorityStoreProtocolError("committed transaction is invalid");
  const cursor = requireAuthorityStoreId(value.cursor, "transaction cursor");
  parseAuthorityCursor(cursor);
  return {
    cursor,
    provider_revision: requireAuthorityStoreId(value.provider_revision, "transaction provider revision"),
    operation_id: requireAuthorityStoreId(value.operation_id, "operation id"),
    events: canonicalAuthorityObjectList(value.events, "transaction events"),
    projection: canonicalAuthorityObject(value.projection, "transaction projection"),
    receipts: canonicalAuthorityObjectList(value.receipts, "transaction receipts"),
  };
}

export function transactionForRevision(value: AuthorityStoreCommittedTransaction): JsonObject {
  return {
    cursor: value.cursor,
    operation_id: value.operation_id,
    events: value.events,
    projection: value.projection,
    receipts: value.receipts,
  };
}

/** File and NoKV retain the whole journal in one envelope. Their wire headers,
 * physical CAS, and revision algorithms remain provider-owned. */
export interface RetainedAuthorityJournal {
  provider_revision: string;
  cursor: string;
  head: JsonObject;
  committed: AuthorityStoreCommittedTransaction[];
}

type RevisionInput = ReturnType<typeof transactionForRevision>;
export type JournalRevision = (previous: string | null, transaction: RevisionInput) => string;

export function decodeRetainedAuthorityJournal(value: JsonObject, label: string,
  revisionFor: JournalRevision): RetainedAuthorityJournal {
  const revision = requireAuthorityStoreId(value.provider_revision, "provider revision");
  const cursor = requireAuthorityStoreId(value.cursor, "provider cursor");
  const head = canonicalAuthorityObject(value.head, `${label} head`);
  if (!Array.isArray(value.committed)) {
    throw new AuthorityStoreProtocolError(`${label} history is invalid`);
  }
  const committed = value.committed.map(decodeAuthorityTransaction);
  if (committed.length === 0 || parseAuthorityCursor(cursor) !== BigInt(committed.length)) {
    throw new AuthorityStoreProtocolError(`${label} lineage is invalid`);
  }
  let previous: string | null = null;
  const operations = new Set<string>();
  for (const [index, entry] of committed.entries()) {
    if (parseAuthorityCursor(entry.cursor) !== BigInt(index + 1)) {
      throw new AuthorityStoreProtocolError(`${label} cursor lineage is invalid`);
    }
    if (operations.has(entry.operation_id)) {
      throw new AuthorityStoreProtocolError(`${label} operation identity is duplicated`);
    }
    operations.add(entry.operation_id);
    if (entry.provider_revision !== revisionFor(previous, transactionForRevision(entry))) {
      throw new AuthorityStoreProtocolError(`${label} revision lineage is invalid`);
    }
    previous = entry.provider_revision;
  }
  const last = committed.at(-1)!;
  if (last.cursor !== cursor || last.provider_revision !== revision ||
      !canonicalAuthorityBytes(last.projection).equals(canonicalAuthorityBytes(head))) {
    throw new AuthorityStoreProtocolError(`${label} head lineage is invalid`);
  }
  return {provider_revision: revision, cursor, head, committed};
}

/** Build only after the provider checked revision and operation uniqueness in
 * its write boundary. This function neither grants admission nor persists. */
export function appendRetainedAuthorityJournal(current: RetainedAuthorityJournal | null,
  commit: AuthorityStoreCommit, revisionFor: JournalRevision): RetainedAuthorityJournal {
  const cursor = (parseAuthorityCursor(current?.cursor ?? null) + 1n).toString();
  const base = {cursor, operation_id: commit.operation_id, events: commit.events,
    projection: commit.next_projection, receipts: commit.receipts};
  const revision = revisionFor(current?.provider_revision ?? null, base);
  return {provider_revision: revision, cursor, head: commit.next_projection,
    committed: [...(current?.committed ?? []), {...base, provider_revision: revision}]};
}
