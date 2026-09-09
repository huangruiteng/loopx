import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { FileAuthorityStore } from "../../loopx/control_plane/coordination/file_authority_store.ts";
import { canonicalAuthoritySha256 } from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {
  TODO_DOMAIN_ITEM_SCHEMA, TODO_DOMAIN_READ_RECORD_SCHEMA, TODO_DOMAIN_RECORD_CONTRACT,
} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import { executeCoordinationTodoUpdate } from "../../loopx/control_plane/coordination/todo_update.ts";

function todo(overrides: Record<string, unknown> = {}) {
  return {schema_version: TODO_DOMAIN_ITEM_SCHEMA, todo_id: "todo_a", role: "agent",
    status: "open", done: false, text: "Old text", archive_state: "active",
    claimed_by: "agent-a", note: "old note", ...overrides};
}

async function seeded(overrides: Record<string, unknown> = {}) {
  const root = await mkdtemp(join(tmpdir(), "loopx-todo-update-"));
  const store = new FileAuthorityStore(root, "goal-a");
  const records = [todo(overrides)];
  if (records[0]!.claimed_by === null) Reflect.deleteProperty(records[0]!, "claimed_by");
  await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
    events: [], receipts: [], next_projection: {goal_id: "goal-a", todos: records, leases: [],
      todo_read_model: {schema_version: TODO_DOMAIN_READ_RECORD_SCHEMA, todo_count: 1,
        records_sha256: canonicalAuthoritySha256(records),
        contract_fields: [...TODO_DOMAIN_RECORD_CONTRACT.fields]}}});
  const request = {goal_id: "goal-a", todo_id: "todo_a", expected_role: "agent",
    actor_agent_id: "agent-a", registered_agents: ["agent-a", "agent-b"],
    operation_id: "update-a", patch: {text: "New text"}, clear_fields: ["note"],
    dry_run: false, now: new Date("2026-09-05T23:00:00Z")};
  return {store, request};
}

test("provider-first update commits complete record and replays by intent", async () => {
  const {store, request} = await seeded();
  const preview = await executeCoordinationTodoUpdate(store, {...request, dry_run: true});
  assert.equal(preview.status, "planned");
  const applied = await executeCoordinationTodoUpdate(store, request);
  assert.equal(applied.status, "applied");
  const head = await store.loadAuthority();
  assert.equal(head.status, "loaded");
  if (head.status !== "loaded") return;
  const updated = (head.head.todos as Record<string, unknown>[])[0]!;
  assert.equal(updated.text, "New text");
  assert.equal(updated.note, undefined);
  assert.equal(updated.claimed_by, "agent-a");
  assert.equal(updated.last_actor_agent_id, "agent-a");
  assert.equal((await executeCoordinationTodoUpdate(store, request)).status, "replayed");
  assert.equal((await executeCoordinationTodoUpdate(store, {...request,
    patch: {text: "Different"}})).reason_code, "coordination_operation_identity_mismatch");
});

test("unclaimed text edits are claim-neutral, including preview and replay", async () => {
  const {store, request} = await seeded({claimed_by: null});
  const before = await store.loadAuthority();
  for (const actor_agent_id of [null, "unknown"]) {
    assert.equal((await executeCoordinationTodoUpdate(store, {...request, actor_agent_id})).reason_code,
      "actor_not_registered");
  }
  assert.equal((await executeCoordinationTodoUpdate(store, {...request, dry_run: true})).status, "planned");
  assert.deepEqual(await store.loadAuthority(), before);
  assert.equal((await executeCoordinationTodoUpdate(store, request)).status, "applied");
  assert.equal((await executeCoordinationTodoUpdate(store, request)).status, "replayed");
  const after = await store.loadAuthority();
  assert.equal(after.status, "loaded");
  if (after.status !== "loaded") return;
  const updated = (after.head.todos as Record<string, unknown>[])[0]!;
  assert.equal(updated.text, "New text");
  assert.equal(updated.note, undefined);
  assert.equal(Object.hasOwn(updated, "claimed_by"), false);
  assert.equal(updated.last_actor_agent_id, "agent-a");
});

