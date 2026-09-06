import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStore, AuthorityStoreReceiptResult } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {normalizeRegisteredTodoAgents, normalizeTodoAgent} from "./todo_agents.ts";
import {
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_ITEM_SCHEMA,
  canonicalTodoDomainRecord,
} from "./coordination_state_contract.ts";
import {
  indexCoordinationProjection,
  prepareCoordinationProjectionCommit,
  validateCoordinationTodoReadModel,
} from "./coordination_projection.ts";

export const COORDINATION_TODO_CREATE_RESULT_SCHEMA =
  "loopx_coordination_todo_create_result_v0";
export const COORDINATION_TODO_CREATE_RECEIPT_SCHEMA =
  "loopx_coordination_todo_create_receipt_v0";

export interface CoordinationTodoCreateInput {
  readonly goal_id: string;
  readonly todo: JsonObject;
  readonly actor_agent_id: string | null;
  readonly registered_agents: readonly string[];
  readonly operation_id: string;
  readonly dry_run: boolean;
  readonly now: Date;
}

export type CoordinationTodoCreateResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_CREATE_RESULT_SCHEMA;
};

function failure(code: string, reason: string, detail: JsonObject = {}): CoordinationTodoCreateResult {
  return {
    ...detail,
    schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA,
    status: "failed",
    reason_code: code,
    reason,
  };
}

function replayCreate(
  receipt: AuthorityStoreReceiptResult,
  input: CoordinationTodoCreateInput,
  requestSha: string,
  status: "replayed" | "applied" | "recovered",
): CoordinationTodoCreateResult | null {
  if (receipt.status === "missing") return null;
  if (receipt.status !== "found") {
    return {schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA, ...receipt};
  }
  const original = receipt.receipts[0];
  if (receipt.receipts.length !== 1 ||
      original?.schema_version !== COORDINATION_TODO_CREATE_RECEIPT_SCHEMA ||
      original.operation_id !== input.operation_id || original.goal_id !== input.goal_id ||
      original.request_sha256 !== requestSha || original.todo_id !== input.todo.todo_id) {
    return failure(
      "coordination_operation_identity_mismatch",
      "operation id already names a different Todo create request",
    );
  }
  return {
    schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA,
    status,
    changed: status !== "replayed",
    todo_id: original.todo_id,
    todo: original.todo,
    provider_revision: receipt.provider_revision,
    cursor: receipt.cursor,
    original_receipt: original,
    projection_delivery: "pending",
    projection_source: "committed_authority_journal",
  };
}

function normalizeCreateInput(rawInput: CoordinationTodoCreateInput): CoordinationTodoCreateInput {
  const todo = canonicalTodoDomainRecord(rawInput.todo, "Todo create record");
  const input = {
    ...rawInput,
    goal_id: requireAuthorityStoreId(rawInput.goal_id, "goal id"),
    operation_id: requireAuthorityStoreId(rawInput.operation_id, "operation id"),
    todo,
    actor_agent_id: rawInput.actor_agent_id === null
      ? null : normalizeTodoAgent(rawInput.actor_agent_id, "actor_agent_id"),
    registered_agents: normalizeRegisteredTodoAgents(rawInput.registered_agents),
  };
  if (typeof input.dry_run !== "boolean") {
    throw new AuthorityStoreProtocolError("dry_run must be a boolean");
  }
  if (!(input.now instanceof Date) || Number.isNaN(input.now.valueOf())) {
    throw new AuthorityStoreProtocolError("now must be a valid Date");
  }
  if (todo.status === "done" || todo.archive_state !== "active") {
    throw new AuthorityStoreProtocolError(
      "Todo create requires an active record that is not already done",
    );
  }
  if (todo.claimed_by !== undefined) {
    const owner = normalizeTodoAgent(todo.claimed_by, "todo.claimed_by");
    if (!input.registered_agents.includes(owner)) {
      throw new AuthorityStoreProtocolError("Todo claim owner is not registered");
    }
    if (input.actor_agent_id !== null && input.actor_agent_id !== owner) {
      throw new AuthorityStoreProtocolError("claimed Todo create requires actor to match owner");
    }
  }
  if (input.actor_agent_id !== null && !input.registered_agents.includes(input.actor_agent_id)) {
    throw new AuthorityStoreProtocolError("actor_agent_id is not registered for this goal");
  }
  return input;
}

function semanticDuplicateResult(
  todo: JsonObject,
  duplicate: JsonObject,
  providerRevision: unknown,
  cursor: unknown,
): CoordinationTodoCreateResult {
  const ignored = new Set(["schema_version", "todo_id", "created_by", "last_actor_agent_id", "updated_at"]);
  const mismatch = Object.entries(todo).find(([field, value]) =>
    !ignored.has(field) && canonicalAuthoritySha256(value) !== canonicalAuthoritySha256(duplicate[field])
  );
  if (mismatch !== undefined) {
    return failure(
      "todo_semantic_duplicate_conflict",
      `an active Todo with the same role/text has different ${mismatch[0]}; use Todo update`,
      {todo_id: duplicate.todo_id},
    );
  }
  return {
    schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA,
    status: "no_change",
    changed: false,
    todo_id: duplicate.todo_id,
    todo: duplicate,
    provider_revision: providerRevision,
    cursor,
  };
}

