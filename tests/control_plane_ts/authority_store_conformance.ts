import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import type {
  AuthorityStore,
  AuthorityStoreCommit,
} from "../../loopx/control_plane/coordination/authority_store.ts";
import { canonicalAuthorityBytes } from "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {
  TODO_CANONICAL_READ_RECORD_FIELDS,
  TODO_CANONICAL_READ_RECORD_SCHEMA,
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_DOMAIN_RECORD_CONTRACT,
} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import { prepareCoordinationProjectionCommit } from "../../loopx/control_plane/coordination/coordination_projection.ts";
import { executeCoordinationTodoClaim } from "../../loopx/control_plane/coordination/todo_claim.ts";
import { executeCoordinationTodoCreate } from "../../loopx/control_plane/coordination/todo_create.ts";
import { executeCoordinationTodoUpdate } from "../../loopx/control_plane/coordination/todo_update.ts";
import { editCoordinationTodo, TODO_COMPATIBILITY_EDIT_SCHEMA } from "../../loopx/control_plane/coordination/todo_compatibility_edit.ts";

export interface AuthorityStoreConformanceFixture {
  store: AuthorityStore;
  contender: AuthorityStore;
}
export type AuthorityStoreConformanceFactory = (
  context: test.TestContext,
) => Promise<AuthorityStoreConformanceFixture>;

function todoClaimProjection(goalId: string, native: boolean): Record<string, unknown> {
  const todos = [{
    schema_version: "todo_item_v0",
    todo_id: "todo-claim",
    role: "agent",
    status: "open",
    done: false,
    text: "Claim through the provider-neutral transaction",
    archive_state: "active",
    source_section: "Agent Todo",
    note: "preserve complete canonical record",
    required_write_scopes: ["loopx/control_plane/**"],
  }];
  if (native) {
    todos[0]!.schema_version = TODO_DOMAIN_ITEM_SCHEMA;
    Reflect.deleteProperty(todos[0]!, "source_section");
  }
  const recordsSha256 = createHash("sha256")
    .update(canonicalAuthorityBytes(todos))
    .digest("hex");
  return {
    goal_id: goalId,
    handoff_mode: "soft_claim",
    todos,
    leases: [],
    todo_read_model: {
      schema_version: native ? TODO_DOMAIN_READ_RECORD_SCHEMA : TODO_CANONICAL_READ_RECORD_SCHEMA,
      todo_count: todos.length,
      records_sha256: recordsSha256,
      contract_fields: native ? [...TODO_DOMAIN_RECORD_CONTRACT.fields] : [...TODO_CANONICAL_READ_RECORD_FIELDS],
    },
  };
}

export function authorityStoreCommitFixture(
  expectedProviderRevision: string | null,
  operationId: string,
  authorityRevision: number,
  leaseEpoch: number,
): AuthorityStoreCommit {
  return {
    expected_provider_revision: expectedProviderRevision,
    operation_id: operationId,
    events: [{
      schema_version: "loopx_authority_event_v0",
      type: "todo_claimed",
      authority_revision: authorityRevision,
      lease_epoch: leaseEpoch,
    }],
    next_projection: {
      schema_version: "loopx_coordination_head_v1",
      authority_revision: authorityRevision,
      coordination: {
        leases: { "todo-a": { lease_epoch: leaseEpoch } },
      },
    },
    receipts: [{
      schema_version: "loopx_authority_receipt_v0",
      operation_id: operationId,
      accepted_authority_revision: authorityRevision,
      lease_epoch: leaseEpoch,
    }],
  };
}

