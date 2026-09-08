import { createHash } from "node:crypto";

import type { JsonObject } from "../effect_program.ts";
import type {
  AuthorityStore,
  AuthorityStoreCommit,
  AuthorityStoreReceiptResult,
} from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_ITEM_SCHEMA,
  canonicalCoordinationTodoRecord,
  canonicalTodoDomainRecord,
} from "./coordination_state_contract.ts";
import {
  indexCoordinationProjection,
  prepareCoordinationProjectionCommit,
  validateCoordinationTodoReadModel,
  type CoordinationProjectionMutation,
} from "./coordination_projection.ts";
import {
  compactPythonWhitespace,
  normalizeRegisteredTodoAgents,
  normalizeTodoAgent,
} from "./todo_agents.ts";
import {
  evaluateCoordinationTodoTerminalDecision,
  type CoordinationTodoTerminalDecisionResult,
} from "./todo_lifecycle_decision.ts";
import {
  reduceTodoCompletionTransaction,
  TODO_COMPLETION_TRANSACTION_REQUEST_SCHEMA,
} from "../todos/completion_transaction.ts";
import {
  TASK_LEASE_SCHEMA_VERSION,
  leaseEpoch,
  leaseInteger,
  normalizeAgent,
  normalizeWriteScopes,
} from "../work_items/task_lease_acquire.ts";
import { selectCoordinationTodoArchive } from "./todo_archive_selection.ts";
import {
  deriveCoordinationTodoSuccessorProposals,
  TODO_SUCCESSOR_DERIVATION_REQUEST_SCHEMA,
} from "./todo_successor_derivation.ts";

export const COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA =
  "loopx_coordination_todo_terminal_lifecycle_result_v0";
export const COORDINATION_TODO_TERMINAL_LIFECYCLE_RECEIPT_SCHEMA =
  "loopx_coordination_todo_terminal_lifecycle_receipt_v0";
export const COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA =
  "loopx_coordination_todo_archive_result_v0";
export const COORDINATION_TODO_ARCHIVE_RECEIPT_SCHEMA =
  "loopx_coordination_todo_archive_receipt_v0";

const TERMINAL_COMMANDS = ["complete", "supersede"] as const;
const TODO_ROLES = ["agent", "user"] as const;
const DECISION_OUTCOMES = ["approve", "reject", "cancel"] as const;
const COMPLETION_IDENTITY_SOURCES = [
  "turn_settlement",
  "unscoped_completion",
  "lifecycle_reentry",
] as const;
const USER_TODO_TASK_CLASSES = new Set(["user_action", "user_gate"]);

type TerminalCommand = typeof TERMINAL_COMMANDS[number];
type TodoRole = typeof TODO_ROLES[number];
type CompletionIdentitySource = typeof COMPLETION_IDENTITY_SOURCES[number];

export interface CoordinationTodoTerminalLifecycleInput {
  readonly goal_id: string;
  readonly todo_id: string;
  readonly expected_role: TodoRole | null;
  readonly command: TerminalCommand;
  readonly actor_agent_id: string | null;
  readonly registered_agents: readonly string[];
  readonly lifecycle_grants: readonly JsonObject[];
  readonly authority_reason: string | null;
  readonly decision_outcome: typeof DECISION_OUTCOMES[number] | null;
  readonly operation_id: string;
  readonly lease_idempotency_key: string | null;
  readonly lease_expected_version: number | null;
  readonly allow_user_gate_auto_acquire: boolean;
  readonly requested_no_followup: boolean;
  readonly requested_completion_turn_key: string | null;
  readonly requested_completion_identity_source: CompletionIdentitySource | null;
  readonly linked_successor_todo_ids: readonly string[];
  readonly successor_intents: readonly JsonObject[];
  readonly note: string | null;
  readonly evidence: string | null;
  readonly reason: string | null;
  readonly clear_claim: boolean;
  readonly validation_declaration: JsonObject | null;
  readonly validation_receipt: JsonObject | null;
  readonly completion_policy_request: JsonObject | null;
  readonly dry_run: boolean;
  readonly now: Date;
}

export interface CoordinationTodoArchiveInput {
  readonly goal_id: string;
  readonly role: TodoRole;
  readonly max_active_done: number;
  readonly operation_id: string;
  readonly dry_run: boolean;
  readonly now: Date;
}

export type CoordinationTodoTerminalLifecycleResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA;
};
export type CoordinationTodoArchiveResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA;
};

type CoordinationTodoTerminalFailureKind =
  | "decision_rejection"
  | "protocol_failure";

function optionalString(value: unknown, label: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") {
    throw new AuthorityStoreProtocolError(`${label} must be a string or null`);
  }
  return value;
}

function optionalAgent(value: unknown, label: string): string | null {
  const candidate = optionalString(value, label);
  return candidate === null ? null : normalizeTodoAgent(candidate, label);
}

function optionalSafeInteger(value: unknown, label: string): number | null {
  if (value === null || value === undefined) return null;
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new AuthorityStoreProtocolError(`${label} must be a non-negative safe integer or null`);
  }
  return Number(value);
}

function requireBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new AuthorityStoreProtocolError(`${label} must be a boolean`);
  }
  return value;
}

function optionalBoolean(value: unknown, label: string): boolean | null {
  if (value === null || value === undefined) return null;
  return requireBoolean(value, label);
}

function requireDate(value: unknown, label: string): Date {
  if (!(value instanceof Date) || Number.isNaN(value.valueOf())) {
    throw new AuthorityStoreProtocolError(`${label} must be a valid Date`);
  }
  return value;
}

function requireLiteral<T extends string>(
  value: unknown,
  values: readonly T[],
  label: string,
): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new AuthorityStoreProtocolError(`${label} must be one of: ${values.join(", ")}`);
  }
  return value as T;
}

