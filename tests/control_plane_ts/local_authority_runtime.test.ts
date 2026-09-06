import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { FileAuthorityStore } from "../../loopx/control_plane/coordination/file_authority_store.ts";
import type { AuthorityStoreCommit } from "../../loopx/control_plane/coordination/authority_store.ts";
import { canonicalAuthorityBytes } from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_DOMAIN_RECORD_CONTRACT,
} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import {
  TODO_CANONICAL_READ_RECORD_FIELDS,
  TODO_CANONICAL_READ_RECORD_SCHEMA,
} from "../../loopx/control_plane/coordination/coordination_projection.ts";
import {
  LOCAL_COORDINATION_PROMOTION_REQUEST_SCHEMA,
  LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
  LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
  LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
  LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA,
  listLocalCoordinationTodos,
  claimLocalCoordinationTodo,
  mutateLocalCoordinationAuthority,
  promoteLocalCoordinationAuthority,
  readLocalCoordinationTodo,
} from "../../loopx/control_plane/coordination/local_authority_runtime.ts";
import {
  COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
  evaluateCoordinationTodoClaimDecision,
} from "../../loopx/control_plane/coordination/todo_claim.ts";
import {
  checkLegacyCoordinationWriteAllowed,
  engageLegacyCoordinationWriterFence,
  LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
  LEGACY_COORDINATION_WRITER_FENCE_SCHEMA,
  LEGACY_COORDINATION_WRITE_CHECK_REQUEST_SCHEMA,
} from "../../loopx/control_plane/coordination/legacy_writer_fence.ts";
import {
  bootstrapCoordinationRuntimeShadow,
  commitCoordinationRuntimeShadow,
  COORDINATION_RUNTIME_SHADOW_BOOTSTRAP_REQUEST_SCHEMA,
  COORDINATION_RUNTIME_SHADOW_REQUEST_SCHEMA,
} from "../../loopx/control_plane/coordination/runtime_shadow.ts";
import { executeTaskLeaseAcquire } from "../../loopx/control_plane/work_items/task_lease_acquire.ts";
import {
  TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION,
  executeTaskLeaseLifecycle,
} from "../../loopx/control_plane/work_items/task_lease_lifecycle.ts";

function sha256(value: unknown): string {
  return createHash("sha256").update(canonicalAuthorityBytes(value)).digest("hex");
}

function withTodoReadModel<T extends Record<string, unknown>>(projection: T): T {
  const todos = projection.todos as Record<string, unknown>[];
  return {
    ...projection,
    todo_read_model: {
      schema_version: TODO_CANONICAL_READ_RECORD_SCHEMA,
      todo_count: todos.length,
      records_sha256: sha256(todos),
      contract_fields: [...TODO_CANONICAL_READ_RECORD_FIELDS],
    },
  };
}

function todoRecord(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: "todo_item_v0",
    todo_id: "todo_a",
    role: "agent",
    status: "open",
    done: false,
    text: "Qualify canonical Todo semantics",
    archive_state: "active",
    source_section: "Agent Todo",
    ...overrides,
  };
}

async function claimSeededTodo(
  root: string,
  todo: Record<string, unknown>,
  operationId: string,
) {
  const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  await store.commitAuthority({
    expected_provider_revision: null,
    operation_id: "seed",
    events: [],
    next_projection: withTodoReadModel({
      goal_id: "goal-a",
      handoff_mode: "soft_claim",
      todos: [todo],
      leases: [],
    }),
    receipts: [],
  });
  const result = await claimLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
    role: "agent",
    claimed_by: "agent-a",
    actor_agent_id: "agent-a",
    registered_agents: ["agent-a", "agent-b"],
    operation_id: operationId,
    observed_at: "2026-09-05T04:30:00Z",
    dry_run: false,
  });
  return { result, receipt: await store.readReceipt(operationId) };
}

async function qualifiedShadow(root: string) {
  const baseline = withTodoReadModel({
    goal_id: "goal-a",
    todos: [todoRecord()],
    leases: [],
  });
  const bootstrapped = await bootstrapCoordinationRuntimeShadow({
    schema_version: COORDINATION_RUNTIME_SHADOW_BOOTSTRAP_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "bootstrap:goal-a:state-0",
    source_version: "state:0",
    projection: baseline,
  });
  assert.equal(bootstrapped.status, "applied");
  const projection = withTodoReadModel({
    ...baseline,
    todos: [todoRecord({ claimed_by: "agent-a" })],
  });
  const mirrored = await commitCoordinationRuntimeShadow({
    schema_version: COORDINATION_RUNTIME_SHADOW_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "todo:goal-a:todo_a:claim-1",
    event_kind: "todo_claim",
    source_version: "state:1",
    projection,
  });
  assert.equal(mirrored.status, "applied");
  return { projection, providerRevision: String(mirrored.provider_revision) };
}