test("unclaimed edits preserve actor exclusion and binding fences", async () => {
  for (const [overrides, reason] of [
    [{excluded_agents: ["agent-a"]}, "actor_excluded"],
    [{bound_agent: "agent-b"}, "bound_agent_mismatch"],
  ] as const) {
    const {store, request} = await seeded({claimed_by: null, ...overrides});
    const before = await store.loadAuthority();
    assert.equal((await executeCoordinationTodoUpdate(store, request)).reason_code, reason);
    assert.deepEqual(await store.loadAuthority(), before);
    assert.equal((await store.readReceipt(request.operation_id)).status, "missing");
  }
});

test("provider-first update rejects authority and lifecycle escalation", async () => {
  const {store, request} = await seeded();
  assert.equal((await executeCoordinationTodoUpdate(store, {...request,
    actor_agent_id: "agent-b"})).reason_code, "update_owner_mismatch");
  assert.equal((await executeCoordinationTodoUpdate(store, {...request,
    actor_agent_id: "unknown"})).reason_code, "actor_not_registered");
  for (const patch of [{status: "done"}, {claimed_by: "agent-b"}, {archive_state: "archive"},
    {excluded_agents: ["agent-a"]}, {required_capabilities: ["network"]},
    {required_decision_scopes: ["release"]}, {continuation_policy: "no_followup"},
    {task_repository: "git:example.invalid/repo"}, {successor_todo_ids: ["todo_b"]}]) {
    const result = await executeCoordinationTodoUpdate(store, {...request, patch});
    assert.equal(result.reason_code, "invalid_coordination_todo_update");
  }
  for (const clear_fields of [["excluded_agents"], ["required_capabilities"],
    ["required_decision_scopes"], ["continuation_policy"], ["task_repository"],
    ["successor_todo_ids"]]) {
    const result = await executeCoordinationTodoUpdate(store, {...request,
      patch: {}, clear_fields});
    assert.equal(result.reason_code, "invalid_coordination_todo_update");
  }
});

for (const claimed_by of ["agent-a", null]) {
test(`provider-first update fails closed without a hard-lease execution proof (${claimed_by ?? "unclaimed"})`, async () => {
  const {store, request} = await seeded({claimed_by});
  const head = await store.loadAuthority();
  assert.equal(head.status, "loaded");
  if (head.status !== "loaded") return;
  await store.commitAuthority({operation_id: "seed-lease",
    expected_provider_revision: head.provider_revision, events: [], receipts: [],
    next_projection: {...head.head, handoff_mode: "hard_lease", leases: [{
      todo_id: "todo_a", owner: "agent-a", status: "active",
      expires_at: "2026-09-06T00:00:00Z",
    }]}});
  const result = await executeCoordinationTodoUpdate(store, request);
  assert.equal(result.reason_code, "update_lease_unsupported");
  assert.equal((await store.readReceipt(request.operation_id)).status, "missing");
});
}

test("provider-first update records no-change identity without state mutation", async () => {
  const {store, request} = await seeded();
  const before = await store.loadAuthority();
  const noChangeRequest = {...request,
    patch: {text: "Old text"}, clear_fields: [], operation_id: "no-change"};
  const result = await executeCoordinationTodoUpdate(store, noChangeRequest);
  assert.equal(result.status, "no_change");
  const after = await store.loadAuthority();
  assert.equal(after.status, "loaded");
  if (before.status !== "loaded" || after.status !== "loaded") return;
  assert.deepEqual(after.head, before.head);
  assert.notEqual(after.provider_revision, before.provider_revision);
  // A consumed no-change identity must not overwrite a later edit on retry.
  assert.equal((await executeCoordinationTodoUpdate(store, request)).status, "applied");
  const later = await store.loadAuthority();
  const replay = await executeCoordinationTodoUpdate(store, noChangeRequest);
  assert.equal(replay.status, "replayed");
  assert.equal(replay.changed, false);
  assert.deepEqual(await store.loadAuthority(), later);
  // Identical parameters under a new attempt are new work, not stale replay.
  assert.equal((await executeCoordinationTodoUpdate(store, {...noChangeRequest,
    operation_id: "independent-reset"})).status, "applied");
});
