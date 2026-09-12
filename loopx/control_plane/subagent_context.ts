/** multi_subagent owns its workflow guidance; the hook mechanism stays generic. */
import { AGENT_CONTEXT_PHASES, projectAgentContext, type AgentContextProvider } from "./agent_context.ts";
import type { JsonObject } from "./effect_program.ts";
import { jsonObject, requireJsonObject } from "./runtime_decode.ts";

export const subagentContextProvider: AgentContextProvider = {
  hookId: "multi_subagent.coordinator", capabilityId: "multi_subagent", revision: "v2",
  phases: AGENT_CONTEXT_PHASES,
  produce(input, config) {
    const guidance = {
      before_plan: [
        "For read-heavy tasks, prefer parallel delegation of multiple fresh, independent evidence questions, including within one Todo, up to the configured child limit. Actively look for useful splits before keeping the research serial; avoid duplicate reads or concurrency for its own sake.",
        "For native child tools, read loopx agent-context with the current --goal-id and --agent-id at --phase before_delegate and --phase after_delegate_result. These read-only calls do not start turns or spend quota.",
        "Reserve a distinct, decision-relevant evidence question for the coordinator to investigate while children work, when useful independent work exists. Integration and child review do not replace that investigation. Wait only when remaining useful work depends on child results; do not invent busywork.",
      ],
      before_delegate: [
        "Give each child a bounded question, sources, read/write limits, expected evidence and stopping condition. Identify the coordinator's concurrent question and dependencies; reuse prior findings and avoid duplicating the children's reads. If no independent work remains, explain the dependency rather than forcing a split.",
        "Explicitly pass the configured model and reasoning effort when the host supports them. Check host availability; never silently substitute. Preferences are not execution receipts.",
      ],
      after_delegate_result: [
        "Check returned sources, omissions and contradictions against the question. Missing or rejected receipts do not establish completed work.",
        "Verify decisive sources and record accept/defer/reject with reasons; link accepted evidence to the plan and deliverable. Revisit uncovered questions using both coordinator and child findings. Waiting on one question need not block other useful research. Run parent validation before writeback; opinions are not independent evidence.",
      ],
    }[input.phase];
    const facts: JsonObject = {
      max_children: config.max_children,
      model_preference: jsonObject(config.model_config),
    };
    const count = input.observations.child_count;
    if (Number.isInteger(count) && Number(count) >= 0) facts.child_count = count;
    if (input.phase === "after_delegate_result") {
      const counts = jsonObject(input.observations.reconciliation_counts);
      facts.receipt_observation = counts ? "host_reconciled" : "not_supplied";
      if (counts) facts.reconciliation_counts = Object.fromEntries(
        Object.entries(counts).filter(([key, item]) =>
          /^[a-z_]{1,40}$/u.test(key) && Number.isInteger(item) && Number(item) >= 0),
      );
    }
    return { guidance, facts, source_refs: [
      "goal_boundary.orchestration", "docs/integrations/codex-subagent-orchestration.md",
    ] };
  },
};

export function evaluateSubagentContext(value: unknown): JsonObject | null {
  const input = requireJsonObject(value, "subagent context");
  const policy = jsonObject(input.orchestration) ?? {};
  const enabled = policy.mode === "multi_subagent" && policy.spawn_allowed === true
    && Number.isInteger(policy.max_children) && Number(policy.max_children) > 0;
  return projectAgentContext({
    phase: input.phase, scope: input.scope, observations: input.observations ?? {},
    capabilities: { multi_subagent: { ...policy, enabled } },
  }, [subagentContextProvider]);
}


export function describeSubagentContext(): JsonObject {
  return { supported_phases: [...subagentContextProvider.phases],
    target: "coordinator", activation: "with_capability", receipt_required: true };
}
