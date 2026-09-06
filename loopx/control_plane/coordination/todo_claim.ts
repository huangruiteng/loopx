import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStore, AuthorityStoreCommit, AuthorityStoreReceiptResult } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {normalizeRegisteredTodoAgents, normalizeTodoAgent} from "./todo_agents.ts";
import {
  prepareCoordinationProjectionCommit,
  indexCoordinationProjection,
  validateCoordinationTodoReadModel,
  type CoordinationProjectionMutation,
} from "./coordination_projection.ts";
import {
  evaluateTaskLeaseAcquireDecision,
  leaseEpoch,
  leaseInteger,
  leaseIsActive,
  normalizeAgent,
  normalizeIdempotencyKey,
  normalizeTtl,
  normalizeWriteScopes,
  ownerRejection,
  TASK_LEASE_SCHEMA_VERSION,
  utcIsoformat,
  type LeaseRecord,
  type TodoFact,
} from "../work_items/task_lease_acquire.ts";

export const COORDINATION_TODO_CLAIM_RESULT_SCHEMA =
  "loopx_coordination_todo_claim_result_v0";
export const COORDINATION_TODO_CLAIM_RECEIPT_SCHEMA =
  "loopx_coordination_todo_claim_receipt_v0";
export const COORDINATION_TODO_CLAIM_DECISION_SCHEMA =
  "loopx_coordination_todo_claim_decision_v0";

export interface CoordinationTodoClaimInput {
  readonly goal_id: string;
  readonly todo_id: string;
  readonly claimed_by: string;
  readonly actor_agent_id: string | null;
  readonly expected_role: string | null;
  readonly registered_agents: readonly string[];
  readonly operation_id: string;
  readonly lease_request?: CoordinationTodoClaimLeaseRequest | null;
  readonly dry_run: boolean;
  readonly now: Date;
}

export interface CoordinationTodoClaimLeaseRequest {
  readonly idempotency_key: string;
  readonly expected_version: number | null;
  readonly ttl_seconds: number;
}

export type CoordinationTodoClaimResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_CLAIM_RESULT_SCHEMA;
};

export interface CoordinationTodoClaimAcceptedDecision extends JsonObject {
  readonly schema_version: typeof COORDINATION_TODO_CLAIM_DECISION_SCHEMA;
  readonly status: "accepted";
  readonly owner: string;
  readonly actor: string | null;
  readonly mode: "single_agent_compatibility" | "registered_peer_actor";
  readonly mutation_authority: JsonObject;
}

export interface CoordinationTodoClaimRejectedDecision extends JsonObject {
  readonly schema_version: typeof COORDINATION_TODO_CLAIM_DECISION_SCHEMA;
  readonly status: "rejected";
  readonly reason_code: string;
  readonly reason: string;
}

export type CoordinationTodoClaimDecision =
  | CoordinationTodoClaimAcceptedDecision
  | CoordinationTodoClaimRejectedDecision;

type ClaimRejection = CoordinationTodoClaimRejectedDecision | null;

function normalizeExcludedAgents(value: unknown): string[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) {
    throw new AuthorityStoreProtocolError("todo.excluded_agents must be an array");
  }
  const normalized = value.map((agent, index) =>
    normalizeTodoAgent(agent, `todo.excluded_agents[${index}]`)
  );
  if (new Set(normalized).size !== normalized.length) {
    throw new AuthorityStoreProtocolError(
      "todo.excluded_agents must contain unique public-safe agent ids",
    );
  }
  return normalized;
}

function failure(code: string, reason: string, detail: JsonObject = {}): CoordinationTodoClaimResult {
  return {
    ...detail,
    schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
    status: "failed",
    reason_code: code,
    reason,
  };
}

function decisionFailure(
  code: string,
  reason: string,
  detail: JsonObject = {},
): CoordinationTodoClaimRejectedDecision {
  return {
    ...detail,
    schema_version: COORDINATION_TODO_CLAIM_DECISION_SCHEMA,
    status: "rejected",
    reason_code: code,
    reason,
  };
}

