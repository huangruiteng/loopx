import {executeCoordinationTodoArchiveCompleted} from "../../loopx/control_plane/coordination/todo_archive.ts";
/** Command recovery over the complete production-scale head. Faults wrap the
 * transport result only; all successful writes still reach the selected backend. */
import assert from "node:assert/strict";
import test from "node:test";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import type {AuthorityStore, AuthorityStoreCommitResult} from "../../loopx/control_plane/coordination/authority_store.ts";
import {canonicalAuthoritySha256} from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {TODO_DOMAIN_ITEM_SCHEMA} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import {executeCoordinationTodoCreate} from "../../loopx/control_plane/coordination/todo_create.ts";
import {executeCoordinationTodoClaim} from "../../loopx/control_plane/coordination/todo_claim.ts";
import {executeCoordinationTodoUpdate} from "../../loopx/control_plane/coordination/todo_update.ts";
import {executeCoordinationMonitorPoll} from "../../loopx/control_plane/coordination/todo_monitor_poll.ts";
import {executeCoordinationTodoTerminalLifecycle} from "../../loopx/control_plane/coordination/todo_terminal_lifecycle.ts";
import {productionScaleCoordinationFixture, PRODUCTION_SCALE_VALIDATION_DECLARATION} from "./production_scale_coordination_fixture.ts";
import type {AuthorityStoreConformanceFactory} from "./authority_store_conformance.ts";

type Command = "create" | "claim" | "update" | "complete" | "supersede" | "archive" | "monitor";
const commands: readonly Command[] = ["create", "claim", "update", "complete", "supersede", "archive", "monitor"];
type Fault = "none" | "lost_response" | "unreadable_receipt" | "ambiguous_unreadable" | "thrown_response";
const faults: readonly Fault[] = ["none", "lost_response", "unreadable_receipt", "ambiguous_unreadable", "thrown_response"];

async function commandFixture(store: AuthorityStore, command: Command) {
  const goal_id = "goal-a";
  const fixture = productionScaleCoordinationFixture(goal_id);
  const projection = fixture.projection;
  const todos = projection.todos as JsonObject[];
  const leased = new Set((projection.leases as JsonObject[]).map(row => row.todo_id));
  const claimTodo = todos.find(row => row.role === "agent" && row.status === "open" &&
    row.task_class === "advancement_task" && !leased.has(row.todo_id))!;
  const monitor = todos.find(row => row.role === "agent" && row.status === "open" &&
    row.task_class === "continuous_monitor" && !leased.has(row.todo_id))!;
  assert.ok(claimTodo); assert.ok(monitor);
  const operation_id = `recover-${command}`;
  const common = {goal_id, operation_id, registered_agents: fixture.registered_agents,
    dry_run: false, now: new Date("2026-09-07T07:00:00Z")};
  assert.equal((await store.commitAuthority({operation_id: "seed-recovery", expected_provider_revision: null,
    events: [], receipts: [], next_projection: projection})).status, "applied");
  const invoke = (target: AuthorityStore, identity = operation_id): Promise<JsonObject> => {
    const request = {...common, operation_id: identity};
    if (command === "create") return executeCoordinationTodoCreate(target, {...request,
      actor_agent_id: "agent-a", todo: {schema_version: TODO_DOMAIN_ITEM_SCHEMA, todo_id: "todo_recovery_created",
        role: "agent", status: "open", done: false, archive_state: "active", text: "Recover the accepted create"}});
    if (command === "claim") return executeCoordinationTodoClaim(target, {...request,
      actor_agent_id: String(claimTodo.claimed_by), claimed_by: String(claimTodo.claimed_by),
      todo_id: String(claimTodo.todo_id), expected_role: "agent",
      lease_request: {idempotency_key: "recovery-lease", expected_version: 0, ttl_seconds: 2700}});
    if (command === "update") return executeCoordinationTodoUpdate(target, {...request,
      actor_agent_id: "agent-a", todo_id: fixture.completion_todo_id, expected_role: "agent",
      patch: {text: "Recover the accepted copy edit"}, clear_fields: [],
      lease_idempotency_key: fixture.completion_lease_idempotency_key,
      lease_expected_version: fixture.completion_lease_expected_version});
    if (command === "archive") return executeCoordinationTodoArchiveCompleted(target, {...request,
      role: "agent", max_active_done: 5});
    if (command === "monitor") return executeCoordinationMonitorPoll(target, {...request,
      actor_agent_id: String(monitor.claimed_by),
      observation: {todo_id: monitor.todo_id, result_hash: "new-recovery-evidence", material_change: true,
        generated_at: "2026-09-07T07:00:00Z"},
      intent: {next_agent_todo: "Advance the recovered material change", next_action_kind: "implement"}});
    return executeCoordinationTodoTerminalLifecycle(target, {...request, command,
      todo_id: fixture.completion_todo_id, actor_agent_id: "agent-a", expected_role: "agent",
      lifecycle_grants: [], authority_reason: null, decision_outcome: null,
      lease_idempotency_key: fixture.completion_lease_idempotency_key,
      lease_expected_version: fixture.completion_lease_expected_version,
      allow_user_gate_auto_acquire: false, requested_no_followup: command === "complete",
      requested_completion_turn_key: null, requested_completion_identity_source: null,
      linked_successor_todo_ids: [], successor_intents: [], note: null, evidence: "synthetic validation",
      reason: "Replace the scoped work", clear_claim: false, completion_policy_request: null,
      validation_declaration: command === "complete" ? PRODUCTION_SCALE_VALIDATION_DECLARATION : null,
      validation_receipt: command === "complete" ? {schema_version: "issue_fix_validation_command_v0", command_label: "production-scale fixture validation",
        exit_code: 0, passed: true, status: "passed", summary: "synthetic validation passed",
        stdout_captured: false, stderr_captured: false, local_path_captured: false} : null});
  };
  return {invoke, operation_id, initial: await store.loadAuthority()};
}

