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

test("empty next_agent_todo preserves legacy absence semantics", () => {
  const empty = resolveTodoCompletionPolicy(
    request({
      next_agent_todo: "",
      next_continuation_policy: "same_agent_non_delivery",
    }),
  );
  assert.equal(empty.effective_next_claimed_by, null);

  assert.throws(
    () =>
      resolveTodoCompletionPolicy(
        request({ next_agent_todo: "", next_claimed_by: "agent-b" }),
      ),
    /--next-claimed-by requires --next-agent-todo/,
  );
  assert.throws(
    () =>
      resolveTodoCompletionPolicy(
        request({ next_agent_todo: "", next_excluded_agents: ["agent-b"] }),
      ),
    /--next-excluded-agent requires --next-agent-todo/,
  );

  const whitespaceOnly = resolveTodoCompletionPolicy(
    request({
      next_agent_todo: " ",
      next_continuation_policy: "same_agent_non_delivery",
    }),
  );
  assert.equal(whitespaceOnly.effective_next_claimed_by, "agent-a");
});

test("agent identity normalization matches the Python Unicode contract", () => {
  const pythonWhitespaceCodePoints = [
    0x0009, 0x000a, 0x000b, 0x000c, 0x000d, 0x001c, 0x001d, 0x001e,
    0x001f, 0x0020, 0x0085, 0x00a0, 0x1680, 0x2000, 0x2001, 0x2002,
    0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a,
    0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
  ];
  for (const codePoint of pythonWhitespaceCodePoints) {
    const separator = String.fromCodePoint(codePoint);
    const result = resolveTodoCompletionPolicy(
      request({
        claimed_by: `agent${separator}a`,
        registered_agents: [`agent${separator}a`, "agent-b"],
        next_agent_todo: "Continue.",
        next_claimed_by: `agent${separator}b`,
        next_excluded_agents: [`agent${separator}a`],
      }),
    );
    assert.equal(result.effective_claimed_by, "agent-a");
    assert.deepEqual(result.registered_agents, ["agent-a", "agent-b"]);
    assert.equal(result.effective_next_claimed_by, "agent-b");
    assert.deepEqual(result.effective_next_excluded_agents, ["agent-a"]);

    const continuation = resolveTodoCompletionPolicy(
      request({
        next_agent_todo: "Continue.",
        next_continuation_policy:
          `${separator}same_agent_non_delivery${separator}`,
      }),
    );
    assert.equal(continuation.effective_next_claimed_by, "agent-a");
    assert.throws(
      () =>
        resolveTodoCompletionPolicy(
          request({ self_merged: true, evidence: separator }),
        ),
      /--self-merged requires --evidence/,
    );
  }

  for (const field of [
    { claimed_by: "\ufeffagent-a" },
    { registered_agents: ["\ufeffagent-a", "agent-b"] },
    { next_agent_todo: "Continue.", next_claimed_by: "\ufeffagent-b" },
    { next_agent_todo: "Continue.", next_excluded_agents: ["\ufeffagent-a"] },
  ]) {
    assert.throws(
      () => resolveTodoCompletionPolicy(request(field)),
      /must be a public-safe (?:registered )?agent id|must contain public-safe agent tokens/,
    );
  }

  const bomContinuation = resolveTodoCompletionPolicy(
    request({
      next_agent_todo: "Continue.",
      next_continuation_policy: "\ufeffsame_agent_non_delivery\ufeff",
    }),
  );
  assert.equal(bomContinuation.effective_next_claimed_by, null);
  const bomEvidence = resolveTodoCompletionPolicy(
    request({ self_merged: true, evidence: "\ufeff" }),
  );
  assert.equal(bomEvidence.self_merged, true);
});
