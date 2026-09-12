import {leaseOwnerRejection as ownerRejection} from "./task_lease_eligibility.ts";
import { ShadowManagementError, requireShadowPrimaryWriteAllowed } from "../coordination/shadow_management.ts";
import { LegacyCoordinationWriteError, requireLegacyCoordinationPrimaryWriteAllowed } from "../coordination/legacy_writer_fence.ts";
import { createHash, randomUUID } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

import {
  EffectRuntimeConflictError,
  EffectRuntimeLockTimeoutError,
  EffectRuntimeRequestError,
  effectRuntimeErrorPayload,
} from "../effect_runtime_errors.ts";
import {
  acquireFileMutationLock,
  atomicWriteJson,
  claimFileMutationLock,
  mutationLockOwner,
  releaseFileMutationLock,
  releaseFileMutationLockClaim,
  withFileMutationLock,
  type FileMutationLock,
  type FileMutationLockClaim,
} from "../effect_runtime_io.ts";
import {
  legacyCoordinationLeaseLockPath,
} from "../coordination/legacy_writer_fence.ts";
import {
  settlementIdentity,
  type JsonObject,
} from "../effect_program.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import {
  decodeTaskLeaseAuthority,
  leaseEpoch,
  leaseInteger,
  leaseIsActive,
  leaseVersion,
  normalizeAgent,
  normalizeGoalId,
  normalizeIdempotencyKey,
  normalizeOwner,
  normalizeTodoId,
  normalizeTtl,
  readLease,
  revalidateAuthoritySources,
  TaskLeaseAcquireError,
  taskLeaseDirectory,
  taskLeaseLockPath,
  taskLeasePath,
  utcIsoformat,
  type AuthorityFacts,
  type LeaseRecord,
  type TodoFact,
  type TodoFactField,
} from "./task_lease_acquire.ts";
import {
  decideTaskLeaseLifecycle,
  type TaskLeaseLifecycleDecision,
  type TaskLeaseLifecycleDecisionInput,
} from "./task_lease_lifecycle_decision.ts";
import {
  beginLeaseOutboxEntry,
  decodeLocalAuthorityShadowBinding,
  type LeaseOutboxCapture,
  type LocalAuthorityShadowBinding,
} from "../coordination/local_authority_shadow_outbox.ts";
import { TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA } from "../coordination/coordination_state_contract.generated.ts";

export const TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION =
  TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA;
export const TASK_LEASE_LIFECYCLE_RECEIPT_SCHEMA =
  "task_lease_lifecycle_receipt_v0";
export const TASK_LEASE_FENCE_RECEIPT_SCHEMA = "task_lease_fence_receipt_v0";
export const TASK_LEASE_LIFECYCLE_OPERATIONS = [
  "renew",
  "transfer",
  "release",
  "terminal_verify",
  "holder_verify",
  "fence_close",
] as const;
export type TaskLeaseLifecycleOperation =
  (typeof TASK_LEASE_LIFECYCLE_OPERATIONS)[number];

type LifecycleStage = "validation" | "durable_writeback";

interface LifecycleRequest {
  schema_version: typeof TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION;
  operation: TaskLeaseLifecycleOperation;
  runtime_root: string;
  goal_id: string;
  todo_id: string;
  owner: string | null;
  idempotency_key: string | null;
  expected_version: number | null;
  ttl_seconds: number | null;
  new_owner: string | null;
  new_idempotency_key: string | null;
  authority: AuthorityFacts | null;
  todo: TodoFact | null;
  delegated_authority: boolean;
  allow_user_gate_auto_acquire: boolean;
  require_active_when_fence_supplied: boolean;
  lock_token: string | null;
  committed: boolean;
  release_lease: boolean;
  fence_owner: string | null;
  fence_idempotency_key: string | null;
  fence_expected_version: number | null;
  fence_expected_lease_epoch: number | null;
  fence_operation_id: string | null;
  current_time: Date | null;
  owner_pid: number | null;
  runtime_shadow: LocalAuthorityShadowBinding | null;
}

interface LifecycleDependencies {
  now?: () => Date;
  beforeWrite?: (lease: JsonObject) => void | Promise<void>;
}

interface LifecycleErrorInfo {
  code: string;
  message: string;
  payload: JsonObject;
  stage: LifecycleStage;
}

class TaskLeaseLifecycleError extends Error {
  readonly code: string;
  readonly payload: JsonObject;
  readonly stage: LifecycleStage;

  constructor(
    message: string,
    code: string,
    payload: JsonObject = {},
    stage: LifecycleStage = "validation",
  ) {
    super(message);
    this.name = "TaskLeaseLifecycleError";
    this.code = code;
    this.payload = payload;
    this.stage = stage;
  }
}

function compact(value: unknown): string {
  if (value === null || value === undefined) return "";
  const raw = typeof value === "string"
    ? value
    : typeof value === "number" || typeof value === "boolean"
      ? String(value)
      : "";
  return raw.trim().split(/\s+/u).filter(Boolean).join(" ");
}

function optionalInteger(value: unknown, label: string): number | null {
  if (value === null || value === undefined) return null;
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    throw new TaskLeaseLifecycleError(
      `${label} must be a non-negative safe integer or null`,
      "invalid_request",
    );
  }
  return value;
}

function optionalExpectedVersion(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new TaskLeaseLifecycleError(
      "expected_version must be a safe integer or null",
      "invalid_request",
    );
  }
  return value;
}

function optionalBoolean(
  value: unknown,
  label: string,
  defaultValue: boolean,
): boolean {
  if (value === undefined) return defaultValue;
  if (typeof value !== "boolean") {
    throw new TaskLeaseLifecycleError(
      `${label} must be a boolean when provided`,
      "invalid_request",
    );
  }
  return value;
}

function optionalPositiveInteger(value: unknown, label: string): number | null {
  if (value === undefined || value === null) return null;
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value <= 0
  ) {
    throw new TaskLeaseLifecycleError(
      `${label} must be a positive safe integer or null`,
      "invalid_request",
    );
  }
  return value;
}

function optionalDate(value: unknown, label: string): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") {
    throw new TaskLeaseLifecycleError(
      `${label} must be an ISO-8601 string or null`,
      "invalid_clock",
    );
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    throw new TaskLeaseLifecycleError(
      `${label} must be a valid ISO-8601 timestamp`,
      "invalid_clock",
    );
  }
  return parsed;
}

function optionalOwner(value: unknown, label: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  try {
    return normalizeOwner(value);
  } catch (error) {
    const message = error instanceof Error ? error.message : `${label} is invalid`;
    throw new TaskLeaseLifecycleError(message, "invalid_owner");
  }
}

function optionalKey(value: unknown, label: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  try {
    return normalizeIdempotencyKey(value);
  } catch (error) {
    const message = error instanceof Error ? error.message : `${label} is invalid`;
    throw new TaskLeaseLifecycleError(message, "invalid_idempotency_key");
  }
}

function optionalFenceOperationId(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (
    typeof value !== "string" ||
    !/^[a-f0-9]{64}$/u.test(value.trim())
  ) {
    throw new TaskLeaseLifecycleError(
      "fence_operation_id must be a 64-character lowercase hexadecimal token",
      "invalid_fence_operation_id",
    );
  }
  return value.trim();
}

function requiredOwner(value: unknown): string {
  const owner = optionalOwner(value, "owner");
  if (owner === null) {
    throw new TaskLeaseLifecycleError(
      "owner must be a public-safe agent id",
      "invalid_owner",
    );
  }
  return owner;
}

function requiredKey(value: unknown): string {
  const key = optionalKey(value, "idempotency_key");
  if (key === null) {
    throw new TaskLeaseLifecycleError(
      "idempotency key must be a public-safe token",
      "invalid_idempotency_key",
    );
  }
  return key;
}

function decodeTodo(
  value: unknown,
  fallback: TodoFact | null,
  expectedTodoId: string,
): TodoFact | null {
  if (value === null || value === undefined) return fallback;
  const record = requireJsonObject(value, "todo");
  let todoId: string;
  try {
    todoId = normalizeTodoId(record.todo_id);
  } catch (error) {
    throw new TaskLeaseLifecycleError(
      error instanceof Error ? error.message : "todo id is invalid",
      "invalid_todo_id",
    );
  }
  if (todoId !== expectedTodoId) {
    // A caller-supplied snapshot is only an elaboration of the authority
    // projection for this lease; it cannot silently authorize a sibling todo.
    throw new TaskLeaseLifecycleError(
      "todo does not match the task-lease identity",
      "todo_identity_mismatch",
      { expected_todo_id: expectedTodoId, actual_todo_id: todoId },
    );
  }
  const excludedRaw = record.excluded_agents;
  const excluded = Array.isArray(excludedRaw)
    ? excludedRaw
    : typeof excludedRaw === "string" ? excludedRaw.split(",") : [];
  // The legacy Python callers pass the active-state row, which can be a
  // partial compatibility view (for example it has no derived
  // ``task_class``). Preserve which fields were actually present so the
  // canonical projection can fill omitted metadata without turning an
  // otherwise valid request into a false authority mismatch. Explicitly
  // supplied fields remain strict below.
  const providedFields = [
    "status",
    "claimed_by",
    "excluded_agents",
    "role",
    "task_class",
    "bound_agent",
    "blocks_agent",
  ] as TodoFactField[];
  const presentFields = providedFields.filter((field) =>
    Object.hasOwn(record, field)
  );
  return {
    todo_id: todoId,
    status: compact(record.status).toLowerCase(),
    claimed_by: normalizeAgent(record.claimed_by),
    excluded_agents: [...new Set(
      excluded.map(normalizeAgent).filter((item): item is string => item !== null),
    )].sort((left, right) => left.localeCompare(right)),
    role: typeof record.role === "string" ? compact(record.role).toLowerCase() : undefined,
    task_class: typeof record.task_class === "string"
      ? compact(record.task_class).toLowerCase()
      : null,
    bound_agent: normalizeAgent(record.bound_agent),
    blocks_agent: normalizeAgent(record.blocks_agent),
    provided_fields: presentFields,
  };
}

function decodeOperation(value: unknown): TaskLeaseLifecycleOperation {
  if (
    typeof value !== "string" ||
    !TASK_LEASE_LIFECYCLE_OPERATIONS.includes(
      value as TaskLeaseLifecycleOperation,
    )
  ) {
    throw new TaskLeaseLifecycleError(
      "task-lease lifecycle operation is unsupported",
      "invalid_operation",
    );
  }
  return value as TaskLeaseLifecycleOperation;
}