function createCandidate(
  input: CoordinationTodoCreateInput,
  readModelSchema: unknown,
): JsonObject {
  const domainCreated = canonicalTodoDomainRecord({
    ...input.todo,
    schema_version: TODO_DOMAIN_ITEM_SCHEMA,
    created_by: input.actor_agent_id,
    last_actor_agent_id: input.actor_agent_id,
    updated_at: input.now.toISOString().replace(/\.\d{3}Z$/u, "Z"),
  }, "created Todo");
  if (readModelSchema === TODO_DOMAIN_READ_RECORD_SCHEMA) return domainCreated;
  return {
    ...domainCreated,
    schema_version: TODO_ITEM_SCHEMA,
    source_section: domainCreated.role === "agent" ? "Agent Todo" : "User Todo",
  };
}

async function commitCreate(
  store: AuthorityStore,
  input: CoordinationTodoCreateInput,
  requestSha: string,
  head: Extract<Awaited<ReturnType<AuthorityStore["loadAuthority"]>>, {status: "loaded"}>,
  created: JsonObject,
  todoId: string,
): Promise<CoordinationTodoCreateResult> {
  const commit = prepareCoordinationProjectionCommit({
    goal_id: input.goal_id,
    operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision,
    projection: head.head,
    mutations: [{kind: "todo_upsert", todo: created}],
  });
  commit.receipts = [{
    schema_version: COORDINATION_TODO_CREATE_RECEIPT_SCHEMA,
    operation_id: input.operation_id,
    goal_id: input.goal_id,
    request_sha256: requestSha,
    todo_id: todoId,
    todo: created,
  }];
  const committed = await store.commitAuthority(commit);
  const readback = replayCreate(
    await store.readReceipt(input.operation_id), input, requestSha,
    committed.status === "applied" ? "applied" : "recovered",
  );
  if (readback !== null) return readback;
  return committed.status === "applied"
    ? failure("coordination_commit_readback_mismatch", "applied create lacks its durable receipt")
    : {schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA, ...committed, changed: false};
}

/** Create one canonical work item through the provider transaction and outbox. */
export async function executeCoordinationTodoCreate(
  store: AuthorityStore,
  rawInput: CoordinationTodoCreateInput,
): Promise<CoordinationTodoCreateResult> {
  let input: CoordinationTodoCreateInput;
  try {
    input = normalizeCreateInput(rawInput);
  } catch (error) {
    return failure(
      "invalid_coordination_todo_create",
      error instanceof Error ? error.message : "invalid Todo create",
    );
  }

  const requestSha = canonicalAuthoritySha256({
    goal_id: input.goal_id,
    todo: input.todo,
    actor_agent_id: input.actor_agent_id,
    dry_run: input.dry_run,
  });
  const existing = replayCreate(
    await store.readReceipt(input.operation_id), input, requestSha, "replayed",
  );
  if (existing !== null) return existing;

  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA, ...head};
  }
  let projection: ReturnType<typeof indexCoordinationProjection>;
  try {
    projection = indexCoordinationProjection(head.head, input.goal_id);
    validateCoordinationTodoReadModel(head.head, input.goal_id);
  } catch (error) {
    return failure(
      "invalid_coordination_projection",
      error instanceof Error ? error.message : "invalid coordination projection",
    );
  }
  const todoId = requireAuthorityStoreId(input.todo.todo_id, "todo id");
  const duplicate = [...projection.todos.values()].find((todo) =>
    todo.role === input.todo.role && todo.archive_state === "active" &&
    todo.status !== "done" && todo.status !== "deferred" && todo.text === input.todo.text
  );
  if (duplicate !== undefined) {
    return semanticDuplicateResult(input.todo, duplicate, head.provider_revision, head.cursor);
  }
  if (projection.todos.has(todoId)) {
    return failure("todo_already_exists", "Todo id already exists in canonical authority", {todo_id: todoId});
  }
  const readModel = canonicalAuthorityObject(head.head.todo_read_model, "Todo read model");
  const created = createCandidate(input, readModel.schema_version);
  if (input.dry_run) {
    return {
      schema_version: COORDINATION_TODO_CREATE_RESULT_SCHEMA,
      status: "planned",
      changed: true,
      dry_run: true,
      todo_id: todoId,
      todo: created,
      provider_revision: head.provider_revision,
      cursor: head.cursor,
    };
  }
  return commitCreate(store, input, requestSha, head, created, todoId);
}
