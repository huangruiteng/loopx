import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveTodoCompletionPolicy,
  TODO_COMPLETION_POLICY_REQUEST_SCHEMA,
} from "../../loopx/control_plane/todos/completion_policy.ts";

function request(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: TODO_COMPLETION_POLICY_REQUEST_SCHEMA,
    goal_id: "goal-example",
    agent_model: "peer_v1",
    claimed_by: "agent-a",
    registered_agents: ["agent-a", "agent-b"],
    next_claimed_by: null,
    next_agent_todo: null,
    next_continuation_policy: null,
    next_excluded_agents: [],
    self_merged: false,
    evidence: null,
    linked_successors: [],
    ...overrides,
  };
}

test("same-agent continuation and linked-successor selection are TS-owned", () => {
  const result = resolveTodoCompletionPolicy(
    request({
      next_agent_todo: "Continue the bounded migration.",
      next_continuation_policy: "same_agent_non_delivery",
      next_excluded_agents: ["AGENT-B", "agent-b"],
      linked_successors: [
        { todo_id: "todo_user", role: "user", status: "open" },
        { todo_id: "todo_done", role: "agent", status: "done" },
        { todo_id: "todo_open", role: "agent", status: "open" },
        { todo_id: "todo_later", role: "agent", status: null },
      ],
    }),
  );

  assert.deepEqual(result, {
    schema_version: "loopx_todo_completion_policy_result_v0",
    effective_claimed_by: "agent-a",
    registered_agents: ["agent-a", "agent-b"],
    effective_next_claimed_by: "agent-a",
    effective_next_excluded_agents: ["agent-b"],
    self_merged: false,
    linked_successor_id: "todo_open",
  });
});
test("registration, exclusion, and self-merge invariants fail closed", () => {
  assert.throws(
    () => resolveTodoCompletionPolicy(request({ claimed_by: "agent-c" })),
    /claimed_by='agent-c' is not registered for goal 'goal-example'; registered_agents=agent-a, agent-b/,
  );
  assert.throws(
    () =>
      resolveTodoCompletionPolicy(
        request({
          next_agent_todo: "Continue.",
          next_claimed_by: "agent-b",
          next_excluded_agents: ["agent-b"],
        }),
      ),
    /next_claimed_by='agent-b' cannot also appear in next_excluded_agents/,
  );
  assert.throws(
    () => resolveTodoCompletionPolicy(request({ self_merged: true })),
    /--self-merged requires --evidence/,
  );
  assert.throws(
    () =>
      resolveTodoCompletionPolicy(
        request({ next_claimed_by: "agent-b" }),
      ),
    /--next-claimed-by requires --next-agent-todo/,
  );
  assert.throws(
    () =>
      resolveTodoCompletionPolicy(
        request({ agent_model: "hierarchy_v2" }),
      ),
    /coordination.agent_model must be peer_v1/,
  );
});