function uniqueIds(value: readonly string[], label: string): string[] {
  if (!Array.isArray(value)) {
    throw new AuthorityStoreProtocolError(`${label} must be an array`);
  }
  const values = value.map((item, index) =>
    requireAuthorityStoreId(item, `${label}[${index}]`));
  if (new Set(values).size !== values.length) {
    throw new AuthorityStoreProtocolError(`${label} must contain unique ids`);
  }
  return values;
}

function lifecycleGrants(value: readonly JsonObject[]): JsonObject[] {
  if (!Array.isArray(value)) {
    throw new AuthorityStoreProtocolError("lifecycle_grants must be an array");
  }
  return value.map((grant, index) =>
    canonicalAuthorityObject(grant, `lifecycle_grants[${index}]`));
}

function requireRegisteredSuccessorAgent(
  value: unknown,
  label: string,
  registeredAgents: readonly string[],
): string | null {
  const agent = optionalAgent(value, label);
  if (agent !== null && !registeredAgents.includes(agent)) {
    throw new AuthorityStoreProtocolError(`${label} is not a registered agent`);
  }
  return agent;
}

function validateSuccessorSemantics(
  successors: readonly JsonObject[],
  registeredAgents: readonly string[],
): void {
  for (const role of TODO_ROLES) {
    if (successors.filter((successor) => successor.role === role).length > 1) {
      throw new AuthorityStoreProtocolError(
        `terminal lifecycle permits at most one generated ${role} successor`,
      );
    }
  }
  for (const successor of successors) {
    const role = requireLiteral(successor.role, TODO_ROLES, "successor.role");
    const taskClass = optionalString(successor.task_class, "successor.task_class");
    const claimedBy = requireRegisteredSuccessorAgent(
      successor.claimed_by,
      "successor.claimed_by",
      registeredAgents,
    );
    const boundAgent = requireRegisteredSuccessorAgent(
      successor.bound_agent,
      "successor.bound_agent",
      registeredAgents,
    );
    const blocksAgent = requireRegisteredSuccessorAgent(
      successor.blocks_agent,
      "successor.blocks_agent",
      registeredAgents,
    );
    const goalBound = optionalBoolean(successor.goal_bound, "successor.goal_bound");
    const globalGate = optionalBoolean(successor.global_gate, "successor.global_gate");
    if (role === "agent") {
      if (USER_TODO_TASK_CLASSES.has(taskClass ?? "") || boundAgent !== null ||
          blocksAgent !== null || goalBound === true || globalGate === true) {
        throw new AuthorityStoreProtocolError(
          "generated Agent successor carries user-only task or binding semantics",
        );
      }
      continue;
    }
    if (!USER_TODO_TASK_CLASSES.has(taskClass ?? "")) {
      throw new AuthorityStoreProtocolError(
        "generated User successor requires task_class user_action or user_gate",
      );
    }
    if (claimedBy !== null) {
      throw new AuthorityStoreProtocolError(
        "generated User successor cannot carry claimed_by ownership",
      );
    }
    if (boundAgent !== null && goalBound === true) {
      throw new AuthorityStoreProtocolError(
        "generated User successor cannot be both agent-bound and goal-bound",
      );
    }
    if (taskClass === "user_action" && (blocksAgent !== null || globalGate === true)) {
      throw new AuthorityStoreProtocolError(
        "generated user_action successor cannot carry blocking gate scope",
      );
    }
    if (taskClass === "user_gate") {
      if (globalGate === true &&
          (blocksAgent !== null || boundAgent !== null || goalBound !== true)) {
        throw new AuthorityStoreProtocolError(
          "goal-wide User gate successor requires goal_bound and no Agent binding",
        );
      }
      if (blocksAgent !== null &&
          (goalBound === true || boundAgent !== blocksAgent)) {
        throw new AuthorityStoreProtocolError(
          "Agent-scoped User gate successor must bind to its blocks_agent",
        );
      }
      if (registeredAgents.length > 1 && blocksAgent === null && globalGate !== true) {
        throw new AuthorityStoreProtocolError(
          "multi-agent User gate successor requires an explicit blocking scope",
        );
      }
    }
    if (registeredAgents.length > 1 && boundAgent === null && goalBound !== true) {
      throw new AuthorityStoreProtocolError(
        "multi-agent User successor requires an explicit Agent or Goal binding",
      );
    }
  }
}