function promotionRequest(
  root: string,
  projection: Record<string, unknown>,
  providerRevision: string,
) {
  const digest = sha256(projection);
  return {
    schema_version: LOCAL_COORDINATION_PROMOTION_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "promote:goal-a:state-1",
    expected_shadow_provider_revision: providerRevision,
    expected_shadow_projection_sha256: digest,
    minimum_operations: 1,
    required_event_kinds: ["todo_claim"],
    writer_fence: {
      schema_version: LEGACY_COORDINATION_WRITER_FENCE_SCHEMA,
      state: "engaged",
      goal_id: "goal-a",
      fence_id: "legacy-writer-fence:goal-a:state-1",
      source_version: "state:1",
      source_projection_sha256: digest,
      expected_shadow_provider_revision: providerRevision,
    },
  };
}

async function engageFence(request: ReturnType<typeof promotionRequest>) {
  const result = await engageLegacyCoordinationWriterFence({
    schema_version: LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
    runtime_root: request.runtime_root,
    goal_id: request.goal_id,
    fence: request.writer_fence,
  });
  assert.equal(result.status, "applied");
}

test("legacy write guard flips from allowed to fail-closed after the durable fence", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-legacy-writer-fence-"));
  const shadow = await qualifiedShadow(root);
  const request = promotionRequest(root, shadow.projection, shadow.providerRevision);
  const check = {
    schema_version: LEGACY_COORDINATION_WRITE_CHECK_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
  };
  assert.equal((await checkLegacyCoordinationWriteAllowed(check)).status, "allowed");
  await engageFence(request);
  const replayed = await engageLegacyCoordinationWriterFence({
    schema_version: LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
    runtime_root: request.runtime_root,
    goal_id: request.goal_id,
    fence: request.writer_fence,
  });
  assert.equal(replayed.status, "replayed");
  const conflict = await engageLegacyCoordinationWriterFence({
    schema_version: LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
    runtime_root: request.runtime_root,
    goal_id: request.goal_id,
    fence: { ...request.writer_fence, fence_id: "legacy-writer-fence:other" },
  });
  assert.equal(conflict.status, "conflict");
  const blocked = await checkLegacyCoordinationWriteAllowed(check);
  assert.equal(blocked.status, "blocked");
  assert.equal(blocked.reason_code, "legacy_coordination_writer_fenced");
  assert.equal(blocked.authority_mode, "file_v0");
});

test("explicit local promotion requires qualified shadow and creates replayable canonical authority", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-promote-"));
  const shadow = await qualifiedShadow(root);
  const request = promotionRequest(root, shadow.projection, shadow.providerRevision);
  await engageFence(request);

  const applied = await promoteLocalCoordinationAuthority(request);
  assert.equal(applied.status, "applied");
  assert.equal(applied.legacy_writer_fenced, true);
  assert.equal(applied.legacy_fallback_used, false);
  assert.equal(applied.canonical_authority, "file_v0");

  const advanced = await mutateLocalCoordinationAuthority({
    schema_version: LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "todo:goal-a:todo_a:advance-after-promotion",
    expected_provider_revision: applied.provider_revision,
    mutations: [{
      kind: "todo_upsert",
      todo: todoRecord({ status: "in_progress", claimed_by: "agent-a" }),
    }],
  });
  assert.equal(advanced.status, "applied");

  const partialReplacement = await mutateLocalCoordinationAuthority({
    schema_version: LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "todo:goal-a:todo_a:partial-after-promotion",
    expected_provider_revision: advanced.provider_revision,
    mutations: [{
      kind: "todo_upsert",
      todo: {
        schema_version: "todo_item_v0",
        todo_id: "todo_a",
        role: "agent",
        status: "done",
        done: true,
        text: "Qualify canonical Todo semantics",
        archive_state: "active",
        source_section: "Agent Todo",
      },
    }],
  });
  assert.equal(partialReplacement.status, "failed");
  assert.equal(partialReplacement.reason_code, "invalid_coordination_mutation");
  assert.match(String(partialReplacement.reason ?? ""), /omits existing fields: claimed_by/);
  const unchanged = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(unchanged.status, "found");
  assert.equal((unchanged.todo as Record<string, unknown>).claimed_by, "agent-a");
  assert.equal((unchanged.todo as Record<string, unknown>).status, "in_progress");

  const replayed = await promoteLocalCoordinationAuthority(request);
  assert.equal(replayed.status, "replayed");
  assert.equal(replayed.provider_revision, applied.provider_revision);

  const read = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(read.status, "found");
  assert.equal((read.todo as Record<string, unknown>).claimed_by, "agent-a");
  assert.equal((read.todo as Record<string, unknown>).status, "in_progress");
  assert.equal(read.legacy_fallback_used, false);
});