export function registerAuthorityStoreConformance(
  providerName: string,
  factory: AuthorityStoreConformanceFactory,
): void {
  test(`${providerName} conformance: atomic transition, projection, and receipt`, async (t) => {
    const { store } = await factory(t);
    assert.deepEqual(await store.loadAuthority(), { status: "missing" });

    const applied = await store.commitAuthority(
      authorityStoreCommitFixture(null, "operation-a", 41, 7),
    );
    assert.equal(applied.status, "applied");
    if (applied.status !== "applied") return;
    assert.notEqual(applied.provider_revision, "41");
    assert.notEqual(applied.provider_revision, "7");
    assert.equal(applied.cursor, "1");

    const loaded = await store.loadAuthority();
    assert.equal(loaded.status, "loaded");
    if (loaded.status !== "loaded") return;
    assert.equal(loaded.head.authority_revision, 41);
    assert.deepEqual(loaded.head.coordination, {
      leases: { "todo-a": { lease_epoch: 7 } },
    });
    assert.equal(loaded.provider_revision, applied.provider_revision);
    assert.equal(loaded.cursor, "1");

    const receipt = await store.readReceipt("operation-a");
    assert.equal(receipt.status, "found");
    if (receipt.status === "found") {
      assert.equal(receipt.provider_revision, applied.provider_revision);
      assert.equal(receipt.receipts[0]?.accepted_authority_revision, 41);
      assert.equal(receipt.receipts[0]?.lease_epoch, 7);
    }
  });

  test(`${providerName} conformance: CAS admits one writer`, async (t) => {
    const { store, contender } = await factory(t);
    const results = await Promise.all([
      store.commitAuthority(authorityStoreCommitFixture(null, "operation-a", 1, 1)),
      contender.commitAuthority(authorityStoreCommitFixture(null, "operation-b", 1, 1)),
    ]);
    assert.deepEqual(results.map((result) => result.status).sort(), ["applied", "conflict"]);
    const applied = results.find((result) => result.status === "applied");
    const conflict = results.find((result) => result.status === "conflict");
    assert.ok(applied && applied.status === "applied");
    assert.ok(conflict && conflict.status === "conflict");
    assert.equal(conflict.conflict_kind, "provider_revision_mismatch");
    assert.equal(conflict.current_provider_revision, applied.provider_revision);
    assert.equal(conflict.current_cursor, "1");
  });

  test(`${providerName} conformance: historical replay and operation fencing`, async (t) => {
    const { store } = await factory(t);
    const first = await store.commitAuthority(
      authorityStoreCommitFixture(null, "operation-a", 1, 3),
    );
    assert.equal(first.status, "applied");
    if (first.status !== "applied") return;
    const second = await store.commitAuthority(
      authorityStoreCommitFixture(first.provider_revision, "operation-b", 2, 9),
    );
    assert.equal(second.status, "applied");
    if (second.status !== "applied") return;

    const historical = await store.readReceipt("operation-a");
    assert.equal(historical.status, "found");
    if (historical.status === "found") {
      assert.equal(historical.cursor, "1");
      assert.equal(historical.receipts[0]?.lease_epoch, 3);
    }
    const duplicate = await store.commitAuthority(
      authorityStoreCommitFixture(second.provider_revision, "operation-a", 3, 10),
    );
    assert.deepEqual(duplicate, {
      status: "conflict",
      conflict_kind: "operation_id_exists",
      current_provider_revision: second.provider_revision,
      current_cursor: "2",
    });
    const loaded = await store.loadAuthority();
    assert.equal(loaded.status, "loaded");
    if (loaded.status === "loaded") assert.equal(loaded.head.authority_revision, 2);
  });

  test(`${providerName} conformance: committed scan is ordered and isolated`, async (t) => {
    const { store } = await factory(t);
    const first = await store.commitAuthority(
      authorityStoreCommitFixture(null, "operation-a", 1, 1),
    );
    assert.equal(first.status, "applied");
    if (first.status !== "applied") return;
    await store.commitAuthority(
      authorityStoreCommitFixture(first.provider_revision, "operation-b", 2, 2),
    );

    const firstPage = await store.scanCommitted(null, 1);
    assert.equal(firstPage.status, "page");
    if (firstPage.status !== "page") return;
    assert.equal(firstPage.transactions[0]?.operation_id, "operation-a");
    assert.equal(firstPage.next_cursor, "1");
    assert.equal(firstPage.has_more, true);
    (firstPage.transactions[0]!.projection as { authority_revision: number })
      .authority_revision = 99;

    const secondPage = await store.scanCommitted("1", 1);
    assert.equal(secondPage.status, "page");
    if (secondPage.status === "page") {
      assert.equal(secondPage.transactions[0]?.operation_id, "operation-b");
      assert.equal(secondPage.next_cursor, "2");
      assert.equal(secondPage.has_more, false);
    }
    const loaded = await store.loadAuthority();
    assert.equal(loaded.status, "loaded");
    if (loaded.status === "loaded") assert.equal(loaded.head.authority_revision, 2);
    assert.equal((await store.scanCommitted("3", 1)).status, "failed");
    assert.equal((await store.scanCommitted(null, 0)).status, "failed");
  });

  test(`${providerName} conformance: malformed JSON fails before a write`, async (t) => {
    const { store } = await factory(t);
    const invalidNumber = authorityStoreCommitFixture(null, "operation-nan", 1, 1);
    invalidNumber.next_projection.authority_revision = Number.NaN;
    assert.equal((await store.commitAuthority(invalidNumber)).status, "failed");

    const invalidObject = authorityStoreCommitFixture(null, "operation-date", 1, 1);
    (invalidObject.next_projection as Record<string, unknown>).coordination = new Date();
    assert.equal((await store.commitAuthority(invalidObject)).status, "failed");
    assert.deepEqual(await store.loadAuthority(), { status: "missing" });
  });

  for (const native of [false, true]) {
    test(`${providerName} conformance: native Todo create is atomic and replayable (${native ? "native" : "v0"})`, async (t) => {
      const {store, contender} = await factory(t);
      const goalId = "goal-claim";
      const projection = todoClaimProjection(goalId, native);
      const initialized = await store.commitAuthority({
        expected_provider_revision: null, operation_id: "init-create",
        events: [], receipts: [], next_projection: projection,
      });
      assert.equal(initialized.status, "applied");
      if (initialized.status !== "applied") return;
      const todo = {
        schema_version: TODO_DOMAIN_ITEM_SCHEMA,
        todo_id: "todo-created",
        role: "agent",
        status: "open",
        done: false,
        text: "Create through the provider-neutral transaction",
        archive_state: "active",
        task_class: "advancement_task",
        action_kind: "implement",
        claimed_by: "agent-a",
      };
      const request = {
        goal_id: goalId, todo, actor_agent_id: "agent-a",
        registered_agents: ["agent-a", "agent-b"], operation_id: "create-todo",
        dry_run: false, now: new Date("2026-09-05T06:00:00Z"),
      };
      const preview = await executeCoordinationTodoCreate(store, {...request, dry_run: true});
      assert.equal(preview.status, "planned");
      assert.equal((await store.loadAuthority()).status, "loaded");
      const [first, second] = await Promise.all([
        executeCoordinationTodoCreate(store, request),
        executeCoordinationTodoCreate(contender, {...request,
          operation_id: "create-todo-contender", todo: {...todo, text: "Competing create"}}),
      ]);
      assert.deepEqual(
        [first.status, second.status].sort((left, right) =>
          String(left).localeCompare(String(right))
        ),
        ["applied", "conflict"],
      );
      const applied = first.status === "applied" ? first : second;
      const replayRequest = first.status === "applied" ? request : {...request,
        operation_id: "create-todo-contender", todo: {...todo, text: "Competing create"}};
      assert.equal(applied.todo_id, todo.todo_id);
      assert.equal(applied.projection_delivery, "pending");
      assert.equal(applied.projection_source, "committed_authority_journal");
      const replayedCreate = await executeCoordinationTodoCreate(store, replayRequest);
      assert.equal(replayedCreate.status, "replayed");
      assert.equal(replayedCreate.projection_delivery, "pending");
      assert.equal((await executeCoordinationTodoCreate(store, {...replayRequest,
        todo: {...replayRequest.todo, note: "different intent"}})).status, "failed");
      assert.equal((await executeCoordinationTodoCreate(store, {...replayRequest,
        operation_id: "semantic-duplicate", todo: {...replayRequest.todo, todo_id: "todo-other"}})).status,
      "no_change");
      const conflictingDuplicate = await executeCoordinationTodoCreate(store, {...replayRequest,
        operation_id: "semantic-duplicate-conflict", todo: {...replayRequest.todo,
          todo_id: "todo-other", task_class: "continuous_monitor"}});
      assert.equal(conflictingDuplicate.status, "failed");
      assert.equal(conflictingDuplicate.reason_code, "todo_semantic_duplicate_conflict");
      const deferredSameText = {
        ...replayRequest.todo,
        todo_id: "todo-deferred-terminal",
        status: "deferred",
        done: true,
        text: "Repeat terminal work",
        ...(native ? {} : {schema_version: "todo_item_v0", source_section: "Agent Todo"}),
      };
      const loadedBeforeDeferred = await store.loadAuthority();
      assert.equal(loadedBeforeDeferred.status, "loaded");
      if (loadedBeforeDeferred.status !== "loaded") return;
      const deferredCommit = prepareCoordinationProjectionCommit({
        goal_id: goalId,
        operation_id: "seed-deferred-terminal",
        expected_provider_revision: loadedBeforeDeferred.provider_revision,
        projection: loadedBeforeDeferred.head,
        mutations: [{kind: "todo_upsert", todo: deferredSameText}],
      });
      assert.equal((await store.commitAuthority(deferredCommit)).status, "applied");
      const recreatedAfterDeferred = await executeCoordinationTodoCreate(store, {
        ...replayRequest,
        operation_id: "create-after-deferred-terminal",
        todo: {...replayRequest.todo, todo_id: "todo-after-deferred-terminal",
          text: "Repeat terminal work"},
      });
      assert.equal(recreatedAfterDeferred.status, "applied");
      const createdDeferred = await executeCoordinationTodoCreate(store, {
        ...replayRequest,
        operation_id: "create-deferred",
        todo: {...replayRequest.todo, todo_id: "todo-new-deferred",
          text: "Wait for the external dependency", status: "deferred", done: true,
          resume_when: "material_change"},
      });
      assert.equal(createdDeferred.status, "applied");
      const inconsistentTerminal = await executeCoordinationTodoCreate(store, {
        ...replayRequest,
        operation_id: "reject-inconsistent-terminal",
        todo: {...replayRequest.todo, todo_id: "todo-inconsistent-terminal",
          status: "done", done: false},
      });
      assert.equal(inconsistentTerminal.status, "failed");
      assert.equal(inconsistentTerminal.reason_code, "invalid_coordination_todo_create");
      const loaded = await store.loadAuthority();
      assert.equal(loaded.status, "loaded");
      if (loaded.status !== "loaded") return;
      const created = (loaded.head.todos as Record<string, unknown>[])
        .find((item) => item.todo_id === todo.todo_id)!;
      assert.equal(created.created_by, "agent-a");
      assert.equal(created.last_actor_agent_id, "agent-a");
      assert.equal(created.updated_at, "2026-09-05T06:00:00Z");
      assert.equal((loaded.head.todo_read_model as Record<string, unknown>).todo_count, 5);
      for (const invalid of [
        {...request, operation_id: "bad-actor", actor_agent_id: "agent-b"},
        {...request, operation_id: "bad-status", todo: {...todo, todo_id: "todo-done", status: "done", done: true}},
        {...request, operation_id: "bad-projection", todo: {...todo, todo_id: "todo-projection", source_section: "Agent Todo"}},
      ]) assert.equal((await executeCoordinationTodoCreate(store, invalid)).status, "failed");
    });
    test(`${providerName} conformance: compatibility edit cannot overwrite a concurrent claim (${native ? "native" : "v0"})`, async (t) => {
      const {store, contender} = await factory(t);
      const goalId = "goal-claim";
      const projection = todoClaimProjection(goalId, native);
      const initialized = await store.commitAuthority({
        expected_provider_revision: null, operation_id: "init-compatibility",
        events: [], receipts: [], next_projection: projection,
      });
      assert.equal(initialized.status, "applied");
      if (initialized.status !== "applied") return;
      const request = {
        schema_version: TODO_COMPATIBILITY_EDIT_SCHEMA, goal_id: goalId,
        todo_id: "todo-claim", operation_id: "edit-compatibility",
        actor_agent_id: "agent-a", registered_agents: ["agent-a", "agent-b"],
        expected_provider_revision: initialized.provider_revision,
        patch: {text: "Edited through a compatibility buffer"}, dry_run: false,
        observed_at: "2026-09-05T05:00:00Z",
      };
      assert.equal((await executeCoordinationTodoClaim(contender, {
        goal_id: goalId, todo_id: "todo-claim", claimed_by: "agent-a",
        actor_agent_id: "agent-a", expected_role: "agent", registered_agents: ["agent-a", "agent-b"],
        operation_id: "claim-before-edit", dry_run: false, now: new Date("2026-09-05T04:30:00Z"),
      })).status, "applied");
      const current = await store.loadAuthority();
      assert.equal(current.status, "loaded");
      if (current.status !== "loaded") return;
      assert.equal((await editCoordinationTodo(store, request)).status, "conflict");
      assert.deepEqual(await store.loadAuthority(), current);
      request.expected_provider_revision = current.provider_revision;
      const preview = await editCoordinationTodo(store, {...request, dry_run: true});
      assert.equal(preview.status, "planned");
      assert.deepEqual(await store.loadAuthority(), current);
      assert.equal((await store.readReceipt(request.operation_id)).status, "missing");
      for (const extra of [{claimed_by: "agent-b"}, {archive_state: "archive"}, {source_section: "fake"}]) {
        assert.equal((await editCoordinationTodo(store, {...request, patch: extra})).status, "failed");
      }
      assert.equal((await editCoordinationTodo(store, {...request, actor_agent_id: "agent-b"})).status, "failed");
      assert.deepEqual(await store.loadAuthority(), current);
      const applied = await editCoordinationTodo(store, request);
      assert.equal(applied.status, "applied", JSON.stringify(applied));
      const after = await store.loadAuthority();
      assert.equal(after.status, "loaded");
      if (after.status !== "loaded") return;
      const old = (current.head.todos as Record<string, unknown>[])[0]!;
      assert.deepEqual(after.head.todos, [{...old, text: request.patch.text, updated_at: "2026-09-05T05:00:00.000Z"}]);
      assert.deepEqual(after.head.leases, current.head.leases);
      assert.equal((await editCoordinationTodo(store, {...request, registered_agents: []})).status, "replayed");
      assert.deepEqual(await store.loadAuthority(), after);
      assert.equal((await editCoordinationTodo(store, {...request, patch: {note: "different intent"}})).status, "failed");
      const noop = {...request, operation_id: "edit-noop", expected_provider_revision: after.provider_revision};
      assert.equal((await editCoordinationTodo(store, noop)).status, "no_change");
      const afterNoop = await store.loadAuthority();
      assert.equal(afterNoop.status, "loaded");
      if (afterNoop.status !== "loaded") return;
      assert.deepEqual(afterNoop.head, after.head);
      assert.equal((await editCoordinationTodo(store, noop)).status, "replayed");
      assert.deepEqual(await store.loadAuthority(), afterNoop);
      // Losing the response after commit is recovered by the exact receipt.
      const ambiguousStore: AuthorityStore = {
        storeIdentity: () => store.storeIdentity(), loadAuthority: () => store.loadAuthority(),
        readReceipt: (id) => store.readReceipt(id), scanCommitted: (cursor, limit) => store.scanCommitted(cursor, limit),
        commitAuthority: async (commit) => {
          assert.equal((await store.commitAuthority(commit)).status, "applied");
          return {status: "ambiguous", reason_code: "lost_response", reason: "synthetic lost response"};
        },
      };
      const recover = {...request, operation_id: "edit-recover",
        expected_provider_revision: afterNoop.provider_revision, patch: {note: "Recovered edit"}};
      assert.equal((await editCoordinationTodo(ambiguousStore, recover)).status, "recovered");
      assert.equal((await editCoordinationTodo(store, recover)).status, "replayed");
      const recoveredHead = await store.loadAuthority();
      assert.equal(recoveredHead.status, "loaded");
      if (recoveredHead.status !== "loaded") return;
      // A competing receipt-only commit after read still invalidates the CAS.
      const racingStore: AuthorityStore = {...ambiguousStore,
        commitAuthority: async (commit) => {
          assert.equal((await contender.commitAuthority({
            ...commit, operation_id: "concurrent-writer", next_projection: recoveredHead.head,
            events: [], receipts: [],
          })).status, "applied");
          return store.commitAuthority(commit);
        },
      };
      assert.equal((await editCoordinationTodo(racingStore, {...recover,
        operation_id: "edit-race", expected_provider_revision: recoveredHead.provider_revision,
        patch: {note: "Must not commit"},
      })).status, "conflict");
      const afterRace = await store.loadAuthority();
      assert.equal(afterRace.status, "loaded");
      if (afterRace.status !== "loaded") return;
      assert.deepEqual(afterRace.head, recoveredHead.head);
      assert.equal((await store.readReceipt("edit-race")).status, "missing");
      for (const invalid of [{dry_run: "false"}, {patch: {}}, {patch: {text: ""}},
        {registered_agents: ["agent-a", "agent-a"]}, {observed_at: "yesterday"},
        {projection: recoveredHead.head}]) {
        assert.equal((await editCoordinationTodo(store, {...request, ...invalid})).status, "failed");
      }
      assert.deepEqual(await store.loadAuthority(), afterRace);
    });
    test(`${providerName} conformance: Todo claim atomically acquires canonical ownership (${native ? "native" : "v0"})`, async (t) => {
      const {store} = await factory(t);
      const goalId = "goal-atomic-ownership";
      const projection = {
        ...todoClaimProjection(goalId, native),
        handoff_mode: "hard_lease",
      };
      assert.equal((await store.commitAuthority({
        expected_provider_revision: null,
        operation_id: "seed-atomic-ownership",
        events: [],
        receipts: [],
        next_projection: projection,
      })).status, "applied");
      const request = {
        goal_id: goalId,
        todo_id: "todo-claim",
        claimed_by: "agent-a",
        actor_agent_id: "agent-a",
        expected_role: "agent",
        registered_agents: ["agent-a", "agent-b"],
        operation_id: "claim-and-acquire",
        lease_request: {
          idempotency_key: "turn:atomic-ownership",
          expected_version: 0,
          ttl_seconds: 2_700,
        },
        dry_run: false,
        now: new Date("2026-09-05T04:30:00Z"),
      };
      const preview = await executeCoordinationTodoClaim(store, {...request, dry_run: true});
      assert.equal(preview.status, "planned");
      assert.equal(preview.todo_changed, true);
      assert.equal(preview.lease_changed, true);
      assert.equal((await store.readReceipt(request.operation_id)).status, "missing");

      const applied = await executeCoordinationTodoClaim(store, request);
      assert.equal(applied.status, "applied", JSON.stringify(applied));
      assert.equal(applied.todo_changed, true);
      assert.equal(applied.lease_changed, true);
      const loaded = await store.loadAuthority();
      assert.equal(loaded.status, "loaded");
      if (loaded.status !== "loaded") return;
      const claimedTodo = (loaded.head.todos as Record<string, unknown>[])[0]!;
      const lease = (loaded.head.leases as Record<string, unknown>[])[0]!;
      assert.equal(claimedTodo.claimed_by, "agent-a");
      assert.equal(lease.owner, "agent-a");
      assert.equal(lease.idempotency_key, "turn:atomic-ownership");
      assert.deepEqual(lease.write_scopes, ["loopx/control_plane/**"]);
      assert.equal((await executeCoordinationTodoClaim(store, request)).status, "replayed");

      const idempotent = await executeCoordinationTodoClaim(store, {
        ...request,
        operation_id: "claim-and-acquire-idempotent",
        lease_request: {...request.lease_request, expected_version: 1},
      });
      assert.equal(idempotent.status, "no_change", JSON.stringify(idempotent));
      assert.equal(idempotent.todo_changed, false);
      assert.equal(idempotent.lease_changed, false);
      assert.equal(idempotent.lease_idempotent, true);
      const afterIdempotent = await store.loadAuthority();
      assert.equal(afterIdempotent.status, "loaded");
      if (afterIdempotent.status !== "loaded") return;
      assert.deepEqual(afterIdempotent.head, loaded.head);
      assert.equal((await store.readReceipt("claim-and-acquire-idempotent")).status, "found");
    });
    test(`${providerName} conformance: competing ownership transactions cannot split claim and lease (${native ? "native" : "v0"})`, async (t) => {
      const {store, contender} = await factory(t);
      const goalId = "goal-competing-ownership";
      const projection = {
        ...todoClaimProjection(goalId, native),
        handoff_mode: "hard_lease",
      };
      assert.equal((await store.commitAuthority({
        expected_provider_revision: null,
        operation_id: "seed-competing-ownership",
        events: [],
        receipts: [],
        next_projection: projection,
      })).status, "applied");
      const request = (owner: "agent-a" | "agent-b") => ({
        goal_id: goalId,
        todo_id: "todo-claim",
        claimed_by: owner,
        actor_agent_id: owner,
        expected_role: "agent",
        registered_agents: ["agent-a", "agent-b"],
        operation_id: `claim-and-acquire:${owner}`,
        lease_request: {
          idempotency_key: `turn:competing-ownership:${owner}`,
          expected_version: 0,
          ttl_seconds: 2_700,
        },
        dry_run: false,
        now: new Date("2026-09-05T04:30:00Z"),
      });

      const results = await Promise.all([
        executeCoordinationTodoClaim(store, request("agent-a")),
        executeCoordinationTodoClaim(contender, request("agent-b")),
      ]);
      assert.deepEqual(
        results.map((result) => result.status).sort(),
        ["applied", "conflict"],
      );
      const winnerIndex = results.findIndex((result) => result.status === "applied");
      assert.notEqual(winnerIndex, -1);
      const winner = winnerIndex === 0 ? "agent-a" : "agent-b";
      const loser = winner === "agent-a" ? "agent-b" : "agent-a";
      const loaded = await store.loadAuthority();
      assert.equal(loaded.status, "loaded");
      if (loaded.status !== "loaded") return;
      const claimedTodo = (loaded.head.todos as Record<string, unknown>[])[0]!;
      const leases = loaded.head.leases as Record<string, unknown>[];
      assert.equal(claimedTodo.claimed_by, winner);
      assert.equal(leases.length, 1);
      assert.equal(leases[0]!.owner, winner);
      assert.equal(leases[0]!.idempotency_key, `turn:competing-ownership:${winner}`);
      assert.equal((await store.readReceipt(`claim-and-acquire:${winner}`)).status, "found");
      assert.equal((await store.readReceipt(`claim-and-acquire:${loser}`)).status, "missing");
      assert.equal((await executeCoordinationTodoClaim(store, request(winner))).status, "replayed");
      const rejected = await executeCoordinationTodoClaim(store, request(loser));
      assert.equal(rejected.status, "failed");
      assert.equal(rejected.reason_code, "claim_owner_mismatch");
      assert.deepEqual(await store.loadAuthority(), loaded);
    });
    for (const fault of ["lease_replaced", "lost_response"] as const) {
      test(`${providerName} conformance: hard-lease claim ${fault} (${native ? "native" : "v0"})`, async (t) => {
        const {store, contender} = await factory(t);
        const goalId = "goal-claim";
        const projection = {...todoClaimProjection(goalId, native), handoff_mode: "hard_lease"};
        assert.equal((await store.commitAuthority({
          operation_id: "seed-hard-lease", expected_provider_revision: null,
          next_projection: projection, events: [], receipts: [],
        })).status, "applied");
        const request = {
          goal_id: goalId, todo_id: "todo-claim", claimed_by: "agent-a",
          actor_agent_id: "agent-a", expected_role: "agent",
          registered_agents: ["agent-a", "agent-b"], operation_id: "claim-hard-lease",
          dry_run: false, now: new Date("2026-09-05T04:30:00Z"),
        };
        // Claim does not mint execution authority: an absent lease rejects
        // without consuming the operation id or changing the provider head.
        const before = await store.loadAuthority();
        assert.equal((await executeCoordinationTodoClaim(store, request)).reason_code,
          "handoff_mode_requires_lease");
        assert.deepEqual(await store.loadAuthority(), before);
        assert.equal((await store.readReceipt(request.operation_id)).status, "missing");
        assert.equal(before.status, "loaded");
        if (before.status !== "loaded") return;
        const lease = {todo_id: request.todo_id, owner: "agent-a", status: "active",
          lease_epoch: 1, expires_at: "2026-09-05T05:00:00Z"};
        assert.equal((await store.commitAuthority(prepareCoordinationProjectionCommit({
          goal_id: goalId, operation_id: "acquire-canonical-lease",
          expected_provider_revision: before.provider_revision, projection: before.head,
          mutations: [{kind: "lease_upsert", lease}],
        }))).status, "applied");
        const leased = await store.loadAuthority();
        assert.equal(leased.status, "loaded");
        if (leased.status !== "loaded") return;
        const intercepted: AuthorityStore = {
          storeIdentity: () => store.storeIdentity(),
          loadAuthority: () => store.loadAuthority(),
          readReceipt: (id) => store.readReceipt(id),
          scanCommitted: (cursor, limit) => store.scanCommitted(cursor, limit),
          commitAuthority: async (commit) => {
            if (fault === "lease_replaced") {
              assert.equal((await contender.commitAuthority(prepareCoordinationProjectionCommit({
                goal_id: goalId, operation_id: "replace-lease-before-claim-commit",
                expected_provider_revision: leased.provider_revision, projection: leased.head,
                mutations: [{kind: "lease_upsert", lease: {...lease, owner: "agent-b", lease_epoch: 2}}],
              }))).status, "applied");
              return store.commitAuthority(commit);
            }
            assert.equal((await store.commitAuthority(commit)).status, "applied");
            return {status: "ambiguous", reason_code: "lost_response",
              reason: "commit response lost after persistence"};
          },
        };
        const result = await executeCoordinationTodoClaim(intercepted, request);
        assert.equal(result.status, fault === "lease_replaced" ? "conflict" : "recovered");
        assert.equal((await store.readReceipt(request.operation_id)).status,
          fault === "lease_replaced" ? "missing" : "found");
        const after = await store.loadAuthority();
        assert.equal(after.status, "loaded");
        if (after.status !== "loaded") return;
        const todo = (after.head.todos as Record<string, unknown>[])[0]!;
        if (fault === "lease_replaced") {
          assert.equal(todo.claimed_by, undefined);
          assert.deepEqual(after.head.leases, [{...lease, owner: "agent-b", lease_epoch: 2}]);
          assert.equal((await executeCoordinationTodoClaim(store, request)).reason_code,
            "handoff_mode_requires_lease");
        } else {
          assert.equal(todo.claimed_by, "agent-a");
          assert.deepEqual(after.head.leases, [lease]);
          // Historical acceptance is retry evidence, not a fresh grant after expiry.
          const expiredRequest = {...request, now: new Date("2026-09-05T06:00:00Z")};
          assert.equal((await executeCoordinationTodoClaim(store, expiredRequest)).status, "replayed");
          assert.equal((await executeCoordinationTodoClaim(store,
            {...expiredRequest, operation_id: "fresh-expired-claim"})).reason_code,
          "handoff_mode_requires_lease");
          assert.equal((await executeCoordinationTodoClaim(store,
            {...request, claimed_by: "agent-b", actor_agent_id: "agent-b"})).reason_code,
          "coordination_operation_identity_mismatch");
        }
        assert.deepEqual(await store.loadAuthority(), after);
      });
    }
    test(`${providerName} conformance: provider-neutral Todo update is atomic and replayable (${native ? "native" : "v0"})`, async (t) => {
      const {store, contender} = await factory(t);
      const goalId = "goal-claim";
      const initialized = await store.commitAuthority({
        expected_provider_revision: null, operation_id: "init-update",
        events: [], receipts: [], next_projection: todoClaimProjection(goalId, native),
      });
      assert.equal(initialized.status, "applied");
      const correction = {goal_id: goalId, todo_id: "todo-claim", expected_role: "agent",
        actor_agent_id: "agent-b", registered_agents: ["agent-a", "agent-b"],
        operation_id: "correct-unclaimed", patch: {text: "Correct unclaimed copy", note: "Correct note"},
        clear_fields: [], dry_run: false, now: new Date("2026-09-05T05:00:00Z")};
      assert.equal((await executeCoordinationTodoUpdate(store, correction)).status, "applied");
      assert.equal((await executeCoordinationTodoUpdate(contender, correction)).status, "replayed");
      const corrected = await store.loadAuthority();
      assert.equal(corrected.status, "loaded");
      if (corrected.status !== "loaded") return;
      const correctedTodo = (corrected.head.todos as Record<string, unknown>[])[0]!;
      assert.equal(correctedTodo.claimed_by, undefined);
      assert.equal(correctedTodo.note, "Correct note");
      assert.equal(correctedTodo.last_actor_agent_id, "agent-b");
      assert.equal((await executeCoordinationTodoClaim(store, {
        goal_id: goalId, todo_id: "todo-claim", claimed_by: "agent-a",
        actor_agent_id: "agent-a", expected_role: "agent",
        registered_agents: ["agent-a", "agent-b"], operation_id: "claim-before-update",
        dry_run: false, now: new Date("2026-09-05T05:15:00Z"),
      })).status, "applied");
      assert.equal((await executeCoordinationTodoUpdate(store, {...correction,
        operation_id: "correct-after-another-agent-claims"})).reason_code, "update_owner_mismatch");
      const request = {goal_id: goalId, todo_id: "todo-claim", expected_role: "agent",
        actor_agent_id: "agent-a", registered_agents: ["agent-a", "agent-b"],
        operation_id: "update-native", patch: {text: "Updated provider-neutrally"},
        clear_fields: ["note"], dry_run: false,
        now: new Date("2026-09-05T05:30:00Z")};
      const preview = await executeCoordinationTodoUpdate(store, {...request, dry_run: true});
      assert.equal(preview.status, "planned");
      const [first, second] = await Promise.all([
        executeCoordinationTodoUpdate(store, request),
        executeCoordinationTodoUpdate(contender, {...request, operation_id: "update-contender",
          patch: {text: "Concurrent update"}}),
      ]);
      assert.deepEqual([String(first.status), String(second.status)].sort(
        (left, right) => left.localeCompare(right)),
        ["applied", "conflict"]);
      const appliedRequest = first.status === "applied" ? request : {...request,
        operation_id: "update-contender", patch: {text: "Concurrent update"}};
      assert.equal((await executeCoordinationTodoUpdate(store, appliedRequest)).status, "replayed");
      assert.equal((await executeCoordinationTodoUpdate(store, {...appliedRequest,
        patch: {text: "Changed intent"}})).reason_code,
      "coordination_operation_identity_mismatch");
      const loaded = await store.loadAuthority();
      assert.equal(loaded.status, "loaded");
      if (loaded.status !== "loaded") return;
      const updated = (loaded.head.todos as Record<string, unknown>[])[0]!;
      assert.equal(updated.text, appliedRequest.patch.text);
      assert.equal(updated.note, undefined);
      assert.equal(updated.claimed_by, "agent-a");
      assert.equal(updated.last_actor_agent_id, "agent-a");
      assert.equal((loaded.head.todo_read_model as Record<string, unknown>).todo_count, 1);
      for (const patch of [{excluded_agents: ["agent-b"]},
        {required_capabilities: ["network"]}, {continuation_policy: "no_followup"}]) {
        assert.equal((await executeCoordinationTodoUpdate(store, {...request,
          operation_id: `reject-patch-${Object.keys(patch)[0]}`, patch,
          clear_fields: []})).reason_code, "invalid_coordination_todo_update");
      }
      for (const field of ["excluded_agents", "required_capabilities", "continuation_policy"]) {
        assert.equal((await executeCoordinationTodoUpdate(store, {...request,
          operation_id: `reject-clear-${field}`, patch: {}, clear_fields: [field]})).reason_code,
        "invalid_coordination_todo_update");
      }
    });
    test(`${providerName} conformance: provider-neutral Todo claim transaction (${native ? "native" : "v0"})`, async (t) => {
      const { store } = await factory(t);
      const goalId = "goal-claim";
      const initialized = await store.commitAuthority({
        expected_provider_revision: null,
        operation_id: "initialize-claim",
        events: [{ schema_version: "loopx_authority_event_v0", type: "promoted" }],
        next_projection: todoClaimProjection(goalId, native),
        receipts: [],
      });
      assert.equal(initialized.status, "applied");

      const request = {
        goal_id: goalId,
        todo_id: "todo-claim",
        claimed_by: "agent-a",
        actor_agent_id: "agent-a",
        expected_role: "agent",
        registered_agents: ["agent-a", "agent-b"],
        operation_id: "claim-todo",
        dry_run: false,
        now: new Date("2026-09-05T04:30:00Z"),
      };
      const claimed = await executeCoordinationTodoClaim(store, request);
      assert.equal(claimed.status, "applied", JSON.stringify(claimed));
      assert.equal(claimed.projection_delivery, "pending");
      assert.equal(claimed.projection_source, "committed_authority_journal");

      const loaded = await store.loadAuthority();
      assert.equal(loaded.status, "loaded");
      if (loaded.status !== "loaded") return;
      const todo = (loaded.head.todos as Record<string, unknown>[])[0];
      assert.equal(todo?.claimed_by, "agent-a");
      assert.equal(todo?.note, "preserve complete canonical record");
      assert.equal((await store.readReceipt("claim-todo")).status, "found");
      const noChangeRequest = {...request, operation_id: "claim-already-owned"};
      const noChange = await executeCoordinationTodoClaim(store, noChangeRequest);
      assert.equal(noChange.status, "no_change", JSON.stringify(noChange));
      assert.equal(noChange.changed, false);
      const afterNoChange = await store.loadAuthority();
      assert.equal(afterNoChange.status, "loaded");
      if (afterNoChange.status !== "loaded") return;
      assert.deepEqual(afterNoChange.head, loaded.head);
      assert.notEqual(afterNoChange.provider_revision, loaded.provider_revision);
      assert.equal((await store.readReceipt(noChangeRequest.operation_id)).status, "found");
      const replayed = await executeCoordinationTodoClaim(store,
        {...noChangeRequest, registered_agents: []});
      assert.deepEqual(replayed, {...noChange, status: "replayed"});
      assert.deepEqual(await store.loadAuthority(), afterNoChange);
      const cleared = await store.commitAuthority(prepareCoordinationProjectionCommit({
        goal_id: goalId, operation_id: "clear-after-no-change",
        expected_provider_revision: afterNoChange.provider_revision,
        projection: afterNoChange.head,
        mutations: [{kind: "todo_upsert", todo: {...todo, claimed_by: null}}],
      }));
      assert.equal(cleared.status, "applied");
      const afterClear = await store.loadAuthority();
      assert.deepEqual(await executeCoordinationTodoClaim(store,
        {...noChangeRequest, registered_agents: []}), {...noChange, status: "replayed"});
      assert.deepEqual(await store.loadAuthority(), afterClear);
    });
  }
}
