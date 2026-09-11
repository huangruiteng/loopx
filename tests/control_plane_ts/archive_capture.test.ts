import assert from "node:assert/strict";
import test from "node:test";
import {captureArchivedTodoDependencies as capture, ARCHIVE_CAPTURE_REQUEST_SCHEMA} from
  "../../loopx/control_plane/todos/archive_capture.ts";

const dependency = {todo_id: "todo_history", archive_state: "archive", status: "done", done: true,
  task_class: "advancement_task", text: "Historical work"};
const request = (archived: object[], active: object[] = [{todo_id: "todo_active", resume_when: "todo_done:todo_history"}]) =>
  ({schema_version: ARCHIVE_CAPTURE_REQUEST_SCHEMA, active, archived});

test("capture carries actual transitive archive nodes, not cached readiness or unrelated history", () => {
  assert.deepEqual(capture(request([{...dependency, resume_when: "todo_done:todo_prior"},
    {...dependency, todo_id: "todo_prior"}, {...dependency, todo_id: "todo_unrelated"}])),
  {schema_version: "todo_archive_dependency_capture_result_v0", records: [{index: 0, role: "agent"}, {index: 1, role: "agent"}]});
  assert.deepEqual(capture(request([], [{todo_id: "todo_active", resume_when: "todo_done:todo_history", resume_ready: true}])).records, []);
});

test("capture never invents user decision authority from class, text, or cached conditions", () => {
  for (const changed of [{task_class: "user_gate"}, {task_class: "user_action"}, {task_class: undefined},
    {role: "user"}, {role: "unknown"}, {global_gate: true}, {decision_outcome: "approve"},
    {status: "open", done: false}, {archive_state: "active"}]) {
    assert.throws(() => capture(request([{...dependency, ...changed}])), /archive dependency capture/);
  }
  assert.deepEqual(capture(request([{...dependency, role: "user", task_class: "user_action"}])).records,
    [{index: 0, role: "user"}]);
});

test("capture preserves unreferenced archived standing decisions and their revocations", () => {
  const standing = (todo_id: string, decision_outcome: string) => ({todo_id, role: "user",
    task_class: "user_gate", status: "done", done: true, archive_state: "archive", global_gate: true,
    decision_scope: {kind: "write_scope", granularity: "goal", scope_key: "release"}, decision_outcome});
  assert.deepEqual(capture(request([
    standing("todo_approve", "approve"), standing("todo_reject", "reject"), standing("todo_cancel", "cancel"),
    {...standing("todo_linked", "approve"), unblocks_todo_id: "todo_delivery"},
  ], [{todo_id: "todo_delivery"}])).records,
  [{index: 0, role: "user"}, {index: 1, role: "user"}, {index: 2, role: "user"}]);
  assert.throws(() => capture(request([standing("todo_reject", "reject"), standing("todo_reject", "reject")],
    [{todo_id: "todo_delivery"}])), /duplicate standing decision identity/);
});

test("duplicate identities cannot be selected by storage order; archived cycles terminate", () => {
  assert.throws(() => capture(request([dependency, dependency])), /duplicate dependency identity/);
  assert.throws(() => capture(request([dependency], [{todo_id: "todo_history", resume_when: "todo_done:todo_history"}])), /duplicate/);
  assert.deepEqual(capture(request([{...dependency, resume_when: "todo_done:todo_history"}])).records,
    [{index: 0, role: "agent"}]);
});