test("local promotion fences shadow revision, digest, and writer-fence identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-promote-fence-"));
  const shadow = await qualifiedShadow(root);
  const request = promotionRequest(root, shadow.projection, shadow.providerRevision);

  const missingFence = await promoteLocalCoordinationAuthority(request);
  assert.equal(missingFence.status, "failed");
  assert.equal(missingFence.reason_code, "local_authority_writer_fence_not_verified");
  await engageFence(request);

  const staleRevision = await promoteLocalCoordinationAuthority({
    ...request,
    expected_shadow_provider_revision: "file:stale",
  });
  assert.equal(staleRevision.status, "failed");
  assert.equal(staleRevision.reason_code, "local_authority_writer_fence_revision_mismatch");

  const mismatchedFence = await promoteLocalCoordinationAuthority({
    ...request,
    writer_fence: { ...request.writer_fence, source_projection_sha256: "0".repeat(64) },
  });
  assert.equal(mismatchedFence.status, "failed");
  assert.equal(
    mismatchedFence.reason_code,
    "local_authority_writer_fence_projection_mismatch",
  );

  const unqualified = await promoteLocalCoordinationAuthority({
    ...request,
    minimum_operations: 2,
  });
  assert.equal(unqualified.status, "failed");
  assert.equal(unqualified.reason_code, "local_authority_shadow_not_qualified");
  const canonical = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  assert.equal((await canonical.loadAuthority()).status, "missing");
});

test("promotion and provider list fail closed without exact Todo consumer semantics", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-semantic-fence-"));
  const incomplete = {
    goal_id: "goal-a",
    todos: [{ todo_id: "todo_a", role: "agent", status: "open" }],
    leases: [],
  };
  const bootstrapped = await bootstrapCoordinationRuntimeShadow({
    schema_version: COORDINATION_RUNTIME_SHADOW_BOOTSTRAP_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "bootstrap:goal-a:incomplete",
    source_version: "state:0",
    projection: incomplete,
  });
  assert.equal(bootstrapped.status, "applied");
  const mirrored = await commitCoordinationRuntimeShadow({
    schema_version: COORDINATION_RUNTIME_SHADOW_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "todo:goal-a:incomplete",
    event_kind: "todo_update",
    source_version: "state:1",
    projection: incomplete,
  });
  assert.equal(mirrored.status, "applied");
  const request = promotionRequest(root, incomplete, String(mirrored.provider_revision));
  request.required_event_kinds = ["todo_update"];
  await engageFence(request);
  const rejected = await promoteLocalCoordinationAuthority(request);
  assert.equal(rejected.status, "failed");
  assert.equal(rejected.reason_code, "local_authority_shadow_not_qualified");

  const canonical = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  const committed = await canonical.commitAuthority({
    expected_provider_revision: null,
    operation_id: "unsafe:test-only",
    events: [{ schema_version: "test_v0" }],
    next_projection: incomplete,
    receipts: [],
  });
  assert.equal(committed.status, "applied");
  const listed = await listLocalCoordinationTodos({
    schema_version: LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
  });
  assert.equal(listed.status, "failed");
  assert.equal(listed.reason_code, "invalid_local_coordination_todo_list_request");
});

test("local canonical runtime reads and mutates only the provider head", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-runtime-"));
  const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  const initial = await store.commitAuthority({
    expected_provider_revision: null,
    operation_id: "promote:goal-a",
    events: [{ schema_version: "promotion_v0" }],
    next_projection: withTodoReadModel({
      goal_id: "goal-a",
      source_authority: "file_v0",
      todos: [todoRecord()],
      leases: [],
    }),
    receipts: [],
  });
  assert.equal(initial.status, "applied");
  if (initial.status !== "applied") return;

  const before = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(before.status, "found");
  assert.equal(before.decision_read_from_provider, true);
  assert.equal(before.legacy_fallback_used, false);

  const mutation = await mutateLocalCoordinationAuthority({
    schema_version: LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    operation_id: "claim:goal-a:todo_a:1",
    expected_provider_revision: initial.provider_revision,
    mutations: [{
      kind: "todo_upsert",
      todo: todoRecord({ claimed_by: "agent-a" }),
    }],
  });
  assert.equal(mutation.status, "applied");
  assert.equal(mutation.decision_read_from_provider, true);
  assert.equal(mutation.legacy_fallback_used, false);

  const after = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal((after.todo as Record<string, unknown>).claimed_by, "agent-a");

  const listed = await listLocalCoordinationTodos({
    schema_version: LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
  });
  assert.equal(listed.status, "loaded");
  assert.deepEqual(listed.todo_ids, ["todo_a"]);
  assert.equal((listed.todos as Record<string, unknown>[])[0]?.claimed_by, "agent-a");
  assert.equal(listed.decision_read_from_provider, true);
  assert.equal(listed.legacy_fallback_used, false);
});

