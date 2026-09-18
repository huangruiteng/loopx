/** A lease acquisition is one full-head admission/CAS with a retained receipt.
 * Unlike historical maintenance replay, success here must supply current proof. */
import type {JsonObject} from "../effect_program.ts";
import type {AuthorityStore} from "./authority_store.ts";
import {AuthorityStoreProtocolError, canonicalAuthorityObject, canonicalAuthoritySha256} from "./authority_store_codec.ts";
import {CoordinationCommandReceipt, commandReceiptResult} from "./command_receipt.ts";
import {indexCoordinationProjection, validateCoordinationTodoReadModel, prepareCoordinationProjectionCommit} from "./coordination_projection.ts";
import {canonicalTaskLease, canonicalTaskLeaseAcquireFacts} from "./task_lease_state.ts";
import {HANDOFF_MODES} from "./handoff_mode_policy.ts";
import {requireStringLiteral} from "../runtime_decode.ts";
import {decideTaskLeaseAcquire, materializeTaskLeaseAcquire} from "../work_items/task_lease_acquire_decision.ts";
import {leaseOwnerRejection} from "../work_items/task_lease_eligibility.ts";
import {normalizeGoalId, normalizeTodoId, normalizeOwner, normalizeIdempotencyKey,
  normalizeWriteScopes, normalizeTtl, leaseEpoch, leaseVersion, leaseIsActive,
  TaskLeaseAcquireError} from "../work_items/task_lease_acquire.ts";

export interface CanonicalTaskLeaseAcquireInput {
  goal_id: string; todo_id: string; owner: string; idempotency_key: string;
  expected_version: number | null; ttl_seconds: number | null;
  write_scopes: readonly string[]; registered_agents: readonly string[]; now: Date;
}

