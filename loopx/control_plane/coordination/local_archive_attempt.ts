import { readFile } from "node:fs/promises";
import { join } from "node:path";

import type { JsonObject } from "../effect_program.ts";
import { durableWriteJson } from "../effect_runtime_io.ts";
import type { AuthorityStore } from "./authority_store.ts";
import {
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  hasExactAuthorityKeys,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import { shadowManagementDirectory } from "./shadow_management.ts";
import {
  COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
  COORDINATION_TODO_ARCHIVE_RECEIPT_SCHEMA,
  executeCoordinationTodoArchiveCompleted,
  type CoordinationTodoArchiveInput,
} from "./todo_terminal_lifecycle.ts";

const ATTEMPT_SCHEMA = "loopx_local_todo_archive_attempt_v0";
export const LOCAL_TODO_ARCHIVE_ACK_RESULT_SCHEMA =
  "loopx_local_coordination_todo_archive_ack_result_v0";

type Role = CoordinationTodoArchiveInput["role"];
interface ArchiveAttempt {
  operation_id: string;
  expected_provider_revision: string | null;
  max_active_done: number;
  store_identity: string;
}

function attemptPath(root: string, goalId: string, role: Role): string {
  return join(shadowManagementDirectory(root, goalId), `archive-${role}.json`);
}

async function readAttempt(root: string, goalId: string, role: Role): Promise<ArchiveAttempt | null> {
  let value: unknown;
  try {
    value = JSON.parse(await readFile(attemptPath(root, goalId, role), "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  const slot = canonicalAuthorityObject(value, "archive attempt slot");
  if (!hasExactAuthorityKeys(slot, ["schema_version", "goal_id", "role", "attempt"]) ||
      slot.schema_version !== ATTEMPT_SCHEMA || slot.goal_id !== goalId || slot.role !== role) {
    throw new Error("archive attempt slot identity mismatch");
  }
  if (slot.attempt === null) return null;
  const attempt = canonicalAuthorityObject(slot.attempt, "archive attempt");
  if (!hasExactAuthorityKeys(attempt, ["operation_id", "expected_provider_revision",
    "max_active_done", "store_identity"]) ||
      !Number.isSafeInteger(attempt.max_active_done) || Number(attempt.max_active_done) < 0) {
    throw new Error("invalid archive attempt");
  }
  return {
    operation_id: requireAuthorityStoreId(attempt.operation_id, "archive operation id"),
    expected_provider_revision: attempt.expected_provider_revision === null ? null :
      requireAuthorityStoreId(attempt.expected_provider_revision, "archive expected provider revision"),
    max_active_done: Number(attempt.max_active_done),
    store_identity: requireAuthorityStoreId(attempt.store_identity, "archive store identity"),
  };
}

async function writeAttempt(
  root: string, goalId: string, role: Role, attempt: ArchiveAttempt | null,
): Promise<void> {
  // A durable null tombstone avoids a delete/parent-fsync recovery window.
  // There are at most two bounded slots per goal, regardless of history size.
  await durableWriteJson(attemptPath(root, goalId, role), {
    schema_version: ATTEMPT_SCHEMA, goal_id: goalId, role,
    attempt: attempt === null ? null : {...attempt},
  });
}

/** Caller holds the goal's shadow-maintenance mutex throughout this operation. */
export async function executeLocalArchiveAttempt(
  store: AuthorityStore, root: string, input: CoordinationTodoArchiveInput,
): Promise<JsonObject> {
  if (input.dry_run) return executeCoordinationTodoArchiveCompleted(store, input);
  let attempt = await readAttempt(root, input.goal_id, input.role);
  if (attempt === null) {
    // A retained v0 receipt may predate observed-head binding. Preserve the
    // actual caller fields; adding today's revision would change its identity.
    const receipt = await store.readReceipt(input.operation_id);
    if (receipt.status === "missing") {
      const head = await store.loadAuthority();
      if (head.status !== "loaded") return {
        schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...head, changed: false,
      };
    } else if (receipt.status !== "found") return {
      schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...receipt, changed: false,
    };
  }
  const identity = await store.storeIdentity();
  if (identity.status !== "available") return {
    schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...identity, changed: false,
  };
  if (attempt !== null && attempt.store_identity !== identity.store_identity) {
    throw new Error("archive attempt belongs to a different authority store");
  }
  if (attempt !== null && attempt.max_active_done !== input.max_active_done) return {
    schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
    status: "conflict", changed: false, conflict_kind: "archive_attempt_pending",
    operation_id: attempt.operation_id,
    reason: "complete the pending archive projection before changing the retention limit",
  };
  if (attempt === null) {
    attempt = {
      operation_id: input.operation_id,
      expected_provider_revision: input.expected_provider_revision ?? null,
      max_active_done: input.max_active_done, store_identity: identity.store_identity,
    };
    // Persist correlation before the provider can commit. The provider alone
    // owns selection, request identity, CAS, and historical result receipts.
    await writeAttempt(root, input.goal_id, input.role, attempt);
  }
  const result = await executeCoordinationTodoArchiveCompleted(store, {
    ...input, operation_id: attempt.operation_id,
    expected_provider_revision: attempt.expected_provider_revision ?? undefined,
  });
  const identityRejected = result.status === "failed" &&
    result.reason_code === "coordination_operation_identity_mismatch";
  const beforeCommitRejected = result.status === "conflict" || (
    result.status === "failed" && ["invalid_coordination_todo_archive",
      "invalid_coordination_projection"].includes(String(result.reason_code))
  );
  if (result.status === "no_change" || identityRejected || (beforeCommitRejected &&
      (await store.readReceipt(attempt.operation_id)).status === "missing")) {
    // No committed mutation exists to project. In particular, retain the
    // established zero-revision-change semantics of no-change archive calls.
    await writeAttempt(root, input.goal_id, input.role, null);
  }
  return {...result, operation_id: attempt.operation_id};
}

/** A successful projection acknowledges exactly one attempt, never a newer one. */
export async function acknowledgeLocalArchiveAttempt(
  store: AuthorityStore, root: string, goalId: string, role: Role, operationId: string,
): Promise<JsonObject> {
  const result = {schema_version: LOCAL_TODO_ARCHIVE_ACK_RESULT_SCHEMA,
    goal_id: goalId, role, operation_id: operationId};
  const attempt = await readAttempt(root, goalId, role);
  if (attempt === null) return {...result, status: "no_change", changed: false};
  if (attempt.operation_id !== operationId) return {...result, status: "stale", changed: false};
  const identity = await store.storeIdentity();
  if (identity.status !== "available") return {...result, ...identity, changed: false};
  if (attempt.store_identity !== identity.store_identity) {
    throw new Error("archive acknowledgement belongs to a different authority store");
  }
  const receipt = await store.readReceipt(operationId);
  const original = receipt.status === "found" ? receipt.receipts[0] : undefined;
  if (receipt.status !== "found" || receipt.receipts.length !== 1 ||
      original?.schema_version !== COORDINATION_TODO_ARCHIVE_RECEIPT_SCHEMA ||
      original.operation_id !== operationId || original.goal_id !== goalId ||
      original.request_sha256 !== canonicalAuthoritySha256({
        goal_id: goalId, role, max_active_done: attempt.max_active_done,
        dry_run: false,
        ...(attempt.expected_provider_revision === null ? {} : {
          expected_provider_revision: attempt.expected_provider_revision,
        }),
      })) return {
    ...result, status: "failed", changed: false,
    reason_code: "archive_ack_receipt_unavailable",
    reason: "archive projection acknowledgement requires its committed receipt",
  };
  await writeAttempt(root, goalId, role, null);
  return {...result, status: "acknowledged", changed: true};
}