test("provider-first Todo claim preserves the complete record and is replay-safe", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-claim-"));
  const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  const richTodo = todoRecord({
    priority: "P0",
    action_kind: "implement",
    required_capabilities: ["network"],
    excluded_agents: ["agent-b"],
    note: "preserve this field",
  });
  const initial = await store.commitAuthority({
    expected_provider_revision: null,
    operation_id: "promote:claim-test",
    events: [{ schema_version: "promotion_v0" }],
    next_projection: withTodoReadModel({
      goal_id: "goal-a",
      handoff_mode: "soft_claim",
      todos: [richTodo],
      leases: [],
    }),
    receipts: [],
  });
  assert.equal(initial.status, "applied");

  const request = {
    schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
    role: "agent",
    claimed_by: " Agent-A ",
    actor_agent_id: "AGENT-A",
    registered_agents: ["agent-a", "agent-b"],
    operation_id: "todo-claim:goal-a:todo_a:one",
    observed_at: "2026-09-05T04:30:00Z",
    dry_run: false,
  };
  const applied = await claimLocalCoordinationTodo(request);
  assert.equal(applied.status, "applied", JSON.stringify(applied));
  assert.equal(applied.changed, true);
  assert.equal(applied.source_authority, "file_v0");
  assert.equal(
    (applied.mutation_authority as Record<string, unknown>).mode,
    "registered_peer_actor",
  );

  const read = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(read.status, "found");
  assert.deepEqual(read.todo, {
    ...richTodo,
    claimed_by: "agent-a",
    updated_at: (read.todo as Record<string, unknown>).updated_at,
  });

  const replayed = await claimLocalCoordinationTodo(request);
  assert.equal(replayed.status, "replayed");

  const repeated = await claimLocalCoordinationTodo({
    ...request,
    operation_id: "todo-claim:goal-a:todo_a:two",
  });
  assert.equal(repeated.status, "no_change");
  assert.equal(repeated.changed, false);
});

test("agent id normalization folds any whitespace run like the Python kernel", async () => {
  // Parity with loopx/control_plane/todos/contract.py normalize_todo_claimed_by:
  // compact_todo_text collapses every whitespace run (tabs included) into one
  // space before mapping it to "-", so the same claim command keeps working
  // before and after promotion.
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-claim-tab-"));
  const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  const seeded = await store.commitAuthority({
    expected_provider_revision: null,
    operation_id: "promote:claim-tab-test",
    events: [{ schema_version: "promotion_v0" }],
    next_projection: withTodoReadModel({
      goal_id: "goal-a",
      handoff_mode: "soft_claim",
      todos: [todoRecord()],
      leases: [],
    }),
    receipts: [],
  });
  assert.equal(seeded.status, "applied");

  const applied = await claimLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
    role: "agent",
    claimed_by: "Agent\tA",
    actor_agent_id: "Agent \t A",
    registered_agents: ["agent-a"],
    operation_id: "todo-claim:goal-a:todo_a:tab",
    observed_at: "2026-09-05T04:30:00Z",
    dry_run: false,
  });
  assert.equal(applied.status, "applied", JSON.stringify(applied));

  const read = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(read.status, "found");
  assert.equal((read.todo as Record<string, unknown>).claimed_by, "agent-a");
});