function decodeRequest(value: unknown): LifecycleRequest {
  const input = requireJsonObject(value, "task lease lifecycle request");
  if (input.schema_version !== TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION) {
    throw new TaskLeaseLifecycleError(
      "Task-lease lifecycle request schema mismatch",
      "schema_mismatch",
    );
  }
  const operation = decodeOperation(input.operation);
  let goalId: string;
  let todoId: string;
  try {
    goalId = normalizeGoalId(input.goal_id);
    todoId = normalizeTodoId(input.todo_id);
  } catch (error) {
    const message = error instanceof Error ? error.message : "lease identity is invalid";
    const code = message.includes("todo id") ? "invalid_todo_id" : "invalid_goal_id";
    throw new TaskLeaseLifecycleError(message, code);
  }

  const ordinary = operation === "renew" || operation === "transfer" || operation === "release";
  const needsOwner = operation === "renew" || operation === "transfer" || operation === "release" || operation === "holder_verify";
  const owner = needsOwner ? requiredOwner(input.owner) : optionalOwner(input.owner, "owner");
  const idempotencyKey = ordinary ? requiredKey(input.idempotency_key) : optionalKey(input.idempotency_key, "idempotency_key");
  const expectedVersion = optionalExpectedVersion(input.expected_version);
  const ttlSeconds = operation === "renew" || operation === "transfer"
    ? normalizeTtl(input.ttl_seconds)
    : null;
  const newOwner = operation === "transfer" ? requiredOwner(input.new_owner) : optionalOwner(input.new_owner, "new_owner");
  const newKey = operation === "transfer" ? requiredKey(input.new_idempotency_key) : optionalKey(input.new_idempotency_key, "new_idempotency_key");

  let authority: AuthorityFacts | null = null;
  if (input.authority !== undefined && input.authority !== null) {
    authority = decodeTaskLeaseAuthority(input.authority);
  }
  if (
    (operation === "renew" || operation === "transfer" || operation === "terminal_verify" || operation === "holder_verify") &&
    authority === null
  ) {
    throw new TaskLeaseLifecycleError(
      "authority is required for this task-lease lifecycle operation",
      "authority_required",
    );
  }
  const fallbackTodo = authority?.todos.get(todoId) ?? null;
  const todo = decodeTodo(input.todo, fallbackTodo, todoId);
  if (
    (operation === "terminal_verify" || operation === "holder_verify") &&
    todo === null
  ) {
    throw new TaskLeaseLifecycleError(
      "todo is required for this task-lease fence operation",
      "todo_not_found",
    );
  }
  const fenceOwner = optionalOwner(input.fence_owner, "fence_owner");
  const fenceKey = optionalKey(input.fence_idempotency_key, "fence_idempotency_key");
  const fenceExpectedVersion = optionalInteger(
    input.fence_expected_version,
    "fence_expected_version",
  );
  const fenceExpectedLeaseEpoch = optionalInteger(
    input.fence_expected_lease_epoch,
    "fence_expected_lease_epoch",
  );
  const requestedFenceOperationId = optionalFenceOperationId(input.fence_operation_id);
  // Holder gates are lock-scoped proofs rather than caller-idempotent
  // mutations. A fresh native id prevents a later ownership update in the
  // same lease generation from colliding with an already closed gate receipt.
  const fenceOperationId = requestedFenceOperationId ?? (
    operation === "holder_verify"
      ? createHash("sha256").update(randomUUID(), "utf8").digest("hex")
      : null
  );
  const lockToken = input.lock_token === null || input.lock_token === undefined
    ? null
    : typeof input.lock_token === "string" &&
        input.lock_token.trim().length > 0 &&
        input.lock_token.length <= 256
      ? input.lock_token.trim()
      : (() => {
          throw new TaskLeaseLifecycleError(
            "lock_token must be a non-empty string of at most 256 characters",
            "invalid_lock_token",
          );
        })();
  return {
    schema_version: TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION,
    operation,
    runtime_root: typeof input.runtime_root === "string" ? input.runtime_root : (() => {
      throw new TaskLeaseLifecycleError("runtime_root must be a string", "invalid_runtime_root");
    })(),
    goal_id: goalId,
    todo_id: todoId,
    owner,
    idempotency_key: idempotencyKey,
    expected_version: expectedVersion,
    ttl_seconds: ttlSeconds,
    new_owner: newOwner,
    new_idempotency_key: newKey,
    authority,
    todo,
    delegated_authority: optionalBoolean(input.delegated_authority, "delegated_authority", false),
    allow_user_gate_auto_acquire: optionalBoolean(input.allow_user_gate_auto_acquire, "allow_user_gate_auto_acquire", false),
    require_active_when_fence_supplied: optionalBoolean(input.require_active_when_fence_supplied, "require_active_when_fence_supplied", true),
    lock_token: lockToken,
    committed: optionalBoolean(input.committed, "committed", false),
    release_lease: optionalBoolean(input.release_lease, "release_lease", false),
    fence_owner: fenceOwner,
    fence_idempotency_key: fenceKey,
    fence_expected_version: fenceExpectedVersion,
    fence_expected_lease_epoch: fenceExpectedLeaseEpoch,
    fence_operation_id: fenceOperationId,
    current_time: optionalDate(input.current_time, "current_time"),
    owner_pid: optionalPositiveInteger(input.owner_pid, "owner_pid"),
    runtime_shadow: decodeLocalAuthorityShadowBinding(input.runtime_shadow),
  };
}

async function captureLeaseWrite(
  request: LifecycleRequest,
  previous: LeaseRecord | null,
  next: LeaseRecord,
  writeClass: string,
): Promise<Awaited<ReturnType<typeof beginLeaseOutboxEntry>> | null> {
  if (request.runtime_shadow === null &&
      await requireShadowPrimaryWriteAllowed(request.runtime_root, request.goal_id) === null) return null;
  const capture = await beginLeaseOutboxEntry({
    runtime_root: request.runtime_root,
    goal_id: request.goal_id,
    lease_directory: taskLeaseDirectory(request),
    write_class: writeClass,
    operation_id: request.idempotency_key ?? request.fence_operation_id,
    previous_lease: previous,
    planned_lease: next,
  });
  if (capture.failure && await requireShadowPrimaryWriteAllowed(request.runtime_root, request.goal_id) !== null) {
    throw new ShadowManagementError("shadow_capture_prepare_failed", "durable shadow preparation failed; the primary lease was not changed");
  }
  return capture;
}

function attachRuntimeShadowCapture(
  response: JsonObject,
  capture: LeaseOutboxCapture | null,
): JsonObject {
  if (capture === null) return response;
  return {
    ...response,
    coordination_runtime_shadow_capture: {
      entry_id: capture.entry_id,
      seq: capture.seq,
      source_bytes_digest: capture.source_bytes_digest,
      failure: capture.failure,
      skipped_reason: capture.skipped_reason,
    },
  };
}

function lifecycleNow(
  request: LifecycleRequest,
  dependencies: LifecycleDependencies,
): Date {
  const at = dependencies.now?.() ?? request.current_time ?? new Date();
  if (Number.isNaN(at.valueOf())) {
    throw new TaskLeaseLifecycleError(
      "task-lease lifecycle clock returned an invalid date",
      "invalid_clock",
    );
  }
  return at;
}

function leasePathFor(request: Pick<LifecycleRequest, "runtime_root" | "goal_id" | "todo_id">): string {
  return taskLeasePath(request);
}

function lockPathFor(request: Pick<LifecycleRequest, "runtime_root" | "goal_id">): string {
  return taskLeaseLockPath(request);
}

function effectIdFor(request: LifecycleRequest): string | null {
  if (!request.owner || !request.idempotency_key) return null;
  return settlementIdentity({
    goal_id: request.goal_id,
    agent_id: request.owner,
    todo_id: request.todo_id,
    turn_instance_id: request.idempotency_key,
  }).effect_id;
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, child]) => [key, stableValue(child)]),
  );
}

function digest(value: unknown): string {
  return createHash("sha256")
    .update(JSON.stringify(stableValue(value)), "utf8")
    .digest("hex");
}

function operationIdentity(request: LifecycleRequest): string | null {
  if (!request.idempotency_key) return null;
  return digest({
    schema_version: TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION,
    operation: request.operation,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    owner: request.owner,
    idempotency_key: request.idempotency_key,
    expected_version: request.expected_version,
  });
}

function operationRequestDigest(request: LifecycleRequest): string | null {
  if (!request.idempotency_key) return null;
  return digest({
    schema_version: TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION,
    operation: request.operation,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    owner: request.owner,
    idempotency_key: request.idempotency_key,
    expected_version: request.expected_version,
    ttl_seconds: request.ttl_seconds,
    new_owner: request.new_owner,
    new_idempotency_key: request.new_idempotency_key,
  });
}

function operationReceiptPath(request: LifecycleRequest): string | null {
  const id = operationIdentity(request);
  if (!id) return null;
  return join(taskLeaseDirectory(request), ".lifecycle-operations", `${id}.json`);
}

function fenceOperationId(request: LifecycleRequest): string {
  if (request.fence_operation_id) return request.fence_operation_id;
  // A verify request has no durable caller-side handle until its response is
  // received.  Derive one from its execution identity so the managed runtime
  // can replay a response after a transport loss.  The close path normally
  // carries the returned id explicitly; its fallback is only for older
  // callers that know the verified lease tuple but not this bridge field.
  const verifyKind = request.operation === "fence_close"
    ? request.fence_idempotency_key === null ? "holder_verify" : "terminal_verify"
    : request.operation;
  return digest({
    schema_version: TASK_LEASE_FENCE_RECEIPT_SCHEMA,
    kind: verifyKind,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    owner: request.operation === "fence_close"
      ? request.fence_owner
      : request.owner,
    idempotency_key: request.operation === "fence_close"
      ? request.fence_idempotency_key
      : request.idempotency_key,
    expected_version: request.operation === "fence_close"
      ? request.fence_expected_version
      : request.expected_version,
    expected_lease_epoch: request.operation === "fence_close"
      ? request.fence_expected_lease_epoch
      : null,
  });
}

function fenceRequestDigest(request: LifecycleRequest): string {
  return digest({
    schema_version: TASK_LEASE_FENCE_RECEIPT_SCHEMA,
    operation: request.operation,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    owner: request.owner,
    idempotency_key: request.idempotency_key,
    expected_version: request.expected_version,
    delegated_authority: request.delegated_authority,
    allow_user_gate_auto_acquire: request.allow_user_gate_auto_acquire,
    require_active_when_fence_supplied: request.require_active_when_fence_supplied,
  });
}

function fenceCloseRequestDigest(request: LifecycleRequest): string {
  return digest({
    schema_version: TASK_LEASE_FENCE_RECEIPT_SCHEMA,
    operation: request.operation,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    lock_token: request.lock_token,
    committed: request.committed,
    release_lease: request.release_lease,
    fence_owner: request.fence_owner,
    fence_idempotency_key: request.fence_idempotency_key,
    fence_expected_version: request.fence_expected_version,
    fence_expected_lease_epoch: request.fence_expected_lease_epoch,
  });
}

function fenceReceiptPath(
  request: LifecycleRequest,
  operationId = fenceOperationId(request),
): string {
  return join(
    taskLeaseDirectory(request),
    ".lifecycle-fences",
    `${operationId}.json`,
  );
}

function fenceReceiptError(path: string, message: string): TaskLeaseLifecycleError {
  return new TaskLeaseLifecycleError(
    message,
    "corrupt_fence_receipt",
    { receipt_path: path },
    "validation",
  );
}

