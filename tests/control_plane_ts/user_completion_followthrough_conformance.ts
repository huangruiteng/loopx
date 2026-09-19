import assert from "node:assert/strict";
import test from "node:test";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import type {AuthorityStore} from "../../loopx/control_plane/coordination/authority_store.ts";
import {executeCoordinationTodoTerminalLifecycle as complete, type CoordinationTodoTerminalLifecycleInput} from "../../loopx/control_plane/coordination/todo_terminal_lifecycle.ts";
import {prepareCoordinationProjectionCommit} from "../../loopx/control_plane/coordination/coordination_projection.ts";
import type {AuthorityStoreConformanceFactory} from "./authority_store_conformance.ts";
import {productionScaleUserCompletionFixture} from "./production_scale_coordination_fixture.ts";

async function loaded(store: AuthorityStore) {
  const result = await store.loadAuthority();
  assert.ok(result.status === "loaded", "fixture authority missing");
  return result;
}

export function registerUserCompletionFollowthroughConformance(provider: string, factory: AuthorityStoreConformanceFactory): void {
  for (const schema of ["legacy", "native"] as const) {
    for (const outcome of ["approve", "reject", "cancel"] as const) {
      test(`${provider}: linked User ${outcome} is atomic and replay-safe (${schema})`, async t => {
        const {store, contender} = await factory(t);
        const goal = "user-decision-followthrough";
        const fixture = productionScaleUserCompletionFixture(goal, schema, outcome === "approve");
        await store.commitAuthority({operation_id: "seed-user-decision", expected_provider_revision: null,
          next_projection: fixture.projection, events: [], receipts: []});
        const before = await loaded(store);
        const request: CoordinationTodoTerminalLifecycleInput = {goal_id: goal, todo_id: fixture.source, expected_role: "user", command: "complete",
          actor_agent_id: "agent-a", registered_agents: fixture.registered_agents, lifecycle_grants: [],
          authority_reason: null, decision_outcome: outcome, operation_id: "decide", lease_idempotency_key: null,
          lease_expected_version: null, allow_user_gate_auto_acquire: true, requested_no_followup: false,
          requested_completion_turn_key: null, requested_completion_identity_source: null,
          linked_successor_todo_ids: [], successor_intents: [], note: null, evidence: "Synthetic exact owner decision",
          reason: null, clear_claim: false, validation_declaration: null, validation_receipt: null,
          completion_policy_request: null, dry_run: false, now: new Date("2026-09-18T06:00:00Z")};
        const preview = await complete(store, {...request, dry_run: true});
        assert.equal(preview.status, "planned", JSON.stringify(preview));
        assert.deepEqual(await loaded(store), before);
        assert.equal((await complete(store, {...request, actor_agent_id: "agent-b"})).status, "failed");
        assert.deepEqual(await loaded(store), before);
        // Inject a real competing write at commit: source, dependent and receipt
        // must all remain untouched when the shared CAS loses.
        const originalCommit = store.commitAuthority.bind(store);
        let raced = false;
        store.commitAuthority = async commit => {
          if (!raced && commit.operation_id === "decide") {
            raced = true;
            await contender.commitAuthority(prepareCoordinationProjectionCommit({goal_id: goal,
              operation_id: "competing-write", expected_provider_revision: before.provider_revision,
              projection: before.head, mutations: []}));
          }
          return originalCommit(commit);
        };
        const lost = await complete(store, request);
        assert.notEqual(lost.status, "applied");
        const racedHead = await loaded(store);
        assert.deepEqual(racedHead.head.todos, before.head.todos);
        assert.equal((await store.readReceipt("decide")).status, "missing");
        // The write succeeds but its transport response is lost. Recover the
        // receipt rather than applying the dependent effect a second time.
        store.commitAuthority = async commit => {
          await originalCommit(commit);
          throw new Error("injected lost response");
        };
        const applied = await complete(store, request);
        store.commitAuthority = originalCommit;
        assert.equal(applied.status, "recovered", JSON.stringify(applied));
        const after = await loaded(store);
        const rows = after.head.todos as JsonObject[];
        const dependent = rows.find(row => row.todo_id === fixture.target)!;
        assert.equal(rows.find(row => row.todo_id === fixture.source)!.status, "done");
        assert.equal(dependent.status, "blocked");
        assert.equal(dependent.claimed_by, "agent-a");
        if (outcome === "approve") {
          assert.deepEqual(dependent.required_decision_scopes, []);
          assert.equal((applied.unblock_resume as JsonObject).state, "other_user_blockers_active");
        } else {
          assert.deepEqual(dependent.required_decision_scopes, [fixture.scope]);
          assert.equal((dependent.decision_scope_outcomes as JsonObject[]).length, 1);
          assert.equal((dependent.decision_scope_outcomes as JsonObject[])[0].outcome, outcome);
          assert.equal((dependent.decision_scope_outcomes as JsonObject[])[0].source_todo_id, fixture.source);
        }
        assert.deepEqual(rows.filter(row => ![fixture.source, fixture.target].includes(String(row.todo_id))),
          (before.head.todos as JsonObject[]).filter(row => ![fixture.source, fixture.target].includes(String(row.todo_id))));
        assert.deepEqual((after.head.leases as JsonObject[]).filter(row => row.todo_id !== fixture.source),
          before.head.leases, "approval must not mint or transfer the dependent task lease");
        const gateLease = (after.head.leases as JsonObject[]).find(row => row.todo_id === fixture.source)!;
        assert.equal(gateLease.status, "released", "the exact gate auto-acquire is released by terminal completion");
        const receipt = await store.readReceipt("decide");
        assert.equal((await complete(contender, request,
          async () => {throw new Error("replay must precede current admission");})).status, "replayed");
        assert.deepEqual(await loaded(store), after);
        assert.deepEqual(await store.readReceipt("decide"), receipt);
        assert.equal((await complete(store, {...request, decision_outcome: outcome === "approve" ? "reject" : "approve"})).reason_code,
          "coordination_operation_identity_mismatch");
      });
    }
  }
}