test("one TypeScript decision owns promoted and legacy Todo claims", () => {
  const input = {
    goal_id: "goal-a",
    todo_id: "todo_a",
    claimed_by: "agent-a",
    actor_agent_id: "agent-a",
    expected_role: "agent",
    registered_agents: ["agent-a", "agent-b"],
    operation_id: "decision-only",
    dry_run: true,
    now: new Date(0),
  };
  const accepted = evaluateCoordinationTodoClaimDecision(todoRecord(), input);
  assert.equal(accepted.status, "accepted");
  assert.equal(
    (accepted.mutation_authority as Record<string, unknown>).mode,
    "registered_peer_actor",
  );

  const rejected = evaluateCoordinationTodoClaimDecision(
    todoRecord({ excluded_agents: [" Agent-A "] }),
    input,
  );
  assert.equal(rejected.status, "rejected");
  assert.equal(rejected.reason_code, "actor_excluded");

  assert.throws(
    () => evaluateCoordinationTodoClaimDecision(
      todoRecord({ excluded_agents: ["agent-a", " Agent-A "] }),
      input,
    ),
    /unique public-safe agent ids/,
  );
});

test("the shared claim decision rejects every pre-commit lifecycle boundary", () => {
  const base: Parameters<typeof evaluateCoordinationTodoClaimDecision>[1] = {
    goal_id: "goal-a",
    todo_id: "todo_a",
    claimed_by: "agent-a",
    actor_agent_id: "agent-a",
    expected_role: "agent",
    registered_agents: ["agent-a", "agent-b"],
    operation_id: "decision-only",
    dry_run: true,
    now: new Date(0),
  };
  const cases: Array<[Record<string, unknown>, Partial<typeof base>, string]> = [
    [{ status: "done" }, {}, "todo_not_open"],
    [{ archive_state: "archive" }, {}, "todo_archived"],
    [{ role: "user" }, { expected_role: "user" }, "todo_not_agent"],
    [{ removed_continuation_policy: "author_reviewer_handoff" }, {},
      "removed_continuation_policy"],
    [{ claimed_by: "agent-b" }, {}, "claim_owner_mismatch"],
    [{}, { actor_agent_id: "agent-b" }, "claim_actor_mismatch"],
    [{}, { actor_agent_id: null }, "actor_required"],
  ];
  for (const [todoOverrides, inputOverrides, code] of cases) {
    const result = evaluateCoordinationTodoClaimDecision(
      todoRecord(todoOverrides),
      { ...base, ...inputOverrides },
    );
    assert.equal(result.status, "rejected", code);
    assert.equal(result.reason_code, code);
  }
});

test("promoted claim rejection preserves the public result envelope", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-claim-rejection-envelope-"));
  const { result: rejected, receipt } = await claimSeededTodo(
    root,
    todoRecord({ status: "done", done: true }),
    "claim-rejected",
  );

  assert.equal(
    rejected.schema_version,
    COORDINATION_TODO_CLAIM_RESULT_SCHEMA,
    JSON.stringify(rejected),
  );
  assert.equal(rejected.status, "failed");
  assert.equal(rejected.reason_code, "todo_not_open", JSON.stringify(rejected));
  assert.deepEqual(receipt, { status: "missing" });
});

test("promoted claim normalizes persisted excluded-agent identities", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-claim-excluded-normalize-"));
  const { result: rejected, receipt } = await claimSeededTodo(
    root,
    todoRecord({ excluded_agents: [" Agent-A "] }),
    "claim-excluded",
  );

  assert.equal(rejected.schema_version, COORDINATION_TODO_CLAIM_RESULT_SCHEMA);
  assert.equal(rejected.status, "failed");
  assert.equal(rejected.reason_code, "actor_excluded");
  assert.deepEqual(receipt, { status: "missing" });
});

