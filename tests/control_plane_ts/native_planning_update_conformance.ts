import assert from "node:assert/strict";
import test from "node:test";
import type {AuthorityStore} from "../../loopx/control_plane/coordination/authority_store.ts";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {canonicalAuthoritySha256} from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {executeCoordinationTodoUpdate} from "../../loopx/control_plane/coordination/todo_update.ts";
import {TODO_DOMAIN_ITEM_SCHEMA, TODO_DOMAIN_READ_RECORD_SCHEMA, TODO_DOMAIN_RECORD_CONTRACT,
  TODO_ITEM_SCHEMA, TODO_CANONICAL_READ_RECORD_SCHEMA, TODO_CANONICAL_READ_RECORD_FIELDS}
  from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import type {AuthorityStoreConformanceFactory} from "./authority_store_conformance.ts";
import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

async function head(store: AuthorityStore) {
  const loaded = await store.loadAuthority();
  assert.equal(loaded.status, "loaded");
  if (loaded.status !== "loaded") throw new Error("fixture head missing");
  return loaded;
}

export function registerNativePlanningUpdateConformance(provider: string, factory: AuthorityStoreConformanceFactory) {
  for (const native of [false, true]) {
    test(`${provider}: planning transaction uses complete ${native ? "native" : "legacy"} records and keeps wait generation`, async t => {
      const {store, contender} = await factory(t);
      const goal = "planning-goal";
      const todos: JsonObject[] = [
        {todo_id: "todo_aaa_target", task_class: "advancement_task", claimed_by: "agent-a", note: "retained",
          successor_todo_ids: ["todo_bbb_successor"]},
        {todo_id: "todo_bbb_successor", task_class: "advancement_task"},
        // Deliberately beyond the hot read-model limit: authoring uses the head, not its summary.
        ...Array.from({length: 40}, (_, i) => ({todo_id: `todo_other_${String(i).padStart(2, "0")}`, task_class: "advancement_task"})),
        {todo_id: "todo_zzz_monitor", task_class: "continuous_monitor", material_change_generation: 7},
      ].map(record => ({schema_version: native ? TODO_DOMAIN_ITEM_SCHEMA : TODO_ITEM_SCHEMA,
        role: "agent", status: "open", done: false, text: "Synthetic planning record", archive_state: "active",
        ...(!native ? {source_section: "Agent Todo"} : {}), ...record}));
      const seed = await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
        events: [], receipts: [], next_projection: {goal_id: goal, handoff_mode: "soft_claim", todos, leases: [],
          todo_read_model: {schema_version: native ? TODO_DOMAIN_READ_RECORD_SCHEMA : TODO_CANONICAL_READ_RECORD_SCHEMA,
            todo_count: todos.length, records_sha256: canonicalAuthoritySha256(todos),
            contract_fields: native ? [...TODO_DOMAIN_RECORD_CONTRACT.fields] : [...TODO_CANONICAL_READ_RECORD_FIELDS]}}});
      assert.equal(seed.status, "applied");
      const request = {goal_id: goal, todo_id: "todo_aaa_target", expected_role: "agent", actor_agent_id: "agent-a",
        registered_agents: ["agent-a", "agent-b"], operation_id: "wait",
        patch: {text: "Synthetic planning record"}, clear_fields: [],
        planning_intent: {resume_when: "monitor_changed:todo_zzz_monitor", reason: "Await material change"},
        dry_run: false, now: new Date("2026-09-10T00:00:00Z")};
      const before = await head(store);
      const preview = await executeCoordinationTodoUpdate(store, {...request, dry_run: true});
      assert.equal(preview.status, "planned", JSON.stringify(preview));
      assert.deepEqual(await head(store), before);
      const applied = await executeCoordinationTodoUpdate(store, request);
      assert.equal(applied.status, "applied", JSON.stringify(applied));
      let current = await head(store);
      let target = (current.head.todos as JsonObject[])[0]!;
      assert.equal(target.resume_monitor_generation, 7);
      assert.deepEqual((current.head.todos as JsonObject[]).slice(1), todos.slice(1));
      // Simulate an independent observation at a new canonical revision.
      const observed = structuredClone(current.head);
      (observed.todos as JsonObject[]).at(-1)!.material_change_generation = 8;
      (observed.todo_read_model as JsonObject).records_sha256 = canonicalAuthoritySha256(observed.todos);
      assert.equal((await contender.commitAuthority({operation_id: "observe", expected_provider_revision: current.provider_revision,
        next_projection: observed, events: [], receipts: []})).status, "applied");
      const topology = await executeCoordinationTodoUpdate(store, {...request, operation_id: "topology",
        planning_intent: {successor_todo_ids: ["todo_bbb_successor"], evidence: "Checked dependency"}});
      assert.equal(topology.status, "failed", JSON.stringify(topology));
      assert.match(String(topology.reason), /clear the satisfied resume_when/);
      assert.equal((await store.readReceipt("topology")).status, "missing");
      const evidenceOnly = await executeCoordinationTodoUpdate(store, {...request, operation_id: "evidence",
        planning_intent: {evidence: "Checked dependency"}});
      assert.equal(evidenceOnly.status, "applied", JSON.stringify(evidenceOnly));
      current = await head(store);
      target = (current.head.todos as JsonObject[])[0]!;
      assert.equal(target.resume_monitor_generation, 7, "retained wait must not silently re-arm");
      assert.equal((await executeCoordinationTodoUpdate(store, request)).status, "replayed");
      assert.deepEqual(await head(store), current);
      assert.equal((await executeCoordinationTodoUpdate(store, {...request,
        planning_intent: {reason: "Different request"}})).reason_code, "coordination_operation_identity_mismatch");
      // Lost commit response is recovered from the same durable receipt.
      const lostResponse: AuthorityStore = {storeIdentity: () => store.storeIdentity(),
        loadAuthority: () => store.loadAuthority(), readReceipt: id => store.readReceipt(id),
        scanCommitted: (cursor, limit) => store.scanCommitted(cursor, limit),
        commitAuthority: async input => {await store.commitAuthority(input); return {
          status: "ambiguous", reason_code: "lost_response", reason: "Synthetic lost response"};}};
      const cleared = await executeCoordinationTodoUpdate(lostResponse, {...request, operation_id: "clear",
        planning_intent: {clear_resume_when: true, successor_todo_ids: [], no_followup: false}});
      assert.equal(cleared.status, "recovered", JSON.stringify(cleared));
      target = ((await head(store)).head.todos as JsonObject[])[0]!;
      assert.equal(target.resume_when, undefined);
      assert.equal(target.resume_monitor_generation, undefined);
      assert.deepEqual(target.successor_todo_ids, []);
      assert.equal(target.no_followup, false);
      assert.equal(target.claimed_by, "agent-a");
      assert.equal(target.note, "retained");

      // Force a canonical-head race between plan and CAS; do not recompute against a stale dependency.
      const racing: AuthorityStore = {...lostResponse, commitAuthority: async input => {
        const fresh = await head(contender);
        await contender.commitAuthority({operation_id: "race-winner", expected_provider_revision: fresh.provider_revision,
          next_projection: fresh.head, events: [], receipts: []});
        return store.commitAuthority(input);
      }};
      const conflict = await executeCoordinationTodoUpdate(racing, {...request, operation_id: "race-loser",
        planning_intent: {...request.planning_intent, successor_todo_ids: ["todo_bbb_successor"]}});
      assert.equal(conflict.status, "conflict", JSON.stringify(conflict));
      assert.equal((await store.readReceipt("race-loser")).status, "missing");
      assert.deepEqual(((await head(store)).head.todos as JsonObject[])[0], target);
    });
  }

  test(`${provider}: production-scale planning edit preserves unrelated state and active lease`, async t => {
    const {store} = await factory(t);
    const fixture = productionScaleCoordinationFixture("planning-scale");
    assert.equal((await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
      next_projection: fixture.projection, events: [], receipts: []})).status, "applied");
    const request = {goal_id: "planning-scale", todo_id: fixture.completion_todo_id, expected_role: "agent",
      actor_agent_id: "agent-a", registered_agents: fixture.registered_agents, operation_id: "scale-edit",
      patch: {}, clear_fields: [], planning_intent: {reason: "Bounded planning update", evidence: "Synthetic readback"},
      lease_idempotency_key: fixture.completion_lease_idempotency_key,
      lease_expected_version: fixture.completion_lease_expected_version,
      dry_run: false, now: new Date("2026-09-07T06:00:00Z")};
    const before = await head(store);
    const applied = await executeCoordinationTodoUpdate(store, request);
    assert.equal(applied.status, "applied", JSON.stringify(applied));
    const after = await head(store);
    assert.deepEqual(after.head.leases, before.head.leases);
    const records = after.head.todos as JsonObject[];
    const original = before.head.todos as JsonObject[];
    assert.equal(records.length, fixture.expected_initial_todo_count);
    assert.deepEqual(records.filter(t => t.todo_id !== request.todo_id), original.filter(t => t.todo_id !== request.todo_id));
    assert.equal(records.find(t => t.todo_id === request.todo_id)?.last_actor_agent_id,
      original.find(t => t.todo_id === request.todo_id)?.last_actor_agent_id,
      "planning-only updates preserve legacy actor attribution");
    for (const [operation_id, change] of [
      ["no-proof", {lease_idempotency_key: null, lease_expected_version: null}],
      ["status-change", {planning_intent: {status: "deferred", resume_when: "pr_merged:#123"}}],
      ["wrong-owner", {actor_agent_id: "agent-b"}],
    ] as const) {
      const result = await executeCoordinationTodoUpdate(store, {...request, operation_id, ...change});
      assert.equal(result.status, "failed", JSON.stringify(result));
      if (operation_id === "status-change") assert.equal(result.reason_code, "update_lease_status_transition_unsupported");
      assert.deepEqual(await head(store), after);
      assert.equal((await store.readReceipt(operation_id)).status, "missing");
    }
  });
}