function normalizeTerminalInput(
  raw: CoordinationTodoTerminalLifecycleInput,
): CoordinationTodoTerminalLifecycleInput {
  const registeredAgents = normalizeRegisteredTodoAgents(raw.registered_agents);
  if (!Array.isArray(raw.successor_intents)) {
    throw new AuthorityStoreProtocolError("successor_intents must be an array");
  }
  const successorIntents = raw.successor_intents.map((intent, index) =>
    canonicalAuthorityObject(intent, `successor_intents[${index}]`));
  return {
    ...raw,
    goal_id: requireAuthorityStoreId(raw.goal_id, "goal id"),
    todo_id: requireAuthorityStoreId(raw.todo_id, "todo id"),
    operation_id: requireAuthorityStoreId(raw.operation_id, "operation id"),
    expected_role: raw.expected_role === null
      ? null : requireLiteral(raw.expected_role, TODO_ROLES, "expected_role"),
    command: requireLiteral(raw.command, TERMINAL_COMMANDS, "command"),
    actor_agent_id: optionalAgent(raw.actor_agent_id, "actor_agent_id"),
    registered_agents: registeredAgents,
    lifecycle_grants: lifecycleGrants(raw.lifecycle_grants),
    authority_reason: optionalString(raw.authority_reason, "authority_reason"),
    decision_outcome: raw.decision_outcome === null
      ? null : requireLiteral(raw.decision_outcome, DECISION_OUTCOMES, "decision_outcome"),
    lease_idempotency_key: optionalString(raw.lease_idempotency_key, "lease_idempotency_key"),
    lease_expected_version: optionalSafeInteger(
      raw.lease_expected_version,
      "lease_expected_version",
    ),
    allow_user_gate_auto_acquire: requireBoolean(
      raw.allow_user_gate_auto_acquire,
      "allow_user_gate_auto_acquire",
    ),
    requested_no_followup: requireBoolean(raw.requested_no_followup, "requested_no_followup"),
    requested_completion_turn_key: optionalString(
      raw.requested_completion_turn_key,
      "requested_completion_turn_key",
    ),
    requested_completion_identity_source:
      raw.requested_completion_identity_source === null
        ? null
        : requireLiteral(
          raw.requested_completion_identity_source,
          COMPLETION_IDENTITY_SOURCES,
          "requested_completion_identity_source",
        ),
    linked_successor_todo_ids: uniqueIds(
      raw.linked_successor_todo_ids,
      "linked_successor_todo_ids",
    ),
    successor_intents: successorIntents,
    note: optionalString(raw.note, "note"),
    evidence: optionalString(raw.evidence, "evidence"),
    reason: optionalString(raw.reason, "reason"),
    clear_claim: requireBoolean(raw.clear_claim, "clear_claim"),
    validation_declaration: raw.validation_declaration === null
      ? null : canonicalAuthorityObject(
        raw.validation_declaration,
        "validation_declaration",
      ),
    validation_receipt: raw.validation_receipt === null
      ? null : canonicalAuthorityObject(raw.validation_receipt, "validation_receipt"),
    completion_policy_request: raw.completion_policy_request === null
      ? null
      : canonicalAuthorityObject(raw.completion_policy_request, "completion_policy_request"),
    dry_run: requireBoolean(raw.dry_run, "dry_run"),
    now: requireDate(raw.now, "now"),
  };
}

function terminalFailure(
  code: string,
  reason: string,
  detail: JsonObject = {},
  kind: CoordinationTodoTerminalFailureKind = "protocol_failure",
): CoordinationTodoTerminalLifecycleResult {
  return {
    ...detail,
    schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
    status: "failed",
    changed: false,
    failure_kind: kind,
    reason_code: code,
    reason,
  };
}

function archiveFailure(code: string, reason: string): CoordinationTodoArchiveResult {
  return {
    schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
    status: "failed",
    changed: false,
    reason_code: code,
    reason,
  };
}

function terminalRequestSha(input: CoordinationTodoTerminalLifecycleInput): string {
  const completionPolicyIdentity = input.completion_policy_request === null
    ? null
    : {
      claimed_by: input.completion_policy_request.claimed_by ?? null,
      next_claimed_by: input.completion_policy_request.next_claimed_by ?? null,
      next_agent_todo: input.completion_policy_request.next_agent_todo ?? null,
      next_action_kind: input.completion_policy_request.next_action_kind ?? null,
      next_continuation_policy:
        input.completion_policy_request.next_continuation_policy ?? null,
      next_excluded_agents:
        input.completion_policy_request.next_excluded_agents ?? [],
      self_merged: input.completion_policy_request.self_merged ?? false,
    };
  return canonicalAuthoritySha256({
    goal_id: input.goal_id,
    todo_id: input.todo_id,
    expected_role: input.expected_role,
    command: input.command,
    actor_agent_id: input.actor_agent_id,
    authority_reason: input.authority_reason,
    decision_outcome: input.decision_outcome,
    lease_idempotency_key: input.lease_idempotency_key,
    lease_expected_version: input.lease_expected_version,
    allow_user_gate_auto_acquire: input.allow_user_gate_auto_acquire,
    requested_no_followup: input.requested_no_followup,
    requested_completion_turn_key: input.requested_completion_turn_key,
    requested_completion_identity_source: input.requested_completion_identity_source,
    linked_successor_todo_ids: input.linked_successor_todo_ids,
    successor_intents: input.successor_intents,
    clear_claim: input.clear_claim,
    completion_policy_request: completionPolicyIdentity,
    validation_declaration_sha256: input.validation_declaration === null
      ? null : canonicalAuthoritySha256(input.validation_declaration),
    dry_run: input.dry_run,
  });
}

function replayTerminal(
  receipt: AuthorityStoreReceiptResult,
  input: CoordinationTodoTerminalLifecycleInput,
  requestSha: string,
  status: "replayed" | "applied" | "recovered",
): CoordinationTodoTerminalLifecycleResult | null {
  if (receipt.status === "missing") return null;
  if (receipt.status !== "found") {
    return {
      schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
      ...receipt,
      changed: false,
    };
  }
  const original = receipt.receipts[0];
  if (receipt.receipts.length !== 1 ||
      original?.schema_version !== COORDINATION_TODO_TERMINAL_LIFECYCLE_RECEIPT_SCHEMA ||
      original.operation_id !== input.operation_id || original.goal_id !== input.goal_id ||
      original.todo_id !== input.todo_id || original.command !== input.command ||
      original.request_sha256 !== requestSha) {
    return terminalFailure(
      "coordination_operation_identity_mismatch",
      "operation id already names a different Todo terminal lifecycle request",
      {},
      "decision_rejection",
    );
  }
  const result = canonicalAuthorityObject(original.result, "terminal lifecycle receipt result");
  return {
    ...result,
    schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
    status: status === "applied" && result.changed === false ? "no_change" : status,
    changed: status !== "replayed" && result.changed === true,
    provider_revision: receipt.provider_revision,
    cursor: receipt.cursor,
    original_receipt: original,
    projection_delivery: result.changed === true ? "pending" : "not_required",
    projection_source: "committed_authority_journal",
  };
}

