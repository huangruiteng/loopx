import { fetchCompletedTodos } from "../src/data/chat.js";

function equal(actual: unknown, expected: unknown) {
  if (actual !== expected) throw new Error(`Expected ${String(expected)}, received ${String(actual)}`);
}

async function rejects(request: Promise<unknown>) {
  try {
    await request;
  } catch {
    return;
  }
  throw new Error("Expected response validation to reject");
}

const originalFetch = globalThis.fetch;
const payload = {
  ok: true,
  goal_id: "test-goal",
  scope: "active_completed_advancement",
  total: 2,
  next_offset: null,
  items: [{ todo_id: "todo_first", text: "Completed work", status: "done", priority: null,
    claimed_by: null, task_class: "advancement_task" }],
};
try {
  globalThis.fetch = async (input) => {
    const url = new URL(String(input), "http://localhost");
    equal(url.pathname, "/api/chat/todos/completed");
    equal(url.searchParams.get("goal_id"), "test-goal");
    equal(url.searchParams.get("agent_id"), "worker");
    equal(url.searchParams.get("offset"), "1");
    return new Response(JSON.stringify(payload));
  };
  const result = await fetchCompletedTodos("test-goal", "worker", 1);
  equal(result.total, 2);
  equal(result.items.length, 1);
  equal(result.next_offset, null);
  globalThis.fetch = async () => new Response(JSON.stringify({ ...payload, goal_id: "other-goal" }));
  await rejects(fetchCompletedTodos("test-goal"));
  globalThis.fetch = async () => new Response("<html>not an API response</html>");
  await rejects(fetchCompletedTodos("test-goal"));
  globalThis.fetch = async () => new Response(JSON.stringify({ error: "unavailable" }), { status: 503 });
  await rejects(fetchCompletedTodos("test-goal"));
} finally {
  globalThis.fetch = originalFetch;
}
console.log("completed task response contracts passed");