for (const native of [false, true]) {
  test(`claim rejects malformed previews and replays historical intent (${native ? "native" : "v0"})`, async () => {
    const root = await mkdtemp(join(tmpdir(), "loopx-claim-intent-"));
    const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
    const todo = todoRecord();
    if (native) {
      todo.schema_version = TODO_DOMAIN_ITEM_SCHEMA;
      delete todo.source_section;
    }
    const projection = withTodoReadModel({
      goal_id: "goal-a", handoff_mode: "hard_lease", todos: [todo],
      leases: [{todo_id: "todo_a", owner: "agent-a", status: "active",
        expires_at: "2026-09-05T05:00:00Z"}],
    });
    if (native) {
      Object.assign(projection, {todo_read_model: {
        schema_version: TODO_DOMAIN_READ_RECORD_SCHEMA,
        todo_count: 1, records_sha256: sha256([todo]),
        contract_fields: [...TODO_DOMAIN_RECORD_CONTRACT.fields],
      }});
    }
    await store.commitAuthority({
      expected_provider_revision: null, operation_id: "seed", events: [],
      next_projection: projection, receipts: [],
    });
    const request = {
      schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
      runtime_root: root, goal_id: "goal-a", todo_id: "todo_a", role: "agent",
      claimed_by: "agent-a", actor_agent_id: "agent-a", registered_agents: ["agent-a", "agent-b"],
      operation_id: "claim-a", observed_at: "2026-09-05T04:30:00Z", dry_run: false,
    };
    const before = await store.loadAuthority();
    for (const dry_run of ["true", 1, null, undefined]) {
      const rejected = await claimLocalCoordinationTodo({...request, dry_run});
      assert.equal(rejected.reason_code, "invalid_local_coordination_todo_claim_request");
      assert.deepEqual(await store.loadAuthority(), before);
      assert.deepEqual(await store.readReceipt("claim-a"), {status: "missing"});
    }
    assert.equal((await claimLocalCoordinationTodo({...request, dry_run: true})).status, "planned");
    assert.deepEqual(await store.loadAuthority(), before);
    const applied = await claimLocalCoordinationTodo(request);
    assert.equal(applied.status, "applied", JSON.stringify(applied));
    const claimed = await store.loadAuthority();
    assert.equal(claimed.status, "loaded");
    if (claimed.status !== "loaded") return;
    const claimedTodo = (claimed.head.todos as Record<string, unknown>[])[0]!;
    if (native) {
      assert.equal(claimedTodo.source_section, undefined);
      assert.equal(claimedTodo.index, undefined);
    }
    // Operation B completes/archives/reassigns the Todo. A retry of A must
    // return A's receipt even after its actor registration and lease expire.
    const completed = await mutateLocalCoordinationAuthority({
      schema_version: LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
      runtime_root: root, goal_id: "goal-a", operation_id: "complete-b",
      expected_provider_revision: claimed.provider_revision,
      mutations: [{kind: "todo_upsert", todo: {...claimedTodo, status: "done", done: true,
        archive_state: "archive", claimed_by: "agent-b"}}],
    });
    assert.equal(completed.status, "applied");
    const afterB = await store.loadAuthority();
    for (const registered_agents of [["agent-b"], []]) {
      const replay = await claimLocalCoordinationTodo({...request,
        registered_agents, observed_at: "2026-09-06T04:30:00Z"});
      assert.equal(replay.status, "replayed", JSON.stringify(replay));
      assert.equal(replay.changed, false);
      assert.equal(replay.provider_revision, applied.provider_revision);
      assert.deepEqual(replay.original_receipt, applied.original_receipt);
      assert.equal(replay.updated_at, applied.updated_at);
    }
    for (const changedIntent of [{claimed_by: "agent-b"}, {actor_agent_id: "agent-b"},
      {todo_id: "todo_b"}, {role: "user"}, {dry_run: true}]) {
      const mismatch = await claimLocalCoordinationTodo({...request, ...changedIntent});
      assert.equal(mismatch.reason_code, "coordination_operation_identity_mismatch");
    }
    assert.deepEqual(await store.loadAuthority(), afterB);
    const fresh = await claimLocalCoordinationTodo({...request, operation_id: "claim-new"});
    assert.equal(fresh.reason_code, "todo_not_open");
  });

  test(`no-change claim is a durable terminal result (${native ? "native" : "v0"})`, async () => {
    for (const later of [{claimed_by: null}, {claimed_by: "agent-b"},
      {status: "done", done: true, archive_state: "archive"}]) {
      const root = await mkdtemp(join(tmpdir(), "loopx-claim-no-change-"));
      const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
      const todo = todoRecord({claimed_by: "agent-a", note: "preserve original bytes"});
      if (native) {
        todo.schema_version = TODO_DOMAIN_ITEM_SCHEMA;
        delete todo.source_section;
      }
      const projection = withTodoReadModel({goal_id: "goal-a", handoff_mode: "soft_claim",
        todos: [todo], leases: []});
      if (native) {
        Object.assign(projection, {todo_read_model: {
          schema_version: TODO_DOMAIN_READ_RECORD_SCHEMA, todo_count: 1,
          records_sha256: sha256([todo]), contract_fields: [...TODO_DOMAIN_RECORD_CONTRACT.fields],
        }});
      }
      await store.commitAuthority({expected_provider_revision: null, operation_id: "seed",
        events: [], next_projection: projection, receipts: []});
      const before = await store.loadAuthority();
      const request = {
        schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
        runtime_root: root, goal_id: "goal-a", todo_id: "todo_a", role: "agent",
        claimed_by: "agent-a", actor_agent_id: "agent-a", registered_agents: ["agent-a"],
        operation_id: "claim-no-change", observed_at: "2026-09-05T04:30:00Z", dry_run: false,
      };
      const preview = await claimLocalCoordinationTodo({...request, dry_run: true});
      assert.equal(preview.status, "no_change");
      assert.equal(preview.changed, false);
      assert.deepEqual(await store.readReceipt(request.operation_id), {status: "missing"});
      const freshEmpty = await claimLocalCoordinationTodo({...request, registered_agents: []});
      assert.equal(freshEmpty.reason_code, "actor_not_registered");
      assert.deepEqual(await store.loadAuthority(), before);
      const accepted = await claimLocalCoordinationTodo(request);
      assert.equal(accepted.status, "no_change", JSON.stringify(accepted));
      assert.equal(accepted.changed, false);
      const receipt = await store.readReceipt(request.operation_id);
      assert.equal(receipt.status, "found");
      const afterA = await store.loadAuthority();
      assert.equal(afterA.status, "loaded");
      if (afterA.status !== "loaded" || before.status !== "loaded") return;
      assert.deepEqual(afterA.head, before.head);
      assert.notEqual(afterA.provider_revision, before.provider_revision);
      const scan = await store.scanCommitted(before.cursor, 10);
      assert.equal(scan.status, "page");
      if (scan.status !== "page") return;
      assert.equal(scan.transactions.length, 1);
      assert.deepEqual(scan.transactions[0]?.events, []);
      const changed = await mutateLocalCoordinationAuthority({
        schema_version: LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
        runtime_root: root, goal_id: "goal-a", operation_id: "later-change",
        expected_provider_revision: afterA.provider_revision,
        mutations: [{kind: "todo_upsert", todo: {...todo, ...later}}],
      });
      assert.equal(changed.status, "applied");
      const afterB = await store.loadAuthority();
      const replayed = await claimLocalCoordinationTodo({...request, registered_agents: [],
        observed_at: "2026-09-06T04:30:00Z"});
      assert.deepEqual(replayed, {...accepted, status: "replayed"});
      for (const changedIntent of [{claimed_by: "agent-b"}, {actor_agent_id: "agent-b"},
        {todo_id: "todo_b"}, {role: "user"}, {dry_run: true}]) {
        assert.equal((await claimLocalCoordinationTodo({...request, ...changedIntent})).reason_code,
          "coordination_operation_identity_mismatch");
      }
      for (const registered_agents of [null, "agent-a", [null], [42], ["invalid!"],
        ["agent-a", "agent-a"]]) {
        assert.equal((await claimLocalCoordinationTodo({...request, registered_agents})).status, "failed");
      }
      assert.deepEqual(await store.loadAuthority(), afterB);
      assert.deepEqual(await store.readReceipt(request.operation_id), receipt);
    }
  });
}