async function commitTerminalResult(
  store: AuthorityStore,
  input: CoordinationTodoTerminalLifecycleInput,
  requestSha: string,
  head: Extract<Awaited<ReturnType<AuthorityStore["loadAuthority"]>>, {status: "loaded"}>,
  result: JsonObject,
  mutations: readonly CoordinationProjectionMutation[],
): Promise<CoordinationTodoTerminalLifecycleResult> {
  if (input.dry_run) {
    return {
      ...result,
      schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
      status: result.changed === true ? "planned" : "no_change",
      dry_run: true,
      provider_revision: head.provider_revision,
      cursor: head.cursor,
    };
  }
  const commit: AuthorityStoreCommit = mutations.length > 0
    ? prepareCoordinationProjectionCommit({
      goal_id: input.goal_id,
      operation_id: input.operation_id,
      expected_provider_revision: head.provider_revision,
      projection: head.head,
      mutations: [...mutations],
    })
    : {
      operation_id: input.operation_id,
      expected_provider_revision: head.provider_revision,
      next_projection: head.head,
      events: [],
      receipts: [],
    };
  commit.receipts = [{
    schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RECEIPT_SCHEMA,
    operation_id: input.operation_id,
    goal_id: input.goal_id,
    todo_id: input.todo_id,
    command: input.command,
    request_sha256: requestSha,
    result,
  }];
  const committed = await store.commitAuthority(commit);
  const readback = replayTerminal(
    await store.readReceipt(input.operation_id),
    input,
    requestSha,
    committed.status === "applied" ? "applied" : "recovered",
  );
  if (readback !== null) return readback;
  return committed.status === "applied"
    ? terminalFailure(
      "coordination_commit_readback_mismatch",
      "applied terminal lifecycle mutation lacks its durable receipt",
    )
    : {
      schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
      ...committed,
      changed: false,
    };
}

function todoFact(todo: JsonObject): JsonObject {
  return {
    todo_id: todo.todo_id,
    status: todo.status,
    role: todo.role,
    task_class: todo.task_class ?? null,
    claimed_by: todo.claimed_by ?? null,
    excluded_agents: todo.excluded_agents ?? [],
    bound_agent: todo.bound_agent ?? null,
    blocks_agent: todo.blocks_agent ?? null,
    decision_scope: todo.decision_scope ?? null,
    required_decision_scopes: todo.required_decision_scopes ?? [],
    unblocks_todo_id: todo.unblocks_todo_id ?? null,
  };
}

function activeLease(lease: JsonObject | undefined, now: Date): boolean {
  if (lease === undefined || lease.status !== "active" || typeof lease.expires_at !== "string") {
    return false;
  }
  const expiresAt = new Date(lease.expires_at);
  return !Number.isNaN(expiresAt.valueOf()) && expiresAt.valueOf() > now.valueOf();
}

function leaseFact(lease: JsonObject | undefined, now: Date): JsonObject | null {
  if (lease === undefined) return null;
  return {
    present: true,
    active: activeLease(lease, now),
    status: typeof lease.status === "string" ? lease.status : null,
    owner: normalizeAgent(lease.owner),
    idempotency_key: typeof lease.idempotency_key === "string"
      ? lease.idempotency_key : null,
    version: leaseInteger(lease, "version") ?? 0,
    lease_epoch: leaseEpoch(lease),
    write_scopes: normalizeWriteScopes(lease.write_scopes),
    acquire_ttl_seconds: leaseInteger(lease, "acquire_ttl_seconds"),
  };
}

function releasedLease(
  current: JsonObject | undefined,
  decision: CoordinationTodoTerminalDecisionResult,
  input: CoordinationTodoTerminalLifecycleInput,
): JsonObject | null {
  if (decision.next_lease === null) return null;
  const observedAt = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  if (current !== undefined) {
    return {
      ...current,
      status: "released",
      updated_at: observedAt,
    };
  }
  return {
    schema_version: TASK_LEASE_SCHEMA_VERSION,
    goal_id: input.goal_id,
    todo_id: input.todo_id,
    owner: decision.next_lease.owner,
    idempotency_key: decision.next_lease.idempotency_key,
    write_scopes: decision.next_lease.write_scopes,
    acquire_ttl_seconds: decision.next_lease.acquire_ttl_seconds,
    version: decision.next_lease.version,
    lease_epoch: decision.next_lease.lease_epoch,
    acquired_at: observedAt,
    updated_at: observedAt,
    expires_at: observedAt,
    status: "released",
  };
}

function successorCandidate(
  todo: JsonObject,
  actor: string | null,
  now: Date,
  domainReadModel: boolean,
  completionPolicy: JsonObject | null,
): JsonObject {
  const policyOwned: JsonObject = todo.role === "agent" && completionPolicy !== null
    ? {
      ...(completionPolicy.effective_next_claimed_by === null
        ? {}
        : {claimed_by: completionPolicy.effective_next_claimed_by}),
      excluded_agents: completionPolicy.effective_next_excluded_agents,
    }
    : {};
  const candidate: JsonObject = {
    ...todo,
    ...policyOwned,
    schema_version: TODO_DOMAIN_ITEM_SCHEMA,
    created_by: todo.created_by ?? actor,
    last_actor_agent_id: actor,
    updated_at: now.toISOString().replace(/\.\d{3}Z$/u, "Z"),
  };
  if (todo.role === "agent" && completionPolicy !== null &&
      completionPolicy.effective_next_claimed_by === null) {
    delete candidate.claimed_by;
  }
  const created = canonicalTodoDomainRecord(candidate, "terminal successor");
  return domainReadModel ? created : canonicalCoordinationTodoRecord({
    ...created,
    schema_version: TODO_ITEM_SCHEMA,
    source_section: created.role === "agent" ? "Agent Todo" : "User Todo",
  }, "terminal successor compatibility record");
}