function rejectInvalidClaimActor(
  input: CoordinationTodoClaimInput,
): ClaimRejection {
  const { registered_agents: registered, claimed_by: owner, actor_agent_id: actor } = input;
  if (!registered.includes(owner)) {
    return decisionFailure(
      "actor_not_registered",
      "claimed_by is not registered for this goal",
      { claimed_by: owner },
    );
  }
  if (actor !== null && !registered.includes(actor)) {
    return decisionFailure(
      "actor_not_registered",
      "actor_agent_id is not registered for this goal",
      { actor_agent_id: actor },
    );
  }
  if (registered.length > 1 && actor === null) {
    return decisionFailure(
      "actor_required",
      "multi-agent Todo claim requires actor_agent_id",
    );
  }
  return actor !== null && actor !== owner
    ? decisionFailure(
      "claim_actor_mismatch",
      "Todo claim requires claimed_by to match actor_agent_id",
      { actor_agent_id: actor, claimed_by: owner },
    )
    : null;
}

function rejectIneligibleTodo(
  todo: JsonObject,
  input: CoordinationTodoClaimInput,
): ClaimRejection {
  if (todo.role !== "agent") {
    return decisionFailure("todo_not_agent", "claimed_by is only valid for agent Todos");
  }
  if (input.expected_role !== null && input.expected_role !== todo.role) {
    return decisionFailure(
      "todo_role_mismatch",
      "Todo does not have the requested role",
      { requested_role: input.expected_role, todo_role: todo.role },
    );
  }
  if (todo.status !== "open") {
    return decisionFailure(
      "todo_not_open",
      "todo claim requires status=open",
      { todo_status: todo.status },
    );
  }
  if (todo.archive_state !== "active") {
    return decisionFailure("todo_archived", "Todo claim requires an active Todo");
  }
  return typeof todo.removed_continuation_policy === "string" &&
      todo.removed_continuation_policy.length > 0
    ? decisionFailure(
      "removed_continuation_policy",
      "Todo uses a removed continuation policy and must be repaired before claiming",
    )
    : null;
}

export function evaluateCoordinationTodoClaimDecision(
  todo: JsonObject,
  input: CoordinationTodoClaimInput,
): CoordinationTodoClaimDecision {
  const registered = input.registered_agents;
  const owner = input.claimed_by;
  const actor = input.actor_agent_id;
  const rejection = rejectInvalidClaimActor(input) ?? rejectIneligibleTodo(todo, input);
  if (rejection !== null) return rejection;
  const excluded = normalizeExcludedAgents(todo.excluded_agents);
  if (excluded.includes(owner)) {
    return decisionFailure(
      "actor_excluded",
      "claiming agent is excluded from this Todo",
      { actor_agent_id: owner },
    );
  }
  const existing = typeof todo.claimed_by === "string" && todo.claimed_by.length > 0
    ? normalizeTodoAgent(todo.claimed_by, "todo.claimed_by")
    : null;
  if (existing !== null && existing !== owner) {
    return decisionFailure(
      "claim_owner_mismatch",
      "Todo is already claimed by another agent",
      { claim_owner: existing },
    );
  }
  const mode = registered.length <= 1 ? "single_agent_compatibility" : "registered_peer_actor";
  return {
    schema_version: COORDINATION_TODO_CLAIM_DECISION_SCHEMA,
    status: "accepted",
    owner,
    actor,
    mode,
    mutation_authority: {
      schema_version: "todo_mutation_authority_v0",
      command: "claim",
      mode,
      actor_agent_id: actor,
      todo_id: todo.todo_id,
      registered_agent_count: registered.length,
      ...(mode === "registered_peer_actor" ? { claim_owner: existing } : {}),
    },
  };
}