test("receipt-only claims require head CAS and recover a lost commit response", async () => {
  for (const fault of ["conflict", "lost_response"] as const) {
    const root = await mkdtemp(join(tmpdir(), "loopx-claim-no-change-fault-"));
    const directory = join(root, "authority", "file-v0");
    const store = new FileAuthorityStore(directory, "goal-a");
    const projection = withTodoReadModel({goal_id: "goal-a", todos: [
      todoRecord({claimed_by: "agent-a"}),
    ], leases: []});
    await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
      events: [], receipts: [], next_projection: projection});
    const before = await store.loadAuthority();
    assert.equal(before.status, "loaded");
    if (before.status !== "loaded") return;
    class FaultStore extends FileAuthorityStore {
      override async commitAuthority(commit: AuthorityStoreCommit) {
        if (fault === "conflict") {
          const concurrent = await store.commitAuthority({...commit, operation_id: "concurrent",
            receipts: [], next_projection: withTodoReadModel({...projection,
              todos: [todoRecord({claimed_by: "agent-b"})]})});
          assert.equal(concurrent.status, "applied");
          return super.commitAuthority(commit);
        }
        assert.equal((await super.commitAuthority(commit)).status, "applied");
        return {status: "ambiguous" as const, reason_code: "lost_response",
          reason: "commit response lost after persistence"};
      }
    }
    const result = await claimLocalCoordinationTodo({
      schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
      runtime_root: root, goal_id: "goal-a", todo_id: "todo_a", role: "agent",
      claimed_by: "agent-a", actor_agent_id: "agent-a", registered_agents: ["agent-a"],
      operation_id: "no-change", observed_at: "2026-09-05T04:30:00Z", dry_run: false,
    }, {createStore: () => new FaultStore(directory, "goal-a")});
    assert.equal(result.changed, false);
    assert.equal(result.status, fault === "conflict" ? "conflict" : "recovered");
    const receipt = await store.readReceipt("no-change");
    assert.equal(receipt.status, fault === "conflict" ? "missing" : "found");
    const after = await store.loadAuthority();
    assert.equal(after.status, "loaded");
    if (after.status !== "loaded") return;
    if (fault === "conflict") {
      assert.equal((after.head.todos as Record<string, unknown>[])[0]?.claimed_by, "agent-b");
    } else {
      assert.deepEqual(after.head, before.head);
      assert.ok(result.original_receipt);
    }
  }
});