function generatedSuccessorId(
  predecessorId: string,
  successor: JsonObject,
  offset: number,
): string {
  const role = String(successor.role);
  const section = role === "agent" ? "Agent Todo" : "User Todo";
  const identity = [
    role,
    section,
    `${predecessorId}:${offset}`,
    compactPythonWhitespace(String(successor.text ?? "")),
  ].join("|");
  return `todo_${createHash("sha1").update(identity, "utf8").digest("hex").slice(0, 12)}`;
}

function materializeSuccessorProposals(
  predecessorId: string,
  proposals: readonly JsonObject[],
): JsonObject[] {
  const successors = proposals.map((proposal, index) =>
    canonicalTodoDomainRecord({
      ...proposal,
      schema_version: TODO_DOMAIN_ITEM_SCHEMA,
      todo_id: generatedSuccessorId(predecessorId, proposal, index + 1),
      status: "open",
      done: false,
      archive_state: "active",
    }, `derived successors[${index}]`));
  const successorIds = successors.map((successor) => String(successor.todo_id));
  if (new Set(successorIds).size !== successorIds.length) {
    throw new AuthorityStoreProtocolError("derived successors must contain unique Todo ids");
  }
  return successors;
}

function terminalTarget(
  todo: JsonObject,
  input: CoordinationTodoTerminalLifecycleInput,
  completion: ReturnType<typeof reduceTodoCompletionTransaction> | null,
  successorIds: readonly string[],
): { todo: JsonObject; clear_fields: string[] } {
  const updatedAt = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  const next: JsonObject = {
    ...todo,
    status: "done",
    done: true,
    completed_at: todo.completed_at ?? updatedAt,
    updated_at: updatedAt,
    last_actor_agent_id: input.actor_agent_id,
    ...(input.note === null ? {} : {note: input.note}),
    ...(input.evidence === null ? {} : {evidence: input.evidence}),
    ...(input.reason === null ? {} : {reason: input.reason}),
    ...(input.decision_outcome === null ? {} : {decision_outcome: input.decision_outcome}),
    ...(input.requested_no_followup ? {no_followup: true} : {}),
    ...(successorIds.length === 0 ? {} : {successor_todo_ids: successorIds}),
  };
  if (input.command === "supersede") {
    next.note = input.note ?? "superseded";
    // Legacy/event projection treats supersede as a terminal completion that
    // leaves the Goal itself active. Keep that durable continuation marker so
    // status/quota consumers do not infer an unclassified terminal record.
    next.completion_continuation = "active_goal";
    if (successorIds.length > 0) next.superseded_by = successorIds[0];
  }
  if (completion?.decision === "commit") {
    Object.assign(next, completion.metadata_updates);
    if (completion.completion_policy?.effective_claimed_by !== null &&
        completion.completion_policy?.effective_claimed_by !== undefined) {
      next.claimed_by = completion.completion_policy.effective_claimed_by;
    }
    if (completion.completion_identity_key !== null) {
      next.completion_turn_key = completion.completion_identity_key;
    }
  }
  const clearFields: string[] = [];
  if (input.clear_claim && "claimed_by" in next) {
    delete next.claimed_by;
    clearFields.push("claimed_by");
  }
  if (todo.schema_version === TODO_DOMAIN_ITEM_SCHEMA) {
    canonicalTodoDomainRecord(next, "terminal Todo");
  } else {
    canonicalCoordinationTodoRecord(next, "terminal Todo");
  }
  return {todo: next, clear_fields: clearFields};
}

function semanticDuplicate(
  todos: ReadonlyMap<string, JsonObject>,
  successor: JsonObject,
): JsonObject | undefined {
  return [...todos.values()].find((todo) =>
    todo.role === successor.role && todo.archive_state === "active" &&
    todo.status !== "done" && todo.status !== "deferred" && todo.text === successor.text);
}

/**
 * Execute complete/supersede as one provider-neutral CAS transaction.
 *
 * Authorization, lease release, completion policy, successor creation,
 * durable replay identity, and projection intent are decided before the
 * provider sees a commit. Python may execute the typed validation effect and
 * project the committed head; it is not a second semantic owner.
 */
