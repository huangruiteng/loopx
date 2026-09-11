import assert from "node:assert/strict";
import test from "node:test";
import { AGENT_CONTEXT_PHASES, projectAgentContext, type AgentContextProvider } from "../../loopx/control_plane/agent_context.ts";
import { evaluateSubagentContext } from "../../loopx/control_plane/subagent_context.ts";

const scope = { goal_id: "goal-a", agent_id: "parent", todo_id: "todo-a" };
const policy = { mode: "multi_subagent", spawn_allowed: true, max_children: 2,
  model_config: { model: "example-small", reasoning_effort: "max" } };
const provider: AgentContextProvider = {
  hookId: "example.context", capabilityId: "example", revision: "v1",
  phases: AGENT_CONTEXT_PHASES,
  produce: () => ({ guidance: ["Inspect original evidence."], facts: {}, source_refs: ["core"] }),
};
const input = { phase: "before_plan", scope, capabilities: { example: { enabled: true } } };

test("disabled capability never calls provider or emits context", () => {
  assert.equal(projectAgentContext({ ...input, capabilities: {} }, [{ ...provider,
    produce() { throw new Error("must not run"); } }]), null);
  for (const orchestration of [{}, { ...policy, spawn_allowed: false },
    { ...policy, mode: "default" }, { ...policy, max_children: 0 },
    { model_config: policy.model_config }]) {
    assert.equal(evaluateSubagentContext({ phase: "before_plan", scope, orchestration }), null);
  }
});

test("all phases supply coordinator guidance without claiming adoption or execution", () => {
  for (const phase of AGENT_CONTEXT_PHASES) {
    const packet = evaluateSubagentContext({ phase, scope, orchestration: policy })!;
    assert.equal(packet.phase, phase);
    assert.equal(packet.delivery, "projected");
    assert.equal(packet.target, "coordinator");
    assert.equal(packet.authority, "guidance_only");
    const contribution = (packet.contributions as Record<string, any>[])[0];
    assert.deepEqual(contribution.facts.model_preference, policy.model_config);
    if (phase === "after_delegate_result") assert.equal(contribution.facts.receipt_observation, "not_supplied");
  }
});

test("stable context ids bind phase, scope, content and policy revision", () => {
  const id = (value: any) => value.contributions[0].context_id;
  const original = projectAgentContext(input, [provider]);
  assert.equal(id(original), id(projectAgentContext(input, [provider])));
  for (const patch of [{ phase: "before_delegate" }, { scope: { ...scope, goal_id: "goal-b" } }]) {
    assert.notEqual(id(original), id(projectAgentContext({ ...input, ...patch }, [provider])));
  }
  assert.notEqual(id(original), id(projectAgentContext(input, [{ ...provider, revision: "v2" }])));
});

test("provider failures, forged control fields and oversize context are isolated", () => {
  for (const produce of [
    () => { throw new Error("private credential text"); },
    () => ({ ...provider.produce({} as any, {}), scope: { goal_id: "other" } }),
    () => ({ ...provider.produce({} as any, {}), action: "approve" }),
    () => ({ ...provider.produce({} as any, {}), facts: { text: "x".repeat(4096) } }),
    () => ({ ...provider.produce({} as any, {}), guidance: [] }),
  ]) {
    const packet = projectAgentContext(input, [
      { ...provider, hookId: "example.bad", produce }, provider,
    ])!;
    assert.equal((packet.contributions as any[]).length, 1);
    assert.equal((packet.failures as any[]).length, 1);
    assert.ok(!JSON.stringify(packet).includes("private credential"));
    assert.deepEqual(packet.scope, scope);
  }
});

test("one provider cannot mutate the dispatcher or another provider inputs", () => {
  const packet = projectAgentContext(input, [{ ...provider, hookId: "example.mutate",
    produce(value) { value.scope.goal_id = "other"; value.capabilities.example = null;
      return provider.produce(value, {}); } }, provider])!;
  assert.deepEqual(packet.scope, scope);
  assert.equal((packet.contributions as any[]).length, 2);
  assert.deepEqual(input.scope, scope);
});

test("aggregate budget and duplicate producer ids remain bounded", () => {
  const packet = projectAgentContext(input, Array.from({ length: 40 }, (_, i) => ({
    ...provider, hookId: `example.${i}`, produce: () => ({
      guidance: ["Evidence."], facts: { text: "中".repeat(300) }, source_refs: ["core"],
    }),
  })))!;
  assert.ok(Buffer.byteLength(JSON.stringify(packet)) <= 3072);
  assert.ok((packet.failures as any[]).length > 0);
  const duplicate = projectAgentContext(input, [provider, provider])!;
  assert.equal((duplicate.contributions as any[]).length, 1);
  assert.equal((duplicate.failures as any[]).length, 1);
});

test("unknown phases and missing coordinator scope fail before invoking a provider", () => {
  assert.throws(() => projectAgentContext({ ...input, phase: "after_execute" }, [provider]));
  assert.throws(() => projectAgentContext({ ...input, scope: {} }, [provider]));
});

test("return phase projects reconciliation counts without copying raw child material", () => {
  const packet = evaluateSubagentContext({ phase: "after_delegate_result", scope,
    orchestration: policy, observations: {
      reconciliation_counts: { planned: 2, observed: 1, incomplete: 1, bad: "secret" },
      child_response: "private original text",
    } })!;
  const facts = (packet.contributions as any[])[0].facts;
  assert.equal(facts.receipt_observation, "host_reconciled");
  assert.deepEqual(facts.reconciliation_counts, { planned: 2, observed: 1, incomplete: 1 });
  assert.ok(!JSON.stringify(packet).includes("private original text"));
});