async function readFenceReceipt(
  path: string,
  request: LifecycleRequest | null = null,
): Promise<FenceReceipt | null> {
  try {
    const raw = JSON.parse(await readFile(path, "utf8"));
    const record = requireJsonObject(raw, "task lease fence receipt");
    const state = record.state;
    if (
      record.schema_version !== TASK_LEASE_FENCE_RECEIPT_SCHEMA ||
      typeof record.operation_id !== "string" ||
      !/^[a-f0-9]{64}$/u.test(record.operation_id) ||
      typeof record.request_digest !== "string" ||
      !/^[a-f0-9]{64}$/u.test(record.request_digest) ||
      (record.close_request_digest !== undefined &&
        record.close_request_digest !== null &&
        (typeof record.close_request_digest !== "string" ||
          !/^[a-f0-9]{64}$/u.test(record.close_request_digest))) ||
      !["acquired", "held", "closed"].includes(state as string) ||
      typeof record.goal_id !== "string" ||
      typeof record.todo_id !== "string" ||
      typeof record.owner_pid !== "number" ||
      !Number.isSafeInteger(record.owner_pid) ||
      record.owner_pid <= 0 ||
      typeof record.lock_token !== "string" ||
      record.lock_token.length === 0 ||
      (record.fence_owner !== undefined && record.fence_owner !== null &&
        typeof record.fence_owner !== "string") ||
      (record.fence_idempotency_key !== undefined &&
        record.fence_idempotency_key !== null &&
        typeof record.fence_idempotency_key !== "string") ||
      (record.fence_expected_version !== undefined &&
        record.fence_expected_version !== null &&
        (typeof record.fence_expected_version !== "number" ||
          !Number.isSafeInteger(record.fence_expected_version))) ||
      (record.fence_expected_lease_epoch !== undefined &&
        record.fence_expected_lease_epoch !== null &&
        (typeof record.fence_expected_lease_epoch !== "number" ||
          !Number.isSafeInteger(record.fence_expected_lease_epoch))) ||
      (record.lease !== undefined && record.lease !== null &&
        (typeof record.lease !== "object" || Array.isArray(record.lease))) ||
      (record.response !== undefined && record.response !== null &&
        (typeof record.response !== "object" || Array.isArray(record.response)))
      || (record.verify_response !== undefined &&
        record.verify_response !== null &&
        (typeof record.verify_response !== "object" ||
          Array.isArray(record.verify_response)))
    ) {
      throw fenceReceiptError(path, "task lease fence receipt is malformed");
    }
    const normalizedGoal = normalizeGoalId(record.goal_id);
    const normalizedTodo = normalizeTodoId(record.todo_id);
    if (normalizedGoal !== record.goal_id || normalizedTodo !== record.todo_id) {
      throw fenceReceiptError(path, "task lease fence receipt identity is not normalized");
    }
    if (request && (
      record.goal_id !== request.goal_id ||
      record.todo_id !== request.todo_id
    )) {
      throw fenceReceiptError(path, "task lease fence receipt identity does not match the request");
    }
    if (request && request.operation !== "fence_close" &&
        record.request_digest !== fenceRequestDigest(request)) {
      throw new TaskLeaseLifecycleError(
        "task lease fence operation id was reused with different verification parameters",
        "fence_operation_reuse",
        { receipt_path: path },
        "validation",
      );
    }
    if (request?.operation === "fence_close" &&
        record.close_request_digest !== undefined &&
        record.close_request_digest !== null &&
        record.close_request_digest !== fenceCloseRequestDigest(request)) {
      throw new TaskLeaseLifecycleError(
        "task lease fence close was retried with different parameters",
        "fence_operation_reuse",
        { receipt_path: path },
        "validation",
      );
    }
    const basename = path.split(/[\\/]/u).pop() ?? "";
    if (basename !== `${record.operation_id}.json`) {
      throw fenceReceiptError(path, "task lease fence receipt path does not match its operation id");
    }
    return {
      schema_version: TASK_LEASE_FENCE_RECEIPT_SCHEMA,
      operation_id: record.operation_id,
      request_digest: record.request_digest,
      close_request_digest: record.close_request_digest === undefined
        ? null
        : record.close_request_digest as string,
      state: state as FenceReceiptState,
      goal_id: record.goal_id,
      todo_id: record.todo_id,
      owner_pid: record.owner_pid,
      lock_token: record.lock_token,
      fence_owner: record.fence_owner === undefined
        ? null
        : record.fence_owner as string | null,
      fence_idempotency_key: record.fence_idempotency_key === undefined
        ? null
        : record.fence_idempotency_key as string | null,
      fence_expected_version: record.fence_expected_version === undefined
        ? null
        : record.fence_expected_version as number | null,
      fence_expected_lease_epoch: record.fence_expected_lease_epoch === undefined
        ? null
        : record.fence_expected_lease_epoch as number | null,
      lease: record.lease === undefined ? null : record.lease as LeaseRecord | null,
      response: record.response === undefined
        ? null
        : record.response as JsonObject | null,
      verify_response: record.verify_response === undefined
        ? null
        : record.verify_response as JsonObject | null,
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    if (error instanceof TaskLeaseLifecycleError) throw error;
    if (error instanceof SyntaxError) {
      throw fenceReceiptError(path, "task lease fence receipt is not valid JSON");
    }
    throw fenceReceiptError(path, "task lease fence receipt is malformed");
  }
}

async function persistFenceReceipt(
  request: LifecycleRequest,
  state: FenceReceiptState,
  lockToken: string,
  options: {
    lease: LeaseRecord | null;
    response: JsonObject | null;
    operationId?: string;
    requestDigest?: string;
    ownerPid?: number;
    fenceOwner?: string | null;
    fenceIdempotencyKey?: string | null;
    fenceExpectedVersion?: number | null;
    fenceExpectedLeaseEpoch?: number | null;
    verifyResponse?: JsonObject | null;
    closeRequestDigest?: string | null;
    base?: FenceReceipt | null;
  },
): Promise<void> {
  const operationId = options.operationId ?? fenceOperationId(request);
  const base = options.base;
  const choose = <T>(
    value: T | undefined,
    fallback: T | null | undefined,
  ): T | null => value !== undefined ? value : fallback ?? null;
  const verifyResponse = options.verifyResponse !== undefined
    ? options.verifyResponse
    : base?.verify_response ?? (
      state === "held"
        ? options.response
        : state === "closed" &&
            base?.response !== null &&
            base?.response !== undefined &&
            base.response.action !== "fence_close"
          ? base.response
          : null
    );
  const closeRequestDigest = options.closeRequestDigest !== undefined
    ? options.closeRequestDigest
    : state === "held"
      ? null
      : base?.close_request_digest ?? null;
  await atomicWriteJson(fenceReceiptPath(request, operationId), {
    schema_version: TASK_LEASE_FENCE_RECEIPT_SCHEMA,
    operation_id: operationId,
    request_digest: options.requestDigest ?? base?.request_digest ?? fenceRequestDigest(request),
    close_request_digest: closeRequestDigest,
    state,
    goal_id: base?.goal_id ?? request.goal_id,
    todo_id: base?.todo_id ?? request.todo_id,
    owner_pid: options.ownerPid ?? base?.owner_pid ?? request.owner_pid ?? process.pid,
    lock_token: lockToken,
    fence_owner: choose(options.fenceOwner, base?.fence_owner),
    fence_idempotency_key: choose(options.fenceIdempotencyKey, base?.fence_idempotency_key),
    fence_expected_version: choose(options.fenceExpectedVersion, base?.fence_expected_version),
    fence_expected_lease_epoch: choose(options.fenceExpectedLeaseEpoch, base?.fence_expected_lease_epoch),
    lease: options.lease,
    response: options.response,
    verify_response: verifyResponse,
  });
}

function fenceLockHandle(
  request: LifecycleRequest,
  token: string,
): FileMutationLock {
  const targetPath = lockPathFor(request);
  return {
    targetPath,
    lockPath: `${targetPath}.ts-effect.lock`,
    token,
  };
}

async function adoptFenceReceiptLock(
  request: LifecycleRequest,
  receipt: FenceReceipt | null,
): Promise<FileMutationLock | null> {
  if (!receipt || receipt.state === "closed") return null;
  const owner = await mutationLockOwner(lockPathFor(request));
  if (!owner || owner.token !== receipt.lock_token) return null;
  const expectedPid = request.owner_pid ?? process.pid;
  if (owner.pid !== expectedPid || receipt.owner_pid !== expectedPid) return null;
  return fenceLockHandle(request, receipt.lock_token);
}


async function findFenceReceiptByToken(
  request: LifecycleRequest,
): Promise<{ path: string; receipt: FenceReceipt } | null> {
  const directory = join(taskLeaseDirectory(request), ".lifecycle-fences");
  let names: string[];
  try {
    names = await readdir(directory);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  const matches: Array<{ path: string; receipt: FenceReceipt }> = [];
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const path = join(directory, name);
    const receipt = await readFenceReceipt(path);
    if (
      receipt &&
      receipt.goal_id === request.goal_id &&
      receipt.todo_id === request.todo_id &&
      receipt.lock_token === request.lock_token
    ) {
      matches.push({ path, receipt });
    }
  }
  if (matches.length > 1) {
    throw fenceReceiptError(
      directory,
      "multiple task lease fence receipts match the lock token",
    );
  }
  return matches[0] ?? null;
}

function fenceLeaseMatchesReceipt(
  lease: LeaseRecord | null,
  receipt: FenceReceipt | null,
): boolean {
  if (!lease || !receipt) return false;
  try {
    return (
      receipt.fence_owner !== null &&
      persistedOwner(lease) === receipt.fence_owner &&
      receipt.fence_expected_version !== null &&
      leaseVersion(lease) === receipt.fence_expected_version &&
      receipt.fence_expected_lease_epoch !== null &&
      leaseEpoch(lease) === receipt.fence_expected_lease_epoch &&
      (receipt.fence_idempotency_key === null ||
        persistedKey(lease) === receipt.fence_idempotency_key)
    );
  } catch {
    return false;
  }
}

function fenceVerificationResponse(
  receipt: FenceReceipt | null,
): JsonObject | null {
  if (!receipt) return null;
  if (receipt.verify_response) return receipt.verify_response;
  // Receipts written by the first native version stored the verification
  // payload directly in `response` while the fence was held. Preserve that
  // read-only compatibility shape, but never treat a close response as proof.
  if (receipt.state === "held" && receipt.response?.action !== "fence_close") {
    return receipt.response;
  }
  return null;
}

function isVerifiedHeldFence(receipt: FenceReceipt | null): boolean {
  if (!receipt || receipt.state !== "held") return false;
  const verification = fenceVerificationResponse(receipt);
  if (!verification || verification.lock_token !== receipt.lock_token) return false;
  return verification.active === true && (
    verification.execution_instance_verified === true ||
    verification.checked === true
  );
}

interface OperationReceipt extends JsonObject {
  schema_version: typeof TASK_LEASE_LIFECYCLE_RECEIPT_SCHEMA;
  operation_id: string;
  request_digest: string;
  state: "prepared" | "committed";
  planned_lease: LeaseRecord | null;
  response: JsonObject;
}

type FenceReceiptState = "acquired" | "held" | "closed";

interface FenceReceipt extends JsonObject {
  schema_version: typeof TASK_LEASE_FENCE_RECEIPT_SCHEMA;
  operation_id: string;
  request_digest: string;
  close_request_digest: string | null;
  state: FenceReceiptState;
  goal_id: string;
  todo_id: string;
  owner_pid: number;
  lock_token: string;
  fence_owner: string | null;
  fence_idempotency_key: string | null;
  fence_expected_version: number | null;
  fence_expected_lease_epoch: number | null;
  lease: LeaseRecord | null;
  response: JsonObject | null;
  verify_response: JsonObject | null;
}

function corruptLease(
  message: string,
  leasePath: string,
  details: JsonObject = {},
): TaskLeaseLifecycleError {
  return new TaskLeaseLifecycleError(
    message,
    "corrupt_lease",
    { lease_path: leasePath, ...details },
    "validation",
  );
}

/**
 * Validate only the persisted fields that lifecycle CAS depends on.  The
 * record codec intentionally keeps unknown fields untouched so older lease
 * producers remain readable, while malformed identity/generation fields fail
 * closed before any lifecycle write.
 */
function validatePersistedLease(
  lease: LeaseRecord,
  request: LifecycleRequest,
  leasePath: string,
): LeaseRecord {
  if (lease.schema_version !== "task_lease_v0") {
    throw corruptLease("lease record schema is unsupported", leasePath, {
      schema_version: lease.schema_version ?? null,
    });
  }
  if (typeof lease.goal_id !== "string" || lease.goal_id !== request.goal_id) {
    throw corruptLease("lease record goal identity does not match the request", leasePath, {
      goal_id: lease.goal_id ?? null,
      expected_goal_id: request.goal_id,
    });
  }
  if (typeof lease.todo_id !== "string" || lease.todo_id !== request.todo_id) {
    throw corruptLease("lease record todo identity does not match the request", leasePath, {
      todo_id: lease.todo_id ?? null,
      expected_todo_id: request.todo_id,
    });
  }
  try {
    normalizeOwner(lease.owner);
  } catch {
    throw corruptLease("lease record owner is invalid", leasePath, {
      owner: lease.owner ?? null,
    });
  }
  try {
    normalizeIdempotencyKey(lease.idempotency_key);
  } catch {
    throw corruptLease("lease record idempotency key is invalid", leasePath);
  }
  if (lease.status !== "active" && lease.status !== "released") {
    throw corruptLease("lease record status is invalid", leasePath, {
      status: lease.status ?? null,
    });
  }
  // These helpers reject bools, fractional values, and negative generations,
  // while preserving the legacy defaults (version 0, epoch 1).
  try {
    leaseVersion(lease);
    leaseEpoch(lease);
  } catch (error) {
    if (error instanceof TaskLeaseAcquireError) {
      throw corruptLease(error.message, leasePath, error.payload);
    }
    throw error;
  }
  if (lease.write_scopes !== undefined) {
    if (!Array.isArray(lease.write_scopes) || lease.write_scopes.some((scope) => typeof scope !== "string")) {
      throw corruptLease("lease record write_scopes must be an array of strings", leasePath);
    }
  }
  return lease;
}

function persistedOwner(lease: LeaseRecord): string {
  try {
    return normalizeOwner(lease.owner);
  } catch {
    throw new TaskLeaseLifecycleError(
      "lease record owner is invalid",
      "corrupt_lease",
      { owner: lease.owner ?? null },
      "validation",
    );
  }
}

function persistedKey(lease: LeaseRecord): string {
  try {
    return normalizeIdempotencyKey(lease.idempotency_key);
  } catch {
    throw new TaskLeaseLifecycleError(
      "lease record idempotency key is invalid",
      "corrupt_lease",
      {},
      "validation",
    );
  }
}

async function readOperationReceipt(
  path: string | null,
  request: LifecycleRequest,
  leasePath: string,
): Promise<OperationReceipt | null> {
  if (!path) return null;
  try {
    const raw = JSON.parse(await readFile(path, "utf8"));
    let record: JsonObject;
    try {
      record = requireJsonObject(raw, "task lease lifecycle receipt");
    } catch {
      throw new TaskLeaseLifecycleError(
        "task lease lifecycle receipt root must be a JSON object",
        "corrupt_lifecycle_receipt",
        { receipt_path: path },
        "validation",
      );
    }
    const expectedOperationId = operationIdentity(request);
    const expectedRequestDigest = operationRequestDigest(request);
    if (
      record.schema_version !== TASK_LEASE_LIFECYCLE_RECEIPT_SCHEMA ||
      typeof record.operation_id !== "string" ||
      !/^[a-f0-9]{64}$/u.test(record.operation_id) ||
      record.operation_id !== expectedOperationId ||
      typeof record.request_digest !== "string" ||
      !/^[a-f0-9]{64}$/u.test(record.request_digest) ||
      (record.state !== "prepared" && record.state !== "committed") ||
      (record.planned_lease !== null &&
        (typeof record.planned_lease !== "object" ||
          Array.isArray(record.planned_lease))) ||
      record.planned_lease === null ||
      typeof record.response !== "object" || record.response === null || Array.isArray(record.response)
    ) {
      throw new TaskLeaseLifecycleError(
        "task lease lifecycle receipt is malformed",
        "corrupt_lifecycle_receipt",
        { receipt_path: path },
        "validation",
      );
    }
    let plannedLease: LeaseRecord;
    try {
      plannedLease = validatePersistedLease(
        record.planned_lease as LeaseRecord,
        request,
        leasePath,
      );
    } catch (error) {
      if (error instanceof TaskLeaseLifecycleError && error.code === "corrupt_lease") {
        throw new TaskLeaseLifecycleError(
          "task lease lifecycle receipt contains an invalid planned lease",
          "corrupt_lifecycle_receipt",
          { receipt_path: path },
          "validation",
        );
      }
      throw error;
    }
    const response = record.response as JsonObject;
    if (
      response.ok !== true ||
      response.schema_version !== "task_lease_v0" ||
      response.action !== request.operation ||
      typeof response.lease !== "object" ||
      response.lease === null ||
      Array.isArray(response.lease) ||
      !plannedLeaseMatches(response.lease as LeaseRecord, plannedLease)
    ) {
      throw new TaskLeaseLifecycleError(
        "task lease lifecycle receipt response is malformed",
        "corrupt_lifecycle_receipt",
        { receipt_path: path },
        "validation",
      );
    }
    return {
      schema_version: TASK_LEASE_LIFECYCLE_RECEIPT_SCHEMA,
      operation_id: record.operation_id,
      request_digest: record.request_digest,
      state: record.state,
      planned_lease: plannedLease,
      response,
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    if (error instanceof TaskLeaseLifecycleError) throw error;
    if (error instanceof SyntaxError) {
      throw new TaskLeaseLifecycleError(
        "task lease lifecycle receipt is not valid JSON",
        "corrupt_lifecycle_receipt",
        { receipt_path: path },
        "validation",
      );
    }
    if ((error as NodeJS.ErrnoException).code) throw error;
    throw new TaskLeaseLifecycleError(
      "task lease lifecycle receipt is malformed",
      "corrupt_lifecycle_receipt",
      { receipt_path: path },
      "validation",
    );
  }
}

function lifecycleSettlement(
  request: LifecycleRequest,
  status: "committed" | "replayed",
  failure?: LifecycleErrorInfo,
): JsonObject {
  const effectId = effectIdFor(request);
  const result: JsonObject = {
    effect_id: effectId,
    receipts: effectId
      ? [{ step: "validation", status, effect_id: effectId }]
      : [],
  };
  if (failure) {
    result.failure = {
      step: failure.stage,
      kind: failure.code === "invalid_owner" || failure.code === "invalid_idempotency_key"
        ? "invalid_identity"
        : failure.stage === "validation" ? "permission_denied" : "writeback_rejected",
      code: failure.code,
    };
  } else if (status === "committed") {
    if (effectId) {
      (result.receipts as JsonObject[]).push({
        step: "durable_writeback",
        status,
        effect_id: effectId,
      });
    }
  }
  return result;
}

function failureEnvelope(
  request: Partial<LifecycleRequest> | null,
  error: LifecycleErrorInfo,
): JsonObject {
  const effectId = request && request.owner && request.idempotency_key
    ? effectIdFor(request as LifecycleRequest)
    : null;
  return {
    ok: false,
    schema_version: "task_lease_v0",
    action: request?.operation ?? "unknown",
    error: error.message,
    error_code: error.code,
    ...(request?.runtime_root && request.goal_id && request.todo_id
      ? { lease_path: leasePathFor(request as LifecycleRequest) }
      : {}),
    ...error.payload,
    settlement: {
      effect_id: effectId,
      receipts: effectId && error.stage !== "validation"
        ? [{ step: "validation", status: "committed", effect_id: effectId }]
        : [],
      failure: {
        step: error.stage,
        kind: error.code === "invalid_owner" || error.code === "invalid_idempotency_key"
          ? "invalid_identity"
          : error.stage === "validation" ? "permission_denied" : "writeback_rejected",
        code: error.code,
      },
    },
  };
}

function failureRequestContext(value: unknown): Partial<LifecycleRequest> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const input = value as Record<string, unknown>;
  const operation = typeof input.operation === "string" &&
      TASK_LEASE_LIFECYCLE_OPERATIONS.includes(
        input.operation as TaskLeaseLifecycleOperation,
      )
    ? input.operation as TaskLeaseLifecycleOperation
    : undefined;
  return operation === undefined ? null : { operation };
}

function errorInfo(error: unknown, fallbackStage: LifecycleStage = "durable_writeback"): LifecycleErrorInfo {
  if (error instanceof ShadowManagementError || error instanceof LegacyCoordinationWriteError) {
    return {code: error.code, message: error.message, payload: error.payload, stage: "validation"};
  }
  if (error instanceof TaskLeaseLifecycleError) {
    return {
      code: error.code,
      message: error.message,
      payload: error.payload,
      stage: error.stage,
    };
  }
  if (error instanceof EffectRuntimeLockTimeoutError) {
    return {
      code: "lock_acquire_timeout",
      message: "task lease mutation lock timed out",
      payload: {},
      stage: "validation",
    };
  }
  if (error instanceof EffectRuntimeRequestError) {
    return {
      code: error.code,
      message: error.message,
      payload: {},
      stage: "validation",
    };
  }
  if (error instanceof EffectRuntimeConflictError) {
    return {
      code: error.code,
      message: error.message,
      payload: {},
      stage: "validation",
    };
  }
  if (error instanceof TaskLeaseAcquireError) {
    return {
      code: error.code,
      message: error.message,
      payload: error.payload,
      stage: "validation",
    };
  }
  const payload = effectRuntimeErrorPayload(error);
  return {
    code: payload.code,
    message: payload.message,
    payload: {},
    stage: fallbackStage,
  };
}

function authorityTodo(
  request: LifecycleRequest,
): TodoFact | null {
  if (request.authority?.todo_projection_error) {
    const error = request.authority.todo_projection_error;
    throw new TaskLeaseLifecycleError(
      error.message,
      error.code,
      error.payload,
      "validation",
    );
  }
  const projected = request.authority?.todos.get(request.todo_id) ?? null;
  if (request.todo && projected && !todoFactsMatch(request.todo, projected)) {
    throw new TaskLeaseLifecycleError(
      "caller todo snapshot disagrees with the canonical authority projection",
      "authority_todo_mismatch",
      { goal_id: request.goal_id, todo_id: request.todo_id },
      "validation",
    );
  }
  // The authority projection is the only authorization source.  A caller
  // supplied Todo can elaborate it, but cannot create an otherwise missing
  // row or override its state.
  return projected;
}

function todoFactsMatch(left: TodoFact, right: TodoFact): boolean {
  const provided = left.provided_fields;
  // Lifecycle authority depends on the core identity/state fields.  They are
  // required by the compact caller contract and remain strict even when an
  // older producer omitted optional metadata.  The latter can be derived by
  // the canonical projection, so absence is treated as "unspecified".
  const matchesOptional = (field: TodoFactField, equal: boolean): boolean =>
    provided === undefined || provided.includes(field) ? equal : true;
  return left.todo_id === right.todo_id &&
    left.status === right.status &&
    left.claimed_by === right.claimed_by &&
    JSON.stringify(left.excluded_agents) === JSON.stringify(right.excluded_agents) &&
    matchesOptional("role", (left.role ?? null) === (right.role ?? null)) &&
    matchesOptional("task_class", (left.task_class ?? null) === (right.task_class ?? null)) &&
    matchesOptional("bound_agent", left.bound_agent === right.bound_agent) &&
    matchesOptional("blocks_agent", left.blocks_agent === right.blocks_agent);
}

function ownerError(
  request: LifecycleRequest,
  code: string,
  todo: TodoFact | null,
  owner = request.owner,
): TaskLeaseLifecycleError {
  let message: string;
  const payload: JsonObject = {
    goal_id: request.goal_id,
    todo_id: request.todo_id,
    owner,
    reason: code,
  };
  if (code === "todo_not_found") message = "todo is missing from the canonical projection";
  else if (code === "todo_not_open") {
    payload.todo_status = todo?.status || "unknown";
    message = `task lease requires an open todo; '${request.todo_id}' is '${payload.todo_status}'`;
  } else if (code === "owner_excluded_from_todo") {
    payload.excluded_agents = [...(todo?.excluded_agents ?? [])];
    message = `task lease owner '${owner}' is excluded from todo '${request.todo_id}'`;
  } else if (code === "owner_conflicts_with_claim") {
    payload.claimed_by = todo?.claimed_by ?? null;
    message = `task lease owner '${owner}' conflicts with todo claim '${payload.claimed_by}'`;
  } else {
    message = `task lease owner '${owner}' is not registered for goal '${request.goal_id}'`;
  }
  return new TaskLeaseLifecycleError(message, code, payload, "validation");
}

function transitionError(
  request: LifecycleRequest,
  code: string,
  lease: LeaseRecord | null,
  leasePath: string,
): TaskLeaseLifecycleError {
  let message: string;
  let payload: JsonObject = { lease, lease_path: leasePath };
  if (code === "version_required") {
    message = `task lease ${request.operation} requires the current lease version`;
    payload = { action: request.operation };
  } else if (code === "version_mismatch") {
    const actual = leaseVersion(lease);
    message = `lease version mismatch: expected ${request.expected_version}, got ${actual}`;
    payload = { expected_version: request.expected_version, actual_version: actual };
  } else if (code === "lease_not_active") {
    message = "lease is missing or expired";
    payload = {};
  } else if (code === "lease_cas_mismatch") {
    message = "lease owner or idempotency key mismatch";
    payload = {};
  } else if (code === "idempotency_key_reuse") {
    message = request.operation === "transfer"
      ? "lease transfer must mint a new execution idempotency key"
      : "idempotency key was reused with different lifecycle parameters";
  } else if (code === "handoff_mode_forbids_lease") {
    message = `goal handoff mode 'soft_claim' forbids task lease ${request.operation}; release and inspect remain available for legacy leftovers`;
    payload = {
      goal_id: request.goal_id,
      todo_id: request.todo_id,
      action: request.operation,
      handoff_mode: request.authority?.handoff_mode,
    };
  } else {
    message = `task lease ${request.operation} rejected by authority core: ${code}`;
  }
  return new TaskLeaseLifecycleError(message, code, payload, "validation");
}

function releasedLease(lease: LeaseRecord, at: Date): LeaseRecord {
  return {
    ...lease,
    lease_epoch: leaseEpoch(lease),
    status: "released",
    released_at: utcIsoformat(at),
    updated_at: utcIsoformat(at),
  };
}

function responseForOrdinary(
  request: LifecycleRequest,
  leasePath: string,
  lease: LeaseRecord | null,
  idempotent: boolean,
  actionValue: JsonObject,
): JsonObject {
  return {
    ok: true,
    schema_version: "task_lease_v0",
    action: request.operation,
    ...actionValue,
    ...(lease === null ? {} : { lease }),
    lease_path: leasePath,
    ...(request.authority?.handoff_mode ? { handoff_mode: request.authority.handoff_mode } : {}),
    ...(idempotent ? { idempotent: true } : { idempotent: false }),
    settlement: lifecycleSettlement(request, idempotent ? "replayed" : "committed"),
  };
}

function plannedLeaseMatches(actual: LeaseRecord | null, planned: LeaseRecord | null): boolean {
  if (actual === null || planned === null) return actual === planned;
  return JSON.stringify(stableValue(actual)) === JSON.stringify(stableValue(planned));
}

function allowsUserGateAutoAcquire(
  request: LifecycleRequest,
  todo: TodoFact | null,
): boolean {
  return request.operation === "terminal_verify" &&
    request.authority?.handoff_mode === "hard_lease" &&
    !request.delegated_authority &&
    request.allow_user_gate_auto_acquire &&
    todo?.role === "user" &&
    todo.task_class === "user_gate";
}

async function loadLeaseForRequest(
  request: LifecycleRequest,
  leasePath: string,
): Promise<LeaseRecord | null> {
  const lease = await readLease(leasePath);
  return lease === null ? null : validatePersistedLease(lease, request, leasePath);
}

async function persistOperationReceipt(
  request: LifecycleRequest,
  state: OperationReceipt["state"],
  plannedLease: LeaseRecord | null,
  response: JsonObject,
): Promise<void> {
  const path = operationReceiptPath(request);
  const operationId = operationIdentity(request);
  const requestDigest = operationRequestDigest(request);
  if (!path || !operationId || !requestDigest) return;
  await atomicWriteJson(path, {
    schema_version: TASK_LEASE_LIFECYCLE_RECEIPT_SCHEMA,
    operation_id: operationId,
    request_digest: requestDigest,
    state,
    planned_lease: plannedLease,
    response,
  });
}

function ordinaryDecision(
  request: LifecycleRequest,
  lease: LeaseRecord | null,
  todo: TodoFact | null,
  at: Date,
): TaskLeaseLifecycleDecision {
  const input: TaskLeaseLifecycleDecisionInput = {
    handoff_mode: request.authority?.handoff_mode ?? "legacy",
    registered_agents: request.authority?.registered_agents ?? [],
    todo: todo === null
      ? null
      : {
          todo_id: todo.todo_id,
          status: todo.status,
          claimed_by: todo.claimed_by,
          excluded_agents: todo.excluded_agents,
        },
    lease: lease === null
      ? null
      : {
          present: true,
          active: leaseIsActive(lease, at),
          status: typeof lease.status === "string" ? lease.status : null,
          owner: persistedOwner(lease),
          idempotency_key: persistedKey(lease),
          version: leaseVersion(lease),
          lease_epoch: leaseEpoch(lease),
          write_scopes: Array.isArray(lease.write_scopes)
            ? lease.write_scopes.filter((scope): scope is string =>
                typeof scope === "string"
              )
            : [],
          // Lifecycle decisions do not depend on the original acquire TTL.
          // Legacy records may carry an unrelated malformed value here; keep
          // that compatibility field out of the decision instead of turning
          // renew/release into a new validation surface.
          acquire_ttl_seconds:
            typeof lease.acquire_ttl_seconds === "number" &&
              Number.isSafeInteger(lease.acquire_ttl_seconds) &&
              lease.acquire_ttl_seconds >= 0
              ? lease.acquire_ttl_seconds
              : null,
        },
    command: {
      operation: request.operation as "renew" | "transfer" | "release",
      owner: request.owner!,
      idempotency_key: request.idempotency_key!,
      expected_version: request.expected_version,
      ttl_seconds: request.ttl_seconds,
      new_owner: request.new_owner,
      new_idempotency_key: request.new_idempotency_key,
    },
  };
  return decideTaskLeaseLifecycle(input);
}

async function ordinaryOperation(
  request: LifecycleRequest,
  dependencies: LifecycleDependencies,
): Promise<JsonObject> {
  const leasePath = leasePathFor(request);
  const operationPath = operationReceiptPath(request);
  const requestDigest = operationRequestDigest(request);
  const at = lifecycleNow(request, dependencies);

  // Preserve the legacy facade's diagnostic ordering.  Handoff policy and
  // required CAS version are request-level gates, so they must win over lease
  // file/receipt errors (and over an optional replay read) just as they did in
  // the Python writer.
  if (request.operation !== "release") {
    if (!request.authority) {
      throw new TaskLeaseLifecycleError("authority is required", "authority_required");
    }
    if (request.authority.handoff_mode === "soft_claim") {
      throw transitionError(request, "handoff_mode_forbids_lease", null, leasePath);
    }
  }
  if (request.expected_version === null) {
    throw transitionError(request, "version_required", null, leasePath);
  }

  const existing = await loadLeaseForRequest(request, leasePath);
  const existingReceipt = await readOperationReceipt(
    operationPath,
    request,
    leasePath,
  );
  if (existingReceipt && requestDigest && existingReceipt.request_digest !== requestDigest) {
    throw new TaskLeaseLifecycleError(
      "idempotency key was reused with different lifecycle parameters",
      "idempotency_key_reuse",
      { lease_path: leasePath },
      "validation",
    );
  }

  // A committed receipt is authoritative for this operation identity.  A
  // divergent lease means an external writer or partial repair changed state;
  // retrying the mutation would risk a second generation.
  if (existingReceipt?.state === "committed" &&
      !plannedLeaseMatches(existing, existingReceipt.planned_lease)) {
    throw new TaskLeaseLifecycleError(
      "task-lease lifecycle receipt does not match the persisted lease",
      "lifecycle_receipt_state_mismatch",
      { lease_path: leasePath },
      "durable_writeback",
    );
  }

  if (existingReceipt?.state === "committed") {
    const replay: JsonObject = { ...existingReceipt.response, idempotent: true };
    replay.settlement = lifecycleSettlement(request, "replayed");
    return replay;
  }
  if (existingReceipt?.state === "prepared" && plannedLeaseMatches(existing, existingReceipt.planned_lease)) {
    const replay: JsonObject = { ...existingReceipt.response, idempotent: true };
    replay.settlement = lifecycleSettlement(request, "replayed");
    await persistOperationReceipt(request, "committed", existingReceipt.planned_lease, replay);
    return replay;
  }

  let todo: TodoFact | null = null;
  if (request.operation !== "release") {
    const authority = request.authority;
    if (!authority) throw new TaskLeaseLifecycleError("authority is required", "authority_required");
    await revalidateAuthoritySources(authority.source_receipts);
    todo = authorityTodo(request);
  }
  const decision = ordinaryDecision(request, existing, todo, at);
  if (decision.outcome === "conflict" || decision.outcome === "rejected") {
    if (
      decision.code === "todo_not_found" ||
      decision.code === "todo_not_open" ||
      decision.code === "owner_not_registered" ||
      decision.code === "owner_excluded_from_todo" ||
      decision.code === "owner_conflicts_with_claim"
    ) {
      const rejectedOwner = request.operation === "transfer" &&
          decision.code === "owner_not_registered" &&
          !request.authority?.registered_agents.includes(request.owner!)
        ? request.owner
        : request.operation === "transfer" ? request.new_owner : request.owner;
      throw ownerError(request, decision.code, todo, rejectedOwner);
    }
    throw transitionError(request, decision.code, existing, leasePath);
  }

  if (request.operation === "release") {
    if (decision.code === "lease_missing") {
      return {
        ok: true,
        schema_version: "task_lease_v0",
        action: "release",
        released: false,
        missing: true,
        lease_path: leasePath,
        ...(request.authority?.handoff_mode
          ? { handoff_mode: request.authority.handoff_mode }
          : {}),
        settlement: lifecycleSettlement(request, "committed"),
      };
    }
    if (decision.code === "lease_release_replay" && existing !== null) {
      return responseForOrdinary(request, leasePath, existing, true, { released: true });
    }
    if (existing === null || decision.next_lease === null) {
      throw transitionError(request, "invalid_lease_snapshot", existing, leasePath);
    }
    const next = releasedLease(existing, at);
    const response = responseForOrdinary(request, leasePath, next, false, { released: true });
    await persistOperationReceipt(request, "prepared", next, response);
    await dependencies.beforeWrite?.(next);
    const shadowCapture = await captureLeaseWrite(
      request, existing, next, "task_lease_release",
    );
    await atomicWriteJson(leasePath, next);
    await shadowCapture?.commit();
    await persistOperationReceipt(request, "committed", next, response);
    return attachRuntimeShadowCapture(response, shadowCapture);
  }
  if (existing === null || decision.next_lease === null) {
    throw transitionError(request, "invalid_lease_snapshot", existing, leasePath);
  }
  const decidedLease = decision.next_lease;
  const next: LeaseRecord = {
    ...existing,
    ...(request.operation === "transfer"
      ? {
          owner: decidedLease.owner,
          idempotency_key: decidedLease.idempotency_key,
          lease_epoch: decidedLease.lease_epoch,
        }
      : {}),
    version: decidedLease.version,
    updated_at: utcIsoformat(at),
    expires_at: utcIsoformat(new Date(at.valueOf() + (request.ttl_seconds ?? 0) * 1_000)),
  };
  const response = responseForOrdinary(
    request,
    leasePath,
    next,
    false,
    request.operation === "renew" ? { renewed: true } : { transferred: true },
  );
  await persistOperationReceipt(request, "prepared", next, response);
  await dependencies.beforeWrite?.(next);
  if (request.authority) await revalidateAuthoritySources(request.authority.source_receipts);
  const shadowCapture = await captureLeaseWrite(
    request, existing, next, `task_lease_${request.operation}`,
  );
  await atomicWriteJson(leasePath, next);
  await shadowCapture?.commit();
  await persistOperationReceipt(request, "committed", next, response);
  return attachRuntimeShadowCapture(response, shadowCapture);
}

function fencePayload(
  request: LifecycleRequest,
  lease: LeaseRecord,
  token: string,
  autoAcquired = false,
): JsonObject {
  return {
    schema_version: "task_lease_v0",
    required: true,
    active: true,
    owner: request.owner,
    version: leaseVersion(lease),
    lease_epoch: leaseEpoch(lease),
    execution_instance_verified: true,
    lock_token: token,
    fence_operation_id: fenceOperationId(request),
    ...(autoAcquired ? { auto_acquired: true } : {}),
  };
}

async function fenceVerify(
  request: LifecycleRequest,
  dependencies: LifecycleDependencies,
): Promise<JsonObject> {
  if (!request.authority) {
    throw new TaskLeaseLifecycleError("authority is required for a fence", "authority_required");
  }
  const operationId = fenceOperationId(request);
  const receiptPath = fenceReceiptPath(request, operationId);
  let keep = false;
  let recheckingClosedNoop = false;
  let receipt = await readFenceReceipt(receiptPath, request);
  let lock: FileMutationLock | null = null;
  let lockClaim: FileMutationLockClaim | null = null;
  try {
    // A closed receipt is terminal only relative to the lease generation that
    // produced it.  Inspect the current lease while holding the same goal
    // lock before replaying it; otherwise an aborted close or a later acquire
    // could turn an old required fence into a keyless success.
    if (receipt?.state === "closed") {
      // The receipt write is authoritative even if the original handler lost
      // its response or failed during best-effort lock cleanup. Retire only
      // this receipt's token before taking a fresh replay lock; an in-flight
      // closer that already owns the token claim wins and keeps the lock.
      await releaseFileMutationLock(
        lockPathFor(request),
        receipt.lock_token,
        null,
        true,
      );
      const replayLock = await acquireFileMutationLock(
        lockPathFor(request),
        request.owner_pid ?? process.pid,
      );
      try {
        await revalidateAuthoritySources(request.authority.source_receipts);
        const closedTodo = authorityTodo(request);
        if (!closedTodo) {
          throw new TaskLeaseLifecycleError(
            "todo is missing from the canonical projection",
            "todo_not_found",
            { goal_id: request.goal_id, todo_id: request.todo_id },
          );
        }
        // Preserve the holder gate's current mode boundary even though the
        // receipt is terminal. A previous proof must not authorize a later
        // soft-claim ownership mutation.
        if (request.operation === "holder_verify" &&
            request.authority.handoff_mode !== "hard_lease") {
          throw new TaskLeaseLifecycleError(
            "task-lease holder verification is only available in hard_lease handoff mode",
            "handoff_mode_forbids_lease",
            {
              goal_id: request.goal_id,
              todo_id: request.todo_id,
              handoff_mode: request.authority.handoff_mode,
            },
          );
        }
        const verifiedOwner = receipt.fence_owner;
        if (verifiedOwner !== null && (
          !request.authority.registered_agents.includes(verifiedOwner) ||
          closedTodo.excluded_agents.includes(verifiedOwner) ||
          (closedTodo.claimed_by !== null &&
            closedTodo.claimed_by !== verifiedOwner)
        )) {
          throw new TaskLeaseLifecycleError(
            "task lease fence receipt owner no longer matches the canonical todo authority",
            "authority_todo_mismatch",
            { goal_id: request.goal_id, todo_id: request.todo_id, fence_owner: verifiedOwner },
          );
        }

        const currentLease = await loadLeaseForRequest(
          request,
          leasePathFor(request),
        );
        const nonRequired = receipt.response?.required === false &&
          receipt.response.active === false;
        if (nonRequired) {
          // A no-op receipt is replayable only while no lease record exists.
          // If a lease was acquired after the no-op, run the normal fence
          // rules again so hard-lease/CAS requirements cannot be bypassed.
          if (
            currentLease === null &&
            (request.authority.handoff_mode !== "hard_lease" ||
              request.delegated_authority)
          ) {
            const { lock_token: _retiredToken, ...publicReplay } = receipt.response!;
            return {
              ...publicReplay,
              required: false,
              active: false,
              closed: true,
              fence_operation_id: operationId,
              idempotent: true,
            };
          }
          if (currentLease === null &&
              request.authority.handoff_mode === "hard_lease" &&
              !request.delegated_authority) {
            // Re-evaluate the stricter authority without replacing a valid
            // legacy no-op receipt with a transient acquired receipt.  The
            // same execution may return to legacy mode after a failed hard
            // lease attempt and must still be able to replay its durable ACK.
            throw new TaskLeaseLifecycleError(
              "hard_lease handoff mode requires an effective task lease to complete this todo; acquire one with `loopx task-lease acquire`",
              "handoff_mode_requires_lease",
              {
                goal_id: request.goal_id,
                todo_id: request.todo_id,
                handoff_mode: request.authority.handoff_mode,
                lease_path: leasePathFor(request),
              },
              "validation",
            );
          }
          // Keep the replay marker so the locked re-read below can continue
          // with the normal lease/CAS checks instead of recursively replaying
          // the same closed no-op receipt forever.
          recheckingClosedNoop = currentLease !== null;
          receipt = null;
        } else {
          const closeReleased = receipt.response?.action === "fence_close" &&
            receipt.response.released === true;
          const tupleMatches = currentLease !== null &&
            receipt.lease !== null &&
            fenceLeaseMatchesReceipt(currentLease, receipt);

          if (closeReleased) {
            // A committed close that released the lease is replayable only
            // against the exact retired generation.  A missing or newer
            // generation is an ABA/stale-fence conflict, never a no-op.
            if (currentLease === null ||
                currentLease.status !== "released" ||
                !tupleMatches ||
                !plannedLeaseMatches(currentLease, receipt.lease)) {
              throw new TaskLeaseLifecycleError(
                "closed task lease fence receipt does not match the current retired lease generation",
                "fence_state_invalid",
                {
                  goal_id: request.goal_id,
                  todo_id: request.todo_id,
                  lease_path: leasePathFor(request),
                  expected_version: receipt.fence_expected_version,
                  expected_lease_epoch: receipt.fence_expected_lease_epoch,
                  actual_version: currentLease ? leaseVersion(currentLease) : null,
                  actual_lease_epoch: currentLease ? leaseEpoch(currentLease) : null,
                },
                "validation",
              );
            }
            const original = receipt.verify_response ?? (
              receipt.response?.action === request.operation ? receipt.response : null
            );
            if (!original) {
              throw fenceReceiptError(
                receiptPath,
                "closed task lease fence receipt omitted its verification response",
              );
            }
            const { lock_token: _retiredToken, ...publicReplay } = original;
            return {
              ...publicReplay,
              required: false,
              active: false,
              closed: true,
              fence_operation_id: operationId,
              idempotent: true,
            };
          }

          // An aborted/non-releasing close leaves the lease active.  It is
          // safe to retry the verification under a newly acquired lock only
          // when the same verified generation is still present.  A different
          // generation must fail closed and force a fresh fence identity.
          if (currentLease !== null &&
              currentLease.status === "active" &&
              tupleMatches) {
            receipt = null;
          } else {
            throw new TaskLeaseLifecycleError(
              "closed task lease fence receipt is stale or has no retryable lease generation",
              "fence_state_invalid",
              {
                goal_id: request.goal_id,
                todo_id: request.todo_id,
                lease_path: leasePathFor(request),
                expected_version: receipt.fence_expected_version,
                expected_lease_epoch: receipt.fence_expected_lease_epoch,
                actual_version: currentLease ? leaseVersion(currentLease) : null,
                actual_lease_epoch: currentLease ? leaseEpoch(currentLease) : null,
              },
              "validation",
            );
          }
        }
      } finally {
        await releaseFileMutationLock(
          replayLock.targetPath,
          replayLock.token,
          null,
          true,
        );
      }
    }
    const adoptedLock = await adoptFenceReceiptLock(request, receipt);
    const acquiredFreshLock = adoptedLock === null;
    lock = adoptedLock ?? await acquireFileMutationLock(
      lockPathFor(request),
      request.owner_pid ?? process.pid,
    );
    try {
      lockClaim = await claimFileMutationLock(lock.targetPath, lock.token);
    } catch (error) {
      // An adopted lock belongs to the execution that published its receipt;
      // if claiming it fails, leave that owner's lock untouched.
      if (!acquiredFreshLock) lock = null;
      throw error;
    }
    if (!lockClaim) {
      if (acquiredFreshLock) {
        await releaseFileMutationLock(lock.targetPath, lock.token, null, true);
        lock = null;
      } else {
        // Another verifier currently owns the token claim. Do not release its
        // adopted lock; report the contention to the caller instead.
        lock = null;
      }
      throw new EffectRuntimeConflictError(
        "task lease fence token is already being verified",
        "fence_token_invalid",
      );
    }
    // A token claim serializes operations that name this token, but it does
    // not prove that the lock pathname still names the same token. The lock
    // may have been closed and replaced between adoption and claim creation.
    // Re-check ownership while holding the claim before trusting or writing
    // any receipt state.
    const claimedOwner = await mutationLockOwner(lock.targetPath);
    if (!claimedOwner || claimedOwner.token !== lock.token) {
      await releaseFileMutationLockClaim(lockClaim);
      lockClaim = null;
      if (acquiredFreshLock) {
        await releaseFileMutationLock(lock.targetPath, lock.token, null, true);
      }
      lock = null;
      throw new EffectRuntimeConflictError(
        "task lease fence token is no longer held",
        "fence_token_invalid",
      );
    }
    // The first receipt read happened before lock acquisition or adoption.
    // Re-read it while holding both the lock and its token claim so a verifier
    // that waited behind another request cannot overwrite a held or closed
    // receipt.
    const lockedReceipt = await readFenceReceipt(receiptPath, request);
    if (lockedReceipt?.state === "closed") {
      // A closed receipt can be retried only for an aborted, non-releasing
      // close whose exact active generation is still present. Otherwise
      // leave it for the normal closed-replay validator below, which either
      // returns the retired result or fails closed on an ABA transition.
      const lockedLease = await loadLeaseForRequest(
        request,
        leasePathFor(request),
      );
      const retryableClosed = lockedReceipt.response?.action === "fence_close" &&
        lockedReceipt.response.released !== true &&
        lockedLease !== null &&
        lockedLease.status === "active" &&
        fenceLeaseMatchesReceipt(lockedLease, lockedReceipt);
      const lockedNonRequired = lockedReceipt.response?.required === false &&
        lockedReceipt.response.active === false;
      if (!retryableClosed &&
          !(recheckingClosedNoop && lockedNonRequired && lockedLease !== null)) {
        receipt = lockedReceipt;
        if (acquiredFreshLock) {
          await releaseFileMutationLock(lock.targetPath, lock.token, lockClaim, true);
        } else {
          await releaseFileMutationLockClaim(lockClaim);
        }
        lockClaim = null;
        lock = null;
        return await fenceVerify(request, dependencies);
      }
      receipt = retryableClosed ? lockedReceipt : null;
    } else {
      receipt = lockedReceipt;
    }
    // Every legacy verify branch (held replay, holder verification, user-gate
    // auto-acquire) persists a receipt; the promoted authority's fence is
    // checked once here, before that first side effect.
    await requireLegacyCoordinationPrimaryWriteAllowed(request.runtime_root, request.goal_id);
    const initialTodo = authorityTodo(request);
    // Publish the token before semantic validation. If the response is lost
    // after acquisition, a retry can adopt this exact lock and finish the
    // validation instead of waiting for a lock timeout.
    if ((acquiredFreshLock && (!receipt || receipt.state === "acquired")) ||
        !receipt) {
      await persistFenceReceipt(request, "acquired", lock.token, {
        operationId,
        lease: null,
        response: null,
        ownerPid: request.owner_pid ?? process.pid,
        fenceOwner: request.owner,
        // Record the auto-acquire intent before the lease write. If the
        // caller loses its response in the write window, a retry can
        // identify the lease it already minted instead of acquiring a
        // second one.
        fenceIdempotencyKey: allowsUserGateAutoAcquire(request, initialTodo)
          ? request.idempotency_key ?? `auto-${request.todo_id}`
          : request.idempotency_key,
        fenceExpectedVersion: request.expected_version,
        base: receipt,
      });
      receipt = await readFenceReceipt(receiptPath, request);
    }
    if (!lock) {
      throw new TaskLeaseLifecycleError(
        "task lease fence lock could not be established",
        "fence_lock_unavailable",
      );
    }
    // Authority is part of the replay boundary.  A fence receipt is a
    // durable execution record, not a bypass around the current canonical
    // projection.  Re-read and revalidate it before returning any replay.
    await revalidateAuthoritySources(request.authority.source_receipts);
    const todo = authorityTodo(request);
    if (!todo) {
      throw new TaskLeaseLifecycleError(
        "todo is missing from the canonical projection",
        "todo_not_found",
        { goal_id: request.goal_id, todo_id: request.todo_id },
      );
    }
    const leasePath = leasePathFor(request);
    const at = lifecycleNow(request, dependencies);
    const rawLease = await readLease(leasePath);
    let lease = rawLease === null
      ? null
      : validatePersistedLease(rawLease, request, leasePath);
    const active = leaseIsActive(lease, at);
    const effective = active && lease !== null && ownerRejection(
      todo,
      persistedOwner(lease),
      request.authority.registered_agents,
    ) === null;

    if (receipt?.state === "held" && receipt.response) {
      if (
        lease &&
        receipt.lease &&
        plannedLeaseMatches(lease, receipt.lease) &&
        (await mutationLockOwner(lockPathFor(request)))?.token === lock.token
      ) {
        const verifiedOwner = receipt.fence_owner ?? persistedOwner(lease);
        if (!request.authority.registered_agents.includes(verifiedOwner) ||
            todo.excluded_agents.includes(verifiedOwner) ||
            (todo.claimed_by !== null && todo.claimed_by !== verifiedOwner)) {
          throw new TaskLeaseLifecycleError(
            "task lease fence receipt owner no longer matches the canonical todo authority",
            "authority_todo_mismatch",
            { goal_id: request.goal_id, todo_id: request.todo_id, fence_owner: verifiedOwner },
          );
        }
        if (request.operation === "holder_verify") {
          if (request.authority.handoff_mode !== "hard_lease" ||
              request.owner !== verifiedOwner ||
              !active ||
              ownerRejection(
                todo,
                verifiedOwner,
                request.authority.registered_agents,
              ) !== null) {
            throw new TaskLeaseLifecycleError(
              "task lease holder verification authority no longer matches the canonical lease projection",
              "authority_todo_mismatch",
              { goal_id: request.goal_id, todo_id: request.todo_id, fence_owner: verifiedOwner },
            );
          }
        } else if (!request.delegated_authority && (!active || !effective)) {
          throw new TaskLeaseLifecycleError(
            "task lease fence authority no longer permits this verification",
            "handoff_mode_lease_claim_divergence",
            { goal_id: request.goal_id, todo_id: request.todo_id, fence_owner: verifiedOwner },
          );
        }
        keep = true;
        const replayResponse = {
          ...receipt.response,
          lock_token: lock.token,
          fence_operation_id: operationId,
          idempotent: true,
        };
        // A held receipt can be replayed by a different caller process after
        // the original owner PID is gone.  The fresh lock is the new
        // transferable capability, so publish its token before returning it.
        if (receipt.lock_token !== lock.token || receipt.owner_pid !== (request.owner_pid ?? process.pid)) {
          await persistFenceReceipt(request, "held", lock.token, {
            operationId,
            lease,
            response: replayResponse,
            verifyResponse: replayResponse,
            ownerPid: request.owner_pid ?? process.pid,
            fenceOwner: verifiedOwner,
            fenceIdempotencyKey: receipt.fence_idempotency_key,
            fenceExpectedVersion: receipt.fence_expected_version,
            fenceExpectedLeaseEpoch: receipt.fence_expected_lease_epoch,
            base: receipt,
          });
        }
        return replayResponse;
      }
    }
    if (request.operation === "holder_verify") {
      if (request.authority.handoff_mode !== "hard_lease") {
        throw new TaskLeaseLifecycleError(
          "task-lease holder verification is only available in hard_lease handoff mode",
          "handoff_mode_forbids_lease",
          { goal_id: request.goal_id, todo_id: request.todo_id, handoff_mode: request.authority.handoff_mode },
        );
      }
      if (!request.owner) throw new TaskLeaseLifecycleError("hard_lease handoff mode requires an attributed actor for ownership changes; provide --agent-id", "handoff_mode_requires_lease", {}, "validation");
      if (!active || !lease) {
        throw new TaskLeaseLifecycleError(
          "hard_lease handoff mode requires a time-active task lease before ownership of an existing todo can change; acquire one with `loopx task-lease acquire`",
          "handoff_mode_requires_lease",
          { goal_id: request.goal_id, todo_id: request.todo_id, reason: "no_active_lease", lease_path: leasePath },
        );
      }
      if (persistedOwner(lease) !== request.owner) {
        throw new TaskLeaseLifecycleError(
          `hard_lease handoff mode: actor '${request.owner}' does not own the time-active task lease held by '${lease.owner}'`,
          "handoff_mode_requires_lease",
          { goal_id: request.goal_id, todo_id: request.todo_id, reason: "lease_owner_mismatch", lease_owner: lease.owner, lease_version: lease.version, lease_epoch: leaseEpoch(lease), expires_at: lease.expires_at, lease_path: leasePath },
        );
      }
      const response = {
        schema_version: "task_lease_v0",
        checked: true,
        active: true,
        owner: persistedOwner(lease),
        version: leaseVersion(lease),
        lease_epoch: leaseEpoch(lease),
        lock_token: lock.token,
        fence_operation_id: operationId,
      };
      await persistFenceReceipt(request, "held", lock.token, {
        operationId,
        lease,
        response,
        ownerPid: request.owner_pid ?? process.pid,
        fenceOwner: persistedOwner(lease),
        fenceExpectedVersion: leaseVersion(lease),
        fenceExpectedLeaseEpoch: leaseEpoch(lease),
        base: receipt,
      });
      keep = true;
      return response;
    }

    const explicitFence = request.idempotency_key !== null || request.expected_version !== null;
    const autoAcquire = allowsUserGateAutoAcquire(request, todo);
    if (autoAcquire && !effective && !active) {
      if (!request.owner) {
        throw new TaskLeaseLifecycleError("hard_lease handoff mode auto-acquire requires an attributed actor; provide --agent-id", "handoff_mode_requires_lease", { goal_id: request.goal_id, todo_id: request.todo_id, reason: "missing_actor", lease_path: leasePath });
      }
      const rejection = ownerRejection(todo, request.owner, request.authority.registered_agents);
      if (rejection) throw ownerError(request, rejection, todo);
      const now = utcIsoformat(at);
      lease = {
        schema_version: "task_lease_v0",
        goal_id: request.goal_id,
        todo_id: request.todo_id,
        owner: request.owner,
        idempotency_key: request.idempotency_key ?? `auto-${request.todo_id}`,
        write_scopes: [],
        acquire_ttl_seconds: 2700,
        version: leaseVersion(lease) + 1,
        lease_epoch: leaseEpoch(lease) + 1,
        acquired_at: now,
        updated_at: now,
        expires_at: utcIsoformat(new Date(at.valueOf() + 2700 * 1_000)),
        status: "active",
      };
      await dependencies.beforeWrite?.(lease);
      await revalidateAuthoritySources(request.authority.source_receipts);
      const shadowCapture = await captureLeaseWrite(
        request, rawLease, lease, "task_lease_auto_acquire",
      );
      await atomicWriteJson(leasePath, lease);
      await shadowCapture?.commit();
      const response = fencePayload(
        { ...request, owner: request.owner },
        lease,
        lock.token,
        true,
      );
      await persistFenceReceipt(request, "held", lock.token, {
        operationId,
        lease,
        response,
        ownerPid: request.owner_pid ?? process.pid,
        fenceOwner: request.owner,
        fenceIdempotencyKey: lease.idempotency_key as string,
        fenceExpectedVersion: leaseVersion(lease),
        fenceExpectedLeaseEpoch: leaseEpoch(lease),
        base: receipt,
      });
      keep = true;
      return attachRuntimeShadowCapture(response, shadowCapture);
    }
    // A response can be lost after an auto-acquire write but before the
    // receipt reaches the caller.  The durable fence receipt proves that the
    // same execution instance already minted this lease, so recover it under
    // the adopted lock instead of treating the active lease as a divergence.
    const recoveredAutoAcquire = request.operation === "terminal_verify" &&
      receipt?.state !== "closed" &&
      receipt?.fence_idempotency_key === `auto-${request.todo_id}` &&
      receipt?.fence_owner !== null &&
      lease !== null &&
      persistedOwner(lease) === receipt.fence_owner &&
      persistedKey(lease) === receipt.fence_idempotency_key &&
      lease.status === "active";
    if (recoveredAutoAcquire) {
      // Keep the narrowing explicit: `lease` is mutable in the surrounding
      // validation flow, so TypeScript cannot retain the conjunction above.
      if (lease === null || receipt === null) {
        throw new TaskLeaseLifecycleError(
          "task lease auto-acquire receipt is missing its lease snapshot",
          "fence_state_invalid",
        );
      }
      const response = fencePayload(
        { ...request, owner: persistedOwner(lease) },
        lease,
        lock.token,
        true,
      );
      await persistFenceReceipt(request, "held", lock.token, {
        operationId,
        lease,
        response,
        ownerPid: request.owner_pid ?? process.pid,
        fenceOwner: persistedOwner(lease),
        fenceIdempotencyKey: persistedKey(lease),
        fenceExpectedVersion: leaseVersion(lease),
        fenceExpectedLeaseEpoch: leaseEpoch(lease),
        base: receipt,
      });
      keep = true;
      return response;
    }
    if (!effective) {
      if (request.authority.handoff_mode === "hard_lease" && !request.delegated_authority) {
        throw new TaskLeaseLifecycleError(
          active ? "hard_lease handoff mode found a time-active lease diverged from the todo projection; repair ownership (release or transfer the lease, or restore claimed_by) before completing." : "hard_lease handoff mode requires an effective task lease to complete this todo; acquire one with `loopx task-lease acquire`",
          active ? "handoff_mode_lease_claim_divergence" : "handoff_mode_requires_lease",
          { goal_id: request.goal_id, todo_id: request.todo_id, handoff_mode: request.authority.handoff_mode, lease_owner: lease?.owner, lease_version: lease?.version, lease_epoch: lease ? leaseEpoch(lease) : 0, expires_at: lease?.expires_at, lease_path: leasePath },
        );
      }
      if (explicitFence && request.require_active_when_fence_supplied) {
        throw new TaskLeaseLifecycleError("task lease fence was supplied but no effective lease is active", "lease_not_active", { goal_id: request.goal_id, todo_id: request.todo_id, lease_path: leasePath });
      }
      const response = {
        schema_version: "task_lease_v0",
        required: false,
        active: false,
        fence_operation_id: operationId,
      };
      await persistFenceReceipt(request, "closed", lock.token, {
        operationId,
        lease: null,
        response,
        ownerPid: request.owner_pid ?? process.pid,
        base: receipt,
      });
      return response;
    }
    if (!lease) throw new TaskLeaseLifecycleError("task lease fence state is invalid", "invalid_lease_snapshot");
    if (!request.idempotency_key) throw new TaskLeaseLifecycleError("todo has an active task lease; lifecycle mutation requires its idempotency key", "lease_fence_required", { goal_id: request.goal_id, todo_id: request.todo_id, lease_owner: lease.owner, lease_version: lease.version, lease_epoch: leaseEpoch(lease), lease_path: leasePath });
    if (persistedOwner(lease) !== request.owner || persistedKey(lease) !== request.idempotency_key) throw new TaskLeaseLifecycleError("task lease owner or execution-instance key mismatch", "lease_cas_mismatch", { goal_id: request.goal_id, todo_id: request.todo_id, lease_owner: lease.owner, lease_version: leaseVersion(lease), lease_epoch: leaseEpoch(lease), actor_agent_id: request.owner, lease_path: leasePath });
    if (request.expected_version === null) throw new TaskLeaseLifecycleError("task lease terminal fence requires the current lease version", "version_required", { action: "terminal_verify" });
    if (leaseVersion(lease) !== request.expected_version) throw new TaskLeaseLifecycleError(`lease version mismatch: expected ${request.expected_version}, got ${leaseVersion(lease)}`, "version_mismatch", { expected_version: request.expected_version, actual_version: leaseVersion(lease) });
    const response = fencePayload(request, lease, lock.token);
    await persistFenceReceipt(request, "held", lock.token, {
      operationId,
      lease,
      response,
      ownerPid: request.owner_pid ?? process.pid,
      fenceOwner: persistedOwner(lease),
      fenceIdempotencyKey: persistedKey(lease),
      fenceExpectedVersion: leaseVersion(lease),
      fenceExpectedLeaseEpoch: leaseEpoch(lease),
      base: receipt,
    });
    keep = true;
    return response;
  } finally {
    // A non-required fence is still a lock-scoped read.  Release the native
    // lock on every return and validation failure; only a returned held fence
    // transfers ownership to the caller for a later fence_close.
    if (lockClaim) {
      if (!keep && lock) {
        await releaseFileMutationLock(
          lock.targetPath,
          lock.token,
          lockClaim,
          true,
        );
        lockClaim = null;
        lock = null;
      } else {
        try {
          await releaseFileMutationLockClaim(lockClaim);
        } catch {
          // Claim cleanup is best effort; the owner PID/token remain
          // reclaimable if this process is interrupted during cleanup.
        }
        lockClaim = null;
      }
    }
    if (!keep && lock) {
      await releaseFileMutationLock(lock.targetPath, lock.token, null, true);
      lock = null;
    }
  }
}

async function replayClosedFenceClose(
  request: LifecycleRequest,
  receipt: FenceReceipt,
  receiptPath: string,
): Promise<JsonObject> {
  if (!receipt.response || receipt.response.action !== "fence_close") {
    throw fenceReceiptError(
      receiptPath,
      "closed task lease fence receipt omitted its close response",
    );
  }
  if (!receipt.close_request_digest) {
    // A close receipt without the request digest cannot prove that a retry has
    // the same commit/release intent. Treat old or hand-edited receipts as
    // corrupt instead of accepting a parameter-changing replay.
    throw fenceReceiptError(
      receiptPath,
      "closed task lease fence receipt omitted its close request digest",
    );
  }
  const expectedDigest = fenceCloseRequestDigest(request);
  if (receipt.close_request_digest !== expectedDigest) {
    throw new TaskLeaseLifecycleError(
      "task lease fence close was retried with different parameters",
      "fence_operation_reuse",
      { receipt_path: receiptPath },
      "validation",
    );
  }

  // Repair a response-loss window before taking a fresh goal lock. If a
  // native closer still owns the token claim, the release helper fails closed
  // and the acquisition below waits for that critical section to finish.
  await releaseFileMutationLock(
    lockPathFor(request),
    receipt.lock_token,
    null,
    true,
  );
  const lock = await acquireFileMutationLock(
    lockPathFor(request),
    request.owner_pid ?? process.pid,
  );
  try {
    const currentReceipt = await readFenceReceipt(receiptPath, request);
    if (!currentReceipt || currentReceipt.state !== "closed" ||
        currentReceipt.close_request_digest !== expectedDigest) {
      throw new TaskLeaseLifecycleError(
        "closed task lease fence receipt changed during replay",
        "fence_state_invalid",
        { receipt_path: receiptPath },
        "validation",
      );
    }
    const currentLease = await loadLeaseForRequest(
      request,
      leasePathFor(request),
    );
    const response = currentReceipt.response;
    if (!response || response.action !== "fence_close" ||
        typeof response.released !== "boolean") {
      throw fenceReceiptError(
        receiptPath,
        "closed task lease fence receipt close response is malformed",
      );
    }
    const tupleMatches = currentLease !== null &&
      fenceLeaseMatchesReceipt(currentLease, currentReceipt);
    if (response.released === true) {
      if (
        currentLease === null ||
        currentLease.status !== "released" ||
        currentReceipt.lease === null ||
        !tupleMatches ||
        !plannedLeaseMatches(currentLease, currentReceipt.lease)
      ) {
        throw new TaskLeaseLifecycleError(
          "closed task lease fence receipt does not match the current retired lease generation",
          "fence_state_invalid",
          {
            goal_id: request.goal_id,
            todo_id: request.todo_id,
            lease_path: leasePathFor(request),
            expected_version: currentReceipt.fence_expected_version,
            expected_lease_epoch: currentReceipt.fence_expected_lease_epoch,
            actual_version: currentLease ? leaseVersion(currentLease) : null,
            actual_lease_epoch: currentLease ? leaseEpoch(currentLease) : null,
          },
          "validation",
        );
      }
    } else if (
      currentReceipt.lease === null
        ? currentLease !== null
        : !tupleMatches || !plannedLeaseMatches(currentLease, currentReceipt.lease)
    ) {
      throw new TaskLeaseLifecycleError(
        "closed task lease fence receipt does not match the current lease generation",
        "fence_state_invalid",
        { receipt_path: receiptPath },
        "validation",
      );
    }
    return { ...response, idempotent: true };
  } finally {
    await releaseFileMutationLock(lock.targetPath, lock.token, null, true);
  }
}

async function fenceClose(
  request: LifecycleRequest,
  dependencies: LifecycleDependencies,
): Promise<JsonObject> {
  if (!request.lock_token) throw new TaskLeaseLifecycleError("fence close requires lock_token", "invalid_lock_token");
  let operationId = fenceOperationId(request);
  let receiptPath = fenceReceiptPath(request, operationId);
  let receipt = await readFenceReceipt(receiptPath, request);
  // Older Python callers did not carry the private operation id.  Resolve a
  // unique receipt by token as a compatibility readback path; all new calls
  // use the exact path returned by fence verification.
  if (!receipt && request.fence_operation_id === null) {
    const match = await findFenceReceiptByToken(request);
    if (match) {
      operationId = match.receipt.operation_id;
      receiptPath = match.path;
      receipt = match.receipt;
    }
  }
  if (receipt && receipt.lock_token !== request.lock_token) {
    throw new EffectRuntimeConflictError(
      "task lease fence receipt does not match the supplied lock token",
      "fence_token_invalid",
    );
  }
  if (receipt?.state === "closed") {
    return await replayClosedFenceClose(request, receipt, receiptPath);
  }
  if (request.committed && request.release_lease && !isVerifiedHeldFence(receipt)) {
    // A token alone is not a lease authority. In particular, an `acquired`
    // receipt can exist after an auto-acquire write lost its response, but it
    // never proves that terminal validation completed. Require a durable held
    // receipt with a verified response before allowing a lease release.
    throw new TaskLeaseLifecycleError(
      "committed task lease fence close requires a verified held fence",
      "fence_state_invalid",
      { receipt_path: receiptPath },
      "validation",
    );
  }
  const lockPath = lockPathFor(request);
  let claim: FileMutationLockClaim | null = null;
  let released = false;
  let alreadyReleased = false;
  try {
    const owner = await mutationLockOwner(lockPath);
    if (!owner || owner.token !== request.lock_token) {
      // A response may have been lost after the close write and lock release.
      // The persisted lease plus the held receipt is enough to finish the
      // close receipt without touching a new lock owner.
      const leasePath = leasePathFor(request);
      const rawLease = await readLease(leasePath);
      const recoveredLease = rawLease === null
        ? null
        : validatePersistedLease(rawLease, request, leasePath);
      if (
        receipt &&
        recoveredLease &&
        receipt.state === "held" &&
        request.committed &&
        request.release_lease &&
        recoveredLease.status === "released" &&
        fenceLeaseMatchesReceipt(recoveredLease, receipt)
      ) {
        const response = {
          ok: true,
          schema_version: "task_lease_v0",
          action: "fence_close",
          released: true,
          idempotent: true,
        };
        await persistFenceReceipt(request, "closed", request.lock_token, {
          operationId,
          lease: recoveredLease,
          response,
          base: receipt,
          requestDigest: receipt.request_digest,
          ownerPid: receipt.owner_pid,
          fenceOwner: receipt.fence_owner,
          fenceIdempotencyKey: receipt.fence_idempotency_key,
          fenceExpectedVersion: receipt.fence_expected_version,
          fenceExpectedLeaseEpoch: receipt.fence_expected_lease_epoch,
          closeRequestDigest: fenceCloseRequestDigest(request),
        });
        return response;
      }
      throw new EffectRuntimeConflictError("task lease fence token is no longer held", "fence_token_invalid");
    }
    claim = await claimFileMutationLock(lockPath, request.lock_token);
    if (!claim) {
      throw new EffectRuntimeConflictError(
        "task lease fence token is already being closed or is no longer held",
        "fence_token_invalid",
      );
    }
    const claimedOwner = await mutationLockOwner(lockPath);
    if (!claimedOwner || claimedOwner.token !== request.lock_token) {
      throw new EffectRuntimeConflictError("task lease fence token is no longer held", "fence_token_invalid");
    }
    let shadowCapture: LeaseOutboxCapture | null = null;
    if (request.committed && request.release_lease) {
      await requireLegacyCoordinationPrimaryWriteAllowed(request.runtime_root, request.goal_id);
      const at = lifecycleNow(request, dependencies);
      const leasePath = leasePathFor(request);
      const rawLease = await readLease(leasePath);
      if (!rawLease) {
        throw new TaskLeaseLifecycleError("task lease fence was active but its lease record is gone", "fence_state_invalid", { lease_path: leasePath }, "durable_writeback");
      }
      const lease = validatePersistedLease(rawLease, request, leasePath);
      const expectedOwner = request.fence_owner ?? receipt?.fence_owner;
      const expectedKey = request.fence_idempotency_key ?? receipt?.fence_idempotency_key;
      const expectedVersion = request.fence_expected_version ?? receipt?.fence_expected_version;
      const expectedEpoch = request.fence_expected_lease_epoch ?? receipt?.fence_expected_lease_epoch;
      const holderFence = receipt?.verify_response?.checked === true ||
        receipt?.response?.checked === true;
      // Holder verification proves ownership with the lease tuple and does
      // not require the caller to know the lease's execution key.  Terminal
      // verification still requires that key to prevent an actor-only close.
      if (
        expectedOwner === null ||
        expectedVersion === null ||
        expectedEpoch === null ||
        (!holderFence && expectedKey === null)
      ) {
        throw new TaskLeaseLifecycleError(
          holderFence
            ? "committed holder fence close requires its verified owner, version, and lease epoch"
            : "committed task lease fence close requires its verified owner, key, version, and lease epoch",
          "fence_cas_mismatch",
          { lease_path: leasePath },
          "durable_writeback",
        );
      }
      if (
        receipt &&
        ((receipt.fence_owner !== null && receipt.fence_owner !== expectedOwner) ||
          (receipt.fence_idempotency_key !== null && expectedKey !== null &&
            receipt.fence_idempotency_key !== expectedKey) ||
          (receipt.fence_expected_version !== null &&
            receipt.fence_expected_version !== expectedVersion) ||
          (receipt.fence_expected_lease_epoch !== null &&
            receipt.fence_expected_lease_epoch !== expectedEpoch))
      ) {
        throw new TaskLeaseLifecycleError(
          "task lease fence close does not match its verified lease tuple",
          "fence_cas_mismatch",
          { lease_path: leasePath },
          "durable_writeback",
        );
      }
      if (
        persistedOwner(lease) !== expectedOwner ||
        (expectedKey !== null && persistedKey(lease) !== expectedKey) ||
        leaseVersion(lease) !== expectedVersion ||
        leaseEpoch(lease) !== expectedEpoch
      ) {
        throw new TaskLeaseLifecycleError("task lease fence changed before close", "fence_cas_mismatch", { lease_path: leasePath, expected_lease_epoch: expectedEpoch, actual_lease_epoch: leaseEpoch(lease) }, "durable_writeback");
      }
      if (lease.status === "released") {
        // The lease write may have committed before the process lost its
        // response or fence receipt.  The verified tuple makes this a safe
        // exactly-once replay rather than a state error.
        released = true;
        alreadyReleased = true;
      } else if (lease.status !== "active") {
        throw new TaskLeaseLifecycleError("task lease fence no longer references an active lease record", "fence_state_invalid", { lease_path: leasePath, status: lease.status ?? null }, "durable_writeback");
      }
      const ownerBeforeWrite = await mutationLockOwner(lockPath);
      if (!ownerBeforeWrite || ownerBeforeWrite.token !== request.lock_token) {
        throw new EffectRuntimeConflictError("task lease fence token is no longer held", "fence_token_invalid");
      }
      if (!alreadyReleased) {
        const next = releasedLease(lease, at);
        await dependencies.beforeWrite?.(next);
        shadowCapture = await captureLeaseWrite(
          request, lease, next, "task_lease_fence_close",
        );
        await atomicWriteJson(leasePath, next);
        await shadowCapture?.commit();
        released = true;
      }
    }
    const response = {
      ok: true,
      schema_version: "task_lease_v0",
      action: "fence_close",
      released,
      ...(alreadyReleased ? { idempotent: true } : {}),
    };
    await persistFenceReceipt(request, "closed", request.lock_token, {
      operationId,
      lease: released
        ? await loadLeaseForRequest(request, leasePathFor(request))
        : receipt?.lease ?? null,
      response,
      base: receipt,
      requestDigest: receipt?.request_digest,
      ownerPid: receipt?.owner_pid ?? request.owner_pid ?? process.pid,
      fenceOwner: request.fence_owner ?? receipt?.fence_owner,
      fenceIdempotencyKey: request.fence_idempotency_key ?? receipt?.fence_idempotency_key,
      fenceExpectedVersion: request.fence_expected_version ?? receipt?.fence_expected_version,
      fenceExpectedLeaseEpoch: request.fence_expected_lease_epoch ?? receipt?.fence_expected_lease_epoch,
      closeRequestDigest: fenceCloseRequestDigest(request),
    });
    return attachRuntimeShadowCapture(response, shadowCapture);
  } finally {
    if (claim) {
      await releaseFileMutationLock(
        lockPath,
        request.lock_token,
        claim,
        // Once the lease/receipt write has committed, cleanup is best effort;
        // even on an earlier failure it must not mask the original result.
        true,
      );
    }
  }
}

export async function executeTaskLeaseLifecycle(
  value: unknown,
  dependencies: LifecycleDependencies = {},
): Promise<JsonObject> {
  let request: LifecycleRequest | null = null;
  try {
    request = decodeRequest(value);
    if (request.operation === "fence_close") return await fenceClose(request, dependencies);
    if (request.operation === "terminal_verify" || request.operation === "holder_verify") {
      const fence = await fenceVerify(request, dependencies);
      const capture = fence.coordination_runtime_shadow_capture;
      delete fence.coordination_runtime_shadow_capture;
      return {
        ok: true,
        schema_version: "task_lease_v0",
        action: request.operation,
        fence,
        settlement: lifecycleSettlement(request, "committed"),
        ...(capture === undefined
          ? {}
          : { coordination_runtime_shadow_capture: capture }),
      };
    }
    return await withFileMutationLock(
      legacyCoordinationLeaseLockPath(request.runtime_root, request.goal_id),
      () => withFileMutationLock(lockPathFor(request!), async () => {
        await requireLegacyCoordinationPrimaryWriteAllowed(request!.runtime_root, request!.goal_id);
        return await ordinaryOperation(request!, dependencies);
      }),
    );
  } catch (error) {
    const info = errorInfo(error);
    return failureEnvelope(request ?? failureRequestContext(value), info);
  }
}
