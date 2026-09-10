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

test("duplicate identities cannot be selected by storage order; archived cycles terminate", () => {
  assert.throws(() => capture(request([dependency, dependency])), /duplicate dependency identity/);
  assert.throws(() => capture(request([dependency], [{todo_id: "todo_history", resume_when: "todo_done:todo_history"}])), /duplicate/);
  assert.deepEqual(capture(request([{...dependency, resume_when: "todo_done:todo_history"}])).records,
    [{index: 0, role: "agent"}]);
});