export async function executeCoordinationTodoTerminalLifecycle(
  store: AuthorityStore,
  rawInput: CoordinationTodoTerminalLifecycleInput,
): Promise<CoordinationTodoTerminalLifecycleResult> {
  let input: CoordinationTodoTerminalLifecycleInput;
  try {
    input = normalizeTerminalInput(rawInput);
  } catch (error) {
    return terminalFailure(
      "invalid_coordination_todo_terminal_lifecycle",
      error instanceof Error ? error.message : "invalid Todo terminal lifecycle request",
    );
  }
  const requestSha = terminalRequestSha(input);
  const replay = replayTerminal(
    await store.readReceipt(input.operation_id),
    input,
    requestSha,
    "replayed",
  );
  if (replay !== null) return replay;

  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {
      schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
      ...head,
      changed: false,
    };
  }
  let projection: ReturnType<typeof indexCoordinationProjection>;
  let readModel: JsonObject;
  try {
    projection = indexCoordinationProjection(head.head, input.goal_id);
    readModel = validateCoordinationTodoReadModel(head.head, input.goal_id);
  } catch (error) {
    return terminalFailure(
      "invalid_coordination_projection",
      error instanceof Error ? error.message : "invalid coordination projection",
    );
  }
  const todo = projection.todos.get(input.todo_id);
  if (todo === undefined) {
    return terminalFailure("todo_not_found", "Todo is missing from the canonical provider head", {
      todo_id: input.todo_id,
    }, "decision_rejection");
  }
  if (input.expected_role !== null && todo.role !== input.expected_role) {
    return terminalFailure(
      "todo_role_mismatch",
      "Todo does not have the requested role",
      {},
      "decision_rejection",
    );
  }
  if (todo.archive_state !== "active") {
    return terminalFailure(
      "todo_archived",
      "Todo terminal lifecycle requires an active Todo",
      {},
      "decision_rejection",
    );
  }
  const handoffMode = typeof head.head.handoff_mode === "string"
    ? head.head.handoff_mode : "legacy";
  if (!["legacy", "soft_claim", "hard_lease"].includes(handoffMode)) {
    return terminalFailure("invalid_handoff_mode", "canonical projection has an invalid handoff mode");
  }
  const decisionTarget = typeof todo.unblocks_todo_id === "string"
    ? projection.todos.get(todo.unblocks_todo_id) : undefined;
  let authority: CoordinationTodoTerminalDecisionResult;
  try {
    authority = evaluateCoordinationTodoTerminalDecision({
      schema_version: "loopx_coordination_todo_terminal_decision_request_v0",
      command: input.command,
      handoff_mode: handoffMode,
      registered_agents: input.registered_agents,
      lifecycle_grants: input.lifecycle_grants,
      todo: todoFact(todo),
      decision_target: decisionTarget === undefined ? null : todoFact(decisionTarget),
      lease: leaseFact(projection.leases.get(input.todo_id), input.now),
      actor_agent_id: input.actor_agent_id,
      authority_action: input.command,
      authority_reason: input.authority_reason,
      decision_outcome: input.decision_outcome,
      lease_idempotency_key: input.lease_idempotency_key,
      lease_expected_version: input.lease_expected_version,
      allow_user_gate_auto_acquire: input.allow_user_gate_auto_acquire,
    });
  } catch (error) {
    return terminalFailure(
      "invalid_coordination_todo_terminal_lifecycle",
      error instanceof Error ? error.message : "invalid Todo terminal decision",
    );
  }
  if (authority.outcome === "rejected" || authority.outcome === "conflict") {
    return terminalFailure(
      authority.code,
      `canonical Todo terminal lifecycle rejected the request: ${authority.code}`,
      {terminal_decision: authority},
      "decision_rejection",
    );
  }

  let completion: ReturnType<typeof reduceTodoCompletionTransaction> | null = null;
  if (input.command === "complete") {
    const validationRequired = todo.completion_validation_required === true;
    const validationSha256 = todo.completion_validation_sha256;
    if (validationRequired) {
      if (typeof validationSha256 !== "string" || !/^[a-f0-9]{64}$/u.test(validationSha256)) {
        return terminalFailure(
          "completion_validation_identity_missing",
          "canonical Todo requires validation but omits its declaration digest",
        );
      }
      if (input.validation_declaration === null) {
        return terminalFailure(
          "completion_validation_declaration_unavailable",
          "private completion validation declaration is unavailable",
        );
      }
      if (canonicalAuthoritySha256(input.validation_declaration) !== validationSha256) {
        return terminalFailure(
          "completion_validation_declaration_mismatch",
          "private completion validation declaration does not match canonical authority",
        );
      }
    } else if (input.validation_declaration !== null) {
      return terminalFailure(
        "completion_validation_declaration_forbidden",
        "Todo without canonical validation authority cannot execute a private declaration",
      );
    }
    try {
      completion = reduceTodoCompletionTransaction({
        schema_version: TODO_COMPLETION_TRANSACTION_REQUEST_SCHEMA,
        goal_id: input.goal_id,
        todo_id: input.todo_id,
        projection_source: "materialized",
        todo: input.validation_declaration === null
          ? todo : {...todo, ...input.validation_declaration},
        requested_no_followup: input.requested_no_followup,
        requested_completion_turn_key: input.requested_completion_turn_key,
        requested_completion_identity_source: input.requested_completion_identity_source,
        requested_has_successor:
          input.successor_intents.length > 0 || input.linked_successor_todo_ids.length > 0,
        dry_run: input.dry_run,
        validation_receipt: input.validation_receipt,
        completion_policy_request: input.completion_policy_request,
      });
    } catch (error) {
      return terminalFailure(
        "invalid_todo_completion_transaction",
        error instanceof Error ? error.message : "invalid Todo completion transaction",
      );
    }
    if (completion.decision === "execute_validation") {
      return {
        schema_version: COORDINATION_TODO_TERMINAL_LIFECYCLE_RESULT_SCHEMA,
        status: "execute_validation",
        changed: false,
        todo_id: input.todo_id,
        command: input.command,
        validation_effect: completion.validation_effect,
        completion_identity_key: completion.completion_identity_key,
        completion_identity_source: completion.completion_identity_source,
        provider_revision: head.provider_revision,
        cursor: head.cursor,
      };
    }
    if (completion.decision === "reject") {
      return terminalFailure(
        completion.failure.kind,
        completion.failure.summary,
        {validation_failure: completion.failure},
      );
    }
  } else if (input.validation_declaration !== null || input.validation_receipt !== null ||
      input.completion_policy_request !== null) {
    return terminalFailure(
      "supersede_completion_payload_forbidden",
      "supersede must not carry completion validation or policy payload",
    );
  }

  if (authority.outcome === "no_change") {
    if (input.successor_intents.length > 0) {
      return terminalFailure(
        "todo_terminal_successor_intent_after_completion",
        "an already terminal Todo cannot accept a new generated successor intent",
        {},
        "decision_rejection",
      );
    }
    const existingSuccessorIds = Array.isArray(todo.successor_todo_ids)
      ? todo.successor_todo_ids.map((value, index) =>
        requireAuthorityStoreId(value, `todo.successor_todo_ids[${index}]`))
      : [];
    return commitTerminalResult(store, input, requestSha, head, {
      todo_id: input.todo_id,
      command: input.command,
      changed: false,
      terminal_decision: authority,
      successor_todo_ids: existingSuccessorIds,
      generated_successor_todo_ids: [],
      validation_receipt: null,
      completion_policy: null,
      completion_identity_key:
        completion === null ? null : completion.completion_identity_key,
      completion_identity_source:
        completion === null ? null : completion.completion_identity_source,
      completed_at: typeof todo.completed_at === "string" ? todo.completed_at : null,
    }, []);
  }

  const domainReadModel = readModel.schema_version === TODO_DOMAIN_READ_RECORD_SCHEMA;
  const completionPolicy = completion?.decision === "commit" &&
      completion.completion_policy !== undefined
    ? canonicalAuthorityObject(completion.completion_policy, "completion policy result")
    : null;
  if (completionPolicy !== null &&
      canonicalAuthoritySha256(completionPolicy.registered_agents) !==
        canonicalAuthoritySha256(input.registered_agents)) {
    return terminalFailure(
      "completion_policy_registry_mismatch",
      "completion policy registered_agents must match terminal authority facts",
    );
  }
  let successors: JsonObject[];
  try {
    const proposals = deriveCoordinationTodoSuccessorProposals({
      schema_version: TODO_SUCCESSOR_DERIVATION_REQUEST_SCHEMA,
      command: input.command,
      predecessor: todo,
      registered_agents: input.registered_agents,
      actor_agent_id: input.actor_agent_id,
      completion_policy: completionPolicy,
      successor_intents: input.successor_intents,
    });
    successors = materializeSuccessorProposals(input.todo_id, proposals);
    validateSuccessorSemantics(successors, input.registered_agents);
  } catch (error) {
    return terminalFailure(
      "invalid_todo_successor_derivation",
      error instanceof Error ? error.message : "invalid Todo successor derivation",
      {},
      "decision_rejection",
    );
  }
  const generatedSuccessorIds = successors.map((successor) => String(successor.todo_id));
  const successorIds = [...new Set([
    ...input.linked_successor_todo_ids,
    ...generatedSuccessorIds,
  ])];
  for (const successorId of input.linked_successor_todo_ids) {
    if (!projection.todos.has(successorId)) {
      return terminalFailure(
        "todo_successor_not_found",
        "linked successor Todo is missing from the canonical provider head",
        {todo_id: successorId},
      );
    }
  }
  for (const successorId of successorIds) {
    if (successorId === input.todo_id) {
      return terminalFailure("todo_successor_cycle", "Todo cannot name itself as a successor");
    }
  }
  if (completionPolicy !== null) {
    const agentSuccessorIntents = input.successor_intents.filter(
      (successor) => successor.role === "agent",
    );
    if (agentSuccessorIntents.length > 1) {
      return terminalFailure(
        "completion_policy_successor_ambiguity",
        "completion policy currently permits at most one generated Agent successor",
      );
    }
    const requestedNextAgentTodo = input.completion_policy_request?.next_agent_todo;
    if ((requestedNextAgentTodo === null || requestedNextAgentTodo === undefined) !==
          (agentSuccessorIntents.length === 0) ||
        (agentSuccessorIntents.length === 1 &&
          requestedNextAgentTodo !== agentSuccessorIntents[0]!.text)) {
      return terminalFailure(
        "completion_policy_successor_mismatch",
        "completion policy next_agent_todo must identify the generated Agent successor",
      );
    }
  }
  const userSuccessor = successors.find((successor) => successor.role === "user");
  if (input.command === "complete" && input.registered_agents.length > 1 &&
      userSuccessor !== undefined) {
    const completingAgent = completionPolicy?.effective_claimed_by;
    if (typeof completingAgent !== "string" || userSuccessor.bound_agent !== completingAgent ||
        (userSuccessor.task_class === "user_gate" &&
          userSuccessor.blocks_agent !== completingAgent)) {
      return terminalFailure(
        "completion_user_successor_binding_mismatch",
        "multi-agent completion must bind its User successor to the effective completing Agent",
      );
    }
  }
  const successorCandidates: JsonObject[] = [];
  for (const successor of successors) {
    const successorId = String(successor.todo_id);
    if (projection.todos.has(successorId)) {
      return terminalFailure("todo_already_exists", "terminal successor Todo id already exists", {
        todo_id: successorId,
      });
    }
    const duplicate = semanticDuplicate(projection.todos, successor);
    if (duplicate !== undefined) {
      return terminalFailure(
        "todo_semantic_duplicate_conflict",
        "an active Todo with the same role/text already exists",
        {todo_id: duplicate.todo_id},
      );
    }
    successorCandidates.push(successorCandidate(
      successor,
      input.actor_agent_id,
      input.now,
      domainReadModel,
      completionPolicy,
    ));
  }

  const currentLease = projection.leases.get(input.todo_id);
  const released = releasedLease(currentLease, authority, input);
  const target = terminalTarget(todo, input, completion, successorIds);
  const changed = authority.outcome === "apply";
  const result: JsonObject = {
    todo_id: input.todo_id,
    command: input.command,
    changed,
    terminal_decision: authority,
    successor_todo_ids: successorIds,
    generated_successor_todo_ids: generatedSuccessorIds,
    generated_successors: successorCandidates,
    validation_receipt:
      completion?.decision === "commit" ? completion.validation_receipt : null,
    completion_policy: completionPolicy,
    completion_identity_key:
      completion === null ? null : completion.completion_identity_key,
    completion_identity_source:
      completion === null ? null : completion.completion_identity_source,
    completed_at: target.todo.completed_at,
  };
  const mutations: CoordinationProjectionMutation[] = changed ? [
    {kind: "todo_upsert", todo: target.todo, clear_fields: target.clear_fields},
    ...successorCandidates.map((successor) => ({kind: "todo_upsert" as const, todo: successor})),
    ...(released === null ? [] : [{kind: "lease_upsert" as const, lease: released}]),
  ] : [];
  return commitTerminalResult(store, input, requestSha, head, result, mutations);
}