function normalizeLeaseRequest(value: unknown): CoordinationTodoClaimLeaseRequest | null {
  if (value === undefined || value === null) return null;
  const request = canonicalAuthorityObject(value, "lease_request");
  const expectedVersion = request.expected_version;
  if (expectedVersion !== null && expectedVersion !== undefined &&
      (!Number.isSafeInteger(expectedVersion) || Number(expectedVersion) < 0)) {
    throw new AuthorityStoreProtocolError(
      "lease_request.expected_version must be a non-negative safe integer or null",
    );
  }
  return {
    idempotency_key: normalizeIdempotencyKey(request.idempotency_key),
    expected_version: expectedVersion === undefined ? null : expectedVersion as number | null,
    ttl_seconds: normalizeTtl(request.ttl_seconds),
  };
}

function todoLeaseFact(todo: JsonObject): TodoFact {
  const requiredWriteScopes = todo.required_write_scopes ?? [];
  if (!Array.isArray(requiredWriteScopes) ||
      requiredWriteScopes.some((scope) => typeof scope !== "string")) {
    throw new AuthorityStoreProtocolError(
      "todo.required_write_scopes must be an array of strings",
    );
  }
  const writeScopes = normalizeWriteScopes(requiredWriteScopes);
  if (writeScopes.length !== requiredWriteScopes.length) {
    throw new AuthorityStoreProtocolError(
      "todo.required_write_scopes contains an invalid or duplicate scope",
    );
  }
  return {
    todo_id: String(todo.todo_id),
    status: typeof todo.status === "string" ? todo.status : "",
    claimed_by: normalizeAgent(todo.claimed_by),
    excluded_agents: normalizeExcludedAgents(todo.excluded_agents),
    role: typeof todo.role === "string" ? todo.role : undefined,
    task_class: typeof todo.task_class === "string" ? todo.task_class : null,
    bound_agent: normalizeAgent(todo.bound_agent),
    blocks_agent: normalizeAgent(todo.blocks_agent),
  };
}

function leaseDecisionInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new AuthorityStoreProtocolError(`${label} must be a non-negative safe integer`);
  }
  return Number(value);
}

function activeLeaseForOwner(
  lease: JsonObject | undefined,
  owner: string,
  now: Date,
): boolean {
  if (lease === undefined || lease.status !== "active" ||
      typeof lease.owner !== "string" || typeof lease.expires_at !== "string") return false;
  let leaseOwner: string;
  try {
    leaseOwner = normalizeTodoAgent(lease.owner, "lease.owner");
  } catch {
    return false;
  }
  if (leaseOwner !== owner) return false;
  const expiresAt = new Date(lease.expires_at);
  return !Number.isNaN(expiresAt.valueOf()) && expiresAt.valueOf() > now.valueOf();
}

/**
 * Claim one Todo against the canonical provider head.
 *
 * The transaction is store-neutral: file, NoKV, and PostgreSQL adapters share
 * the same semantic decision, complete-record replacement, CAS, and receipt.
 * No caller-supplied projection is accepted.
 */
