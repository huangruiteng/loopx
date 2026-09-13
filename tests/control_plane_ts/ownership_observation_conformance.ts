import assert from "node:assert/strict";
import test from "node:test";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {canonicalAuthoritySha256} from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {readCoordinationOwnership} from "../../loopx/control_plane/coordination/ownership_observation.ts";
import type {AuthorityStoreConformanceFactory} from "./authority_store_conformance.ts";
import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

const at = "2026-09-13T00:00:00Z";
export function registerOwnershipObservationConformance(provider: string, factory: AuthorityStoreConformanceFactory) {
  for (const scenario of ["empty", "full_conflict", "bounded", "malformed_lease"] as const) {
    test(`${provider}: readonly ownership observation ${scenario}`, async t => {
      const {store} = await factory(t);
      const goal = "ownership-goal";
      const projection = productionScaleCoordinationFixture(goal).projection;
      const todos = projection.todos as JsonObject[];
      for (const todo of todos) delete todo.claimed_by;
      const target = [...todos].reverse().find(todo => todo.role === "agent" && todo.done !== true)!;
      const lease = {...(projection.leases as JsonObject[])[0]!, todo_id: target.todo_id,
        status: "active", owner: "agent-a", expires_at: "2027-01-01T00:00:00Z",
        private_diagnostic: "PRIVATE_LEASE_PAYLOAD", idempotency_key: "PRIVATE_OPERATION_KEY"};
      if (scenario !== "empty") target.claimed_by = "agent-b";
      if (scenario === "bounded") for (const todo of todos) if (todo.role === "agent" && todo.done !== true) todo.claimed_by = "agent-b";
      if (scenario === "malformed_lease") lease.expires_at = "invalid";
      projection.leases = scenario === "empty" ? [] : scenario === "bounded"
        ? [...todos.slice(0, 140).map(todo => ({...lease, todo_id: todo.todo_id})), lease]
        : [lease];
      (projection.todo_read_model as JsonObject).records_sha256 = canonicalAuthoritySha256(todos);
      assert.equal((await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
        next_projection: projection, events: [], receipts: []})).status, "applied");
      const before = await store.loadAuthority();
      const result = await readCoordinationOwnership(store, goal, at);
      assert.equal(result.status, "loaded");
      assert.equal(result.todo_count, 464);
      const entries = result.entries as JsonObject[];
      assert.equal(JSON.stringify(result).includes("PRIVATE_"), false);
      if (scenario === "empty") assert.deepEqual(entries, []);
      if (scenario === "full_conflict") {
        assert.equal(entries[0]!.reason, "owner_conflicts_with_claim");
        assert.equal(entries[0]!.claimed_by, "agent-b");
        assert.equal(entries[0]!.todo_id, target.todo_id);
      }
      if (scenario === "bounded") {
        assert.equal(entries.length, 100); assert.equal(result.truncated, true);
        assert.ok(Number(result.total_count) > 100);
        assert.equal(entries[0]!.reason, "owner_conflicts_with_claim");
      }
      if (scenario === "malformed_lease") assert.equal(entries[0]!.status, "hard_lease_unreadable");
      assert.deepEqual(await store.loadAuthority(), before);
      assert.equal((await store.readReceipt("observation")).status, "missing");
    });
  }
}
