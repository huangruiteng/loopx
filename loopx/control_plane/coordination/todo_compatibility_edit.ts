import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStore } from "./authority_store.ts";
import { canonicalAuthorityBytes, canonicalAuthorityObject, canonicalAuthoritySha256, requireAuthorityStoreId } from "./authority_store_codec.ts";
import { prepareCoordinationProjectionCommit, indexCoordinationProjection, validateCoordinationTodoReadModel } from "./coordination_projection.ts";
import { projectionDelivery } from "../todos/projection_delivery.ts";

export const TODO_COMPATIBILITY_EDIT_SCHEMA = "loopx_todo_compatibility_edit_request_v0";
export const TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA = "loopx_todo_compatibility_edit_result_v0";

/**
 * A compatibility editor proposes only text/note changes against an exact
 * provider revision. It cannot submit a snapshot, change ownership/lifecycle,
 * clear unrepresented fields, or make Markdown the commit authority.
 *
 * This trusted embedded entrypoint does not grant remote service authority.
 * Conflict requires rereading and rerunning the editor, never snapshot rebasing.
 */
export async function editCoordinationTodo(
  store: AuthorityStore,
  value: unknown,
): Promise<JsonObject> {
  const failure = (reason_code: string, reason: string): JsonObject => ({
    schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA,
    status: "failed", changed: false, reason_code, reason,
  });
  try {
    const input = canonicalAuthorityObject(value, "Todo compatibility edit");
    if (input.schema_version !== TODO_COMPATIBILITY_EDIT_SCHEMA) {
      throw new Error("Todo compatibility edit schema mismatch");
    }
    const allowed = new Set(["schema_version", "goal_id", "todo_id", "operation_id",
      "expected_provider_revision", "actor_agent_id", "registered_agents", "patch", "dry_run", "observed_at"]);
    if (Object.keys(input).some((key) => !allowed.has(key))) {
      throw new Error("Todo compatibility edit contains unsupported fields");
    }
    const goalId = requireAuthorityStoreId(input.goal_id, "goal id");
    const todoId = requireAuthorityStoreId(input.todo_id, "todo id");
    const operationId = requireAuthorityStoreId(input.operation_id, "operation id");
    const revision = requireAuthorityStoreId(input.expected_provider_revision, "expected provider revision");
    const actor = requireAuthorityStoreId(input.actor_agent_id, "actor agent id");
    if (typeof input.observed_at !== "string" ||
        !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/u.test(input.observed_at) ||
        Number.isNaN(Date.parse(input.observed_at))) {
      throw new Error("observed_at must be an ISO timestamp");
    }
    const updatedAt = new Date(input.observed_at).toISOString();
    if (!Array.isArray(input.registered_agents) ||
        input.registered_agents.some((agent) => typeof agent !== "string") ||
        new Set(input.registered_agents).size !== input.registered_agents.length) {
      throw new Error("registered_agents must be a unique string array");
    }
    if (typeof input.dry_run !== "boolean") throw new Error("dry_run must be a boolean");
    const patch = canonicalAuthorityObject(input.patch, "compatibility patch");
    if (Object.keys(patch).length === 0 || Object.entries(patch).some(([key, item]) =>
      !["text", "note"].includes(key) || typeof item !== "string" || !item.trim()
    )) {
      throw new Error("compatibility patch accepts only non-empty text and note strings");
    }
    const requestSha = canonicalAuthoritySha256({
      goal_id: goalId, todo_id: todoId, actor_agent_id: actor,
      expected_provider_revision: revision, patch,
    });
    const readReceipt = async (status: string): Promise<JsonObject | null> => {
      const receipt = await store.readReceipt(operationId);
      if (receipt.status === "missing") return null;
      if (receipt.status !== "found") return {schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA, ...receipt, changed: false};
      const original = receipt.receipts[0];
      if (receipt.receipts.length !== 1 ||
          original?.schema_version !== "loopx_todo_compatibility_edit_receipt_v0" ||
          original.operation_id !== operationId || original.request_sha256 !== requestSha ||
          typeof original.changed !== "boolean") {
        return failure("coordination_operation_identity_mismatch", "operation id names a different compatibility edit");
      }
      return {
        schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA,
        status: status === "applied" && !original.changed ? "no_change" : status,
        changed: status !== "replayed" && original.changed,
        provider_revision: receipt.provider_revision, cursor: receipt.cursor,
        projection_delivery: projectionDelivery(original.changed),
        projection_source: "committed_authority_journal",
      };
    };
    // Preview evaluates current eligibility and never consumes/replays identity.
    if (!input.dry_run) {
      const replay = await readReceipt("replayed");
      if (replay !== null) return replay;
    }
    if (!input.registered_agents.includes(actor)) {
      return failure("actor_not_registered", "compatibility edit requires a registered actor");
    }
    const head = await store.loadAuthority();
    if (head.status !== "loaded") return {schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA, ...head, changed: false};
    validateCoordinationTodoReadModel(head.head, goalId);
    const index = indexCoordinationProjection(head.head, goalId);
    if (head.provider_revision !== revision) return {
      schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA,
      status: "conflict", changed: false, conflict_kind: "provider_revision_mismatch",
      current_provider_revision: head.provider_revision, current_cursor: head.cursor,
    };
    const todo = index.todos.get(todoId);
    if (todo === undefined) return failure("todo_not_found", "canonical Todo is missing");
    if (todo.role !== "agent" || todo.status !== "open" || todo.archive_state !== "active") {
      return failure("unsupported_compatibility_edit_target", "compatibility editing requires an active open agent Todo");
    }
    if (todo.claimed_by !== actor ||
        (Array.isArray(todo.excluded_agents) && todo.excluded_agents.includes(actor)) ||
        (typeof todo.removed_continuation_policy === "string" && todo.removed_continuation_policy)) {
      return failure("compatibility_edit_owner_mismatch", "compatibility editing requires the current non-excluded claim owner");
    }
    // Lease-bearing edits need a separate execution-instance proof; do not
    // infer that proof merely from actor identity or bypass the existing fence.
    if (![undefined, "legacy", "soft_claim"].includes(head.head.handoff_mode as string | undefined) || index.leases.has(todoId)) {
      return failure("compatibility_edit_lease_unsupported", "lease-bearing compatibility edits are not yet supported");
    }
    const next = {...todo, ...patch};
    const changed = !canonicalAuthorityBytes(next).equals(canonicalAuthorityBytes(todo));
    if (input.dry_run) return {
      schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA, status: changed ? "planned" : "no_change",
      changed, provider_revision: revision, cursor: head.cursor,
    };
    if (changed) next.updated_at = updatedAt;
    const commit = changed ? prepareCoordinationProjectionCommit({
      goal_id: goalId, operation_id: operationId,
      expected_provider_revision: revision,
      projection: head.head,
      mutations: [{kind: "todo_upsert", todo: next}],
    }) : {operation_id: operationId, expected_provider_revision: revision,
      next_projection: head.head, events: [], receipts: []};
    commit.receipts = [{schema_version: "loopx_todo_compatibility_edit_receipt_v0",
      operation_id: operationId, request_sha256: requestSha, changed}];
    const result = await store.commitAuthority(commit);
    const readback = await readReceipt(result.status === "applied" ? "applied" : "recovered");
    if (readback !== null) return readback;
    if (result.status === "applied") return failure("compatibility_commit_readback_mismatch", "applied edit lacks its durable receipt");
    return {
      schema_version: TODO_COMPATIBILITY_EDIT_RESULT_SCHEMA, ...result,
      changed: false,
    };
  } catch (error) {
    return failure("invalid_todo_compatibility_edit", error instanceof Error ? error.message : "invalid compatibility edit");
  }
}