function normalizeArchiveInput(raw: CoordinationTodoArchiveInput): CoordinationTodoArchiveInput {
  if (!Number.isSafeInteger(raw.max_active_done) || raw.max_active_done < 0) {
    throw new AuthorityStoreProtocolError("max_active_done must be a non-negative safe integer");
  }
  return {
    ...raw,
    goal_id: requireAuthorityStoreId(raw.goal_id, "goal id"),
    role: requireLiteral(raw.role, TODO_ROLES, "role"),
    operation_id: requireAuthorityStoreId(raw.operation_id, "operation id"),
    dry_run: requireBoolean(raw.dry_run, "dry_run"),
    now: requireDate(raw.now, "now"),
  };
}

function replayArchive(
  receipt: AuthorityStoreReceiptResult,
  input: CoordinationTodoArchiveInput,
  requestSha: string,
  status: "replayed" | "applied" | "recovered",
): CoordinationTodoArchiveResult | null {
  if (receipt.status === "missing") return null;
  if (receipt.status !== "found") {
    return {schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...receipt, changed: false};
  }
  const original = receipt.receipts[0];
  if (receipt.receipts.length !== 1 ||
      original?.schema_version !== COORDINATION_TODO_ARCHIVE_RECEIPT_SCHEMA ||
      original.operation_id !== input.operation_id || original.goal_id !== input.goal_id ||
      original.request_sha256 !== requestSha) {
    return archiveFailure(
      "coordination_operation_identity_mismatch",
      "operation id already names a different Todo archive request",
    );
  }
  const result = canonicalAuthorityObject(original.result, "Todo archive receipt result");
  return {
    ...result,
    schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
    status,
    changed: status !== "replayed" && result.changed === true,
    provider_revision: receipt.provider_revision,
    cursor: receipt.cursor,
    original_receipt: original,
    projection_delivery: result.changed === true ? "pending" : "not_required",
    projection_source: "committed_authority_journal",
  };
}