export function registerCoordinationReceiptConformance(provider: string, factory: AuthorityStoreConformanceFactory) {
  for (const command of commands) for (const fault of faults) {
    test(`${provider}: ${command} receipt recovery / ${fault}`, async t => {
      const {store} = await factory(t);
      const {invoke, operation_id, initial} = await commandFixture(store, command);
      let attempted = false, commits = 0;
      const wrapped: AuthorityStore = {
        storeIdentity: () => store.storeIdentity(), loadAuthority: () => store.loadAuthority(),
        scanCommitted: (cursor, limit) => store.scanCommitted(cursor, limit),
        readReceipt: id => attempted && (fault === "unreadable_receipt" || fault === "ambiguous_unreadable")
          ? Promise.resolve({status: "unavailable", reason_code: "synthetic_disconnect", reason: "receipt transport disconnected"})
          : store.readReceipt(id),
        commitAuthority: async commit => {
          commits++; attempted = true;
          const result = await store.commitAuthority(commit);
          assert.equal(result.status, "applied", JSON.stringify(result));
          if (fault === "thrown_response") throw new Error("synthetic response lost after commit");
          return (fault === "lost_response" || fault === "ambiguous_unreadable")
            ? {status: "ambiguous", reason_code: "synthetic_timeout", reason: "commit response lost"} satisfies AuthorityStoreCommitResult
            : result;
        },
      };
      const result = await invoke(wrapped);
      const uncertain = fault === "unreadable_receipt" || fault === "ambiguous_unreadable";
      assert.equal(result.status, uncertain ? "ambiguous" : fault === "none" ? "applied" : "recovered", JSON.stringify(result));
      if (uncertain) {
        assert.equal((result.recovery as JsonObject).operation_id, operation_id);
        assert.equal((result.recovery as JsonObject).retry_with_same_operation_id, true);
        assert.equal(result.changed, false);
      }
      assert.equal(commits, 1, "a response fault never triggers a second commit");
      const after = await store.loadAuthority();
      assert.notDeepEqual(after, initial);
      const receipt = await store.readReceipt(operation_id);
      assert.equal(receipt.status, "found");
      assert.equal((await invoke(store)).status, "replayed");
      assert.deepEqual(await store.loadAuthority(), after, "retry never changes head, leases or successors");
      // An unrelated later transaction must not redirect recovery to the latest head.
      assert.equal(after.status, "loaded");
      if (after.status !== "loaded" || receipt.status !== "found") return;
      await store.commitAuthority({operation_id: "later-write", expected_provider_revision: after.provider_revision,
        next_projection: after.head, events: [], receipts: []});
      const replay = await invoke(store);
      assert.equal(replay.cursor, receipt.cursor);
      assert.equal(replay.provider_revision, receipt.provider_revision);
      assert.equal(canonicalAuthoritySha256(replay.original_receipt ?? (replay.writeback as JsonObject)),
        canonicalAuthoritySha256(result.original_receipt ?? replay.original_receipt ?? replay.writeback));
    });
  }
}