export async function executeCanonicalTaskLeaseAcquire(store: AuthorityStore, raw: CanonicalTaskLeaseAcquireInput,
  beforeCommit?: (lease: JsonObject) => Promise<void>): Promise<JsonObject> {
  const schema = "loopx_canonical_task_lease_acquire_result_v0";
  const failed = (code: string, reason: string, detail: JsonObject = {}) =>
    ({schema_version: schema, status: "failed", changed: false, reason_code: code, reason, failure_stage: "validation", ...detail});
  let input: CanonicalTaskLeaseAcquireInput & {ttl_seconds: number};
  try {
    input = {...raw, goal_id: normalizeGoalId(raw.goal_id), todo_id: normalizeTodoId(raw.todo_id),
      owner: normalizeOwner(raw.owner), idempotency_key: normalizeIdempotencyKey(raw.idempotency_key),
      write_scopes: normalizeWriteScopes(raw.write_scopes), ttl_seconds: normalizeTtl(raw.ttl_seconds),
      registered_agents: raw.registered_agents.map(normalizeOwner)};
    if (input.expected_version !== null && (!Number.isSafeInteger(input.expected_version) || input.expected_version < 0)) {
      return failed("invalid_expected_version", "expected lease version must be a non-negative safe integer");
    }
    if (!(input.now instanceof Date) || !Number.isFinite(input.now.valueOf())) return failed("invalid_clock", "lease acquire requires a valid clock");
  } catch (error) {
    return failed(error instanceof TaskLeaseAcquireError ? error.code : "invalid_canonical_acquire_request",
      error instanceof Error ? error.message : "invalid canonical lease acquire");
  }
  const identityFields = {goal_id: input.goal_id, todo_id: input.todo_id, owner: input.owner, idempotency_key: input.idempotency_key};
  const identity = {schema_version: "loopx_canonical_task_lease_acquire_receipt_v0",
    operation_id: `lease-acquire:${canonicalAuthoritySha256(identityFields)}`, goal_id: input.goal_id,
    request_sha256: canonicalAuthoritySha256({...identityFields, expected_version: input.expected_version,
      ttl_seconds: input.ttl_seconds, write_scopes: [...input.write_scopes].sort()})};
  const receipt = new CoordinationCommandReceipt({result_schema: schema, identity, failure: failed,
    decode(original) {
      const payload = commandReceiptResult(original);
      const lease = canonicalTaskLease(canonicalAuthorityObject(payload.fields.lease, "acquire receipt lease"), input.goal_id, input.todo_id);
      const scopes = [...(lease.write_scopes ?? []) as string[]].sort();
      if (JSON.stringify(scopes) !== JSON.stringify([...input.write_scopes].sort()) ||
          (lease.acquire_ttl_seconds != null && lease.acquire_ttl_seconds !== input.ttl_seconds) ||
          (payload.changed && input.expected_version !== null && leaseVersion(lease) !== input.expected_version + 1)) {
        throw new AuthorityStoreProtocolError("acquire receipt does not match its original parameters");
      }
      if (lease.owner !== input.owner || lease.idempotency_key !== input.idempotency_key || lease.status !== "active" ||
          leaseVersion(lease) < 1 || leaseEpoch(lease) < 1 || !leaseIsActive(lease, new Date(String(lease.acquired_at)))) {
        throw new AuthorityStoreProtocolError("acquire receipt does not match its execution identity");
      }
      return {...payload, fields: {...payload.fields, operation_id: identity.operation_id}};
    }});

  const readFacts = async () => {
    const head = await store.loadAuthority();
    if (head.status !== "loaded") return {head, facts: null, mode: null};
    validateCoordinationTodoReadModel(head.head, input.goal_id);
    const index = indexCoordinationProjection(head.head, input.goal_id);
    return {head, facts: canonicalTaskLeaseAcquireFacts(index, input.goal_id, input.todo_id, input.registered_agents, input.now),
      mode: requireStringLiteral(head.head.handoff_mode ?? "legacy", HANDOFF_MODES, "canonical handoff_mode")};
  };
  // Do not grant execution from a receipt that outlived its execution generation.
  const currentProof = async (result: JsonObject): Promise<JsonObject> => {
    if (!["applied", "no_change", "replayed", "recovered"].includes(String(result.status))) return result;
    const {head, facts, mode} = await readFacts();
    if (head.status !== "loaded" || facts === null) return {...failed("canonical_acquire_readback_required",
      "acquisition receipt is durable but current authority is unavailable; retry the same request"),
      status: "ambiguous", original_receipt: result.original_receipt, recovery: {operation_id: identity.operation_id, retry_with_same_operation_id: true}};
    const original = canonicalTaskLease(canonicalAuthorityObject(result.lease, "original acquire lease"), input.goal_id, input.todo_id);
    const current = facts.current;
    const details = {handoff_mode: mode, original_receipt: result.original_receipt,
      current_provider_revision: head.provider_revision, current_cursor: head.cursor};
    const rejection = mode === "soft_claim" ? "handoff_mode_forbids_lease" : leaseOwnerRejection(facts.todo, input.owner, input.registered_agents);
    if (rejection) return failed(rejection, `current authority rejects lease acquire replay: ${rejection}`, details);
    if (!current || !leaseIsActive(current, input.now) || current.owner !== input.owner ||
        current.idempotency_key !== input.idempotency_key || leaseEpoch(current) !== leaseEpoch(original) ||
        leaseVersion(current) < leaseVersion(original)) {
      return failed("idempotency_key_reuse", "acquire receipt belongs to a retired execution; use a new execution key", details);
    }
    // Renewal may advance version/expiry within this execution. Return current
    // usable proof while the immutable receipt preserves the original decision.
    return {...result, ...details, lease: current};
  };

  let committed = false;
  try {
    const replay = await receipt.read(store);
    if (replay !== null) return await currentProof(replay);
    const {head, facts, mode} = await readFacts();
    if (head.status !== "loaded" || facts === null) return failed("canonical_lease_authority_unavailable",
      "canonical lease authority is unavailable; restore the selected provider before retrying", {...head});
    const decision = decideTaskLeaseAcquire({handoff_mode: mode!, registered_agents: input.registered_agents,
      ...facts, command: input});
    if (decision.outcome === "rejected" || decision.outcome === "conflict") {
      return failed(decision.code, `canonical task lease acquire rejected: ${decision.code}`, {
        handoff_mode: mode, expected_version: input.expected_version, actual_version: leaseVersion(facts.current),
        ...(facts.todo ? {todo_status: facts.todo.status, claimed_by: facts.todo.claimed_by, excluded_agents: [...facts.todo.excluded_agents]} : {}),
        ...(decision.conflict_indexes.length ? {conflicts: decision.conflict_indexes.map(i => facts.other_leases[i])} : {})});
    }
    const changed = decision.outcome === "apply";
    const lease = changed ? materializeTaskLeaseAcquire(input, input, decision, input.now) : facts.current;
    if (!lease) throw new AuthorityStoreProtocolError("accepted acquire lacks a lease");
    const commit = changed ? prepareCoordinationProjectionCommit({goal_id: input.goal_id,
      operation_id: identity.operation_id, expected_provider_revision: head.provider_revision, projection: head.head,
      mutations: [{kind: "lease_upsert", lease}]}) : {operation_id: identity.operation_id,
        expected_provider_revision: head.provider_revision, next_projection: head.head, events: [], receipts: []};
    commit.receipts = [{...identity, result: {changed, lease, handoff_mode: mode}}];
    await beforeCommit?.(lease);
    committed = true;
    const result = await receipt.commit(store, commit);
    return await currentProof(result);
  } catch (error) {
    if (committed) return {...failed("canonical_acquire_recovery_required", "acquire may be durable; retry the same request"),
      status: "ambiguous", failure_stage: "durable_writeback", recovery: {operation_id: identity.operation_id, retry_with_same_operation_id: true}};
    return failed(error instanceof TaskLeaseAcquireError ? error.code : "invalid_canonical_acquire_state",
      error instanceof Error ? error.message : "canonical acquisition state is invalid");
  }
}