/** Archive the oldest canonical completed records while preserving standing decisions. */
export async function executeCoordinationTodoArchiveCompleted(
  store: AuthorityStore,
  rawInput: CoordinationTodoArchiveInput,
): Promise<CoordinationTodoArchiveResult> {
  let input: CoordinationTodoArchiveInput;
  try {
    input = normalizeArchiveInput(rawInput);
  } catch (error) {
    return archiveFailure(
      "invalid_coordination_todo_archive",
      error instanceof Error ? error.message : "invalid Todo archive request",
    );
  }
  const requestSha = canonicalAuthoritySha256({
    goal_id: input.goal_id,
    role: input.role,
    max_active_done: input.max_active_done,
    dry_run: input.dry_run,
  });
  const replay = replayArchive(
    await store.readReceipt(input.operation_id), input, requestSha, "replayed",
  );
  if (replay !== null) return replay;
  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...head, changed: false};
  }
  let projection: ReturnType<typeof indexCoordinationProjection>;
  try {
    projection = indexCoordinationProjection(head.head, input.goal_id);
    validateCoordinationTodoReadModel(head.head, input.goal_id);
  } catch (error) {
    return archiveFailure(
      "invalid_coordination_projection",
      error instanceof Error ? error.message : "invalid coordination projection",
    );
  }
  const selection = selectCoordinationTodoArchive({
    role: input.role,
    max_active_done: input.max_active_done,
    todos: projection.todo_ids.map((todoId) => projection.todos.get(todoId)!),
  });
  const moved = selection.moved_todo_ids.map((todoId) => projection.todos.get(todoId)!);
  const updatedAt = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  const result: JsonObject = {
    role: selection.role,
    changed: moved.length > 0,
    active_done_before: selection.active_done_before,
    active_done_after: selection.active_done_after,
    max_active_done: selection.max_active_done,
    moved_count: selection.moved_count,
    moved_todo_ids: selection.moved_todo_ids,
    retained_standing_decision_count: selection.retained_standing_decision_count,
  };
  if (input.dry_run) {
    return {
      ...result,
      schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
      status: moved.length > 0 ? "planned" : "no_change",
      dry_run: true,
      provider_revision: head.provider_revision,
      cursor: head.cursor,
    };
  }
  if (moved.length === 0) {
    return {
      ...result,
      schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA,
      status: "no_change",
      dry_run: false,
      provider_revision: head.provider_revision,
      cursor: head.cursor,
    };
  }
  const mutations: CoordinationProjectionMutation[] = moved.map((todo) => ({
    kind: "todo_upsert",
    todo: {...todo, archive_state: "archive", updated_at: updatedAt},
  }));
  const commit: AuthorityStoreCommit = prepareCoordinationProjectionCommit({
    goal_id: input.goal_id,
    operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision,
    projection: head.head,
    mutations,
  });
  commit.receipts = [{
    schema_version: COORDINATION_TODO_ARCHIVE_RECEIPT_SCHEMA,
    operation_id: input.operation_id,
    goal_id: input.goal_id,
    request_sha256: requestSha,
    result,
  }];
  const committed = await store.commitAuthority(commit);
  const readback = replayArchive(
    await store.readReceipt(input.operation_id),
    input,
    requestSha,
    committed.status === "applied" ? "applied" : "recovered",
  );
  if (readback !== null) return readback;
  return committed.status === "applied"
    ? archiveFailure(
      "coordination_commit_readback_mismatch",
      "applied Todo archive mutation lacks its durable receipt",
    )
    : {schema_version: COORDINATION_TODO_ARCHIVE_RESULT_SCHEMA, ...committed, changed: false};
}
