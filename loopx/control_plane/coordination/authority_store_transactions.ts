import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStoreCommittedTransaction } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  canonicalAuthorityObjectList,
  hasExactAuthorityKeys,
  isAuthorityJsonObject,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";

/** Shared wire decoder used by every authority provider. */
export function decodeAuthorityTransaction(value: unknown): AuthorityStoreCommittedTransaction {
  if (!isAuthorityJsonObject(value) || !hasExactAuthorityKeys(value, [
    "cursor", "provider_revision", "operation_id", "events", "projection", "receipts",
  ])) throw new AuthorityStoreProtocolError("committed transaction is invalid");
  return {
    cursor: requireAuthorityStoreId(value.cursor, "transaction cursor"),
    provider_revision: requireAuthorityStoreId(value.provider_revision, "transaction provider revision"),
    operation_id: requireAuthorityStoreId(value.operation_id, "operation id"),
    events: canonicalAuthorityObjectList(value.events, "transaction events"),
    projection: canonicalAuthorityObject(value.projection, "transaction projection"),
    receipts: canonicalAuthorityObjectList(value.receipts, "transaction receipts"),
  };
}

export function cloneAuthorityTransaction(value: AuthorityStoreCommittedTransaction): AuthorityStoreCommittedTransaction {
  return structuredClone(value);
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