test("provider-first Todo claim validates authority and hard-lease ownership", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-claim-gates-"));
  const store = new FileAuthorityStore(join(root, "authority", "file-v0"), "goal-a");
  const initial = await store.commitAuthority({
    expected_provider_revision: null,
    operation_id: "promote:claim-gates",
    events: [{ schema_version: "promotion_v0" }],
    next_projection: withTodoReadModel({
      goal_id: "goal-a",
      handoff_mode: "hard_lease",
      todos: [todoRecord({ excluded_agents: ["agent-b"] })],
      leases: [],
    }),
    receipts: [],
  });
  assert.equal(initial.status, "applied");
  const base = {
    schema_version: LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
    role: "agent",
    actor_agent_id: "agent-a",
    registered_agents: ["agent-a", "agent-b"],
    operation_id: "todo-claim:goal-a:todo_a:gated",
    observed_at: "2026-09-05T04:30:00Z",
    dry_run: false,
  };

  const mismatch = await claimLocalCoordinationTodo({
    ...base,
    claimed_by: "agent-b",
  });
  assert.equal(mismatch.reason_code, "claim_actor_mismatch");

  const missingLease = await claimLocalCoordinationTodo({
    ...base,
    claimed_by: "agent-a",
  });
  assert.equal(missingLease.reason_code, "handoff_mode_requires_lease");

  const dryRun = await claimLocalCoordinationTodo({
    ...base,
    claimed_by: "agent-a",
    dry_run: true,
  });
  assert.equal(dryRun.reason_code, "handoff_mode_requires_lease");
  const unchanged = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal((unchanged.todo as Record<string, unknown>).claimed_by, undefined);
});

test("local canonical runtime never falls back when provider state is missing", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-missing-"));
  const result = await readLocalCoordinationTodo({
    schema_version: LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA,
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_a",
  });
  assert.equal(result.status, "missing");
  assert.equal(result.decision_read_from_provider, true);
  assert.equal(result.legacy_fallback_used, false);
});

test("engaged promotion fence blocks every native legacy task-lease writer", async () => {
  const root = await mkdtemp(join(tmpdir(), "loopx-local-authority-lease-fence-"));
  const shadow = await qualifiedShadow(root);
  const request = promotionRequest(root, shadow.projection, shadow.providerRevision);
  await engageFence(request);

  const authorityPath = join(root, "authority-source.json");
  const authorityContent = "authority-v1";
  await writeFile(authorityPath, authorityContent, "utf8");
  const authority = {
    handoff_mode: "hard_lease",
    registered_agent_candidates: [["agent-a"]],
    todos: [{
      todo_id: "todo_abc",
      status: "open",
      claimed_by: "agent-a",
      role: "agent",
      task_class: "advancement_task",
    }],
    todo_projection_error: null,
    source_receipts: [{
      source_id: "authority",
      path: authorityPath,
      state: "file",
      sha256: createHash("sha256").update(authorityContent).digest("hex"),
    }],
  };
  const acquire = await executeTaskLeaseAcquire({
    schema_version: "loopx_task_lease_acquire_native_v0",
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_abc",
    owner: "agent-a",
    idempotency_key: "lease:fenced-acquire",
    write_scopes: [],
    ttl_seconds: 60,
    expected_version: null,
    authority,
  });
  assert.equal(acquire.ok, false);
  assert.equal(acquire.error_code, "legacy_coordination_writer_fenced");

  const renew = await executeTaskLeaseLifecycle({
    schema_version: TASK_LEASE_LIFECYCLE_REQUEST_SCHEMA_VERSION,
    operation: "renew",
    runtime_root: root,
    goal_id: "goal-a",
    todo_id: "todo_abc",
    owner: "agent-a",
    idempotency_key: "lease:fenced-renew",
    expected_version: 1,
    ttl_seconds: 60,
    new_owner: null,
    new_idempotency_key: null,
    authority,
  });
  assert.equal(renew.ok, false);
  assert.equal(renew.error_code, "legacy_coordination_writer_fenced");
});
