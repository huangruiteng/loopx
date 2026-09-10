import assert from "node:assert/strict";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { productionScaleCoordinationFixture } from "./production_scale_coordination_fixture.ts";
import { monitorSuccessorIntent, planMonitorSuccessor, MONITOR_SUCCESSOR_REQUEST_SCHEMA } from "../../loopx/control_plane/scheduler/monitor_successor.ts";

const intent = {material_change: true, next_agent_todo: "Validate the transition.", next_action_kind: "validate"};
const plan = (extra = {}, source_task_repository: string | null = null) => planMonitorSuccessor({
  schema_version: MONITOR_SUCCESSOR_REQUEST_SCHEMA, todo_id: "todo_monitor", result_hash: "revision-a",
  source_task_repository, intent: {...intent, ...extra},
});

test("one successor plan preserves explicit execution and user-decision semantics", () => {
  const result = plan({next_action_kind: "VALIDATE", next_claimed_by: "Agent A",
    next_required_capabilities: ["file--write", "network read", "file--write"]});
  assert.deepEqual(result.agent_route, {action_kind: "validate", task_repository: null,
    required_capabilities: ["file__write", "network_read"], continuation_policy: "independent_handoff",
    claimed_by: "agent-a", target_key: "monitor-successor:todo_monitor:5189357b78fc8ba5"});
  for (const taskClass of ["user_action", "user_gate"]) {
    const normalized = monitorSuccessorIntent({material_change: true, next_user_todo: "Review the transition.", next_user_task_class: taskClass});
    assert.equal(normalized.next_user_task_class, taskClass);
    assert.equal(normalized.next_agent_todo, null);
  }
});

test("invalid successor intent is rejected as a whole, not partly normalized away", () => {
  for (const invalid of [
    {next_required_capabilities: ["filesystem_write", "bad/capability"]},
    {next_claimed_by: "bad/actor"}, {next_action_kind: "not an action"},
    {next_continuation_policy: "primary_review"}, {material_change: false},
    {next_user_todo: "Approve"}, {next_user_task_class: "user_gate"},
  ]) assert.throws(() => plan(invalid));
  assert.throws(() => monitorSuccessorIntent({material_change: false, next_claimed_by: "agent-a"}), /require --next-agent-todo/);
  assert.throws(() => plan({}, "git:github.com/example/source"), /require explicit --next-task-repository/);
});

test("repository transport aliases match the retained node-independent codec", () => {
  const inputs = ["git:github.com/example/repo", "https://github.com/example/repo.git",
    "git@github.com:example/repo.git", "ssh://git@github.com/example/repo.git",
    "http://github.com:80/example/repo/", "https://github.com:22/example/repo",
    "ssh://git@github.com:443/example/repo", "ssh://git@github.com:8022/example//repo.git",
    "git://github.com:80/example/repo", "https://GITHUB.com/example/repo.git"];
  const python = spawnSync("python", ["-c", "import json,sys; from loopx.repository_identity import normalize_repository_identity; print(json.dumps([normalize_repository_identity(x) for x in json.load(sys.stdin)]))"],
    {input: JSON.stringify(inputs), encoding: "utf8"});
  assert.equal(python.status, 0, python.stderr);
  const expected = JSON.parse(python.stdout);
  for (const [index, input] of inputs.entries()) {
    const actual = monitorSuccessorIntent({...intent, next_task_repository: input}).next_task_repository;
    assert.equal(actual, expected[index]);
    assert.equal(monitorSuccessorIntent({...intent, next_task_repository: actual}).next_task_repository, actual);
  }
});

test("unsafe repository routes cannot be silently repaired by URL parsing", () => {
  for (const repo of ["https://github.com/example/../other", "git:github.com/example/./repo",
    "https://user:password@example.invalid/repo", "https://example.invalid/repo?credential=value",
    "https://example.invalid/repo#fragment", "file:///repo", "https://example.invalid/", "not a repository",
    "https://example.invalid\\other/repo", "https://example.invalid/a%2fb", "https://example.invalid/a b"]) {
    assert.throws(() => plan({next_task_repository: repo}));
  }
});

test("production-scale monitor route planning is read-only and preserves target separation", () => {
  const fixture = productionScaleCoordinationFixture("goal-route-fixture");
  const original = structuredClone(fixture.projection);
  const todos = fixture.projection.todos as Record<string, unknown>[];
  const monitors = todos.filter(todo => todo.task_class === "continuous_monitor");
  assert.equal(monitors.length, 63);
  const targets = new Set<unknown>();
  for (const monitor of monitors) {
    // A route can be described for historical context, but is never a lifecycle grant.
    const result = planMonitorSuccessor({schema_version: MONITOR_SUCCESSOR_REQUEST_SCHEMA,
      todo_id: monitor.todo_id, result_hash: "same-material-hash",
      source_task_repository: monitor.task_repository ?? null,
      intent: {...intent, next_task_repository: monitor.task_repository ?? null,
        next_required_capabilities: monitor.required_capabilities ?? []}});
    targets.add((result.agent_route as Record<string, unknown>).target_key);
  }
  assert.equal(targets.size, monitors.length);
  assert.equal(todos.length, fixture.expected_initial_todo_count);
  assert.equal((fixture.projection.leases as unknown[]).length, fixture.expected_current_lease_count);
  assert.deepEqual(fixture.projection, original);
});