export async function executeCoordinationTodoClaim(
  store: AuthorityStore,
  rawInput: CoordinationTodoClaimInput,
): Promise<CoordinationTodoClaimResult> {
  let input: CoordinationTodoClaimInput;
  try {
    input = {
      ...rawInput,
      goal_id: requireAuthorityStoreId(rawInput.goal_id, "goal id"),
      todo_id: requireAuthorityStoreId(rawInput.todo_id, "todo id"),
      operation_id: requireAuthorityStoreId(rawInput.operation_id, "operation id"),
      claimed_by: normalizeTodoAgent(rawInput.claimed_by, "claimed_by"),
      actor_agent_id: rawInput.actor_agent_id === null
        ? null : normalizeTodoAgent(rawInput.actor_agent_id, "actor_agent_id"),
      registered_agents: normalizeRegisteredTodoAgents(rawInput.registered_agents),
      lease_request: normalizeLeaseRequest(rawInput.lease_request),
    };
    if (typeof input.dry_run !== "boolean") {
      throw new AuthorityStoreProtocolError("dry_run must be a boolean");
    }
    if (!(input.now instanceof Date) || Number.isNaN(input.now.valueOf())) {
      throw new AuthorityStoreProtocolError("now must be a valid Date");
    }
  } catch (error) {
    return failure(
      "invalid_coordination_todo_claim",
      error instanceof Error ? error.message : "invalid Todo claim",
    );
  }
  const leaseRequest = input.lease_request ?? null;

  // Intent identity excludes observation time and current authorization facts.
  // A receipt proves historical acceptance, never a renewed/current lease.
  const requestSha = canonicalAuthoritySha256({
    goal_id: input.goal_id,
    todo_id: input.todo_id,
    claimed_by: input.claimed_by,
    actor_agent_id: input.actor_agent_id,
    expected_role: input.expected_role,
    dry_run: input.dry_run,
    ...(leaseRequest === null ? {} : {lease_request: leaseRequest}),
  });
  const replay = (
    receipt: AuthorityStoreReceiptResult,
    status: "replayed" | "applied" | "recovered",
  ): CoordinationTodoClaimResult | null => {
    if (receipt.status === "missing") return null;
    if (receipt.status !== "found") {
      return { schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA, ...receipt };
    }
    const original = receipt.receipts[0];
    if (receipt.receipts.length !== 1 ||
        original?.schema_version !== COORDINATION_TODO_CLAIM_RECEIPT_SCHEMA ||
        original.operation_id !== input.operation_id || original.goal_id !== input.goal_id ||
        original.request_sha256 !== requestSha) {
      return failure("coordination_operation_identity_mismatch",
        "operation id already names a different coordination request");
    }
    let result: JsonObject;
    try {
      result = canonicalAuthorityObject(original.result, "original claim result");
      if (result.todo_id !== input.todo_id || result.claimed_by !== input.claimed_by ||
          (result.changed !== undefined && typeof result.changed !== "boolean") ||
          (result.changed !== false && typeof result.updated_at !== "string") ||
          typeof result.handoff_mode !== "string" ||
          result.mutation_authority === null || typeof result.mutation_authority !== "object") {
        throw new AuthorityStoreProtocolError("original claim result is invalid");
      }
      if (leaseRequest !== null) {
        const lease = canonicalAuthorityObject(result.lease, "original claim lease");
        if (lease.todo_id !== input.todo_id || lease.owner !== input.claimed_by ||
            lease.idempotency_key !== leaseRequest.idempotency_key) {
          throw new AuthorityStoreProtocolError("original claim lease identity is invalid");
        }
      }
    } catch (error) {
      return failure("invalid_coordination_todo_claim_receipt",
        error instanceof Error ? error.message : "invalid claim receipt");
    }
    return {
      ...result,
      schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
      status: status === "applied" && result.changed === false ? "no_change" : status,
      changed: status !== "replayed" && result.changed !== false,
      provider_revision: receipt.provider_revision,
      cursor: receipt.cursor,
      original_receipt: original,
      projection_delivery: result.changed === false ? "not_required" : "pending",
      projection_source: "committed_authority_journal",
    };
  };
  const existing = replay(await store.readReceipt(input.operation_id), "replayed");
  if (existing !== null) return existing;

  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {
      schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
      ...head,
    } as CoordinationTodoClaimResult;
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
  const todo = projection.todos.get(input.todo_id);
  if (todo === undefined) {
    return failure("todo_not_found", "Todo is missing from the canonical provider head", {
      todo_id: input.todo_id,
    });
  }

  let authority: ReturnType<typeof evaluateCoordinationTodoClaimDecision>;
  try {
    authority = evaluateCoordinationTodoClaimDecision(todo, input);
  } catch (error) {
    return failure(
      "invalid_coordination_todo_claim",
      error instanceof Error ? error.message : "invalid Todo claim",
    );
  }
  if (authority.status !== "accepted" || typeof authority.owner !== "string") {
    return failure(
      typeof authority.reason_code === "string" ? authority.reason_code : "invalid_coordination_todo_claim",
      typeof authority.reason === "string" ? authority.reason : "Todo claim was rejected",
      authority,
    );
  }

  const handoffMode = typeof head.head.handoff_mode === "string"
    ? head.head.handoff_mode
    : "legacy";
  if (!["legacy", "soft_claim", "hard_lease"].includes(handoffMode)) {
    return failure("invalid_handoff_mode", "canonical projection has an invalid handoff mode");
  }
  if (leaseRequest !== null && handoffMode !== "hard_lease") {
    return failure(
      "claim_lease_requires_hard_lease",
      "atomic Todo claim and lease acquire requires handoff_mode=hard_lease",
      { todo_id: input.todo_id, handoff_mode: handoffMode },
    );
  }

  let lease: JsonObject | null = null;
  let leaseChanged = false;
  let leaseIdempotent = false;
  try {
    const currentLease = projection.leases.get(input.todo_id);
    if (handoffMode === "hard_lease" && leaseRequest !== null) {
      const todoFact = todoLeaseFact(todo);
      const currentActive = currentLease !== undefined && leaseIsActive(currentLease, input.now);
      const currentEffective = currentLease !== undefined && currentActive && ownerRejection(
        todoFact,
        normalizeAgent(currentLease.owner),
        input.registered_agents,
      ) === null;
      const otherLeases = projection.lease_todo_ids.flatMap((todoId) => {
        if (todoId === input.todo_id) return [];
        const candidate = projection.leases.get(todoId)!;
        const active = leaseIsActive(candidate, input.now);
        const otherTodo = projection.todos.get(todoId);
        return [{
          todo_id: todoId,
          active,
          effective: active && otherTodo !== undefined && ownerRejection(
            todoLeaseFact(otherTodo),
            normalizeAgent(candidate.owner),
            input.registered_agents,
          ) === null,
          write_scopes: normalizeWriteScopes(candidate.write_scopes),
        }];
      });
      const writeScopes = normalizeWriteScopes(todo.required_write_scopes ?? []);
      const decision = evaluateTaskLeaseAcquireDecision({
        handoff_mode: handoffMode,
        registered_agents: [...input.registered_agents],
        todo: todoFact,
        lease: currentLease === undefined ? null : {
          present: true,
          active: currentActive,
          effective: currentEffective,
          status: typeof currentLease.status === "string" ? currentLease.status : null,
          owner: normalizeAgent(currentLease.owner),
          idempotency_key: typeof currentLease.idempotency_key === "string"
            ? currentLease.idempotency_key : null,
          version: leaseInteger(currentLease, "version") ?? 0,
          lease_epoch: leaseEpoch(currentLease),
          write_scopes: normalizeWriteScopes(currentLease.write_scopes),
          acquire_ttl_seconds: leaseInteger(currentLease, "acquire_ttl_seconds"),
        },
        other_leases: otherLeases,
        command: {
          owner: authority.owner,
          idempotency_key: leaseRequest.idempotency_key,
          ttl_seconds: leaseRequest.ttl_seconds,
          write_scopes: writeScopes,
          expected_version: leaseRequest.expected_version,
        },
      });
      if (decision.outcome === "no_change") {
        if (currentLease === undefined) {
          throw new AuthorityStoreProtocolError(
            "lease acquire replay is missing its canonical lease",
          );
        }
        lease = currentLease;
        leaseIdempotent = true;
      } else if (decision.outcome === "apply") {
        if (decision.next_lease === null) {
          throw new AuthorityStoreProtocolError("lease acquire apply is missing next_lease");
        }
        const acquiredAt = utcIsoformat(input.now);
        lease = {
          schema_version: TASK_LEASE_SCHEMA_VERSION,
          goal_id: input.goal_id,
          todo_id: input.todo_id,
          owner: authority.owner,
          idempotency_key: leaseRequest.idempotency_key,
          write_scopes: writeScopes,
          acquire_ttl_seconds: leaseRequest.ttl_seconds,
          version: leaseDecisionInteger(decision.next_lease.version, "next_lease.version"),
          lease_epoch: leaseDecisionInteger(
            decision.next_lease.lease_epoch,
            "next_lease.lease_epoch",
          ),
          acquired_at: acquiredAt,
          updated_at: acquiredAt,
          expires_at: utcIsoformat(
            new Date(input.now.valueOf() + leaseRequest.ttl_seconds * 1_000),
          ),
          status: "active",
        } satisfies LeaseRecord;
        leaseChanged = true;
      } else {
        return failure(
          decision.code,
          `canonical task lease acquire rejected the Todo claim: ${decision.code}`,
          {
            todo_id: input.todo_id,
            actor_agent_id: authority.owner,
            lease_decision: decision,
          },
        );
      }
    } else if (handoffMode === "hard_lease" &&
        !activeLeaseForOwner(currentLease, authority.owner, input.now)) {
      return failure(
        "handoff_mode_requires_lease",
        "hard_lease Todo claim requires an active canonical lease held by the claiming agent",
        { todo_id: input.todo_id, actor_agent_id: authority.owner },
      );
    }
  } catch (error) {
    return failure(
      "invalid_coordination_task_lease",
      error instanceof Error ? error.message : "invalid canonical task lease",
      {todo_id: input.todo_id},
    );
  }

  const mutationAuthority = canonicalAuthorityObject(
    authority.mutation_authority,
    "Todo claim mutation authority",
  );
  const updatedAt = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  const todoChanged = todo.claimed_by !== authority.owner;
  const changed = todoChanged || leaseChanged;
  const result = {
    todo_id: input.todo_id,
    claimed_by: authority.owner,
    changed,
    handoff_mode: handoffMode,
    ...(changed ? {updated_at: updatedAt} : {}),
    mutation_authority: mutationAuthority,
    ...(leaseRequest === null ? {} : {
      todo_changed: todoChanged,
      lease_changed: leaseChanged,
      lease_idempotent: leaseIdempotent,
      lease,
    }),
  };

  if (input.dry_run) {
    return {
      ...result,
      schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
      status: changed ? "planned" : "no_change",
      dry_run: true,
      provider_revision: head.provider_revision,
      cursor: head.cursor,
    };
  }

  // A successful no-op still consumes its operation identity. Commit only its
  // receipt under the observed head's CAS; never fabricate a Todo mutation.
  const mutations: CoordinationProjectionMutation[] = [
    ...(leaseChanged && lease !== null
      ? [{kind: "lease_upsert" as const, lease}]
      : []),
    ...(todoChanged
      ? [{ kind: "todo_upsert" as const, todo: {...todo,
        claimed_by: authority.owner, updated_at: updatedAt} }]
      : []),
  ];
  const commit: AuthorityStoreCommit = mutations.length > 0 ? prepareCoordinationProjectionCommit({
    goal_id: input.goal_id,
    operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision,
    projection: head.head,
    mutations,
  }) : {
    operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision,
    next_projection: head.head,
    events: [],
    receipts: [],
  };
  // Reuse the validated reduction and event, but persist claim intent/result:
  // a full replacement's digest depends on state and cannot identify a retry.
  commit.receipts = [{
    schema_version: COORDINATION_TODO_CLAIM_RECEIPT_SCHEMA,
    operation_id: input.operation_id,
    goal_id: input.goal_id,
    request_sha256: requestSha,
    result,
  }];
  const committed = await store.commitAuthority(commit);
  const readback = replay(await store.readReceipt(input.operation_id),
    committed.status === "applied" ? "applied" : "recovered");
  if (readback !== null) return readback;
  return committed.status === "applied"
    ? failure("coordination_commit_readback_mismatch", "applied claim lacks its durable receipt")
    : { schema_version: COORDINATION_TODO_CLAIM_RESULT_SCHEMA, ...committed, changed: false };
}
